"""Payroll record breakdown (v1.16.0): the six salary components, the run's currency, and
viewing a run no longer regenerating its month-end reports."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from fw.main import app
from fw.modules.payroll.breakdown import SALARY_COMPONENTS
from fw.modules.payroll.models import EmployeeSalary, PayrollRecord
from fw.modules.reports.handlers.payroll import fetch_payroll
from fw.modules.reports.models import GeneratedReport
from fw.modules.reports.schemas import ReportFilterParams
from tests.test_payroll_api import _cleanup_period, _create_test_employee, _create_test_user

PERIOD_START = date(2026, 4, 1)
PERIOD_END = date(2026, 4, 30)

SALARY = {
    "basic_salary": Decimal("1000.00"),
    "special_allowance": Decimal("200.00"),
    "fixed_ot_amount": Decimal("150.00"),
    "bonus": Decimal("75.00"),
    "telephone_allowance": Decimal("40.00"),
    "housing_transport_allowance": Decimal("300.00"),
}


async def _run(session: AsyncSession) -> tuple[dict, dict, str, EmployeeSalary]:
    """A fresh April run with one employee whose six components are all set."""
    await _cleanup_period(session, PERIOD_START, PERIOD_END)
    emp = await _create_test_employee(session, f"T_{uuid4().hex[:6]}", "Breakdown Worker")
    salary = EmployeeSalary(
        employee_id=emp.id,
        effective_from=date(2026, 1, 1),
        standard_hours=Decimal("8.0"),
        **SALARY,
    )
    session.add(salary)
    await session.commit()
    _, token = await _create_test_user(session, None, "ADMIN")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/api/v1/payroll/runs",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "period_start": str(PERIOD_START),
                "period_end": str(PERIOD_END),
                "country": "AE",
            },
        )
    assert r.status_code == 201, r.text
    run = r.json()
    record = next(x for x in run["records"] if x["employee_id"] == str(emp.id))
    return run, record, token, salary


def _parts(record: dict) -> dict[str, Decimal]:
    return {key: Decimal(str(record[key])) for key in SALARY_COMPONENTS}


async def test_six_components_add_up_to_salary_portion(db_session: AsyncSession) -> None:
    run, record, token, _ = await _run(db_session)

    assert _parts(record) == SALARY
    assert sum(_parts(record).values()) == Decimal(str(record["salary_portion"]))
    assert Decimal(str(record["salary_portion"])) == Decimal("1765.00")
    assert run["currency"] == "AED"

    # The run stores them, so the payroll report reads the same six.
    rows = await fetch_payroll(
        db_session,
        ReportFilterParams(country="AE", payroll_run_id=run["id"]),
        scope=None,
    )
    row = next(x for x in rows if x["worker_id"] == record["employee_tally_id"])
    assert row["basic_salary"] == SALARY["basic_salary"]
    assert row["bonus_amount"] == SALARY["bonus"]
    assert row["housing_allowance"] == SALARY["housing_transport_allowance"]

    # Viewing the run does not generate its month-end reports again.
    async def report_count() -> int:
        return int(
            await db_session.scalar(
                select(func.count(GeneratedReport.id)).where(
                    GeneratedReport.payroll_run_id == run["id"]
                )
            )
            or 0
        )

    before = await report_count()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        for _ in range(2):
            r = await c.get(
                f"/api/v1/payroll/runs/{run['id']}", headers={"Authorization": f"Bearer {token}"}
            )
            assert r.status_code == 200, r.text
            assert r.json()["currency"] == "AED"
    db_session.expire_all()
    assert await report_count() == before


async def test_older_runs_fall_back_to_the_salary_row(db_session: AsyncSession) -> None:
    run, record, token, salary = await _run(db_session)
    rec_id = record["id"]

    # A record stored the way runs did before v1.16.0: only basic, nested under "salary".
    old_snapshot = {
        "salary": {
            "standard_hours": "8.0",
            "basic_salary": "1000.00",
            "salary_portion": str(record["salary_portion"]),
        },
        "ot1_rate": "0",
        "ot2_rate": "0",
    }
    await db_session.execute(
        update(PayrollRecord).where(PayrollRecord.id == rec_id).values(snapshot=old_snapshot)
    )
    await db_session.commit()

    async def fetch() -> dict:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.get(
                f"/api/v1/payroll/runs/{run['id']}", headers={"Authorization": f"Bearer {token}"}
            )
        assert r.status_code == 200, r.text
        return next(x for x in r.json()["records"] if x["id"] == rec_id)

    # From the salary row the run used (salary_id).
    got = await fetch()
    assert _parts(got) == SALARY
    assert sum(_parts(got).values()) == Decimal(str(got["salary_portion"]))

    # Without salary_id: the employee's row in effect at the end of the period.
    await db_session.execute(
        update(PayrollRecord).where(PayrollRecord.id == rec_id).values(salary_id=None)
    )
    await db_session.commit()
    got = await fetch()
    assert _parts(got) == SALARY
    assert salary.id is not None
