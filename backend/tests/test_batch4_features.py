"""Integration and unit tests for Batch 4 features:
1. Break Time (One source of truth):
   - Salary break > seasonal/effective time rule > company default
   - Job item break override strictly display-only
   - Crew break propagation to salary structure with effective date, future row update, same-date update, locked period guardrail
   - Worker newly linked to supervisor inherits crew break
2. Fixed Crew Hierarchy (DEC-10):
   - Soft-deactivation (is_active, deactivated_at, deactivated_by)
   - Reactivation of previously deactivated link
   - Hierarchy violations audit endpoint and Excel export
   - Move to supervisor and deactivation actions
   - Transitive leadership inheritance and approval re-routing
"""

from __future__ import annotations

import asyncio
import io
import socket
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import openpyxl
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from fw.core.db import async_session_factory, engine
from fw.core.errors import AppError
from fw.main import app
from fw.modules.identity import AuthService, User, UserService
from fw.modules.org import Employee, EmployeeReportingLine, OrgService
from fw.modules.payroll import EmployeeSalary, PayrollRun, PayrollSalaryService
from fw.modules.scheduling import LeaveRequest, SchedulingService
from fw.rules.attendance.engine import DailyCalculationInputs, compute_daily_attendance


def is_db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=0.5):
            return True
    except OSError:
        return False


db_required = pytest.mark.skipif(
    not is_db_available(),
    reason="Database integration tests require PostgreSQL running on localhost:5432",
)


@pytest.fixture(autouse=True)
async def cleanup_db():
    yield
    await engine.dispose()
    await asyncio.sleep(0.01)


ADMIN_PW = "AdminBatch4Pass!99"


async def get_admin_client():
    async with async_session_factory() as session:
        admin_user = await UserService.get_or_create_system_admin(session, password=ADMIN_PW)
        token = AuthService.create_access_token(admin_user)

    transport = ASGITransport(app=app)
    return AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    )


# ---------------------------------------------------------------------------
# 1. Pure Attendance Engine Break Tests
# ---------------------------------------------------------------------------


