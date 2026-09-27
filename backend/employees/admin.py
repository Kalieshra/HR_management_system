from django.contrib import admin

from employees.models import Employee, SalaryHistory


class SalaryHistoryInline(admin.TabularInline):
    model = SalaryHistory
    extra = 0
    fields = ["effective_from", "base_salary", "insurable_salary", "note"]


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ["code", "name_ar", "company", "branch", "base_salary", "is_active"]
    list_filter = ["company", "branch", "is_active"]
    search_fields = ["code", "name_ar", "name_en", "national_id"]
    inlines = [SalaryHistoryInline]
