"""Handler for Employee Utilization Report (DEC-28)."""

from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fw.modules.attendance.models import AttendanceCalculation, AttendanceRecord
from fw.modules.org.models import Employee
from fw.modules.reports.schemas import ReportFilterParams


async def fetch_employee_utilization(
    session: AsyncSession,
    filters: ReportFilterParams,
    scoped_ids: set[UUID] | None,
) -> list[dict[str, Any]]:
    """Query productive vs travel vs idle time breakdown per worker (DEC-28)."""
    stmt = (
        select(AttendanceRecord)
        .join(Employee, AttendanceRecord.employee_id == Employee.id)
        .options(selectinload(AttendanceRecord.current_calculation))
        .order_by(AttendanceRecord.work_date.desc(), Employee.name.asc())
    )

    conditions = []
    if scoped_ids is not None:
        conditions.append(AttendanceRecord.employee_id.in_(scoped_ids))
    if filters.employee_id:
        conditions.append(AttendanceRecord.employee_id == filters.employee_id)
    if filters.date_from:
        conditions.append(AttendanceRecord.work_date >= filters.date_from)
    if filters.date_to:
        conditions.append(AttendanceRecord.work_date <= filters.date_to)
    if filters.country:
        conditions.append(Employee.country == filters.country)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    result = await session.execute(stmt)
    records = result.scalars().all()

    emp_ids = {r.employee_id for r in records}
    emp_map: dict[UUID, Employee] = {}
    if emp_ids:
        eres = await session.execute(select(Employee).where(Employee.id.in_(emp_ids)))
        emp_map = {e.id: e for e in eres.scalars().all()}

    rows: list[dict[str, Any]] = []
    for r in records:
        emp = emp_map.get(r.employee_id)
        calc: AttendanceCalculation | None = r.current_calculation
        if not calc:
            continue

        shift_span = calc.shift_span_minutes
        productive = calc.productive_minutes
        travel = calc.transit_minutes
        idle = calc.idle_minutes
        break_used = calc.break_minutes_used

        util_pct = round((productive / shift_span * 100.0), 1) if shift_span > 0 else 0.0
        scheduled_min = calc.standard_hours_minutes
        worked_min = calc.worked_minutes
        sched_vs_worked_pct = (
            round((worked_min / scheduled_min * 100.0), 1) if scheduled_min > 0 else 0.0
        )

        rows.append(
            {
                "worker_id": emp.tally_id if emp else "",
                "worker_name": emp.name if emp else "",
                "work_date": r.work_date,
                "shift_span_minutes": shift_span,
                "productive_minutes": productive,
                "travel_minutes": travel,
                "idle_minutes": idle,
                "break_minutes": break_used,
                "utilization_pct": util_pct,
                "scheduled_minutes": scheduled_min,
                "worked_minutes": worked_min,
                "scheduled_vs_worked_pct": sched_vs_worked_pct,
                "tag": "INFERRED",
            }
        )

    return rows
