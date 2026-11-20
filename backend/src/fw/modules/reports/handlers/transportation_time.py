"""Handler for Transportation Time Report."""

from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fw.modules.attendance.models import AttendanceCalculation, AttendanceRecord
from fw.modules.org.models import Employee
from fw.modules.reports.schemas import ReportFilterParams
from fw.modules.scheduling import AccessScope


async def fetch_transportation_time(
    session: AsyncSession,
    filters: ReportFilterParams,
    scope: AccessScope | None,
) -> list[dict[str, Any]]:
    """Query commute out, inter-site, commute back, and total transit per worker/day."""
    stmt = (
        select(AttendanceRecord)
        .join(Employee, AttendanceRecord.employee_id == Employee.id)
        .options(selectinload(AttendanceRecord.current_calculation))
        .order_by(AttendanceRecord.work_date.desc(), Employee.name.asc())
    )

    conditions = []
    # DEC-57 site-day rule: employee-days scheduled on my worksites (+ crew for Supt/Eng)
    conditions_scope = (
        scope.operations_clause(AttendanceRecord.employee_id, AttendanceRecord.work_date)
        if scope
        else None
    )
    if conditions_scope is not None:
        conditions.append(conditions_scope)
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

        total_transit = calc.transit_minutes
        commute_out = 0
        if calc.accommodation_departure_at and calc.first_site_entry_at:
            commute_out = max(
                0,
                int(
                    (calc.first_site_entry_at - calc.accommodation_departure_at).total_seconds()
                    / 60
                ),
            )

        commute_back = 0
        if calc.last_site_exit_at and calc.accommodation_return_at:
            commute_back = max(
                0, int((calc.accommodation_return_at - calc.last_site_exit_at).total_seconds() / 60)
            )

        inter_site = max(0, total_transit - commute_out - commute_back)
        is_driver = bool(emp and emp.role == "DRIVER")

        rows.append(
            {
                "worker_id": emp.tally_id if emp else "",
                "worker_name": emp.name if emp else "",
                "work_date": r.work_date,
                "commute_out_minutes": commute_out,
                "inter_site_minutes": inter_site,
                "commute_back_minutes": commute_back,
                "total_transit_minutes": total_transit,
                "is_driver_day": "YES" if is_driver else "NO",
                "tag": "INFERRED",
            }
        )

    return rows
