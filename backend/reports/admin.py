from django.contrib import admin

from reports.models import ReportFile


@admin.register(ReportFile)
class ReportFileAdmin(admin.ModelAdmin):
    list_display = ["period", "kind", "generated_at", "emailed_at"]
    list_filter = ["company", "kind"]
