"""Pure domain rules for Base Roster Templates (Blueprint recurring engine).

The Base Planner configures standard recurring staffing patterns for contract job items.
It operates in two modes:
  - UNIFORM: The same assigned crew is scheduled across all active working days of the job.
  - DAY_OF_WEEK: A day-specific crew matrix allowing independent staffing on each day of the week
    (e.g. allocating replacement workers on Friday for crew members whose weekly off is Friday).
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
    weekday_mask: str  # "ALL" or "MON".."SUN"
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


def resolve_base_template_slots(
    allocation_mode: str,
    entries: list[BlueprintEntry],
    target_dates: list[date],
    public_holidays: set[date],
    worker_weekly_off_days: dict[UUID, str],  # employee_id -> "FRI", "SUN", etc.
    job_working_days: set[str] | None = None,  # set of active weekdays, e.g. {"MON", "TUE", ...}
) -> list[ResolvedTemplateSlot]:
    """Resolve a Base Roster Template into daily slots across a list of calendar dates.

    Args:
        allocation_mode: 'UNIFORM' or 'DAY_OF_WEEK'.
        entries: List of BlueprintEntry definitions.
        target_dates: Calendar dates to evaluate (e.g. a 7-day week or 1-month range).
        public_holidays: Dates that are recognized company/state public holidays.
        worker_weekly_off_days: Mapping of employee_id to their weekly rest day ("MON".."SUN").
        job_working_days: Active days of the job item. If None, all days are considered active.

    Returns:
        List of ResolvedTemplateSlot objects.
    """
    mode = allocation_mode.upper()
    resolved: list[ResolvedTemplateSlot] = []

    for d in target_dates:
        dow = INT_TO_WEEKDAY[d.weekday()]

        # If the job item only works on specific days, skip non-working days
        if job_working_days is not None and dow not in job_working_days:
            continue

        is_holiday = d in public_holidays

        # Filter matching entries for this date
        matching_entries: list[BlueprintEntry] = []
        if mode == "UNIFORM":
            # In UNIFORM mode, entries with mask == 'ALL' apply to all working days
            matching_entries = [e for e in entries if e.weekday_mask in ("ALL", dow)]
        else:
            # In DAY_OF_WEEK mode, only entries explicitly configured for this weekday apply
            matching_entries = [e for e in entries if e.weekday_mask == dow]

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
    """Validate template entries against required staffing count and completeness.

    Returns:
        List of warning/issue messages (empty if completely compliant).
    """
    issues: list[str] = []
    mode = allocation_mode.upper()

    if not entries:
        issues.append("Base template has no assigned workers.")
        return issues

    if mode == "UNIFORM":
        # Check that uniform crew count matches required staff count
        uniform_entries = [e for e in entries if e.weekday_mask == "ALL"]
        if len(uniform_entries) < required_staff_count:
            issues.append(
                f"Uniform crew has {len(uniform_entries)} workers; required is {required_staff_count}."
            )
    else:
        # Check each active working day has enough workers assigned
        for dow in sorted(job_working_days, key=lambda w: WEEKDAY_TO_INT.get(w, 0)):
            day_entries = [e for e in entries if e.weekday_mask == dow]
            if len(day_entries) < required_staff_count:
                issues.append(
                    f"{dow} has {len(day_entries)} workers assigned; required is {required_staff_count}."
                )

    return issues
