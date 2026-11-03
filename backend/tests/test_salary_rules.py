"""Unit tests for employee salary business rules."""

from datetime import date
from decimal import Decimal

from fw.rules.payroll.salary import (
    calculate_salary_difference,
    calculate_salary_portion,
    compute_next_payroll_month_start,
    round_money,
)


def test_calculate_salary_portion():
    basic = Decimal("1500.00")
    special = Decimal("250.50")
    fixed_ot = Decimal("300.00")
    bonus = Decimal("100.00")
    telephone = Decimal("50.00")
    housing = Decimal("400.00")

    portion = calculate_salary_portion(
        basic=basic,
        special_allowance=special,
        fixed_ot=fixed_ot,
        bonus=bonus,
        telephone_allowance=telephone,
        housing_transport_allowance=housing,
    )
    assert portion == Decimal("2600.50")


def test_round_money_half_up():
    assert round_money("123.454") == Decimal("123.45")
    assert round_money("123.455") == Decimal("123.46")
    assert round_money("123.456") == Decimal("123.46")


def test_compute_next_payroll_month_start():
    assert compute_next_payroll_month_start(date(2026, 11, 3)) == date(2026, 12, 1)
    assert compute_next_payroll_month_start(date(2026, 11, 30)) == date(2026, 12, 1)
    assert compute_next_payroll_month_start(date(2026, 12, 15)) == date(2027, 1, 1)


def test_calculate_salary_difference():
    prev = Decimal("2500.00")
    curr = Decimal("2800.00")
    assert calculate_salary_difference(curr, prev) == Decimal("300.00")

    # Initial salary (no previous)
    assert calculate_salary_difference(curr, None) == Decimal("0.00")

    # Salary reduction
    curr_lower = Decimal("2300.00")
    assert calculate_salary_difference(curr_lower, prev) == Decimal("-200.00")
