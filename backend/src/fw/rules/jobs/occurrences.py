"""Occurrence generation rules across rolling horizon (docs/04-scheduling-engine.md Sections 2-4)."""

import calendar
import math
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

WEEKDAY_INDEX_MAP: dict[str, int] = {
    "MONDAY": 0,
    "TUESDAY": 1,
    "WEDNESDAY": 2,
    "THURSDAY": 3,
    "FRIDAY": 4,
    "SATURDAY": 5,
    "SUNDAY": 6,
}


@dataclass(frozen=True)
class OccurrenceSlot:
    """A generated candidate occurrence slot."""

    window_start: date
    window_end: date
    slot_index: int
    due_date: date | None
    suggested_date: date | None
    required_staff_count: int
    required_hours_per_staff: Decimal


def is_budget_only_staff_type(
    staff_grade_description: str,
    budget_only_types: list[str] | set[str] | None,
) -> bool:
    """Check whether a staff type is budget-only (DEC-09, DEC-48, BR-JB-07)."""
    if not budget_only_types:
        return False
    norm_set = {t.strip().upper() for t in budget_only_types}
    return staff_grade_description.strip().upper() in norm_set


def _get_working_days_in_window(
    start: date,
    end: date,
    weekly_off_weekday: int = 6,  # 6 = Sunday
) -> list[date]:
    """Get all working dates between start and end (inclusive), skipping weekly off day."""
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() != weekly_off_weekday:
            days.append(current)
        current += timedelta(days=1)
    return days


def _suggest_date(working_days: list[date], slot_index: int, total_slots: int) -> date | None:
    """Calculate suggested date for the i-th of k occurrences over n working days:

    - When total_slots == 1: default to the first working day of the window (Monday).
    - When total_slots > 1: formula working_day[floor((i + 0.5) * n / k)]
    """
    n = len(working_days)
    if n == 0 or total_slots <= 0:
        return None
    if total_slots == 1:
        return working_days[0]
    idx = int(math.floor((slot_index + 0.5) * n / total_slots))
    clamped_idx = max(0, min(idx, n - 1))
    return working_days[clamped_idx]


