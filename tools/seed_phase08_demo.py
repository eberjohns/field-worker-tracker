"""Phase 08 Demo Script.

Demonstrates:
1. Replaying a simulated day with late arrival (Scenario H variant).
2. Event ingestion & PostGIS spatial enrichment.
3. Daily attendance engine calculating planned vs actual, shortfall beyond grace period.
4. Review routing with anomaly reason chips (Short hours, PENDING_REVIEW).
5. Supervisor explanation comment submission.
6. Engineer approval decision and immutable calculation version preservation.
"""

import asyncio
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from fw.core.db import async_session_factory
from fw.main import app  # noqa: F401
from fw.modules.attendance.models import AttendanceRecord
from fw.modules.attendance.schemas import AttendanceCommentCreateRequest, AttendanceDecisionRequest
from fw.modules.attendance.service import AttendanceService
from fw.modules.events.schemas import EventBatchRequest, MobileEventItem
from fw.modules.events.service import EventsService
from fw.modules.identity import hash_password
from fw.modules.identity.models import User
from fw.modules.jobs.models import JobItem, Worksite
from fw.modules.org.models import Accommodation, Employee, EmployeeReportingLine, Group, RegisteredDevice, Zone
from fw.modules.scheduling.models import ScheduledWork
from fw.modules.settings.models import TimeRule


