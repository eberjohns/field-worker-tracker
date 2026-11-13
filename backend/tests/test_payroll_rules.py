"""Unit tests for pure payroll business rules and formulas.

Verifies:
- Documented example: Basic 1100 -> OT1 rate 6.61, OT2 rate 7.93
- Gratuity (basic / 365 * 30) and leave salary (basic / 12)
- Five provisions + gratuity + leave salary = per-month provision
- Total staff cost and 5% HR OH -> final total staff cost
- Missed hours deduction
- Salary revision planned hourly cost formula for job budgeting
"""

from decimal import Decimal

from fw.rules.payroll import (
    calculate_final_total_staff_cost,
    calculate_gratuity,
    calculate_gross_pay,
    calculate_hourly_ot_rate,
    calculate_hr_overhead,
    calculate_leave_salary,
    calculate_missed_hours_deduction,
    calculate_per_month_provision,
    calculate_provisions,
    calculate_revision_planned_hourly_cost,
    calculate_salary_portion,
    calculate_total_staff_cost,
)


def test_documented_overtime_rate_example():
    """Verify checklist requirement:

    The documented example reproduces: OT1 rate (1100/208)*1.25 = 6.61, OT2 = 7.93
    """
    basic = Decimal("1100")
    ot1_rate = calculate_hourly_ot_rate(basic, multiplier=Decimal("1.25"), divisor=Decimal("208"))
    ot2_rate = calculate_hourly_ot_rate(basic, multiplier=Decimal("1.50"), divisor=Decimal("208"))

    assert ot1_rate == Decimal("6.61")
    assert ot2_rate == Decimal("7.93")


def test_gratuity_and_leave_salary_formulas():
    """Verify checklist requirement:

    Gratuity and leave salary use the formula for everyone.
    gratuity = basic / 365 * 30
    leave_salary = basic / 12
    """
    basic = Decimal("1200")
    # Gratuity: 1200 / 365 * 30 = 98.6301... -> 98.63
    gratuity = calculate_gratuity(basic)
    assert gratuity == Decimal("98.63")

    # Leave salary: 1200 / 12 = 100.00
    leave_sal = calculate_leave_salary(basic)
    assert leave_sal == Decimal("100.00")


def test_provisions_and_final_total_staff_cost():
    """Verify checklist requirement:

    Per-month provision = five provisions + gratuity + leave salary;
    HR OH 5% added to total staff cost for the final figure.
    """
    # 5 company provisions
    provisions = calculate_provisions(
        visa=Decimal("100.00"),
        air_ticket=Decimal("75.00"),
        uniform=Decimal("25.00"),
        accommodation=Decimal("300.00"),
        medical=Decimal("50.00"),
    )
    assert provisions == Decimal("550.00")

    basic = Decimal("1200")
    gratuity = calculate_gratuity(basic)  # 98.63
    leave_sal = calculate_leave_salary(basic)  # 100.00

    per_month_prov = calculate_per_month_provision(provisions, gratuity, leave_sal)
    # 550.00 + 98.63 + 100.00 = 748.63
    assert per_month_prov == Decimal("748.63")

    salary_portion = calculate_salary_portion(
        basic=basic,
        special_allowance=Decimal("200.00"),
        fixed_ot=Decimal("100.00"),
    )
    # 1200 + 200 + 100 = 1500.00
    assert salary_portion == Decimal("1500.00")

    ot1_amount = Decimal("66.10")  # 10 hrs * 6.61
    ot2_amount = Decimal("39.65")  # 5 hrs * 7.93
    missed_hours_deduction = Decimal("0.00")

    gross_pay = calculate_gross_pay(
        salary_portion=salary_portion,
        ot1_amount=ot1_amount,
        ot2_amount=ot2_amount,
        missed_hours_deduction=missed_hours_deduction,
    )
    # 1500.00 + 66.10 + 39.65 = 1605.75
    assert gross_pay == Decimal("1605.75")

    total_staff_cost = calculate_total_staff_cost(gross_pay, per_month_prov)
    # 1605.75 + 748.63 = 2354.38
    assert total_staff_cost == Decimal("2354.38")

    hr_oh = calculate_hr_overhead(total_staff_cost)
    # 2354.38 * 0.05 = 117.719 -> 117.72
    assert hr_oh == Decimal("117.72")

    final_cost = calculate_final_total_staff_cost(total_staff_cost, hr_oh)
    # 2354.38 + 117.72 = 2472.10
    assert final_cost == Decimal("2472.10")


def test_missed_hours_deduction():
    """Verify deduction for missed unpaid hours."""
    basic = Decimal("1040")
    # Hourly rate: 1040 / 208 = 5.00
    deduction = calculate_missed_hours_deduction(basic, missed_hours=Decimal("16.0"))
    assert deduction == Decimal("80.00")

    # Gross pay reflects deduction
    salary_portion = Decimal("1200.00")
    gross = calculate_gross_pay(
        salary_portion=salary_portion,
        missed_hours_deduction=deduction,
    )
    assert gross == Decimal("1120.00")


def test_revision_planned_hourly_cost_for_job_budget():
    """Verify job budget planned hourly cost formula from revision line."""
    # (salary_portion + line_provisions) * 1.05 / 208
    rev_salary_portion = Decimal("1500.00")
    rev_provisions = Decimal("500.00")
    # Base = 2000.00. With 5% HR OH = 2100.00.
    # 2100 / 208 = 10.09615... -> 10.10
    hourly_cost = calculate_revision_planned_hourly_cost(
        revision_salary_portion=rev_salary_portion,
        revision_provisions_sum=rev_provisions,
    )
    assert hourly_cost == Decimal("10.10")
