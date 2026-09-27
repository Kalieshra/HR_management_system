"""factory_boy factories shared by the test suite."""

from datetime import date
from decimal import Decimal

import factory
from factory.django import DjangoModelFactory

from accounts.models import Membership, Role, User
from attendance.models import AttendanceStatus, DailyRecord
from companies.models import Branch, Company, PayrollPolicy
from employees.models import Employee
from payroll.models import MonthlyAdjustment, PayrollLine, Period


class CompanyFactory(DjangoModelFactory):
    class Meta:
        model = Company

    name_ar = factory.Sequence(lambda n: f"شركة {n}")
    name_en = factory.Sequence(lambda n: f"Company {n}")
    slug = factory.Sequence(lambda n: f"company-{n}")


class BranchFactory(DjangoModelFactory):
    class Meta:
        model = Branch

    company = factory.SubFactory(CompanyFactory)
    name_ar = factory.Sequence(lambda n: f"فرع {n}")
    code = factory.Sequence(lambda n: f"B{n:02d}")


class PayrollPolicyFactory(DjangoModelFactory):
    class Meta:
        model = PayrollPolicy

    company = factory.SubFactory(CompanyFactory)
    effective_from = date(2020, 1, 1)


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.test")
    full_name = factory.Sequence(lambda n: f"User {n}")

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        obj.set_password(extracted or "TestPass!2026")
        if create:
            obj.save()


class MembershipFactory(DjangoModelFactory):
    class Meta:
        model = Membership

    user = factory.SubFactory(UserFactory)
    company = factory.SubFactory(CompanyFactory)
    role = Role.COMPANY_ADMIN


class EmployeeFactory(DjangoModelFactory):
    class Meta:
        model = Employee

    company = factory.SubFactory(CompanyFactory)
    branch = factory.SubFactory(BranchFactory, company=factory.SelfAttribute("..company"))
    code = factory.Sequence(lambda n: f"E{n:04d}")
    name_ar = factory.Sequence(lambda n: f"موظف {n}")
    job_title = "عضو فريق"
    daily_hours = Decimal("9")
    base_salary = Decimal("6000")
    insurable_salary = Decimal("0")
    hire_date = date(2024, 1, 1)


class PeriodFactory(DjangoModelFactory):
    class Meta:
        model = Period

    company = factory.SubFactory(CompanyFactory)
    year = 2026
    month = 2


class DailyRecordFactory(DjangoModelFactory):
    class Meta:
        model = DailyRecord

    company = factory.SubFactory(CompanyFactory)
    employee = factory.SubFactory(EmployeeFactory, company=factory.SelfAttribute("..company"))
    date = date(2026, 2, 2)
    status = AttendanceStatus.PRESENT


class MonthlyAdjustmentFactory(DjangoModelFactory):
    class Meta:
        model = MonthlyAdjustment

    company = factory.SubFactory(CompanyFactory)
    period = factory.SubFactory(PeriodFactory, company=factory.SelfAttribute("..company"))
    employee = factory.SubFactory(EmployeeFactory, company=factory.SelfAttribute("..company"))
    amount = Decimal("100")


class PayrollLineFactory(DjangoModelFactory):
    class Meta:
        model = PayrollLine

    company = factory.SubFactory(CompanyFactory)
    period = factory.SubFactory(PeriodFactory, company=factory.SelfAttribute("..company"))
    employee = factory.SubFactory(EmployeeFactory, company=factory.SelfAttribute("..company"))
    employee_code = factory.SelfAttribute("employee.code")
    employee_name = factory.SelfAttribute("employee.name_ar")
    base_salary = Decimal("6000")
