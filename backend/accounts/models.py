"""Users, their membership of companies, and invitations."""

import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class Language(models.TextChoices):
    AR = "ar", _("Arabic")
    EN = "en", _("English")


class Role(models.TextChoices):
    COMPANY_ADMIN = "company_admin", _("Company admin")
    BRANCH_ENTRY = "branch_entry", _("Branch data entry")


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError(_("Users must have an email address."))
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_platform_admin", True)
        if extra.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))
        return self._create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """Email-login user.

    `is_platform_admin` is the platform-owner role from the spec: it spans every
    company, so it lives on the user rather than in a per-company membership.
    """

    email = models.EmailField(_("email address"), unique=True)
    full_name = models.CharField(_("full name"), max_length=200, blank=True)
    preferred_language = models.CharField(
        _("preferred language"), max_length=2, choices=Language.choices, default=Language.AR
    )
    is_platform_admin = models.BooleanField(_("platform admin"), default=False)
    is_active = models.BooleanField(_("active"), default=True)
    is_staff = models.BooleanField(_("staff"), default=False)
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["email"]

    def __str__(self) -> str:
        return self.email

    def get_full_name(self) -> str:
        return self.full_name or self.email

    def get_short_name(self) -> str:
        return self.full_name.split(" ")[0] if self.full_name else self.email


class Membership(TimeStampedModel):
    """Ties a user to one company with a role, optionally limited to branches."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    company = models.ForeignKey(
        "companies.Company", on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(_("role"), max_length=20, choices=Role.choices)
    # Empty means "every branch" for a company_admin; a branch_entry user is
    # limited to exactly the branches listed here.
    branches = models.ManyToManyField("companies.Branch", blank=True, related_name="memberships")

    class Meta:
        verbose_name = _("membership")
        verbose_name_plural = _("memberships")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "company"], name="membership_unique_per_company"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.company} ({self.role})"

    @property
    def is_company_admin(self) -> bool:
        return self.role == Role.COMPANY_ADMIN

    def allowed_branch_ids(self) -> list[int] | None:
        """None means every branch; otherwise the explicit branch scope."""
        if self.is_company_admin:
            return None
        return list(self.branches.values_list("id", flat=True))


def _default_token() -> str:
    return secrets.token_urlsafe(32)


def _default_expiry():
    return timezone.now() + timedelta(days=7)


class Invitation(TimeStampedModel):
    """A pending invite to join a company (or the platform, when company is null)."""

    email = models.EmailField(_("email address"))
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.CASCADE,
        related_name="invitations",
        null=True,
        blank=True,
    )
    role = models.CharField(_("role"), max_length=20, choices=Role.choices)
    token = models.CharField(_("token"), max_length=64, unique=True, default=_default_token)
    expires_at = models.DateTimeField(_("expires at"), default=_default_expiry)
    accepted_at = models.DateTimeField(_("accepted at"), null=True, blank=True)
    invited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="sent_invitations"
    )

    class Meta:
        verbose_name = _("invitation")
        verbose_name_plural = _("invitations")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.email} -> {self.company or 'platform'}"

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @property
    def is_pending(self) -> bool:
        return self.accepted_at is None and not self.is_expired
