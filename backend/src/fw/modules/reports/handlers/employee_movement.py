"""Handler for Employee Movement Report."""

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.modules.attendance.models import SiteVisit, TrackingGap
from fw.modules.jobs.models import Worksite
from fw.modules.org.models import Accommodation, Employee
from fw.modules.reports.schemas import ReportFilterParams


async def fetch_employee_movement(
    session: AsyncSession,
    filters: ReportFilterParams,
    scoped_ids: set[UUID] | None,
) -> list[dict[str, Any]]:
    """Reconstruct daily chronological movement trail for workers."""
    visit_stmt = select(SiteVisit).order_by(SiteVisit.work_date.asc(), SiteVisit.entry_at.asc())
    visit_conds = []
    if scoped_ids is not None:
        visit_conds.append(SiteVisit.employee_id.in_(scoped_ids))
    if filters.employee_id:
        visit_conds.append(SiteVisit.employee_id == filters.employee_id)
    if filters.date_from:
        visit_conds.append(SiteVisit.work_date >= filters.date_from)
    if filters.date_to:
        visit_conds.append(SiteVisit.work_date <= filters.date_to)

    if visit_conds:
        visit_stmt = visit_stmt.where(and_(*visit_conds))

    visit_res = await session.execute(visit_stmt)
    visits = visit_res.scalars().all()

    gap_stmt = select(TrackingGap).order_by(TrackingGap.work_date.asc())
    gap_conds = []
    if scoped_ids is not None:
        gap_conds.append(TrackingGap.employee_id.in_(scoped_ids))
    if filters.employee_id:
        gap_conds.append(TrackingGap.employee_id == filters.employee_id)
    if filters.date_from:
        gap_conds.append(TrackingGap.work_date >= filters.date_from)
    if filters.date_to:
        gap_conds.append(TrackingGap.work_date <= filters.date_to)

    if gap_conds:
        gap_stmt = gap_stmt.where(and_(*gap_conds))

    gap_res = await session.execute(gap_stmt)
    gaps = gap_res.scalars().all()

    emp_ids = {v.employee_id for v in visits} | {g.employee_id for g in gaps}
    emp_map: dict[UUID, Employee] = {}
    if emp_ids:
        eres = await session.execute(select(Employee).where(Employee.id.in_(emp_ids)))
        emp_map = {e.id: e for e in eres.scalars().all()}

    site_ids = {v.worksite_id for v in visits if v.worksite_id}
    site_map: dict[UUID, Worksite] = {}
    if site_ids:
        sres = await session.execute(select(Worksite).where(Worksite.id.in_(site_ids)))
        site_map = {s.id: s for s in sres.scalars().all()}

    acc_ids = {v.accommodation_id for v in visits if v.accommodation_id}
    acc_map: dict[UUID, Accommodation] = {}
    if acc_ids:
        ares = await session.execute(select(Accommodation).where(Accommodation.id.in_(acc_ids)))
        acc_map = {a.id: a for a in ares.scalars().all()}

    day_events: dict[tuple[UUID, date], list[dict[str, Any]]] = {}

    for v in visits:
        key = (v.employee_id, v.work_date)
        if key not in day_events:
            day_events[key] = []

        place_name = "Unknown"
        if v.place_type == "SITE" and v.worksite_id and v.worksite_id in site_map:
            ws = site_map[v.worksite_id]
            place_name = f"{ws.job_number} - {ws.job_name}"
        elif v.place_type == "ACCOMMODATION" and v.accommodation_id and v.accommodation_id in acc_map:
            place_name = acc_map[v.accommodation_id].name
        elif v.place_type == "ACCOMMODATION":
            place_name = "Accommodation"

        day_events[key].append(
            {
                "timestamp": v.entry_at,
                "segment_type": v.place_type,
                "location_name": place_name,
                "start_time": v.entry_at.strftime("%H:%M:%S"),
                "end_time": v.exit_at.strftime("%H:%M:%S") if v.exit_at else "-",
                "duration_minutes": v.duration_minutes,
                "observation_type": "INFERRED" if v.exit_inferred else "OBSERVED",
                "unaccounted_minutes": 0,
            }
        )

    for g in gaps:
        key = (g.employee_id, g.work_date)
        if key not in day_events:
            day_events[key] = []
        day_events[key].append(
            {
                "timestamp": g.created_at,
                "segment_type": "TRACKING_GAP",
                "location_name": "Location Disabled / Gap",
                "start_time": g.created_at.strftime("%H:%M:%S"),
                "end_time": "-",
                "duration_minutes": 0,
                "observation_type": "OBSERVED",
                "unaccounted_minutes": 0,
            }
        )

    rows: list[dict[str, Any]] = []
    for (emp_id, w_date), evts in sorted(day_events.items(), key=lambda x: (x[0][1], str(x[0][0]))):
        emp = emp_map.get(emp_id)
        evts.sort(key=lambda x: x["timestamp"])
        for seq, e in enumerate(evts, start=1):
            rows.append(
                {
                    "worker_id": emp.tally_id if emp else "",
                    "worker_name": emp.name if emp else "",
                    "work_date": w_date,
                    "seq": seq,
                    "segment_type": e["segment_type"],
                    "location_name": e["location_name"],
                    "start_time": e["start_time"],
                    "end_time": e["end_time"],
                    "duration_minutes": e["duration_minutes"],
                    "observation_type": e["observation_type"],
                    "unaccounted_minutes": e["unaccounted_minutes"],
                }
            )

    return rows
