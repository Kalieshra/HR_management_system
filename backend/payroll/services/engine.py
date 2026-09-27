"""The payroll calculation engine.

Pure functions over `Decimal`. **No Django imports** — this module is the one
place where the workbook's arithmetic lives, and it is tested directly against
`docs/reference/accounting_monthly.xlsx`.

Column letters refer to the reference workbook (see
`docs/reference/workbook-spec.md`):

    H = F/30*G              earned days value
    J = I*F/30/E            overtime (1x hourly rate, no statutory premium)
    L = K*F/30              leave allowance
    O = N+M+L+J+H           total earnings
    Q = F/30/E*P            lateness
    U = F/30*T              administrative penalty
    W = H/30*V              fingerprint penalty  <- based on H, not F
    Y = F/30*X*1            unexcused absence
    AA = (F/30*Z)*0.25      sick
    AC = AB*11%             insurance (no income tax exists in the workbook)
    AF = AE+AD+Y+U+R+Q+AA+S+W+AC    total deductions
    AG = O-AF               net salary
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_UP, Decimal, getcontext, localcontext

# Generous working precision; every stored result is quantised to 6 dp.
getcontext().prec = 28

ZERO = Decimal("0")
CALC_EXPONENT = Decimal("0.000001")  # 6 dp — how results are stored
DISPLAY_EXPONENT = Decimal("0.01")  # 2 dp — how results are shown

FINGERPRINT_BASE_EARNED = "earned"
FINGERPRINT_BASE_BASE = "base"


def quantize_calc(value: Decimal) -> Decimal:
    """Round to the 6 dp the database stores."""
    return Decimal(value).quantize(CALC_EXPONENT, rounding=ROUND_HALF_UP)


def quantize_display(value: Decimal) -> Decimal:
    """Round to the 2 dp shown in the UI and written with format #,##0.00."""
    return Decimal(value).quantize(DISPLAY_EXPONENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class PolicyValues:
    """The knobs behind the workbook's hard-coded constants.

    Defaults reproduce `accounting_monthly.xlsx` exactly.
    """

    month_day_basis: Decimal = Decimal("30")
    overtime_multiplier: Decimal = Decimal("1")
    absence_multiplier: Decimal = Decimal("1")
    sick_deduction_rate: Decimal = Decimal("0.25")
    insurance_employee_rate: Decimal = Decimal("0.11")
    fingerprint_penalty_base: str = FINGERPRINT_BASE_EARNED
    income_tax_enabled: bool = False

    @classmethod
    def from_policy(cls, policy) -> PolicyValues:
        """Build from a `companies.PayrollPolicy` row (duck-typed, no import)."""
        if policy is None:
            return cls()
        return cls(
            month_day_basis=Decimal(policy.month_day_basis),
            overtime_multiplier=Decimal(policy.overtime_multiplier),
            absence_multiplier=Decimal(policy.absence_multiplier),
            sick_deduction_rate=Decimal(policy.sick_deduction_rate),
            insurance_employee_rate=Decimal(policy.insurance_employee_rate),
            fingerprint_penalty_base=policy.fingerprint_penalty_base,
            income_tax_enabled=bool(policy.income_tax_enabled),
        )


@dataclass(frozen=True)
class LineInputs:
    """Everything the engine needs for one employee-month.

    Field names match `PayrollLine`; the Excel column is in the comment.
    """

    base_salary: Decimal = ZERO  # F
    daily_hours: Decimal = Decimal("9")  # E
    work_days: Decimal = ZERO  # G
    overtime_hours: Decimal = ZERO  # I
    leave_allowance_days: Decimal = ZERO  # K
    bonus: Decimal = ZERO  # M
    other_earnings: Decimal = ZERO  # N
    late_hours: Decimal = ZERO  # P
    advances: Decimal = ZERO  # R
    carried_advance: Decimal = ZERO  # S
    admin_penalty_days: Decimal = ZERO  # T
    fingerprint_penalty_days: Decimal = ZERO  # V
    unexcused_absence_days: Decimal = ZERO  # X
    sick_days: Decimal = ZERO  # Z
    insurable_salary: Decimal = ZERO  # AB
    deviations: Decimal = ZERO  # AD
    shortage_custody: Decimal = ZERO  # AE

    def normalised(self) -> LineInputs:
        """Coerce every field to `Decimal`, treating None as zero."""
        values = {}
        for name in self.__dataclass_fields__:
            raw = getattr(self, name)
            values[name] = ZERO if raw is None else Decimal(str(raw))
        return replace(self, **values)


@dataclass(frozen=True)
class LineResult:
    """The twelve calculated columns, each quantised to 6 dp."""

    work_days_value: Decimal = ZERO  # H
    overtime_value: Decimal = ZERO  # J
    leave_allowance_value: Decimal = ZERO  # L
    total_earnings: Decimal = ZERO  # O
    late_value: Decimal = ZERO  # Q
    admin_penalty_value: Decimal = ZERO  # U
    fingerprint_penalty_value: Decimal = ZERO  # W
    unexcused_absence_value: Decimal = ZERO  # Y
    sick_value: Decimal = ZERO  # AA
    insurance_and_tax: Decimal = ZERO  # AC
    total_deductions: Decimal = ZERO  # AF
    net_salary: Decimal = ZERO  # AG
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Decimal]:
        return {
            name: getattr(self, name) for name in self.__dataclass_fields__ if name != "warnings"
        }


