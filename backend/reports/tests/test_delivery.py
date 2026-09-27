"""Emailing the monthly report, by hand and on a schedule."""

import datetime as dt
from decimal import Decimal

import pytest
from django.core import mail

from core.factories import (
    BranchFactory,
    CompanyFactory,
    EmployeeFactory,
    PayrollPolicyFactory,
    PeriodFactory,
)
from payroll.models import PeriodStatus
from payroll.services.runner import close_period, run_period
from reports.models import ReportFile
from reports.services.generator import generate_excel
from reports.services.mailer import send_monthly_report
from reports.tasks import send_scheduled_reports

pytestmark = pytest.mark.django_db

D = Decimal


@pytest.fixture
def closed_period():
    company = CompanyFactory(
        slug="mail-co", report_emails=["finance@demo.test", "owner@demo.test"], report_day=5
    )
    PayrollPolicyFactory(company=company)
    branch = BranchFactory(company=company)
    EmployeeFactory(company=company, branch=branch, base_salary=D("6000"))

    period = PeriodFactory(company=company)
    run_period(period)
    close_period(period)
    return period


def test_report_email_carries_the_workbook_as_an_attachment(closed_period):
    report = generate_excel(closed_period)
    mail.outbox.clear()

    sent = send_monthly_report(closed_period, report)

    assert sent == 1
    message = mail.outbox[0]
    assert message.to == ["finance@demo.test", "owner@demo.test"]
    assert len(message.attachments) == 1
    filename, _content, mimetype = message.attachments[0]
    assert filename.endswith(".xlsx")
    assert "spreadsheetml" in mimetype


def test_the_email_has_an_arabic_html_alternative(closed_period):
    report = generate_excel(closed_period)
    mail.outbox.clear()

    send_monthly_report(closed_period, report)

    html = mail.outbox[0].alternatives[0][0]
    assert 'dir="rtl"' in html
    assert "صافى الرواتب" in html


def test_sending_records_who_received_it(closed_period):
    report = generate_excel(closed_period)

    send_monthly_report(closed_period, report)

    report.refresh_from_db()
    assert report.emailed_at is not None
    assert report.emailed_to == ["finance@demo.test", "owner@demo.test"]


def test_a_company_without_recipients_is_not_emailed(closed_period):
    closed_period.company.report_emails = []
    closed_period.company.save()
    report = generate_excel(closed_period)
    mail.outbox.clear()

    assert send_monthly_report(closed_period, report) == 0
    assert mail.outbox == []


def test_scheduled_task_emails_the_report_when_last_month_is_closed(closed_period, monkeypatch):
    """Beat runs on `report_day`; the previous month must be the one sent."""
    company = closed_period.company
    company.report_day = 15
    company.save()

    # Pretend today is the 15th of the month after the period.
    today = dt.date(closed_period.year, closed_period.month, 1) + dt.timedelta(days=40)
    today = today.replace(day=15)
    monkeypatch.setattr("reports.tasks.timezone.localdate", lambda: today)

    mail.outbox.clear()
    result = send_scheduled_reports()

    assert result["sent"] == 1
    assert result["reminded"] == 0
    assert len(mail.outbox) == 1
    assert mail.outbox[0].attachments


def test_scheduled_task_sends_a_reminder_when_the_month_is_still_open(closed_period, monkeypatch):
    period = closed_period
    period.status = PeriodStatus.CALCULATED
    period.save()

    company = period.company
    company.report_day = 15
    company.save()

    today = dt.date(period.year, period.month, 1) + dt.timedelta(days=40)
    today = today.replace(day=15)
    monkeypatch.setattr("reports.tasks.timezone.localdate", lambda: today)

    mail.outbox.clear()
    result = send_scheduled_reports()

    assert result["sent"] == 0
    assert result["reminded"] == 1
    assert not mail.outbox[0].attachments
    assert "لم يتم إغلاق" in mail.outbox[0].subject


def test_scheduled_task_ignores_companies_whose_day_is_not_today(closed_period, monkeypatch):
    closed_period.company.report_day = 3
    closed_period.company.save()
    monkeypatch.setattr("reports.tasks.timezone.localdate", lambda: dt.date(2026, 4, 15))

    mail.outbox.clear()
    result = send_scheduled_reports()

    assert result == {"sent": 0, "reminded": 0, "skipped": 0}
    assert mail.outbox == []


def test_generating_twice_keeps_both_files(closed_period):
    first = generate_excel(closed_period)
    second = generate_excel(closed_period)

    assert first.pk != second.pk
    assert ReportFile.objects.for_company(closed_period.company).count() == 2