async def run_demo():
    print("=" * 70)
    print("🚀 FIELD WORKER TRACKER - PHASE 08 DEMO: EVENTS & ATTENDANCE ENGINE")
    print("=" * 70)

    work_date = date(2026, 11, 4)  # Wednesday (normal workday)

    async with async_session_factory() as session:
        # 1. Provision Group & Zone
        res = await session.execute(select(Group).where(Group.code == "DUBAI_PARKS"))
        grp = res.scalar_one_or_none()
        if not grp:
            grp = Group(code="DUBAI_PARKS", name="Dubai Parks & Resorts")
            session.add(grp)
            await session.flush()

        res = await session.execute(select(Zone).where(Zone.code == "ZONE_A"))
        zn = res.scalar_one_or_none()
        if not zn:
            zn = Zone(code="ZONE_A", name="Zone A (Marina / JBR)")
            session.add(zn)
            await session.flush()

        # 2. Provision Accommodation (Warsan Camp)
        res = await session.execute(select(Accommodation).where(Accommodation.accommodation_code == "WARSAN_DEMO"))
        acc = res.scalar_one_or_none()
        acc_poly_wkt = "POLYGON((55.4100 25.1560, 55.4145 25.1560, 55.4145 25.1605, 55.4100 25.1605, 55.4100 25.1560))"
        if not acc:
            acc = Accommodation(
                accommodation_code="WARSAN_DEMO",
                name="Warsan Staff Accommodation Camp",
                boundary=WKTElement(acc_poly_wkt, srid=4326),
                is_active=True,
            )
            session.add(acc)
            await session.flush()

        # 3. Provision Worksite (DSO)
        res = await session.execute(select(Worksite).where(Worksite.job_number == "12A14301"))
        ws = res.scalar_one_or_none()
        silicon_poly_wkt = "POLYGON((55.3800 25.1280, 55.3880 25.1280, 55.3880 25.1340, 55.3800 25.1340, 55.3800 25.1280))"
        if not ws:
            ws = Worksite(
                job_number="12A14301",
                job_name="Dubai Silicon Oasis Landscape Maintenance",
                group_id=grp.id,
                zone_id=zn.id,
                country="AE",
                is_outdoor=True,
                boundary=WKTElement(silicon_poly_wkt, srid=4326),
                is_active=True,
            )
            session.add(ws)
            await session.flush()

        # 4. Job Item (8.0 hours planned)
        res = await session.execute(select(JobItem).where(JobItem.worksite_id == ws.id, JobItem.sub_item_code == "01"))
        ji = res.scalar_one_or_none()
        if not ji:
            ji = JobItem(
                worksite_id=ws.id,
                sub_item_code="01",
                staff_grade_description="Landscape Gardener",
                planned_grade_code="LG-01",
                frequency_unit="WEEK",
                occurrences_per_period=Decimal("6.0"),
                period_interval=1,
                required_staff_count=1,
                hours_per_occurrence_per_staff=Decimal("8.0"),
                start_date=date(2026, 1, 1),
                deployment_type="PERMANENT",
                break_override_minutes=30,
                is_active=True,
            )
            session.add(ji)
            await session.flush()

        # 5. Worker (1193 - Shanto Miah)
        res = await session.execute(select(Employee).where(Employee.tally_id == "1193"))
        worker = res.scalar_one_or_none()
        if not worker:
            worker = Employee(
                tally_id="1193",
                name="Shanto Miah",
                role="WORKER",
                country="AE",
                accommodation_id=acc.id,
                weekly_off_day="SUNDAY",
            )
            session.add(worker)
            await session.flush()
        else:
            worker.accommodation_id = acc.id
            await session.flush()

        # 6. Registered Device for Worker
        res = await session.execute(select(RegisteredDevice).where(RegisteredDevice.employee_id == worker.id))
        dev = res.scalar_one_or_none()
        if not dev:
            dev = RegisteredDevice(
                employee_id=worker.id,
                device_identifier="pixel8_shanto_demo",
                platform="ANDROID",
                device_model="Google Pixel 8",
                is_active=True,
                last_seen_at=datetime.now(UTC),
            )
            session.add(dev)
            await session.flush()

        # 7. Supervisor (SUP001) and Engineer (ENG001)
        res = await session.execute(select(Employee).where(Employee.tally_id == "SUP001"))
        sup_emp = res.scalar_one_or_none()
        if not sup_emp:
            sup_emp = Employee(tally_id="SUP001", name="Ahmed Al Mansoor", role="SUPERVISOR", country="AE")
            session.add(sup_emp)
            await session.flush()
            sup_user = User(
                employee_id=sup_emp.id,
                username="SUP001",
                credential_hash=hash_password("Supervisor123!"),
                role="SUPERVISOR",
                is_active=True,
                must_change_password=False,
            )
            session.add(sup_user)
        else:
            sup_user = (await session.execute(select(User).where(User.employee_id == sup_emp.id))).scalar_one()

        res = await session.execute(select(Employee).where(Employee.tally_id == "ENG001"))
        eng_emp = res.scalar_one_or_none()
        if not eng_emp:
            eng_emp = Employee(tally_id="ENG001", name="Rami Al Khouri", role="ENGINEER", country="AE")
            session.add(eng_emp)
            await session.flush()
            eng_user = User(
                employee_id=eng_emp.id,
                username="ENG001",
                credential_hash=hash_password("Engineer123!"),
                role="ENGINEER",
                is_active=True,
                must_change_password=False,
            )
            session.add(eng_user)
        else:
            eng_user = (await session.execute(select(User).where(User.employee_id == eng_emp.id))).scalar_one()

        # 8. Scheduled Work today
        res = await session.execute(
            select(ScheduledWork).where(
                ScheduledWork.employee_id == worker.id,
                ScheduledWork.work_date == work_date,
            )
        )
        sw = res.scalar_one_or_none()
        if not sw:
            sw = ScheduledWork(
                employee_id=worker.id,
                work_date=work_date,
                worksite_id=ws.id,
                job_item_id=ji.id,
                assigned_hours=Decimal("8.0"),
                sequence=1,
                status="ACTIVE",
                source="DIRECT",
            )
            session.add(sw)

        # 9. Company Standard Time Rule
        res = await session.execute(select(TimeRule).where(TimeRule.name == "Company Standard Schedule"))
        tr = res.scalars().first()
        if not tr:
            tr = TimeRule(
                name="Company Standard Schedule",
                country="AE",
                scope_type="COMPANY",
                applies_to="ALL",
                start_date=date(2026, 1, 1),
                accommodation_start=time(5, 0),
                first_site_start=time(6, 0),
                break_minutes=30,
                last_site_end=time(15, 30),
                accommodation_end=time(17, 0),
                is_active=True,
            )
            session.add(tr)

        await session.commit()

    print("✓ Infrastructure & Users Verified:")
    print(f"  - Worker: Shanto Miah (Tally ID: 1193, Camp: Warsan)")
    print(f"  - Worksite: {ws.job_name} ({ws.job_number})")
    print(f"  - Planned Schedule: 05:00 Camp -> 06:00 Site -> 15:30 Exit -> 17:00 Camp (8h required)")
    print(f"  - Supervisor: Ahmed Al Mansoor (SUP001)")
    print(f"  - Engineer: Rami Al Khouri (ENG001)")
    print("-" * 70)

    # 10. Generate simulated events (Late Arrival Scenario):
    # Worker departs camp at 05:35, arrives at DSO at 06:40 (40 min late), exits at 15:30, returns to camp at 16:30.
    batch_id = uuid4()
    events = [
        # 05:35 UTC Camp Exit
        MobileEventItem(
            event_id=uuid4(),
            event_type="EXIT",
            event_timestamp_utc=datetime(2026, 11, 4, 5, 35, tzinfo=timezone.utc),
            latitude=Decimal("25.155"),
            longitude=Decimal("55.405"),
            accuracy_meters=12.0,
            accommodation_id=acc.id,
        ),
        # 06:40 UTC First Site Entry (40 mins late!)
        MobileEventItem(
            event_id=uuid4(),
            event_type="ENTRY",
            event_timestamp_utc=datetime(2026, 11, 4, 6, 40, tzinfo=timezone.utc),
            latitude=Decimal("25.131"),
            longitude=Decimal("55.384"),
            accuracy_meters=8.0,
            job_id=ws.id,
        ),
        # 11:00 UTC Midday Ping Inside Site
        MobileEventItem(
            event_id=uuid4(),
            event_type="PING",
            event_timestamp_utc=datetime(2026, 11, 4, 11, 0, tzinfo=timezone.utc),
            latitude=Decimal("25.132"),
            longitude=Decimal("55.385"),
            accuracy_meters=10.0,
            job_id=ws.id,
        ),
        # 15:30 UTC Site Exit
        MobileEventItem(
            event_id=uuid4(),
            event_type="EXIT",
            event_timestamp_utc=datetime(2026, 11, 4, 15, 30, tzinfo=timezone.utc),
            latitude=Decimal("25.127"),
            longitude=Decimal("55.378"),
            accuracy_meters=15.0,
            job_id=ws.id,
        ),
        # 16:30 UTC Camp Return
        MobileEventItem(
            event_id=uuid4(),
            event_type="ENTRY",
            event_timestamp_utc=datetime(2026, 11, 4, 16, 30, tzinfo=timezone.utc),
            latitude=Decimal("25.158"),
            longitude=Decimal("55.412"),
            accuracy_meters=9.0,
            accommodation_id=acc.id,
        ),
    ]

    print("📡 Ingesting Mobile Location Events Batch...")
    payload = EventBatchRequest(
        batch_id=batch_id,
        device_clock_utc=datetime(2026, 11, 4, 16, 35, tzinfo=timezone.utc),
        events=events,
    )

    async with async_session_factory() as session:
        results = await EventsService.ingest_batch(
            session=session,
            batch=payload,
            device_id=dev.id,
            employee_id=worker.id,
        )
        print(f"  ✓ Ingested {len(results)} events synchronously.")
        print(f"  ✓ PostGIS spatial enrichment & attendance engine triggered.")
        await session.commit()

    print("-" * 70)
    print("📋 Reading Calculated Attendance Row...")
    async with async_session_factory() as session:
        rec_q = (
            select(AttendanceRecord)
            .where(
                AttendanceRecord.employee_id == worker.id,
                AttendanceRecord.work_date == work_date,
            )
            .options(
                selectinload(AttendanceRecord.current_calculation),
                selectinload(AttendanceRecord.comments),
                selectinload(AttendanceRecord.approvals),
            )
        )
        record = (await session.execute(rec_q)).scalar_one_or_none()
        assert record is not None
        calc = record.current_calculation
        assert calc is not None

        def fmt_m(mins: int | None) -> str:
            if mins is None:
                return "-"
            is_neg = mins < 0
            m_abs = abs(mins)
            return f"{'-' if is_neg else ''}{m_abs // 60:02d}:{m_abs % 60:02d}"

        def fmt_signed(mins: int | None) -> str:
            if mins is None or mins == 0:
                return "00:00"
            is_neg = mins < 0
            m_abs = abs(mins)
            return f"{'-' if is_neg else '+'}{m_abs // 60:02d}:{m_abs % 60:02d}"

        print(f"  - Work Date:        {record.work_date}")
        print(f"  - Business Status:  {record.business_status}")
        print(f"  - Review Status:    {record.review_status}")
        print(f"  - Review Reasons:   {calc.review_reasons}")
        print(f"  - Planned Schedule: Acc.st: {calc.planned_accommodation_departure} | First: {calc.planned_first_site_start} | Break: {calc.planned_break_minutes}m | Last: {calc.planned_last_site_end} | Acc.end: {calc.planned_accommodation_return}")
        print(f"  - Actual Measured:  Acc.st: {calc.accommodation_departure_at.strftime('%H:%M')} | First: {calc.first_site_entry_at.strftime('%H:%M')} | Break: {calc.break_minutes_used}m | Last: {calc.last_site_exit_at.strftime('%H:%M')} | Acc.end: {calc.accommodation_return_at.strftime('%H:%M')}")
        print(f"  - Worked Minutes:   {fmt_m(calc.worked_minutes)} (Required: {fmt_m(calc.required_minutes)})")
        print(f"  - Signed Variation: {fmt_signed(calc.variation_minutes)} (Shortfall: {calc.shortfall_minutes}m)")
        print(f"  - Movements Split:  Productive: {fmt_m(calc.productive_minutes)} | Transit: {fmt_m(calc.transit_minutes)} | Idle: {fmt_m(calc.idle_minutes)}")
        print(f"  - Calculation Hash: {calc.input_hash}")
        record_id = record.id

    print("-" * 70)
    print("💬 Step 1: Supervisor Submits Explanation Comment...")
    async with async_session_factory() as session:
        comment = await AttendanceService.add_comment(
            session=session,
            attendance_id=record_id,
            author_user_id=sup_user.id,
            request=AttendanceCommentCreateRequest(
                comment_type="EXPLANATION",
                comment_text="Worker delayed by 40 minutes due to Warsan camp bus mechanical failure at 05:40. Gate pass #9102 verified.",
            ),
        )
        print(f"  ✓ Comment added by {sup_user.username} ({comment.comment_type}):")
        print(f"    \"{comment.comment_text}\"")
        await session.commit()

    print("-" * 70)
    print("✅ Step 2: Engineer Approves Attendance with Justification...")
    async with async_session_factory() as session:
        approval = await AttendanceService.record_decision(
            session=session,
            attendance_id=record_id,
            reviewer_user_id=eng_user.id,
            request=AttendanceDecisionRequest(
                decision="APPROVED",
                comment="Approved bus breakdown explanation per Gate Pass #9102.",
            ),
        )
        print(f"  ✓ Decision recorded by {eng_user.username}: {approval.decision}")
        print(f"    Comment: \"{approval.comment}\"")
        await session.commit()

    print("-" * 70)
    print("🔍 Final State Verification:")
    async with async_session_factory() as session:
        final_record = (await session.execute(rec_q)).scalar_one_or_none()
        assert final_record is not None
        print(f"  - Final Review Status: {final_record.review_status}")
        print(f"  - Total Comments:      {len(final_record.comments)}")
        print(f"  - Total Approvals:     {len(final_record.approvals)}")
        assert final_record.review_status == "APPROVED"
        print("  ✓ Full lifecycle verified successfully: Anomaly -> Pending Review -> Commented -> Approved.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_demo())
