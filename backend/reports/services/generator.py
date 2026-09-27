"""Generating and storing report files."""

from __future__ import annotations

from django.core.files.base import ContentFile

from companies.services import resolve_policy
from payroll.models import PayrollLine
from reports.models import ReportFile, ReportKind
from reports.services import excel


def lines_for(period):
    return list(
        PayrollLine.all_objects.filter(company=period.company, period=period).order_by(
            "branch_snapshot", "employee_code"
        )
    )


def generate_excel(period, user=None) -> ReportFile:
    """Build the workbook for a period and store it as a `ReportFile`."""
    company = period.company
    policy = resolve_policy(company, period.start_date)
    language = company.report_language

    content = excel.generate_workbook(period, lines_for(period), policy, language)
    name = excel.report_filename(company, period)

    report = ReportFile(
        company=company,
        period=period,
        kind=ReportKind.XLSX,
        generated_by=user if getattr(user, "pk", None) else None,
    )
    report.file.save(name, ContentFile(content), save=True)
    return report
