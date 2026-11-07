"""Pure business logic for Day Markers (Doc 04 Section 6).

Day markers explain why a day has no work or requires attention:
- SKIPPED: public holiday (jobs are skipped on public holidays)
- WEEKLY_OFF: the worker's weekly off day
- ON_LEAVE: approved leave
- TO_BE_COVERED: a job slot with no available worker
- FREE: the worker has no assignment and is available
- NO_BOUNDARY: the site has no boundary yet (chip warning)
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from fw.rules.scheduling.assignment import INT_TO_WEEKDAY


class DayMarker(StrEnum):
    """Enumeration of standard day markers."""

    SKIPPED = "SKIPPED"
    WEEKLY_OFF = "WEEKLY_OFF"
    ON_LEAVE = "ON_LEAVE"
    TO_BE_COVERED = "TO_BE_COVERED"
    FREE = "FREE"
    NO_BOUNDARY = "NO_BOUNDARY"


@dataclass(frozen=True)
class WorkerDayContext:
    """Context for a worker on a specific date to compute their day marker."""

    employee_id: str
    work_date: date
    weekly_off_day: str | None  # e.g. "SUNDAY" or "SUN"
    has_active_assignments: bool
    is_public_holiday: bool
    is_on_leave: bool = False


def normalize_day_name(day_name: str | None) -> str | None:
    """Normalize day name to 3-letter uppercase (e.g. 'SUNDAY' -> 'SUN')."""
    if not day_name:
        return None
    cleaned = day_name.strip().upper()
    return cleaned[:3] if len(cleaned) >= 3 else cleaned


def evaluate_worker_day_marker(context: WorkerDayContext) -> DayMarker | None:
    """Evaluate explainable day marker for a worker on a date.

    Returns:
    - None if the worker has active assignments (unless a slot is uncovered).
    - SKIPPED if it is a public holiday and no active assignment exists.
    - ON_LEAVE if the worker is on approved leave.
    - WEEKLY_OFF if the date matches the worker's weekly off day.
    - FREE if the worker has no assignments and is available.
    """
    if context.has_active_assignments:
        return None

    if context.is_public_holiday:
        return DayMarker.SKIPPED

    if context.is_on_leave:
        return DayMarker.ON_LEAVE

    weekday_3 = INT_TO_WEEKDAY[context.work_date.weekday()]
    worker_off_3 = normalize_day_name(context.weekly_off_day)

    if worker_off_3 and weekday_3 == worker_off_3:
        return DayMarker.WEEKLY_OFF

    return DayMarker.FREE
