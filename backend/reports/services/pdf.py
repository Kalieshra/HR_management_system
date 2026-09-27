"""Payslip PDFs (`شرايط قبض`) rendered with WeasyPrint.

One strip per employee, sized so a page of them can be printed and cut, mirroring
the workbook's strip sheets. Arabic text needs a font with Arabic coverage —
the backend image installs `fonts-noto-core` for exactly this.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.files.base import ContentFile
from django.template.loader import render_to_string

from companies.models import ReportLanguage
from payroll.services.engine import quantize_display
from reports.models import ReportFile, ReportKind
from reports.services.generator import lines_for
from reports.services.layout import ARABIC_MONTHS

#: (PayrollLine field, Arabic label, English label) for the earnings block.
EARNING_ROWS = (
    ("base_salary", "الراتب", "Salary"),
    ("work_days_value", "قيمة ايام العمل", "Work days value"),
    ("overtime_value", "قيمة الاضافى", "Overtime"),
    ("leave_allowance_value", "قيمة بدل الاجازات", "Leave allowance"),
    ("bonus", "مكافأة", "Bonus"),
    ("other_earnings", "اخرى", "Other"),
    ("total_earnings", "اجمالى الاستحقاق", "Total earnings"),
)

DEDUCTION_ROWS = (
    ("late_value", "قيمة ساعات التأخير", "Late"),
    ("advances", "سلف", "Advances"),
    ("carried_advance", "سلفة مرحله", "Carried advance"),
    ("admin_penalty_value", "قيمة الجزاء الادارى", "Admin penalty"),
    ("fingerprint_penalty_value", "قيمة جزاء البصمه", "Fingerprint penalty"),
    ("unexcused_absence_value", "جزاء غياب بدون اذن", "Unexcused absence"),
    ("sick_value", "قيمة المرضى", "Sick"),
    ("insurance_and_tax", "تأمينات وضرائب", "Insurance & tax"),
    ("deviations", "الانحرافات", "Deviations"),
    ("shortage_custody", "عجز منتجات& عهدة", "Shortage / custody"),
    ("total_deductions", "اجمالى الاستقطاع", "Total deductions"),
)


def _money(value) -> str:
    return f"{quantize_display(Decimal(value or 0)):,.2f}"


def _rows(line, definitions, language: str) -> list[dict]:
    return [
        {"label": label_en if language == "en" else label_ar, "value": _money(getattr(line, field))}
        for field, label_ar, label_en in definitions
    ]


def build_context(period, lines, language: str) -> dict:
    is_arabic = language != ReportLanguage.EN
    month = ARABIC_MONTHS[period.month] if is_arabic else period.start_date.strftime("%B")
    title = (
        f"شرايط قبض {period.company.display_name} — {month} {period.year}"
        if is_arabic
        else f"{period.company.name_en or period.company.name_ar} payslips — {month} {period.year}"
    )

    return {
        "title": title,
        "language": "ar" if is_arabic else "en",
        "direction": "rtl" if is_arabic else "ltr",
        "amount_align": "left" if is_arabic else "right",
        "page_orientation": "portrait",
        "labels": {
            "earnings": "الاستحقاق" if is_arabic else "Earnings",
            "deductions": "الاستقطاع" if is_arabic else "Deductions",
            "net": "صافى الراتب" if is_arabic else "Net salary",
        },
        "slips": [
            {
                "line": line,
                "earnings": _rows(line, EARNING_ROWS, language),
                "deductions": _rows(line, DEDUCTION_ROWS, language),
                "net": _money(line.net_salary),
            }
            for line in lines
        ],
    }


def render_payslips(period, lines=None, language: str | None = None) -> bytes:
    """Render the payslip PDF for a period."""
    from weasyprint import HTML  # imported lazily: heavy native dependency

    language = language or period.company.report_language
    lines = lines if lines is not None else lines_for(period)
    html = render_to_string("reports/payslips.html", build_context(period, lines, language))
    return HTML(string=html).write_pdf()


def generate_payslips(period, user=None) -> ReportFile:
    content = render_payslips(period)
    name = f"{period.company.slug}-{period.year}-{period.month:02d}-payslips.pdf"

    report = ReportFile(
        company=period.company,
        period=period,
        kind=ReportKind.PDF,
        generated_by=user if getattr(user, "pk", None) else None,
    )
    report.file.save(name, ContentFile(content), save=True)
    return report
