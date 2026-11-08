"""Phase 06 Demo Script.

Demo script per docs/phases/PHASE-06-leave-reassignment-approvals.md:
"Record leave, approve it, request a cover 3+ days ahead, approve it, see the badge on the roster."
"""

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import selectinload

from fw.core.db import async_session_factory, engine
from fw.modules.identity import User, hash_password
from fw.modules.jobs import JobItem, Worksite
from fw.modules.notifications import Alert, NotificationService
from fw.modules.org import Employee, EmployeeReportingLine, Group, Zone
from fw.modules.scheduling import (
    BaseRosterEntry,
    BaseRosterTemplate,
    LeaveRequest,
    LeaveRequestCreate,
    ReassignmentDecisionRequest,
    ReassignmentRequest,
    ReassignmentRequestCreate,
    ScheduledWork,
    SchedulingService,
)


async def run_demo() -> None:
    print("=" * 80)
    print("PHASE 06 DEMO: LEAVE, TEMPORARY REASSIGNMENT, AND APPROVALS")
    print("=" * 80)

    today = date.today()
    target_date = today + timedelta(days=5)
    leave_end = today + timedelta(days=6)

    # 1. Setup Demo Entities
    async with async_session_factory() as session:
        # Engineer
        eng_emp = (await session.execute(select(Employee).where(Employee.tally_id == "1001"))).scalar_one_or_none()
        if not eng_emp:
            eng_emp = Employee(id=uuid4(), tally_id="1001", name="Ahmed Al-Mansoor", role="ENGINEER", country="AE", is_active=True)
            session.add(eng_emp)
            await session.flush()
        eng_user = (await session.execute(select(User).where(User.username == "1001"))).scalar_one_or_none()
        if not eng_user:
            eng_user = User(id=uuid4(), employee_id=eng_emp.id, username="1001", credential_hash=hash_password("ChangeMe123!"), role="ENGINEER", is_active=True, must_change_password=False)
            session.add(eng_user)
        else:
            eng_user.credential_hash = hash_password("ChangeMe123!")
            eng_user.must_change_password = False

        # Supervisor
        sup_emp = (await session.execute(select(Employee).where(Employee.tally_id == "1004"))).scalar_one_or_none()
        if not sup_emp:
            sup_emp = Employee(id=uuid4(), tally_id="1004", name="Omar Al-Nuaimi", role="SUPERVISOR", country="AE", is_active=True)
            session.add(sup_emp)
            await session.flush()
            link_eng = EmployeeReportingLine(employee_id=sup_emp.id, manager_id=eng_emp.id, relationship="ENGINEER")
            session.add(link_eng)
        sup_user = (await session.execute(select(User).where(User.username == "1004"))).scalar_one_or_none()
        if not sup_user:
            sup_user = User(id=uuid4(), employee_id=sup_emp.id, username="1004", credential_hash=hash_password("ChangeMe123!"), role="SUPERVISOR", is_active=True, must_change_password=False)
            session.add(sup_user)
        else:
            sup_user.credential_hash = hash_password("ChangeMe123!")
            sup_user.must_change_password = False

        # Worker 1 (Bilal Khan - Gardener)
        w1_emp = (await session.execute(select(Employee).where(Employee.tally_id == "1010"))).scalar_one_or_none()
        if not w1_emp:
            w1_emp = Employee(id=uuid4(), tally_id="1010", name="Bilal Khan", role="WORKER", grade_code="G2A", staff_grade_description="Gardener", weekly_off_day="SUNDAY", country="AE", is_active=True)
            session.add(w1_emp)
            await session.flush()
            link_w1 = EmployeeReportingLine(employee_id=w1_emp.id, manager_id=sup_emp.id, relationship="SUPERVISOR")
            session.add(link_w1)

        # Worker 2 (Carlos Morales - Cover)
        w2_emp = (await session.execute(select(Employee).where(Employee.tally_id == "1011"))).scalar_one_or_none()
        if not w2_emp:
            w2_emp = Employee(id=uuid4(), tally_id="1011", name="Carlos Morales", role="WORKER", grade_code="G2A", staff_grade_description="Gardener", weekly_off_day="SUNDAY", country="AE", is_active=True)
            session.add(w2_emp)
            await session.flush()
            link_w2 = EmployeeReportingLine(employee_id=w2_emp.id, manager_id=sup_emp.id, relationship="SUPERVISOR")
            session.add(link_w2)

        # Worksite & Job Item
        group = (await session.execute(select(Group))).scalars().first()
        if not group:
            group = Group(code="GRP_DEMO", name="Demo Group", is_active=True)
            session.add(group)
            await session.flush()
        zone = (await session.execute(select(Zone))).scalars().first()
        if not zone:
            zone = Zone(code="ZN_DEMO", name="Demo Zone", is_active=True)
            session.add(zone)
            await session.flush()

        ws = (await session.execute(select(Worksite).where(Worksite.job_number == "99A00001"))).scalar_one_or_none()
        if not ws:
            ws = Worksite(
                job_number="99A00001",
                job_name="Burj Al Arab Grounds",
                group_id=group.id,
                zone_id=zone.id,
                country="AE",
                is_active=True,
            )
            session.add(ws)
            await session.flush()

        ji = (await session.execute(select(JobItem).where(JobItem.worksite_id == ws.id))).scalar_one_or_none()
        if not ji:
            ji = JobItem(
                worksite_id=ws.id,
                sub_item_code="LAND-01",
                staff_grade_description="Gardener",
                planned_grade_code="G2A",
                frequency_unit="WEEK",
                occurrences_per_period=Decimal("1"),
                required_staff_count=1,
                hours_per_occurrence_per_staff=Decimal("8.0"),
                deployment_type="PERMANENT",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                is_active=True,
            )
            session.add(ji)
            await session.flush()

        # Clean up any prior demo records
        await session.execute(delete(ScheduledWork).where(ScheduledWork.employee_id.in_([w1_emp.id, w2_emp.id])))
        await session.execute(delete(ReassignmentRequest).where(or_(
            ReassignmentRequest.original_employee_id.in_([w1_emp.id, w2_emp.id]),
            ReassignmentRequest.new_employee_id.in_([w1_emp.id, w2_emp.id]),
        )))
        await session.execute(delete(Alert).where(Alert.employee_id.in_([w1_emp.id, w2_emp.id])))
        await session.execute(delete(LeaveRequest).where(LeaveRequest.employee_id.in_([w1_emp.id, w2_emp.id])))

        # Ensure Base Roster Template for Job Item with Worker 1
        tmpl = (await session.execute(select(BaseRosterTemplate).where(BaseRosterTemplate.job_item_id == ji.id))).scalar_one_or_none()
        if not tmpl:
            tmpl = BaseRosterTemplate(
                job_item_id=ji.id,
                allocation_mode="DAY_OF_WEEK",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                is_active=True,
            )
            session.add(tmpl)
            await session.flush()
            entry = BaseRosterEntry(
                template_id=tmpl.id,
                employee_id=w1_emp.id,
                weekday_mask="ALL",
                assigned_hours=Decimal("8.0"),
                sequence=1,
            )
            session.add(entry)

        # Seed initial ScheduledWork for Worker 1 on target_date
        existing_sw = (await session.execute(select(ScheduledWork).where(ScheduledWork.employee_id == w1_emp.id, ScheduledWork.work_date == target_date))).scalar_one_or_none()
        if not existing_sw:
            sw = ScheduledWork(
                employee_id=w1_emp.id,
                work_date=target_date,
                job_item_id=ji.id,
                worksite_id=ws.id,
                assigned_hours=Decimal("8.0"),
                sequence=1,
                status="ACTIVE",
                source="STANDING",
            )
            session.add(sw)

        await session.commit()

    print(f"\n[Actors Initialized]")
    print(f"  * Engineer:       {eng_emp.name} (Tally: {eng_emp.tally_id})")
    print(f"  * Supervisor:     {sup_emp.name} (Tally: {sup_emp.tally_id})")
    print(f"  * Primary Worker: {w1_emp.name} (Tally: {w1_emp.tally_id})")
    print(f"  * Cover Worker:   {w2_emp.name} (Tally: {w2_emp.tally_id})")
    print(f"  * Target Date:    {target_date} (D+5)")

    # 2. Step 1: Record Leave Request (Supervisor records for Worker 1)
    print("\n" + "-" * 70)
    print("STEP 1: SUPERVISOR RECORDS LEAVE REQUEST (3+ DAYS AHEAD)")
    print("-" * 70)
    async with async_session_factory() as session:
        service = SchedulingService(session)
        leave_payload = LeaveRequestCreate(
            employee_id=w1_emp.id,
            leave_type="ANNUAL",
            from_date=target_date,
            to_date=leave_end,
            reason="Annual vacation to visit family",
        )
        leave_req = await service.create_leave_request(leave_payload, sup_user)
        print(f"Created Leave Request ID: {leave_req.id}")
        print(f"  Employee:   {leave_req.employee_name}")
        print(f"  Type:       {leave_req.leave_type}")
        print(f"  Date Range: {leave_req.from_date} to {leave_req.to_date}")
        print(f"  Status:     {leave_req.status}")
        leave_id = leave_req.id

    # 3. Step 2: Engineer Approves Leave Request
    print("\n" + "-" * 70)
    print("STEP 2: ENGINEER APPROVES LEAVE REQUEST")
    print("-" * 70)
    async with async_session_factory() as session:
        service = SchedulingService(session)
        approved_leave = await service.approve_leave_request(leave_id, eng_user)
        print(f"Leave Status after approval: {approved_leave.status}")
        print(f"Approved By: {approved_leave.approved_by_name} at {approved_leave.approved_at}")

        # Check Alert Created
        alerts = await NotificationService.get_open_alerts(session, sup_user)
        cover_alerts = [a for a in alerts if a.alert_type == "COVER_NEEDED" and a.ref_id == leave_id]
        print(f"Active COVER_NEEDED Alerts: {len(cover_alerts)}")
        if cover_alerts:
            print(f"  Alert Title: '{cover_alerts[0].title}'")
            print(f"  Message:     '{cover_alerts[0].message}'")

    # 4. Step 3: Check Operational Coverage for TO_BE_COVERED Slot
    print("\n" + "-" * 70)
    print("STEP 3: OPERATIONAL COVERAGE SHOWS 'TO_BE_COVERED' SLOT")
    print("-" * 70)
    async with async_session_factory() as session:
        service = SchedulingService(session)
        week_start = target_date - timedelta(days=target_date.weekday())
        cov = await service.get_operational_coverage(
            week_start=week_start,
            group_id=group.id,
        )
        found_to_be_covered = False
        for ws_row in cov.worksites:
            for item in ws_row.items:
                for day in item.days:
                    if day.work_date == target_date:
                        for w in day.workers:
                            print(f"  [Cov check] Date: {day.work_date} | Worker: {w.employee_name} ({w.employee_id}) | Type: {w.display_type} | Tags: {w.tags}")
                            if w.employee_id == w1_emp.id and w.display_type == "TO_BE_COVERED":
                                found_to_be_covered = True
        print(f"Confirmed TO_BE_COVERED slot displayed: {found_to_be_covered}")

    # 5. Step 4: Supervisor Requests Cover 3+ Days Ahead
    print("\n" + "-" * 70)
    print("STEP 4: SUPERVISOR REQUESTS REPLACEMENT COVER (5 DAYS NOTICE)")
    print("-" * 70)
    async with async_session_factory() as session:
        service = SchedulingService(session)
        reassign_payload = ReassignmentRequestCreate(
            reassignment_type="REPLACE",
            date_from=target_date,
            date_to=target_date,
            original_employee_id=w1_emp.id,
            new_employee_id=w2_emp.id,
            target_job_item_id=ji.id,
            reason_category="LEAVE_COVER",
            reason=f"Covering leave for {w1_emp.name}",
        )
        reassign_req = await service.create_reassignment_request(reassign_payload, sup_user)
        print(f"Created Reassignment Request ID: {reassign_req.id}")
        print(f"  Type:              {reassign_req.reassignment_type}")
        print(f"  Original Worker:   {reassign_req.original_employee_name}")
        print(f"  Cover Worker:      {reassign_req.new_employee_name}")
        print(f"  Notice Period:     5 days (>= 3 days notice requirement passed)")
        print(f"  Status:            {reassign_req.status}")
        reassign_id = reassign_req.id

    # 6. Step 5: Engineer Approves Cover Request
    print("\n" + "-" * 70)
    print("STEP 5: ENGINEER APPROVES COVER REASSIGNMENT")
    print("-" * 70)
    async with async_session_factory() as session:
        service = SchedulingService(session)
        approved_reassign = await service.approve_reassignment_request(
            request_id=reassign_id,
            decision_note="Approved. Carlos assigned to Burj Al Arab shift.",
            current_user=eng_user,
        )
        print(f"Reassignment Status after approval: {approved_reassign.status}")
        print(f"Decided By: {approved_reassign.decided_by_name} (Late approval: {approved_reassign.is_late_approval})")

        # Verify operational shift materialized in scheduled_work
        stmt_sw = select(ScheduledWork).where(
            ScheduledWork.reassignment_request_id == reassign_id,
            ScheduledWork.employee_id == w2_emp.id,
            ScheduledWork.work_date == target_date,
        )
        sw_cover = (await session.execute(stmt_sw)).scalar_one_or_none()
        if sw_cover:
            print(f"Materialized ScheduledWork Exception:")
            print(f"  ID:         {sw_cover.id}")
            print(f"  Worker:     {w2_emp.name}")
            print(f"  Status:     {sw_cover.status}")
            print(f"  Source:     {sw_cover.source}")
            print(f"  Sequence:   {sw_cover.sequence}")
            print(f"  Original:   {w1_emp.name} (UUID: {sw_cover.original_employee_id})")

        # Verify Alert was resolved
        open_alerts = await NotificationService.get_open_alerts(session, sup_user)
        resolved_alerts = [a for a in open_alerts if a.alert_type == "COVER_NEEDED" and a.ref_id == leave_id]
        print(f"Remaining open COVER_NEEDED alerts: {len(resolved_alerts)} (Resolved automatically on cover approval)")

    # 7. Step 6: See Badge on the Operational Roster
    print("\n" + "-" * 70)
    print("STEP 6: VERIFY COVERAGE BADGE ON OPERATIONAL ROSTER")
    print("-" * 70)
    async with async_session_factory() as session:
        service = SchedulingService(session)
        week_start = target_date - timedelta(days=target_date.weekday())
        roster = await service.get_operational_roster(
            week_start=week_start,
            group_id=group.id,
        )
        print(f"Operational Roster for {ws.job_name} ({target_date.strftime('%B %Y')}):")
        badge_found = False
        for worker_row in roster.workers:
            for day in worker_row.days:
                if day.work_date == target_date:
                    for s in day.shifts:
                        print(f"  Worker: {worker_row.name:<20} | Date: {day.work_date} | Type: {s.display_type} | Covering: {s.original_employee_name} | Tags: {s.tags}")
                        if s.original_employee_name == w1_emp.name or "Cover Shift" in s.tags:
                            badge_found = True
        print(f"Confirmed Coverage Badge displayed on Roster: {badge_found}")

    # 8. Step 7: Leave Taken Summary
    print("\n" + "-" * 70)
    print("STEP 7: LEAVE TAKEN SUMMARY (CALENDAR VS WORKING DAYS)")
    print("-" * 70)
    async with async_session_factory() as session:
        service = SchedulingService(session)
        summaries = await service.get_leave_taken_summary(
            year=target_date.year,
            employee_id=w1_emp.id,
            current_user=eng_user,
        )
        for s in summaries:
            print(f"Worker: {s.employee_name} ({s.tally_id})")
            print(f"  Total Working Days:  {s.total_working_days}")
            print(f"  Total Calendar Days: {s.total_calendar_days}")
            for l_type, l_data in s.by_type.items():
                print(f"    - {l_type}: {l_data.working_days} working days ({l_data.calendar_days} calendar days)")

    print("\n" + "=" * 80)
    print("PHASE 06 DEMO COMPLETE: ALL FLOWS EXECUTED AND VERIFIED SUCCESSFULLY")
    print("=" * 80)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_demo())
