from django.contrib import admin

from companies.models import Branch, Company, PayrollPolicy


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["name_ar", "name_en", "slug", "is_active", "report_day"]
    list_filter = ["is_active"]
    search_fields = ["name_ar", "name_en", "slug"]
    prepopulated_fields = {"slug": ("name_en",)}


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ["name_ar", "company", "code", "is_active"]
    list_filter = ["company", "is_active"]
    search_fields = ["name_ar", "name_en", "code"]


@admin.register(PayrollPolicy)
class PayrollPolicyAdmin(admin.ModelAdmin):
    list_display = [
        "company",
        "effective_from",
        "month_day_basis",
        "overtime_multiplier",
        "sick_deduction_rate",
        "insurance_employee_rate",
        "fingerprint_penalty_base",
    ]
    list_filter = ["company", "fingerprint_penalty_base"]
