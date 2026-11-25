"""Background jobs and the payroll draft job (Batch 9 step 4).

- POST /payroll/runs/jobs returns 202 with the job; the job builds the same draft as the
  synchronous endpoint, with progress, and stores the run id in ``result``.
- One active job per country and month (409); a job whose process stopped (no heartbeat) is
  stored as INTERRUPTED and no longer blocks a new one.
- A failing job is FAILED with the error's code, and its work is rolled back.
- Only Admins start payroll jobs; non-Admins see only their own jobs.
- The batched salary and minutes lookups give what the per-employee lookups gave.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.errors import AppError
from fw.core.progress import report_progress
from fw.main import app
from fw.modules.org.models import Group
from fw.modules.payroll.models import EmployeeSalary, PayrollRecord, PayrollRun
from fw.modules.payroll.repository import PayrollRepository
from fw.modules.tasks import (
    JOB_FAILED,
    JOB_INTERRUPTED,
    JOB_RUNNING,
    JOB_SUCCEEDED,
    BackgroundJob,
    BackgroundJobService,
)
from tests.test_payroll_api import _cleanup_period, _create_test_employee, _create_test_user

PERIOD = {"period_start": "2027-02-01", "period_end": "2027-02-28", "country": "AE"}
DEDUPE = "payroll_draft:AE:2027-02-01"


async def _clear_jobs(session: AsyncSession) -> None:
    await session.execute(delete(BackgroundJob).where(BackgroundJob.dedupe_key == DEDUPE))
    await session.commit()


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_payroll_draft_job_builds_the_run_with_progress(db_session: AsyncSession):
    await _cleanup_period(db_session, date(2027, 2, 1), date(2027, 2, 28))
    await _clear_jobs(db_session)
    emp = await _create_test_employee(db_session, f"BJ_{uuid4().hex[:6]}", "Job Worker")
    db_session.add(
        EmployeeSalary(
            employee_id=emp.id,
            effective_from=date(2026, 1, 1),
            standard_hours=Decimal("8.0"),
            basic_salary=Decimal("1000.00"),
            special_allowance=Decimal("200.00"),
        )
    )
    await db_session.commit()
    _, admin_token = await _create_test_user(db_session, None, "ADMIN")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/payroll/runs/jobs", headers=_h(admin_token), json=PERIOD)
        assert resp.status_code == 202, resp.text
        job = resp.json()
        assert job["kind"] == "payroll_draft"
        assert job["status"] in ("QUEUED", "RUNNING")

        await BackgroundJobService.wait(job["id"])

        resp = await client.get(f"/api/v1/background-jobs/{job['id']}", headers=_h(admin_token))
        assert resp.status_code == 200, resp.text
        done = resp.json()
        assert done["status"] == JOB_SUCCEEDED, done
        assert done["result"]["run_no"] == 1
        # The last progress written is the month-end reports, all of them.
        assert done["phase"] == "reports"
        assert done["progress_done"] == done["progress_total"] > 0
        assert done["finished_at"] is not None

        listed = await client.get(
            "/api/v1/background-jobs?kind=payroll_draft", headers=_h(admin_token)
        )
        assert any(j["id"] == job["id"] for j in listed.json())

    run = await db_session.get(PayrollRun, done["result"]["payroll_run_id"])
    assert run is not None and run.status == "DRAFT"
    rec = (
        await db_session.execute(
            select(PayrollRecord).where(
                PayrollRecord.payroll_run_id == run.id, PayrollRecord.employee_id == emp.id
            )
        )
    ).scalar_one()
    assert rec.salary_portion == Decimal("1200.00")
    await _cleanup_period(db_session, date(2027, 2, 1), date(2027, 2, 28))
    await _clear_jobs(db_session)


@pytest.mark.asyncio
async def test_one_active_job_per_month_and_stale_jobs_are_interrupted(db_session: AsyncSession):
    await _clear_jobs(db_session)
    _, admin_token = await _create_test_user(db_session, None, "ADMIN")
    running = BackgroundJob(
        kind="payroll_draft",
        dedupe_key=DEDUPE,
        status=JOB_RUNNING,
        params=PERIOD,
        heartbeat_at=datetime.now(UTC),
    )
    db_session.add(running)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/payroll/runs/jobs", headers=_h(admin_token), json=PERIOD)
        assert resp.status_code == 409, resp.text
        assert resp.json()["code"] == "JOB_ALREADY_RUNNING"
        assert resp.json()["job_id"] == str(running.id)

        # Its process stopped: no heartbeat for longer than the limit.
        running.heartbeat_at = datetime.now(UTC) - timedelta(minutes=10)
        await db_session.commit()

        resp = await client.get(f"/api/v1/background-jobs/{running.id}", headers=_h(admin_token))
        assert resp.json()["status"] == JOB_INTERRUPTED
        assert resp.json()["error_code"] == "JOB_INTERRUPTED"

        resp = await client.post("/api/v1/payroll/runs/jobs", headers=_h(admin_token), json=PERIOD)
        assert resp.status_code == 202, resp.text
        await BackgroundJobService.wait(resp.json()["id"])

    await _cleanup_period(db_session, date(2027, 2, 1), date(2027, 2, 28))
    await _clear_jobs(db_session)


@pytest.mark.asyncio
async def test_failed_job_rolls_back_its_work(db_session: AsyncSession):
    marker = f"BJ-ROLLBACK-{uuid4().hex[:8]}"

    async def work(session: AsyncSession) -> dict[str, Any]:
        session.add(Group(code=marker, name=marker))
        await session.flush()
        await report_progress("step", 1, 2)
        raise AppError(code="SOMETHING_MISSING", message="A setting is missing.", status_code=422)

    job = await BackgroundJobService.start(kind="test_job", params={}, fn=work)
    await BackgroundJobService.wait(job.id)

    stored = await BackgroundJobService.get(db_session, job.id)
    assert stored is not None
    assert stored.status == JOB_FAILED
    assert stored.error_code == "SOMETHING_MISSING"
    assert stored.error_message == "A setting is missing."
    assert stored.phase == "step"
    found = (await db_session.execute(select(Group).where(Group.code == marker))).first()
    assert found is None
    await db_session.execute(delete(BackgroundJob).where(BackgroundJob.id == job.id))
    await db_session.commit()


@pytest.mark.asyncio
async def test_only_admins_start_payroll_jobs_and_others_see_only_their_own(
    db_session: AsyncSession,
):
    sup_emp = await _create_test_employee(
        db_session, f"BJS_{uuid4().hex[:6]}", "Job Supervisor", role="SUPERVISOR"
    )
    _, sup_token = await _create_test_user(db_session, sup_emp, "SUPERVISOR")
    other = BackgroundJob(kind="test_job", status=JOB_SUCCEEDED, params={})
    db_session.add(other)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/payroll/runs/jobs", headers=_h(sup_token), json=PERIOD)
        assert resp.status_code == 403
        resp = await client.get(f"/api/v1/background-jobs/{other.id}", headers=_h(sup_token))
        assert resp.status_code == 404
        resp = await client.get("/api/v1/background-jobs", headers=_h(sup_token))
        assert all(j["id"] != str(other.id) for j in resp.json())

    await db_session.execute(delete(BackgroundJob).where(BackgroundJob.id == other.id))
    await db_session.commit()


@pytest.mark.asyncio
async def test_report_progress_outside_a_job_does_nothing():
    await report_progress("anything", 1, 2)


@pytest.mark.asyncio
async def test_batched_salary_lookup_matches_the_single_lookup(db_session: AsyncSession):
    a = await _create_test_employee(db_session, f"BJA_{uuid4().hex[:6]}", "Salary A")
    b = await _create_test_employee(db_session, f"BJB_{uuid4().hex[:6]}", "Salary B")
    c = await _create_test_employee(db_session, f"BJC_{uuid4().hex[:6]}", "Salary C")
    for emp, eff, basic in [
        (a, date(2026, 1, 1), "1000.00"),
        (a, date(2026, 6, 1), "1100.00"),
        (a, date(2027, 1, 1), "1200.00"),  # after the as-of date
        (b, date(2026, 3, 1), "900.00"),
    ]:
        db_session.add(
            EmployeeSalary(
                employee_id=emp.id,
                effective_from=eff,
                standard_hours=Decimal("8.0"),
                basic_salary=Decimal(basic),
            )
        )
    await db_session.commit()

    as_of = date(2026, 10, 31)
    batched = await PayrollRepository.get_latest_salaries_for_employees(
        db_session, [a.id, b.id, c.id], as_of
    )
    for emp in (a, b, c):
        single = await PayrollRepository.get_latest_salary_for_employee(db_session, emp.id, as_of)
        got = batched.get(emp.id)
        assert (got.id if got else None) == (single.id if single else None)
    assert batched[a.id].basic_salary == Decimal("1100.00")
    assert c.id not in batched
