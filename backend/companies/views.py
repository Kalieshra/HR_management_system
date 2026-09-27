"""Company-scoped endpoints (branches, payroll policy) and platform endpoints."""

from django.db.models import Count, Q
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Invitation, Membership
from accounts.serializers import (
    InvitationCreateSerializer,
    InvitationSerializer,
    MembershipSerializer,
)
from audit.services import record_audit
from companies.models import Branch, Company, PayrollPolicy
from companies.serializers import BranchSerializer, CompanySerializer, PayrollPolicySerializer
from companies.services import invalidate_policy_cache, resolve_policy
from core.middleware import resolve_company
from core.permissions import HasCompanyAccess, IsCompanyAdmin, IsPlatformAdmin
from core.viewsets import TenantViewSet
from employees.models import Employee


class PlatformCompanyViewSet(viewsets.ModelViewSet):
    """Platform owner: open, suspend and inspect company accounts."""

    serializer_class = CompanySerializer
    permission_classes = [IsPlatformAdmin]
    search_fields = ["name_ar", "name_en", "slug"]
    # No DELETE: payroll history is protected by design, so a tenant is
    # suspended rather than destroyed. Use `suspend`/`activate`.
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        return Company.objects.annotate(
            branch_count=Count("branchs", distinct=True),
            employee_count=Count("employees", filter=Q(employees__is_active=True), distinct=True),
        ).order_by("name_ar")

    def perform_create(self, serializer):
        company = serializer.save()
        record_audit(
            company=company,
            user=self.request.user,
            action="create",
            instance=company,
            after=serializer.data,
        )

    @extend_schema(request=None, responses={200: CompanySerializer}, tags=["platform"])
    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        company = self.get_object()
        company.is_active = False
        company.save(update_fields=["is_active", "updated_at"])
        record_audit(
            company=company,
            user=request.user,
            action="update",
            instance=company,
            after={"is_active": False},
        )
        return Response(CompanySerializer(company).data)

    @extend_schema(request=None, responses={200: CompanySerializer}, tags=["platform"])
    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        company = self.get_object()
        company.is_active = True
        company.save(update_fields=["is_active", "updated_at"])
        record_audit(
            company=company,
            user=request.user,
            action="update",
            instance=company,
            after={"is_active": True},
        )
        return Response(CompanySerializer(company).data)

    @extend_schema(
        request=InvitationCreateSerializer,
        responses={201: InvitationSerializer},
        tags=["platform"],
    )
    @action(detail=True, methods=["post"], url_path="invite-admin")
    def invite_admin(self, request, pk=None):
        company = self.get_object()
        serializer = InvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        invitation = Invitation.objects.create(
            email=serializer.validated_data["email"],
            company=company,
            role=serializer.validated_data["role"],
            invited_by=request.user,
        )
        record_audit(
            company=company,
            user=request.user,
            action="create",
            instance=invitation,
            after={"email": invitation.email, "role": invitation.role},
        )
        return Response(InvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)


class PlatformStatsView(viewsets.ViewSet):
    permission_classes = [IsPlatformAdmin]

    @extend_schema(responses={200: dict}, tags=["platform"])
    def list(self, request):
        from accounts.models import User
        from payroll.models import Period, PeriodStatus
        from reports.models import ReportFile

        companies = Company.objects.all()
        return Response(
            {
                "companies_total": companies.count(),
                "companies_active": companies.filter(is_active=True).count(),
                "users_total": User.objects.count(),
                "employees_total": Employee.all_objects.filter(is_active=True).count(),
                "periods_closed": Period.all_objects.filter(status=PeriodStatus.CLOSED).count(),
                "reports_sent": ReportFile.all_objects.exclude(emailed_at=None).count(),
                "recent_reports": list(
                    ReportFile.all_objects.exclude(emailed_at=None)
                    .order_by("-emailed_at")
                    .values("id", "company__name_ar", "kind", "emailed_at")[:10]
                ),
            }
        )


