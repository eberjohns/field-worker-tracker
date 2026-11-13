import json
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid5

import structlog
from geoalchemy2.functions import ST_AsGeoJSON
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.events import (
    AccommodationBoundaryChanged,
    EmployeeProfileChanged,
    HolidayChanged,
    ScheduledWorkChanged,
    TimeRuleChanged,
    TransportRunChanged,
    WorksiteBoundaryChanged,
    event_bus,
)
from fw.modules.jobs import JobItem, Worksite
from fw.modules.org import Accommodation, Employee, EmployeeReportingLine
from fw.modules.scheduling import (
    BaseRosterEntry,
    BaseRosterTemplate,
    LeaveApprovedEvent,
    ScheduledWork,
)
from fw.modules.sync.geo import compute_geofence_circle
from fw.modules.sync.schemas import (
    AccommodationPayload,
    DayPlanPayload,
    DayPlanPlannedTimes,
    GeofenceCircle,
    JobItemSummary,
    JobPayload,
    ProfilePayload,
    ProfileSupervisor,
    ScheduleItemPayload,
    TransportDriverSyncPayload,
    TransportPassengerSyncPayload,
    TransportRunPayload,
    TransportStopSyncPayload,
)
from fw.modules.sync.service import (
    SyncService,
    _geometry_to_geojson,
    _subtract_minutes_from_time_str,
)
from fw.modules.transport import (
    TransportRun,
    TransportRunPassenger,
    TransportRunStop,
    Vehicle,
)
from fw.rules.scheduling import INT_TO_WEEKDAY

logger = structlog.get_logger(__name__)


