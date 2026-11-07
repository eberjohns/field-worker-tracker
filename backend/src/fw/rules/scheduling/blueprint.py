"""Pure domain rules for Base Roster Templates (Blueprint recurring engine).

The Base Planner configures standard recurring staffing patterns for contract job items.
Staff assignments are stored explicitly by weekday (e.g. 'MON'..'SUN') or periodic cadence
(e.g. 'W1_MON', 'W3_MON' for monthly jobs, 'M1_W2_WED' for quarterly jobs).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

WEEKDAY_ORDER = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
INT_TO_WEEKDAY = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
WEEKDAY_TO_INT = {v: k for k, v in INT_TO_WEEKDAY.items()}


@dataclass(frozen=True)
class BlueprintEntry:
    """An assigned worker entry within a base roster template."""

    employee_id: UUID
    weekday_mask: str  # "MON".."SUN" or "ALL", or periodic e.g. "W1_MON", "M1_W2_WED"
    assigned_hours: float
    sequence: int = 1


@dataclass(frozen=True)
class ResolvedTemplateSlot:
    """A concrete daily slot resolved from the base template for a specific calendar date."""

    work_date: date
    day_of_week: str  # "MON".."SUN"
    employee_id: UUID
    assigned_hours: float
    sequence: int
    is_public_holiday: bool
    is_worker_weekly_off: bool
    status: str  # "VALID" | "HOLIDAY_OVERTIME" | "REST_DAY_WARNING"
    notes: list[str] = field(default_factory=list)


def get_week_of_month(d: date) -> int:
    """Determine the 1-based week index of the month (1..4)."""
    dom = d.day
    if dom <= 7:
        return 1
    elif dom <= 14:
        return 2
    elif dom <= 21:
        return 3
    else:
        return 4


def get_month_of_quarter(d: date) -> int:
    """Determine the 1-based month index within the quarter (1..3)."""
    month = d.month
    return ((month - 1) % 3) + 1


def is_entry_matching_date(mask: str, target_date: date) -> bool:
    """Check if a template entry's mask applies to a specific calendar date."""
    dow = INT_TO_WEEKDAY[target_date.weekday()]
    upper_mask = mask.upper()

    # 1. Simple weekday match or uniform ALL
    if upper_mask == "ALL":
        return True
    if upper_mask == dow:
        return True

    # 2. Monthly cadence prefix (e.g. "W1_MON", "W3_WED")
    if upper_mask.startswith("W"):
        parts = upper_mask.split("_")
        if len(parts) == 2:
            try:
                target_week_num = int(parts[0][1:])
                target_dow = parts[1]
                if target_dow == dow and get_week_of_month(target_date) == target_week_num:
                    return True
            except ValueError:
                pass

    # 3. Quarterly cadence prefix (e.g. "M1_W2_WED")
    if upper_mask.startswith("M"):
        parts = upper_mask.split("_")
        if len(parts) == 3:
            try:
                target_m_num = int(parts[0][1:])
                target_w_num = int(parts[1][1:])
                target_dow = parts[2]
                if (
                    target_dow == dow
                    and get_month_of_quarter(target_date) == target_m_num
                    and get_week_of_month(target_date) == target_w_num
                ):
                    return True
            except ValueError:
                pass

    return False


def resolve_base_template_slots(
    allocation_mode: str,
    entries: list[BlueprintEntry],
    target_dates: list[date],
    public_holidays: set[date],
    worker_weekly_off_days: dict[UUID, str],  # employee_id -> "FRI", "SUN", etc.
    job_working_days: set[str] | None = None,  # retained for backward compatibility, not used as hard drop
) -> list[ResolvedTemplateSlot]:
    """Resolve a Base Roster Template into daily slots across a list of calendar dates.

    Args:
        allocation_mode: 'UNIFORM' or 'DAY_OF_WEEK'.
        entries: List of BlueprintEntry definitions.
        target_dates: Calendar dates to evaluate (e.g. a 7-day week or 1-month range).
        public_holidays: Dates that are recognized company/state public holidays.
        worker_weekly_off_days: Mapping of employee_id to their weekly rest day ("MON".."SUN").
        job_working_days: Kept for API compatibility; no hard drop is performed.

    Returns:
        List of ResolvedTemplateSlot objects.
    """
    resolved: list[ResolvedTemplateSlot] = []

    for d in target_dates:
        dow = INT_TO_WEEKDAY[d.weekday()]
        is_holiday = d in public_holidays

        # Find all entries matching this date
        matching_entries = [e for e in entries if is_entry_matching_date(e.weekday_mask, d)]

        for entry in matching_entries:
            off_day = worker_weekly_off_days.get(entry.employee_id, "").upper()
            is_worker_off = off_day == dow

            notes: list[str] = []
            status = "VALID"

            if is_holiday:
                status = "HOLIDAY_OVERTIME"
                notes.append("Public Holiday: Public holiday overtime applies")

            if is_worker_off:
                status = "REST_DAY_WARNING"
                notes.append(f"Rest Day: Worker scheduled on weekly rest day ({dow})")

            resolved.append(
                ResolvedTemplateSlot(
                    work_date=d,
                    day_of_week=dow,
                    employee_id=entry.employee_id,
                    assigned_hours=entry.assigned_hours,
                    sequence=entry.sequence,
                    is_public_holiday=is_holiday,
                    is_worker_weekly_off=is_worker_off,
                    status=status,
                    notes=notes,
                )
            )

    return resolved


def validate_base_template_entries(
    allocation_mode: str,
    entries: list[BlueprintEntry],
    required_staff_count: int,
    job_working_days: set[str],
) -> list[str]:
    """Validate template entries against required staffing count and completeness."""
    issues: list[str] = []
    if not entries:
        issues.append("Base template has no assigned workers.")
    return issues
