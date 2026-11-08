"""Pure business logic for Temporary Reassignments (Doc 04 Section 9, D2, BR-SC-04, DEC-43).

Pure functions without database or HTTP dependencies:
- Strict notice validation (at least 3 days for any role)
- Late approval detection
- Worker hours and constraint preview
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum


class ReassignmentType(StrEnum):
    """Types of temporary operational reassignments."""

    REPLACE = "REPLACE"
    MOVE = "MOVE"
    ADD = "ADD"
    CANCEL = "CANCEL"


class ReassignmentStatus(StrEnum):
    """Lifecycle status of a reassignment request."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class WorkerHoursPreview:
    """Preview of worker hours and capacity following a proposed reassignment."""

    employee_id: str
    work_date: date
    standard_hours: Decimal
    current_assigned_hours: Decimal
    proposed_hours_delta: Decimal
    resulting_hours: Decimal
    free_hours: Decimal
    planned_overtime_hours: Decimal
    warnings: list[str]


def validate_reassignment_notice(
    date_from: date,
    today_work_date: date,
    min_notice_days: int = 3,
) -> tuple[bool, str | None]:
    """Validate that the reassignment request meets the mandatory notice period.

    Per DEC-43, D2, and Phase 06 checklist:
    A request under min_notice_days (default 3 calendar days) is refused for any role.
    """
    notice_days = (date_from - today_work_date).days
    if notice_days < min_notice_days:
        return (
            False,
            f"Reassignment request requires at least {min_notice_days} days notice. "
            f"Requested start date is {date_from}, but minimum allowed is "
            f"{today_work_date + timedelta(days=min_notice_days)}.",
        )
    return True, None


def check_late_approval(
    date_from: date,
    decision_date: date,
    min_notice_days: int = 3,
) -> bool:
    """Check if the approval is arriving too late (less than the minimum notice period).

    Per D2: If approval arrives less than the notice period before date_from,
    it is still allowed but flagged LATE_APPROVAL.
    """
    days_remaining = (date_from - decision_date).days
    return days_remaining < min_notice_days


def is_reassignment_expired(
    date_from: date,
    current_work_date: date,
    status: str,
) -> bool:
    """Check if a pending reassignment request has expired because date_from has passed."""
    return status == ReassignmentStatus.PENDING and current_work_date > date_from


def preview_reassignment_hours(
    employee_id: str,
    work_date: date,
    standard_hours: Decimal,
    current_hours: Decimal,
    proposed_delta: Decimal,
    worker_grade_group: str | None = None,
    job_item_grade_group: str | None = None,
    is_on_approved_leave: bool = False,
    has_permanent_assignment: bool = False,
    is_target_permanent: bool = False,
) -> WorkerHoursPreview:
    """Compute resulting daily hours and evaluate potential warnings.

    Warnings:
    - OVER_STANDARD_HOURS: resulting hours > standard hours (planned overtime)
    - UNDER_STANDARD_HOURS: resulting hours < standard hours
    - GRADE_GROUP_MISMATCH: worker's grade group differs from job item's
    - ON_APPROVED_LEAVE: worker has approved leave on that date
    - PERMANENT_EXCLUSIVE: permanent assignment conflict
    """
    resulting = max(Decimal("0.00"), current_hours + proposed_delta)
    free = max(Decimal("0.00"), standard_hours - resulting)
    planned_ot = max(Decimal("0.00"), resulting - standard_hours)

    warnings: list[str] = []

    if resulting > standard_hours:
        warnings.append("OVER_STANDARD_HOURS")
    elif resulting < standard_hours:
        warnings.append("UNDER_STANDARD_HOURS")

    if (
        worker_grade_group
        and job_item_grade_group
        and worker_grade_group.upper() != job_item_grade_group.upper()
    ):
        warnings.append("GRADE_GROUP_MISMATCH")

    if is_on_approved_leave:
        warnings.append("ON_APPROVED_LEAVE")

    if is_target_permanent and (current_hours > 0 or has_permanent_assignment):
        warnings.append("PERMANENT_EXCLUSIVE")
    elif has_permanent_assignment and proposed_delta > 0:
        warnings.append("PERMANENT_EXCLUSIVE")

    return WorkerHoursPreview(
        employee_id=employee_id,
        work_date=work_date,
        standard_hours=standard_hours,
        current_assigned_hours=current_hours,
        proposed_hours_delta=proposed_delta,
        resulting_hours=resulting,
        free_hours=free,
        planned_overtime_hours=planned_ot,
        warnings=warnings,
    )

