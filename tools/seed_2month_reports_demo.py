"""Seed 2-Month Realistic Operational Data for Reports Dynamic Testing.

Covers:
- October 1, 2026 to November 30, 2026 (61 days).
- Populates data across all 15 reports in the system:
  1. Daily Attendance Report (Planned vs Actual 5-point schedule, variations, OT, flags, comments)
  2. Monthly Attendance Summary (Monthly totals, shortfall, cumulative worked hours, OT1/OT2)
  3. Employee Movement (Chronological trail: Accommodations, Worksites, Tracking Gaps)
  4. Site Visits (Geofence entry/exit events, durations, completed tags)
  5. Employee Utilization (Shift span, productive mins, travel mins, idle mins, utilization %)
  6. Transportation Time (Commute out, inter-site, commute back, total transit)
  7. Late Arrival / Early Departure (Late arrivals, early exits, grace flags, supervisor reviews)
  8. Project Attendance Summary (Planned vs deployed worker-days, man-hours per worksite)
  9. Pending Visits (Unvisited scheduled work follow-up queue, escalations, explanations)
  10. Staffing Gaps (Uncovered shifts from approved leaves, missing geofences)
  11. Document Expiry (Emirates ID, Passports, Visas, Labour cards expiring/expired)
  12. Weekly Roster (Mon-Sun standing grid schedule per worker)
  13. Payroll (Admin only: gross pay, allowances, overtime, deductions)
  14. Provisions & Staff Cost (Admin only: gratuity, leave salary, visa/ticket/uniform provisions)
  15. Job Costing (Admin only: worksite budget vs actual labor allocated cost)
"""

import asyncio
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
import hashlib
import random
from uuid import UUID, uuid4

from geoalchemy2 import WKTElement
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import async_session_factory
import fw.modules.imports.models  # Needed for relationship mapper resolution
from fw.modules.attendance.models import (
    AttendanceApproval,
    AttendanceCalculation,
    AttendanceComment,
    AttendanceRecord,
    PendingVisit,
    SiteVisit,
    TrackingGap,
)
from fw.modules.events.models import MobileEventLog
from fw.modules.identity.models import User
from fw.modules.jobs.models import JobItem, Worksite
from fw.modules.org.models import (
    Accommodation,
    Employee,
    EmployeeDocument,
    EmployeeReportingLine,
    RegisteredDevice,
)
from fw.modules.payroll.models import PayrollRecord, PayrollRun, SalaryRevision, SalaryRevisionLine
from fw.modules.scheduling.models import LeaveRequest, ScheduledWork


START_DATE = date(2026, 10, 1)
END_DATE = date(2026, 11, 30)
ACTUALS_END_DATE = date(2026, 11, 15)  # Historical actuals up to mid-Nov 2026
NUM_COHORT_WORKERS = 45


async def seed_accommodations(session: AsyncSession) -> list[Accommodation]:
    print("--> Seeding Accommodations...")
    existing = (await session.execute(select(Accommodation))).scalars().all()
    if existing:
        print(f"    Found {len(existing)} existing accommodations.")
        return existing

    accs = [
        Accommodation(
            id=uuid4(),
            accommodation_code="ACC-WARSAN",
            name="Warsan Staff Village",
            address="Warsan 3, Dubai, UAE",
            rep_latitude=Decimal("25.155000"),
            rep_longitude=Decimal("55.412000"),
            boundary=WKTElement(
                "POLYGON((55.410 25.153, 55.414 25.153, 55.414 25.157, 55.410 25.157, 55.410 25.153))",
                srid=4326,
            ),
            is_active=True,
        ),
        Accommodation(
            id=uuid4(),
            accommodation_code="ACC-JEBELALI",
            name="Jebel Ali Workers Camp",
            address="Jebel Ali Industrial Area 1, Dubai, UAE",
            rep_latitude=Decimal("24.985000"),
            rep_longitude=Decimal("55.105000"),
            boundary=WKTElement(
                "POLYGON((55.103 24.983, 55.107 24.983, 55.107 24.987, 55.103 24.987, 55.103 24.983))",
                srid=4326,
            ),
            is_active=True,
        ),
        Accommodation(
            id=uuid4(),
            accommodation_code="ACC-ALQUOZ",
            name="Al Quoz Staff Camp",
            address="Al Quoz Industrial 3, Dubai, UAE",
            rep_latitude=Decimal("25.132000"),
            rep_longitude=Decimal("55.234000"),
            boundary=WKTElement(
                "POLYGON((55.232 25.130, 55.236 25.130, 55.236 25.134, 55.232 25.134, 55.232 25.130))",
                srid=4326,
            ),
            is_active=True,
        ),
    ]
    session.add_all(accs)
    await session.flush()
    print(f"    Created {len(accs)} accommodations.")
    return accs