def test_pure_break_calculation_and_job_item_ignored():
    """Verify that job_item_break_override is ignored and break_source is populated."""
    from datetime import time
    from fw.rules.attendance.engine import ScheduledAssignment
    from fw.rules.attendance.visits import ConstructedVisit
    from fw.rules.time_rules import ResolvedTimeSchedule

    def make_sched(break_m: int) -> ResolvedTimeSchedule:
        return ResolvedTimeSchedule(
            accommodation_start=time(6, 0),
            first_site_start=time(7, 0),
            break_minutes=break_m,
            last_site_end=time(16, 0),
            accommodation_end=time(17, 0),
            planned_total_minutes=660,
            planned_worked_minutes=660 - break_m,
            standard_hours_change_minutes=0,
            has_accommodation=True,
            winning_rule_id=None,
            winning_rule_name="Default Company Rule",
        )

    work_date = date(2026, 11, 19)
    schedule = make_sched(30)
    site_id = uuid4()
    # Worker arrived at 07:00, left at 16:00 (540 minutes on site).
    # first_site_break_override is 90 mins (should be IGNORED, break_source wins).
    visits = [
        ConstructedVisit(
            work_date=work_date,
            place_type="SITE",
            worksite_id=site_id,
            accommodation_id=None,
            entry_event_id=uuid4(),
            exit_event_id=uuid4(),
            entry_at=datetime(2026, 11, 19, 7, 0, tzinfo=timezone.utc),
            exit_at=datetime(2026, 11, 19, 16, 0, tzinfo=timezone.utc),
            exit_inferred=False,
            last_inside_at=datetime(2026, 11, 19, 16, 0, tzinfo=timezone.utc),
            counts_as_completed=True,
            duration_minutes=540,
        )
    ]
    assignments = [
        ScheduledAssignment(
            scheduled_work_id=uuid4(),
            worksite_id=site_id,
            assigned_hours=8.0,
        )
    ]

    # Test 1: Salary break takes priority (e.g. 45 mins)
    inputs_sal = DailyCalculationInputs(
        employee_id=uuid4(),
        tally_id="W01",
        work_date=work_date,
        is_driver=False,
        has_accommodation=True,
        standard_hours=8.0,
        schedule=make_sched(45),
        assignments=assignments,
        visits=visits,
        gaps=[],
        is_public_holiday=False,
        is_weekly_off=False,
        is_ot2_weekday=False,
        has_approved_leave=False,
        first_site_break_override=90,
        break_source="SALARY_STRUCTURE",
    )
    res_sal = compute_daily_attendance(inputs_sal)
    # Elapsed: 540 min. Break: 45 min -> Worked: 495 min
    assert res_sal.worked_minutes == 495
    assert res_sal.planned_break_minutes == 45
    assert res_sal.break_source == "SALARY_STRUCTURE"

    # Test 2: Time rule break (e.g. 30 mins)
    inputs_tr = DailyCalculationInputs(
        employee_id=uuid4(),
        tally_id="W01",
        work_date=work_date,
        is_driver=False,
        has_accommodation=True,
        standard_hours=8.0,
        schedule=schedule,
        assignments=assignments,
        visits=visits,
        gaps=[],
        is_public_holiday=False,
        is_weekly_off=False,
        is_ot2_weekday=False,
        has_approved_leave=False,
        first_site_break_override=90,
        break_source="TIME_RULE",
    )
    res_tr = compute_daily_attendance(inputs_tr)
    # Elapsed: 540 min. Break: 30 min -> Worked: 510 min
    assert res_tr.worked_minutes == 510
    assert res_tr.planned_break_minutes == 30
    assert res_tr.break_source == "TIME_RULE"

    # Test 3: Company default (e.g. 60 mins)
    inputs_cd = DailyCalculationInputs(
        employee_id=uuid4(),
        tally_id="W01",
        work_date=work_date,
        is_driver=False,
        has_accommodation=True,
        standard_hours=8.0,
        schedule=make_sched(60),
        assignments=assignments,
        visits=visits,
        gaps=[],
        is_public_holiday=False,
        is_weekly_off=False,
        is_ot2_weekday=False,
        has_approved_leave=False,
        first_site_break_override=90,
        break_source="COMPANY_DEFAULT",
    )
    res_cd = compute_daily_attendance(inputs_cd)
    # Elapsed: 540 min. Break: 60 min -> Worked: 480 min
    assert res_cd.worked_minutes == 480
    assert res_cd.planned_break_minutes == 60
    assert res_cd.break_source == "COMPANY_DEFAULT"


# ---------------------------------------------------------------------------
# 2. Crew Break Propagation Tests
# ---------------------------------------------------------------------------


