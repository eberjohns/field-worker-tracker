from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.modules.events.models import MobileEventLog
from fw.modules.events.schemas import (
    EventBatchRequest,
    EventResultItem,
    EventStatus,
    RejectReason,
)
from fw.modules.org.models import Employee

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