async def handle_scheduled_work_changed(event: ScheduledWorkChanged, session: AsyncSession) -> None:
    """When schedule items change, record delta changes, update DayPlan, and flag runs."""
    now = datetime.now(UTC)
    today = now.date()
    window_end = today + timedelta(days=30)

    # Flag any active published transport runs on event.work_date containing these workers
    if event.work_date and event.employee_ids:
        trans_q = (
            select(TransportRun)
            .join(TransportRunPassenger, TransportRun.id == TransportRunPassenger.run_id)
            .where(
                TransportRun.run_date == event.work_date,
                TransportRun.status == "PUBLISHED",
                TransportRun.is_active.is_(True),
                TransportRunPassenger.employee_id.in_(event.employee_ids),
            )
        )
        t_res = await session.execute(trans_q)
        for tr in t_res.scalars().all():
            tr.needs_update = True

    for emp_id in event.employee_ids:
        # Query active scheduled work for this worker in the window
        sw_query = (
            select(ScheduledWork, JobItem, Worksite)
            .join(JobItem, ScheduledWork.job_item_id == JobItem.id)
            .join(Worksite, ScheduledWork.worksite_id == Worksite.id)
            .where(
                ScheduledWork.employee_id == emp_id,
                ScheduledWork.work_date >= today,
                ScheduledWork.work_date <= window_end,
            )
        )
        res = await session.execute(sw_query)
        rows = res.all()

        for sw, ji, ws in rows:
            is_urgent = (sw.work_date - today).days <= 1
            priority = 1 if is_urgent else 0

            # Job summary
            item_summary = JobItemSummary(
                staff_grade_description=ji.staff_grade_description,
                deployment_type=ji.deployment_type or "PERMANENT",
                required_staff_count=ji.required_staff_count or 1,
                hours_per_occurrence_per_staff=float(ji.hours_per_occurrence_per_staff or 9.0),
            )

            op = "DELETE" if sw.status == "CANCELLED" else "UPSERT"
            sch_payload = ScheduleItemPayload(
                scheduled_work_id=sw.id,
                work_date=sw.work_date.isoformat(),
                sequence=sw.sequence,
                assigned_hours=float(sw.assigned_hours or 0.0),
                status=sw.status,
                job_id=sw.worksite_id,
                job_item_id=sw.job_item_id,
                sub_item_code=ji.sub_item_code,
                occurrence_id=sw.occurrence_id,
                job_item_summary=item_summary,
                source=sw.source or "PLANNED",
                is_reassignment=bool(sw.reassignment_request_id is not None),
            )

            await SyncService.write_sync_change(
                session=session,
                employee_id=emp_id,
                entity_type="SCHEDULE_ITEM",
                entity_id=str(sw.id),
                entity_version=sw.version or 1,
                op=op,
                payload=sch_payload.model_dump(mode="json") if op == "UPSERT" else None,
                priority=priority,
            )

            # Also ensure JOB entity is synced
            boundary_geojson = _geometry_to_geojson(ws.boundary)
            circle = compute_geofence_circle(boundary_geojson, extra_radius_m=300.0)
            job_payload = JobPayload(
                job_id=ws.id,
                job_number=ws.job_number,
                job_name=ws.job_name,
                boundary=boundary_geojson,
                geofence_circle=GeofenceCircle(**circle) if circle else None,
                boundary_missing=(boundary_geojson is None),
            )
            await SyncService.write_sync_change(
                session=session,
                employee_id=emp_id,
                entity_type="JOB",
                entity_id=str(ws.id),
                entity_version=ws.version or 1,
                op="UPSERT",
                payload=job_payload.model_dump(mode="json"),
                priority=priority,
            )

            # Update DAY_PLAN for that work date
            day_str = sw.work_date.isoformat()
            alarm_time = _subtract_minutes_from_time_str("05:00", 30)
            day_payload = DayPlanPayload(
                work_date=day_str,
                status="WORKING" if sw.status == "ACTIVE" else "FREE",
                marker=None,
                planned=DayPlanPlannedTimes(
                    accommodation_start="05:00",
                    first_site_start="06:00",
                    break_minutes=30,
                    last_site_end="15:30",
                    accommodation_end="17:00",
                )
                if sw.status == "ACTIVE"
                else None,
                standard_hours=8,
                alarm_time=alarm_time if sw.status == "ACTIVE" else None,
            )
            await SyncService.write_sync_change(
                session=session,
                employee_id=emp_id,
                entity_type="DAY_PLAN",
                entity_id=day_str,
                entity_version=1,
                op="UPSERT",
                payload=day_payload.model_dump(mode="json"),
                priority=priority,
            )

        # Also merge Base Blueprint entries for dates without an operational shift
        bp_query = (
            select(BaseRosterEntry, BaseRosterTemplate, JobItem, Worksite)
            .join(BaseRosterTemplate, BaseRosterEntry.template_id == BaseRosterTemplate.id)
            .join(JobItem, BaseRosterTemplate.job_item_id == JobItem.id)
            .join(Worksite, JobItem.worksite_id == Worksite.id)
            .where(
                BaseRosterEntry.employee_id == emp_id,
                BaseRosterTemplate.is_active.is_(True),
                JobItem.is_active.is_(True),
                Worksite.is_active.is_(True),
            )
        )
        bp_rows = (await session.execute(bp_query)).all()
        covered_dates = {sw.work_date for sw, _, _ in rows}

        cur_check = today
        while cur_check <= window_end:
            if cur_check not in covered_dates:
                dow = INT_TO_WEEKDAY[cur_check.weekday()]
                for entry, tmpl, ji, ws in bp_rows:
                    if tmpl.start_date and tmpl.start_date > cur_check:
                        continue
                    if tmpl.end_date and tmpl.end_date < cur_check:
                        continue

                    mask = (entry.weekday_mask or "").upper()
                    matches_dow = mask in ("ALL", dow)
                    if not matches_dow and "_" in mask:
                        parts = mask.split("_")
                        if len(parts) == 2 and parts[1] == dow:
                            day_of_month = cur_check.day
                            week_num = (day_of_month - 1) // 7 + 1
                            if parts[0] == f"W{week_num}":
                                matches_dow = True

                    if matches_dow:
                        bp_item_id = uuid5(
                            UUID("00000000-0000-0000-0000-000000000001"),
                            f"bp_{entry.id}_{cur_check.isoformat()}",
                        )
                        is_urgent = (cur_check - today).days <= 1
                        priority = 1 if is_urgent else 0

                        item_summary = JobItemSummary(
                            staff_grade_description=ji.staff_grade_description,
                            deployment_type=ji.deployment_type or "PERMANENT",
                            required_staff_count=ji.required_staff_count or 1,
                            hours_per_occurrence_per_staff=float(
                                ji.hours_per_occurrence_per_staff or 9.0
                            ),
                        )
                        sch_payload = ScheduleItemPayload(
                            scheduled_work_id=bp_item_id,
                            work_date=cur_check.isoformat(),
                            sequence=entry.sequence or 1,
                            assigned_hours=float(entry.assigned_hours or 0.0),
                            status="ACTIVE",
                            job_id=ws.id,
                            job_item_id=ji.id,
                            sub_item_code=ji.sub_item_code,
                            occurrence_id=None,
                            job_item_summary=item_summary,
                            source="PLANNED",
                            is_reassignment=False,
                        )
                        await SyncService.write_sync_change(
                            session=session,
                            employee_id=emp_id,
                            entity_type="SCHEDULE_ITEM",
                            entity_id=str(bp_item_id),
                            entity_version=1,
                            op="UPSERT",
                            payload=sch_payload.model_dump(mode="json"),
                            priority=priority,
                        )

                        boundary_geojson = _geometry_to_geojson(ws.boundary)
                        circle = compute_geofence_circle(boundary_geojson, extra_radius_m=300.0)
                        job_payload = JobPayload(
                            job_id=ws.id,
                            job_number=ws.job_number,
                            job_name=ws.job_name,
                            boundary=boundary_geojson,
                            geofence_circle=GeofenceCircle(**circle) if circle else None,
                            boundary_missing=(boundary_geojson is None),
                        )
                        await SyncService.write_sync_change(
                            session=session,
                            employee_id=emp_id,
                            entity_type="JOB",
                            entity_id=str(ws.id),
                            entity_version=ws.version or 1,
                            op="UPSERT",
                            payload=job_payload.model_dump(mode="json"),
                            priority=priority,
                        )

                        day_str = cur_check.isoformat()
                        alarm_time = _subtract_minutes_from_time_str("05:00", 30)
                        day_payload = DayPlanPayload(
                            work_date=day_str,
                            status="WORKING",
                            marker=None,
                            planned=DayPlanPlannedTimes(
                                accommodation_start="05:00",
                                first_site_start="06:00",
                                break_minutes=30,
                                last_site_end="15:30",
                                accommodation_end="17:00",
                            ),
                            standard_hours=8,
                            alarm_time=alarm_time,
                        )
                        await SyncService.write_sync_change(
                            session=session,
                            employee_id=emp_id,
                            entity_type="DAY_PLAN",
                            entity_id=day_str,
                            entity_version=1,
                            op="UPSERT",
                            payload=day_payload.model_dump(mode="json"),
                            priority=priority,
                        )
            cur_check += timedelta(days=1)


