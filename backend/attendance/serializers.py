"""Daily attendance serializers, including the grid's bulk upsert payload."""

from rest_framework import serializers

from attendance.models import AttendanceStatus, DailyRecord
from core.fields import QuantityField


class DailyRecordSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source="employee.code", read_only=True)
    employee_name = serializers.CharField(source="employee.name_ar", read_only=True)
    branch_id = serializers.IntegerField(source="employee.branch_id", read_only=True)
    overtime_hours = QuantityField(required=False)
    late_hours = QuantityField(required=False)
    admin_penalty_days = QuantityField(required=False)
    fingerprint_penalty_days = QuantityField(required=False)

    class Meta:
        model = DailyRecord
        fields = [
            "id",
            "employee",
            "employee_code",
            "employee_name",
            "branch_id",
            "date",
            "status",
            "overtime_hours",
            "late_hours",
            "admin_penalty_days",
            "fingerprint_penalty_days",
            "note",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]


class BulkRowSerializer(serializers.Serializer):
    """One cell-row of the daily-entry grid."""

    employee = serializers.IntegerField()
    date = serializers.DateField()
    status = serializers.ChoiceField(choices=AttendanceStatus.choices)
    overtime_hours = serializers.DecimalField(max_digits=6, decimal_places=2, required=False)
    late_hours = serializers.DecimalField(max_digits=6, decimal_places=2, required=False)
    admin_penalty_days = serializers.DecimalField(max_digits=6, decimal_places=2, required=False)
    fingerprint_penalty_days = serializers.DecimalField(
        max_digits=6, decimal_places=2, required=False
    )
    note = serializers.CharField(required=False, allow_blank=True, max_length=300)


class BulkUpsertSerializer(serializers.Serializer):
    rows = serializers.ListField(child=BulkRowSerializer(), max_length=500)


class DayCompletionSerializer(serializers.Serializer):
    date = serializers.DateField()
    recorded = serializers.IntegerField()
    expected = serializers.IntegerField()
    complete = serializers.BooleanField()
