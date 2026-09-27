"""Employee serializers."""

from rest_framework import serializers

from core.fields import MoneyField, QuantityField
from employees.models import Employee, SalaryHistory


class EmployeeSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name_ar", read_only=True)
    base_salary = MoneyField()
    insurable_salary = MoneyField(required=False)
    daily_hours = QuantityField(required=False)

    class Meta:
        model = Employee
        fields = [
            "id",
            "code",
            "name_ar",
            "name_en",
            "branch",
            "branch_name",
            "job_title",
            "national_id",
            "hire_date",
            "termination_date",
            "daily_hours",
            "base_salary",
            "insurable_salary",
            "is_active",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        company = self.context["request"].company
        branch = attrs.get("branch") or getattr(self.instance, "branch", None)
        if branch is not None and branch.company_id != company.pk:
            raise serializers.ValidationError(
                {"branch": serializers.ErrorDetail("That branch belongs to another company.")}
            )

        code = attrs.get("code")
        if code:
            clash = Employee.objects.for_company(company).filter(code=code)
            if self.instance:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise serializers.ValidationError({"code": "This code is already in use."})
        return attrs


class SalaryHistorySerializer(serializers.ModelSerializer):
    base_salary = MoneyField()
    insurable_salary = MoneyField(required=False)

    class Meta:
        model = SalaryHistory
        fields = ["id", "employee", "base_salary", "insurable_salary", "effective_from", "note"]
        read_only_fields = ["id"]


class EmployeeImportRowSerializer(serializers.Serializer):
    """One row of the employee import sheet, after header mapping."""

    code = serializers.CharField()
    name_ar = serializers.CharField()
    name_en = serializers.CharField(required=False, allow_blank=True)
    branch = serializers.CharField()
    job_title = serializers.CharField(required=False, allow_blank=True)
    daily_hours = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    base_salary = serializers.DecimalField(max_digits=14, decimal_places=2)
    insurable_salary = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
