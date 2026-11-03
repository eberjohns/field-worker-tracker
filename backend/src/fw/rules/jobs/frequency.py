"""Frequency calculation rules per BR-JB-06 and docs/04-scheduling-engine.md Section 2."""

from decimal import ROUND_HALF_UP, Decimal

PERIODS_PER_YEAR: dict[str, int] = {
    "WEEK": 52,
    "MONTH": 12,
    "QUARTER": 4,
    "YEAR": 1,
}


class InvalidFrequencyError(ValueError):
    """Raised when frequency parameters are invalid."""

    pass


def calculate_expected_activities_per_year(
    frequency_unit: str,
    occurrences_per_period: Decimal | float | int,
    period_interval: int = 1,
) -> Decimal:
    """Calculate expected activities per year from structured frequency.

    Formula:
        expected_activities_per_year = occurrences_per_period * periods_per_year / period_interval
    """
    unit_upper = frequency_unit.strip().upper()
    if unit_upper not in PERIODS_PER_YEAR:
        raise InvalidFrequencyError(
            f"Invalid frequency unit '{frequency_unit}'. Must be one of {list(PERIODS_PER_YEAR.keys())}."
        )

    if period_interval <= 0:
        raise InvalidFrequencyError("period_interval must be greater than 0.")

    occ = Decimal(str(occurrences_per_period))
    if occ <= Decimal("0"):
        raise InvalidFrequencyError("occurrences_per_period must be greater than 0.")

    periods = Decimal(PERIODS_PER_YEAR[unit_upper])
    interval = Decimal(period_interval)

    activities = (occ * periods) / interval
    # Quantize to 3 decimal places for precision
    return activities.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def calculate_expected_annual_hours(
    expected_activities_per_year: Decimal | float | int,
    required_staff_count: int,
    hours_per_occurrence_per_staff: Decimal | float | int,
) -> Decimal:
    """Calculate expected annual man-hours from expected activities.

    Formula:
        expected_annual_hours = activities * required_staff_count * hours_per_occurrence_per_staff
    """
    if required_staff_count <= 0:
        raise InvalidFrequencyError("required_staff_count must be greater than 0.")

    hours = Decimal(str(hours_per_occurrence_per_staff))
    if hours <= Decimal("0"):
        raise InvalidFrequencyError("hours_per_occurrence_per_staff must be greater than 0.")

    activities = Decimal(str(expected_activities_per_year))
    staff = Decimal(required_staff_count)

    total_hours = activities * staff * hours
    return total_hours.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
