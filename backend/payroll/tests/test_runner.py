"""Period lifecycle: aggregation, overrides, closing, reopening, loans."""

from datetime import date
from decimal import Decimal

import pytest

from attendance.models import AttendanceStatus
from core.factories import (
    CompanyFactory,
    DailyRecordFactory,
    EmployeeFactory,
    MonthlyAdjustmentFactory,
    PayrollPolicyFactory,
    PeriodFactory,
    UserFactory,
)
from payroll.models import AdjustmentKind, Loan, PayrollLine, PeriodStatus
from payroll.services.runner import (
    PeriodClosedError,
    close_period,
    reopen_period,
    run_period,
)

pytestmark = pytest.mark.django_db

D = Decimal


@pytest.fixture
def company():
    company = CompanyFactory()
    PayrollPolicyFactory(company=company)
    return company


@pytest.fixture
def period(company):
    return PeriodFactory(company=company)


def _present_days(company, employee, count, **kwargs):
    for day in range(1, count + 1):
        DailyRecordFactory(
            company=company,
            employee=employee,
            date=date(2026, 2, day),
            status=AttendanceStatus.PRESENT,
            **kwargs,
        )


def test_run_period_aggregates_daily_records(company, period):
    employee = EmployeeFactory(company=company, base_salary=D("6000"))
    _present_days(company, employee, 20)

    run_period(period)

    line = PayrollLine.objects.for_company(company).get(employee=employee)
    assert line.work_days == D("20.00")
    assert line.work_days_value == D("4000.000000")  # 6000/30*20


def test_work_days_are_capped_at_the_month_basis(company, period):
    """A 31-day month must not pay 31/30 of the salary."""
    employee = EmployeeFactory(company=company, base_salary=D("3000"))
    for day in range(1, 29):
        DailyRecordFactory(company=company, employee=employee, date=date(2026, 2, day))

    run_period(period)

    line = PayrollLine.objects.for_company(company).get(employee=employee)
    assert line.work_days == D("28.00")
    assert line.work_days <= 30


def test_paid_leave_counts_as_a_work_day_but_sick_does_not(company, period):
    employee = EmployeeFactory(company=company)
    DailyRecordFactory(
        company=company,
        employee=employee,
        date=date(2026, 2, 1),
        status=AttendanceStatus.PAID_LEAVE,
    )
    DailyRecordFactory(
        company=company,
        employee=employee,
        date=date(2026, 2, 2),
        status=AttendanceStatus.SICK,
    )
    DailyRecordFactory(
        company=company,
        employee=employee,
        date=date(2026, 2, 3),
        status=AttendanceStatus.UNEXCUSED_ABSENCE,
    )

    run_period(period)

    line = PayrollLine.objects.for_company(company).get(employee=employee)
    assert line.work_days == D("1.00")
    assert line.sick_days == D("1.00")
    assert line.unexcused_absence_days == D("1.00")


def test_adjustments_of_the_same_kind_are_summed(company, period):
    employee = EmployeeFactory(company=company)
    MonthlyAdjustmentFactory(
        company=company,
        period=period,
        employee=employee,
        kind=AdjustmentKind.BONUS,
        amount=D("300"),
    )
    MonthlyAdjustmentFactory(
        company=company,
        period=period,
        employee=employee,
        kind=AdjustmentKind.BONUS,
        amount=D("200"),
    )

    run_period(period)

    line = PayrollLine.objects.for_company(company).get(employee=employee)
    assert line.bonus == D("500.00")


def test_overrides_survive_recalculation(company, period):
    """A manual figure must not be blown away by the next aggregation."""
    employee = EmployeeFactory(company=company, base_salary=D("6000"))
    _present_days(company, employee, 10)
    run_period(period)

    line = PayrollLine.objects.for_company(company).get(employee=employee)
    line.work_days = D("30")
    line.overrides = {"work_days": "10.00"}
    line.save()

    run_period(period)

    line.refresh_from_db()
    assert line.work_days == D("30.00"), "override was overwritten by the aggregate"
    assert line.work_days_value == D("6000.000000")
    assert line.overrides["work_days"] == "10.00", "original aggregate must be recorded"


