"""Handler for Late Arrival / Early Departure Report."""

from datetime import datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fw.core.clock import get_country_timezone
from fw.modules.attendance.models import AttendanceCalculation, AttendanceRecord
from fw.modules.org.models import Employee
from fw.modules.reports.schemas import ReportFilterParams
from fw.modules.scheduling import AccessScope


def _site_minutes(at: datetime, tz: ZoneInfo) -> int:
    """Minutes after midnight in site time. Timestamps are stored in UTC and the planned times
    are site wall-clock times, so the actual time is converted before they are compared."""
    local = at.astimezone(tz) if at.tzinfo is not None else at
    return local.hour * 60 + local.minute


async def fetch_late_early_departure(
    session: AsyncSession,
    filters: ReportFilterParams,
    scope: AccessScope | None,
) -> list[dict[str, Any]]:
    """Query rows where arrival, departure, or shortfall deviated beyond scheduled times."""
    stmt = (
        select(AttendanceRecord)
        .join(Employee, AttendanceRecord.employee_id == Employee.id)
        .options(
            selectinload(AttendanceRecord.current_calculation),
            selectinload(AttendanceRecord.comments),
        )
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
        calc: AttendanceCalculation | None = r.current_calculation
        if not calc:
            continue

        emp = emp_map.get(r.employee_id)
        tz = get_country_timezone(emp.country if emp else None)

        late_arr = 0
        if calc.planned_first_site_start and calc.first_site_entry_at:
            act_min = _site_minutes(calc.first_site_entry_at, tz)
            pl_min = calc.planned_first_site_start.hour * 60 + calc.planned_first_site_start.minute
            late_arr = max(0, act_min - pl_min)

        late_dep_acc = 0
        if calc.planned_accommodation_departure and calc.accommodation_departure_at:
            act_min = _site_minutes(calc.accommodation_departure_at, tz)
            pl_min = (
                calc.planned_accommodation_departure.hour * 60
                + calc.planned_accommodation_departure.minute
            )
            late_dep_acc = max(0, act_min - pl_min)

        early_dep = 0
        if calc.planned_last_site_end and calc.last_site_exit_at:
            act_min = _site_minutes(calc.last_site_exit_at, tz)
            pl_min = calc.planned_last_site_end.hour * 60 + calc.planned_last_site_end.minute
            early_dep = max(0, pl_min - act_min)

        shortfall = calc.shortfall_minutes

        if late_arr == 0 and late_dep_acc == 0 and early_dep == 0 and shortfall == 0:
            continue

        latest_comment = r.comments[-1].comment_text if r.comments else ""

        rows.append(
            {
                "worker_id": emp.tally_id if emp else "",
                "worker_name": emp.name if emp else "",
                "work_date": r.work_date,
                "late_arrival_minutes": late_arr,
                "late_dep_acc_minutes": late_dep_acc,
                "early_dep_minutes": early_dep,
                "shortfall_minutes": shortfall,
                "grace_applied": "YES" if calc.grace_applied else "NO",
                "comments": latest_comment,
                "review_state": r.review_status,
            }
        )

    return rows