@db_required
@pytest.mark.asyncio
async def test_crew_break_propagation_future_and_same_date():
    """Verify crew break propagation: future rows updated, same-date updated, change_source='CREW_BREAK'."""
    tag = uuid4().hex[:6].upper()
    today = date.today()
    future_date = today + timedelta(days=30)

    async with async_session_factory() as session:
        # Create Supervisor
        sup = Employee(
            id=uuid4(),
            tally_id=f"SUP_{tag}",
            name=f"Supervisor {tag}",
            role="SUPERVISOR",
            country="AE",
            is_active=True,
        )
        # Create Worker
        w = Employee(
            id=uuid4(),
            tally_id=f"WRK_{tag}",
            name=f"Worker {tag}",
            role="WORKER",
            country="AE",
            is_active=True,
        )
        session.add_all([sup, w])
        await session.flush()

        # Link Worker to Supervisor
        rep = EmployeeReportingLine(
            employee_id=w.id,
            manager_id=sup.id,
            relationship="SUPERVISOR",
            is_active=True,
        )
        session.add(rep)

        # Baseline salary row
        sal1 = EmployeeSalary(
            employee_id=w.id,
            effective_from=date(2026, 1, 1),
            standard_hours=Decimal("8.0"),
            basic_salary=Decimal("1200.00"),
            break_minutes=30,
        )
        # Future-dated salary row
        sal_future = EmployeeSalary(
            employee_id=w.id,
            effective_from=future_date,
            standard_hours=Decimal("8.0"),
            basic_salary=Decimal("1400.00"),
            break_minutes=30,
        )
        session.add_all([sal1, sal_future])
        await session.commit()
        sup_id = sup.id
        w_id = w.id

    client = await get_admin_client()
    try:
        # Admin sets crew break to 60 mins on the supervisor with effective_from = today
        res = await client.patch(
            f"/api/v1/employees/{sup_id}",
            json={
                "break_override_minutes": 60,
                "effective_from": today.isoformat(),
                "version": 1,
            },
        )
        assert res.status_code == 200, res.text

        # Verify worker salary rows
        async with async_session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(EmployeeSalary)
                        .where(EmployeeSalary.employee_id == w_id)
                        .order_by(EmployeeSalary.effective_from.asc())
                    )
                )
                .scalars()
                .all()
            )

            # We should have:
            # 1. 2026-01-01 (original 30 min break)
            # 2. today (new row created by propagation with break_minutes=60, change_source='CREW_BREAK')
            # 3. future_date (future row updated with break_minutes=60)
            assert len(rows) == 3
            today_row = next((r for r in rows if r.effective_from == today), None)
            assert today_row is not None
            assert today_row.break_minutes == 60
            assert today_row.change_source == "CREW_BREAK"
            assert today_row.basic_salary == Decimal("1200.00")

            fut_row = next((r for r in rows if r.effective_from == future_date), None)
            assert fut_row is not None
            assert fut_row.break_minutes == 60

        # Now test same-date update: updating supervisor break again on the same day updates in place
        res2 = await client.patch(
            f"/api/v1/employees/{sup_id}",
            json={
                "break_override_minutes": 45,
                "effective_from": today.isoformat(),
                "version": 2,
            },
        )
        assert res2.status_code == 200

        async with async_session_factory() as session:
            rows2 = (
                (
                    await session.execute(
                        select(EmployeeSalary)
                        .where(EmployeeSalary.employee_id == w_id)
                        .order_by(EmployeeSalary.effective_from.asc())
                    )
                )
                .scalars()
                .all()
            )
            # Still 3 rows, not 4
            assert len(rows2) == 3
            today_row2 = next((r for r in rows2 if r.effective_from == today), None)
            assert today_row2 is not None
            assert today_row2.break_minutes == 45
    finally:
        await client.aclose()


@db_required
@pytest.mark.asyncio
async def test_crew_break_locked_period_guardrail():
    """Verify that propagating crew break to a period with APPROVED payroll is rejected with 422."""
    tag = uuid4().hex[:6].upper()
    past_date = date(2026, 1, 15)

    async with async_session_factory() as session:
        sup = Employee(
            id=uuid4(),
            tally_id=f"SUP_LK_{tag}",
            name=f"Sup Locked {tag}",
            role="SUPERVISOR",
            country="AE",
            is_active=True,
        )
        w = Employee(
            id=uuid4(),
            tally_id=f"WRK_LK_{tag}",
            name=f"Worker Locked {tag}",
            role="WORKER",
            country="AE",
            is_active=True,
        )
        session.add_all([sup, w])
        await session.flush()

        rep = EmployeeReportingLine(
            employee_id=w.id,
            manager_id=sup.id,
            relationship="SUPERVISOR",
            is_active=True,
        )
        sal = EmployeeSalary(
            employee_id=w.id,
            effective_from=date(2025, 1, 1),
            standard_hours=Decimal("8.0"),
            basic_salary=Decimal("1200.00"),
            break_minutes=30,
        )
        session.add_all([rep, sal])

        # Approved payroll run for Jan 2026
        prun = PayrollRun(
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            country="AE",
            status="APPROVED",
            run_no=1,
            calculation_version="v1.0",
        )
        session.add(prun)
        await session.commit()
        sup_id = sup.id

    client = await get_admin_client()
    try:
        res = await client.patch(
            f"/api/v1/employees/{sup_id}",
            json={
                "break_override_minutes": 60,
                "effective_from": past_date.isoformat(),
                "version": 1,
            },
        )
        assert res.status_code == 422
        body = res.json()
        assert "PAYROLL_PERIOD_LOCKED" in str(body)
    finally:
        await client.aclose()


