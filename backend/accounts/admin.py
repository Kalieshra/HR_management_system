from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from accounts.models import Invitation, Membership, User


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ["company"]
    filter_horizontal = ["branches"]


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["email", "full_name", "is_platform_admin", "is_active", "is_staff"]
    list_filter = ["is_platform_admin", "is_active", "is_staff", "preferred_language"]
    search_fields = ["email", "full_name"]
    ordering = ["email"]
    inlines = [MembershipInline]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("full_name", "preferred_language")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "is_platform_admin",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "is_platform_admin"),
            },
        ),
    )


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "company", "role"]
    list_filter = ["role", "company"]
    search_fields = ["user__email", "company__name_ar"]
    filter_horizontal = ["branches"]


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ["email", "company", "role", "expires_at", "accepted_at"]
    list_filter = ["role", "company"]
    search_fields = ["email"]
