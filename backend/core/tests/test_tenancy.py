"""The tenant guard: a query that forgets its company must fail loudly."""

import pytest

from companies.models import Branch
from core.factories import BranchFactory, CompanyFactory, EmployeeFactory
from core.models import UnscopedTenantQueryError
from employees.models import Employee

pytestmark = pytest.mark.django_db


@pytest.fixture
def two_companies():
    alpha = CompanyFactory()
    beta = CompanyFactory()
    EmployeeFactory.create_batch(3, company=alpha)
    EmployeeFactory.create_batch(2, company=beta)
    return alpha, beta


def test_unscoped_iteration_raises(two_companies):
    with pytest.raises(UnscopedTenantQueryError):
        list(Employee.objects.all())


def test_unscoped_count_raises(two_companies):
    with pytest.raises(UnscopedTenantQueryError):
        Employee.objects.count()


def test_unscoped_exists_raises(two_companies):
    with pytest.raises(UnscopedTenantQueryError):
        Employee.objects.filter(is_active=True).exists()


def test_unscoped_update_raises(two_companies):
    with pytest.raises(UnscopedTenantQueryError):
        Employee.objects.update(is_active=False)


def test_unscoped_delete_raises(two_companies):
    with pytest.raises(UnscopedTenantQueryError):
        Employee.objects.all().delete()


def test_for_company_returns_only_that_companys_rows(two_companies):
    alpha, beta = two_companies

    assert Employee.objects.for_company(alpha).count() == 3
    assert Employee.objects.for_company(beta).count() == 2


def test_scoping_survives_further_filtering(two_companies):
    """Chaining must not lose the scope flag."""
    alpha, _ = two_companies

    queryset = Employee.objects.for_company(alpha).filter(is_active=True).order_by("code")

    assert queryset.count() == 3


def test_one_companys_row_is_invisible_to_another(two_companies):
    alpha, beta = two_companies
    target = Employee.objects.for_company(beta).first()

    assert not Employee.objects.for_company(alpha).filter(pk=target.pk).exists()


def test_unscoped_escape_hatch_is_explicit(two_companies):
    assert Employee.objects.unscoped().count() == 5
    assert Employee.all_objects.count() == 5


def test_related_traversal_still_works(two_companies):
    """Django's own descriptors use the unscoped manager, so they must not raise."""
    alpha, _ = two_companies
    branch = Branch.objects.for_company(alpha).first()

    assert branch.employees.count() >= 0


def test_every_tenant_model_enforces_the_guard():
    """A new tenant-owned model must not be able to opt out by accident."""
    from attendance.models import DailyRecord
    from payroll.models import Loan, MonthlyAdjustment, PayrollLine, Period
    from reports.models import ReportFile

    models = [
        Branch,
        DailyRecord,
        Employee,
        Loan,
        MonthlyAdjustment,
        PayrollLine,
        Period,
        ReportFile,
    ]
    for model in models:
        with pytest.raises(UnscopedTenantQueryError):
            model.objects.count()


def test_branch_factory_keeps_employee_and_branch_in_one_company():
    company = CompanyFactory()
    branch = BranchFactory(company=company)
    employee = EmployeeFactory(company=company, branch=branch)

    assert employee.company_id == branch.company_id == company.pk