@db_required
@pytest.mark.asyncio
async def test_worker_newly_linked_inherits_supervisor_break():
    """Verify that a worker newly linked to a supervisor with break_override_minutes inherits the break."""
    tag = uuid4().hex[:6].upper()
    async with async_session_factory() as session:
        sup = Employee(
            id=uuid4(),
            tally_id=f"SUP_BR_{tag}",
            name=f"Sup Break {tag}",
            role="SUPERVISOR",
            break_override_minutes=50,
            country="AE",
            is_active=True,
        )
        w = Employee(
            id=uuid4(),
            tally_id=f"WRK_BR_{tag}",
            name=f"Worker Break {tag}",
            role="WORKER",
            country="AE",
            is_active=True,
        )
        sal = EmployeeSalary(
            employee_id=w.id,
            effective_from=date(2026, 1, 1),
            standard_hours=Decimal("8.0"),
            basic_salary=Decimal("1200.00"),
            break_minutes=30,
        )
        session.add_all([sup, w, sal])
        await session.commit()
        sup_id = sup.id
        w_id = w.id

    client = await get_admin_client()
    try:
        # Link worker to supervisor
        res = await client.post(
            f"/api/v1/employees/{w_id}/reporting-lines",
            json={"manager_id": str(sup_id), "relationship": "SUPERVISOR"},
        )
        assert res.status_code == 201, res.text

        # Verify worker salary record was created or updated with break_minutes=50
        async with async_session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(EmployeeSalary).where(EmployeeSalary.employee_id == w_id)
                    )
                )
                .scalars()
                .all()
            )
            assert len(rows) >= 1
            latest = sorted(rows, key=lambda r: r.effective_from, reverse=True)[0]
            assert latest.break_minutes == 50
            assert latest.change_source == "CREW_BREAK"
    finally:
        await client.aclose()


# ---------------------------------------------------------------------------
# 3. Soft Deactivation and Hierarchy Violations Tests
# ---------------------------------------------------------------------------


@db_required
@pytest.mark.asyncio
async def test_reporting_line_soft_deactivation_and_reactivation():
    """Verify that remove_reporting_line soft-deactivates, and re-adding re-activates."""
    tag = uuid4().hex[:6].upper()
    async with async_session_factory() as session:
        sup = Employee(
            id=uuid4(),
            tally_id=f"SUP_SD_{tag}",
            name=f"Sup Soft {tag}",
            role="SUPERVISOR",
            country="AE",
            is_active=True,
        )
        w = Employee(
            id=uuid4(),
            tally_id=f"WRK_SD_{tag}",
            name=f"Worker Soft {tag}",
            role="WORKER",
            country="AE",
            is_active=True,
        )
        session.add_all([sup, w])
        await session.commit()
        sup_id = sup.id
        w_id = w.id

    client = await get_admin_client()
    try:
        # Add reporting line
        add_res = await client.post(
            f"/api/v1/employees/{w_id}/reporting-lines",
            json={"manager_id": str(sup_id), "relationship": "SUPERVISOR"},
        )
        assert add_res.status_code == 201
        line_id = add_res.json()["id"]

        # Deactivate reporting line
        del_res = await client.delete(f"/api/v1/employees/{w_id}/reporting-lines/{line_id}")
        assert del_res.status_code == 200

        # Check DB: record must NOT be deleted, is_active must be False
        async with async_session_factory() as session:
            line = await session.get(EmployeeReportingLine, line_id)
            assert line is not None
            assert line.is_active is False
            assert line.deactivated_at is not None

            # list_reporting_lines must return empty
            active_lines = await OrgService.list_reporting_lines(session, w_id)
            assert len(active_lines) == 0

        # Re-add the same reporting line -> should re-activate the existing record
        re_add_res = await client.post(
            f"/api/v1/employees/{w_id}/reporting-lines",
            json={"manager_id": str(sup_id), "relationship": "SUPERVISOR"},
        )
        assert re_add_res.status_code == 201
        assert re_add_res.json()["id"] == line_id

        async with async_session_factory() as session:
            line_re = await session.get(EmployeeReportingLine, line_id)
            assert line_re is not None
            assert line_re.is_active is True
            assert line_re.deactivated_at is None
    finally:
        await client.aclose()


