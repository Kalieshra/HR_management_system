"""Company, branch and payroll-policy serializers."""

from rest_framework import serializers

from companies.models import Branch, Company, PayrollPolicy


class CompanySerializer(serializers.ModelSerializer):
    branch_count = serializers.IntegerField(read_only=True)
    employee_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Company
        fields = [
            "id",
            "name_ar",
            "name_en",
            "slug",
            "logo",
            "is_active",
            "report_emails",
            "report_day",
            "report_language",
            "branch_count",
            "employee_count",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class BranchSerializer(serializers.ModelSerializer):
    employee_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Branch
        fields = ["id", "name_ar", "name_en", "code", "is_active", "employee_count"]
        read_only_fields = ["id"]


class PayrollPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollPolicy
        fields = [
            "id",
            "effective_from",
            "month_day_basis",
            "overtime_multiplier",
            "absence_multiplier",
            "sick_deduction_rate",
            "insurance_employee_rate",
            "fingerprint_penalty_base",
            "default_daily_hours",
            "income_tax_enabled",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
