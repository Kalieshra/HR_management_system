"""Tenant isolation across every tenant-owned endpoint.

For each endpoint: a signed-in user of company A, sending A's `X-Company-Id`,
must never see or be able to touch company B's rows. Listing must exclude them
and detail/update/delete must 404 — not 403, which would confirm the row exists.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from accounts.models import Role
from attendance.models import DailyRecord
from core.factories import (
    BranchFactory,
    CompanyFactory,
    EmployeeFactory,
    MembershipFactory,
    PayrollPolicyFactory,
    PeriodFactory,
    UserFactory,
)
from employees.models import SalaryHistory
from payroll.models import AdjustmentKind, Loan, MonthlyAdjustment, PayrollLine
from reports.models import ReportFile

pytestmark = pytest.mark.django_db

PASSWORD = "TestPass!2026"


class Tenant:
    """A company with one admin and one row of every tenant-owned model."""

    def __init__(self, label):
        self.company = CompanyFactory(slug=f"tenant-{label}")
        PayrollPolicyFactory(company=self.company)
        self.branch = BranchFactory(company=self.company, name_ar=f"فرع {label}")
        self.user = UserFactory(email=f"admin-{label}@example.test", password=PASSWORD)
        MembershipFactory(user=self.user, company=self.company, role=Role.COMPANY_ADMIN)

        self.employee = EmployeeFactory(
            company=self.company, branch=self.branch, code=f"{label}-001"
        )
        self.period = PeriodFactory(company=self.company)
        self.daily = DailyRecord.all_objects.create(
            company=self.company, employee=self.employee, date=date(2026, 2, 3)
        )
        self.adjustment = MonthlyAdjustment.all_objects.create(
            company=self.company,
            period=self.period,
            employee=self.employee,
            kind=AdjustmentKind.BONUS,
            amount=Decimal("100"),
        )
        self.loan = Loan.all_objects.create(
            company=self.company,
            employee=self.employee,
            total=Decimal("1000"),
            monthly_installment=Decimal("100"),
            remaining=Decimal("1000"),
            start_year=2026,
            start_month=1,
        )
        self.line = PayrollLine.all_objects.create(
            company=self.company,
            period=self.period,
            employee=self.employee,
            employee_code=self.employee.code,
            employee_name=self.employee.name_ar,
        )
        self.salary = SalaryHistory.all_objects.create(
            company=self.company,
            employee=self.employee,
            base_salary=Decimal("6000"),
            insurable_salary=Decimal("0"),
            effective_from=date(2025, 1, 1),
        )
        self.report = ReportFile.all_objects.create(
            company=self.company, period=self.period, kind="xlsx"
        )
        self.policy = self.company.payrollpolicys.first()
        self.membership = self.user.memberships.first()


@pytest.fixture
def alpha():
    return Tenant("a")


@pytest.fixture
def beta():
    return Tenant("b")


@pytest.fixture
def as_alpha(api, alpha):
    api.post(
        reverse("core:accounts:login"),
        {"email": alpha.user.email, "password": PASSWORD},
        format="json",
    )
    api.credentials(HTTP_X_COMPANY_ID=str(alpha.company.pk))
    return api


#: (route basename, attribute on Tenant holding the foreign row)
ENDPOINTS = [
    ("core:branch", "branch"),
    ("core:employee", "employee"),
    ("core:daily-record", "daily"),
    ("core:period", "period"),
    ("core:adjustment", "adjustment"),
    ("core:loan", "loan"),
    ("core:line", "line"),
    ("core:salary-history", "salary"),
    ("core:report", "report"),
    ("core:policy", "policy"),
    ("core:membership", "membership"),
]


@pytest.mark.parametrize(("basename", "attr"), ENDPOINTS)
def test_list_never_includes_another_companys_rows(as_alpha, alpha, beta, basename, attr):
    response = as_alpha.get(reverse(f"{basename}-list"))

    assert response.status_code == 200
    body = response.json()
    rows = body["results"] if isinstance(body, dict) and "results" in body else body
    foreign_id = getattr(beta, attr).pk
    assert all(row["id"] != foreign_id for row in rows), f"{basename} leaked a foreign row"


@pytest.mark.parametrize(("basename", "attr"), ENDPOINTS)
def test_detail_of_another_companys_row_is_404(as_alpha, beta, basename, attr):
    url = reverse(f"{basename}-detail", args=[getattr(beta, attr).pk])

    assert as_alpha.get(url).status_code == 404


#: Endpoints that expose no write verbs at all, so they answer 405 for every
#: id — existing or not — and therefore leak nothing.
READ_ONLY = {"core:report"}
WRITABLE = [e for e in ENDPOINTS if e[0] not in READ_ONLY]


@pytest.mark.parametrize(
    ("basename", "attr"),
    [e for e in WRITABLE if e[0] != "core:line"],
)
def test_delete_of_another_companys_row_is_404(as_alpha, beta, basename, attr):
    url = reverse(f"{basename}-detail", args=[getattr(beta, attr).pk])

    assert as_alpha.delete(url).status_code == 404


@pytest.mark.parametrize(("basename", "attr"), WRITABLE)
def test_patch_of_another_companys_row_is_404(as_alpha, beta, basename, attr):
    url = reverse(f"{basename}-detail", args=[getattr(beta, attr).pk])

    assert as_alpha.patch(url, {}, format="json").status_code == 404


@pytest.mark.parametrize("basename", sorted(READ_ONLY))
def test_read_only_endpoints_reject_writes_for_everyone(as_alpha, alpha, beta, basename):
    """405 before any lookup, so it cannot be used to probe for foreign rows."""
    own = reverse(f"{basename}-detail", args=[alpha.report.pk])
    foreign = reverse(f"{basename}-detail", args=[beta.report.pk])
    missing = reverse(f"{basename}-detail", args=[99999])

    assert as_alpha.delete(own).status_code == 405
    assert as_alpha.delete(foreign).status_code == 405
    assert as_alpha.delete(missing).status_code == 405


def test_own_rows_are_reachable(as_alpha, alpha):
    """The isolation tests would pass trivially if nothing were visible."""
    for basename, attr in ENDPOINTS:
        url = reverse(f"{basename}-detail", args=[getattr(alpha, attr).pk])
        assert as_alpha.get(url).status_code == 200, basename


def test_period_actions_are_scoped(as_alpha, beta):
    for verb in ("calculate", "close", "reopen"):
        url = reverse(f"core:period-{verb}", args=[beta.period.pk])
        assert as_alpha.post(url).status_code == 404, verb

    url = reverse("core:period-lines", args=[beta.period.pk])
    assert as_alpha.get(url).status_code == 404


def test_employee_salary_history_action_is_scoped(as_alpha, beta):
    url = reverse("core:employee-salary-history", args=[beta.employee.pk])

    assert as_alpha.get(url).status_code == 404


def test_cannot_create_a_row_pointing_at_another_companys_branch(as_alpha, beta):
    response = as_alpha.post(
        reverse("core:employee-list"),
        {
            "code": "SNEAK-1",
            "name_ar": "محاولة",
            "branch": beta.branch.pk,
            "base_salary": "5000",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "branch" in response.json()


def test_created_rows_are_stamped_with_the_active_company(as_alpha, alpha):
    response = as_alpha.post(
        reverse("core:employee-list"),
        {
            "code": "NEW-1",
            "name_ar": "موظف جديد",
            "branch": alpha.branch.pk,
            "base_salary": "5000",
        },
        format="json",
    )

    assert response.status_code == 201
    from employees.models import Employee

    created = Employee.all_objects.get(code="NEW-1")
    assert created.company_id == alpha.company.pk


def test_dashboard_is_scoped(as_alpha, alpha, beta):
    response = as_alpha.get(reverse("core:dashboard-summary"))

    assert response.status_code == 200
    # alpha has exactly one employee; beta's must not be counted.
    assert response.json()["employees"] == 1


def test_bulk_daily_entry_rejects_another_companys_employee(as_alpha, beta):
    response = as_alpha.post(
        reverse("core:daily-record-bulk"),
        {"rows": [{"employee": beta.employee.pk, "date": "2026-02-10", "status": "present"}]},
        format="json",
    )

    assert response.status_code == 400
