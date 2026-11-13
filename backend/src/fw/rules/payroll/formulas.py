"""Pure business rules for payroll calculations and month-end cost formulas.

Per docs/06-payroll-and-cost.md and DEC-01, DEC-29, DEC-30, DEC-39:
- OT1 rate = (basic / 208) * 1.25
- OT2 rate = (basic / 208) * 1.50
- gratuity = basic / 365 * 30
- leave_salary = basic / 12
- per_month_provision = five company provisions (visa, air_ticket, uniform, accommodation, medical) + gratuity + leave_salary
- gross_pay = salary_portion - missed_hours_deduction + ot1_amount + ot2_amount
- net_pay = gross_pay (zero deductions)
- total_staff_cost = gross_pay + per_month_provision
- hr_oh = total_staff_cost * 5%
- final_total_staff_cost = total_staff_cost + hr_oh
- Job budget planned hourly cost = (revision_salary_portion + revision_line_provisions) * 1.05 / 208
"""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
DEFAULT_OT_DIVISOR = Decimal("208")
DEFAULT_OT1_MULTIPLIER = Decimal("1.25")
DEFAULT_OT2_MULTIPLIER = Decimal("1.50")
DEFAULT_HR_OH_RATE = Decimal("0.05")


def round_money(val: Decimal | int | float | str) -> Decimal:
    """Round monetary figures half-up to 2 decimal places."""
    d = Decimal(str(val)) if not isinstance(val, Decimal) else val
    return d.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_hourly_ot_rate(
    basic_salary: Decimal | int | float | str,
    multiplier: Decimal = DEFAULT_OT1_MULTIPLIER,
    divisor: Decimal = DEFAULT_OT_DIVISOR,
) -> Decimal:
    """Calculate hourly overtime rate.

    Example: basic 1100 -> (1100 / 208) * 1.25 = 6.61
             basic 1100 -> (1100 / 208) * 1.50 = 7.93
    """
    b = Decimal(str(basic_salary))
    rate = (b / divisor) * multiplier
    return round_money(rate)


def calculate_gratuity(basic_salary: Decimal | int | float | str) -> Decimal:
    """Calculate monthly gratuity provision: basic / 365 * 30."""
    b = Decimal(str(basic_salary))
    val = (b / Decimal("365")) * Decimal("30")
    return round_money(val)


def calculate_leave_salary(basic_salary: Decimal | int | float | str) -> Decimal:
    """Calculate monthly leave salary provision: basic / 12."""
    b = Decimal(str(basic_salary))
    val = b / Decimal("12")
    return round_money(val)


def calculate_provisions(
    visa: Decimal | int | float | str = Decimal("0.00"),
    air_ticket: Decimal | int | float | str = Decimal("0.00"),
    uniform: Decimal | int | float | str = Decimal("0.00"),
    accommodation: Decimal | int | float | str = Decimal("0.00"),
    medical: Decimal | int | float | str = Decimal("0.00"),
) -> Decimal:
    """Sum the 5 standard company provisions."""
    total = (
        Decimal(str(visa))
        + Decimal(str(air_ticket))
        + Decimal(str(uniform))
        + Decimal(str(accommodation))
        + Decimal(str(medical))
    )
    return round_money(total)


def calculate_per_month_provision(
    provisions_sum: Decimal | int | float | str,
    gratuity: Decimal | int | float | str,
    leave_salary: Decimal | int | float | str,
) -> Decimal:
    """Calculate per-month provision: provisions + gratuity + leave_salary."""
    total = (
        Decimal(str(provisions_sum))
        + Decimal(str(gratuity))
        + Decimal(str(leave_salary))
    )
    return round_money(total)


def calculate_missed_hours_deduction(
    basic_salary: Decimal | int | float | str,
    missed_hours: Decimal | int | float | str,
    divisor: Decimal = DEFAULT_OT_DIVISOR,
) -> Decimal:
    """Calculate deduction for missed unpaid hours (unexcused absence or unpaid leave)."""
    b = Decimal(str(basic_salary))
    hours = Decimal(str(missed_hours))
    if hours <= Decimal("0.00"):
        return Decimal("0.00")
    hourly_rate = b / divisor
    return round_money(hours * hourly_rate)


def calculate_gross_pay(
    salary_portion: Decimal | int | float | str,
    ot1_amount: Decimal | int | float | str = Decimal("0.00"),
    ot2_amount: Decimal | int | float | str = Decimal("0.00"),
    missed_hours_deduction: Decimal | int | float | str = Decimal("0.00"),
) -> Decimal:
    """Gross pay = salary_portion - missed_hours_deduction + ot1_amount + ot2_amount."""
    gross = (
        Decimal(str(salary_portion))
        - Decimal(str(missed_hours_deduction))
        + Decimal(str(ot1_amount))
        + Decimal(str(ot2_amount))
    )
    # Gross pay cannot be negative
    if gross < Decimal("0.00"):
        gross = Decimal("0.00")
    return round_money(gross)


def calculate_total_staff_cost(
    gross_pay: Decimal | int | float | str,
    per_month_provision: Decimal | int | float | str,
) -> Decimal:
    """Total staff cost = gross_pay + per_month_provision."""
    total = Decimal(str(gross_pay)) + Decimal(str(per_month_provision))
    return round_money(total)


def calculate_hr_overhead(
    total_staff_cost: Decimal | int | float | str,
    hr_oh_rate: Decimal = DEFAULT_HR_OH_RATE,
) -> Decimal:
    """HR overhead = total_staff_cost * 5%."""
    total = Decimal(str(total_staff_cost))
    return round_money(total * hr_oh_rate)


def calculate_final_total_staff_cost(
    total_staff_cost: Decimal | int | float | str,
    hr_oh: Decimal | int | float | str,
) -> Decimal:
    """Final total staff cost = total_staff_cost + hr_oh."""
    final_cost = Decimal(str(total_staff_cost)) + Decimal(str(hr_oh))
    return round_money(final_cost)


def calculate_revision_planned_hourly_cost(
    revision_salary_portion: Decimal | int | float | str,
    revision_provisions_sum: Decimal | int | float | str,
    hr_oh_rate: Decimal = DEFAULT_HR_OH_RATE,
    divisor: Decimal = DEFAULT_OT_DIVISOR,
) -> Decimal:
    """Calculate planned hourly labor cost for job budget from a salary revision line.

    planned_hourly_cost = (revision_salary_portion + revision_provisions) * (1 + HR_OH) / 208
    """
    total_base = Decimal(str(revision_salary_portion)) + Decimal(str(revision_provisions_sum))
    with_overhead = total_base * (Decimal("1.00") + hr_oh_rate)
    hourly = with_overhead / divisor
    return round_money(hourly)
