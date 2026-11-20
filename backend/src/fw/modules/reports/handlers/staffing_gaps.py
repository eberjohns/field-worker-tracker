"""Handler for Staffing Gaps Report."""

from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.clock import site_today
from fw.modules.jobs.models import Worksite
from fw.modules.org.models import Employee
from fw.modules.reports.schemas import ReportFilterParams
from fw.modules.scheduling import AccessScope
from fw.modules.scheduling.models import LeaveRequest


async def fetch_staffing_gaps(
    session: AsyncSession,
    filters: ReportFilterParams,
    scope: AccessScope | None,
) -> list[dict[str, Any]]:
    """Query uncovered shifts caused by approved leave or staffing deficits."""
    from_d = filters.date_from or site_today()
    to_d = filters.date_to or (from_d + timedelta(days=30))

    stmt = select(LeaveRequest).where(
        LeaveRequest.status == "APPROVED",
        LeaveRequest.is_active.is_(True),
        LeaveRequest.from_date <= to_d,
        LeaveRequest.to_date >= from_d,
    )
    if filters.employee_id:
        stmt = stmt.where(LeaveRequest.employee_id == filters.employee_id)

    res = await session.execute(stmt)
    leaves = list(res.scalars().all())
    if scope is not None and not scope.unrestricted:
        # DEC-57: a leave is in scope when the worker is in my crew, or is scheduled (any
        # status, since leave cancels the rows) on my worksites during the leave.
        site_days = await scope.site_days(session, from_d, to_d, any_status=True)
        leaves = [
            lv
            for lv in leaves
            if lv.employee_id in scope.crew_ids
            or any(e == lv.employee_id and lv.from_date <= d <= lv.to_date for e, d in site_days)
        ]

    emp_ids = {lv.employee_id for lv in leaves}
    emp_map: dict[UUID, Employee] = {}
    if emp_ids:
        eres = await session.execute(select(Employee).where(Employee.id.in_(emp_ids)))
        emp_map = {e.id: e for e in eres.scalars().all()}

    ws_stmt = select(Worksite).where(
        Worksite.is_active.is_(True),
        Worksite.boundary.is_(None),
    )
    if scope is not None and scope.worksite_filter is not None:
        ws_stmt = ws_stmt.where(Worksite.id.in_(list(scope.worksite_filter)))
    ws_res = await session.execute(ws_stmt)
    missing_boundary_sites = ws_res.scalars().all()

    rows: list[dict[str, Any]] = []
    for lv in leaves:
        emp = emp_map.get(lv.employee_id)
        rows.append(
            {
                "target_date": lv.from_date,
                "worksite_name": "Scheduled Sites",
                "job_item_name": f"Cover for {emp.name if emp else 'Worker'}",
                "gap_reason": "LEAVE_UNCOVERED",
                "staff_type": emp.staff_grade_description if emp else "Standard",
                "required_hours": 8.0,
                "allocated_hours": 0.0,
                "gap_hours": 8.0,
                "status": "OPEN",
            }
        )

    for ws in missing_boundary_sites:
        rows.append(
            {
                "target_date": site_today(),
                "worksite_name": ws.job_name,
                "job_item_name": "Geofence Missing",
                "gap_reason": "MISSING_BOUNDARY",
                "staff_type": "-",
                "required_hours": 0.0,
                "allocated_hours": 0.0,
                "gap_hours": 0.0,
                "status": "ACTION_REQUIRED",
            }
        )

    return rows