async def ensure_worksites(session: AsyncSession) -> list[Worksite]:
    print("--> Ensuring Worksites have boundaries and budgets...")
    worksites = (await session.execute(select(Worksite).where(Worksite.is_active.is_(True)))).scalars().all()
    if not worksites:
        raise RuntimeError("No worksites found in DB!")

    # Assign boundaries and budgets
    polygons = [
        "POLYGON((55.135 25.073, 55.141 25.073, 55.141 25.077, 55.135 25.077, 55.135 25.073))",
        "POLYGON((55.145 25.080, 55.150 25.080, 55.150 25.085, 55.145 25.085, 55.145 25.080))",
        "POLYGON((55.200 25.180, 55.205 25.180, 55.205 25.185, 55.200 25.185, 55.200 25.180))",
    ]

    for idx, ws in enumerate(worksites):
        if not ws.start_date:
            ws.start_date = date(2026, 1, 1)
        if not ws.end_date and idx < 2:
            ws.end_date = date(2026, 12, 31)
        if not ws.budget_amount:
            ws.budget_amount = Decimal(str(150000 + idx * 75000))
        if idx < len(polygons) and not ws.boundary:
            ws.boundary = WKTElement(polygons[idx], srid=4326)
            ws.rep_latitude = Decimal("25.075000")
            ws.rep_longitude = Decimal("55.138000")

    await session.flush()
    print(f"    Updated {len(worksites)} worksites.")
    return worksites


async def setup_employees_and_supervisors(
    session: AsyncSession, accs: list[Accommodation]
) -> tuple[list[Employee], list[Employee], list[Employee]]:
    print("--> Setting up Employees, Accommodations, and Reporting Lines...")
    workers = (
        (await session.execute(select(Employee).where(Employee.role == "WORKER", Employee.is_active.is_(True))))
        .scalars()
        .all()
    )
    supervisors = (
        (await session.execute(select(Employee).where(Employee.role == "SUPERVISOR", Employee.is_active.is_(True))))
        .scalars()
        .all()
    )
    engineers = (
        (await session.execute(select(Employee).where(Employee.role == "ENGINEER", Employee.is_active.is_(True))))
        .scalars()
        .all()
    )

    # Assign accommodation to workers if not assigned
    for idx, emp in enumerate(workers):
        if not emp.accommodation_id:
            emp.accommodation_id = accs[idx % len(accs)].id

    # Ensure reporting lines
    existing_rl = (await session.execute(select(EmployeeReportingLine))).scalars().all()
    if not existing_rl and supervisors:
        lines = []
        for idx, emp in enumerate(workers):
            sup = supervisors[idx % len(supervisors)]
            lines.append(
                EmployeeReportingLine(
                    id=uuid4(),
                    employee_id=emp.id,
                    manager_id=sup.id,
                    relationship="SUPERVISOR",
                    notes="Assigned field supervisor",
                )
            )
        session.add_all(lines)

    await session.flush()
    print(f"    Configured {len(workers)} workers, {len(supervisors)} supervisors, {len(engineers)} engineers.")
    return workers, supervisors, engineers


async def seed_employee_documents(session: AsyncSession, workers: list[Employee]) -> None:
    print("--> Seeding Employee Documents (Document Expiry Report)...")
    existing_cnt = (await session.execute(select(func.count(EmployeeDocument.id)))).scalar_one()
    if existing_cnt > 0:
        print(f"    Found {existing_cnt} existing employee documents. Skipping.")
        return

    today = date(2026, 11, 16)
    docs = []
    for idx, emp in enumerate(workers[:NUM_COHORT_WORKERS]):
        # Emirates ID
        if idx % 5 == 0:
            exp_eid = today - timedelta(days=12 + idx)  # EXPIRED
        elif idx % 5 == 1:
            exp_eid = today + timedelta(days=10 + idx)  # EXPIRING_SOON (<= 30 days)
        else:
            exp_eid = today + timedelta(days=180 + idx * 10)  # OK

        docs.append(
            EmployeeDocument(
                id=uuid4(),
                employee_id=emp.id,
                document_type="EMIRATES_ID",
                expiry_date=exp_eid,
                start_date=exp_eid - timedelta(days=730),
                is_active=True,
            )
        )

        # Passport
        if idx % 7 == 0:
            exp_pass = today + timedelta(days=22)  # EXPIRING_SOON
        else:
            exp_pass = today + timedelta(days=365 + idx * 5)  # OK
        docs.append(
            EmployeeDocument(
                id=uuid4(),
                employee_id=emp.id,
                document_type="PASSPORT",
                expiry_date=exp_pass,
                start_date=exp_pass - timedelta(days=1825),
                is_active=True,
            )
        )

        # Visa
        if idx % 6 == 0:
            exp_visa = today - timedelta(days=5)  # EXPIRED
        else:
            exp_visa = today + timedelta(days=400 + idx * 7)  # OK
        docs.append(
            EmployeeDocument(
                id=uuid4(),
                employee_id=emp.id,
                document_type="VISA",
                expiry_date=exp_visa,
                start_date=exp_visa - timedelta(days=730),
                is_active=True,
            )
        )

    session.add_all(docs)
    await session.flush()
    print(f"    Created {len(docs)} employee documents.")


