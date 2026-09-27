"""Report history, generation and delivery."""

from django.http import FileResponse, Http404
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from audit.services import record_audit
from core.permissions import HasCompanyAccess, IsCompanyAdmin
from core.viewsets import TenantViewSet
from payroll.models import PayrollLine, Period
from reports.models import ReportFile, ReportKind
from reports.serializers import ReportFileSerializer
from reports.services.generator import generate_excel
from reports.services.mailer import send_monthly_report
from reports.services.pdf import generate_payslips


class ReportFileViewSet(TenantViewSet):
    """Browse generated files, make new ones, and email them."""

    serializer_class = ReportFileSerializer
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["period", "kind"]

    def get_queryset(self):
        company = self.company
        if company is None:
            return ReportFile.objects.none()
        return (
            ReportFile.objects.for_company(company)
            .select_related("period")
            .order_by("-generated_at")
        )

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasCompanyAccess(), IsCompanyAdmin()]
        return [HasCompanyAccess()]

    def _period(self, period_id):
        period = Period.objects.for_company(self.company).filter(pk=period_id).first()
        if period is None:
            raise Http404
        return period

    def _require_lines(self, period):
        if not PayrollLine.objects.for_company(self.company).filter(period=period).exists():
            return Response(
                {"detail": _("Calculate the period before generating a report.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None

    @extend_schema(request=None, responses={201: ReportFileSerializer}, tags=["reports"])
    @action(detail=False, methods=["post"], url_path=r"(?P<period_id>\d+)/xlsx")
    def xlsx(self, request, period_id=None):
        period = self._period(period_id)
        if (problem := self._require_lines(period)) is not None:
            return problem

        report = generate_excel(period, user=request.user)
        record_audit(
            company=self.company,
            user=request.user,
            action="create",
            instance=report,
            after={"kind": "xlsx", "period": str(period)},
        )
        return Response(self.get_serializer(report).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={201: ReportFileSerializer}, tags=["reports"])
    @action(detail=False, methods=["post"], url_path=r"(?P<period_id>\d+)/payslips")
    def payslips(self, request, period_id=None):
        period = self._period(period_id)
        if (problem := self._require_lines(period)) is not None:
            return problem

        report = generate_payslips(period, user=request.user)
        record_audit(
            company=self.company,
            user=request.user,
            action="create",
            instance=report,
            after={"kind": "pdf", "period": str(period)},
        )
        return Response(self.get_serializer(report).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: dict}, tags=["reports"])
    @action(detail=False, methods=["post"], url_path=r"(?P<period_id>\d+)/email")
    def email(self, request, period_id=None):
        """Generate (if needed) and send the workbook to the report recipients."""
        period = self._period(period_id)
        if (problem := self._require_lines(period)) is not None:
            return problem

        recipients = request.data.get("recipients") or list(self.company.report_emails or [])
        if not recipients:
            return Response(
                {"detail": _("Add at least one report recipient in settings first.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        report = (
            ReportFile.objects.for_company(self.company)
            .filter(period=period, kind=ReportKind.XLSX)
            .order_by("-generated_at")
            .first()
        )
        if report is None:
            report = generate_excel(period, user=request.user)

        sent = send_monthly_report(period, report, recipients)
        record_audit(
            company=self.company,
            user=request.user,
            action="update",
            instance=report,
            after={"emailed_to": recipients},
        )
        return Response({"sent": sent, "recipients": recipients, "report": report.pk})

    @extend_schema(responses={200: bytes}, tags=["reports"])
    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        report = self.get_object()
        if not report.file:
            raise Http404
        return FileResponse(
            report.file.open("rb"),
            as_attachment=True,
            filename=report.file.name.rsplit("/", 1)[-1],
        )
