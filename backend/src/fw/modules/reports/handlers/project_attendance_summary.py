"""Handler for Project Attendance Summary Report."""

from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.modules.attendance.models import SiteVisit
from fw.modules.jobs.models import Worksite
from fw.modules.org.models import Group, Zone
from fw.modules.reports.schemas import ReportFilterParams
from fw.modules.scheduling import AccessScope
from fw.modules.scheduling.models import ScheduledWork


async def fetch_project_attendance_summary(
    session: AsyncSession,
    filters: ReportFilterParams,
    scope: AccessScope | None,
) -> list[dict[str, Any]]:
    """Aggregate planned vs deployed manpower and hours per project/worksite."""
    ws_stmt = select(Worksite).where(Worksite.is_active.is_(True))
    if filters.worksite_id:
        ws_stmt = ws_stmt.where(Worksite.id == filters.worksite_id)
    if filters.country:
        ws_stmt = ws_stmt.where(Worksite.country == filters.country)
    # Rows are per worksite: non-admins see only the worksites in their scope (DEC-57)
    if scope is not None and scope.worksite_filter is not None:
        ws_stmt = ws_stmt.where(Worksite.id.in_(list(scope.worksite_filter)))

    ws_res = await session.execute(ws_stmt)
    worksites = ws_res.scalars().all()
    if not worksites:
        return []

    ws_map = {w.id: w for w in worksites}
    group_ids = {w.group_id for w in worksites if w.group_id}
    zone_ids = {w.zone_id for w in worksites if w.zone_id}

    group_map: dict[UUID, str] = {}
    if group_ids:
        gres = await session.execute(select(Group).where(Group.id.in_(group_ids)))
        group_map = {g.id: g.name for g in gres.scalars().all()}

    zone_map: dict[UUID, str] = {}
    if zone_ids:
        zres = await session.execute(select(Zone).where(Zone.id.in_(zone_ids)))
        zone_map = {z.id: z.name for z in zres.scalars().all()}

    sched_stmt = select(ScheduledWork).where(ScheduledWork.worksite_id.in_(ws_map.keys()))
    if filters.date_from:
        sched_stmt = sched_stmt.where(ScheduledWork.work_date >= filters.date_from)
    if filters.date_to:
        sched_stmt = sched_stmt.where(ScheduledWork.work_date <= filters.date_to)
    sched_stmt_scope = (
        scope.operations_clause(ScheduledWork.employee_id, ScheduledWork.work_date)
        if scope
        else None
    )
    if sched_stmt_scope is not None:
        sched_stmt = sched_stmt.where(sched_stmt_scope)

    sched_res = await session.execute(sched_stmt)
    scheduled_items = sched_res.scalars().all()

    visit_stmt = select(SiteVisit).where(
        SiteVisit.place_type == "SITE", SiteVisit.worksite_id.in_(ws_map.keys())
    )
    if filters.date_from:
        visit_stmt = visit_stmt.where(SiteVisit.work_date >= filters.date_from)
    if filters.date_to:
        visit_stmt = visit_stmt.where(SiteVisit.work_date <= filters.date_to)
    visit_stmt_scope = (
        scope.operations_clause(SiteVisit.employee_id, SiteVisit.work_date) if scope else None
    )
    if visit_stmt_scope is not None:
        visit_stmt = visit_stmt.where(visit_stmt_scope)

    visit_res = await session.execute(visit_stmt)
    visits = visit_res.scalars().all()

    sched_by_ws = defaultdict(list)
    for s in scheduled_items:
        sched_by_ws[s.worksite_id].append(s)

    visits_by_ws = defaultdict(list)
    for v in visits:
        visits_by_ws[v.worksite_id].append(v)

    rows: list[dict[str, Any]] = []
    for ws_id, ws in ws_map.items():
        w_sched = sched_by_ws.get(ws_id, [])
        w_visits = visits_by_ws.get(ws_id, [])

        sched_worker_days = len(w_sched)
        sched_man_hours = round(sum(float(s.assigned_hours or 8.0) for s in w_sched), 1)

        deployed_worker_ids = {v.employee_id for v in w_visits}
        deployed_worker_days = len(
            {(v.employee_id, v.work_date) for v in w_visits if v.counts_as_completed}
        )
        actual_man_hours = round(sum(v.duration_minutes for v in w_visits) / 60.0, 1)

        pres_count = deployed_worker_days
        abs_count = max(0, sched_worker_days - pres_count)
        understaffed_days = 1 if sched_worker_days > pres_count else 0

        rows.append(
            {
                "worksite_code": ws.job_number,
                "worksite_name": ws.job_name,
                "group_name": group_map.get(ws.group_id, "-") if ws.group_id else "-",
                "zone_name": zone_map.get(ws.zone_id, "-") if ws.zone_id else "-",
                "scheduled_worker_days": sched_worker_days,
                "scheduled_man_hours": sched_man_hours,
                "deployed_workers": len(deployed_worker_ids),
                "deployed_worker_days": deployed_worker_days,
                "actual_man_hours": actual_man_hours,
                "present_count": pres_count,
                "partial_count": 0,
                "absent_count": abs_count,
                "understaffed_days": understaffed_days,
            }
        )

    rows.sort(key=lambda r: r["worksite_name"])
    return rows
