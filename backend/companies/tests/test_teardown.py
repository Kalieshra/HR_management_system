"""Deleting a tenant, and why the API refuses to."""

from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from attendance.models import DailyRecord
from companies.models import Branch, Company, PayrollPolicy
from companies.services import delete_company_data
from core.factories import (
    BranchFactory,
    CompanyFactory,
    EmployeeFactory,
    PayrollPolicyFactory,
    PeriodFactory,
    UserFactory,
)
from employees.models import Employee
from payroll.models import PayrollLine, Period
from payroll.services.runner import run_period
from reports.services.generator import generate_excel

pytestmark = pytest.mark.django_db

PASSWORD = "TestPass!2026"
D = Decimal


@pytest.fixture
def populated_company():
    """A company with a row in every table that points back at it."""
    company = CompanyFactory(slug="teardown-co")
    PayrollPolicyFactory(company=company)
    branch = BranchFactory(company=company)
    employee = EmployeeFactory(company=company, branch=branch, base_salary=D("6000"))
    DailyRecord.all_objects.create(company=company, employee=employee, date=date(2026, 2, 3))

    period = PeriodFactory(company=company)
    run_period(period)
    generate_excel(period)
    return company


def test_a_plain_delete_is_blocked_by_the_protected_keys(populated_company):
    """Documents *why* teardown needs an explicit order."""
    from django.db.models import ProtectedError

    with pytest.raises(ProtectedError):
        Company.objects.filter(pk=populated_company.pk).delete()


def test_delete_company_data_removes_everything(populated_company):
    company_id = populated_company.pk

    delete_company_data(populated_company)

    assert not Company.objects.filter(pk=company_id).exists()
    for model in (Branch, Employee, Period, PayrollLine, PayrollPolicy, DailyRecord):
        assert not model.all_objects.filter(company_id=company_id).exists(), model.__name__


def test_deleting_one_tenant_leaves_the_others_alone(populated_company):
    other = CompanyFactory(slug="survivor")
    PayrollPolicyFactory(company=other)
    survivor = EmployeeFactory(company=other, branch=BranchFactory(company=other))

    delete_company_data(populated_company)

    assert Company.objects.filter(pk=other.pk).exists()
    assert Employee.all_objects.filter(pk=survivor.pk).exists()


def test_the_platform_api_does_not_expose_delete(api, populated_company):
    """Tenants are suspended, never destroyed — payroll history must survive."""
    owner = UserFactory(password=PASSWORD, is_platform_admin=True)
    api.post(
        reverse("core:accounts:login"),
        {"email": owner.email, "password": PASSWORD},
        format="json",
    )

    response = api.delete(reverse("core:platform-company-detail", args=[populated_company.pk]))

    assert response.status_code == 405
    assert Company.objects.filter(pk=populated_company.pk).exists()


def test_suspend_is_the_supported_way_to_switch_a_tenant_off(api, populated_company):
    owner = UserFactory(password=PASSWORD, is_platform_admin=True)
    api.post(
        reverse("core:accounts:login"),
        {"email": owner.email, "password": PASSWORD},
        format="json",
    )

    response = api.post(reverse("core:platform-company-suspend", args=[populated_company.pk]))

    assert response.status_code == 200
    populated_company.refresh_from_db()
    assert populated_company.is_active is False
