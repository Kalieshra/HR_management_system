"""Report endpoints: who may generate, and what comes back."""

from decimal import Decimal

import pytest
from django.core import mail
from django.urls import reverse

from accounts.models import Role
from core.factories import (
    BranchFactory,
    CompanyFactory,
    EmployeeFactory,
    MembershipFactory,
    PayrollPolicyFactory,
    PeriodFactory,
    UserFactory,
)
from payroll.services.runner import run_period

pytestmark = pytest.mark.django_db

PASSWORD = "TestPass!2026"
D = Decimal


@pytest.fixture
def company_with_period():
    company = CompanyFactory(slug="api-reports", report_emails=["boss@demo.test"])
    PayrollPolicyFactory(company=company)
    branch = BranchFactory(company=company)
    EmployeeFactory(company=company, branch=branch, base_salary=D("6000"))
    period = PeriodFactory(company=company)
    run_period(period)
    return company, period


@pytest.fixture
def admin_client(api, company_with_period):
    company, _period = company_with_period
    user = UserFactory(password=PASSWORD)
    MembershipFactory(user=user, company=company, role=Role.COMPANY_ADMIN)
    api.post(
        reverse("core:accounts:login"),
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    api.credentials(HTTP_X_COMPANY_ID=str(company.pk))
    return api


@pytest.fixture
def entry_client(api, company_with_period):
    company, _period = company_with_period
    branch = company.branchs.first()
    user = UserFactory(password=PASSWORD)
    membership = MembershipFactory(user=user, company=company, role=Role.BRANCH_ENTRY)
    membership.branches.set([branch])
    api.post(
        reverse("core:accounts:login"),
        {"email": user.email, "password": PASSWORD},
        format="json",
    )
    api.credentials(HTTP_X_COMPANY_ID=str(company.pk))
    return api


def test_admin_can_generate_the_workbook(admin_client, company_with_period):
    _company, period = company_with_period

    response = admin_client.post(reverse("core:report-xlsx", args=[period.pk]))

    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "xlsx"
    assert body["size"] > 0
    assert body["file_url"].endswith(".xlsx")


def test_admin_can_generate_payslips(admin_client, company_with_period):
    _company, period = company_with_period

    response = admin_client.post(reverse("core:report-payslips", args=[period.pk]))

    assert response.status_code == 201
    assert response.json()["kind"] == "pdf"


def test_branch_entry_user_cannot_generate_reports(entry_client, company_with_period):
    _company, period = company_with_period

    response = entry_client.post(reverse("core:report-xlsx", args=[period.pk]))

    assert response.status_code == 403


def test_emailing_sends_to_the_configured_recipients(admin_client, company_with_period):
    _company, period = company_with_period
    mail.outbox.clear()

    response = admin_client.post(reverse("core:report-email", args=[period.pk]))

    assert response.status_code == 200
    assert response.json()["recipients"] == ["boss@demo.test"]
    assert len(mail.outbox) == 1


def test_emailing_without_recipients_is_refused(admin_client, company_with_period):
    company, period = company_with_period
    company.report_emails = []
    company.save()

    response = admin_client.post(reverse("core:report-email", args=[period.pk]))

    assert response.status_code == 400


def test_generating_for_an_uncalculated_period_is_refused(admin_client, company_with_period):
    company, _period = company_with_period
    empty = PeriodFactory(company=company, year=2025, month=1)

    response = admin_client.post(reverse("core:report-xlsx", args=[empty.pk]))

    assert response.status_code == 400


def test_generating_for_another_companys_period_is_404(admin_client):
    other = CompanyFactory(slug="other-reports")
    PayrollPolicyFactory(company=other)
    foreign = PeriodFactory(company=other)

    response = admin_client.post(reverse("core:report-xlsx", args=[foreign.pk]))

    assert response.status_code == 404


def test_download_streams_the_file(admin_client, company_with_period):
    _company, period = company_with_period
    created = admin_client.post(reverse("core:report-xlsx", args=[period.pk])).json()

    response = admin_client.get(reverse("core:report-download", args=[created["id"]]))

    assert response.status_code == 200
    assert "attachment" in response["Content-Disposition"]
