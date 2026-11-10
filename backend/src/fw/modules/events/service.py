from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import and_, or_, outerjoin, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.modules.events.models import EmployeeLastPosition, LiveLocationAccessLog, MobileEventLog
from fw.modules.events.schemas import (
    EventBatchRequest,
    EventResultItem,
    EventStatus,
    LivePositionItem,
    LivePositionsResponse,
    RejectReason,
)
from fw.modules.jobs import Worksite
from fw.modules.org import Employee, EmployeeReportingLine, Group, Zone
from fw.modules.settings import SettingsService

logger = structlog.get_logger(__name__)


class EventsService:
    """Ingestion, validation, and synchronous enrichment pipeline for mobile location events."""

    @staticmethod
    async def ingest_batch(
        session: AsyncSession,
        employee_id: UUID,
        device_id: UUID,
        batch: EventBatchRequest,
    ) -> list[EventResultItem]:
        now = datetime.now(UTC)
        results: list[EventResultItem] = []
        accepted_event_ids: list[UUID] = []

        # Find employee country for work_date timezone resolution
        emp_q = select(Employee.country).where(Employee.id == employee_id)
        emp_res = await session.execute(emp_q)
        country = emp_res.scalar_one_or_none() or "AE"
        tz = ZoneInfo("Asia/Dubai" if country.upper() == "AE" else "Asia/Riyadh")

        # Find existing event IDs in database for duplicate detection
        incoming_ids = [e.event_id for e in batch.events]
        existing_query = select(MobileEventLog.event_id).where(
            MobileEventLog.event_id.in_(incoming_ids)
        )
        res = await session.execute(existing_query)
        existing_ids = set(res.scalars().all())

        affected_work_dates: set = set()

        for item in batch.events:
            # 1. Duplicate check (Idempotent replay)
            if item.event_id in existing_ids:
                results.append(
                    EventResultItem(
                        event_id=item.event_id,
                        status=EventStatus.DUPLICATE,
                    )
                )
                continue

            # 2. Timestamp checks
            if item.event_timestamp_utc > now + timedelta(minutes=5):
                results.append(
                    EventResultItem(
                        event_id=item.event_id,
                        status=EventStatus.REJECTED,
                        reason=RejectReason.TIMESTAMP_IN_FUTURE,
                    )
                )
                continue

            if item.event_timestamp_utc < now - timedelta(days=7):
                results.append(
                    EventResultItem(
                        event_id=item.event_id,
                        status=EventStatus.REJECTED,
                        reason=RejectReason.TIMESTAMP_TOO_OLD,
                    )
                )
                continue

            # 3. Coordinate validation
            if item.event_type.value in ("ENTRY", "EXIT", "PING"):
                if (
                    item.latitude is None
                    or item.longitude is None
                    or not (-90.0 <= float(item.latitude) <= 90.0)
                    or not (-180.0 <= float(item.longitude) <= 180.0)
                ):
                    results.append(
                        EventResultItem(
                            event_id=item.event_id,
                            status=EventStatus.REJECTED,
                            reason=RejectReason.INVALID_COORDINATES,
                        )
                    )
                    continue

            # Valid event -> Insert immutable fact into mobile_event_logs
            geom_wkt = None
            if item.latitude is not None and item.longitude is not None:
                geom_wkt = f"SRID=4326;POINT({float(item.longitude)} {float(item.latitude)})"

            log_entry = MobileEventLog(
                event_id=item.event_id,
                employee_id=employee_id,
                device_id=device_id,
                job_id=item.job_id,
                job_item_id=item.job_item_id,
                accommodation_id=item.accommodation_id,
                event_type=item.event_type.value,
                event_timestamp_utc=item.event_timestamp_utc,
                location_captured_at_utc=item.location_captured_at_utc,
                latitude=item.latitude,
                longitude=item.longitude,
                geom=geom_wkt,
                accuracy_meters=item.accuracy_meters,
                is_mock_location=item.is_mock_location,
                sequence_number=item.sequence_number,
                device_clock_utc=batch.device_clock_utc,
                server_received_at=now,
                is_processed=False,
                raw_payload=item.model_dump(mode="json"),
                batch_id=batch.batch_id,
                processing_status="ACCEPTED",
                flags=[],
            )
            session.add(log_entry)
            existing_ids.add(item.event_id)
            accepted_event_ids.append(item.event_id)

            # Determine work_date in site local time zone
            local_date = item.event_timestamp_utc.astimezone(tz).date()
            affected_work_dates.add(local_date)

            results.append(
                EventResultItem(
                    event_id=item.event_id,
                    status=EventStatus.ACCEPTED,
                )
            )

        await session.flush()

        # Publish EventsIngested domain event for attendance enrichment & calculation
        if accepted_event_ids:
            from fw.core.events import EventsIngested, event_bus

            await event_bus.publish(
                EventsIngested(
                    employee_id=employee_id,
                    event_ids=accepted_event_ids,
                    affected_work_dates=list(affected_work_dates),
                ),
                session=session,
            )

        return results

    @staticmethod
    async def log_live_access(
        session: AsyncSession,
        user_id: UUID,
        access_type: str,
        filters: dict[str, Any],
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> LiveLocationAccessLog:
        """Record a live location access entry in live_location_access_logs."""
        log = LiveLocationAccessLog(
            user_id=user_id,
            access_type=access_type,
            filters=filters,
            client_ip=client_ip,
            user_agent=user_agent,
            created_at=datetime.now(UTC),
        )
        session.add(log)
        await session.flush()
        return log

    @staticmethod
    async def get_live_positions(
        session: AsyncSession,
        user: Any,
        scoped_employee_ids: set[UUID] | None,
        scheduled_employee_ids: set[UUID],
        today_assignments_by_emp: dict[UUID, list[dict[str, Any]]],
        supervisor_id: UUID | None = None,
        group_id: UUID | None = None,
        state_filter: str | None = None,
        as_of: datetime | None = None,
    ) -> LivePositionsResponse:
        """Fetch real-time last known positions with calculated live state."""
        now = as_of or datetime.now(UTC)

        # 1. Resolve live active window minutes setting
        window_minutes = await SettingsService.get_setting(
            session=session,
            key="live_active_window_minutes",
            default=15,
        )
        try:
            window_minutes_val = int(window_minutes) if window_minutes else 15
        except (ValueError, TypeError):
            window_minutes_val = 15
        active_cutoff = now - timedelta(minutes=window_minutes_val)

        # 2. Query active employees within scope
        emp_query = (
            select(
                Employee,
                EmployeeLastPosition,
                Worksite.job_name.label("server_site_name"),
            )
            .outerjoin(EmployeeLastPosition, Employee.id == EmployeeLastPosition.employee_id)
            .outerjoin(Worksite, EmployeeLastPosition.server_site_id == Worksite.id)
            .where(Employee.is_active.is_(True))
        )

        if user.role != "ADMIN":
            if scoped_employee_ids is not None:
                emp_query = emp_query.where(Employee.id.in_(scoped_employee_ids))
            elif user.employee_id:
                emp_query = emp_query.where(Employee.id == user.employee_id)
            else:
                emp_query = emp_query.where(Employee.id.in_([]))

        rows = (await session.execute(emp_query)).all()

        # Build supervisor lookup for these employees
        emp_ids = [r[0].id for r in rows]
        sup_lookup: dict[UUID, tuple[UUID, str]] = {}
        if emp_ids:
            sup_stmt = (
                select(
                    EmployeeReportingLine.employee_id,
                    EmployeeReportingLine.manager_id,
                    Employee.name,
                )
                .join(Employee, EmployeeReportingLine.manager_id == Employee.id)
                .where(
                    EmployeeReportingLine.employee_id.in_(emp_ids),
                    EmployeeReportingLine.relationship == "SUPERVISOR",
                )
            )
            sup_rows = (await session.execute(sup_stmt)).all()
            for s_emp_id, m_id, m_name in sup_rows:
                sup_lookup[s_emp_id] = (m_id, m_name)

        items: list[LivePositionItem] = []
        active_count = 0
        offline_count = 0
        disabled_count = 0
        not_scheduled_count = 0

        for emp, pos, site_name in rows:
            sup_info = sup_lookup.get(emp.id)
            sup_id = sup_info[0] if sup_info else None
            sup_name = sup_info[1] if sup_info else None

            # Filter by supervisor_id if requested
            if supervisor_id and sup_id != supervisor_id:
                continue

            assignments = today_assignments_by_emp.get(emp.id, [])
            group_id_val = assignments[0].get("group_id") if assignments else None
            group_name = assignments[0].get("group_name") if assignments else None
            zone_id_val = assignments[0].get("zone_id") if assignments else None
            zone_name = assignments[0].get("zone_name") if assignments else None

            if group_id and group_id_val != group_id:
                continue

            has_sched = emp.id in scheduled_employee_ids

            # If worker has no position ever and no schedule today, omit from live map
            if pos is None and not has_sched:
                continue

            # Determine live state
            if pos is None:
                # Scheduled today but no events received yet
                live_state = "NO_RECENT_SIGNAL"
                lat = None
                lon = None
                acc = None
                ev_type = "UNKNOWN"
                ev_time = now
                recv_time = now
                last_contact = now
                age_sec = -1
                contact_age_sec = -1
                tracking_en = True
                verdict = None
                server_site = None
            else:
                lat = float(pos.latitude) if pos.latitude is not None else None
                lon = float(pos.longitude) if pos.longitude is not None else None
                acc = pos.accuracy_meters
                ev_type = pos.event_type
                ev_time = pos.event_timestamp_utc
                recv_time = pos.received_at_utc
                last_contact = pos.last_contact_at
                age_sec = max(0, int((now - ev_time).total_seconds()))
                contact_age_sec = max(0, int((now - last_contact).total_seconds()))
                tracking_en = pos.tracking_enabled
                verdict = pos.server_verdict
                server_site = pos.server_site_id

                if not tracking_en or ev_type.upper() == "LOCATION_DISABLED":
                    live_state = "LOCATION_DISABLED"
                elif recv_time >= active_cutoff:
                    live_state = "ACTIVE" if has_sched else "NOT_SCHEDULED"
                else:
                    live_state = "NO_RECENT_SIGNAL" if has_sched else "NOT_SCHEDULED"

            # Tally counts
            if live_state == "ACTIVE":
                active_count += 1
            elif live_state in ("NO_RECENT_SIGNAL", "OFFLINE"):
                offline_count += 1
            elif live_state == "LOCATION_DISABLED":
                disabled_count += 1
            elif live_state == "NOT_SCHEDULED":
                not_scheduled_count += 1

            # Check state_filter
            if state_filter:
                sf = state_filter.upper()
                if sf == "ACTIVE" and live_state != "ACTIVE":
                    continue
                if sf in ("OFFLINE", "NO_RECENT_SIGNAL") and live_state not in ("NO_RECENT_SIGNAL", "OFFLINE"):
                    continue
                if sf in ("DISABLED", "LOCATION_DISABLED") and live_state != "LOCATION_DISABLED":
                    continue
                if sf == "NOT_SCHEDULED" and live_state != "NOT_SCHEDULED":
                    continue

            assignments = today_assignments_by_emp.get(emp.id, [])

            items.append(
                LivePositionItem(
                    employee_id=emp.id,
                    tally_id=emp.tally_id,
                    name=emp.name,
                    role=emp.role,
                    supervisor_id=sup_id,
                    supervisor_name=sup_name,
                    group_id=group_id_val,
                    group_name=group_name,
                    zone_id=zone_id_val,
                    zone_name=zone_name,
                    latitude=lat,
                    longitude=lon,
                    accuracy_meters=acc,
                    event_type=ev_type,
                    event_timestamp_utc=ev_time,
                    received_at_utc=recv_time,
                    last_contact_at=last_contact,
                    age_seconds=age_sec,
                    contact_age_seconds=contact_age_sec,
                    tracking_enabled=tracking_en,
                    server_verdict=verdict,
                    server_site_id=server_site,
                    server_site_name=site_name,
                    live_state=live_state,
                    has_schedule_today=has_sched,
                    today_assignments=assignments,
                )
            )

        return LivePositionsResponse(
            items=items,
            active_count=active_count,
            offline_count=offline_count,
            disabled_count=disabled_count,
            not_scheduled_count=not_scheduled_count,
            total_count=len(items),
            as_of=now,
        )

