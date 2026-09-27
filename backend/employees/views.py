"""Employee endpoints, including the Excel import wizard."""

from django.http import HttpResponse
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from audit.services import record_audit, serialise
from core.permissions import HasCompanyAccess, IsCompanyAdmin
from core.viewsets import TenantViewSet
from employees import services
from employees.models import Employee, SalaryHistory
from employees.serializers import EmployeeSerializer, SalaryHistorySerializer


class EmployeeViewSet(TenantViewSet):
    serializer_class = EmployeeSerializer
    filterset_fields = ["branch", "is_active"]
    search_fields = ["code", "name_ar", "name_en", "job_title", "national_id"]
    ordering_fields = ["code", "name_ar", "base_salary"]
    branch_scoped = True

    def get_queryset(self):
        queryset = Employee.objects.select_related("branch").order_by("code")
        company = self.company
        if company is None:
            return queryset.none()
        return self.apply_branch_scope(queryset.for_company(company))

    def get_permissions(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return [HasCompanyAccess(), IsCompanyAdmin()]
        return [HasCompanyAccess()]

    def perform_create(self, serializer):
        employee = serializer.save(company=self.company)
        record_audit(
            company=self.company,
            user=self.request.user,
            action="create",
            instance=employee,
            after=serialise(employee),
        )

    def perform_update(self, serializer):
        before = serialise(serializer.instance)
        employee = serializer.save()
        after = serialise(employee)
        record_audit(
            company=self.company,
            user=self.request.user,
            action="update",
            instance=employee,
            before=before,
            after=after,
        )

    def perform_destroy(self, instance):
        record_audit(
            company=self.company,
            user=self.request.user,
            action="delete",
            instance=instance,
            before=serialise(instance),
        )
        # Employees are deactivated rather than deleted so history survives.
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])

    @extend_schema(responses={200: SalaryHistorySerializer(many=True)}, tags=["employees"])
    @action(detail=True, methods=["get"], url_path="salary-history")
    def salary_history(self, request, pk=None):
        employee = self.get_object()
        queryset = employee.salary_history.order_by("-effective_from")
        return Response(SalaryHistorySerializer(queryset, many=True).data)

    @extend_schema(
        request=SalaryHistorySerializer,
        responses={201: SalaryHistorySerializer},
        tags=["employees"],
    )
    @salary_history.mapping.post
    def add_salary(self, request, pk=None):
        employee = self.get_object()
        serializer = SalaryHistorySerializer(data={**request.data, "employee": employee.pk})
        serializer.is_valid(raise_exception=True)
        record = serializer.save(company=self.company, employee=employee)

        # The master row tracks the newest salary so new periods pick it up.
        latest = employee.salary_history.order_by("-effective_from").first()
        if latest and latest.pk == record.pk:
            employee.base_salary = record.base_salary
            employee.insurable_salary = record.insurable_salary
            employee.save(update_fields=["base_salary", "insurable_salary", "updated_at"])

        record_audit(
            company=self.company,
            user=request.user,
            action="update",
            instance=employee,
            after={"base_salary": str(record.base_salary), "from": str(record.effective_from)},
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={200: bytes}, tags=["employees"])
    @action(detail=False, methods=["get"], url_path="import-template")
    def import_template(self, request):
        content = services.build_template()
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="employees-template.xlsx"'
        return response

    @extend_schema(request=None, responses={200: dict}, tags=["employees"])
    @action(
        detail=False,
        methods=["post"],
        url_path="import",
        parser_classes=[MultiPartParser, FormParser],
        permission_classes=[HasCompanyAccess, IsCompanyAdmin],
    )
    def import_preview(self, request):
        """Upload a sheet and get back a per-row preview with errors."""
        uploaded = request.FILES.get("file")
        if uploaded is None:
            return Response(
                {"detail": _("Attach a file to import.")}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            rows = services.read_upload(uploaded)
        except Exception as exc:
            return Response(
                {"detail": _("That file could not be read: %(error)s") % {"error": exc}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid, errors = services.validate_rows(self.company, rows)
        return Response(
            {
                "total": len(rows),
                "valid": [
                    {k: str(v) if k == "branch" else v for k, v in row.items() if k != "branch"}
                    | {"branch_name": row["branch_name"]}
                    for row in valid
                ],
                "errors": errors,
                "summary": {
                    "create": sum(1 for row in valid if row["action"] == "create"),
                    "update": sum(1 for row in valid if row["action"] == "update"),
                    "failed": len(errors),
                },
            }
        )

    @extend_schema(request=None, responses={200: dict}, tags=["employees"])
    @action(
        detail=False,
        methods=["post"],
        url_path="import/commit",
        parser_classes=[MultiPartParser, FormParser],
        permission_classes=[HasCompanyAccess, IsCompanyAdmin],
    )
    def import_commit(self, request):
        """Re-validate the same upload and write the valid rows."""
        uploaded = request.FILES.get("file")
        if uploaded is None:
            return Response(
                {"detail": _("Attach a file to import.")}, status=status.HTTP_400_BAD_REQUEST
            )

        rows = services.read_upload(uploaded)
        valid, errors = services.validate_rows(self.company, rows)
        result = services.commit_rows(self.company, valid)

        record_audit(
            company=self.company,
            user=request.user,
            action="create",
            model="EmployeeImport",
            after=result,
        )
        return Response({**result, "failed": len(errors), "errors": errors})


class SalaryHistoryViewSet(TenantViewSet):
    serializer_class = SalaryHistorySerializer
    permission_classes = [HasCompanyAccess, IsCompanyAdmin]
    filterset_fields = ["employee"]

    def get_queryset(self):
        company = self.company
        if company is None:
            return SalaryHistory.objects.none()
        return (
            SalaryHistory.objects.for_company(company)
            .select_related("employee")
            .order_by("-effective_from")
        )
