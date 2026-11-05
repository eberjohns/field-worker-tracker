"""Pure business logic for standing assignment date expansion."""

from collections.abc import Generator
from dataclasses import dataclass
from datetime import date, timedelta

WEEKDAY_NAMES: tuple[str, ...] = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
WEEKDAY_TO_INT: dict[str, int] = {name: idx for idx, name in enumerate(WEEKDAY_NAMES)}
INT_TO_WEEKDAY: dict[int, str] = dict(enumerate(WEEKDAY_NAMES))

DEFAULT_WORKING_DAYS: tuple[str, ...] = ("MON", "TUE", "WED", "THU", "FRI", "SAT")


@dataclass(frozen=True)
class AssignmentDateSlot:
    """A generated calendar date slot for a standing assignment."""

    work_date: date
    weekday: str
    is_public_holiday: bool
    is_working_day: bool


def normalize_weekday_pattern(pattern: list[str] | None) -> set[str]:
    """Normalize weekday pattern list to a set of uppercase 3-letter strings."""
    if not pattern:
        return set(DEFAULT_WORKING_DAYS)
    return {p.strip().upper()[:3] for p in pattern if p.strip().upper()[:3] in WEEKDAY_TO_INT}


def generate_assignment_dates(
    start_date: date,
    end_date: date,
    weekday_pattern: list[str] | None = None,
    public_holidays: set[date] | None = None,
    skip_public_holidays: bool = True,
) -> Generator[AssignmentDateSlot, None, None]:
    """Generate calendar date slots for a standing assignment.

    Yields AssignmentDateSlot for each date in [start_date, end_date].
    is_working_day is True if the day falls on the weekday pattern and is not
    skipped by a public holiday.
    """
    if start_date > end_date:
        return

    pattern_set = normalize_weekday_pattern(weekday_pattern)
    holidays = public_holidays or set()

    current = start_date
    while current <= end_date:
        weekday_str = INT_TO_WEEKDAY[current.weekday()]
        is_holiday = current in holidays
        matches_pattern = weekday_str in pattern_set
        is_working = matches_pattern and not (skip_public_holidays and is_holiday)

        yield AssignmentDateSlot(
            work_date=current,
            weekday=weekday_str,
            is_public_holiday=is_holiday,
            is_working_day=is_working,
        )
        current += timedelta(days=1)

