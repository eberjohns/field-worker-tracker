"""Decomposition of job occurrence hours into job unit days (DEC-11, BR-JB-05)."""

from decimal import Decimal

DEFAULT_PLANNED_WORKDAY_HOURS = Decimal("9.0")


def split_job_unit_days(
    hours_per_occurrence_per_staff: Decimal | float | int,
    planned_workday_hours: Decimal | float | int = DEFAULT_PLANNED_WORKDAY_HOURS,
) -> list[Decimal]:
    """Split hours_per_occurrence_per_staff into 9-hour daily chunks.

    Example: 42.688 h = 4 x 9 + 6.688 -> returns [Decimal('9.0'), Decimal('9.0'), Decimal('9.0'), Decimal('9.0'), Decimal('6.688')].
    Returns empty list if hours <= 0.
    """
    total = Decimal(str(hours_per_occurrence_per_staff))
    day_unit = Decimal(str(planned_workday_hours))

    if total <= Decimal("0") or day_unit <= Decimal("0"):
        return []

    chunks: list[Decimal] = []
    remaining = total
    while remaining > day_unit:
        chunks.append(day_unit)
        remaining -= day_unit

    if remaining > Decimal("0"):
        chunks.append(remaining)

    return chunks


def calculate_days_per_occurrence(
    hours_per_occurrence_per_staff: Decimal | float | int,
    planned_workday_hours: Decimal | float | int = DEFAULT_PLANNED_WORKDAY_HOURS,
) -> int:
    """Calculate the number of job unit days required for an occurrence.

    Formula: ceil(hours_per_occurrence_per_staff / planned_workday_hours)
    """
    chunks = split_job_unit_days(hours_per_occurrence_per_staff, planned_workday_hours)
    return len(chunks)
