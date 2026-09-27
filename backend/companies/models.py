"""Tenants: the companies the platform owner opens accounts for."""

from decimal import Decimal

from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TenantModel, TimeStampedModel


class ReportLanguage(models.TextChoices):
    AR = "ar", _("Arabic")
    EN = "en", _("English")


class Company(TimeStampedModel):
    """One tenant. Every other tenant-owned row points back here."""

    name_ar = models.CharField(_("name (Arabic)"), max_length=200)
    name_en = models.CharField(_("name (English)"), max_length=200, blank=True)
    slug = models.SlugField(_("slug"), max_length=80, unique=True)
    logo = models.ImageField(_("logo"), upload_to="logos/", blank=True, null=True)
    is_active = models.BooleanField(_("active"), default=True)

    # Monthly report delivery
    report_emails = ArrayField(
        models.EmailField(),
        verbose_name=_("report recipients"),
        default=list,
        blank=True,
    )
    report_day = models.PositiveSmallIntegerField(
        _("report day of month"),
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(28)],
    )
    report_language = models.CharField(
        _("report language"),
        max_length=2,
        choices=ReportLanguage.choices,
        default=ReportLanguage.AR,
    )

    class Meta:
        verbose_name = _("company")
        verbose_name_plural = _("companies")
        ordering = ["name_ar"]

    def __str__(self) -> str:
        return self.name_ar or self.name_en or self.slug

    @property
    def display_name(self) -> str:
        return self.name_ar or self.name_en


class Branch(TenantModel):
    """A physical location. Employees belong to exactly one."""

    name_ar = models.CharField(_("name (Arabic)"), max_length=200)
    name_en = models.CharField(_("name (English)"), max_length=200, blank=True)
    code = models.CharField(_("code"), max_length=32, blank=True)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("branch")
        verbose_name_plural = _("branches")
        ordering = ["name_ar"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "name_ar"], name="branch_unique_name_per_company"
            ),
        ]

    def __str__(self) -> str:
        return self.name_ar


class FingerprintPenaltyBase(models.TextChoices):
    EARNED = "earned", _("Earned days value (H)")
    BASE = "base", _("Base salary (F)")


class PayrollPolicy(TenantModel):
    """A versioned set of payroll rules.

    The engine picks the newest policy whose `effective_from` is on or before the
    first day of the period being calculated, so historical months keep the rules
    they were closed under. The defaults reproduce the reference workbook exactly.
    """

    effective_from = models.DateField(_("effective from"))

    month_day_basis = models.PositiveSmallIntegerField(_("month day basis"), default=30)
    overtime_multiplier = models.DecimalField(
        _("overtime multiplier"), max_digits=6, decimal_places=4, default=Decimal("1")
    )
    absence_multiplier = models.DecimalField(
        _("unexcused absence multiplier"),
        max_digits=6,
        decimal_places=4,
        default=Decimal("1"),
    )
    sick_deduction_rate = models.DecimalField(
        _("sick deduction rate"), max_digits=6, decimal_places=4, default=Decimal("0.25")
    )
    insurance_employee_rate = models.DecimalField(
        _("insurance rate"), max_digits=6, decimal_places=4, default=Decimal("0.11")
    )
    fingerprint_penalty_base = models.CharField(
        _("fingerprint penalty base"),
        max_length=8,
        choices=FingerprintPenaltyBase.choices,
        default=FingerprintPenaltyBase.EARNED,
    )
    default_daily_hours = models.DecimalField(
        _("default daily hours"), max_digits=5, decimal_places=2, default=Decimal("9")
    )
    income_tax_enabled = models.BooleanField(_("income tax enabled"), default=False)

    class Meta:
        verbose_name = _("payroll policy")
        verbose_name_plural = _("payroll policies")
        ordering = ["-effective_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "effective_from"], name="policy_unique_version_per_company"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.company} @ {self.effective_from}"
