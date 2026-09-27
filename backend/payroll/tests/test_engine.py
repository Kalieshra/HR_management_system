"""Unit tests for the engine.

The February 2026 workbook fixture leaves four calculated columns at zero —
L (leave allowance), W (fingerprint penalty), AA (sick) and AC (insurance, since
every AB is empty) — so workbook parity alone cannot prove those formulas. These
tests exercise them directly, along with the policy knobs and the divide-by-zero
guards.
"""

from decimal import Decimal

import pytest

from payroll.services.engine import (
    FINGERPRINT_BASE_BASE,
    LineInputs,
    PolicyValues,
    calculate_line,
    quantize_display,
)

D = Decimal


def test_leave_allowance_is_days_times_daily_rate():
    """L = K*F/30 — untested by the workbook fixture (every K is zero)."""
    result = calculate_line(LineInputs(base_salary=D("6000"), leave_allowance_days=D("3")))

    assert result.leave_allowance_value == D("600.000000")  # 6000/30*3
    assert result.total_earnings == D("600.000000")


def test_sick_days_deduct_a_quarter_of_a_day():
    """AA = (F/30*Z)*0.25 — untested by the fixture (every Z is zero)."""
    result = calculate_line(LineInputs(base_salary=D("6000"), sick_days=D("4")))

    assert result.sick_value == D("200.000000")  # 6000/30*4*0.25
    assert result.total_deductions == D("200.000000")


def test_insurance_is_eleven_percent_of_the_insurable_salary():
    """AC = AB*11% — untested by the fixture (every AB is empty)."""
    result = calculate_line(LineInputs(base_salary=D("9000"), insurable_salary=D("5000")))

    assert result.insurance_and_tax == D("550.000000")
    assert result.total_deductions == D("550.000000")


def test_fingerprint_penalty_uses_earned_days_not_base_salary():
    """W = H/30*V. The workbook divides the *earned* value, which is the quirk."""
    inputs = LineInputs(
        base_salary=D("6000"),
        work_days=D("30"),
        fingerprint_penalty_days=D("2"),
    )
    result = calculate_line(inputs)

    # H = 6000/30*30 = 6000; W = 6000/30*2 = 400
    assert result.work_days_value == D("6000.000000")
    assert result.fingerprint_penalty_value == D("400.000000")


def test_fingerprint_penalty_differs_from_base_when_days_are_partial():
    """With 15 worked days, H is half of F, so the two policies disagree."""
    inputs = LineInputs(
        base_salary=D("6000"),
        work_days=D("15"),
        fingerprint_penalty_days=D("2"),
    )

    earned = calculate_line(inputs)  # default policy
    on_base = calculate_line(inputs, PolicyValues(fingerprint_penalty_base=FINGERPRINT_BASE_BASE))

    assert earned.fingerprint_penalty_value == D("200.000000")  # 3000/30*2
    assert on_base.fingerprint_penalty_value == D("400.000000")  # 6000/30*2


def test_overtime_pays_one_times_the_hourly_rate_by_default():
    """J = I*F/30/E — the workbook applies no statutory premium."""
    result = calculate_line(
        LineInputs(base_salary=D("9000"), daily_hours=D("9"), overtime_hours=D("10"))
    )

    # 9000/30/9 = 33.333333 per hour; x10
    assert quantize_display(result.overtime_value) == D("333.33")


def test_overtime_multiplier_is_a_policy_knob():
    inputs = LineInputs(base_salary=D("9000"), daily_hours=D("9"), overtime_hours=D("10"))
    result = calculate_line(inputs, PolicyValues(overtime_multiplier=D("1.5")))

    assert quantize_display(result.overtime_value) == D("500.00")


def test_absence_multiplier_is_a_policy_knob():
    inputs = LineInputs(base_salary=D("6000"), unexcused_absence_days=D("2"))

    assert calculate_line(inputs).unexcused_absence_value == D("400.000000")
    assert calculate_line(
        inputs, PolicyValues(absence_multiplier=D("2"))
    ).unexcused_absence_value == D("800.000000")


def test_month_basis_is_thirty_days_regardless_of_the_calendar():
    """A full February (28 days worked) still earns 28/30 of the salary."""
    result = calculate_line(LineInputs(base_salary=D("3000"), work_days=D("28")))

    assert result.work_days_value == D("2800.000000")


def test_zero_daily_hours_is_flagged_not_raised():
    """Guard: E=0 would divide by zero for J and Q."""
    result = calculate_line(
        LineInputs(
            base_salary=D("6000"),
            daily_hours=D("0"),
            overtime_hours=D("10"),
            late_hours=D("5"),
            work_days=D("30"),
        )
    )

    assert result.overtime_value == D("0")
    assert result.late_value == D("0")
    assert "daily_hours_is_zero" in result.warnings
    # Day-based columns are unaffected.
    assert result.work_days_value == D("6000.000000")


def test_zero_month_basis_is_flagged_not_raised():
    result = calculate_line(
        LineInputs(base_salary=D("6000"), work_days=D("30")),
        PolicyValues(month_day_basis=D("0")),
    )

    assert result.work_days_value == D("0")
    assert "month_day_basis_is_zero" in result.warnings


def test_net_is_earnings_minus_deductions_and_can_go_negative():
    """An employee who owes more than they earned nets a negative figure."""
    result = calculate_line(
        LineInputs(base_salary=D("3000"), work_days=D("10"), advances=D("2000"))
    )

    assert result.total_earnings == D("1000.000000")
    assert result.total_deductions == D("2000.000000")
    assert result.net_salary == D("-1000.000000")


def test_all_deduction_components_are_summed_into_af():
    """AF = AE+AD+Y+U+R+Q+AA+S+W+AC — every term must appear exactly once."""
    result = calculate_line(
        LineInputs(
            base_salary=D("6000"),
            daily_hours=D("10"),
            work_days=D("30"),
            late_hours=D("1"),  # Q = 6000/30/10 = 20
            advances=D("100"),  # R
            carried_advance=D("50"),  # S
            admin_penalty_days=D("1"),  # U = 200
            fingerprint_penalty_days=D("1"),  # W = 6000/30 = 200
            unexcused_absence_days=D("1"),  # Y = 200
            sick_days=D("4"),  # AA = 200
            insurable_salary=D("1000"),  # AC = 110
            deviations=D("25"),  # AD
            shortage_custody=D("75"),  # AE
        )
    )

    expected = D("20") + D("100") + D("50") + D("200") + D("200") + D("200") + D("200")
    expected += D("110") + D("25") + D("75")
    assert result.total_deductions == expected.quantize(D("0.000001"))


def test_none_inputs_are_treated_as_zero():
    result = calculate_line(LineInputs(base_salary=D("6000"), work_days=None, bonus=None))

    assert result.work_days_value == D("0")
    assert result.total_earnings == D("0")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(D("1.005"), D("1.01")), (D("2.344"), D("2.34")), (D("2.345"), D("2.35"))],
)
def test_display_rounding_is_half_up(raw, expected):
    assert quantize_display(raw) == expected
