"""Company-level helpers shared by the API and the payroll engine."""

from __future__ import annotations

from datetime import date

from django.core.cache import cache

from companies.models import PayrollPolicy

POLICY_CACHE_TTL = 600  # 10 minutes


def policy_cache_key(company_id: int) -> str:
    return f"policy:{company_id}"


def resolve_policy(company, on_date: date) -> PayrollPolicy | None:
    """Newest policy effective on or before `on_date`, or None to use defaults."""
    return (
        PayrollPolicy.all_objects.filter(company=company, effective_from__lte=on_date)
        .order_by("-effective_from")
        .first()
    )


def current_policy(company) -> PayrollPolicy | None:
    """Today's policy, cached per company. Invalidated when a version is saved."""
    key = policy_cache_key(company.pk)
    cached = cache.get(key)
    if cached is not None:
        return cached if cached != "none" else None

    policy = resolve_policy(company, date.today())
    cache.set(key, policy or "none", POLICY_CACHE_TTL)
    return policy


def invalidate_policy_cache(company_id: int) -> None:
    cache.delete(policy_cache_key(company_id))


def delete_company_data(company) -> dict[str, int]:
    """Delete everything a company owns, then the company itself.

    `Employee.branch` and `PayrollLine.employee` are `PROTECT` on purpose — you
    should not be able to delete a branch with staff on it, or an employee with
    payroll history. That protection also blocks a plain `company.delete()`, so
    a genuine tenant teardown has to walk the graph leaves-first.
    """
    from attendance.models import DailyRecord
    from companies.models import Branch, PayrollPolicy
    from employees.models import Employee, SalaryHistory
    from payroll.models import Loan, MonthlyAdjustment, PayrollLine, Period
    from reports.models import ReportFile

    removed: dict[str, int] = {}
    # Leaves first: each model here is only referenced by the ones above it.
    for model in (
        ReportFile,
        PayrollLine,
        MonthlyAdjustment,
        Loan,
        DailyRecord,
        SalaryHistory,
        Employee,
        Period,
        Branch,
        PayrollPolicy,
    ):
        count, _details = model.all_objects.filter(company=company).delete()
        removed[model.__name__] = count

    company.delete()
    return removed