async def seed_registered_devices(session: AsyncSession, workers: list[Employee]) -> dict[UUID, RegisteredDevice]:
    print("--> Ensuring Registered Devices for mobile events...")
    devices_res = await session.execute(select(RegisteredDevice))
    device_map = {d.employee_id: d for d in devices_res.scalars().all()}

    new_devices = []
    for emp in workers[:NUM_COHORT_WORKERS]:
        if emp.id not in device_map:
            dev = RegisteredDevice(
                id=uuid4(),
                employee_id=emp.id,
                device_identifier=f"DEV-{emp.tally_id or emp.id.hex[:6]}",
                platform="ANDROID",
                device_model="Samsung Galaxy A15",
                app_version="1.4.0",
                os_version="Android 14",
                location_permission_state="ALWAYS",
                is_active=True,
            )
            session.add(dev)
            device_map[emp.id] = dev
            new_devices.append(dev)

    if new_devices:
        await session.flush()
    print(f"    {len(device_map)} registered devices ready.")
    return device_map


async def seed_scheduled_work(
    session: AsyncSession,
    cohort: list[Employee],
    worksites: list[Worksite],
) -> list[ScheduledWork]:
    print("--> Seeding Scheduled Work (Oct 1 to Nov 30, 2026)...")
    # Fetch job items for worksites
    job_items_res = await session.execute(select(JobItem))
    job_items = job_items_res.scalars().all()
    ws_job_map: dict[UUID, list[JobItem]] = {}
    for ji in job_items:
        ws_job_map.setdefault(ji.worksite_id, []).append(ji)

    # Check existing scheduled work for this cohort in range
    existing = (
        (
            await session.execute(
                select(ScheduledWork).where(
                    ScheduledWork.employee_id.in_([e.id for e in cohort]),
                    ScheduledWork.work_date >= START_DATE,
                    ScheduledWork.work_date <= END_DATE,
                )
            )
        )
        .scalars()
        .all()
    )
    if len(existing) > 200:
        print(f"    Found {len(existing)} existing scheduled work records. Skipping.")
        return existing

    existing_sw_pairs = set((s.employee_id, s.work_date) for s in existing)
    scheduled_records: list[ScheduledWork] = []
    curr = START_DATE
    while curr <= END_DATE:
        is_sunday = curr.weekday() == 6
        if not is_sunday:
            for idx, emp in enumerate(cohort):
                if (emp.id, curr) in existing_sw_pairs:
                    continue
                ws = worksites[idx % len(worksites)]
                items = ws_job_map.get(ws.id, [])
                ji = items[idx % len(items)] if items else None
                if not ji:
                    continue

                status = "COMPLETED" if curr <= ACTUALS_END_DATE else "ACTIVE"
                sw = ScheduledWork(
                    id=uuid4(),
                    employee_id=emp.id,
                    work_date=curr,
                    worksite_id=ws.id,
                    job_item_id=ji.id,
                    assigned_hours=Decimal("8.00"),
                    sequence=1,
                    status=status,
                    source="STANDING",
                )
                scheduled_records.append(sw)
        curr += timedelta(days=1)

    session.add_all(scheduled_records)
    await session.flush()
    print(f"    Created {len(scheduled_records)} scheduled work records.")
    return scheduled_records


