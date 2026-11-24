"""A payroll draft with scheduled work allocates the staff cost to the worksites (v1.17.0).

Before, every record's job cost allocations were built while the record had no id yet, so any
draft where an employee had ACTIVE scheduled work linked to an occurrence failed with a 500
(NOT NULL on job_cost_allocations.payroll_record_id).
"""

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.main import app
from fw.modules.jobs import JobItem, Worksite
from fw.modules.jobs.models import JobOccurrence
from fw.modules.org import Group, Zone
from fw.modules.payroll.models import EmployeeSalary, JobCostAllocation, PayrollRecord
from fw.modules.scheduling.models import ScheduledWork
from tests.ids import unique_job_number
from tests.test_payroll_api import _cleanup_period, _create_test_employee, _create_test_user

PERIOD_START = date(2026, 3, 1)
PERIOD_END = date(2026, 3, 31)


async def test_draft_with_scheduled_work_allocates_cost_per_worksite(
    db_session: AsyncSession,
) -> None:
    session = db_session
    await _cleanup_period(session, PERIOD_START, PERIOD_END)
    emp = await _create_test_employee(session, f"T_{uuid4().hex[:6]}", "Allocation Worker")
    session.add(
        EmployeeSalary(
            employee_id=emp.id,
            effective_from=date(2026, 1, 1),
            standard_hours=Decimal("8.0"),
            basic_salary=Decimal("1000.00"),
        )
    )
    group = Group(code=f"A{uuid4().hex[:6]}", name=f"Alloc Group {uuid4().hex[:6]}")
    zone = Zone(code=f"A{uuid4().hex[:6]}", name=f"Alloc Zone {uuid4().hex[:6]}")
    session.add_all([group, zone])
    await session.flush()
    sites = []
    for n in range(2):
        ws = Worksite(
            job_number=unique_job_number("12A"),
            job_name=f"Allocation site {n + 1}",
            group_id=group.id,
            zone_id=zone.id,
            country="AE",
            start_date=date(2026, 1, 1),
        )
        session.add(ws)
        await session.flush()
        item = JobItem(
            worksite_id=ws.id,
            sub_item_code="A",
            staff_grade_description="Gardener Helper",
            planned_grade_code="G1A",
            frequency_unit="WEEK",
            occurrences_per_period=Decimal("1"),
            period_interval=1,
            required_staff_count=1,
            hours_per_occurrence_per_staff=Decimal("8"),
            start_date=date(2026, 1, 1),
            deployment_type="PERMANENT",
        )
        session.add(item)
        await session.flush()
        sites.append((ws, item))

    # Site 1: three days, site 2: one day (8 h each), all linked to an occurrence.
    days = {0: [date(2026, 3, 2), date(2026, 3, 3), date(2026, 3, 4)], 1: [date(2026, 3, 5)]}
    for n, (ws, item) in enumerate(sites):
        for day in days[n]:
            occ = JobOccurrence(
                job_item_id=item.id,
                window_start=day,
                window_end=day + timedelta(days=6),
                slot_index=1,
                due_date=day,
                required_staff_count=1,
                required_hours_per_staff=Decimal("8"),
            )
            session.add(occ)
            await session.flush()
            session.add(
                ScheduledWork(
                    employee_id=emp.id,
                    work_date=day,
                    occurrence_id=occ.id,
                    job_item_id=item.id,
                    worksite_id=ws.id,
                    assigned_hours=Decimal("8.0"),
                    sequence=1,
                    status="ACTIVE",
                    source="STANDING",
                    is_late_approval=False,
                    is_weekly_off_cover=False,
                    version=1,
                )
            )
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

    record = (
        await session.execute(
            select(PayrollRecord).where(
                PayrollRecord.payroll_run_id == r.json()["id"], PayrollRecord.employee_id == emp.id
            )
        )
    ).scalar_one()
    allocations = (
        (
            await session.execute(
                select(JobCostAllocation).where(JobCostAllocation.payroll_record_id == record.id)
            )
        )
        .scalars()
        .all()
    )
    by_site = {a.worksite_id: a for a in allocations}
    assert set(by_site) == {sites[0][0].id, sites[1][0].id}
    assert by_site[sites[0][0].id].worked_minutes == 3 * 8 * 60
    assert by_site[sites[1][0].id].worked_minutes == 8 * 60
    # The cost is split 3:1 and adds up to the record's final staff cost (to the cent).
    total = sum((a.allocated_amount for a in allocations), Decimal("0"))
    assert abs(total - record.final_total_staff_cost) <= Decimal("0.01")
    assert by_site[sites[0][0].id].allocated_amount > by_site[sites[1][0].id].allocated_amount

    await _cleanup_period(session, PERIOD_START, PERIOD_END)
