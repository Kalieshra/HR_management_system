"""API v1 routing. Everything tenant-scoped reads `X-Company-Id`."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from attendance.views import DailyRecordViewSet
from companies.views import (
    BranchViewSet,
    CompanySettingsView,
    MembershipViewSet,
    PayrollPolicyViewSet,
    PlatformCompanyViewSet,
    PlatformStatsView,
)
from core import views
from employees.views import EmployeeViewSet, SalaryHistoryViewSet
from payroll.views import (
    DashboardView,
    LoanViewSet,
    MonthlyAdjustmentViewSet,
    PayrollLineViewSet,
    PeriodViewSet,
)
from reports.views import ReportFileViewSet

app_name = "core"

router = DefaultRouter()
# Platform owner
router.register("platform/companies", PlatformCompanyViewSet, basename="platform-company")
router.register("platform/stats", PlatformStatsView, basename="platform-stats")
# Company settings
router.register("branches", BranchViewSet, basename="branch")
router.register("policy", PayrollPolicyViewSet, basename="policy")
router.register("users", MembershipViewSet, basename="membership")
# Core data
router.register("employees", EmployeeViewSet, basename="employee")
router.register("salary-history", SalaryHistoryViewSet, basename="salary-history")
router.register("daily-records", DailyRecordViewSet, basename="daily-record")
# Payroll
router.register("periods", PeriodViewSet, basename="period")
router.register("lines", PayrollLineViewSet, basename="line")
router.register("adjustments", MonthlyAdjustmentViewSet, basename="adjustment")
router.register("loans", LoanViewSet, basename="loan")
# Reports
router.register("reports", ReportFileViewSet, basename="report")

urlpatterns = [
    path("health/", views.HealthView.as_view(), name="health"),
    path("health/ready/", views.ReadyView.as_view(), name="ready"),
    path("auth/", include("accounts.urls")),
    path("company", CompanySettingsView.as_view(), name="company-settings"),
    path("dashboard/summary", DashboardView.as_view(), name="dashboard-summary"),
    path("", include(router.urls)),
]
