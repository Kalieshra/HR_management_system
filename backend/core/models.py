"""Shared model primitives for shared-schema multi-tenancy.

Every tenant-owned row carries a `company` FK. `TenantManager` refuses to hand
back rows unless the caller has explicitly scoped the queryset with
`.for_company(company)` (or opted out with `.unscoped()`), which turns a missing
tenant filter into a loud error instead of a silent cross-tenant data leak.
"""

from decimal import Decimal

from django.db import models
from django.utils.translation import gettext_lazy as _

# Inputs are entered with 2 decimals; calculated values keep 6 so that a chain
# of divisions (F/30/E) does not lose precision before presentation rounding.
MONEY_DIGITS = 14
MONEY_DP = 2
CALC_DP = 6
ZERO = Decimal("0")


class UnscopedTenantQueryError(RuntimeError):
    """Raised when a tenant-owned queryset is evaluated without a company filter."""


class TenantQuerySet(models.QuerySet):
    """A queryset that must be scoped to one company before it yields rows."""

    _tenant_scoped = False

    def _clone(self):
        clone = super()._clone()
        clone._tenant_scoped = self._tenant_scoped
        return clone

    def for_company(self, company):
        """Scope to a single company. `company` may be a model instance or a pk."""
        clone = self.filter(company=company)
        clone._tenant_scoped = True
        return clone

    def unscoped(self):
        """Escape hatch for platform-level work (admin, migrations, seeding)."""
        clone = self._clone()
        clone._tenant_scoped = True
        return clone

    def _assert_scoped(self):
        if not self._tenant_scoped:
            raise UnscopedTenantQueryError(
                f"{self.model.__name__} queries must be scoped with "
                f".for_company(company) — or .unscoped() when that is deliberate."
            )

    # Every path that reaches the database goes through one of these.
    def _fetch_all(self):
        self._assert_scoped()
        super()._fetch_all()

    def count(self):
        self._assert_scoped()
        return super().count()

    def exists(self):
        self._assert_scoped()
        return super().exists()

    def aggregate(self, *args, **kwargs):
        self._assert_scoped()
        return super().aggregate(*args, **kwargs)

    def update(self, **kwargs):
        self._assert_scoped()
        return super().update(**kwargs)

    def delete(self):
        self._assert_scoped()
        return super().delete()


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    """Default manager for tenant-owned models."""


class UnscopedManager(models.Manager):
    """Plain manager used by the admin, migrations and related-object traversal."""


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantModel(TimeStampedModel):
    """Base class for everything owned by exactly one company."""

    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="%(class)ss",
        verbose_name=_("company"),
    )

    objects = TenantManager()
    all_objects = UnscopedManager()

    class Meta:
        abstract = True
        # Django's own traversal — related descriptors (employee.daily_records),
        # m2m .set(), the admin, serialisation — goes through the base and
        # default managers, which must not be the strict one. Application code
        # calls `.objects`, which is strict and demands `.for_company(...)`.
        base_manager_name = "all_objects"
        default_manager_name = "all_objects"


def money_field(**kwargs):
    kwargs.setdefault("max_digits", MONEY_DIGITS)
    kwargs.setdefault("decimal_places", MONEY_DP)
    kwargs.setdefault("default", ZERO)
    return models.DecimalField(**kwargs)


def calc_field(**kwargs):
    kwargs.setdefault("max_digits", MONEY_DIGITS + CALC_DP)
    kwargs.setdefault("decimal_places", CALC_DP)
    kwargs.setdefault("default", ZERO)
    return models.DecimalField(**kwargs)
