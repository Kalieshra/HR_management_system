from django.contrib import admin

from payroll.models import Loan, MonthlyAdjustment, PayrollLine, Period


@admin.register(Period)
class PeriodAdmin(admin.ModelAdmin):
    list_display = ["company", "year", "month", "status", "calculated_at", "closed_at"]
    list_filter = ["company", "status", "year"]


@admin.register(MonthlyAdjustment)
class MonthlyAdjustmentAdmin(admin.ModelAdmin):
    list_display = ["employee", "period", "kind", "amount"]
    list_filter = ["company", "kind", "period"]
    search_fields = ["employee__code", "employee__name_ar"]


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ["employee", "total", "monthly_installment", "remaining", "is_active"]
    list_filter = ["company", "is_active"]
    search_fields = ["employee__code", "employee__name_ar"]


@admin.register(PayrollLine)
class PayrollLineAdmin(admin.ModelAdmin):
    list_display = [
        "employee_code",
        "employee_name",
        "period",
        "base_salary",
        "total_earnings",
        "total_deductions",
        "net_salary",
    ]
    list_filter = ["company", "period", "branch_snapshot"]
    search_fields = ["employee_code", "employee_name"]
