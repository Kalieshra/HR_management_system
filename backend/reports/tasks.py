"""Celery tasks for report generation and the monthly send."""

from __future__ import annotations

import datetime as dt

from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone

from companies.models import Company
from payroll.models import Period, PeriodStatus
from reports.services.generator import generate_excel
from reports.services.mailer import send_close_reminder, send_monthly_report
from reports.services.pdf import generate_payslips

logger = get_task_logger(__name__)


@shared_task(name="reports.generate_excel")
def generate_excel_task(period_id: int, user_id: int | None = None) -> dict:
    period = Period.all_objects.select_related("company").get(pk=period_id)
    report = generate_excel(period, user_id and _user(user_id))
    return {"report_id": report.pk, "file": report.file.name}


@shared_task(name="reports.generate_payslips")
def generate_payslips_task(period_id: int, user_id: int | None = None) -> dict:
    period = Period.all_objects.select_related("company").get(pk=period_id)
    report = generate_payslips(period, user_id and _user(user_id))
    return {"report_id": report.pk, "file": report.file.name}


@shared_task(name="reports.email_report")
def email_report_task(period_id: int, report_id: int | None = None) -> dict:
    from reports.models import ReportFile, ReportKind

    period = Period.all_objects.select_related("company").get(pk=period_id)
    report = (
        ReportFile.all_objects.get(pk=report_id)
        if report_id
        else ReportFile.all_objects.filter(
            company=period.company, period=period, kind=ReportKind.XLSX
        )
        .order_by("-generated_at")
        .first()
    )
    if report is None:
        report = generate_excel(period)

    sent = send_monthly_report(period, report)
    return {"report_id": report.pk, "sent": sent}


@shared_task(name="reports.send_scheduled_reports")
def send_scheduled_reports() -> dict:
    """Beat task: every company whose `report_day` is today gets last month's report.

    Closed month -> generate and email the workbook. Still open -> email a
    reminder instead, so nobody silently misses payroll.
    """
    today = timezone.localdate()
    previous = today.replace(day=1) - dt.timedelta(days=1)

    sent = reminded = skipped = 0
    for company in Company.objects.filter(is_active=True, report_day=today.day):
        if not company.report_emails:
            skipped += 1
            continue

        period = Period.all_objects.filter(
            company=company, year=previous.year, month=previous.month
        ).first()

        if period is not None and period.status == PeriodStatus.CLOSED:
            report = generate_excel(period)
            send_monthly_report(period, report)
            sent += 1
        else:
            send_close_reminder(company, previous.year, previous.month)
            reminded += 1

    logger.info("scheduled reports: sent=%s reminded=%s skipped=%s", sent, reminded, skipped)
    return {"sent": sent, "reminded": reminded, "skipped": skipped}


def _user(user_id: int):
    from accounts.models import User

    return User.objects.filter(pk=user_id).first()
