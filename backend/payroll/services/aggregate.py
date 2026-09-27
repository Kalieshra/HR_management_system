"""Turn a month of daily records and adjustments into engine inputs.

This is the bridge between what companies type in every day and the pure
arithmetic in `engine.py`. Company admins can override any aggregated input on
the monthly review grid; overrides survive recalculation and are kept in
`PayrollLine.overrides` as {field: originally_aggregated_value}.
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Q, Sum

from attendance.models import AttendanceStatus, DailyRecord
from employees.models import Employee
from payroll.models import AdjustmentKind, MonthlyAdjustment
from payroll.services.engine import LineInputs

ZERO = Decimal("0")

#: MonthlyAdjustment kind -> the LineInputs field it feeds.
ADJUSTMENT_TO_FIELD = {
    AdjustmentKind.BONUS: "bonus",  # M
    AdjustmentKind.OTHER_EARNING: "other_earnings",  # N
    AdjustmentKind.ADVANCE: "advances",  # R
    AdjustmentKind.CARRIED_ADVANCE: "carried_advance",  # S
    AdjustmentKind.DEVIATION: "deviations",  # AD
    AdjustmentKind.SHORTAGE_CUSTODY: "shortage_custody",  # AE
    AdjustmentKind.LEAVE_ALLOWANCE_DAYS: "leave_allowance_days",  # K
}

#: Inputs a company admin may override on the review grid.
OVERRIDABLE_FIELDS = (
    "work_days",
    "overtime_hours",
    "leave_allowance_days",
    "bonus",
    "other_earnings",
    "late_hours",
    "advances",
    "carried_advance",
    "admin_penalty_days",
    "fingerprint_penalty_days",
    "unexcused_absence_days",
    "sick_days",
    "insurable_salary",
    "deviations",
    "shortage_custody",
)


def active_employees_for(period) -> list[Employee]:
    """Employees to include in a period: active, and employed during the month."""
    candidates = Employee.all_objects.filter(company=period.company).select_related("branch")
    start, end = period.start_date, period.end_date
    return [
        employee
        for employee in candidates
        if (employee.is_active or employee.is_employed_during(start, end))
        and employee.is_employed_during(start, end)
    ]


def aggregate_attendance(period, employee_ids: list[int]) -> dict[int, dict]:
    """Per-employee totals from `DailyRecord` for the period."""
    rows = (
        DailyRecord.all_objects.filter(
            company=period.company,
            employee_id__in=employee_ids,
            date__gte=period.start_date,
            date__lte=period.end_date,
        )
        .values("employee_id")
        .annotate(
            work_days=Count(
                "id",
                filter=Q(status__in=[AttendanceStatus.PRESENT, AttendanceStatus.PAID_LEAVE]),
            ),
            overtime_hours=Sum("overtime_hours"),
            late_hours=Sum("late_hours"),
            admin_penalty_days=Sum("admin_penalty_days"),
            fingerprint_penalty_days=Sum("fingerprint_penalty_days"),
            unexcused_absence_days=Count("id", filter=Q(status=AttendanceStatus.UNEXCUSED_ABSENCE)),
            sick_days=Count("id", filter=Q(status=AttendanceStatus.SICK)),
        )
    )
    return {row["employee_id"]: row for row in rows}


def aggregate_adjustments(period, employee_ids: list[int]) -> dict[int, dict]:
    """Per-employee sums of `MonthlyAdjustment`, grouped by kind."""
    rows = (
        MonthlyAdjustment.all_objects.filter(
            company=period.company, period=period, employee_id__in=employee_ids
        )
        .values("employee_id", "kind")
        .annotate(total=Sum("amount"))
    )

    totals: dict[int, dict] = {}
    for row in rows:
        field = ADJUSTMENT_TO_FIELD.get(row["kind"])
        if field is None:
            continue
        bucket = totals.setdefault(row["employee_id"], {})
        bucket[field] = bucket.get(field, ZERO) + (row["total"] or ZERO)
    return totals


def collect_notes(period, employee_id: int) -> str:
    """Concatenate the month's daily and adjustment notes for column AH."""
    daily = (
        DailyRecord.all_objects.filter(
            company=period.company,
            employee_id=employee_id,
            date__gte=period.start_date,
            date__lte=period.end_date,
        )
        .exclude(note="")
        .order_by("date")
        .values_list("date", "note")
    )
    adjustments = (
        MonthlyAdjustment.all_objects.filter(
            company=period.company, period=period, employee_id=employee_id
        )
        .exclude(note="")
        .values_list("note", flat=True)
    )

    parts = [f"{day:%d}: {note}" for day, note in daily]
    parts.extend(adjustments)
    return " | ".join(parts)


def build_inputs(period, employee, attendance: dict, adjustments: dict, policy) -> dict:
    """Assemble the raw (pre-override) engine inputs for one employee."""
    base_salary, insurable_salary = employee.salary_on(period.start_date)
    basis = Decimal(policy.month_day_basis if policy else 30)

    work_days = Decimal(attendance.get("work_days") or 0)
    # The workbook's month is 30 days; a 31-day month cannot pay 31/30 of salary.
    work_days = min(work_days, basis)

    values = {
        "base_salary": base_salary,
        "daily_hours": employee.daily_hours,
        "work_days": work_days,
        "overtime_hours": attendance.get("overtime_hours") or ZERO,
        "late_hours": attendance.get("late_hours") or ZERO,
        "admin_penalty_days": attendance.get("admin_penalty_days") or ZERO,
        "fingerprint_penalty_days": attendance.get("fingerprint_penalty_days") or ZERO,
        "unexcused_absence_days": Decimal(attendance.get("unexcused_absence_days") or 0),
        "sick_days": Decimal(attendance.get("sick_days") or 0),
        "insurable_salary": insurable_salary,
        "leave_allowance_days": ZERO,
        "bonus": ZERO,
        "other_earnings": ZERO,
        "advances": ZERO,
        "carried_advance": ZERO,
        "deviations": ZERO,
        "shortage_custody": ZERO,
    }
    values.update(adjustments)
    return values


def to_line_inputs(values: dict) -> LineInputs:
    allowed = set(LineInputs.__dataclass_fields__)
    return LineInputs(**{k: v for k, v in values.items() if k in allowed})
