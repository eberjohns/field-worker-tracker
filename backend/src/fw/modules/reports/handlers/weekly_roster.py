"""Handler for Weekly Roster Export."""

from collections import defaultdict
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.clock import site_today
from fw.modules.jobs.models import Worksite
from fw.modules.org.models import Employee
from fw.modules.reports.schemas import ReportFilterParams
from fw.modules.scheduling import AccessScope
from fw.modules.scheduling.models import ScheduledWork


async def fetch_weekly_roster(
    session: AsyncSession,
    filters: ReportFilterParams,
    scope: AccessScope | None,
) -> list[dict[str, Any]]:
    """Generate weekly schedule in Mon-Sun worker grid format."""
    ref_date = filters.week_start or filters.date_from or site_today()
    mon = ref_date - timedelta(days=ref_date.weekday())
    week_days = [mon + timedelta(days=i) for i in range(7)]

    # DEC-57 per-cell site-day rule: a worker appears when any day of the week is in scope;
    # days outside scope show as hidden.
    site_days: set[tuple[UUID, date]] = set()
    emp_stmt = select(Employee).where(Employee.is_active.is_(True))
    if scope is not None and not scope.unrestricted:
        site_days = await scope.site_days(session, week_days[0], week_days[6])
        visible = {e for e, _ in site_days}
        if scope.role in ("SUPERINTENDENT", "ENGINEER"):
            visible |= set(scope.crew_ids)
        emp_stmt = emp_stmt.where(Employee.id.in_(list(visible)))
    if filters.employee_id:
        emp_stmt = emp_stmt.where(Employee.id == filters.employee_id)
    if filters.country:
        emp_stmt = emp_stmt.where(Employee.country == filters.country)

    emp_res = await session.execute(emp_stmt)
    employees = emp_res.scalars().all()
    if not employees:
        return []

    emp_ids = [e.id for e in employees]

    sched_stmt = select(ScheduledWork).where(
        ScheduledWork.employee_id.in_(emp_ids),
        ScheduledWork.work_date >= week_days[0],
        ScheduledWork.work_date <= week_days[6],
    )
    sched_res = await session.execute(sched_stmt)
    scheduled_items = sched_res.scalars().all()

    ws_ids = {s.worksite_id for s in scheduled_items}
    ws_map: dict[UUID, str] = {}
    if ws_ids:
        wres = await session.execute(select(Worksite).where(Worksite.id.in_(ws_ids)))
        ws_map = {w.id: f"{w.job_number} ({w.job_name})" for w in wres.scalars().all()}

    work_by_emp_day = defaultdict(list)
    for s in scheduled_items:
        site_str = ws_map.get(s.worksite_id, "Site")
        hrs = float(s.assigned_hours or 8.0)
        work_by_emp_day[(s.employee_id, s.work_date)].append(f"{site_str} [{hrs}h]")

    rows: list[dict[str, Any]] = []
    for emp in employees:
        day_cells = []
        tot_planned_hrs = 0.0
        for d in week_days:
            if scope is not None and scope.employee_day_access(emp.id, d, site_days) is None:
                day_cells.append("-")
                continue
            items = work_by_emp_day.get((emp.id, d), [])
            if items:
                cell_text = "; ".join(items)
                tot_planned_hrs += 8.0
            else:
                cell_text = "Weekly-OFF" if d.weekday() == 6 else "Free"
            day_cells.append(cell_text)

        rows.append(
            {
                "worker_id": emp.tally_id,
                "worker_name": emp.name,
                "grade": emp.staff_grade_description or "Standard",
                "supervisor_name": "Supervisor",
                "engineer_name": "Engineer",
                "mon_sites": day_cells[0],
                "tue_sites": day_cells[1],
                "wed_sites": day_cells[2],
                "thu_sites": day_cells[3],
                "fri_sites": day_cells[4],
                "sat_sites": day_cells[5],
                "sun_sites": day_cells[6],
                "total_planned_hours": tot_planned_hrs,
                "standard_hours": 48.0,
            }
        )

    rows.sort(key=lambda r: r["worker_name"])
    return rows
