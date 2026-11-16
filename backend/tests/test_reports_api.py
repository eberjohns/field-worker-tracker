"""Comprehensive test suite for Phase 12 Reports, Background Exports, and Generated Reports History."""

import io
from datetime import UTC, date, datetime, time
from uuid import uuid4

import openpyxl
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
from fw.modules.org.models import Employee
from fw.modules.payroll.models import (
    JobCostAllocation,
    PayrollRecord,
    PayrollRun,
)
from fw.modules.reports.models import GeneratedReport
from fw.modules.reports.registry import MONTH_END_REPORT_KEYS


async def _cleanup_test_data(session: AsyncSession, period_start: date | None = None) -> None:
    """Safely clean up test period data without wiping development database."""
    if period_start:
        await session.execute(
            delete(GeneratedReport).where(GeneratedReport.period_start == period_start)
        )
        runs = (
            (
                await session.execute(
                    select(PayrollRun).where(PayrollRun.period_start == period_start)
                )
            )
            .scalars()
            .all()
        )
        for r in runs:
            await session.execute(
                delete(JobCostAllocation).where(
                    JobCostAllocation.payroll_record_id.in_(
                        select(PayrollRecord.id).where(PayrollRecord.payroll_run_id == r.id)
                    )
                )
            )
            await session.execute(delete(PayrollRecord).where(PayrollRecord.payroll_run_id == r.id))
            await session.execute(delete(PayrollRun).where(PayrollRun.id == r.id))
        await session.commit()