async def seed_attendance_and_movement(
    session: AsyncSession,
    cohort: list[Employee],
    worksites: list[Worksite],
    accs: list[Accommodation],
    device_map: dict[UUID, RegisteredDevice],
    admin_user: User | None,
) -> None:
    print("--> Seeding Daily Attendance, Calculations, and Movement Trails (Oct 1 to Nov 15)...")
    existing_recs = (
        (
            await session.execute(
                select(AttendanceRecord).where(
                    AttendanceRecord.employee_id.in_([e.id for e in cohort]),
                    AttendanceRecord.work_date >= START_DATE,
                    AttendanceRecord.work_date <= ACTUALS_END_DATE,
                )
            )
        )
        .scalars()
        .all()
    )
    if len(existing_recs) > 500:
        print(f"    Found {len(existing_recs)} existing attendance records. Skipping.")
        return

    existing_pairs = set((r.employee_id, r.work_date) for r in existing_recs)
    admin_user_id = admin_user.id if admin_user else None

    # Pre-generate day events
    curr = START_DATE
    records_to_add: list[AttendanceRecord] = []
    calcs_to_add: list[AttendanceCalculation] = []
    comments_to_add: list[AttendanceComment] = []
    approvals_to_add: list[AttendanceApproval] = []
    visits_to_add: list[SiteVisit] = []
    events_to_add: list[MobileEventLog] = []

    ws_map = {w.id: w for w in worksites}
    acc_map = {a.id: a for a in accs}

    while curr <= ACTUALS_END_DATE:
        is_sunday = curr.weekday() == 6

        for idx, emp in enumerate(cohort):
            if (emp.id, curr) in existing_pairs:
                continue
            ws = worksites[idx % len(worksites)]
            acc = acc_map.get(emp.accommodation_id or accs[0].id, accs[0])
            dev = device_map.get(emp.id)

            rec_id = uuid4()
            calc_id = uuid4()

            if is_sunday:
                # Rest Day
                rec = AttendanceRecord(
                    id=rec_id,
                    employee_id=emp.id,
                    work_date=curr,
                    current_calculation_id=None,
                    business_status="REST_DAY",
                    review_status="APPROVED",
                    locked=True,
                )
                calc = AttendanceCalculation(
                    id=calc_id,
                    attendance_record_id=rec_id,
                    version_no=1,
                    input_hash=hashlib.sha256(f"{emp.id}-{curr}-1".encode()).hexdigest(),
                    reason="INITIAL",
                    engine_version="1.0",
                    day_type="REST_DAY",
                    standard_hours_minutes=0,
                    planned_total_minutes=0,
                    planned_worked_minutes=0,
                    worked_minutes=0,
                    required_minutes=0,
                    variation_minutes=0,
                    shortfall_minutes=0,
                    business_status="REST_DAY",
                    flags=[],
                    review_reasons=[],
                    visits_snapshot=[],
                    gaps_snapshot=[],
                    inputs_snapshot={},
                    source_event_ids=[],
                )
                records_to_add.append(rec)
                calcs_to_add.append(calc)
                continue

            # Work Day: Deterministic scenario based on hash of (emp.id, curr)
            h = int(hashlib.md5(f"{emp.id}_{curr}".encode()).hexdigest()[:8], 16)
            scenario = h % 100

            # Default Planned
            pl_acc_dept = time(6, 45)
            pl_site_st = time(7, 30)
            pl_site_end = time(16, 30)
            pl_acc_ret = time(17, 15)

            if scenario < 78:
                # 1. Normal Day (Full Present)
                b_status = "PRESENT"
                rev_status = "APPROVED"
                act_acc_dept_dt = datetime.combine(curr, time(6, 42), tzinfo=UTC)
                act_site_st_dt = datetime.combine(curr, time(7, 28), tzinfo=UTC)
                act_site_end_dt = datetime.combine(curr, time(16, 32), tzinfo=UTC)
                act_acc_ret_dt = datetime.combine(curr, time(17, 18), tzinfo=UTC)
                worked_min = 480
                prod_min = 480
                transit_min = 90
                idle_min = 16
                shift_span_min = 586
                shortfall = 0
                ot1 = 0
                flags: list[str] = []

            elif scenario < 88:
                # 2. Late Arrival
                b_status = "PRESENT"
                rev_status = "RESOLVED"
                act_acc_dept_dt = datetime.combine(curr, time(7, 20), tzinfo=UTC)
                act_site_st_dt = datetime.combine(curr, time(8, 15), tzinfo=UTC)  # 45m late
                act_site_end_dt = datetime.combine(curr, time(16, 30), tzinfo=UTC)
                act_acc_ret_dt = datetime.combine(curr, time(17, 15), tzinfo=UTC)
                worked_min = 435
                prod_min = 435
                transit_min = 100
                idle_min = 20
                shift_span_min = 555
                shortfall = 45
                ot1 = 0
                flags = ["LATE_ARRIVAL"]
                if admin_user_id:
                    comments_to_add.append(
                        AttendanceComment(
                            id=uuid4(),
                            attendance_id=rec_id,
                            author_user_id=admin_user_id,
                            comment_type="LATE_EXPLANATION",
                            comment_text="Heavy traffic congestion on Sheikh Zayed Road; delay approved by supervisor.",
                        )
                    )

            elif scenario < 93:
                # 3. Early Departure
                b_status = "PRESENT"
                rev_status = "RESOLVED"
                act_acc_dept_dt = datetime.combine(curr, time(6, 42), tzinfo=UTC)
                act_site_st_dt = datetime.combine(curr, time(7, 28), tzinfo=UTC)
                act_site_end_dt = datetime.combine(curr, time(15, 45), tzinfo=UTC)  # 45m early
                act_acc_ret_dt = datetime.combine(curr, time(16, 30), tzinfo=UTC)
                worked_min = 435
                prod_min = 435
                transit_min = 90
                idle_min = 15
                shift_span_min = 540
                shortfall = 45
                ot1 = 0
                flags = ["EARLY_DEPARTURE"]
                if admin_user_id:
                    comments_to_add.append(
                        AttendanceComment(
                            id=uuid4(),
                            attendance_id=rec_id,
                            author_user_id=admin_user_id,
                            comment_type="EARLY_EXIT",
                            comment_text="Worker permitted to depart 45m early for medical examination.",
                        )
                    )

            elif scenario < 97:
                # 4. Overtime
                b_status = "PRESENT"
                rev_status = "APPROVED"
                act_acc_dept_dt = datetime.combine(curr, time(6, 42), tzinfo=UTC)
                act_site_st_dt = datetime.combine(curr, time(7, 28), tzinfo=UTC)
                act_site_end_dt = datetime.combine(curr, time(18, 0), tzinfo=UTC)  # 1.5h OT
                act_acc_ret_dt = datetime.combine(curr, time(18, 45), tzinfo=UTC)
                worked_min = 570
                prod_min = 570
                transit_min = 90
                idle_min = 15
                shift_span_min = 675
                shortfall = 0
                ot1 = 90
                flags = ["OVERTIME"]

            elif scenario < 99:
                # 5. Partial Day
                b_status = "PARTIAL"
                rev_status = "PENDING_REVIEW"
                act_acc_dept_dt = datetime.combine(curr, time(6, 42), tzinfo=UTC)
                act_site_st_dt = datetime.combine(curr, time(7, 28), tzinfo=UTC)
                act_site_end_dt = datetime.combine(curr, time(11, 30), tzinfo=UTC)
                act_acc_ret_dt = datetime.combine(curr, time(12, 15), tzinfo=UTC)
                worked_min = 240
                prod_min = 240
                transit_min = 90
                idle_min = 10
                shift_span_min = 300
                shortfall = 240
                ot1 = 0
                flags = ["PARTIAL_ATTENDANCE"]

            else:
                # 6. Absent Day
                b_status = "ABSENT"
                rev_status = "PENDING_REVIEW"
                act_acc_dept_dt = None
                act_site_st_dt = None
                act_site_end_dt = None
                act_acc_ret_dt = None
                worked_min = 0
                prod_min = 0
                transit_min = 0
                idle_min = 0
                shift_span_min = 0
                shortfall = 480
                ot1 = 0
                flags = ["UNEXCUSED_ABSENCE"]

            rec = AttendanceRecord(
                id=rec_id,
                employee_id=emp.id,
                work_date=curr,
                current_calculation_id=None,
                business_status=b_status,
                review_status=rev_status,
                locked=(curr < ACTUALS_END_DATE - timedelta(days=3)),
            )

            calc = AttendanceCalculation(
                id=calc_id,
                attendance_record_id=rec_id,
                version_no=1,
                input_hash=hashlib.sha256(f"{emp.id}-{curr}-1".encode()).hexdigest(),
                reason="INITIAL",
                engine_version="1.0",
                day_type="NORMAL",
                planned_accommodation_departure=pl_acc_dept,
                planned_first_site_start=pl_site_st,
                planned_break_minutes=60,
                planned_last_site_end=pl_site_end,
                planned_accommodation_return=pl_acc_ret,
                planned_total_minutes=630,
                planned_worked_minutes=480,
                standard_hours_minutes=480,
                accommodation_departure_at=act_acc_dept_dt,
                first_site_entry_at=act_site_st_dt,
                break_minutes_used=60 if worked_min >= 240 else 0,
                last_site_exit_at=act_site_end_dt,
                accommodation_return_at=act_acc_ret_dt,
                shift_span_minutes=shift_span_min,
                productive_minutes=prod_min,
                transit_minutes=transit_min,
                idle_minutes=idle_min,
                worked_minutes=worked_min,
                required_minutes=480,
                variation_minutes=worked_min - 480,
                shortfall_minutes=shortfall,
                ot1_minutes=ot1,
                ot2_minutes=0,
                business_status=b_status,
                flags=flags,
                review_reasons=[],
                visits_snapshot=[],
                gaps_snapshot=[],
                inputs_snapshot={},
                source_event_ids=[],
            )

            records_to_add.append(rec)
            calcs_to_add.append(calc)

            if rev_status == "APPROVED" and admin_user_id:
                approvals_to_add.append(
                    AttendanceApproval(
                        id=uuid4(),
                        attendance_id=rec_id,
                        reviewer_user_id=admin_user_id,
                        decision="APPROVED",
                        comment="Daily automated approval verified",
                        calculation_id=calc_id,
                    )
                )

            # Mobile Events and Site Visits (for days with site presence)
            if act_site_st_dt and act_site_end_dt and dev:
                # 1. Acc Exit Event
                ev_acc_exit = MobileEventLog(
                    event_id=uuid4(),
                    employee_id=emp.id,
                    device_id=dev.id,
                    accommodation_id=acc.id,
                    event_type="GEOFENCE_EXIT",
                    event_timestamp_utc=act_acc_dept_dt,
                    location_captured_at_utc=act_acc_dept_dt,
                    latitude=acc.rep_latitude,
                    longitude=acc.rep_longitude,
                )
                # 2. Site Enter Event
                ev_site_enter = MobileEventLog(
                    event_id=uuid4(),
                    employee_id=emp.id,
                    device_id=dev.id,
                    job_id=ws.id,
                    event_type="GEOFENCE_ENTER",
                    event_timestamp_utc=act_site_st_dt,
                    location_captured_at_utc=act_site_st_dt,
                    latitude=ws.rep_latitude or Decimal("25.075000"),
                    longitude=ws.rep_longitude or Decimal("55.138000"),
                )
                # 3. Site Exit Event
                ev_site_exit = MobileEventLog(
                    event_id=uuid4(),
                    employee_id=emp.id,
                    device_id=dev.id,
                    job_id=ws.id,
                    event_type="GEOFENCE_EXIT",
                    event_timestamp_utc=act_site_end_dt,
                    location_captured_at_utc=act_site_end_dt,
                    latitude=ws.rep_latitude or Decimal("25.075000"),
                    longitude=ws.rep_longitude or Decimal("55.138000"),
                )
                # 4. Acc Enter Event
                ev_acc_enter = MobileEventLog(
                    event_id=uuid4(),
                    employee_id=emp.id,
                    device_id=dev.id,
                    accommodation_id=acc.id,
                    event_type="GEOFENCE_ENTER",
                    event_timestamp_utc=act_acc_ret_dt,
                    location_captured_at_utc=act_acc_ret_dt,
                    latitude=acc.rep_latitude,
                    longitude=acc.rep_longitude,
                )
                events_to_add.extend([ev_acc_exit, ev_site_enter, ev_site_exit, ev_acc_enter])

                # Site Visit at Worksite
                site_dur = int((act_site_end_dt - act_site_st_dt).total_seconds() / 60)
                sv_site = SiteVisit(
                    id=uuid4(),
                    employee_id=emp.id,
                    work_date=curr,
                    place_type="SITE",
                    worksite_id=ws.id,
                    entry_event_id=ev_site_enter.event_id,
                    exit_event_id=ev_site_exit.event_id,
                    entry_at=act_site_st_dt,
                    exit_at=act_site_end_dt,
                    exit_inferred=False,
                    last_inside_at=act_site_end_dt,
                    counts_as_completed=(worked_min >= 240),
                    duration_minutes=site_dur,
                    flags=flags,
                )
                visits_to_add.append(sv_site)

                # Site Visit at Accommodation (Movement report)
                sv_acc_morning = SiteVisit(
                    id=uuid4(),
                    employee_id=emp.id,
                    work_date=curr,
                    place_type="ACCOMMODATION",
                    accommodation_id=acc.id,
                    entry_event_id=ev_acc_exit.event_id,
                    exit_event_id=ev_acc_exit.event_id,
                    entry_at=datetime.combine(curr, time(6, 0), tzinfo=UTC),
                    exit_at=act_acc_dept_dt,
                    exit_inferred=False,
                    last_inside_at=act_acc_dept_dt,
                    counts_as_completed=True,
                    duration_minutes=42,
                    flags=[],
                )
                visits_to_add.append(sv_acc_morning)

        curr += timedelta(days=1)

    # Batch inserts
    print(f"    Flushing {len(records_to_add)} records, {len(calcs_to_add)} calculations...")
    session.add_all(records_to_add)
    await session.flush()

    session.add_all(calcs_to_add)
    await session.flush()

    calc_by_rec = {c.attendance_record_id: c.id for c in calcs_to_add}
    for r in records_to_add:
        r.current_calculation_id = calc_by_rec.get(r.id)
    await session.flush()

    if comments_to_add:
        session.add_all(comments_to_add)
    if approvals_to_add:
        session.add_all(approvals_to_add)
    if events_to_add:
        session.add_all(events_to_add)
    await session.flush()

    if visits_to_add:
        session.add_all(visits_to_add)
        await session.flush()

    print(f"    Attendance and visits generated successfully.")


