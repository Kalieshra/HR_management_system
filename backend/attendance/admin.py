from django.contrib import admin

from attendance.models import DailyRecord


@admin.register(DailyRecord)
class DailyRecordAdmin(admin.ModelAdmin):
    list_display = ["employee", "date", "status", "overtime_hours", "late_hours"]
    list_filter = ["company", "status", "date"]
    search_fields = ["employee__code", "employee__name_ar"]
    date_hierarchy = "date"
