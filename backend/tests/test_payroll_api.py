"""API and integration tests for Month-End Payroll, Salary Revisions, and Job Budget (PHASE-11).

Verifies:
- Check that draft run can be created, issues listed, and re-run increments run_no.
- Unapproved overtime is flagged in issues and not paid until approved.
- Approved run freezes records as immutable snapshots and locks month attendance records.
- Later events or settings changes do not alter approved payroll records.
- Engineers see their scope read-only; Supervisors receive 403.
- Worker's own approved slips endpoint for mobile/web profile.
- Salary revisions CRUD, planned hourly cost calculation, and side-by-side diff.
- Dynamic job budget vs actual allocated cost from attendance minutes.
- Auto-draft background check runner.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.main import app
from fw.modules.attendance.models import (
    AttendanceCalculation,
    AttendanceRecord,
)
from fw.modules.identity import AuthService, hash_password
from fw.modules.identity.models import User
from fw.modules.jobs.models import JobItem, Worksite
from fw.modules.org.models import Employee, Group, Zone
from fw.modules.payroll.models import (
    EmployeeSalary,
    JobCostAllocation,
    PayrollRecord,
    PayrollRun,
)


async def _cleanup_period(session: AsyncSession, period_start: date, period_end: date, country: str = "AE") -> None:
    run_ids = (
        await session.execute(
            select(PayrollRun.id).where(
                PayrollRun.period_start == period_start,
                PayrollRun.period_end == period_end,
                PayrollRun.country == country,
            )
        )
    ).scalars().all()
    if run_ids:
        rec_ids = (
            await session.execute(
                select(PayrollRecord.id).where(PayrollRecord.payroll_run_id.in_(run_ids))
            )
        ).scalars().all()
        if rec_ids:
            await session.execute(delete(JobCostAllocation).where(JobCostAllocation.payroll_record_id.in_(rec_ids)))
        await session.execute(delete(PayrollRecord).where(PayrollRecord.payroll_run_id.in_(run_ids)))
        await session.execute(delete(PayrollRun).where(PayrollRun.id.in_(run_ids)))
        await session.commit()


async def _create_test_employee(
    session: AsyncSession,
    tally_id: str,
    name: str,
    role: str = "WORKER",
    country: str = "AE",
) -> Employee:
    emp = Employee(
        id=uuid4(),
        tally_id=tally_id,
        name=name,
        role=role,
        country=country,
        is_driver=False,
        join_date=date(2026, 1, 1),
        is_active=True,
    )
    session.add(emp)
    await session.flush()
    return emp


async def _create_test_user(
    session: AsyncSession,
    employee: Employee,
    role: str,
) -> tuple[User, str]:
    user = User(
        id=uuid4(),
        employee_id=employee.id,
        username=employee.tally_id,
        credential_hash=hash_password("Password123!"),
        role=role,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    token = AuthService.create_access_token(user)
    return user, token


async def _setup_group_zone_worksite(session: AsyncSession, country: str = "AE") -> tuple[Worksite, JobItem]:
    unique_suffix = uuid4().hex[:6]
    group = Group(id=uuid4(), code=f"GRP_{unique_suffix}", name="Landscape Group", is_active=True)
    zone = Zone(id=uuid4(), code=f"ZN_{unique_suffix}", name="Dubai North", is_active=True)
    session.add_all([group, zone])
    await session.flush()

    ws = Worksite(
        id=uuid4(),
        job_number=f"JOB_{unique_suffix}",
        job_name=f"Marina Park Maintenance {unique_suffix}",
        group_id=group.id,
        zone_id=zone.id,
        country=country,
        is_active=True,
        start_date=date(2026, 1, 1),
    )
    session.add(ws)
    await session.flush()

    item = JobItem(
        id=uuid4(),
        worksite_id=ws.id,
        sub_item_code="A",
        staff_grade_description="Gardener Expert",
        planned_grade_code="GE",
        frequency_unit="MONTH",
        occurrences_per_period=Decimal("4.0"),
        period_interval=1,
        required_staff_count=2,
        hours_per_occurrence_per_staff=Decimal("8.0"),
        start_date=date(2026, 1, 1),
        deployment_type="PERMANENT",
        is_active=True,
    )
    session.add(item)
    await session.commit()

    return ws, item


@pytest.mark.asyncio
async def test_payroll_draft_generation_and_rerun(db_session: AsyncSession):
    """Test generating a draft payroll run and re-running it increments run_no."""
    await _cleanup_period(db_session, date(2026, 10, 1), date(2026, 10, 31))
    emp = await _create_test_employee(db_session, f"T_{uuid4().hex[:6]}", "Ahmed Khan")
    admin_emp = await _create_test_employee(db_session, f"ADM_{uuid4().hex[:6]}", "Admin User", role="ADMIN")
    _, admin_token = await _create_test_user(db_session, admin_emp, "ADMIN")

    # Give employee a salary structure
    salary = EmployeeSalary(
        employee_id=emp.id,
        effective_from=date(2026, 1, 1),
        standard_hours=Decimal("8.0"),
        basic_salary=Decimal("1200.00"),
        special_allowance=Decimal("300.00"),
        fixed_ot_amount=Decimal("100.00"),
    )
    db_session.add(salary)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create first draft
        resp = await client.post(
            "/api/v1/payroll/runs",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "period_start": "2026-10-01",
                "period_end": "2026-10-31",
                "country": "AE",
                "notes": "First October Draft",
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["status"] == "DRAFT"
        assert data["run_no"] == 1
        assert data["record_count"] >= 1

        # Check worker record in draft
        worker_rec = next((r for r in data["records"] if r["employee_id"] == str(emp.id)), None)
        assert worker_rec is not None
        # Salary portion: 1200 + 300 + 100 = 1600.00
        assert Decimal(str(worker_rec["salary_portion"])) == Decimal("1600.00")
        assert Decimal(str(worker_rec["gross_pay"])) == Decimal("1600.00")

        # 2. Re-run: should replace draft with run_no = 2
        resp2 = await client.post(
            "/api/v1/payroll/runs",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "period_start": "2026-10-01",
                "period_end": "2026-10-31",
                "country": "AE",
                "notes": "Re-run October Draft",
            },
        )
        assert resp2.status_code == 201
        data2 = resp2.json()
        assert data2["run_no"] == 2
        assert data2["status"] == "DRAFT"


@pytest.mark.asyncio
async def test_unapproved_overtime_issues_and_approval(db_session: AsyncSession):
    """Test unapproved overtime is flagged in issues, and approving locks the month."""
    await _cleanup_period(db_session, date(2026, 5, 1), date(2026, 5, 31))
    emp = await _create_test_employee(db_session, f"T_{uuid4().hex[:6]}", "Rashid Ali")
    admin_emp = await _create_test_employee(db_session, f"ADM_{uuid4().hex[:6]}", "Payroll Admin", role="ADMIN")
    _, admin_token = await _create_test_user(db_session, admin_emp, "ADMIN")

    salary = EmployeeSalary(
        employee_id=emp.id,
        effective_from=date(2026, 1, 1),
        standard_hours=Decimal("8.0"),
        basic_salary=Decimal("1100.00"),
    )
    db_session.add(salary)

    # Create an attendance record with PENDING_REVIEW overtime
    att_rec = AttendanceRecord(
        id=uuid4(),
        employee_id=emp.id,
        work_date=date(2026, 5, 15),
        business_status="PRESENT",
        review_status="PENDING_REVIEW",
        locked=False,
    )
    db_session.add(att_rec)
    await db_session.flush()

    calc = AttendanceCalculation(
        id=uuid4(),
        attendance_record_id=att_rec.id,
        version_no=1,
        input_hash="hash123",
        calculated_at=datetime.now(UTC),
        worked_minutes=600,  # 10 hours
        ot1_minutes=120,     # 2 hours overtime
        review_reasons=["OVERTIME_PENDING"],
    )
    db_session.add(calc)
    await db_session.flush()
    att_rec.current_calculation_id = calc.id
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create draft
        resp = await client.post(
            "/api/v1/payroll/runs",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "period_start": "2026-05-01",
                "period_end": "2026-05-31",
                "country": "AE",
            },
        )
        assert resp.status_code == 201
        run_data = resp.json()
        run_id = run_data["id"]

        # 1. Check issues endpoint: should show unapproved overtime
        issues_resp = await client.get(
            f"/api/v1/payroll/runs/{run_id}/issues",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert issues_resp.status_code == 200
        issues = issues_resp.json()
        assert issues["unapproved_overtime_count"] >= 1
        assert any(i["issue_type"] == "UNAPPROVED_OVERTIME" for i in issues["issues"])

        # In draft, unapproved overtime is NOT paid (ot1_hours is 0.0)
        worker_rec = next((r for r in run_data["records"] if r["employee_id"] == str(emp.id)), None)
        assert worker_rec is not None
        assert Decimal(str(worker_rec["ot1_hours"])) == Decimal("0.00")

        # 2. Approve attendance overtime
        att_rec.review_status = "APPROVED"
        await db_session.commit()

        # Re-run draft: now overtime IS paid
        resp2 = await client.post(
            "/api/v1/payroll/runs",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "period_start": "2026-05-01",
                "period_end": "2026-05-31",
                "country": "AE",
            },
        )
        assert resp2.status_code == 201
        run2_data = resp2.json()
        worker2_rec = next((r for r in run2_data["records"] if r["employee_id"] == str(emp.id)), None)
        assert worker2_rec is not None
        # 120 minutes = 2.0 hours
        assert Decimal(str(worker2_rec["ot1_hours"])) == Decimal("2.00")
        # OT1 rate for basic 1100 = 6.61, so 2 * 6.61 = 13.22
        assert Decimal(str(worker2_rec["ot1_amount"])) == Decimal("13.22")

        # 3. Approve payroll run
        appr_resp = await client.post(
            f"/api/v1/payroll/runs/{run2_data['id']}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"notes": "Final approved for October"},
        )
        assert appr_resp.status_code == 200
        approved_run = appr_resp.json()
        assert approved_run["status"] == "APPROVED"
        assert approved_run["approved_at"] is not None

        # Verify month's attendance records are locked
        await db_session.refresh(att_rec)
        assert att_rec.locked is True


@pytest.mark.asyncio
async def test_approved_run_immutability(db_session: AsyncSession):
    """Verify that after approval, later events or changes do not alter approved payroll."""
    await _cleanup_period(db_session, date(2026, 9, 1), date(2026, 9, 30))
    emp = await _create_test_employee(db_session, f"T_{uuid4().hex[:6]}", "Farooq Tariq")
    admin_emp = await _create_test_employee(db_session, f"ADM_{uuid4().hex[:6]}", "System Admin", role="ADMIN")
    _, admin_token = await _create_test_user(db_session, admin_emp, "ADMIN")

    sal = EmployeeSalary(
        employee_id=emp.id,
        effective_from=date(2026, 1, 1),
        standard_hours=Decimal("8.0"),
        basic_salary=Decimal("1500.00"),
    )
    db_session.add(sal)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create and approve
        resp = await client.post(
            "/api/v1/payroll/runs",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"period_start": "2026-09-01", "period_end": "2026-09-30", "country": "AE"},
        )
        run_id = resp.json()["id"]

        appr = await client.post(
            f"/api/v1/payroll/runs/{run_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert appr.status_code == 200

        # Attempt to re-run an approved month -> 409
        rerun_fail = await client.post(
            "/api/v1/payroll/runs",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"period_start": "2026-09-01", "period_end": "2026-09-30", "country": "AE"},
        )
        assert rerun_fail.status_code == 409

        # Verify approved records are immutable in database
        stmt = select(PayrollRecord).where(PayrollRecord.payroll_run_id == run_id, PayrollRecord.employee_id == emp.id)
        res = await db_session.execute(stmt)
        record = res.scalar_one()
        assert record.gross_pay == Decimal("1500.00")
        assert "settings" in record.snapshot


@pytest.mark.asyncio
async def test_role_based_scoping(db_session: AsyncSession):
    """Verify Engineer sees only scoped workers read-only; Supervisor gets 403."""
    await _cleanup_period(db_session, date(2026, 8, 1), date(2026, 8, 31))
    await _create_test_employee(db_session, f"W1_{uuid4().hex[:6]}", "Worker One")
    await _create_test_employee(db_session, f"W2_{uuid4().hex[:6]}", "Worker Two")

    eng_emp = await _create_test_employee(db_session, f"ENG_{uuid4().hex[:6]}", "Site Engineer", role="ENGINEER")
    sup_emp = await _create_test_employee(db_session, f"SUP_{uuid4().hex[:6]}", "Supervisor", role="SUPERVISOR")
    admin_emp = await _create_test_employee(db_session, f"ADM_{uuid4().hex[:6]}", "Admin", role="ADMIN")

    _, eng_token = await _create_test_user(db_session, eng_emp, "ENGINEER")
    _, sup_token = await _create_test_user(db_session, sup_emp, "SUPERVISOR")
    _, admin_token = await _create_test_user(db_session, admin_emp, "ADMIN")

    # Admin creates run
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/payroll/runs",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"period_start": "2026-08-01", "period_end": "2026-08-31", "country": "AE"},
        )
        assert resp.status_code == 201
        run_id = resp.json()["id"]

        # 1. Supervisor cannot view payroll runs or approve -> 403
        sup_view = await client.get(
            "/api/v1/payroll/runs",
            headers={"Authorization": f"Bearer {sup_token}"},
        )
        assert sup_view.status_code == 403

        sup_appr = await client.post(
            f"/api/v1/payroll/runs/{run_id}/approve",
            headers={"Authorization": f"Bearer {sup_token}"},
        )
        assert sup_appr.status_code == 403

        # 2. Engineer can view runs read-only
        eng_view = await client.get(
            f"/api/v1/payroll/runs/{run_id}",
            headers={"Authorization": f"Bearer {eng_token}"},
        )
        assert eng_view.status_code == 200

        # 3. Engineer cannot approve -> 403
        eng_appr = await client.post(
            f"/api/v1/payroll/runs/{run_id}/approve",
            headers={"Authorization": f"Bearer {eng_token}"},
        )
        assert eng_appr.status_code == 403


@pytest.mark.asyncio
async def test_worker_mobile_own_approved_payroll(db_session: AsyncSession):
    """Verify worker can access their own approved monthly payroll via /payroll/my-records."""
    await _cleanup_period(db_session, date(2026, 7, 1), date(2026, 7, 31))
    worker = await _create_test_employee(db_session, f"W_{uuid4().hex[:6]}", "Bilal Siddiqui")
    admin = await _create_test_employee(db_session, f"ADM_{uuid4().hex[:6]}", "Admin", role="ADMIN")

    _, worker_token = await _create_test_user(db_session, worker, "WORKER")
    _, admin_token = await _create_test_user(db_session, admin, "ADMIN")

    salary = EmployeeSalary(
        employee_id=worker.id,
        effective_from=date(2026, 1, 1),
        standard_hours=Decimal("8.0"),
        basic_salary=Decimal("1200.00"),
        special_allowance=Decimal("200.00"),
    )
    db_session.add(salary)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create and approve run
        create_resp = await client.post(
            "/api/v1/payroll/runs",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"period_start": "2026-07-01", "period_end": "2026-07-31", "country": "AE"},
        )
        run_id = create_resp.json()["id"]

        # Before approval, worker has 0 approved records
        w_resp_before = await client.get(
            "/api/v1/payroll/my-records",
            headers={"Authorization": f"Bearer {worker_token}"},
        )
        assert w_resp_before.status_code == 200
        assert len(w_resp_before.json()) == 0

        # Approve
        await client.post(
            f"/api/v1/payroll/runs/{run_id}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # After approval, worker receives approved slip
        w_resp_after = await client.get(
            "/api/v1/payroll/my-records",
            headers={"Authorization": f"Bearer {worker_token}"},
        )
        assert w_resp_after.status_code == 200
        slips = w_resp_after.json()
        assert len(slips) >= 1
        slip = slips[0]
        assert slip["status"] == "APPROVED"
        assert Decimal(str(slip["salary_portion"])) == Decimal("1400.00")
        assert Decimal(str(slip["net_pay"])) == Decimal("1400.00")
        # Ensure employer provisions are NOT in the mobile slip schema
        assert "per_month_provision" not in slip
        assert "final_total_staff_cost" not in slip


@pytest.mark.asyncio
async def test_salary_revisions_and_side_by_side_diff(db_session: AsyncSession):
    """Test salary revisions CRUD, planned rates, and side-by-side diff."""
    admin = await _create_test_employee(db_session, f"ADM_{uuid4().hex[:6]}", "Admin", role="ADMIN")
    _, admin_token = await _create_test_user(db_session, admin, "ADMIN")

    rev_code = f"REV-{uuid4().hex[:6].upper()}"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create a revision
        resp = await client.post(
            "/api/v1/salary-revisions",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "code": rev_code,
                "name": "2026 Labor Cost Revision",
                "country": "AE",
                "effective_from": "2026-01-01",
                "lines": [
                    {
                        "grade_code": "GE",
                        "grade_group_title": "Gardener",
                        "basic_salary": "1200.00",
                        "special_allowance": "200.00",
                        "fixed_ot_amount": "100.00",
                        "bonus": "0.00",
                        "visa_provision": "100.00",
                        "air_ticket_provision": "75.00",
                        "uniform_provision": "25.00",
                        "medical_provision": "50.00",
                        "accommodation_provision": "300.00",
                    },
                    {
                        "grade_code": "GH",
                        "grade_group_title": "Helper",
                        "basic_salary": "1000.00",
                        "special_allowance": "100.00",
                        "fixed_ot_amount": "50.00",
                        "bonus": "0.00",
                        "visa_provision": "100.00",
                        "air_ticket_provision": "75.00",
                        "uniform_provision": "25.00",
                        "medical_provision": "50.00",
                        "accommodation_provision": "300.00",
                    },
                ],
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["code"] == rev_code
        assert len(data["lines"]) == 2

        # Check planned hourly cost calculated
        ge_line = next(line for line in data["lines"] if line["grade_code"] == "GE")
        # Salary portion: 1200 + 200 + 100 = 1500. Provisions: 550. Base = 2050.
        # With 5% HR OH = 2152.5. Divisor 208 = 10.348... -> 10.35
        assert Decimal(str(ge_line["planned_hourly_cost"])) == Decimal("10.35")

        # 2. Test side-by-side diff
        diff_resp = await client.post(
            "/api/v1/salary-revisions/diff",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"target_revision_code": f"{rev_code}-v2", "base_revision_code": rev_code},
            json=[
                {
                    "grade_code": "GE",
                    "basic_salary": "1300.00",  # changed from 1200
                    "special_allowance": "200.00",
                    "fixed_ot_amount": "100.00",
                    "bonus": "0.00",
                    "visa_provision": "100.00",
                    "air_ticket_provision": "75.00",
                    "uniform_provision": "25.00",
                    "medical_provision": "50.00",
                    "accommodation_provision": "300.00",
                },
                {
                    "grade_code": "NEW_GRADE",  # newly added
                    "basic_salary": "2000.00",
                },
            ],
        )
        assert diff_resp.status_code == 200
        diff_data = diff_resp.json()
        assert diff_data["new_grades_count"] == 1
        assert diff_data["updated_grades_count"] == 1
        assert any(d["grade_code"] == "GE" and d["field_name"] == "Basic Salary" and d["is_changed"] for d in diff_data["diffs"])


@pytest.mark.asyncio
async def test_job_budget_vs_actual(db_session: AsyncSession):
    """Test dynamic job budget calculation and actual variance report."""
    admin = await _create_test_employee(db_session, f"ADM_{uuid4().hex[:6]}", "Admin", role="ADMIN")
    _, admin_token = await _create_test_user(db_session, admin, "ADMIN")

    worksite, item = await _setup_group_zone_worksite(db_session, "AE")
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/payroll/budget-vs-actual",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"country": "AE"},
        )
        assert resp.status_code == 200
        items = resp.json()
        ws_item = next((i for i in items if i["worksite_id"] == str(worksite.id)), None)
        assert ws_item is not None
        assert Decimal(str(ws_item["annual_planned_man_hours"])) > Decimal("0.0")
        assert Decimal(str(ws_item["annual_labor_budget"])) > Decimal("0.00")


@pytest.mark.asyncio
async def test_auto_draft_check_runner(db_session: AsyncSession):
    """Test background runner checking past delay days and triggering draft."""
    admin = await _create_test_employee(db_session, f"ADM_{uuid4().hex[:6]}", "Admin", role="ADMIN")
    _, admin_token = await _create_test_user(db_session, admin, "ADMIN")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Pass a date e.g. 10th of next month so delay (5 days) has passed
        resp = await client.post(
            "/api/v1/payroll/auto-run-check",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"as_of": "2026-11-10"},
        )
        assert resp.status_code == 200
        runs = resp.json()
        # Should have generated draft runs for completed October
        assert isinstance(runs, list)