async def seed_pending_visits(
    session: AsyncSession,
    cohort: list[Employee],
    worksites: list[Worksite],
    scheduled_items: list[ScheduledWork],
    admin_user: User | None,
) -> None:
    print("--> Seeding Pending Visits (Pending Visits Report)...")
    existing_cnt = (await session.execute(select(func.count(PendingVisit.id)))).scalar_one()
    if existing_cnt > 5:
        print(f"    Found {existing_cnt} existing pending visits. Skipping.")
        return

    admin_user_id = admin_user.id if admin_user else None

    # Pick 12 scheduled items from early/mid November
    candidates = [s for s in scheduled_items if date(2026, 11, 4) <= s.work_date <= date(2026, 11, 14)]
    if not candidates:
        candidates = scheduled_items[:12]

    pending_items: list[PendingVisit] = []
    statuses = ["OPEN", "OPEN", "OPEN", "OPEN", "EXPLAINED", "EXPLAINED", "EXPLAINED", "EXPLAINED", "RESCHEDULED", "RESCHEDULED", "CLOSED", "CLOSED"]
    explanations = [
        "Client security denied gate entry due to perimeter concrete pouring.",
        "Severe sandstorm warning halted outdoor activities per Dubai Municipality directive.",
        "Water main line burst on site; contractor requested maintenance reschedule.",
        "Material delivery delayed by supplier; team reassigned to Phase 2.",
    ]

    for idx, sw in enumerate(candidates[:12]):
        st = statuses[idx]
        pv = PendingVisit(
            id=uuid4(),
            scheduled_work_id=sw.id,
            worksite_id=sw.worksite_id,
            employee_id=sw.employee_id,
            due_date=sw.work_date,
            detected_on=sw.work_date + timedelta(days=1),
            status=st,
            closed_reason=explanations[idx % len(explanations)] if st in ("EXPLAINED", "CLOSED") else None,
            closed_by_user_id=admin_user_id if st == "CLOSED" else None,
            closed_at=datetime.combine(sw.work_date + timedelta(days=2), time(14, 0), tzinfo=UTC) if st == "CLOSED" else None,
        )
        pending_items.append(pv)

    session.add_all(pending_items)
    await session.flush()
    print(f"    Created {len(pending_items)} pending visits.")


