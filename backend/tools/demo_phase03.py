"""Phase 03 Demo Script.

Demo script per docs/phases/PHASE-03-import-and-salary.md:
"Import the sample workbook, change two cells, re-upload and read the preview,
commit, then open an employee's salary history."
"""

import asyncio
import io
from uuid import uuid4

import openpyxl

from fw.core.db import async_session_factory, engine
from fw.modules.identity import User
from fw.modules.imports import generate_import_template_bytes
from fw.modules.imports.service import ImportService
from fw.modules.org import Employee
from fw.modules.payroll import PayrollSalaryService


async def run_demo() -> None:
    print("=" * 70)
    print("PHASE 03 DEMO: IMPORT FRAMEWORK, MASTER DATA & SALARY STRUCTURES")
    print("=" * 70)

    # 1. Setup Admin Actor
    admin_emp_id = uuid4()
    admin_user_id = uuid4()
    tally_admin = f"ADM{str(uuid4())[:4]}"

    test_worker_tally = f"WRK{str(uuid4())[:4]}"
    test_group_code = f"GRP{str(uuid4())[:3]}"

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
        await session.commit()

    print(f"\n[Actor] Authenticated as Admin: {tally_admin} (ID: {admin_user_id})")

    # 2. Build workbook with an initial employee, group, and salary row
    print("\n[Step 1] Preparing workbook with initial employee and salary structure...")
    template_raw = generate_import_template_bytes()
    wb = openpyxl.load_workbook(io.BytesIO(template_raw))

    # Groups
    ws_g = wb["Groups"]
    ws_g.cell(row=5, column=1, value="")
    ws_g.cell(row=5, column=2, value=test_group_code)
    ws_g.cell(row=5, column=3, value="Demo Facility Management")

    # Accommodations
    ws_a = wb["Accommodations"]
    ws_a.cell(row=5, column=1, value="")
    ws_a.cell(row=5, column=2, value="ACC-01")
    ws_a.cell(row=5, column=3, value="Sonapur Camp 1")
    ws_a.cell(row=5, column=4, value="Sonapur")
    ws_a.cell(row=5, column=5, value="AE")

    # Employees
    ws_e = wb["Employees"]
    ws_e.cell(row=5, column=1, value="")
    ws_e.cell(row=5, column=2, value=test_worker_tally)
    ws_e.cell(row=5, column=3, value="Rashid Khan")
    ws_e.cell(row=5, column=4, value="WORKER")
    ws_e.cell(row=5, column=5, value="G1C")
    ws_e.cell(row=5, column=6, value="Gardener Helper")
    ws_e.cell(row=5, column=7, value="AE")
    ws_e.cell(row=5, column=8, value="FRIDAY")
    ws_e.cell(row=5, column=18, value="+971501112233")  # phone

    # Employee_Salary
    ws_s = wb["Employee_Salary"]
    ws_s.cell(row=5, column=1, value="")
    ws_s.cell(row=5, column=2, value=test_worker_tally)
    ws_s.cell(row=5, column=3, value="2026-01-01")
    ws_s.cell(row=5, column=4, value=8.0)
    ws_s.cell(row=5, column=5, value=1200.00)
    ws_s.cell(row=5, column=6, value=100.00)

    buf1 = io.BytesIO()
    wb.save(buf1)
    bytes_batch1 = buf1.getvalue()

    # 3. First upload and preview
    print("\n[Step 2] Uploading batch 1 for preview...")
    async with async_session_factory() as session:
        prev1 = await ImportService.parse_and_preview(
            session=session,
            file_bytes=bytes_batch1,
            filename="Demo_Import_Batch_1.xlsx",
            user_id=admin_user_id,
        )
        print(f" -> Batch 1 ID: {prev1.batch_id}")
        print(f" -> Total rows detected: {prev1.summary.get('total_rows')}")
        print(f" -> Counts: {prev1.summary.get('counts')}")
        print(f" -> Can commit: {prev1.can_commit}")

        # Commit batch 1
        print("\n[Step 3] Committing batch 1 (one atomic transaction)...")
        commit1 = await ImportService.commit_batch(
            session=session,
            batch_id=prev1.batch_id,
            user_id=admin_user_id,
        )
        print(f" -> Status: {commit1.status} at {commit1.committed_at}")
        await session.commit()

    # 4. Modify two cells in workbook:
    # Cell 1: Change weekly_off_day from FRIDAY to SUNDAY
    # Cell 2: Clear phone using '_' (cell rule: '_' clears optional)
    # Cell 3: Add second salary row (revision)
    print(
        "\n[Step 4] Modifying cells: weekly_off_day: FRIDAY -> SUNDAY, phone: '_' (clear), new salary revision..."
    )
    ws_e.cell(row=5, column=8, value="SUNDAY")
    ws_e.cell(row=5, column=18, value="_")

    # Add second salary revision on row 6
    ws_s.cell(row=6, column=1, value="")
    ws_s.cell(row=6, column=2, value=test_worker_tally)
    ws_s.cell(row=6, column=3, value="2026-07-01")
    ws_s.cell(row=6, column=4, value=8.0)
    ws_s.cell(row=6, column=5, value=1500.00)
    ws_s.cell(row=6, column=6, value=200.00)

    buf2 = io.BytesIO()
    wb.save(buf2)
    bytes_batch2 = buf2.getvalue()

    # 5. Upload batch 2 and read preview diffs
    print("\n[Step 5] Re-uploading modified workbook to inspect field-level diffs...")
    async with async_session_factory() as session:
        prev2 = await ImportService.parse_and_preview(
            session=session,
            file_bytes=bytes_batch2,
            filename="Demo_Import_Batch_2.xlsx",
            user_id=admin_user_id,
        )
        print(f" -> Batch 2 ID: {prev2.batch_id}")
        print(f" -> Counts: {prev2.summary.get('counts')}")

        for r in prev2.rows:
            if r.status == "ERROR":
                print(f" -> ERROR ROW: Sheet [{r.sheet}], Key [{r.natural_key}], Codes: {r.codes}, Msgs: {r.messages}")
            if r.action == "UPDATED":
                print(f" -> UPDATED ROW: Sheet [{r.sheet}], Key [{r.natural_key}]")
                for field_name, delta in r.diff.items():
                    print(f"    * {field_name}: '{delta.get('old')}' -> '{delta.get('new')}'")

        # Commit batch 2
        print("\n[Step 6] Committing batch 2...")
        commit2 = await ImportService.commit_batch(
            session=session,
            batch_id=prev2.batch_id,
            user_id=admin_user_id,
        )
        print(f" -> Status: {commit2.status}")
        await session.commit()

    # 6. Verify employee salary history
    print(f"\n[Step 7] Reading salary history for worker [{test_worker_tally}]...")
    async with async_session_factory() as session:
        emp_match = (
            await session.execute(
                openpyxl.load_workbook
                and None
                or None  # noqa
                or Employee.__table__.select().where(Employee.tally_id == test_worker_tally)
            )
        ).first()
        emp_id = emp_match.id  # type: ignore

        history = await PayrollSalaryService.get_salary_history(session, emp_id)
        assert history is not None
        print(f" -> Worker: {history.employee_name} ({history.tally_id})")
        print(
            f" -> Current Fixed Salary Portion: {history.current_salary.salary_portion if history.current_salary else None}"
        )
        print(f" -> Last Change Date: {history.last_change_date}")
        print(f" -> Last Change Difference: +{history.last_change_difference}")
        print(" -> Revision History:")
        for rev in history.history:
            print(
                f"    * Effective {rev.effective_from}: Basic {rev.basic_salary}, Portion {rev.salary_portion}, Diff {rev.difference}"
            )

    await engine.dispose()
    print("\n" + "=" * 70)
    print("PHASE 03 DEMO COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_demo())
