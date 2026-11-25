"""Template slots for one day that have no scheduled work yet (19 Nov meeting item 11).

The materialiser (ADR-032) turns Base Planner templates into scheduled work from *tomorrow*
onwards, so a template saved today, or a worker planned only in the Base Planner before the
materialiser existed, has no ``scheduled_work`` row for today. The phone already merges these
template slots into its schedule (sync snapshot). The Live Map and the dashboard read only
``scheduled_work`` and so showed such workers as "Not Scheduled".

The rule matches the phone's: an employee who has any ``scheduled_work`` row on the day (any
status) is planned by those rows, so templates are only consulted for employees with none.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.modules.jobs import JobItem, Worksite
from fw.modules.scheduling.models import BaseRosterEntry, BaseRosterTemplate, ScheduledWork
from fw.rules.scheduling.blueprint import is_entry_matching_date


@dataclass(frozen=True)
class TemplateSlot:
    employee_id: UUID
    worksite_id: UUID
    worksite_name: str | None
    group_id: UUID | None
    zone_id: UUID | None
    assigned_hours: Decimal


async def unmaterialised_template_slots(
    session: AsyncSession,
    day: date,
    employee_ids: set[UUID] | None = None,
) -> list[TemplateSlot]:
    """Active template slots on ``day`` for employees with no scheduled work that day."""
    stmt = (
        select(BaseRosterEntry, BaseRosterTemplate, Worksite)
        .join(BaseRosterTemplate, BaseRosterEntry.template_id == BaseRosterTemplate.id)
        .join(JobItem, BaseRosterTemplate.job_item_id == JobItem.id)
        .join(Worksite, JobItem.worksite_id == Worksite.id)
        .where(
            BaseRosterTemplate.is_active.is_(True),
            BaseRosterTemplate.start_date <= day,
            (BaseRosterTemplate.end_date.is_(None)) | (BaseRosterTemplate.end_date >= day),
            JobItem.is_active.is_(True),
            Worksite.is_active.is_(True),
            ~select(ScheduledWork.id)
            .where(
                ScheduledWork.employee_id == BaseRosterEntry.employee_id,
                ScheduledWork.work_date == day,
            )
            .exists(),
        )
        .order_by(BaseRosterEntry.sequence.asc())
    )
    if employee_ids is not None:
        if not employee_ids:
            return []
        stmt = stmt.where(BaseRosterEntry.employee_id.in_(employee_ids))
    rows = (await session.execute(stmt)).all()
    return [
        TemplateSlot(
            employee_id=entry.employee_id,
            worksite_id=ws.id,
            worksite_name=ws.job_name,
            group_id=ws.group_id,
            zone_id=ws.zone_id,
            assigned_hours=entry.assigned_hours,
        )
        for entry, _tmpl, ws in rows
        if is_entry_matching_date(entry.weekday_mask or "", day)
    ]
