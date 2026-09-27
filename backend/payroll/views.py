"""Payroll endpoints: periods, the review grid, adjustments and loans."""

from decimal import Decimal

from django.core.cache import cache
from django.db.models import Count, Sum
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.services import record_audit, serialise
from core.middleware import resolve_company
from core.permissions import HasCompanyAccess, IsCompanyAdmin
from core.viewsets import TenantViewSet
from payroll.models import Loan, MonthlyAdjustment, PayrollLine, Period, PeriodStatus
from payroll.serializers import (
    LoanSerializer,
    MonthlyAdjustmentSerializer,
    PayrollLineOverrideSerializer,
    PayrollLineSerializer,
    PeriodSerializer,
)
from payroll.services.aggregate import OVERRIDABLE_FIELDS
from payroll.services.cache import LINES_TTL, invalidate_company_cache, lines_totals_key
from payroll.services.engine import quantize_display
from payroll.services.runner import (
    ASYNC_THRESHOLD,
    assert_period_open,
    close_period,
    reopen_period,
    run_period,
)

TOTAL_COLUMNS = [
    "base_salary",
    "work_days",
    "work_days_value",
    "overtime_hours",
    "overtime_value",
    "leave_allowance_days",
    "leave_allowance_value",
    "bonus",
    "other_earnings",
    "total_earnings",
    "late_hours",
    "late_value",
    "advances",
    "carried_advance",
    "admin_penalty_days",
    "admin_penalty_value",
    "fingerprint_penalty_days",
    "fingerprint_penalty_value",
    "unexcused_absence_days",
    "unexcused_absence_value",
    "sick_days",
    "sick_value",
    "insurable_salary",
    "insurance_and_tax",
    "deviations",
    "shortage_custody",
    "total_deductions",
    "net_salary",
]


def _totals_for(queryset) -> dict:
    aggregates = queryset.aggregate(
        **{column: Sum(column) for column in TOTAL_COLUMNS},
        employee_count=Count("id"),
    )
    result = {"employee_count": aggregates.pop("employee_count") or 0}
    for column, value in aggregates.items():
        result[column] = str(quantize_display(value or Decimal("0")))
    return result