@db_required
@pytest.mark.asyncio
async def test_hierarchy_violations_audit_excel_and_actions():
    """Verify hierarchy violations detection, Excel export, move to supervisor, and approval routing."""
    tag = uuid4().hex[:6].upper()

    async with async_session_factory() as session:
        # 1. Engineer
        eng = Employee(
            id=uuid4(),
            tally_id=f"ENG_{tag}",
            name=f"Engineer {tag}",
            role="ENGINEER",
            country="AE",
            is_active=True,
        )
        # 2. Supervisor
        sup = Employee(
            id=uuid4(),
            tally_id=f"SUP_V_{tag}",
            name=f"Supervisor V {tag}",
            role="SUPERVISOR",
            country="AE",
            is_active=True,
        )
        # 3. Worker
        w = Employee(
            id=uuid4(),
            tally_id=f"WRK_V_{tag}",
            name=f"Worker V {tag}",
            role="WORKER",
            country="AE",
            is_active=True,
        )
        session.add_all([eng, sup, w])
        await session.flush()

        # Legitimate link: Worker -> Supervisor
        session.add(
            EmployeeReportingLine(
                employee_id=w.id,
                manager_id=sup.id,
                relationship="SUPERVISOR",
                is_active=True,
            )
        )
        # Non-conforming direct link: Worker -> Engineer
        direct_viol_line = EmployeeReportingLine(
            employee_id=w.id,
            manager_id=eng.id,
            relationship="ENGINEER",
            is_active=True,
        )
        session.add(direct_viol_line)

        # Create user account for Engineer so we can test approval inbox
        eng_user = User(
            id=uuid4(),
            employee_id=eng.id,
            username=eng.tally_id,
            credential_hash="hash",
            role="ENGINEER",
            is_active=True,
        )
        session.add(eng_user)

        # Pending leave request for the worker
        leave = LeaveRequest(
            employee_id=w.id,
            leave_type="ANNUAL",
            from_date=date.today() + timedelta(days=5),
            to_date=date.today() + timedelta(days=7),
            reason="Annual leave",
            recorded_by_user_id=eng_user.id,
            status="REQUESTED",
        )
        session.add(leave)
        await session.commit()
        viol_line_id = direct_viol_line.id
        eng_id = eng.id
        sup_id = sup.id
        w_id = w.id

    client = await get_admin_client()
    try:
        # 1. Audit endpoint lists the violation
        res_viol = await client.get("/api/v1/employees/hierarchy-violations")
        assert res_viol.status_code == 200
        viols = res_viol.json()
        target_viol = next((v for v in viols if v["reporting_line_id"] == str(viol_line_id)), None)
        assert target_viol is not None
        assert target_viol["violation_code"] == "WORKER_DIRECT_LINK_NOT_ALLOWED"
        assert target_viol["can_move_to_supervisor"] is True
        assert target_viol["supervisor_name"] == f"Supervisor V {tag}"

        # 2. Export Excel
        res_exp = await client.get("/api/v1/employees/hierarchy-violations/export")
        assert res_exp.status_code == 200
        assert (
            res_exp.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        wb = openpyxl.load_workbook(io.BytesIO(res_exp.content))
        ws = wb.active
        assert ws is not None
        assert ws.title == "Hierarchy Violations"
        assert ws.cell(row=1, column=1).value == "Employee Tally ID"

        # 3. Action: Move to supervisor
        res_move = await client.post(
            f"/api/v1/employees/hierarchy-violations/{viol_line_id}/move-to-supervisor"
        )
        assert res_move.status_code == 200

        # Verify DB state:
        # - Direct worker -> engineer line is deactivated
        # - New supervisor -> engineer line is active
        async with async_session_factory() as session:
            old_line = await session.get(EmployeeReportingLine, viol_line_id)
            assert old_line is not None
            assert old_line.is_active is False

            sup_eng_q = select(EmployeeReportingLine).where(
                EmployeeReportingLine.employee_id == sup_id,
                EmployeeReportingLine.manager_id == eng_id,
                EmployeeReportingLine.relationship == "ENGINEER",
                EmployeeReportingLine.is_active == True,
            )
            sup_eng_line = (await session.execute(sup_eng_q)).scalar_one_or_none()
            assert sup_eng_line is not None

            # 4. Approvals routing: Engineer's inbox should still see worker's leave via inherited transitive scope!
            eng_token = AuthService.create_access_token(eng_user)
            eng_client = AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
                headers={"Authorization": f"Bearer {eng_token}"},
            )
            inbox_res = await eng_client.get("/api/v1/approvals?status=PENDING")
            assert inbox_res.status_code == 200
            inbox_data = inbox_res.json()
            assert any(item["employee_id"] == str(w_id) for item in inbox_data["leave_requests"])
            await eng_client.aclose()

    finally:
        await client.aclose()


