"""Handler for Staffing Gaps Report."""

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.modules.jobs.models import Worksite
from fw.modules.org.models import Employee
from fw.modules.reports.schemas import ReportFilterParams
from fw.modules.scheduling.models import LeaveRequest


async def fetch_staffing_gaps(
    session: AsyncSession,
    filters: ReportFilterParams,
    scoped_ids: set[UUID] | None,
) -> list[dict[str, Any]]:
    """Query uncovered shifts caused by approved leave or staffing deficits."""
    from_d = filters.date_from or date.today()
    to_d = filters.date_to or (from_d + timedelta(days=30))

    stmt = select(LeaveRequest).where(
        LeaveRequest.status == "APPROVED",
        LeaveRequest.is_active.is_(True),
        LeaveRequest.from_date <= to_d,
        LeaveRequest.to_date >= from_d,
    )
    if scoped_ids is not None:
        stmt = stmt.where(LeaveRequest.employee_id.in_(scoped_ids))
    if filters.employee_id:
        stmt = stmt.where(LeaveRequest.employee_id == filters.employee_id)

    res = await session.execute(stmt)
    leaves = res.scalars().all()

    emp_ids = {lv.employee_id for lv in leaves}
    emp_map: dict[UUID, Employee] = {}
    if emp_ids:
        eres = await session.execute(select(Employee).where(Employee.id.in_(emp_ids)))
        emp_map = {e.id: e for e in eres.scalars().all()}

    ws_stmt = select(Worksite).where(
        Worksite.is_active.is_(True),
        Worksite.boundary.is_(None),
    )
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
                "target_date": date.today(),
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
