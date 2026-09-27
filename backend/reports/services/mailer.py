"""Emailing the monthly report."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from companies.models import ReportLanguage
from payroll.services.engine import quantize_display
from reports.services.generator import lines_for
from reports.services.layout import ARABIC_MONTHS

SUMMARY_ROWS = (
    ("base_salary", "اجمالى الرواتب", "Total salaries"),
    ("total_earnings", "اجمالى الاستحقاق", "Total earnings"),
    ("total_deductions", "اجمالى الاستقطاع", "Total deductions"),
    ("net_salary", "صافى الرواتب", "Net payroll"),
)


def _month_label(period, is_arabic: bool) -> str:
    return (
        f"{ARABIC_MONTHS[period.month]} {period.year}"
        if is_arabic
        else f"{period.start_date.strftime('%B')} {period.year}"
    )


def _totals(period) -> dict[str, Decimal]:
    totals = dict.fromkeys((field for field, _, _ in SUMMARY_ROWS), Decimal(0))
    for line in lines_for(period):
        for field in totals:
            totals[field] += Decimal(getattr(line, field))
    return totals


def send_monthly_report(period, report, recipients: list[str] | None = None) -> int:
    """Email the generated workbook to the company's report recipients."""
    company = period.company
    recipients = recipients or list(company.report_emails or [])
    if not recipients:
        return 0

    is_arabic = company.report_language != ReportLanguage.EN
    month = _month_label(period, is_arabic)
    totals = _totals(period)

    subject = (
        f"تقرير الرواتب — {company.display_name} — {month}"
        if is_arabic
        else f"Payroll report — {company.name_en or company.name_ar} — {month}"
    )
    context = {
        "subject": subject,
        "language": "ar" if is_arabic else "en",
        "direction": "rtl" if is_arabic else "ltr",
        "amount_align": "left" if is_arabic else "right",
        "intro": (
            "تجد المرفق تقرير الرواتب الشهري."
            if is_arabic
            else "The monthly payroll report is attached."
        ),
        "footer": (
            "تم إرسال هذه الرسالة تلقائيًا من نظام إدارة الموارد البشرية."
            if is_arabic
            else "Sent automatically by HR Management System."
        ),
        "rows": [
            {
                "label": label_ar if is_arabic else label_en,
                "value": f"{quantize_display(totals[field]):,.2f}",
            }
            for field, label_ar, label_en in SUMMARY_ROWS
        ],
    }

    html = render_to_string("email/monthly_report.html", context)
    text = "\n".join(f"{row['label']}: {row['value']}" for row in context["rows"])

    message = EmailMultiAlternatives(
        subject=subject,
        body=f"{context['intro']}\n\n{text}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
    )
    message.attach_alternative(html, "text/html")

    report.file.open("rb")
    try:
        message.attach(
            report.file.name.rsplit("/", 1)[-1],
            report.file.read(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    finally:
        report.file.close()

    sent = message.send(fail_silently=False)

    report.emailed_to = recipients
    report.emailed_at = timezone.now()
    report.save(update_fields=["emailed_to", "emailed_at", "updated_at"])
    return sent


def send_close_reminder(company, period_year: int, period_month: int) -> int:
    """Nudge the company when report day arrives and the month isn't closed."""
    recipients = list(company.report_emails or [])
    if not recipients:
        return 0

    is_arabic = company.report_language != ReportLanguage.EN
    month = (
        f"{ARABIC_MONTHS[period_month]} {period_year}"
        if is_arabic
        else f"{period_month}/{period_year}"
    )
    subject = (
        f"تذكير: لم يتم إغلاق شهر {month}"
        if is_arabic
        else f"Reminder: {month} payroll is not closed yet"
    )
    context = {
        "subject": subject,
        "language": "ar" if is_arabic else "en",
        "direction": "rtl" if is_arabic else "ltr",
        "intro": (
            "لم يتم إغلاق الشهر بعد، لذلك لم يتم إرسال التقرير."
            if is_arabic
            else "The month is still open, so no report was sent."
        ),
        "cta": "فتح مراجعة الرواتب" if is_arabic else "Open the payroll review",
        "link": f"{settings.FRONTEND_ORIGIN}/{'ar' if is_arabic else 'en'}/payroll",
    }

    html = render_to_string("email/reminder.html", context)
    message = EmailMultiAlternatives(
        subject=subject,
        body=f"{context['intro']} {context['link']}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
    )
    message.attach_alternative(html, "text/html")
    return message.send(fail_silently=False)
