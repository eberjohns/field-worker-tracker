"""Pure business rules for employee salary structures.

Per docs/06-payroll-and-cost.md and DEC-06:
- salary_portion = basic + special_allowance + fixed_ot + bonus + telephone_allowance + housing_transport_allowance
- salary changes apply from the next payroll month (first day of next calendar month)
- last change date and difference (new fixed salary - previous fixed salary)
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def round_money(val: Decimal | int | float | str) -> Decimal:
    """Round money half-up to 2 decimal places."""
    d = Decimal(str(val)) if not isinstance(val, Decimal) else val
    return d.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_salary_portion(
    basic: Decimal | int | float | str,
    special_allowance: Decimal | int | float | str = Decimal("0.00"),
    fixed_ot: Decimal | int | float | str = Decimal("0.00"),
    bonus: Decimal | int | float | str = Decimal("0.00"),
    telephone_allowance: Decimal | int | float | str = Decimal("0.00"),
    housing_transport_allowance: Decimal | int | float | str = Decimal("0.00"),
) -> Decimal:
    """Calculate the total fixed salary portion."""
    total = (
        Decimal(str(basic))
        + Decimal(str(special_allowance))
        + Decimal(str(fixed_ot))
        + Decimal(str(bonus))
        + Decimal(str(telephone_allowance))
        + Decimal(str(housing_transport_allowance))
    )
    return round_money(total)


def compute_next_payroll_month_start(as_of: date) -> date:
    """Return the first calendar day of the upcoming payroll month.

    Example: 2026-11-03 -> 2026-12-01; 2026-12-15 -> 2027-01-01.
    """
    if as_of.month == 12:
        return date(as_of.year + 1, 1, 1)
    return date(as_of.year, as_of.month + 1, 1)


def calculate_salary_difference(
    current_portion: Decimal,
    previous_portion: Decimal | None,
) -> Decimal:
    """Calculate the difference between current and previous salary portion.

    Difference = current - previous (negative represents a reduction).
    If no previous portion exists, returns 0.00.
    """
    if previous_portion is None:
        return Decimal("0.00")
    diff = current_portion - previous_portion
    return round_money(diff)
