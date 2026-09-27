"""Payroll periods, monthly amounts, loans, and the calculated salary lines.

`PayrollLine` mirrors the reference workbook column for column; the Excel letter
of each field is noted so the report generator and the review grid stay aligned
with `docs/reference/workbook-spec.md`.
"""

from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TenantModel, calc_field, money_field


class PeriodStatus(models.TextChoices):
    OPEN = "open", _("Open")
    CALCULATED = "calculated", _("Calculated")
    CLOSED = "closed", _("Closed")


class AdjustmentKind(models.TextChoices):
    BONUS = "bonus", _("Bonus")  # M
    OTHER_EARNING = "other_earning", _("Other earning")  # N
    ADVANCE = "advance", _("Advance")  # R
    CARRIED_ADVANCE = "carried_advance", _("Carried advance")  # S
    DEVIATION = "deviation", _("Deviation")  # AD
    SHORTAGE_CUSTODY = "shortage_custody", _("Shortage / custody")  # AE
    LEAVE_ALLOWANCE_DAYS = "leave_allowance_days", _("Leave allowance (days)")  # K


#: Adjustment kinds that add to earnings rather than deductions.
EARNING_KINDS = frozenset(
    {
        AdjustmentKind.BONUS,
        AdjustmentKind.OTHER_EARNING,
        AdjustmentKind.LEAVE_ALLOWANCE_DAYS,
    }
)

ARABIC_MONTHS = {
    1: "يناير",
    2: "فبراير",
    3: "مارس",
    4: "ابريل",
    5: "مايو",
    6: "يونيو",
    7: "يوليو",
    8: "اغسطس",
    9: "سبتمبر",
    10: "اكتوبر",
    11: "نوفمبر",
    12: "ديسمبر",
}


class Period(TenantModel):
    """One company-month. Closing it freezes every number inside."""

    year = models.PositiveSmallIntegerField(_("year"))
    month = models.PositiveSmallIntegerField(_("month"))
    status = models.CharField(
        _("status"), max_length=12, choices=PeriodStatus.choices, default=PeriodStatus.OPEN
    )
    calculated_at = models.DateTimeField(_("calculated at"), null=True, blank=True)
    closed_at = models.DateTimeField(_("closed at"), null=True, blank=True)
    closed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_periods",
    )

    class Meta:
        verbose_name = _("payroll period")
        verbose_name_plural = _("payroll periods")
        ordering = ["-year", "-month"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "year", "month"], name="period_unique_per_company_month"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.year}-{self.month:02d}"

    @property
    def is_closed(self) -> bool:
        return self.status == PeriodStatus.CLOSED

    @property
    def start_date(self):
        from datetime import date

        return date(self.year, self.month, 1)

    @property
    def end_date(self):
        from calendar import monthrange
        from datetime import date

        return date(self.year, self.month, monthrange(self.year, self.month)[1])

    @property
    def arabic_label(self) -> str:
        return f"{ARABIC_MONTHS[self.month]} {self.year}"


