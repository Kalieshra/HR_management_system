from django.contrib import admin

from audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "company", "user", "action", "model", "object_id"]
    list_filter = ["company", "action", "model"]
    search_fields = ["object_id", "model"]
    readonly_fields = ["created_at", "updated_at", "before", "after"]
