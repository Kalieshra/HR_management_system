"""Payroll serializers: periods, lines, adjustments and loans."""

from rest_framework import serializers

from core.fields import MoneyField, QuantityField
from payroll.models import Loan, MonthlyAdjustment, PayrollLine, Period
from payroll.services.aggregate import OVERRIDABLE_FIELDS


class PeriodSerializer(serializers.ModelSerializer):
    label = serializers.CharField(source="arabic_label", read_only=True)
    line_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Period
        fields = [
            "id",
            "year",
            "month",
            "label",
            "status",
            "calculated_at",
            "closed_at",
            "line_count",
        ]
        read_only_fields = ["id", "status", "calculated_at", "closed_at"]


class PayrollLineSerializer(serializers.ModelSerializer):
    """One row of the monthly review grid, laid out like the Excel columns."""

    base_salary = MoneyField(read_only=True)
    bonus = MoneyField()
    other_earnings = MoneyField()
    advances = MoneyField()
    carried_advance = MoneyField()
    insurable_salary = MoneyField()
    deviations = MoneyField()
    shortage_custody = MoneyField()

    work_days = QuantityField()
    overtime_hours = QuantityField()
    leave_allowance_days = QuantityField()
    late_hours = QuantityField()
    admin_penalty_days = QuantityField()
    fingerprint_penalty_days = QuantityField()
    unexcused_absence_days = QuantityField()
    sick_days = QuantityField()
    daily_hours = QuantityField(read_only=True)

    work_days_value = MoneyField(read_only=True)
    overtime_value = MoneyField(read_only=True)
    leave_allowance_value = MoneyField(read_only=True)
    total_earnings = MoneyField(read_only=True)
    late_value = MoneyField(read_only=True)
    admin_penalty_value = MoneyField(read_only=True)
    fingerprint_penalty_value = MoneyField(read_only=True)
    unexcused_absence_value = MoneyField(read_only=True)
    sick_value = MoneyField(read_only=True)
    insurance_and_tax = MoneyField(read_only=True)
    total_deductions = MoneyField(read_only=True)
    net_salary = MoneyField(read_only=True)

    class Meta:
        model = PayrollLine
        fields = [
            "id",
            "employee",
            "employee_code",  # A
            "employee_name",  # B
            "branch_snapshot",  # C
            "job_title_snapshot",  # D
            "daily_hours",  # E
            "base_salary",  # F
            "work_days",  # G
            "work_days_value",  # H
            "overtime_hours",  # I
            "overtime_value",  # J
            "leave_allowance_days",  # K
            "leave_allowance_value",  # L
            "bonus",  # M
            "other_earnings",  # N
            "total_earnings",  # O
            "late_hours",  # P
            "late_value",  # Q
            "advances",  # R
            "carried_advance",  # S
            "admin_penalty_days",  # T
            "admin_penalty_value",  # U
            "fingerprint_penalty_days",  # V
            "fingerprint_penalty_value",  # W
            "unexcused_absence_days",  # X
            "unexcused_absence_value",  # Y
            "sick_days",  # Z
            "sick_value",  # AA
            "insurable_salary",  # AB
            "insurance_and_tax",  # AC
            "deviations",  # AD
            "shortage_custody",  # AE
            "total_deductions",  # AF
            "net_salary",  # AG
            "notes",  # AH
            "overrides",
            "warnings",
        ]
        read_only_fields = [
            "id",
            "employee",
            "employee_code",
            "employee_name",
            "branch_snapshot",
            "job_title_snapshot",
            "overrides",
            "warnings",
        ]


class PayrollLineOverrideSerializer(serializers.Serializer):
    """PATCH body for the review grid: only aggregated inputs may be overridden."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in OVERRIDABLE_FIELDS:
            self.fields[name] = serializers.DecimalField(
                max_digits=14, decimal_places=2, required=False
            )
        self.fields["notes"] = serializers.CharField(required=False, allow_blank=True)


class MonthlyAdjustmentSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source="employee.code", read_only=True)
    employee_name = serializers.CharField(source="employee.name_ar", read_only=True)
    amount = MoneyField()

    class Meta:
        model = MonthlyAdjustment
        fields = [
            "id",
            "period",
            "employee",
            "employee_code",
            "employee_name",
            "kind",
            "amount",
            "note",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class LoanSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source="employee.code", read_only=True)
    employee_name = serializers.CharField(source="employee.name_ar", read_only=True)
    total = MoneyField()
    monthly_installment = MoneyField()
    remaining = MoneyField(required=False)

    class Meta:
        model = Loan
        fields = [
            "id",
            "employee",
            "employee_code",
            "employee_name",
            "total",
            "monthly_installment",
            "remaining",
            "start_year",
            "start_month",
            "is_active",
            "note",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        validated_data.setdefault("remaining", validated_data["total"])
        return super().create(validated_data)


class PeriodTotalsSerializer(serializers.Serializer):
    base_salary = MoneyField()
    total_earnings = MoneyField()
    total_deductions = MoneyField()
    net_salary = MoneyField()
    employee_count = serializers.IntegerField()
