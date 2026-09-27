"""Daily attendance — the raw data companies enter every day."""

from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TenantModel


class AttendanceStatus(models.TextChoices):
    PRESENT = "present", _("Present")
    UNEXCUSED_ABSENCE = "unexcused_absence", _("Unexcused absence")
    SICK = "sick", _("Sick")
    PAID_LEAVE = "paid_leave", _("Paid leave")
    WEEKLY_OFF = "weekly_off", _("Weekly off")
    EXCUSED_ABSENCE = "excused_absence", _("Excused absence")


#: Statuses that count towards column G (ايام العمل).
PAID_DAY_STATUSES = frozenset({AttendanceStatus.PRESENT, AttendanceStatus.PAID_LEAVE})


def _hours_field(label):
    return models.DecimalField(label, max_digits=6, decimal_places=2, default=Decimal("0"))


def _days_field(label):
    return models.DecimalField(label, max_digits=6, decimal_places=2, default=Decimal("0"))


class DailyRecord(TenantModel):
    """One employee, one day. Aggregated into a `PayrollLine` at month end."""

    employee = models.ForeignKey(
        "employees.Employee", on_delete=models.CASCADE, related_name="daily_records"
    )
    date = models.DateField(_("date"), db_index=True)
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.PRESENT,
    )

    overtime_hours = _hours_field(_("overtime hours"))
    late_hours = _hours_field(_("late hours"))
    admin_penalty_days = _days_field(_("administrative penalty (days)"))
    fingerprint_penalty_days = _days_field(_("fingerprint penalty (days)"))

    note = models.CharField(_("note"), max_length=300, blank=True)
    entered_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="daily_records_entered",
    )

    class Meta:
        verbose_name = _("daily record")
        verbose_name_plural = _("daily records")
        ordering = ["-date", "employee__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "date"], name="dailyrecord_unique_per_employee_day"
            ),
        ]
        indexes = [models.Index(fields=["company", "date"])]

    def __str__(self) -> str:
        return f"{self.employee.code} {self.date} {self.status}"

    @property
    def counts_as_work_day(self) -> bool:
        return self.status in PAID_DAY_STATUSES
