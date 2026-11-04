"""Phase 04 Demo Script.

Demo script per docs/phases/PHASE-04-sites-boundaries-jobs.md:
"Import two jobs with items, draw one boundary, copy it to the second, view occurrences for a month."
"""

import asyncio
import io
from datetime import date
from uuid import uuid4

import openpyxl

from fw.core.db import async_session_factory, engine
from fw.modules.identity import User
from fw.modules.imports import generate_import_template_bytes
from fw.modules.imports.service import ImportService
from fw.modules.jobs import JobsService
from fw.modules.org import Employee, Group, Zone


async def run_demo() -> None:
    print("=" * 70)
    print("PHASE 04 DEMO: WORKSITES, BOUNDARIES, JOB ITEMS & OCCURRENCES")
    print("=" * 70)

    # 1. Setup Admin Actor and Master Data
    admin_emp_id = uuid4()
    admin_user_id = uuid4()
    tally_admin = f"ADM{str(uuid4())[:4]}"

    demo_group_code = f"GRP{str(uuid4())[:3]}"
    demo_zone_code = f"ZON{str(uuid4())[:3]}"

    async with async_session_factory() as session:
        admin_emp = Employee(
            id=admin_emp_id,
            tally_id=tally_admin,
            name="Demo Admin",
            role="ADMIN",
            country="AE",
            is_active=True,
        )
        session.add(admin_emp)
        await session.flush()

        admin_user = User(
            id=admin_user_id,
            employee_id=admin_emp_id,
            username=tally_admin,
            credential_hash="fakehash",
            role="ADMIN",
            is_active=True,
            must_change_password=False,
        )
        session.add(admin_user)

        # Add group & zone for import resolution
        g = Group(code=demo_group_code, name="Phase 04 Demo Group")
        z = Zone(code=demo_zone_code, name="Dubai Marina Zone")
        session.add(g)
        session.add(z)

        await session.commit()

    print(f"\n[Actor] Authenticated as Admin: {tally_admin} (ID: {admin_user_id})")
    print(f"[Master Data] Created Group: {demo_group_code}, Zone: {demo_zone_code}")

    # 2. Generate and Populate Import Workbook with Two Worksites & Job Items
    print("\n" + "-" * 50)
    print("STEP 1: IMPORT TWO JOBS WITH ITEMS VIA EXCEL WORKBOOK")
    print("-" * 50)

    template_bytes = generate_import_template_bytes()
    wb = openpyxl.load_workbook(io.BytesIO(template_bytes))

    ws_worksites = wb["Worksites"]
    ws_items = wb["Job_Items"]

    # Job 1: 26A50001 (A -> Outdoor)
    # Job 2: 26B50002 (B -> Indoor)
    job1_num = f"26A{str(uuid4().int)[:5]}"
    job2_num = f"26B{str(uuid4().int)[:5]}"

    # Worksites columns:
    # 1: _action, 2: job_number, 3: job_name, 4: renewal_reference, 5: group_code,
    # 6: zone_code, 7: customer_type, 8: country, 9: is_outdoor, 10: contract_start_date,
    # 11: contract_end_date, 12: labour_budget_amount, 13: notes
    ws_worksites.cell(row=5, column=1, value="")
    ws_worksites.cell(row=5, column=2, value=job1_num)
    ws_worksites.cell(row=5, column=3, value="Dubai Hills Estate Landscape")
    ws_worksites.cell(row=5, column=4, value="REN-2026")
    ws_worksites.cell(row=5, column=5, value=demo_group_code)
    ws_worksites.cell(row=5, column=6, value=demo_zone_code)
    ws_worksites.cell(row=5, column=7, value="Direct")
    ws_worksites.cell(row=5, column=8, value="AE")
    ws_worksites.cell(row=5, column=9, value="Y")
    ws_worksites.cell(row=5, column=10, value="2026-01-01")
    ws_worksites.cell(row=5, column=11, value="2026-12-31")
    ws_worksites.cell(row=5, column=12, value=85000.00)

    ws_worksites.cell(row=6, column=1, value="")
    ws_worksites.cell(row=6, column=2, value=job2_num)
    ws_worksites.cell(row=6, column=3, value="Dubai Hills Club Indoor Feature")
    ws_worksites.cell(row=6, column=4, value=None)
    ws_worksites.cell(row=6, column=5, value=demo_group_code)
    ws_worksites.cell(row=6, column=6, value=demo_zone_code)
    ws_worksites.cell(row=6, column=7, value="Direct")
    ws_worksites.cell(row=6, column=8, value="AE")
    ws_worksites.cell(row=6, column=9, value="N")
    ws_worksites.cell(row=6, column=10, value="2026-01-01")
    ws_worksites.cell(row=6, column=11, value="2026-12-31")
    ws_worksites.cell(row=6, column=12, value=35000.00)

    # Job Items columns:
    # 1: _action, 2: job_number, 3: sub_item_code, 4: staff_grade_description,
    # 5: planned_grade_code, 6: deployment_type, 7: frequency_unit, 8: occurrences_per_period,
    # 9: period_interval, 10: weekday_pattern, 11: required_staff_count,
    # 12: hours_per_occurrence_per_staff, 13: break_override_minutes
    ws_items.cell(row=5, column=1, value="")
    ws_items.cell(row=5, column=2, value=job1_num)
    ws_items.cell(row=5, column=3, value="01")
    ws_items.cell(row=5, column=4, value="Gardener - Hand Watering")
    ws_items.cell(row=5, column=5, value="G1C")
    ws_items.cell(row=5, column=6, value="PERMANENT")
    ws_items.cell(row=5, column=7, value="WEEK")
    ws_items.cell(row=5, column=8, value=6.0)
    ws_items.cell(row=5, column=9, value=1)
    ws_items.cell(row=5, column=10, value="MON,TUE,WED,THU,FRI,SAT")
    ws_items.cell(row=5, column=11, value=3)
    ws_items.cell(row=5, column=12, value=9.0)

    ws_items.cell(row=6, column=1, value="")
    ws_items.cell(row=6, column=2, value=job1_num)
    ws_items.cell(row=6, column=3, value="02")
    ws_items.cell(row=6, column=4, value="Team Leader")
    ws_items.cell(row=6, column=5, value="TL1")
    ws_items.cell(row=6, column=6, value="REMOTE")
    ws_items.cell(row=6, column=7, value="MONTH")
    ws_items.cell(row=6, column=8, value=1.0)
    ws_items.cell(row=6, column=9, value=1)
    ws_items.cell(row=6, column=10, value=None)
    ws_items.cell(row=6, column=11, value=1)
    ws_items.cell(row=6, column=12, value=9.0)

    ws_items.cell(row=7, column=1, value="")
    ws_items.cell(row=7, column=2, value=job2_num)
    ws_items.cell(row=7, column=3, value="01")
    ws_items.cell(row=7, column=4, value="Gardener - Tree Trimming")
    ws_items.cell(row=7, column=5, value="G1C")
    ws_items.cell(row=7, column=6, value="REMOTE")
    ws_items.cell(row=7, column=7, value="MONTH")
    ws_items.cell(row=7, column=8, value=2.0)
    ws_items.cell(row=7, column=9, value=1)
    ws_items.cell(row=7, column=10, value=None)
    ws_items.cell(row=7, column=11, value=1)
    ws_items.cell(row=7, column=12, value=6.0)

    upload_stream = io.BytesIO()
    wb.save(upload_stream)
    upload_bytes = upload_stream.getvalue()

    # Upload & Commit
    async with async_session_factory() as session:
        prev = await ImportService.parse_and_preview(
            session=session,
            file_bytes=upload_bytes,
            filename="Phase04_Demo_Jobs.xlsx",
            user_id=admin_user_id,
        )
        print(
            f"[Import Preview] Total Rows={prev.summary.get('total_rows')}, Counts={prev.summary.get('counts')}, can_commit={prev.can_commit}"
        )
        assert prev.can_commit is True

        commit_res = await ImportService.commit_batch(
            session=session,
            batch_id=prev.batch_id,
            user_id=admin_user_id,
        )
        await session.commit()
        print(
            f"[Import Commit] Batch {commit_res.batch_id} committed: status={commit_res.status} at {commit_res.committed_at}"
        )

    # 3. Verify Worksites and Check Boundary Queue
    print("\n" + "-" * 50)
    print("STEP 2: VERIFY JOBS & BOUNDARY SETUP QUEUE")
    print("-" * 50)

    async with async_session_factory() as session:
        all_ws = await JobsService.list_worksites(session=session, q="26")
        ws1 = next(w for w in all_ws if w.job_number == job1_num)
        ws2 = next(w for w in all_ws if w.job_number == job2_num)
        print(
            f"Worksite 1: {ws1.job_number} '{ws1.job_name}' | is_outdoor={ws1.is_outdoor} | has_boundary={ws1.has_boundary}"
        )
        print(
            f"Worksite 2: {ws2.job_number} '{ws2.job_name}' | is_outdoor={ws2.is_outdoor} | has_boundary={ws2.has_boundary}"
        )

        queue = await JobsService.get_boundary_queue(session=session)
        print(
            f"Boundary Queue: {queue.unset_count} unset boundaries out of {queue.total_count} total entities."
        )
        assert ws1.has_boundary is False
        assert ws2.has_boundary is False

    # 4. Draw/Set Boundary on Worksite 1
    print("\n" + "-" * 50)
    print("STEP 3: DRAW VALID BOUNDARY ON WORKSITE 1")
    print("-" * 50)

    # Dubai Hills Estate Polygon coordinates [lng, lat]
    dubai_hills_polygon = {
        "type": "Polygon",
        "coordinates": [
            [
                [55.2400, 25.1100],
                [55.2500, 25.1100],
                [55.2500, 25.1200],
                [55.2400, 25.1200],
                [55.2400, 25.1100],
            ]
        ],
    }

    async with async_session_factory() as session:
        updated_ws1 = await JobsService.update_worksite_boundary(
            session=session,
            worksite_id=ws1.id,
            geojson_dict=dubai_hills_polygon,
            actor_user_id=admin_user_id,
            actor_role="ADMIN",
        )
        await session.commit()
        print(f"Worksite 1 updated: has_boundary={updated_ws1.has_boundary}")
        print(
            f"Boundary GeoJSON: type={updated_ws1.boundary_geojson['type']}, vertices={len(updated_ws1.boundary_geojson['coordinates'][0])}"
        )
        print(
            f"Representative Point: lat={updated_ws1.rep_latitude}, lng={updated_ws1.rep_longitude}"
        )

    # 5. Copy Boundary from Worksite 1 to Worksite 2
    print("\n" + "-" * 50)
    print("STEP 4: COPY BOUNDARY FROM WORKSITE 1 TO WORKSITE 2")
    print("-" * 50)

    async with async_session_factory() as session:
        updated_ws2 = await JobsService.copy_boundary(
            session=session,
            target_worksite_id=ws2.id,
            source_worksite_id=ws1.id,
            actor_user_id=admin_user_id,
            actor_role="ADMIN",
        )
        await session.commit()
        print(f"Worksite 2 updated via copy: has_boundary={updated_ws2.has_boundary}")
        print(
            f"Representative Point matches: lat={updated_ws2.rep_latitude}, lng={updated_ws2.rep_longitude}"
        )
        assert updated_ws2.has_boundary is True
        assert updated_ws2.rep_latitude == updated_ws1.rep_latitude
        assert updated_ws2.rep_longitude == updated_ws1.rep_longitude

    # 6. View Generated Occurrences for a Month
    print("\n" + "-" * 50)
    print("STEP 5: VIEW OCCURRENCES FOR A MONTH (2026-12-01 to 2026-12-31)")
    print("-" * 50)

    async with async_session_factory() as session:
        december_occs = await JobsService.list_occurrences(
            session=session,
            worksite_id=ws1.id,
            from_date=date(2026, 12, 1),
            to_date=date(2026, 12, 31),
        )
        print(f"Total occurrences for Worksite 1 in December 2026: {len(december_occs)}")
        print(
            f"{'Slot':<6} | {'Item ID':<10} | {'Window Start':<12} | {'Due Date':<12} | {'Staff':<6} | {'Hours':<6} | {'Status'}"
        )
        print("-" * 75)
        for occ in december_occs[:10]:
            print(
                f"#{occ.slot_index:<5} | {str(occ.job_item_id)[:8]:<10} | {str(occ.window_start):<12} | {str(occ.due_date):<12} | {occ.required_staff_count:<5} | {occ.required_hours_per_staff:<5} | {occ.status}"
            )
        if len(december_occs) > 10:
            print(f"... and {len(december_occs) - 10} more occurrences in the month.")

    print("\n" + "=" * 70)
    print("PHASE 04 DEMO COMPLETED SUCCESSFULLY!")
    print("=" * 70)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_demo())