@db_required
@pytest.mark.asyncio
async def test_propagation_on_worker_with_no_salary_row_creates_none():
    """Verify that propagate_crew_break_to_worker creates no rows if worker has no salary row."""
    tag = uuid4().hex[:6].upper()
    async with async_session_factory() as session:
        w = Employee(
            id=uuid4(),
            tally_id=f"WRK_NOSAL_{tag}",
            name=f"Worker No Sal {tag}",
            role="WORKER",
            country="AE",
            is_active=True,
        )
        session.add(w)
        await session.commit()
        w_id = w.id

    async with async_session_factory() as session:
        await PayrollSalaryService.propagate_crew_break_to_worker(
            session=session,
            worker_id=w_id,
            break_minutes=45,
            effective_from=date(2026, 11, 1),
        )
        await session.commit()

    async with async_session_factory() as session:
        q = select(EmployeeSalary).where(EmployeeSalary.employee_id == w_id)
        salaries = (await session.execute(q)).scalars().all()
        assert len(salaries) == 0, "No salary rows should be created when worker has no salary row!"


@db_required
@pytest.mark.asyncio
async def test_first_import_and_reimport_crew_break_idempotency():
    """First import of worker + supervisor-with-crew-break + salary row effective 2026-11-01
    gives exactly one salary row with imported basic and crew break.
    Running same import twice creates no new rows.
    """
    from fw.modules.imports import generate_import_template_bytes

    tag = uuid4().hex[:6].upper()
    sup_tally = f"SUP_{tag}"
    wrk_tally = f"WRK_{tag}"

    # Provision supervisor with crew break in DB
    async with async_session_factory() as session:
        sup = Employee(
            id=uuid4(),
            tally_id=sup_tally,
            name=f"Supervisor {tag}",
            role="SUPERVISOR",
            country="AE",
            is_active=True,
            break_override_minutes=45,
        )
        session.add(sup)
        await session.commit()

    # Build Excel file with Worker in Employees, reporting line, and salary row
    wb = openpyxl.load_workbook(io.BytesIO(generate_import_template_bytes()))

    # Employees sheet
    ws_emp = wb["Employees"]
    ws_emp.cell(row=5, column=1, value="")
    ws_emp.cell(row=5, column=2, value=wrk_tally)
    ws_emp.cell(row=5, column=3, value=f"Worker {tag}")
    ws_emp.cell(row=5, column=4, value="WORKER")
    ws_emp.cell(row=5, column=5, value="G1C")
    ws_emp.cell(row=5, column=6, value="Gardener Helper")
    ws_emp.cell(row=5, column=7, value="AE")
    ws_emp.cell(row=5, column=10, value="")

    # Employee_Reporting sheet
    ws_rep = wb["Employee_Reporting"]
    ws_rep.cell(row=5, column=1, value="")
    ws_rep.cell(row=5, column=2, value=wrk_tally)
    ws_rep.cell(row=5, column=3, value=sup_tally)
    ws_rep.cell(row=5, column=4, value="SUPERVISOR")

    # Employee_Salary sheet (effective 2026-11-01, basic 1500.00, break_minutes omitted)
    ws_sal = wb["Employee_Salary"]
    ws_sal.cell(row=5, column=1, value="")
    ws_sal.cell(row=5, column=2, value=wrk_tally)
    ws_sal.cell(row=5, column=3, value="2026-11-01")
    ws_sal.cell(row=5, column=4, value="8.0")
    ws_sal.cell(row=5, column=5, value="1500.00")

    buf = io.BytesIO()
    wb.save(buf)
    file_bytes = buf.getvalue()

    client = await get_admin_client()
    try:
        # Pass 1: First upload and commit
        files = {
            "file": (
                "import_batch4.xlsx",
                file_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }
        res1 = await client.post(
            "/api/v1/imports?sheets=Employees,Employee_Reporting,Employee_Salary",
            files=files,
        )
        assert res1.status_code == 201
        batch1 = res1.json()
        assert batch1["status"] == "PREVIEWED"
        assert batch1["can_commit"] is True

        com1 = await client.post(f"/api/v1/imports/{batch1['batch_id']}/commit")
        assert com1.status_code == 200

        # Verify DB state after Pass 1: exactly 1 salary row with basic 1500.00 and break 45
        async with async_session_factory() as session:
            emp = (await session.execute(select(Employee).where(Employee.tally_id == wrk_tally))).scalar_one()
            sal_rows = (
                await session.execute(
                    select(EmployeeSalary).where(EmployeeSalary.employee_id == emp.id)
                )
            ).scalars().all()
            assert len(sal_rows) == 1, f"Expected exactly 1 salary row, got {len(sal_rows)}"
            assert sal_rows[0].basic_salary == Decimal("1500.00")
            assert sal_rows[0].break_minutes == 45
            assert sal_rows[0].effective_from == date(2026, 11, 1)

        # Pass 2: Re-run the exact same import
        files2 = {
            "file": (
                "import_batch4.xlsx",
                file_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }
        res2 = await client.post(
            "/api/v1/imports?sheets=Employees,Employee_Reporting,Employee_Salary",
            files=files2,
        )
        assert res2.status_code == 201
        batch2 = res2.json()
        com2 = await client.post(f"/api/v1/imports/{batch2['batch_id']}/commit")
        assert com2.status_code == 200

        # Verify DB state after Pass 2: still exactly 1 salary row
        async with async_session_factory() as session:
            emp = (await session.execute(select(Employee).where(Employee.tally_id == wrk_tally))).scalar_one()
            sal_rows = (
                await session.execute(
                    select(EmployeeSalary).where(EmployeeSalary.employee_id == emp.id)
                )
            ).scalars().all()
            assert len(sal_rows) == 1, f"Running same import twice should create no new rows, got {len(sal_rows)}"
            assert sal_rows[0].basic_salary == Decimal("1500.00")
            assert sal_rows[0].break_minutes == 45
    finally:
        await client.aclose()


@db_required
@pytest.mark.asyncio
async def test_reimport_worker_with_new_supervisor():
    """When a worker's supervisor changes via import:
    - Preview shows action UPDATE (old supervisor -> new supervisor)
    - Commit deactivates old active supervisor link (is_active=False, deactivated_at/by, audit log)
    - Re-import succeeds without error!
    """
    from fw.modules.imports import generate_import_template_bytes

    tag = uuid4().hex[:6].upper()
    sup1_tally = f"SUP1_{tag}"
    sup2_tally = f"SUP2_{tag}"
    wrk_tally = f"WRK_SW_{tag}"

    # Provision supervisor 1 and worker with active reporting link
    async with async_session_factory() as session:
        sup1 = Employee(
            id=uuid4(),
            tally_id=sup1_tally,
            name=f"Supervisor One {tag}",
            role="SUPERVISOR",
            country="AE",
            is_active=True,
        )
        sup2 = Employee(
            id=uuid4(),
            tally_id=sup2_tally,
            name=f"Supervisor Two {tag}",
            role="SUPERVISOR",
            country="AE",
            is_active=True,
        )
        w = Employee(
            id=uuid4(),
            tally_id=wrk_tally,
            name=f"Worker Switch {tag}",
            role="WORKER",
            country="AE",
            is_active=True,
        )
        session.add_all([sup1, sup2, w])
        await session.flush()

        rep = EmployeeReportingLine(
            employee_id=w.id,
            manager_id=sup1.id,
            relationship="SUPERVISOR",
            is_active=True,
        )
        session.add(rep)
        await session.commit()
        w_id = w.id
        sup1_id = sup1.id
        sup2_id = sup2.id
        old_rep_id = rep.id

    wb = openpyxl.load_workbook(io.BytesIO(generate_import_template_bytes()))

    # Re-import Employee_Reporting with new supervisor SUP2
    ws_rep = wb["Employee_Reporting"]
    ws_rep.cell(row=5, column=1, value="")
    ws_rep.cell(row=5, column=2, value=wrk_tally)
    ws_rep.cell(row=5, column=3, value=sup2_tally)
    ws_rep.cell(row=5, column=4, value="SUPERVISOR")

    buf = io.BytesIO()
    wb.save(buf)
    file_bytes = buf.getvalue()

    client = await get_admin_client()
    try:
        files = {
            "file": (
                "switch_sup.xlsx",
                file_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }
        res = await client.post("/api/v1/imports?sheets=Employee_Reporting", files=files)
        assert res.status_code == 201
        data = res.json()
        assert data["status"] == "PREVIEWED"
        assert data["can_commit"] is True

        # Check preview rows for Employee_Reporting
        rep_rows_res = await client.get(
            f"/api/v1/imports/{data['batch_id']}/preview?sheet=Employee_Reporting"
        )
        assert rep_rows_res.status_code == 200
        rep_rows = rep_rows_res.json()["rows"]
        assert len(rep_rows) == 1
        assert rep_rows[0]["action"] == "UPDATED"

        # Commit switch
        commit_res = await client.post(f"/api/v1/imports/{data['batch_id']}/commit")
        assert commit_res.status_code == 200
        assert commit_res.json()["status"] == "COMMITTED"

        # Verify DB state:
        # - Old line is deactivated
        # - New line is active
        async with async_session_factory() as session:
            old_line = await session.get(EmployeeReportingLine, old_rep_id)
            assert old_line is not None
            assert old_line.is_active is False
            assert old_line.deactivated_at is not None

            new_line_q = select(EmployeeReportingLine).where(
                EmployeeReportingLine.employee_id == w_id,
                EmployeeReportingLine.manager_id == sup2_id,
                EmployeeReportingLine.relationship == "SUPERVISOR",
                EmployeeReportingLine.is_active == True,
            )
            new_line = (await session.execute(new_line_q)).scalar_one_or_none()
            assert new_line is not None
    finally:
        await client.aclose()
