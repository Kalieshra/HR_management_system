"""Parity with `docs/reference/accounting_monthly.xlsx`.

The most important test in the project: every calculated column of every
employee row in the workbook must be reproduced by the engine to within 0.01,
and so must the four headline totals. If this fails, the product is wrong — the
workbook is the specification, not the code.
"""

from decimal import Decimal

import pytest
from django.conf import settings

from payroll.services.engine import LineInputs, PolicyValues, calculate_line
from payroll.services.workbook import CALCULATED_FIELDS, load_reference

TOLERANCE = Decimal("0.01")

# Headline totals of sheet `تقرير الرواتب`, February 2026.
EXPECTED_TOTALS = {
    "base_salary": Decimal("162500.00"),  # F
    "total_earnings": Decimal("156959.26"),  # O
    "total_deductions": Decimal("42220.37"),  # AF
    "net_salary": Decimal("114738.89"),  # AG
}

EXPECTED_EMPLOYEE_COUNT = 23


@pytest.fixture(scope="module")
def workbook():
    path = settings.REFERENCE_WORKBOOK
    if not path.exists():
        pytest.fail(f"Reference workbook missing at {path}")
    return load_reference(path)


def _calculate(row):
    return calculate_line(LineInputs(**row.inputs), PolicyValues())


@pytest.mark.workbook
def test_workbook_has_the_expected_shape(workbook):
    assert len(workbook.rows) == EXPECTED_EMPLOYEE_COUNT
    assert "فبراير 2026" in workbook.title


@pytest.mark.workbook
def test_every_calculated_column_matches_the_workbook(workbook):
    """Feed each row's inputs through the engine and compare all 12 outputs."""
    failures = []

    for row in workbook.rows:
        result = _calculate(row)
        for column in CALCULATED_FIELDS:
            actual = getattr(result, column)
            expected = row.expected[column]
            if abs(actual - expected) > TOLERANCE:
                failures.append(
                    f"row {row.row_number} ({row.code} {row.name}) {column}: "
                    f"engine={actual} workbook={expected}"
                )

    assert not failures, "\n".join(failures)


@pytest.mark.workbook
def test_totals_match_the_workbook(workbook):
    """Sum the engine's output across all rows and compare with the totals row."""
    totals = {column: Decimal("0") for column in CALCULATED_FIELDS}
    base_salary_total = Decimal("0")

    for row in workbook.rows:
        result = _calculate(row)
        base_salary_total += row.inputs["base_salary"]
        for column in CALCULATED_FIELDS:
            totals[column] += getattr(result, column)

    assert abs(base_salary_total - EXPECTED_TOTALS["base_salary"]) <= TOLERANCE
    for column in ("total_earnings", "total_deductions", "net_salary"):
        assert (
            abs(totals[column] - EXPECTED_TOTALS[column]) <= TOLERANCE
        ), f"{column}: engine={totals[column]} expected={EXPECTED_TOTALS[column]}"


@pytest.mark.workbook
def test_engine_totals_match_the_workbooks_own_totals_row(workbook):
    """Cross-check against every numeric total cached in row 201, not just the four."""
    failures = []

    for column in CALCULATED_FIELDS:
        engine_total = sum(
            (getattr(_calculate(row), column) for row in workbook.rows), Decimal("0")
        )
        workbook_total = workbook.totals.get(column, Decimal("0"))
        if abs(engine_total - workbook_total) > TOLERANCE:
            failures.append(f"{column}: engine={engine_total} workbook={workbook_total}")

    assert not failures, "\n".join(failures)


@pytest.mark.workbook
@pytest.mark.parametrize(
    ("code", "expected"),
    [
        # Employee 1 — overtime and an advance.
        (
            "1",
            {
                "work_days_value": Decimal("6766.67"),
                "overtime_value": Decimal("311.11"),
                "total_earnings": Decimal("7077.78"),
                "total_deductions": Decimal("1600.00"),
                "net_salary": Decimal("5477.78"),
            },
        ),
        # Employee 6 — lateness, admin penalty, shortage.
        (
            "6",
            {
                "total_earnings": Decimal("6331.48"),
                "total_deductions": Decimal("4481.48"),
                "net_salary": Decimal("1850.00"),
            },
        ),
        # Employee 8 — unexcused absence.
        (
            "8",
            {
                "unexcused_absence_value": Decimal("600.00"),
                "total_deductions": Decimal("1785.56"),
                "net_salary": Decimal("3414.44"),
            },
        ),
    ],
)
def test_spot_checks(workbook, code, expected):
    result = _calculate(workbook.by_code(code))
    for column, value in expected.items():
        assert (
            abs(getattr(result, column) - value) <= TOLERANCE
        ), f"employee {code} {column}: engine={getattr(result, column)} expected={value}"
