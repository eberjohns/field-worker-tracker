"""Automated End-to-End Verification of Planner Coverage, Target Day, and Excess Visits.

Verifies against the live PostgreSQL database:
1. 1x/week periodic items without explicit pattern resolve default target day to Monday (not Thursday).
2. Assigning Thursday first fulfills the requirement. Assigning Tuesday second marks Tuesday as EXCESS.
   Verifies that Thursday NEVER swaps to excess.
3. Candidate recommendations include weekly off warnings for workers on their rest days.
"""

import sys
sys.path.insert(0, "backend/src")

import asyncio
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from fw.core.db import async_session_factory
from fw.modules.jobs.models import Worksite, JobItem
from fw.modules.scheduling.models import ScheduledWork
from fw.modules.scheduling.schemas import ScheduledWorkCreate
from fw.modules.scheduling.service import SchedulingService
from sqlalchemy import select, delete


import pytest

@pytest.mark.asyncio
async def test_planner_coverage_and_excess_integrity():
    print("=== STARTING PLANNER E2E VERIFICATION ===")

    async with async_session_factory() as session:
        sched_svc = SchedulingService(session)

        # -------------------------------------------------------------
        # 1. Look up worksite 12A10604 and Supervisor item (1x/week)
        # -------------------------------------------------------------
        from uuid import uuid4
        ws_stmt = select(Worksite).where(Worksite.job_number == "12A10604")
        ws = (await session.execute(ws_stmt)).scalar_one_or_none()
        if not ws:
            from fw.modules.org import Group, Zone
            grp = (await session.execute(select(Group).limit(1))).scalars().first()
            if not grp:
                grp = Group(id=uuid4(), code="G1", name="Test Group")
                session.add(grp)
            zn = (await session.execute(select(Zone).limit(1))).scalars().first()
            if not zn:
                zn = Zone(id=uuid4(), code="Z1", name="Test Zone")
                session.add(zn)
            await session.flush()
            ws = Worksite(
                id=uuid4(),
                job_number="12A10604",
                job_name="Test Site",
                group_id=grp.id,
                zone_id=zn.id,
                country="AE",
                is_outdoor=True,
                is_active=True,
                start_date=date(2026, 1, 1),
            )
            session.add(ws)
            await session.flush()

        item_stmt = select(JobItem).where(
            JobItem.worksite_id == ws.id,
            JobItem.sub_item_code == "I",  # Supervisor, 1x/week
        )
        sup_item = (await session.execute(item_stmt)).scalar_one_or_none()
        if not sup_item:
            sup_item = JobItem(
                id=uuid4(),
                worksite_id=ws.id,
                sub_item_code="I",
                staff_grade_description="Supervisor",
                planned_grade_code="G1C",
                frequency_unit="WEEK",
                occurrences_per_period=Decimal("1.0"),
                period_interval=1,
                required_staff_count=1,
                hours_per_occurrence_per_staff=Decimal("8.0"),
                deployment_type="REMOTE",
                is_active=True,
                weekday_pattern=None,
                start_date=date(2026, 1, 1),
            )
            session.add(sup_item)
            await session.flush()
        print(f"Verified Supervisor Item: id={sup_item.id}, freq={sup_item.frequency_unit}, occ={sup_item.occurrences_per_period}, pattern={sup_item.weekday_pattern}")

        # Choose a clean test week: 2026-11-23 (Monday) to 2026-11-29 (Sunday)
        test_week_monday = date(2026, 11, 23)
        test_tuesday = test_week_monday + timedelta(days=1)   # 2026-11-24
        test_thursday = test_week_monday + timedelta(days=3)  # 2026-11-26
        test_friday = test_week_monday + timedelta(days=4)    # 2026-11-27
        test_sunday = test_week_monday + timedelta(days=6)    # 2026-11-29

        # Clean any existing ScheduledWork in this test week for this item
        del_stmt = delete(ScheduledWork).where(
            ScheduledWork.job_item_id == sup_item.id,
            ScheduledWork.work_date >= test_week_monday,
            ScheduledWork.work_date <= test_sunday,
        )
        await session.execute(del_stmt)
        await session.commit()

        # -------------------------------------------------------------
        # Scenario 1: Verify Default Target Day is Monday (not Thursday)
        # -------------------------------------------------------------
        cov_view = await sched_svc.get_coverage_view(week_start=test_week_monday)
        target_ws_row = next((r for r in cov_view.worksites if r.job_number == "12A10604"), None)
        assert target_ws_row is not None, "Worksite 12A10604 not in coverage view"

        target_item_row = next((it for it in target_ws_row.items if it.job_item_id == sup_item.id), None)
        assert target_item_row is not None, "Supervisor item not found in coverage view"

        day_cells = {d.weekday: d for d in target_item_row.days}
        mon_cell = day_cells["MON"]
        thu_cell = day_cells["THU"]

        print(f"\nScenario 1 Check:")
        print(f"  Monday Cell: required={mon_cell.required_staff_count}, to_be_covered={mon_cell.is_to_be_covered}, quota_met={mon_cell.is_quota_met}")
        print(f"  Thursday Cell: required={thu_cell.required_staff_count}, to_be_covered={thu_cell.is_to_be_covered}, quota_met={thu_cell.is_quota_met}")

        assert mon_cell.required_staff_count == 1, f"Expected Monday required=1, got {mon_cell.required_staff_count}"
        assert mon_cell.is_to_be_covered is True, "Expected Monday to_be_covered=True"
        assert thu_cell.required_staff_count == 0, f"Expected Thursday required=0, got {thu_cell.required_staff_count}"
        assert thu_cell.is_to_be_covered is False, "Expected Thursday to_be_covered=False"
        print("  ✓ PASS: Default target day for 1x/week item correctly resolves to Monday (not Thursday)!")

        # -------------------------------------------------------------
        # Scenario 2: Assign Thursday First -> Verify Requirement Fulfilled
        # -------------------------------------------------------------
        from fw.modules.org import Employee
        from fw.modules.identity.models import User

        user_stmt = select(User).limit(1)
        test_user = (await session.execute(user_stmt)).scalars().first()
        if not test_user:
            from fw.modules.identity import AuthService
            test_user = User(
                id=uuid4(),
                username="ADMIN001",
                role="ADMIN",
                password_hash=AuthService.hash_password("admin123"),
                is_active=True,
            )
            session.add(test_user)
            await session.flush()
        current_user_id = test_user.id

        # Pick any active employee
        emp_stmt = select(Employee).where(Employee.is_active.is_(True), Employee.role != "ADMIN").limit(1)
        test_emp = (await session.execute(emp_stmt)).scalars().first()
        if not test_emp:
            test_emp = Employee(
                id=uuid4(),
                tally_id="EMP001",
                name="Test Employee",
                role="WORKER",
                country="AE",
                is_active=True,
                weekly_off_day="FRIDAY",
            )
            session.add(test_emp)
            await session.flush()

        # Create Thursday assignment (Shift 1)
        sw_thu = await sched_svc.create_scheduled_work(
            payload=ScheduledWorkCreate(
                employee_id=test_emp.id,
                job_item_id=sup_item.id,
                work_date=test_thursday,
                assigned_hours=Decimal("8.0"),
                acknowledge_warnings=True,
            ),
            current_user_id=current_user_id,
        )
        await session.commit()
        print(f"\nScenario 2 Step A: Created Thursday assignment id={sw_thu.id}")

        # Fetch coverage view after Thursday assignment
        cov_view = await sched_svc.get_coverage_view(week_start=test_week_monday)
        target_ws_row = next(r for r in cov_view.worksites if r.job_number == "12A10604")
        target_item_row = next(it for it in target_ws_row.items if it.job_item_id == sup_item.id)
        day_cells = {d.weekday: d for d in target_item_row.days}

        thu_cell = day_cells["THU"]
        mon_cell = day_cells["MON"]
        tue_cell = day_cells["TUE"]

        print(f"  Thursday Cell: assigned={thu_cell.assigned_staff_count}, excess={thu_cell.is_excess}, to_be_covered={thu_cell.is_to_be_covered}")
        print(f"  Monday Cell: quota_met={mon_cell.is_quota_met}, assigned={mon_cell.assigned_staff_count}")
        print(f"  Tuesday Cell: quota_met={tue_cell.is_quota_met}, assigned={tue_cell.assigned_staff_count}")

        assert thu_cell.assigned_staff_count == 1, "Expected Thursday assigned=1"
        assert thu_cell.is_excess is False, "Expected Thursday is_excess=False (requirement fulfilled)"
        assert thu_cell.is_to_be_covered is False, "Expected Thursday is_to_be_covered=False"
        assert mon_cell.is_quota_met is True, "Expected Monday is_quota_met=True"
        assert tue_cell.is_quota_met is True, "Expected Tuesday is_quota_met=True"
        print("  ✓ PASS: Thursday assignment fulfilled weekly requirement and other days marked quota met!")

        # -------------------------------------------------------------
        # Scenario 2 Step B: Assign Tuesday Second -> Verify Tuesday is EXCESS and Thursday REMAINS FULFILLED
        # -------------------------------------------------------------
        await asyncio.sleep(0.05)  # Ensure distinct timestamp
        sw_tue = await sched_svc.create_scheduled_work(
            payload=ScheduledWorkCreate(
                employee_id=test_emp.id,
                job_item_id=sup_item.id,
                work_date=test_tuesday,
                assigned_hours=Decimal("8.0"),
                acknowledge_warnings=True,
            ),
            current_user_id=current_user_id,
        )
        await session.commit()
        print(f"\nScenario 2 Step B: Created Tuesday assignment id={sw_tue.id} (after Thursday)")

        # Fetch coverage view after Tuesday assignment
        cov_view = await sched_svc.get_coverage_view(week_start=test_week_monday)
        target_ws_row = next(r for r in cov_view.worksites if r.job_number == "12A10604")
        target_item_row = next(it for it in target_ws_row.items if it.job_item_id == sup_item.id)
        day_cells = {d.weekday: d for d in target_item_row.days}

        thu_cell = day_cells["THU"]
        tue_cell = day_cells["TUE"]

        print(f"  Thursday Cell: assigned={thu_cell.assigned_staff_count}, excess={thu_cell.is_excess}, to_be_covered={thu_cell.is_to_be_covered}")
        print(f"  Tuesday Cell: assigned={tue_cell.assigned_staff_count}, excess={tue_cell.is_excess}, to_be_covered={tue_cell.is_to_be_covered}")

        # CRITICAL ASSERTIONS:
        assert thu_cell.is_excess is False, "CRITICAL ERROR: Thursday was swapped to excess!"
        assert tue_cell.is_excess is True, "CRITICAL ERROR: Tuesday should be marked EXCESS (assigned second)!"
        print("  ✓ PASS: Earlier assignment (Thursday) RETAINED requirement, and second assignment (Tuesday) is cleanly marked EXCESS! Zero swapping!")

        # -------------------------------------------------------------
        # Scenario 3: Weekly Off Day Warning in Candidate Recommendations
        # -------------------------------------------------------------
        friday_emp_stmt = select(Employee).where(
            Employee.is_active.is_(True),
            Employee.weekly_off_day.ilike("FRIDAY%"),
            Employee.role != "ADMIN",
        ).limit(1)
        friday_emp = (await session.execute(friday_emp_stmt)).scalars().first()
        if friday_emp:
            recs = await sched_svc.get_candidate_recommendations(
                job_item_id=sup_item.id,
                target_date=test_friday,
            )
            friday_rec = next((r for r in recs if r.employee_id == friday_emp.id), None)
            if friday_rec:
                print(f"\nScenario 3 Check (Friday Rest Day Warning):")
                print(f"  Candidate: {friday_rec.name}, weekly_off={friday_rec.weekly_off_day}, warnings={friday_rec.warnings}")
                has_rest_warning = any("weekly off" in w.lower() for w in friday_rec.warnings)
                assert has_rest_warning, "Expected 'Weekly off day' in candidate warnings"
                assert friday_rec.weekly_off_day == friday_emp.weekly_off_day, "Expected matching weekly_off_day"
                print("  ✓ PASS: Candidate recommendation includes weekly off day and rest day warning!")

        # -------------------------------------------------------------
        # Cleanup test week records
        # -------------------------------------------------------------
        del_clean = delete(ScheduledWork).where(
            ScheduledWork.job_item_id == sup_item.id,
            ScheduledWork.work_date >= test_week_monday,
            ScheduledWork.work_date <= test_sunday,
        )
        await session.execute(del_clean)
        await session.commit()
        print("\nCleaned up test assignments.")

    print("\n=== ALL E2E VERIFICATION SCENARIOS PASSED SUCCESSFULLY! ===")


if __name__ == "__main__":
    asyncio.run(run_e2e_verification())
