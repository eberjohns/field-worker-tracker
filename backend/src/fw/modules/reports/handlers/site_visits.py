"""Handler for Site Visit Report."""

from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.modules.attendance.models import SiteVisit
from fw.modules.jobs.models import Worksite
from fw.modules.org.models import Employee
from fw.modules.reports.schemas import ReportFilterParams


async def fetch_site_visits(
    session: AsyncSession,
    filters: ReportFilterParams,
    scoped_ids: set[UUID] | None,
) -> list[dict[str, Any]]:
    """Query verified site visits grouped by worker."""
    stmt = (
        select(SiteVisit)
        .where(SiteVisit.place_type == "SITE")
        .order_by(SiteVisit.work_date.desc(), SiteVisit.entry_at.desc())
    )

    conditions = []
    if scoped_ids is not None:
        conditions.append(SiteVisit.employee_id.in_(scoped_ids))
    if filters.employee_id:
        conditions.append(SiteVisit.employee_id == filters.employee_id)
    if filters.worksite_id:
        conditions.append(SiteVisit.worksite_id == filters.worksite_id)
    if filters.date_from:
        conditions.append(SiteVisit.work_date >= filters.date_from)
    if filters.date_to:
        conditions.append(SiteVisit.work_date <= filters.date_to)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    result = await session.execute(stmt)
    visits = result.scalars().all()

    emp_ids = {v.employee_id for v in visits}
    emp_map: dict[UUID, Employee] = {}
    if emp_ids:
        eres = await session.execute(select(Employee).where(Employee.id.in_(emp_ids)))
        emp_map = {e.id: e for e in eres.scalars().all()}

    site_ids = {v.worksite_id for v in visits if v.worksite_id}
    site_map: dict[UUID, Worksite] = {}
    if site_ids:
        sres = await session.execute(select(Worksite).where(Worksite.id.in_(site_ids)))
        site_map = {s.id: s for s in sres.scalars().all()}

    rows: list[dict[str, Any]] = []
    for v in visits:
        emp = emp_map.get(v.employee_id)
        ws = site_map.get(v.worksite_id) if v.worksite_id else None

        rows.append(
            {
                "worker_id": emp.tally_id if emp else "",
                "worker_name": emp.name if emp else "",
                "work_date": v.work_date,
                "worksite_code": ws.job_number if ws else "",
                "worksite_name": ws.job_name if ws else "Unknown Site",
                "job_item_name": "Scheduled Task",
                "scheduled_hours": 8.0,
                "entry_time": v.entry_at.strftime("%H:%M:%S"),
                "exit_time": v.exit_at.strftime("%H:%M:%S") if v.exit_at else "-",
                "time_spent_minutes": v.duration_minutes,
                "exit_tag": "INFERRED" if v.exit_inferred else "OBSERVED",
                "counted_as_completed": "YES" if v.counts_as_completed else "NO",
                "flags": ", ".join(v.flags) if v.flags else "",
            }
        )

    rows.sort(key=lambda r: (r["worker_name"], str(r["work_date"])))
    return rows