async def handle_holiday_changed(event: HolidayChanged, session: AsyncSession) -> None:
    """When a public holiday is created or updated, update DayPlan for affected workers."""
    now = datetime.now(UTC)
    today = now.date()

    # Query active employees in this country
    emp_query = select(Employee).where(
        Employee.country == event.country,
        Employee.is_active.is_(True),
    )
    res = await session.execute(emp_query)
    employees = list(res.scalars().all())

    target_date = event.holiday_date if isinstance(event.holiday_date, date) else today
    is_urgent = (target_date - today).days <= 1
    priority = 1 if is_urgent else 0
    day_str = target_date.isoformat()

    day_payload = DayPlanPayload(
        work_date=day_str,
        status="SKIPPED",
        marker="PUBLIC_HOLIDAY",
        planned=None,
        standard_hours=8,
        alarm_time=None,
    )

    for emp in employees:
        await SyncService.write_sync_change(
            session=session,
            employee_id=emp.id,
            entity_type="DAY_PLAN",
            entity_id=day_str,
            entity_version=1,
            op="UPSERT",
            payload=day_payload.model_dump(mode="json"),
            priority=priority,
        )


async def handle_time_rule_changed(event: TimeRuleChanged, session: AsyncSession) -> None:
    """When time rules or seasonal hours change, update DAY_PLAN for active workers."""
    now = datetime.now(UTC)
    today = now.date()
    window_end = today + timedelta(days=30)

    emp_query = select(Employee).where(
        Employee.country == event.country,
        Employee.is_active.is_(True),
    )
    res = await session.execute(emp_query)
    employees = list(res.scalars().all())

    for emp in employees:
        # Update day plans in window
        cur = today
        while cur <= window_end:
            is_urgent = (cur - today).days <= 1
            alarm_time = _subtract_minutes_from_time_str("05:00", 30)
            day_payload = DayPlanPayload(
                work_date=cur.isoformat(),
                status="WORKING",
                marker=None,
                planned=DayPlanPlannedTimes(
                    accommodation_start="05:00",
                    first_site_start="06:00",
                    break_minutes=30,
                    last_site_end="15:30",
                    accommodation_end="17:00",
                ),
                standard_hours=8,
                alarm_time=alarm_time,
            )
            await SyncService.write_sync_change(
                session=session,
                employee_id=emp.id,
                entity_type="DAY_PLAN",
                entity_id=cur.isoformat(),
                entity_version=1,
                op="UPSERT",
                payload=day_payload.model_dump(mode="json"),
                priority=1 if is_urgent else 0,
            )
            cur += timedelta(days=1)