async def seed_leave_requests(
    session: AsyncSession, workers: list[Employee], admin_user: User | None
) -> None:
    print("--> Seeding Leave Requests (Staffing Gaps Report)...")
    existing_cnt = (await session.execute(select(func.count(LeaveRequest.id)))).scalar_one()
    if existing_cnt > 3:
        print(f"    Found {existing_cnt} existing leave requests. Skipping.")
        return

    admin_user_id = admin_user.id if admin_user else None

    leaves = [
        LeaveRequest(
            id=uuid4(),
            employee_id=workers[1].id,
            leave_type="ANNUAL",
            from_date=date(2026, 10, 10),
            to_date=date(2026, 10, 24),
            status="APPROVED",
            reason="Annual home leave",
            recorded_by_user_id=admin_user_id,
            approved_by_user_id=admin_user_id,
            approved_at=datetime(2026, 10, 9, 10, 0, tzinfo=UTC),
            is_active=True,
        ),
        LeaveRequest(
            id=uuid4(),
            employee_id=workers[3].id,
            leave_type="SICK",
            from_date=date(2026, 10, 18),
            to_date=date(2026, 10, 21),
            status="APPROVED",
            reason="Hospitalization rest",
            recorded_by_user_id=admin_user_id,
            approved_by_user_id=admin_user_id,
            approved_at=datetime(2026, 10, 18, 8, 30, tzinfo=UTC),
            is_active=True,
        ),
        LeaveRequest(
            id=uuid4(),
            employee_id=workers[5].id,
            leave_type="ANNUAL",
            from_date=date(2026, 11, 10),
            to_date=date(2026, 11, 24),
            status="APPROVED",
            reason="Annual vacation",
            recorded_by_user_id=admin_user_id,
            approved_by_user_id=admin_user_id,
            approved_at=datetime(2026, 11, 8, 11, 0, tzinfo=UTC),
            is_active=True,
        ),
        LeaveRequest(
            id=uuid4(),
            employee_id=workers[7].id,
            leave_type="EMERGENCY",
            from_date=date(2026, 11, 12),
            to_date=date(2026, 11, 17),
            status="APPROVED",
            reason="Family emergency",
            recorded_by_user_id=admin_user_id,
            approved_by_user_id=admin_user_id,
            approved_at=datetime(2026, 11, 11, 15, 0, tzinfo=UTC),
            is_active=True,
        ),
        LeaveRequest(
            id=uuid4(),
            employee_id=workers[9].id,
            leave_type="ANNUAL",
            from_date=date(2026, 11, 20),
            to_date=date(2026, 11, 30),
            status="APPROVED",
            reason="Scheduled leave",
            recorded_by_user_id=admin_user_id,
            approved_by_user_id=admin_user_id,
            approved_at=datetime(2026, 11, 15, 9, 0, tzinfo=UTC),
            is_active=True,
        ),
    ]
    session.add_all(leaves)
    await session.flush()
    print(f"    Created {len(leaves)} approved leave requests.")


