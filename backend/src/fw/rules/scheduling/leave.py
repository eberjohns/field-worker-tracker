"""Pure business logic for Leave Management (Doc 04 Section 9, D2, BR-SC-05, DEC-46).

Pure functions without database or HTTP dependencies:
- Leave date and notice validation
- Overlap detection
- Working days vs calendar days leave calculation
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from fw.rules.scheduling.markers import normalize_day_name


class LeaveType(StrEnum):
    """Supported leave types."""

    ANNUAL = "ANNUAL"
    SICK = "SICK"
    UNPAID = "UNPAID"
    EMERGENCY = "EMERGENCY"
    OTHER = "OTHER"


class LeaveStatus(StrEnum):
    """Lifecycle status of a leave request."""

    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class LeaveRecord:
    """Read-only view of a leave request for rule calculations."""

    id: uuid.UUID
    employee_id: uuid.UUID
    leave_type: str
    from_date: date
    to_date: date
    status: str


def validate_leave_dates(
    from_date: date,
    to_date: date,
    today_work_date: date,
    is_admin: bool = False,
    min_notice_days: int = 3,
) -> tuple[bool, str | None]:
    """Validate leave request date boundaries and notice requirements.

    - to_date must be on or after from_date.
    - Non-admin users must submit leave with at least `min_notice_days` notice.
    - Admin users can record leaves for any date, including the past.
    """
    if to_date < from_date:
        return False, f"End date ({to_date}) cannot be before start date ({from_date})."

    if not is_admin:
        notice_days = (from_date - today_work_date).days
        if notice_days < min_notice_days:
            return (
                False,
                f"Leave request requires at least {min_notice_days} days notice. "
                f"Earliest allowed start date is {today_work_date + timedelta(days=min_notice_days)}.",
            )

    return True, None


def check_overlapping_leaves(
    employee_id: uuid.UUID,
    from_date: date,
    to_date: date,
    existing_leaves: Sequence[LeaveRecord],
    exclude_leave_id: uuid.UUID | None = None,
) -> tuple[bool, str | None]:
    """Check whether the proposed leave overlaps with any existing REQUESTED or APPROVED leave.

    Returns:
        (True, None) if clean.
        (False, reason) if overlapping.
    """
    for req in existing_leaves:
        if exclude_leave_id and req.id == exclude_leave_id:
            continue
        if req.employee_id != employee_id:
            continue
        if req.status not in (LeaveStatus.REQUESTED, LeaveStatus.APPROVED):
            continue

        # Check interval overlap: [from_date, to_date] vs [req.from_date, req.to_date]
        if not (to_date < req.from_date or from_date > req.to_date):
            return (
                False,
                f"Leave overlaps with existing {req.status} leave "
                f"({req.leave_type}: {req.from_date} to {req.to_date}).",
            )

    return True, None


def calculate_leave_taken(
    approved_leaves: Sequence[LeaveRecord],
    year: int,
    weekly_off_day: str | None,
    public_holidays: set[date],
) -> dict[str, dict[str, int]]:
    """Calculate leave taken in a calendar year grouped by leave type.

    Counts:
    - working_days: days excluding public holidays and weekly-off days (exclusive leave).
    - calendar_days: total calendar days falling in the year.

    Returns:
        Mapping of leave_type -> {"working_days": int, "calendar_days": int}
    """
    normalized_off = normalize_day_name(weekly_off_day) or "SUN"
    dow_names = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

    summary: dict[str, dict[str, int]] = {
        lt.value: {"working_days": 0, "calendar_days": 0} for lt in LeaveType
    }

    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)

    for leave in approved_leaves:
        if leave.status != LeaveStatus.APPROVED:
            continue

        # Clamp interval to target calendar year
        start = max(leave.from_date, year_start)
        end = min(leave.to_date, year_end)

        if start > end:
            continue

        lt = leave.leave_type.upper()
        if lt not in summary:
            summary[lt] = {"working_days": 0, "calendar_days": 0}

        cur = start
        while cur <= end:
            summary[lt]["calendar_days"] += 1

            dow = dow_names[cur.weekday()]
            is_off_day = dow == normalized_off
            is_holiday = cur in public_holidays

            if not is_off_day and not is_holiday:
                summary[lt]["working_days"] += 1

            cur += timedelta(days=1)

    return summary