async def handle_worksite_boundary_changed(
    event: WorksiteBoundaryChanged, session: AsyncSession
) -> None:
    """Fan-out worksite boundary updates to all scheduled workers."""
    if not event.worksite_id:
        return

    now = datetime.now(UTC)
    today = now.date()
    window_end = today + timedelta(days=30)

    # Find worksite with boundary GeoJSON explicitly loaded
    ws_query = select(
        Worksite,
        ST_AsGeoJSON(Worksite.boundary).label("boundary_geojson"),
    ).where(Worksite.id == event.worksite_id)
    ws_res = await session.execute(ws_query)
    ws_row = ws_res.first()
    if not ws_row:
        return
    ws, boundary_json_str = ws_row
    boundary_geojson = json.loads(boundary_json_str) if boundary_json_str else None

    circle = compute_geofence_circle(boundary_geojson, extra_radius_m=300.0)
    job_payload = JobPayload(
        job_id=ws.id,
        job_number=ws.job_number,
        job_name=ws.job_name,
        boundary=boundary_geojson,
        geofence_circle=GeofenceCircle(**circle) if circle else None,
        boundary_missing=(boundary_geojson is None),
    )

    # Find affected workers scheduled at this site in the next 30 days
    workers_query = (
        select(ScheduledWork.employee_id)
        .where(
            ScheduledWork.worksite_id == event.worksite_id,
            ScheduledWork.work_date >= today,
            ScheduledWork.work_date <= window_end,
            ScheduledWork.status == "ACTIVE",
        )
        .distinct()
    )
    w_res = await session.execute(workers_query)
    employee_ids = list(w_res.scalars().all())

    for emp_id in employee_ids:
        await SyncService.write_sync_change(
            session=session,
            employee_id=emp_id,
            entity_type="JOB",
            entity_id=str(ws.id),
            entity_version=ws.version or 1,
            op="UPSERT",
            payload=job_payload.model_dump(mode="json"),
            priority=1,
        )


async def handle_leave_approved(event: LeaveApprovedEvent, session: AsyncSession) -> None:
    """When leave is approved, update DAY_PLAN for the worker."""
    cur = event.date_from
    today = datetime.now(UTC).date()
    while cur <= event.date_to:
        day_str = cur.isoformat()
        is_urgent = (cur - today).days <= 1
        day_payload = DayPlanPayload(
            work_date=day_str,
            status="LEAVE",
            marker=None,
            planned=None,
            standard_hours=8,
            alarm_time=None,
        )
        await SyncService.write_sync_change(
            session=session,
            employee_id=event.employee_id,
            entity_type="DAY_PLAN",
            entity_id=day_str,
            entity_version=1,
            op="UPSERT",
            payload=day_payload.model_dump(mode="json"),
            priority=1 if is_urgent else 0,
        )
        cur += timedelta(days=1)


async def handle_employee_profile_changed(
    event: EmployeeProfileChanged, session: AsyncSession
) -> None:
    """When a worker profile, accommodation, or supervisor changes, write sync changes."""
    if not event.employee_id:
        return

    employee = await session.get(Employee, event.employee_id)
    if not employee or not employee.is_active:
        return

    # Query supervisor
    rep_query = (
        select(Employee)
        .join(EmployeeReportingLine, EmployeeReportingLine.manager_id == Employee.id)
        .where(
            EmployeeReportingLine.employee_id == employee.id,
            EmployeeReportingLine.relationship == "SUPERVISOR",
        )
    )
    rep_res = await session.execute(rep_query)
    supervisor_emp = rep_res.scalar_one_or_none()
    supervisor_payload = None
    if supervisor_emp:
        supervisor_payload = ProfileSupervisor(
            name=supervisor_emp.name,
            phone=supervisor_emp.phone,
        )

    profile_payload = ProfilePayload(
        employee_id=employee.id,
        tally_id=employee.tally_id,
        name=employee.name,
        role=employee.role or "WORKER",
        staff_grade_description=employee.staff_grade_description,
        weekly_off_day=employee.weekly_off_day or "FRIDAY",
        is_driver=employee.is_driver or False,
        supervisor=supervisor_payload,
        accommodation_id=employee.accommodation_id,
    )

    await SyncService.write_sync_change(
        session=session,
        employee_id=employee.id,
        entity_type="PROFILE",
        entity_id=str(employee.id),
        entity_version=employee.version or 1,
        op="UPSERT",
        payload=profile_payload.model_dump(mode="json"),
        priority=1,
    )

    # If accommodation is assigned, sync accommodation details and polygon
    if employee.accommodation_id:
        acc = await session.get(Accommodation, employee.accommodation_id)
        if acc:
            boundary_geojson = _geometry_to_geojson(acc.boundary)
            circle = compute_geofence_circle(boundary_geojson, extra_radius_m=300.0)
            acc_payload = AccommodationPayload(
                accommodation_id=acc.id,
                name=acc.name,
                address=acc.address,
                boundary=boundary_geojson,
                geofence_circle=GeofenceCircle(**circle) if circle else None,
            )
            await SyncService.write_sync_change(
                session=session,
                employee_id=employee.id,
                entity_type="ACCOMMODATION",
                entity_id=str(acc.id),
                entity_version=acc.version or 1,
                op="UPSERT",
                payload=acc_payload.model_dump(mode="json"),
                priority=1,
            )


