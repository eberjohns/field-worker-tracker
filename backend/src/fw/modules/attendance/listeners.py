from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.events import EventsIngested, event_bus
from fw.modules.events import EventEnrichmentService
from fw.modules.scheduling.models import ScheduledWork


async def handle_events_ingested(event: EventsIngested, session: AsyncSession) -> None:
    """When raw mobile events are accepted, run PostGIS enrichment and attendance calculation."""
    if not event.employee_id or not event.event_ids:
        return

    from fw.modules.attendance.service import AttendanceService

    for w_date in event.affected_work_dates:
        # 1. Fetch assigned worksite IDs for the worker on this date
        assigned_q = select(ScheduledWork.worksite_id).where(
            ScheduledWork.employee_id == event.employee_id,
            ScheduledWork.work_date == w_date,
            ScheduledWork.status == "ACTIVE",
        )
        assigned_res = await session.execute(assigned_q)
        assigned_site_ids = set(assigned_res.scalars().all())

        # 2. Enrich events via PostGIS against worksite and accommodation boundaries
        await EventEnrichmentService.enrich_events(
            session=session,
            event_ids=event.event_ids,
            employee_id=event.employee_id,
            work_date=w_date,
            assigned_site_ids=assigned_site_ids,
        )

        # 3. Recalculate daily attendance
        await AttendanceService.recalculate_day(
            session=session,
            employee_id=event.employee_id,
            work_date=w_date,
            reason="NEW_EVENTS",
        )


_registered = False


def register_attendance_listeners() -> None:
    global _registered
    if not _registered:
        event_bus.subscribe_sync(EventsIngested, handle_events_ingested)
        _registered = True