def test_running_a_period_sets_status_calculated(company, period):
    EmployeeFactory(company=company)

    run_period(period)

    period.refresh_from_db()
    assert period.status == PeriodStatus.CALCULATED
    assert period.calculated_at is not None


def test_closed_period_rejects_recalculation(company, period):
    EmployeeFactory(company=company)
    run_period(period)
    close_period(period)

    with pytest.raises(PeriodClosedError):
        run_period(period)


def test_close_then_reopen_restores_calculated_status(company, period):
    user = UserFactory()
    EmployeeFactory(company=company)
    run_period(period)

    close_period(period, user=user)
    assert period.status == PeriodStatus.CLOSED
    assert period.closed_by == user

    reopen_period(period, user=user)
    assert period.status == PeriodStatus.CALCULATED
    assert period.closed_at is None


def test_reopening_an_open_period_is_an_error(company, period):
    EmployeeFactory(company=company)
    run_period(period)

    with pytest.raises(PeriodClosedError):
        reopen_period(period)


def test_loan_creates_an_advance_and_draws_down_on_close(company, period):
    employee = EmployeeFactory(company=company, base_salary=D("6000"))
    _present_days(company, employee, 28)
    loan = Loan.all_objects.create(
        company=company,
        employee=employee,
        total=D("3000"),
        monthly_installment=D("500"),
        remaining=D("3000"),
        start_year=2026,
        start_month=1,
    )

    run_period(period)

    line = PayrollLine.objects.for_company(company).get(employee=employee)
    assert line.advances == D("500.00")

    close_period(period)
    loan.refresh_from_db()
    assert loan.remaining == D("2500.00")
    assert loan.is_active is True


def test_loan_never_charges_more_than_the_balance(company, period):
    employee = EmployeeFactory(company=company)
    loan = Loan.all_objects.create(
        company=company,
        employee=employee,
        total=D("1000"),
        monthly_installment=D("500"),
        remaining=D("200"),
        start_year=2026,
        start_month=1,
    )

    run_period(period)

    line = PayrollLine.objects.for_company(company).get(employee=employee)
    assert line.advances == D("200.00")

    close_period(period)
    loan.refresh_from_db()
    assert loan.remaining == D("0.00")
    assert loan.is_active is False


def test_loan_that_starts_later_is_not_charged_yet(company, period):
    employee = EmployeeFactory(company=company)
    Loan.all_objects.create(
        company=company,
        employee=employee,
        total=D("1000"),
        monthly_installment=D("500"),
        remaining=D("1000"),
        start_year=2026,
        start_month=6,
    )

    run_period(period)

    line = PayrollLine.objects.for_company(company).get(employee=employee)
    assert line.advances == D("0.00")


def test_recalculation_is_idempotent(company, period):
    employee = EmployeeFactory(company=company, base_salary=D("6000"))
    _present_days(company, employee, 15)

    run_period(period)
    first = PayrollLine.objects.for_company(company).get(employee=employee).net_salary

    period.status = PeriodStatus.OPEN
    period.save()
    run_period(period)
    second = PayrollLine.objects.for_company(company).get(employee=employee).net_salary

    assert first == second
    assert PayrollLine.objects.for_company(company).count() == 1


def test_lines_are_scoped_to_their_company(company, period):
    other = CompanyFactory()
    PayrollPolicyFactory(company=other)
    other_period = PeriodFactory(company=other)
    EmployeeFactory(company=company)
    EmployeeFactory(company=other)

    run_period(period)
    run_period(other_period)

    assert PayrollLine.objects.for_company(company).count() == 1
    assert PayrollLine.objects.for_company(other).count() == 1
    mine = PayrollLine.objects.for_company(company).first()
    assert not PayrollLine.objects.for_company(other).filter(pk=mine.pk).exists()


def test_snapshots_freeze_employee_details(company, period):
    """Renaming an employee must not change a line that was already calculated."""
    employee = EmployeeFactory(company=company, name_ar="الاسم الأول")
    run_period(period)

    employee.name_ar = "اسم جديد"
    employee.save()

    line = PayrollLine.objects.for_company(company).get(employee=employee)
    assert line.employee_name == "الاسم الأول"
