"""Pure domain rules for Operational Planner cell state resolution.

Resolves effective daily worker assignments for a job item cell by combining:
  1. Base Blueprint template slots (recurring plan)
  2. Approved leave records (identifies absent base workers)
  3. Single-day operational shifts (overrides, replacements, direct assignments)

Precedence order:
  OPERATIONAL OVERRIDE / DIRECT (solid 100% opacity)
    > APPROVED LEAVE WITHOUT COVER (TO_BE_COVERED amber dashed)
    > BASE BLUEPRINT (muted 40% opacity)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from fw.rules.scheduling.blueprint import ResolvedTemplateSlot, is_same_weekday


@dataclass(frozen=True)
class OperationalShiftInput:
    """A single-day operational shift record from scheduled_work table."""

    id: UUID
    work_date: date
    employee_id: UUID
    source: str  # "TEMPLATE" | "STANDING" | "DIRECT" | "OVERRIDE" | "EXCEPTION"
    original_employee_id: UUID | None
    override_reason: str | None
    assigned_hours: float
    sequence: int = 1
    status: str = "ACTIVE"  # "ACTIVE" | "CANCELLED"


@dataclass(frozen=True)
class ResolvedOperationalCellWorker:
    """An effective worker display item within an operational day cell."""

    employee_id: UUID
    assigned_hours: float
    sequence: int
    display_type: str  # "BLUEPRINT" (muted) | "OVERRIDE" (solid) | "DIRECT" (solid) | "TO_BE_COVERED" (dashed) | "REMOVED" (red)
    opacity_class: str  # "muted" (40%) | "solid" (100%) | "warning" (amber dashed) | "removed" (red)
    original_employee_id: UUID | None = None
    shift_id: UUID | None = None
    reason: str | None = None
    is_public_holiday: bool = False
    is_rest_day: bool = False
    tags: list[str] = field(default_factory=list)


def resolve_operational_cell(
    work_date: date,
    base_slots: list[ResolvedTemplateSlot],
    approved_leave_worker_ids: set[UUID],
    operational_shifts: list[OperationalShiftInput],
    is_public_holiday: bool = False,
    worker_weekly_off_days: dict[UUID, str] | None = None,
) -> list[ResolvedOperationalCellWorker]:
    """Resolve effective workers for a single job item on a specific calendar date.

    Args:
        work_date: The calendar date being resolved.
        base_slots: Blueprint slots scheduled for this date.
        approved_leave_worker_ids: Set of worker UUIDs with approved leave on this date.
        operational_shifts: Single-day operational shifts on this date for this job item.
        is_public_holiday: Whether this date is a recognized public holiday.
        worker_weekly_off_days: Mapping of employee_id -> weekly off day string ("FRI", etc.).

    Returns:
        List of ResolvedOperationalCellWorker items to display in the cell.
    """
    off_days = worker_weekly_off_days or {}
    dow = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")[work_date.weekday()]

    # Index operational shifts
    replacements_by_orig_worker: dict[UUID, OperationalShiftInput] = {}
    cancellations_by_worker: dict[UUID, OperationalShiftInput] = {}
    direct_shifts: list[OperationalShiftInput] = []

    for s in operational_shifts:
        if s.status == "CANCELLED":
            cancellations_by_worker[s.employee_id] = s
        elif s.original_employee_id is not None and s.source == "OVERRIDE":
            replacements_by_orig_worker[s.original_employee_id] = s
        elif s.source in ("DIRECT", "OVERRIDE", "EXCEPTION"):
            direct_shifts.append(s)

    resolved: list[ResolvedOperationalCellWorker] = []

    # 1. Process base blueprint slots
    for base in base_slots:
        w_id = base.employee_id
        is_on_leave = w_id in approved_leave_worker_ids
        replacement = replacements_by_orig_worker.get(w_id)
        cancellation = cancellations_by_worker.get(w_id)

        if cancellation is not None:
            # Replaced/cancelled base worker
            resolved.append(
                ResolvedOperationalCellWorker(
                    employee_id=w_id,
                    assigned_hours=base.assigned_hours,
                    sequence=base.sequence,
                    display_type="REMOVED",
                    opacity_class="removed",
                    original_employee_id=None,
                    shift_id=cancellation.id,
                    reason=cancellation.override_reason or "Base Shift Removed",
                    is_public_holiday=is_public_holiday,
                    is_rest_day=False,
                    tags=["Removed", "Cancelled Base Shift"],
                )
            )
        elif replacement is not None:
            # Replaced by an operational override!
            rep_off = is_same_weekday(off_days.get(replacement.employee_id), dow)
            tags = ["Cover Replacement"]
            if is_public_holiday:
                tags.append("Holiday Overtime")
            if rep_off:
                tags.append("Rest Day Overtime")

            resolved.append(
                ResolvedOperationalCellWorker(
                    employee_id=replacement.employee_id,
                    assigned_hours=replacement.assigned_hours,
                    sequence=replacement.sequence,
                    display_type="OVERRIDE",
                    opacity_class="solid",
                    original_employee_id=w_id,
                    shift_id=replacement.id,
                    reason=replacement.override_reason or "Leave Cover",
                    is_public_holiday=is_public_holiday,
                    is_rest_day=rep_off,
                    tags=tags,
                )
            )
        elif is_on_leave:
            # Worker is on leave and NOT replaced -> TO_BE_COVERED
            resolved.append(
                ResolvedOperationalCellWorker(
                    employee_id=w_id,
                    assigned_hours=base.assigned_hours,
                    sequence=base.sequence,
                    display_type="TO_BE_COVERED",
                    opacity_class="warning",
                    original_employee_id=w_id,
                    shift_id=None,
                    reason="Approved Leave - Cover Required",
                    is_public_holiday=is_public_holiday,
                    is_rest_day=False,
                    tags=["Leave Gap", "Needs Cover"],
                )
            )
        else:
            # Normal base blueprint worker present
            w_off = is_same_weekday(off_days.get(w_id), dow)
            tags = ["Base Plan"]
            if is_public_holiday:
                tags.append("Holiday Overtime")
            if w_off:
                tags.append("Rest Day Overtime")

            resolved.append(
                ResolvedOperationalCellWorker(
                    employee_id=w_id,
                    assigned_hours=base.assigned_hours,
                    sequence=base.sequence,
                    display_type="BLUEPRINT",
                    opacity_class="muted",
                    original_employee_id=None,
                    shift_id=None,
                    reason=None,
                    is_public_holiday=is_public_holiday,
                    is_rest_day=w_off,
                    tags=tags,
                )
            )

    # 2. Add direct operational shifts (those not replacing a specific base slot)
    for direct in direct_shifts:
        # Check if already handled
        if direct.employee_id in [r.employee_id for r in resolved]:
            continue

        dir_off = is_same_weekday(off_days.get(direct.employee_id), dow)
        tags = ["Operational Shift"]
        if is_public_holiday:
            tags.append("Holiday Overtime")
        if dir_off:
            tags.append("Rest Day Overtime")

        resolved.append(
            ResolvedOperationalCellWorker(
                employee_id=direct.employee_id,
                assigned_hours=direct.assigned_hours,
                sequence=direct.sequence,
                display_type="DIRECT",
                opacity_class="solid",
                original_employee_id=None,
                shift_id=direct.id,
                reason=direct.override_reason,
                is_public_holiday=is_public_holiday,
                is_rest_day=dir_off,
                tags=tags,
            )
        )

    return resolved