async def handle_accommodation_boundary_changed(
    event: AccommodationBoundaryChanged, session: AsyncSession
) -> None:
    """When an accommodation camp boundary is updated, fan-out to all assigned workers."""
    if not event.accommodation_id:
        return

    query = select(
        Accommodation,
        ST_AsGeoJSON(Accommodation.boundary).label("boundary_geojson"),
    ).where(Accommodation.id == event.accommodation_id)
    res = await session.execute(query)
    row = res.first()
    if not row:
        return

    acc, boundary_json_str = row
    boundary_geojson = json.loads(boundary_json_str) if boundary_json_str else None
    circle = compute_geofence_circle(boundary_geojson, extra_radius_m=300.0)
    acc_payload = AccommodationPayload(
        accommodation_id=acc.id,
        name=acc.name,
        address=acc.address,
        boundary=boundary_geojson,
        geofence_circle=GeofenceCircle(**circle) if circle else None,
    )

    # Find all active workers living at this accommodation
    w_query = select(Employee.id).where(
        Employee.accommodation_id == event.accommodation_id,
        Employee.is_active == True,  # noqa: E712
    )
    res = await session.execute(w_query)
    employee_ids = list(res.scalars().all())

    for emp_id in employee_ids:
        await SyncService.write_sync_change(
            session=session,
            employee_id=emp_id,
            entity_type="ACCOMMODATION",
            entity_id=str(acc.id),
            entity_version=acc.version or 1,
            op="UPSERT",
            payload=acc_payload.model_dump(mode="json"),
            priority=1,
        )