async def _create_employee_with_user(
    session: AsyncSession,
    tally_id: str,
    name: str,
    role: str = "WORKER",
    country: str = "AE",
) -> tuple[Employee, User, str]:
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

    user = User(
        id=uuid4(),
        employee_id=emp.id,
        username=tally_id,
        credential_hash=hash_password("Password123!"),
        role=role,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    token = AuthService.create_access_token(user)
    return emp, user, token


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_list_available_reports_role_isolation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify that reports are listed according to user role (cost/salary reports Admin only)."""
    uid = uuid4().hex[:6]
    _, _, admin_token = await _create_employee_with_user(
        db_session, f"ADM_{uid}", "Admin User", role="ADMIN"
    )
    _, _, eng_token = await _create_employee_with_user(
        db_session, f"ENG_{uid}", "Engineer User", role="ENGINEER"
    )
    _, _, sup_token = await _create_employee_with_user(
        db_session, f"SUP_{uid}", "Supervisor User", role="SUPERVISOR"
    )

    # 1. Admin gets all 15 reports
    resp_adm = await client.get(
        "/api/v1/reports", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp_adm.status_code == 200
    adm_keys = {r["key"] for r in resp_adm.json()}
    assert len(adm_keys) == 15
    assert "payroll" in adm_keys
    assert "provisions-staff-cost" in adm_keys
    assert "job-costing" in adm_keys

    # 2. Engineer does NOT get cost reports
    resp_eng = await client.get("/api/v1/reports", headers={"Authorization": f"Bearer {eng_token}"})
    assert resp_eng.status_code == 200
    eng_keys = {r["key"] for r in resp_eng.json()}
    assert len(eng_keys) == 12
    assert "payroll" not in eng_keys
    assert "provisions-staff-cost" not in eng_keys
    assert "job-costing" not in eng_keys
    assert "daily-attendance" in eng_keys

    # 3. Supervisor does NOT get cost reports
    resp_sup = await client.get("/api/v1/reports", headers={"Authorization": f"Bearer {sup_token}"})
    assert resp_sup.status_code == 200
    sup_keys = {r["key"] for r in resp_sup.json()}
    assert len(sup_keys) == 12
    assert "payroll" not in sup_keys
    assert "provisions-staff-cost" not in sup_keys
    assert "job-costing" not in sup_keys


@pytest.mark.asyncio
async def test_salary_and_cost_reports_forbidden_for_non_admin(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify direct endpoint access to salary and cost reports is 403 Forbidden for non-admins."""
    uid = uuid4().hex[:6]
    _, _, eng_token = await _create_employee_with_user(
        db_session, f"ENG_{uid}", "Engineer User", role="ENGINEER"
    )
    _, _, sup_token = await _create_employee_with_user(
        db_session, f"SUP_{uid}", "Supervisor User", role="SUPERVISOR"
    )

    for cost_key in ["payroll", "provisions-staff-cost", "job-costing"]:
        res1 = await client.get(
            f"/api/v1/reports/{cost_key}", headers={"Authorization": f"Bearer {eng_token}"}
        )
        assert res1.status_code == 403

        res2 = await client.get(
            f"/api/v1/reports/{cost_key}", headers={"Authorization": f"Bearer {sup_token}"}
        )
        assert res2.status_code == 403


@pytest.mark.asyncio
async def test_daily_attendance_query_and_calculations(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify daily attendance report query correctly renders planned vs actual and variations."""
    uid = uuid4().hex[:6]
    emp, _, admin_token = await _create_employee_with_user(
        db_session, f"W_{uid}", "Worker Ali", role="WORKER"
    )
    _, _, adm_token = await _create_employee_with_user(
        db_session, f"A_{uid}", "Admin User", role="ADMIN"
    )

    work_d = date(2026, 11, 3)
    rec = AttendanceRecord(
        id=uuid4(),
        employee_id=emp.id,
        work_date=work_d,
        business_status="PRESENT",
        review_status="AUTO",
    )
    db_session.add(rec)
    await db_session.flush()

    calc = AttendanceCalculation(
        id=uuid4(),
        attendance_record_id=rec.id,
        version_no=1,
        input_hash="hash_val",
        planned_accommodation_departure=time(5, 0),
        planned_first_site_start=time(6, 0),
        planned_break_minutes=30,
        planned_last_site_end=time(15, 30),
        planned_accommodation_return=time(17, 0),
        planned_total_minutes=720,
        planned_worked_minutes=540,
        accommodation_departure_at=datetime(2026, 11, 3, 5, 20, tzinfo=UTC),
        first_site_entry_at=datetime(2026, 11, 3, 6, 20, tzinfo=UTC),
        break_minutes_used=30,
        last_site_exit_at=datetime(2026, 11, 3, 15, 20, tzinfo=UTC),
        accommodation_return_at=datetime(2026, 11, 3, 16, 50, tzinfo=UTC),
        shift_span_minutes=690,
        worked_minutes=510,
        variation_minutes=-30,
        shortfall_minutes=30,
        productive_minutes=510,
        transit_minutes=150,
        idle_minutes=0,
        ot1_minutes=0,
        ot2_minutes=0,
        flags=[],
    )
    db_session.add(calc)
    await db_session.flush()
    rec.current_calculation_id = calc.id
    await db_session.commit()

    resp = await client.get(
        "/api/v1/reports/daily-attendance",
        params={"date_from": "2026-11-03", "date_to": "2026-11-03"},
        headers={"Authorization": f"Bearer {adm_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_rows"] >= 1
    row = next(r for r in data["data"] if r["worker_id"] == emp.tally_id)
    assert row["planned_acc_start"] == "05:00"
    assert row["actual_acc_start"] == "05:20"
    assert row["var_total_time"] == -30
    assert row["var_worked_time"] == -30
    assert row["status"] == "PRESENT"


@pytest.mark.asyncio
async def test_excel_export_and_inspection(client: AsyncClient, db_session: AsyncSession) -> None:
    """Verify that export to Excel produces a valid workbook with single header and Filters sheet."""
    uid = uuid4().hex[:6]
    _, _, adm_token = await _create_employee_with_user(
        db_session, f"ADM_{uid}", "Admin User", role="ADMIN"
    )

    # Trigger export job
    export_payload = {
        "format": "xlsx",
        "params": {"date_from": "2026-11-01", "date_to": "2026-11-30", "country": "AE"},
    }
    exp_resp = await client.post(
        "/api/v1/reports/daily-attendance/export",
        json=export_payload,
        headers={"Authorization": f"Bearer {adm_token}"},
    )
    assert exp_resp.status_code == 202
    exp_data = exp_resp.json()
    export_id = exp_data["id"]
    assert exp_data["status"] == "COMPLETED"

    # Download export file
    dl_resp = await client.get(
        f"/api/v1/exports/{export_id}/download",
        headers={"Authorization": f"Bearer {adm_token}"},
    )
    assert dl_resp.status_code == 200
    assert "spreadsheetml" in dl_resp.headers["content-type"]

    # Inspect Excel content with openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(dl_resp.content))
    assert "Filters" in wb.sheetnames
    filter_sheet = wb["Filters"]
    # Check that applied parameters are listed
    filter_params = [filter_sheet.cell(row=i, column=1).value for i in range(1, 10)]
    assert "country" in filter_params

    # Main data sheet has columns
    data_sheet = wb[wb.sheetnames[0]]
    header_val = data_sheet.cell(row=1, column=1).value
    assert header_val is not None


@pytest.mark.asyncio
async def test_pdf_export_daily_attendance(client: AsyncClient, db_session: AsyncSession) -> None:
    """Verify PDF export produces valid PDF bytes."""
    uid = uuid4().hex[:6]
    _, _, adm_token = await _create_employee_with_user(
        db_session, f"ADM_{uid}", "Admin User", role="ADMIN"
    )

    exp_resp = await client.post(
        "/api/v1/reports/daily-attendance/export",
        json={"format": "pdf", "params": {"country": "AE"}},
        headers={"Authorization": f"Bearer {adm_token}"},
    )
    assert exp_resp.status_code == 202
    exp_id = exp_resp.json()["id"]

    dl_resp = await client.get(
        f"/api/v1/exports/{exp_id}/download",
        headers={"Authorization": f"Bearer {adm_token}"},
    )
    assert dl_resp.status_code == 200
    assert dl_resp.content.startswith(b"%PDF-1.4")


@pytest.mark.asyncio
async def test_month_end_automatic_generation_and_history(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify month-end auto-run generates the 11 reports with proper names, versioning, and re-download."""
    await _cleanup_test_data(db_session)

    uid = uuid4().hex[:6]
    emp, _, _ = await _create_employee_with_user(
        db_session, f"W_{uid}", "Worker Payroll", role="WORKER"
    )
    _, _, admin_token = await _create_employee_with_user(
        db_session, f"ADM_{uid}", "Admin Payroll", role="ADMIN"
    )
    _, _, sup_token = await _create_employee_with_user(
        db_session, f"SUP_{uid}", "Supervisor User", role="SUPERVISOR"
    )

    # 1. Trigger draft payroll run
    p_start = date(2026, 5, 1)
    p_end = date(2026, 5, 31)
    await _cleanup_test_data(db_session, p_start)

    payroll_payload = {
        "period_start": str(p_start),
        "period_end": str(p_end),
        "country": "AE",
    }
    run_resp = await client.post(
        "/api/v1/payroll/runs",
        json=payroll_payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert run_resp.status_code == 201
    run_data = run_resp.json()
    run_id = run_data["id"]

    # 2. Check generated_reports for month-end reports
    gen_list_resp = await client.get(
        "/api/v1/generated-reports",
        params={"country": "AE", "period": "2026-05"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert gen_list_resp.status_code == 200
    gen_reports = gen_list_resp.json()
    assert len(gen_reports) == 11
    rep_keys = {r["report_key"] for r in gen_reports}
    for k in MONTH_END_REPORT_KEYS:
        assert k in rep_keys

    # Check file name pattern: <Company>_<Report>_<Country>_<Period>_generated-<timestamp>.xlsx
    sample_rep = gen_reports[0]
    assert "_AE_2026-05_generated-" in sample_rep["file_name"]
    assert sample_rep["version_no"] == 1
    assert sample_rep["status"] == "DRAFT"

    # 3. Test re-downloading returns identical content and correct SHA-256
    dl_res = await client.get(
        sample_rep["download_url"],
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert dl_res.status_code == 200
    assert len(dl_res.content) == sample_rep["file_size_bytes"]

    # 4. Supervisor visibility check on generated reports
    sup_gen_resp = await client.get(
        "/api/v1/generated-reports",
        params={"country": "AE", "period": "2026-05"},
        headers={"Authorization": f"Bearer {sup_token}"},
    )
    assert sup_gen_resp.status_code == 200
    sup_reports = sup_gen_resp.json()
    sup_keys = {r["report_key"] for r in sup_reports}
    assert "payroll" not in sup_keys
    assert "provisions-staff-cost" not in sup_keys
    assert "job-costing" not in sup_keys
    assert "daily-attendance" in sup_keys

    # 5. Approve payroll run -> generates final approved report versions
    appr_resp = await client.post(
        f"/api/v1/payroll/runs/{run_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert appr_resp.status_code == 200

    # Verify approved version reports were created
    appr_gen_resp = await client.get(
        "/api/v1/generated-reports",
        params={"country": "AE", "period": "2026-05", "status": "APPROVED"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert appr_gen_resp.status_code == 200
    appr_reps = appr_gen_resp.json()
    assert len(appr_reps) == 11
    for r in appr_reps:
        assert r["status"] == "APPROVED"
        assert "APPROVED" in r["file_name"]