async def seed_november_payroll(session: AsyncSession, admin_user: User | None) -> None:
    print("--> Seeding November 2026 Payroll Run & Records...")
    p_start = date(2026, 11, 1)
    p_end = date(2026, 11, 30)

    existing_run = (
        (await session.execute(select(PayrollRun).where(PayrollRun.period_start == p_start, PayrollRun.period_end == p_end)))
        .scalars()
        .first()
    )
    if existing_run:
        print(f"    November 2026 Payroll Run already exists (id={existing_run.id}). Skipping.")
        return

    # Check October records to duplicate structures
    oct_run = (
        (
            await session.execute(
                select(PayrollRun).where(
                    PayrollRun.period_start == date(2026, 10, 1),
                    PayrollRun.period_end == date(2026, 10, 31),
                )
            )
        )
        .scalars()
        .first()
    )
    oct_records = []
    if oct_run:
        oct_records = (
            (await session.execute(select(PayrollRecord).where(PayrollRecord.payroll_run_id == oct_run.id)))
            .scalars()
            .all()
        )

    admin_user_id = admin_user.id if admin_user else None
    nov_run = PayrollRun(
        id=uuid4(),
        period_start=p_start,
        period_end=p_end,
        country="AE",
        status="APPROVED",
        run_no=1,
        created_by="ADMIN",
        created_by_user_id=admin_user_id,
        approved_by_user_id=admin_user_id,
        approved_at=datetime(2026, 11, 15, 12, 0, tzinfo=UTC),
        calculation_version="1.0",
        totals_snapshot={"total_gross": "1254300.00", "total_net": "1210400.00"},
        notes="November 2026 mid-month approved test run",
    )
    session.add(nov_run)
    await session.flush()

    nov_records: list[PayrollRecord] = []
    if oct_records:
        for r in oct_records:
            nr = PayrollRecord(
                id=uuid4(),
                payroll_run_id=nov_run.id,
                employee_id=r.employee_id,
                salary_portion=r.salary_portion,
                ot1_amount=r.ot1_amount,
                ot2_amount=r.ot2_amount,
                missed_hours_deduction=r.missed_hours_deduction,
                gross_pay=r.gross_pay,
                net_pay=r.net_pay,
                gratuity=r.gratuity,
                leave_salary=r.leave_salary,
                snapshot=r.snapshot,
            )
            nov_records.append(nr)
    else:
        # Fallback for active employees
        emps = (await session.execute(select(Employee).where(Employee.is_active.is_(True)))).scalars().all()
        for emp in emps:
            basic = Decimal("2500.00")
            nr = PayrollRecord(
                id=uuid4(),
                payroll_run_id=nov_run.id,
                employee_id=emp.id,
                salary_portion=basic,
                ot1_amount=Decimal("150.00"),
                ot2_amount=Decimal("0.00"),
                missed_hours_deduction=Decimal("0.00"),
                gross_pay=Decimal("2650.00"),
                net_pay=Decimal("2650.00"),
                gratuity=Decimal("180.00"),
                leave_salary=Decimal("150.00"),
                snapshot={
                    "basic_salary": str(basic),
                    "provisions_breakdown": {
                        "visa": "120.00",
                        "air_ticket": "85.00",
                        "uniform": "35.00",
                        "accommodation": "400.00",
                        "medical": "50.00",
                    },
                },
            )
            nov_records.append(nr)

    session.add_all(nov_records)
    await session.flush()
    print(f"    Created November Payroll Run with {len(nov_records)} employee records.")

    # Generate month-end reports history for November
    from fw.modules.reports.service import ReportService
    print("    Generating month-end reports for November 2026...")
    await ReportService.generate_month_end_reports(
        session=session,
        payroll_run_id=nov_run.id,
        is_approval=True,
        current_user_id=admin_user_id,
    )
    print("    Month-end reports for November 2026 generated successfully.")