def calculate_line(inputs: LineInputs, policy: PolicyValues | None = None) -> LineResult:
    """Calculate one payroll line exactly as the workbook does.

    Division by zero is never raised: a zero `daily_hours` makes the two
    hour-based columns (J, Q) zero and records a warning instead, and a zero
    `month_day_basis` does the same for every day-based column.
    """
    policy = policy or PolicyValues()
    values = inputs.normalised()
    warnings: list[str] = []

    with localcontext() as ctx:
        ctx.prec = 28

        basis = Decimal(policy.month_day_basis)
        if basis <= 0:
            warnings.append("month_day_basis_is_zero")
            daily_rate = ZERO
        else:
            daily_rate = values.base_salary / basis  # F/30

        hours = values.daily_hours
        if hours <= 0:
            warnings.append("daily_hours_is_zero")
            hourly_rate = ZERO
        else:
            hourly_rate = daily_rate / hours  # F/30/E

        # --- earnings ---------------------------------------------------
        work_days_value = daily_rate * values.work_days  # H
        overtime_value = values.overtime_hours * hourly_rate * policy.overtime_multiplier  # J
        leave_allowance_value = values.leave_allowance_days * daily_rate  # L
        total_earnings = (  # O
            values.other_earnings
            + values.bonus
            + leave_allowance_value
            + overtime_value
            + work_days_value
        )

        # --- deductions -------------------------------------------------
        late_value = hourly_rate * values.late_hours  # Q
        admin_penalty_value = daily_rate * values.admin_penalty_days  # U

        # The workbook divides the *earned days value* by the basis here, not
        # the base salary. Preserved deliberately; see workbook-spec.md.
        if policy.fingerprint_penalty_base == FINGERPRINT_BASE_BASE:
            fingerprint_source = values.base_salary
        else:
            fingerprint_source = work_days_value
        fingerprint_penalty_value = (  # W
            (fingerprint_source / basis * values.fingerprint_penalty_days) if basis > 0 else ZERO
        )

        unexcused_absence_value = (  # Y
            daily_rate * values.unexcused_absence_days * policy.absence_multiplier
        )
        sick_value = (daily_rate * values.sick_days) * policy.sick_deduction_rate  # AA
        insurance_and_tax = values.insurable_salary * policy.insurance_employee_rate  # AC

        total_deductions = (  # AF
            values.shortage_custody
            + values.deviations
            + unexcused_absence_value
            + admin_penalty_value
            + values.advances
            + late_value
            + sick_value
            + values.carried_advance
            + fingerprint_penalty_value
            + insurance_and_tax
        )

        net_salary = total_earnings - total_deductions  # AG

    return LineResult(
        work_days_value=quantize_calc(work_days_value),
        overtime_value=quantize_calc(overtime_value),
        leave_allowance_value=quantize_calc(leave_allowance_value),
        total_earnings=quantize_calc(total_earnings),
        late_value=quantize_calc(late_value),
        admin_penalty_value=quantize_calc(admin_penalty_value),
        fingerprint_penalty_value=quantize_calc(fingerprint_penalty_value),
        unexcused_absence_value=quantize_calc(unexcused_absence_value),
        sick_value=quantize_calc(sick_value),
        insurance_and_tax=quantize_calc(insurance_and_tax),
        total_deductions=quantize_calc(total_deductions),
        net_salary=quantize_calc(net_salary),
        warnings=tuple(warnings),
    )
