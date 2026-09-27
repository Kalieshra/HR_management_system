"""Generated report files (Excel workbooks, payslip PDFs) and their delivery."""

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TenantModel


class ReportKind(models.TextChoices):
    XLSX = "xlsx", _("Excel workbook")
    PDF = "pdf", _("Payslip PDF")


class ReportFile(TenantModel):
    """One generated artefact for one period, plus who it was emailed to."""

    period = models.ForeignKey(
        "payroll.Period", on_delete=models.CASCADE, related_name="report_files"
    )
    kind = models.CharField(_("kind"), max_length=8, choices=ReportKind.choices)
    file = models.FileField(_("file"), upload_to="reports/%Y/%m/")
    generated_at = models.DateTimeField(_("generated at"), auto_now_add=True)
    generated_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    emailed_to = ArrayField(
        models.EmailField(), verbose_name=_("emailed to"), default=list, blank=True
    )
    emailed_at = models.DateTimeField(_("emailed at"), null=True, blank=True)

    class Meta:
        verbose_name = _("report file")
        verbose_name_plural = _("report files")
        ordering = ["-generated_at"]

    def __str__(self) -> str:
        return f"{self.period} {self.kind}"