class MonthlyAdjustment(TenantModel):
    """A one-off amount for an employee in a period. Rows of a kind are summed."""

    period = models.ForeignKey(Period, on_delete=models.CASCADE, related_name="adjustments")
    employee = models.ForeignKey(
        "employees.Employee", on_delete=models.CASCADE, related_name="adjustments"
    )
    kind = models.CharField(_("kind"), max_length=24, choices=AdjustmentKind.choices)
    amount = money_field(verbose_name=_("amount"))
    note = models.CharField(_("note"), max_length=300, blank=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        verbose_name = _("monthly adjustment")
        verbose_name_plural = _("monthly adjustments")
        ordering = ["employee__code", "kind"]
        indexes = [models.Index(fields=["company", "period", "employee"])]

    def __str__(self) -> str:
        return f"{self.employee.code} {self.kind} {self.amount}"


class Loan(TenantModel):
    """An advance repaid monthly.

    Each time a period is calculated the outstanding instalment is materialised
    as an `advance` adjustment, which keeps the سلف workflow identical to the
    workbook while letting the balance run down automatically.
    """

    employee = models.ForeignKey(
        "employees.Employee", on_delete=models.CASCADE, related_name="loans"
    )
    total = money_field(verbose_name=_("total"))
    monthly_installment = money_field(verbose_name=_("monthly instalment"))
    start_year = models.PositiveSmallIntegerField(_("start year"))
    start_month = models.PositiveSmallIntegerField(_("start month"))
    remaining = money_field(verbose_name=_("remaining"))
    note = models.CharField(_("note"), max_length=300, blank=True)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("loan")
        verbose_name_plural = _("loans")
        ordering = ["employee__code"]

    def __str__(self) -> str:
        return f"{self.employee.code}: {self.remaining}/{self.total}"

    def starts_on_or_before(self, year: int, month: int) -> bool:
        return (self.start_year, self.start_month) <= (year, month)

    def installment_for(self, year: int, month: int) -> Decimal:
        """What this loan takes in the given month — never more than the balance."""
        if not self.is_active or self.remaining <= 0:
            return Decimal("0")
        if not self.starts_on_or_before(year, month):
            return Decimal("0")
        return min(self.monthly_installment, self.remaining)


class PayrollLine(TenantModel):
    """One employee's calculated salary for one period — a row of the report.

    Master data is snapshotted so a closed month never changes when an employee
    is later renamed, moved or given a raise.
    """

    period = models.ForeignKey(Period, on_delete=models.CASCADE, related_name="lines")
    employee = models.ForeignKey(
        "employees.Employee", on_delete=models.PROTECT, related_name="payroll_lines"
    )

    # --- snapshots (columns A-F) -----------------------------------------
    employee_code = models.CharField(_("code"), max_length=32)  # A
    employee_name = models.CharField(_("name"), max_length=200)  # B
    branch_snapshot = models.CharField(_("branch"), max_length=200)  # C
    job_title_snapshot = models.CharField(_("job title"), max_length=120, blank=True)  # D
    daily_hours = models.DecimalField(  # E
        _("daily hours"), max_digits=5, decimal_places=2, default=Decimal("9")
    )
    base_salary = money_field(verbose_name=_("base salary"))  # F

    # --- inputs ------------------------------------------------------------
    work_days = models.DecimalField(  # G
        _("work days"), max_digits=6, decimal_places=2, default=Decimal("0")
    )
    overtime_hours = models.DecimalField(  # I
        _("overtime hours"), max_digits=6, decimal_places=2, default=Decimal("0")
    )
    leave_allowance_days = models.DecimalField(  # K
        _("leave allowance days"), max_digits=6, decimal_places=2, default=Decimal("0")
    )
    bonus = money_field(verbose_name=_("bonus"))  # M
    other_earnings = money_field(verbose_name=_("other earnings"))  # N
    late_hours = models.DecimalField(  # P
        _("late hours"), max_digits=6, decimal_places=2, default=Decimal("0")
    )
    advances = money_field(verbose_name=_("advances"))  # R
    carried_advance = money_field(verbose_name=_("carried advance"))  # S
    admin_penalty_days = models.DecimalField(  # T
        _("administrative penalty days"), max_digits=6, decimal_places=2, default=Decimal("0")
    )
    fingerprint_penalty_days = models.DecimalField(  # V
        _("fingerprint penalty days"), max_digits=6, decimal_places=2, default=Decimal("0")
    )
    unexcused_absence_days = models.DecimalField(  # X
        _("unexcused absence days"), max_digits=6, decimal_places=2, default=Decimal("0")
    )
    sick_days = models.DecimalField(  # Z
        _("sick days"), max_digits=6, decimal_places=2, default=Decimal("0")
    )
    insurable_salary = money_field(verbose_name=_("insurable salary"))  # AB
    deviations = money_field(verbose_name=_("deviations"))  # AD
    shortage_custody = money_field(verbose_name=_("shortage / custody"))  # AE

    # --- calculated --------------------------------------------------------
    work_days_value = calc_field(verbose_name=_("work days value"))  # H
    overtime_value = calc_field(verbose_name=_("overtime value"))  # J
    leave_allowance_value = calc_field(verbose_name=_("leave allowance value"))  # L
    total_earnings = calc_field(verbose_name=_("total earnings"))  # O
    late_value = calc_field(verbose_name=_("late value"))  # Q
    admin_penalty_value = calc_field(verbose_name=_("administrative penalty value"))  # U
    fingerprint_penalty_value = calc_field(verbose_name=_("fingerprint penalty value"))  # W
    unexcused_absence_value = calc_field(verbose_name=_("unexcused absence value"))  # Y
    sick_value = calc_field(verbose_name=_("sick value"))  # AA
    insurance_and_tax = calc_field(verbose_name=_("insurance and tax"))  # AC
    total_deductions = calc_field(verbose_name=_("total deductions"))  # AF
    net_salary = calc_field(verbose_name=_("net salary"))  # AG

    notes = models.TextField(_("notes"), blank=True)  # AH

    #: Manual edits to aggregated inputs: {field: original_value}. Highlighted
    #: in the review grid and re-applied on every recalculation.
    overrides = models.JSONField(_("overrides"), default=dict, blank=True)
    #: Engine warnings (e.g. daily_hours == 0), surfaced in the UI.
    warnings = models.JSONField(_("warnings"), default=list, blank=True)

    class Meta:
        verbose_name = _("payroll line")
        verbose_name_plural = _("payroll lines")
        ordering = ["employee_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["period", "employee"], name="payrollline_unique_per_period_employee"
            ),
        ]
        indexes = [models.Index(fields=["company", "period"])]

    def __str__(self) -> str:
        return f"{self.employee_code} {self.period}: {self.net_salary}"

    @property
    def is_overridden(self) -> bool:
        return bool(self.overrides)
