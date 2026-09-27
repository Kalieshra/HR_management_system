"""Append-only audit trail for every change that affects pay."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class AuditAction(models.TextChoices):
    CREATE = "create", _("Create")
    UPDATE = "update", _("Update")
    DELETE = "delete", _("Delete")
    CLOSE = "close", _("Close period")
    REOPEN = "reopen", _("Reopen period")
    CALCULATE = "calculate", _("Calculate period")
    OVERRIDE = "override", _("Override payroll line")


class AuditLog(TimeStampedModel):
    """A single recorded change.

    `company` is nullable because platform-level actions (creating or suspending
    a company) have no tenant of their own.
    """

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="audit_logs",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs"
    )
    action = models.CharField(_("action"), max_length=16, choices=AuditAction.choices)
    model = models.CharField(_("model"), max_length=64)
    object_id = models.CharField(_("object id"), max_length=64, blank=True)
    before = models.JSONField(_("before"), null=True, blank=True)
    after = models.JSONField(_("after"), null=True, blank=True)

    class Meta:
        verbose_name = _("audit log")
        verbose_name_plural = _("audit logs")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "-created_at"]),
            models.Index(fields=["model", "object_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action} {self.model}#{self.object_id}"
