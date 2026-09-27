"""Employee master data and its salary history."""

from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TenantModel, money_field


class Employee(TenantModel):
    """One person on the payroll.

    `daily_hours` (column E), `base_salary` (F) and `insurable_salary` (AB) are
    the master values the engine divides by; a period always uses the values
    that were effective on its first day, via `SalaryHistory`.
    """

    branch = models.ForeignKey(
        "companies.Branch", on_delete=models.PROTECT, related_name="employees"
    )
    code = models.CharField(_("code"), max_length=32)
    name_ar = models.CharField(_("name (Arabic)"), max_length=200)
    name_en = models.CharField(_("name (English)"), max_length=200, blank=True)
    job_title = models.CharField(_("job title"), max_length=120, blank=True)
    national_id = models.CharField(_("national ID"), max_length=20, blank=True)

    hire_date = models.DateField(_("hire date"), null=True, blank=True)
    termination_date = models.DateField(_("termination date"), null=True, blank=True)

    daily_hours = models.DecimalField(
        _("daily hours"), max_digits=5, decimal_places=2, default=Decimal("9")
    )
    base_salary = money_field(verbose_name=_("base salary"))
    insurable_salary = money_field(verbose_name=_("insurable salary"))

    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("employee")
        verbose_name_plural = _("employees")
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"], name="employee_unique_code_per_company"
            ),
        ]
        indexes = [models.Index(fields=["company", "is_active"])]

    def __str__(self) -> str:
        return f"{self.code} — {self.name_ar}"

    @property
    def display_name(self) -> str:
        return self.name_ar or self.name_en

    def salary_on(self, on_date):
        """Base/insurable salary effective on a date, falling back to the master row."""
        record = (
            self.salary_history.filter(effective_from__lte=on_date)
            .order_by("-effective_from")
            .first()
        )
        if record is None:
            return self.base_salary, self.insurable_salary
        return record.base_salary, record.insurable_salary

    def is_employed_during(self, start, end) -> bool:
        """True when the employment window overlaps [start, end]."""
        if self.hire_date and self.hire_date > end:
            return False
        return not (self.termination_date and self.termination_date < start)


class SalaryHistory(TenantModel):
    """A dated salary version. The newest row on or before a date wins."""

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="salary_history")
    base_salary = money_field(verbose_name=_("base salary"))
    insurable_salary = money_field(verbose_name=_("insurable salary"))
    effective_from = models.DateField(_("effective from"))
    note = models.CharField(_("note"), max_length=200, blank=True)

    class Meta:
        verbose_name = _("salary history")
        verbose_name_plural = _("salary history")
        ordering = ["-effective_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "effective_from"], name="salary_unique_per_employee_date"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.employee.code} @ {self.effective_from}: {self.base_salary}"
