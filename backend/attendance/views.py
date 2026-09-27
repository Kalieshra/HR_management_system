"""Daily-entry endpoints. The grid autosaves through `bulk`."""

from datetime import date as date_cls

from django.db import transaction
from django.db.models import Count
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from attendance.models import DailyRecord
from attendance.serializers import (
    BulkUpsertSerializer,
    DailyRecordSerializer,
    DayCompletionSerializer,
)
from audit.services import record_audit, serialise
from core.pagination import LargePagination
from core.permissions import CanEnterBranchData, HasCompanyAccess, allowed_branch_ids
from core.viewsets import TenantViewSet
from employees.models import Employee
from payroll.models import Period
from payroll.services.cache import invalidate_company_cache
from payroll.services.runner import assert_period_open


class DailyRecordViewSet(TenantViewSet):
    serializer_class = DailyRecordSerializer
    permission_classes = [HasCompanyAccess, CanEnterBranchData]
    pagination_class = LargePagination
    filterset_fields = ["employee", "date", "status"]
    branch_scoped = True
    branch_lookup = "employee__branch_id"

    def get_queryset(self):
        queryset = DailyRecord.objects.select_related("employee", "employee__branch")
        company = self.company
        if company is None:
            return queryset.none()

        queryset = self.apply_branch_scope(queryset.for_company(company))

        params = self.request.query_params
        if branch := params.get("branch"):
            queryset = queryset.filter(employee__branch_id=branch)
        if date_from := params.get("date_from"):
            queryset = queryset.filter(date__gte=date_from)
        if date_to := params.get("date_to"):
            queryset = queryset.filter(date__lte=date_to)
        return queryset.order_by("date", "employee__code")

    def _guard_period(self, on_date):
        """Refuse to touch a day that belongs to a closed month."""
        period = (
            Period.objects.for_company(self.company)
            .filter(year=on_date.year, month=on_date.month)
            .first()
        )
        if period is not None:
            assert_period_open(period)

    def perform_create(self, serializer):
        self._guard_period(serializer.validated_data["date"])
        record = serializer.save(company=self.company, entered_by=self.request.user)
        invalidate_company_cache(self.company.pk)
        record_audit(
            company=self.company,
            user=self.request.user,
            action="create",
            instance=record,
            after=serialise(record),
        )

    def perform_update(self, serializer):
        self._guard_period(serializer.instance.date)
        before = serialise(serializer.instance)
        record = serializer.save(entered_by=self.request.user)
        invalidate_company_cache(self.company.pk)
        record_audit(
            company=self.company,
            user=self.request.user,
            action="update",
            instance=record,
            before=before,
            after=serialise(record),
        )

    def perform_destroy(self, instance):
        self._guard_period(instance.date)
        record_audit(
            company=self.company,
            user=self.request.user,
            action="delete",
            instance=instance,
            before=serialise(instance),
        )
        instance.delete()
        invalidate_company_cache(self.company.pk)

    @extend_schema(request=BulkUpsertSerializer, responses={200: dict}, tags=["attendance"])
    @action(detail=False, methods=["post"])
    def bulk(self, request):
        """Upsert up to 500 rows in one transaction — the grid's autosave."""
        serializer = BulkUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rows = serializer.validated_data["rows"]
        if not rows:
            return Response({"saved": 0, "created": 0, "updated": 0})

        for row in rows:
            self._guard_period(row["date"])

        allowed = allowed_branch_ids(request)
        employee_ids = {row["employee"] for row in rows}
        employees = Employee.objects.for_company(self.company).filter(pk__in=employee_ids)
        if allowed is not None:
            employees = employees.filter(branch_id__in=allowed)
        by_id = {employee.pk: employee for employee in employees}

        unknown = employee_ids - set(by_id)
        if unknown:
            return Response(
                {
                    "detail": _("Unknown or out-of-scope employees: %(ids)s")
                    % {"ids": ", ".join(str(i) for i in sorted(unknown))}
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        created = updated = 0
        with transaction.atomic():
            for row in rows:
                _record, was_created = DailyRecord.all_objects.update_or_create(
                    company=self.company,
                    employee=by_id[row["employee"]],
                    date=row["date"],
                    defaults={
                        "status": row["status"],
                        "overtime_hours": row.get("overtime_hours") or 0,
                        "late_hours": row.get("late_hours") or 0,
                        "admin_penalty_days": row.get("admin_penalty_days") or 0,
                        "fingerprint_penalty_days": row.get("fingerprint_penalty_days") or 0,
                        "note": row.get("note", ""),
                        "entered_by": request.user,
                    },
                )
                created += int(was_created)
                updated += int(not was_created)

        invalidate_company_cache(self.company.pk)
        record_audit(
            company=self.company,
            user=request.user,
            action="update",
            model="DailyRecordBulk",
            after={"created": created, "updated": updated},
        )
        return Response({"saved": len(rows), "created": created, "updated": updated})

    @extend_schema(responses={200: DayCompletionSerializer(many=True)}, tags=["attendance"])
    @action(detail=False, methods=["get"])
    def calendar(self, request):
        """Per-day completion for the month — drives the calendar strip."""
        year = int(request.query_params.get("year", date_cls.today().year))
        month = int(request.query_params.get("month", date_cls.today().month))
        branch = request.query_params.get("branch")

        employees = Employee.objects.for_company(self.company).filter(is_active=True)
        allowed = allowed_branch_ids(request)
        if allowed is not None:
            employees = employees.filter(branch_id__in=allowed)
        if branch:
            employees = employees.filter(branch_id=branch)
        expected = employees.count()

        counts = (
            self.get_queryset()
            .filter(date__year=year, date__month=month)
            .values("date")
            .annotate(recorded=Count("id"))
        )
        by_date = {row["date"]: row["recorded"] for row in counts}

        import calendar as cal

        days = cal.monthrange(year, month)[1]
        payload = []
        for day in range(1, days + 1):
            on = date_cls(year, month, day)
            recorded = by_date.get(on, 0)
            payload.append(
                {
                    "date": on,
                    "recorded": recorded,
                    "expected": expected,
                    "complete": expected > 0 and recorded >= expected,
                }
            )
        return Response(DayCompletionSerializer(payload, many=True).data)

    @extend_schema(request=None, responses={200: dict}, tags=["attendance"])
    @action(detail=False, methods=["post"], url_path="copy-from")
    def copy_from(self, request):
        """Copy a previous day's rows onto a target day."""
        source = request.data.get("source_date")
        target = request.data.get("target_date")
        if not source or not target:
            return Response(
                {"detail": _("Both source_date and target_date are required.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_date = date_cls.fromisoformat(str(target))
        self._guard_period(target_date)

        source_rows = self.get_queryset().filter(date=source)
        copied = 0
        with transaction.atomic():
            for row in source_rows:
                DailyRecord.all_objects.update_or_create(
                    company=self.company,
                    employee_id=row.employee_id,
                    date=target_date,
                    defaults={
                        "status": row.status,
                        "overtime_hours": row.overtime_hours,
                        "late_hours": row.late_hours,
                        "admin_penalty_days": row.admin_penalty_days,
                        "fingerprint_penalty_days": row.fingerprint_penalty_days,
                        "note": row.note,
                        "entered_by": request.user,
                    },
                )
                copied += 1

        invalidate_company_cache(self.company.pk)
        return Response({"copied": copied})