async def handle_transport_run_changed(event: TransportRunChanged, session: AsyncSession) -> None:
    """When a transport run is published, modified, or cancelled, record delta sync changes."""
    if not event.run_id:
        return

    if event.op == "DELETE":
        # Delete tombstone to driver
        if event.driver_id:
            await SyncService.write_sync_change(
                session=session,
                employee_id=event.driver_id,
                entity_type="TRANSPORT_RUN",
                entity_id=str(event.run_id),
                entity_version=1,
                op="DELETE",
                payload=None,
                priority=1,
            )
        # Delete tombstone to all affected passengers
        for emp_id in event.affected_employee_ids:
            await SyncService.write_sync_change(
                session=session,
                employee_id=emp_id,
                entity_type="TRANSPORT_RUN",
                entity_id=str(event.run_id),
                entity_version=1,
                op="DELETE",
                payload=None,
                priority=1,
            )
        return

    # OP == "UPSERT"
    run = await session.get(TransportRun, event.run_id)
    if not run or not run.is_active or run.status != "PUBLISHED":
        return

    driver_emp = await session.get(Employee, run.driver_id)
    driver_payload = TransportDriverSyncPayload(
        name=driver_emp.name if driver_emp else "Driver",
        phone=driver_emp.phone if driver_emp else None,
    )
    vehicle = await session.get(Vehicle, run.vehicle_id) if run.vehicle_id else None
    vehicle_label = vehicle.label if vehicle else None

    # Fetch stops
    stops_q = (
        select(TransportRunStop)
        .where(TransportRunStop.run_id == run.id)
        .order_by(TransportRunStop.sequence.asc())
    )
    stops_res = await session.execute(stops_q)
    run_stops = stops_res.scalars().all()

    # Build driver full payload and passenger-specific payloads
    driver_stops_payload = []
    passenger_to_stop: dict[UUID, TransportStopSyncPayload] = {}

    for st in run_stops:
        pass_q = select(TransportRunPassenger).where(TransportRunPassenger.stop_id == st.id)
        pass_res = await session.execute(pass_q)
        stop_passengers = pass_res.scalars().all()

        pass_payloads = []
        for sp in stop_passengers:
            p_emp = await session.get(Employee, sp.employee_id)
            if p_emp:
                pass_payloads.append(
                    TransportPassengerSyncPayload(name=p_emp.name, tally_id=p_emp.tally_id)
                )

        stop_name = "Stop"
        if st.worksite_id:
            ws_obj = await session.get(Worksite, st.worksite_id)
            if ws_obj:
                stop_name = ws_obj.job_name
        elif st.accommodation_id:
            acc_obj = await session.get(Accommodation, st.accommodation_id)
            if acc_obj:
                stop_name = acc_obj.name

        st_payload = TransportStopSyncPayload(
            sequence=st.sequence,
            stop_type=st.stop_type,
            job_id=st.worksite_id,
            accommodation_id=st.accommodation_id,
            name=stop_name,
            planned_time=str(st.planned_time) if st.planned_time else None,
            passengers=pass_payloads,
        )
        driver_stops_payload.append(st_payload)

        for sp in stop_passengers:
            p_emp = await session.get(Employee, sp.employee_id)
            if p_emp:
                passenger_to_stop[sp.employee_id] = TransportStopSyncPayload(
                    sequence=st.sequence,
                    stop_type=st.stop_type,
                    job_id=st.worksite_id,
                    accommodation_id=st.accommodation_id,
                    name=stop_name,
                    planned_time=str(st.planned_time) if st.planned_time else None,
                    passengers=[
                        TransportPassengerSyncPayload(
                            name=p_emp.name,
                            tally_id=p_emp.tally_id,
                        )
                    ],
                )

    # 1. Driver gets all stops and all passengers
    driver_run_payload = TransportRunPayload(
        run_id=run.id,
        run_date=run.run_date.isoformat(),
        direction=run.direction,
        vehicle_label=vehicle_label,
        driver=driver_payload,
        stops=driver_stops_payload,
    )
    await SyncService.write_sync_change(
        session=session,
        employee_id=run.driver_id,
        entity_type="TRANSPORT_RUN",
        entity_id=str(run.id),
        entity_version=run.version or 1,
        op="UPSERT",
        payload=driver_run_payload.model_dump(mode="json"),
        priority=1,
    )

    # 2. Passenger gets driver, vehicle, and only their own stop
    current_passenger_ids = set(passenger_to_stop.keys())
    for emp_id, stop_payload in passenger_to_stop.items():
        pass_run_payload = TransportRunPayload(
            run_id=run.id,
            run_date=run.run_date.isoformat(),
            direction=run.direction,
            vehicle_label=vehicle_label,
            driver=driver_payload,
            stops=[stop_payload],
        )
        await SyncService.write_sync_change(
            session=session,
            employee_id=emp_id,
            entity_type="TRANSPORT_RUN",
            entity_id=str(run.id),
            entity_version=run.version or 1,
            op="UPSERT",
            payload=pass_run_payload.model_dump(mode="json"),
            priority=1,
        )

    # 3. For any workers who were previously on this run but removed, send DELETE tombstone
    for prev_emp_id in event.affected_employee_ids:
        if prev_emp_id not in current_passenger_ids and prev_emp_id != run.driver_id:
            await SyncService.write_sync_change(
                session=session,
                employee_id=prev_emp_id,
                entity_type="TRANSPORT_RUN",
                entity_id=str(event.run_id),
                entity_version=1,
                op="DELETE",
                payload=None,
                priority=1,
            )


_registered = False


def register_sync_listeners() -> None:
    """Register all domain-event subscribers on the global event bus."""
    global _registered
    if _registered:
        return
    _registered = True
    event_bus.subscribe_sync(ScheduledWorkChanged, handle_scheduled_work_changed)
    event_bus.subscribe_sync(HolidayChanged, handle_holiday_changed)
    event_bus.subscribe_sync(TimeRuleChanged, handle_time_rule_changed)
    event_bus.subscribe_sync(WorksiteBoundaryChanged, handle_worksite_boundary_changed)
    event_bus.subscribe_sync(LeaveApprovedEvent, handle_leave_approved)
    event_bus.subscribe_sync(EmployeeProfileChanged, handle_employee_profile_changed)
    event_bus.subscribe_sync(AccommodationBoundaryChanged, handle_accommodation_boundary_changed)
    event_bus.subscribe_sync(TransportRunChanged, handle_transport_run_changed)