class CompanySettingsView(APIView):
    """The active company's own settings.

    Separate from `platform/companies` because that endpoint belongs to the
    platform owner; a company admin may read and edit only their own tenant.
    """

    permission_classes = [HasCompanyAccess]

    def initial(self, request, *args, **kwargs):
        resolve_company(request)
        super().initial(request, *args, **kwargs)

    @extend_schema(responses={200: CompanySerializer}, tags=["settings"])
    def get(self, request):
        return Response(CompanySerializer(request.company).data)

    @extend_schema(request=CompanySerializer, responses={200: CompanySerializer}, tags=["settings"])
    def patch(self, request):
        if not IsCompanyAdmin().has_permission(request, self):
            return Response(
                {"detail": _("Company administrator access is required.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        # The tenant identity itself is the platform owner's to change.
        editable = {
            key: value
            for key, value in request.data.items()
            if key in {"name_ar", "name_en", "report_emails", "report_day", "report_language"}
        }
        serializer = CompanySerializer(request.company, data=editable, partial=True)
        serializer.is_valid(raise_exception=True)
        company = serializer.save()
        record_audit(
            company=company,
            user=request.user,
            action="update",
            instance=company,
            after=editable,
        )
        return Response(CompanySerializer(company).data)


class BranchViewSet(TenantViewSet):
    serializer_class = BranchSerializer
    filterset_fields = ["is_active"]
    search_fields = ["name_ar", "name_en", "code"]

    def get_queryset(self):
        queryset = Branch.objects.annotate(
            employee_count=Count("employees", filter=Q(employees__is_active=True))
        ).order_by("name_ar")
        company = self.company
        if company is None:
            return queryset.none()
        return queryset.for_company(company)

    def get_permissions(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return [HasCompanyAccess(), IsCompanyAdmin()]
        return [HasCompanyAccess()]


class PayrollPolicyViewSet(TenantViewSet):
    """GET the current policy; POST a new effective-dated version."""

    serializer_class = PayrollPolicySerializer

    def get_queryset(self):
        company = self.company
        if company is None:
            return PayrollPolicy.objects.none()
        return PayrollPolicy.objects.for_company(company).order_by("-effective_from")

    def get_permissions(self):
        if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
            return [HasCompanyAccess(), IsCompanyAdmin()]
        return [HasCompanyAccess()]

    def perform_create(self, serializer):
        policy = serializer.save(company=self.company)
        invalidate_policy_cache(self.company.pk)
        record_audit(
            company=self.company,
            user=self.request.user,
            action="create",
            instance=policy,
            after=serializer.data,
        )

    def perform_update(self, serializer):
        policy = serializer.save()
        invalidate_policy_cache(self.company.pk)
        record_audit(
            company=self.company,
            user=self.request.user,
            action="update",
            instance=policy,
            after=serializer.data,
        )

    @extend_schema(responses={200: PayrollPolicySerializer}, tags=["settings"])
    @action(detail=False, methods=["get"])
    def current(self, request):
        from datetime import date

        policy = resolve_policy(self.company, date.today())
        if policy is None:
            return Response(PayrollPolicySerializer(PayrollPolicy(company=self.company)).data)
        return Response(PayrollPolicySerializer(policy).data)


class MembershipViewSet(viewsets.ModelViewSet):
    """Company users and their branch scope."""

    serializer_class = MembershipSerializer
    permission_classes = [HasCompanyAccess, IsCompanyAdmin]

    def initial(self, request, *args, **kwargs):
        resolve_company(request)
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        company = getattr(self.request, "company", None)
        if company is None:
            return Membership.objects.none()
        return (
            Membership.objects.filter(company=company)
            .select_related("user", "company")
            .prefetch_related("branches")
            .order_by("user__email")
        )

    @extend_schema(
        request=InvitationCreateSerializer, responses={201: InvitationSerializer}, tags=["settings"]
    )
    @action(detail=False, methods=["post"])
    def invite(self, request):
        serializer = InvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        invitation = Invitation.objects.create(
            email=serializer.validated_data["email"],
            company=request.company,
            role=serializer.validated_data["role"],
            invited_by=request.user,
        )
        record_audit(
            company=request.company,
            user=request.user,
            action="create",
            instance=invitation,
            after={"email": invitation.email, "role": invitation.role},
        )
        return Response(InvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={200: InvitationSerializer(many=True)}, tags=["settings"])
    @action(detail=False, methods=["get"])
    def invitations(self, request):
        queryset = Invitation.objects.filter(company=request.company).order_by("-created_at")
        return Response(InvitationSerializer(queryset, many=True).data)

    def destroy(self, request, *args, **kwargs):
        membership = self.get_object()
        if membership.user_id == request.user.pk:
            return Response(
                {"detail": _("You cannot remove your own access.")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)
