from datetime import UTC, date, datetime
from uuid import UUID

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.events import (
    LocationDisabledRecorded,
    LocationEnabledRecorded,
    event_bus,
)
from fw.modules.events.live_publisher import live_position_broadcaster
from fw.modules.events.models import EmployeeLastPosition, MobileEventLog
from fw.modules.jobs import Worksite
from fw.modules.org import Accommodation
from fw.rules.attendance.verdicts import EventVerdictInput, evaluate_event_verdict


class EventEnrichmentService:
    """PostGIS spatial enrichment and verdict classification for raw mobile events."""

    @staticmethod
    async def enrich_events(
        session: AsyncSession,
        event_ids: list[UUID],
        employee_id: UUID,
        work_date: date,
        assigned_site_ids: set[UUID] | None = None,
        clock_skew_tolerance_s: int = 120,
        max_location_accuracy_m: float = 100.0,
    ) -> list[MobileEventLog]:
        if not event_ids:
            return []

        # 1. Use assigned worksite IDs if provided
        assigned_site_ids = assigned_site_ids or set()

        # 2. Fetch the events
        events_q = select(MobileEventLog).where(MobileEventLog.event_id.in_(event_ids))
        events_res = await session.execute(events_q)
        events = list(events_res.scalars().all())

        for ev in events:
            # Publish tracking state events for alert management
            if ev.event_type.upper() == "LOCATION_DISABLED":
                await event_bus.publish(
                    LocationDisabledRecorded(
                        employee_id=ev.employee_id,
                        event_id=ev.event_id,
                        captured_at=ev.event_timestamp_utc,
                    ),
                    session=session,
                )
            elif ev.event_type.upper() == "LOCATION_ENABLED":
                await event_bus.publish(
                    LocationEnabledRecorded(
                        employee_id=ev.employee_id,
                        event_id=ev.event_id,
                        captured_at=ev.event_timestamp_utc,
                    ),
                    session=session,
                )

            if ev.latitude is None or ev.longitude is None:
                # No fix available (e.g. initial LOCATION_DISABLED)
                verdict_res = evaluate_event_verdict(
                    EventVerdictInput(
                        event_id=ev.event_id,
                        event_type=ev.event_type,
                        event_timestamp_utc=ev.event_timestamp_utc,
                        device_clock_utc=ev.device_clock_utc,
                        server_received_at=ev.server_received_at,
                        latitude=None,
                        longitude=None,
                        accuracy_meters=ev.accuracy_meters,
                        is_mock_location=ev.is_mock_location,
                        is_inside_polygon=False,
                        distance_to_polygon_m=None,
                        matched_site_id=None,
                        matched_accommodation_id=None,
                        has_assigned_polygon=False,
                    ),
                    max_location_accuracy_m=max_location_accuracy_m,
                    clock_skew_tolerance_s=clock_skew_tolerance_s,
                )
                ev.server_verdict = verdict_res.verdict.value
                ev.flags = verdict_res.flags
                ev.device_clock_skew_s = verdict_res.device_clock_skew_s
                ev.processing_status = "ENRICHED"
                ev.is_processed = True
                continue

            pt_geom = func.ST_SetSRID(
                func.ST_MakePoint(float(ev.longitude), float(ev.latitude)), 4326
            )

            # Query candidate worksites covering the point or nearest worksite
            # A) Check worksites containing the point
            covering_sites_q = select(Worksite.id).where(
                Worksite.is_active.is_(True),
                Worksite.boundary.is_not(None),
                func.ST_Covers(Worksite.boundary, pt_geom),
            )
            cov_res = await session.execute(covering_sites_q)
            covering_site_ids = set(cov_res.scalars().all())

            matched_site_id: UUID | None = None
            is_inside_site = False

            if covering_site_ids:
                is_inside_site = True
                # Prioritize assigned worksite if among covering sites
                assigned_intersection = covering_site_ids.intersection(assigned_site_ids)
                if assigned_intersection:
                    matched_site_id = next(iter(assigned_intersection))
                else:
                    matched_site_id = next(iter(covering_site_ids))

            # B) Check accommodations containing the point
            covering_acc_q = select(Accommodation.id).where(
                Accommodation.is_active.is_(True),
                Accommodation.boundary.is_not(None),
                func.ST_Covers(Accommodation.boundary, pt_geom),
            )
            acc_res = await session.execute(covering_acc_q)
            covering_acc_ids = list(acc_res.scalars().all())
            matched_acc_id = covering_acc_ids[0] if covering_acc_ids else None
            is_inside_acc = matched_acc_id is not None

            # C) If not inside any polygon, resolve target polygon and distance
            distance_to_polygon_m: float | None = None
            if not is_inside_site and not is_inside_acc:
                # 1. If device reported accommodation_id, associate with accommodation
                if ev.accommodation_id is not None:
                    matched_acc_id = ev.accommodation_id
                    dist_q = select(
                        func.ST_Distance(
                            cast(pt_geom, Geography),
                            cast(Accommodation.boundary, Geography),
                        )
                    ).where(
                        Accommodation.id == ev.accommodation_id,
                        Accommodation.boundary.is_not(None),
                    )
                    dist_res = await session.execute(dist_q)
                    d_val = dist_res.scalar()
                    if d_val is not None:
                        distance_to_polygon_m = float(d_val)
                # 2. If device reported job_id (e.g. exit from site), associate with that site
                elif ev.job_id is not None:
                    matched_site_id = ev.job_id
                    dist_q = select(
                        func.ST_Distance(
                            cast(pt_geom, Geography),
                            cast(Worksite.boundary, Geography),
                        )
                    ).where(
                        Worksite.id == ev.job_id,
                        Worksite.boundary.is_not(None),
                    )
                    dist_res = await session.execute(dist_q)
                    d_val = dist_res.scalar()
                    if d_val is not None:
                        distance_to_polygon_m = float(d_val)
                # 3. If employee has assigned sites today, measure distance to nearest assigned site
                elif assigned_site_ids:
                    nearest_assigned_q = (
                        select(
                            Worksite.id,
                            func.ST_Distance(
                                cast(pt_geom, Geography),
                                cast(Worksite.boundary, Geography),
                            ).label("dist_m"),
                        )
                        .where(
                            Worksite.id.in_(assigned_site_ids),
                            Worksite.boundary.is_not(None),
                        )
                        .order_by("dist_m")
                        .limit(1)
                    )
                    nearest_res = await session.execute(nearest_assigned_q)
                    nearest_row = nearest_res.first()
                    if nearest_row is not None:
                        matched_site_id = nearest_row[0]
                        distance_to_polygon_m = float(nearest_row[1])
                # 4. Fallback to nearest active worksite
                else:
                    nearest_site_q = (
                        select(
                            Worksite.id,
                            func.ST_Distance(
                                cast(pt_geom, Geography),
                                cast(Worksite.boundary, Geography),
                            ).label("dist_m"),
                        )
                        .where(
                            Worksite.is_active.is_(True),
                            Worksite.boundary.is_not(None),
                        )
                        .order_by("dist_m")
                        .limit(1)
                    )
                    nearest_res = await session.execute(nearest_site_q)
                    nearest_row = nearest_res.first()
                    if nearest_row is not None:
                        matched_site_id = nearest_row[0]
                        distance_to_polygon_m = float(nearest_row[1])

            # Run verdict rule
            has_assigned = (matched_site_id in assigned_site_ids) if matched_site_id else False
            verdict_res = evaluate_event_verdict(
                EventVerdictInput(
                    event_id=ev.event_id,
                    event_type=ev.event_type,
                    event_timestamp_utc=ev.event_timestamp_utc,
                    device_clock_utc=ev.device_clock_utc,
                    server_received_at=ev.server_received_at,
                    latitude=float(ev.latitude) if ev.latitude is not None else None,
                    longitude=float(ev.longitude) if ev.longitude is not None else None,
                    accuracy_meters=ev.accuracy_meters,
                    is_mock_location=ev.is_mock_location,
                    is_inside_polygon=(is_inside_site or is_inside_acc),
                    distance_to_polygon_m=distance_to_polygon_m
                    if not (is_inside_site or is_inside_acc)
                    else 0.0,
                    matched_site_id=matched_site_id if matched_acc_id is None else None,
                    matched_accommodation_id=matched_acc_id,
                    has_assigned_polygon=has_assigned,
                ),
                max_location_accuracy_m=max_location_accuracy_m,
                clock_skew_tolerance_s=clock_skew_tolerance_s,
            )

            ev.server_site_id = verdict_res.server_site_id
            ev.server_accommodation_id = verdict_res.server_accommodation_id
            ev.server_verdict = verdict_res.verdict.value
            ev.distance_to_polygon_m = verdict_res.distance_to_polygon_m
            ev.flags = verdict_res.flags
            ev.device_clock_skew_s = verdict_res.device_clock_skew_s
            ev.processing_status = "ENRICHED"
            ev.is_processed = True

        # Upsert employee_last_position using the latest event in the batch
        if events:
            # Group by employee_id to find latest event per employee
            by_emp: dict[UUID, MobileEventLog] = {}
            for e in events:
                if e.employee_id not in by_emp or e.event_timestamp_utc > by_emp[e.employee_id].event_timestamp_utc:
                    by_emp[e.employee_id] = e
            for latest_e in by_emp.values():
                await EventEnrichmentService._update_last_position(session, latest_e)

        await session.flush()
        return events

    @staticmethod
    async def _update_last_position(session: AsyncSession, event: MobileEventLog) -> None:
        pos_q = select(EmployeeLastPosition).where(
            EmployeeLastPosition.employee_id == event.employee_id
        )
        pos_res = await session.execute(pos_q)
        pos = pos_res.scalar_one_or_none()

        tracking_enabled = event.event_type.upper() != "LOCATION_DISABLED"
        is_newer = False

        if pos is None:
            pos = EmployeeLastPosition(
                employee_id=event.employee_id,
                last_event_id=event.event_id,
                event_type=event.event_type,
                latitude=event.latitude,
                longitude=event.longitude,
                accuracy_meters=event.accuracy_meters,
                event_timestamp_utc=event.event_timestamp_utc,
                received_at_utc=event.server_received_at,
                server_verdict=event.server_verdict,
                server_site_id=event.server_site_id,
                tracking_enabled=tracking_enabled,
                last_contact_at=datetime.now(UTC),
            )
            session.add(pos)
            is_newer = True
        else:
            # Upsert position details ONLY if newer timestamp
            if event.event_timestamp_utc >= pos.event_timestamp_utc:
                pos.last_event_id = event.event_id
                pos.event_type = event.event_type
                pos.latitude = event.latitude
                pos.longitude = event.longitude
                pos.accuracy_meters = event.accuracy_meters
                pos.event_timestamp_utc = event.event_timestamp_utc
                pos.received_at_utc = event.server_received_at
                pos.server_verdict = event.server_verdict
                pos.server_site_id = event.server_site_id
                pos.tracking_enabled = tracking_enabled
                pos.last_contact_at = datetime.now(UTC)
                is_newer = True
            else:
                # Late upload: older location event does not overwrite coordinates, but confirms device contact
                pos.last_contact_at = datetime.now(UTC)

        # Broadcast update to connected live map streams and PostgreSQL NOTIFY
        if is_newer:
            payload = {
                "employee_id": str(pos.employee_id),
                "latitude": float(pos.latitude) if pos.latitude is not None else None,
                "longitude": float(pos.longitude) if pos.longitude is not None else None,
                "accuracy_meters": pos.accuracy_meters,
                "event_type": pos.event_type,
                "event_timestamp_utc": pos.event_timestamp_utc.isoformat(),
                "server_verdict": pos.server_verdict,
                "server_site_id": str(pos.server_site_id) if pos.server_site_id else None,
                "tracking_enabled": pos.tracking_enabled,
                "last_contact_at": pos.last_contact_at.isoformat(),
            }
            await live_position_broadcaster.broadcast_position_update(pos.employee_id, payload)
            try:
                # PostgreSQL NOTIFY (no-op if unsupported by engine in SQLite tests)
                await session.execute(
                    text(f"NOTIFY live_positions, '{pos.employee_id}'")
                )
            except Exception:
                pass