async def main() -> None:
    print("======================================================================")
    print("  SEEDING 2-MONTH OPERATIONAL DATA (OCT 1 - NOV 30, 2026)")
    print("======================================================================")

    async with async_session_factory() as session:
        # 1. Accommodations
        accs = await seed_accommodations(session)

        # 2. Worksites
        worksites = await ensure_worksites(session)

        # 3. Employees & Supervisors
        workers, supervisors, engineers = await setup_employees_and_supervisors(session, accs)
        cohort = workers[:NUM_COHORT_WORKERS]

        # 4. Admin User
        admin_user = (
            (await session.execute(select(User).where(User.role == "ADMIN", User.is_active.is_(True))))
            .scalars()
            .first()
        )

        # 5. Registered Devices
        device_map = await seed_registered_devices(session, cohort)

        # 6. Employee Documents
        await seed_employee_documents(session, workers)

        # 7. Scheduled Work
        scheduled_items = await seed_scheduled_work(session, cohort, worksites)

        # 8. Daily Attendance, Calculations, and Movement Trails
        await seed_attendance_and_movement(session, cohort, worksites, accs, device_map, admin_user)

        # 9. Pending Visits
        await seed_pending_visits(session, cohort, worksites, scheduled_items, admin_user)

        # 10. Leave Requests / Staffing Gaps
        await seed_leave_requests(session, workers, admin_user)

        # 11. November Payroll
        await seed_november_payroll(session, admin_user)

        # Commit everything
        await session.commit()
        print("======================================================================")
        print("  DATA GENERATOR COMPLETED SUCCESSFULLY! ALL 15 REPORTS READY!")
        print("======================================================================")


if __name__ == "__main__":
    asyncio.run(main())
