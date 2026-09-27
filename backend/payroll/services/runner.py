"""Running, closing and reopening a payroll period."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from audit.services import record_audit
from companies.services import resolve_policy
from payroll.models import AdjustmentKind, Loan, MonthlyAdjustment, PayrollLine, PeriodStatus
from payroll.services import aggregate as agg
from payroll.services.engine import PolicyValues, calculate_line

ZERO = Decimal("0")

#: Above this many employees the calculation is handed to Celery.
ASYNC_THRESHOLD = 50


class PeriodClosedError(RuntimeError):
    """Raised on any attempt to modify a closed period."""


def _format_original(value) -> str:
    """The pre-override aggregate, as the review grid's tooltip shows it (2 dp)."""
    return str(Decimal(value).quantize(Decimal("0.01")))


def assert_period_open(period) -> None:
    if period.is_closed:
        raise PeriodClosedError(
            _("Period %(period)s is closed and cannot be modified.") % {"period": period}
        )


def materialise_loan_installments(period, user=None) -> int:
    """Create this month's `advance` adjustment for each running loan.

    Idempotent: re-running a calculation does not double-charge, because the
    loan's instalment row for the period is updated in place.
    """
    loans = Loan.all_objects.filter(
        company=period.company, is_active=True, remaining__gt=0
    ).select_related("employee")

    created = 0
    for loan in loans:
        amount = loan.installment_for(period.year, period.month)
        if amount <= 0:
            continue

        note = f"loan:{loan.pk}"
        adjustment, was_created = MonthlyAdjustment.all_objects.update_or_create(
            company=period.company,
            period=period,
            employee=loan.employee,
            kind=AdjustmentKind.ADVANCE,
            note=note,
            defaults={"amount": amount, "created_by": user},
        )
        if was_created:
            created += 1
        del adjustment
    return created


@transaction.atomic
def run_period(period, user=None) -> list[PayrollLine]:
    """Aggregate, calculate and upsert every `PayrollLine` for the period."""
    assert_period_open(period)

    policy = resolve_policy(period.company, period.start_date)
    policy_values = PolicyValues.from_policy(policy)

    materialise_loan_installments(period, user=user)

    employees = agg.active_employees_for(period)
    employee_ids = [employee.pk for employee in employees]

    attendance = agg.aggregate_attendance(period, employee_ids)
    adjustments = agg.aggregate_adjustments(period, employee_ids)

    existing = {
        line.employee_id: line
        for line in PayrollLine.all_objects.filter(company=period.company, period=period)
    }

    lines: list[PayrollLine] = []
    for employee in employees:
        values = agg.build_inputs(
            period,
            employee,
            attendance.get(employee.pk, {}),
            adjustments.get(employee.pk, {}),
            policy,
        )

        line = existing.get(employee.pk) or PayrollLine(
            company=period.company, period=period, employee=employee
        )

        # Manual overrides win over the aggregate, but we keep recording what
        # the aggregate *would* have been so the grid can show both.
        overrides = dict(line.overrides or {})
        for field_name in list(overrides):
            if field_name in values:
                overrides[field_name] = _format_original(values[field_name])
                values[field_name] = getattr(line, field_name)

        line.employee_code = employee.code
        line.employee_name = employee.display_name
        line.branch_snapshot = employee.branch.name_ar if employee.branch else ""
        line.job_title_snapshot = employee.job_title
        line.daily_hours = values["daily_hours"]
        line.base_salary = values["base_salary"]

        for field_name in agg.OVERRIDABLE_FIELDS:
            setattr(line, field_name, values.get(field_name, ZERO))

        result = calculate_line(agg.to_line_inputs(values), policy_values)
        for field_name, value in result.as_dict().items():
            setattr(line, field_name, value)

        line.overrides = overrides
        line.warnings = list(result.warnings)
        if not line.notes:
            line.notes = agg.collect_notes(period, employee.pk)

        lines.append(line)

    _save_lines(period, lines, existing)

    period.status = PeriodStatus.CALCULATED
    period.calculated_at = timezone.now()
    period.save(update_fields=["status", "calculated_at", "updated_at"])

    record_audit(
        company=period.company,
        user=user,
        action="calculate",
        instance=period,
        after={"lines": len(lines), "status": period.status},
    )
    return lines


def _save_lines(period, lines, existing) -> None:
    to_create = [line for line in lines if line.pk is None]
    to_update = [line for line in lines if line.pk is not None]

    if to_create:
        PayrollLine.all_objects.bulk_create(to_create)
    if to_update:
        fields = [
            "employee_code",
            "employee_name",
            "branch_snapshot",
            "job_title_snapshot",
            "daily_hours",
            "base_salary",
            *agg.OVERRIDABLE_FIELDS,
            "work_days_value",
            "overtime_value",
            "leave_allowance_value",
            "total_earnings",
            "late_value",
            "admin_penalty_value",
            "fingerprint_penalty_value",
            "unexcused_absence_value",
            "sick_value",
            "insurance_and_tax",
            "total_deductions",
            "net_salary",
            "overrides",
            "warnings",
            "notes",
            "updated_at",
        ]
        PayrollLine.all_objects.bulk_update(to_update, fields)

    # Employees who left the period's scope should not keep a stale line.
    keep = {line.employee_id for line in lines}
    stale = [line.pk for employee_id, line in existing.items() if employee_id not in keep]
    if stale:
        PayrollLine.all_objects.filter(pk__in=stale).delete()


@transaction.atomic
def close_period(period, user=None):
    """Freeze the period and draw down loan balances by what was charged."""
    if period.is_closed:
        raise PeriodClosedError(_("Period is already closed."))

    before = {"status": period.status}
    period.status = PeriodStatus.CLOSED
    period.closed_at = timezone.now()
    period.closed_by = user
    period.save(update_fields=["status", "closed_at", "closed_by", "updated_at"])

    _apply_loan_repayments(period)

    record_audit(
        company=period.company,
        user=user,
        action="close",
        instance=period,
        before=before,
        after={"status": period.status},
    )
    return period


def _apply_loan_repayments(period) -> None:
    loans = Loan.all_objects.filter(company=period.company, is_active=True, remaining__gt=0)
    for loan in loans:
        charged = loan.installment_for(period.year, period.month)
        if charged <= 0:
            continue
        loan.remaining = max(ZERO, loan.remaining - charged)
        loan.is_active = loan.remaining > 0
        loan.save(update_fields=["remaining", "is_active", "updated_at"])


@transaction.atomic
def reopen_period(period, user=None):
    """Unfreeze a closed period (company admins only) and restore loan balances."""
    if not period.is_closed:
        raise PeriodClosedError(_("Period is not closed."))

    before = {"status": period.status}
    period.status = PeriodStatus.CALCULATED
    period.closed_at = None
    period.closed_by = None
    period.save(update_fields=["status", "closed_at", "closed_by", "updated_at"])

    _reverse_loan_repayments(period)

    record_audit(
        company=period.company,
        user=user,
        action="reopen",
        instance=period,
        before=before,
        after={"status": period.status},
    )
    return period


def _reverse_loan_repayments(period) -> None:
    loans = Loan.all_objects.filter(company=period.company)
    for loan in loans:
        charged = min(loan.monthly_installment, loan.total - loan.remaining)
        if charged <= 0:
            continue
        loan.remaining = min(loan.total, loan.remaining + charged)
        loan.is_active = loan.remaining > 0
        loan.save(update_fields=["remaining", "is_active", "updated_at"])