def generate_occurrence_slots(
    frequency_unit: str,
    occurrences_per_period: Decimal | float | int,
    period_interval: int,
    required_staff_count: int,
    hours_per_occurrence_per_staff: Decimal | float | int,
    horizon_start: date,
    horizon_end: date,
    item_start_date: date,
    item_end_date: date | None = None,
    weekday_pattern: list[str] | None = None,
    staff_grade_description: str = "",
    budget_only_types: list[str] | set[str] | None = None,
) -> list[OccurrenceSlot]:
    """Generate occurrence slots for a job item across a rolling horizon window.

    - Budget-only staff types return an empty list (they never generate occurrences).
    - Windows are aligned with ISO weeks, calendar months, quarters, or calendar years.
    - Idempotent by (job_item_id, window_start, slot_index).
    """
    if is_budget_only_staff_type(staff_grade_description, budget_only_types):
        return []

    unit = frequency_unit.strip().upper()
    k_occ = int(math.floor(float(occurrences_per_period)))
    if k_occ <= 0:
        return []

    interval = max(1, period_interval)
    staff_count = max(1, required_staff_count)
    req_hours = Decimal(str(hours_per_occurrence_per_staff))

    # Active date range for occurrences
    active_from = max(horizon_start, item_start_date)
    active_to = horizon_end
    if item_end_date is not None:
        active_to = min(active_to, item_end_date)

    if active_from > active_to:
        return []

    slots: list[OccurrenceSlot] = []

    if unit == "WEEK":
        # Align to Monday of the week of active_from
        curr_monday = active_from - timedelta(days=active_from.weekday())
        week_count = 0

        while curr_monday <= active_to:
            curr_sunday = curr_monday + timedelta(days=6)
            # Only generate if the week interval matches
            if (week_count % interval) == 0:
                # Check overlap with [active_from, active_to]
                if curr_sunday >= active_from and curr_monday <= active_to:
                    working_days = _get_working_days_in_window(curr_monday, curr_sunday)
                    pattern_days: list[int] = []
                    if weekday_pattern:
                        for wp in weekday_pattern:
                            w_upper = wp.strip().upper()
                            if w_upper in WEEKDAY_INDEX_MAP:
                                pattern_days.append(WEEKDAY_INDEX_MAP[w_upper])

                    for i in range(k_occ):
                        due_dt: date | None = None
                        suggested_dt: date | None = None

                        if i < len(pattern_days):
                            target_day = curr_monday + timedelta(days=pattern_days[i])
                            if active_from <= target_day <= active_to:
                                due_dt = target_day
                                suggested_dt = target_day
                        else:
                            suggested_dt = _suggest_date(working_days, i, k_occ)

                        slots.append(
                            OccurrenceSlot(
                                window_start=curr_monday,
                                window_end=curr_sunday,
                                slot_index=i,
                                due_date=due_dt,
                                suggested_date=suggested_dt,
                                required_staff_count=staff_count,
                                required_hours_per_staff=req_hours,
                            )
                        )
            curr_monday += timedelta(days=7)
            week_count += 1

    elif unit == "MONTH":
        # Monthly calendar windows
        curr_year = active_from.year
        curr_month = active_from.month
        month_count = 0

        while True:
            first_day = date(curr_year, curr_month, 1)
            last_day_num = calendar.monthrange(curr_year, curr_month)[1]
            last_day = date(curr_year, curr_month, last_day_num)

            if first_day > active_to:
                break

            if (month_count % interval) == 0 and last_day >= active_from and first_day <= active_to:
                working_days = _get_working_days_in_window(first_day, last_day)
                for i in range(k_occ):
                    sugg = _suggest_date(working_days, i, k_occ)
                    slots.append(
                        OccurrenceSlot(
                            window_start=first_day,
                            window_end=last_day,
                            slot_index=i,
                            due_date=None,
                            suggested_date=sugg,
                            required_staff_count=staff_count,
                            required_hours_per_staff=req_hours,
                        )
                    )

            # Advance to next month
            month_count += 1
            if curr_month == 12:
                curr_year += 1
                curr_month = 1
            else:
                curr_month += 1

    elif unit == "QUARTER":
        # Quarterly calendar windows
        curr_year = active_from.year
        curr_q = (active_from.month - 1) // 3  # 0, 1, 2, 3
        q_count = 0

        while True:
            start_m = curr_q * 3 + 1
            end_m = start_m + 2
            first_day = date(curr_year, start_m, 1)
            last_day_num = calendar.monthrange(curr_year, end_m)[1]
            last_day = date(curr_year, end_m, last_day_num)

            if first_day > active_to:
                break

            if (q_count % interval) == 0 and last_day >= active_from and first_day <= active_to:
                working_days = _get_working_days_in_window(first_day, last_day)
                for i in range(k_occ):
                    sugg = _suggest_date(working_days, i, k_occ)
                    slots.append(
                        OccurrenceSlot(
                            window_start=first_day,
                            window_end=last_day,
                            slot_index=i,
                            due_date=None,
                            suggested_date=sugg,
                            required_staff_count=staff_count,
                            required_hours_per_staff=req_hours,
                        )
                    )

            q_count += 1
            if curr_q == 3:
                curr_year += 1
                curr_q = 0
            else:
                curr_q += 1

    elif unit == "YEAR":
        # Calendar year split into k equal sub-windows
        curr_year = active_from.year
        year_count = 0

        while True:
            first_day = date(curr_year, 1, 1)
            last_day = date(curr_year, 12, 31)

            if first_day > active_to:
                break

            if (year_count % interval) == 0 and last_day >= active_from and first_day <= active_to:
                total_days = (last_day - first_day).days + 1
                sub_window_size = total_days / k_occ

                for i in range(k_occ):
                    sub_start = first_day + timedelta(days=int(i * sub_window_size))
                    sub_end = (
                        first_day + timedelta(days=int((i + 1) * sub_window_size) - 1)
                        if i < k_occ - 1
                        else last_day
                    )
                    working_days = _get_working_days_in_window(sub_start, sub_end)
                    sugg = _suggest_date(working_days, 0, 1) if working_days else None

                    slots.append(
                        OccurrenceSlot(
                            window_start=sub_start,
                            window_end=sub_end,
                            slot_index=i,
                            due_date=None,
                            suggested_date=sugg,
                            required_staff_count=staff_count,
                            required_hours_per_staff=req_hours,
                        )
                    )

            year_count += 1
            curr_year += 1

    return slots