class PeriodViewSet(TenantViewSet):
    serializer_class = PeriodSerializer
    filterset_fields = ["year", "month", "status"]

    def get_queryset(self):
        company = self.company
        if company is None:
            return Period.objects.none()
        return (
            Period.objects.for_company(company)
            .annotate(line_count=Count("lines"))
            .order_by("-year", "-month")
        )

    def get_permissions(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return [HasCompanyAccess(), IsCompanyAdmin()]
        return [HasCompanyAccess()]

    @extend_schema(request=None, responses={200: dict}, tags=["payroll"])
    @action(detail=True, methods=["post"], permission_classes=[HasCompanyAccess, IsCompanyAdmin])
    def calculate(self, request, pk=None):
        """Recalculate the period — inline for small companies, Celery for large."""
        period = self.get_object()
        assert_period_open(period)

        from employees.models import Employee

        headcount = Employee.objects.for_company(self.company).filter(is_active=True).count()

        if headcount > ASYNC_THRESHOLD:
            from payroll.tasks import calculate_period_task

            task = calculate_period_task.delay(period.pk, request.user.pk)
            return Response(
                {"queued": True, "task_id": task.id, "employees": headcount},
                status=status.HTTP_202_ACCEPTED,
            )

        lines = run_period(period, user=request.user)
        invalidate_company_cache(self.company.pk)
        period.refresh_from_db()
        return Response({"queued": False, "lines": len(lines), "status": period.status})

    @extend_schema(responses={200: PayrollLineSerializer(many=True)}, tags=["payroll"])
    @action(detail=True, methods=["get"])
    def lines(self, request, pk=None):
        """Every line of the period, plus company and per-branch totals."""
        period = self.get_object()
        queryset = PayrollLine.objects.for_company(self.company).filter(period=period)

        if branch := request.query_params.get("branch"):
            queryset = queryset.filter(branch_snapshot=branch)

        queryset = queryset.order_by("employee_code")

        key = lines_totals_key(self.company.pk, period.pk)
        cached = cache.get(key)
        if cached is None:
            all_lines = PayrollLine.objects.for_company(self.company).filter(period=period)
            branches = sorted(set(all_lines.values_list("branch_snapshot", flat=True)))
            cached = {
                "totals": _totals_for(all_lines),
                "by_branch": {
                    name: _totals_for(all_lines.filter(branch_snapshot=name)) for name in branches
                },
                "branches": branches,
            }
            cache.set(key, cached, LINES_TTL)

        return Response(
            {
                "period": PeriodSerializer(period).data,
                "results": PayrollLineSerializer(queryset, many=True).data,
                **cached,
            }
        )

    @extend_schema(request=None, responses={200: PeriodSerializer}, tags=["payroll"])
    @action(detail=True, methods=["post"], permission_classes=[HasCompanyAccess, IsCompanyAdmin])
    def close(self, request, pk=None):
        period = self.get_object()
        if not PayrollLine.objects.for_company(self.company).filter(period=period).exists():
            return Response(
                {"detail": _("Calculate the period before closing it.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        close_period(period, user=request.user)
        invalidate_company_cache(self.company.pk)
        return Response(PeriodSerializer(period).data)

    @extend_schema(request=None, responses={200: PeriodSerializer}, tags=["payroll"])
    @action(detail=True, methods=["post"], permission_classes=[HasCompanyAccess, IsCompanyAdmin])
    def reopen(self, request, pk=None):
        period = self.get_object()
        reopen_period(period, user=request.user)
        invalidate_company_cache(self.company.pk)
        return Response(PeriodSerializer(period).data)


class PayrollLineViewSet(TenantViewSet):
    """Read lines and PATCH overrides onto them."""

    serializer_class = PayrollLineSerializer
    http_method_names = ["get", "patch", "head", "options"]
    filterset_fields = ["period", "branch_snapshot"]
    search_fields = ["employee_code", "employee_name"]

    def get_queryset(self):
        company = self.company
        if company is None:
            return PayrollLine.objects.none()
        return PayrollLine.objects.for_company(company).order_by("employee_code")

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [HasCompanyAccess(), IsCompanyAdmin()]
        return [HasCompanyAccess()]

    def partial_update(self, request, *args, **kwargs):
        line = self.get_object()
        assert_period_open(line.period)

        serializer = PayrollLineOverrideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        changes = serializer.validated_data
        if not changes:
            return Response(PayrollLineSerializer(line).data)

        before = serialise(line)
        overrides = dict(line.overrides or {})

        for field_name, value in changes.items():
            if field_name == "notes":
                line.notes = value
                continue
            if field_name not in OVERRIDABLE_FIELDS:
                continue
            if field_name not in overrides:
                overrides[field_name] = str(getattr(line, field_name))
            setattr(line, field_name, value)

        line.overrides = overrides
        line.save()

        # Recalculate just this line so the derived columns stay consistent.
        _recalculate_single(line, self.company)

        invalidate_company_cache(self.company.pk)
        record_audit(
            company=self.company,
            user=request.user,
            action="override",
            instance=line,
            before=before,
            after=serialise(line),
        )
        line.refresh_from_db()
        return Response(PayrollLineSerializer(line).data)


def _recalculate_single(line, company) -> None:
    from companies.services import resolve_policy
    from payroll.services.aggregate import to_line_inputs
    from payroll.services.engine import PolicyValues, calculate_line

    policy = resolve_policy(company, line.period.start_date)
    values = {name: getattr(line, name) for name in OVERRIDABLE_FIELDS}
    values["base_salary"] = line.base_salary
    values["daily_hours"] = line.daily_hours

    result = calculate_line(to_line_inputs(values), PolicyValues.from_policy(policy))
    for field_name, value in result.as_dict().items():
        setattr(line, field_name, value)
    line.warnings = list(result.warnings)
    line.save()


class MonthlyAdjustmentViewSet(TenantViewSet):
    serializer_class = MonthlyAdjustmentSerializer
    filterset_fields = ["period", "employee", "kind"]
    branch_scoped = True
    branch_lookup = "employee__branch_id"

    def get_queryset(self):
        company = self.company
        if company is None:
            return MonthlyAdjustment.objects.none()
        queryset = MonthlyAdjustment.objects.for_company(company).select_related("employee")
        return self.apply_branch_scope(queryset).order_by("employee__code", "kind")

    def get_permissions(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return [HasCompanyAccess(), IsCompanyAdmin()]
        return [HasCompanyAccess()]

    def perform_create(self, serializer):
        period = serializer.validated_data["period"]
        assert_period_open(period)
        adjustment = serializer.save(company=self.company, created_by=self.request.user)
        invalidate_company_cache(self.company.pk)
        record_audit(
            company=self.company,
            user=self.request.user,
            action="create",
            instance=adjustment,
            after=serialise(adjustment),
        )

    def perform_update(self, serializer):
        assert_period_open(serializer.instance.period)
        before = serialise(serializer.instance)
        adjustment = serializer.save()
        invalidate_company_cache(self.company.pk)
        record_audit(
            company=self.company,
            user=self.request.user,
            action="update",
            instance=adjustment,
            before=before,
            after=serialise(adjustment),
        )

    def perform_destroy(self, instance):
        assert_period_open(instance.period)
        record_audit(
            company=self.company,
            user=self.request.user,
            action="delete",
            instance=instance,
            before=serialise(instance),
        )
        instance.delete()
        invalidate_company_cache(self.company.pk)


class LoanViewSet(TenantViewSet):
    serializer_class = LoanSerializer
    permission_classes = [HasCompanyAccess, IsCompanyAdmin]
    filterset_fields = ["employee", "is_active"]

    def get_queryset(self):
        company = self.company
        if company is None:
            return Loan.objects.none()
        return (
            Loan.objects.for_company(company).select_related("employee").order_by("employee__code")
        )

    def perform_create(self, serializer):
        loan = serializer.save(company=self.company)
        record_audit(
            company=self.company,
            user=self.request.user,
            action="create",
            instance=loan,
            after=serialise(loan),
        )


class DashboardView(APIView):
    """Read-only summary for the company dashboard (cached for 10 minutes)."""

    permission_classes = [HasCompanyAccess]

    def initial(self, request, *args, **kwargs):
        resolve_company(request)
        super().initial(request, *args, **kwargs)

    @property
    def company(self):
        return getattr(self.request, "company", None)

    @extend_schema(responses={200: dict}, tags=["dashboard"])
    def get(self, request):
        from datetime import date

        from attendance.models import DailyRecord
        from companies.models import Branch
        from employees.models import Employee
        from payroll.services.cache import DASHBOARD_TTL, dashboard_key

        today = date.today()
        year = int(request.query_params.get("year", today.year))
        month = int(request.query_params.get("month", today.month))

        key = dashboard_key(self.company.pk, year, month)
        cached = cache.get(key)
        if cached is not None:
            return Response(cached)

        period = Period.objects.for_company(self.company).filter(year=year, month=month).first()

        employees = Employee.objects.for_company(self.company).filter(is_active=True)
        headcount = employees.count()

        import calendar as cal

        days_in_month = cal.monthrange(year, month)[1]
        elapsed = days_in_month if (year, month) < (today.year, today.month) else today.day
        expected_records = headcount * max(elapsed, 0)

        recorded = (
            DailyRecord.objects.for_company(self.company)
            .filter(date__year=year, date__month=month)
            .count()
        )

        per_branch = []
        for branch in Branch.objects.for_company(self.company).filter(is_active=True):
            branch_heads = employees.filter(branch=branch).count()
            branch_records = (
                DailyRecord.objects.for_company(self.company)
                .filter(date__year=year, date__month=month, employee__branch=branch)
                .count()
            )
            branch_expected = branch_heads * max(elapsed, 0)
            per_branch.append(
                {
                    "branch_id": branch.pk,
                    "branch": branch.name_ar,
                    "employees": branch_heads,
                    "recorded": branch_records,
                    "expected": branch_expected,
                    "completion": round(
                        (branch_records / branch_expected * 100) if branch_expected else 0, 1
                    ),
                }
            )

        totals = {}
        if period is not None:
            lines = PayrollLine.objects.for_company(self.company).filter(period=period)
            totals = _totals_for(lines)

        alerts = []
        missing = employees.filter(base_salary=0)
        if missing.exists():
            alerts.append(
                {
                    "level": "warning",
                    "code": "employees_without_salary",
                    "count": missing.count(),
                }
            )
        if expected_records and recorded < expected_records:
            alerts.append(
                {
                    "level": "info",
                    "code": "missing_daily_records",
                    "count": expected_records - recorded,
                }
            )

        payload = {
            "year": year,
            "month": month,
            "period": PeriodSerializer(period).data if period else None,
            "status": period.status if period else PeriodStatus.OPEN,
            "employees": headcount,
            "branches": Branch.objects.for_company(self.company).filter(is_active=True).count(),
            "completion": round((recorded / expected_records * 100) if expected_records else 0, 1),
            "recorded": recorded,
            "expected": expected_records,
            "per_branch": per_branch,
            "totals": totals,
            "alerts": alerts,
        }
        cache.set(key, payload, DASHBOARD_TTL)
        return Response(payload)
