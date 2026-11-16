"""Handler for Monthly Attendance Report."""

from collections import defaultdict
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fw.modules.attendance.models import AttendanceRecord
from fw.modules.org.models import Employee
from fw.modules.reports.schemas import ReportFilterParams


async def fetch_monthly_attendance(
    session: AsyncSession,
    filters: ReportFilterParams,
    scoped_ids: set[UUID] | None,
) -> list[dict[str, Any]]:
    """Aggregate attendance per worker across the requested month or date range."""
    target_from = filters.date_from
    target_to = filters.date_to
    if filters.year and filters.month and not target_from:
        import calendar

        _, last_day = calendar.monthrange(filters.year, filters.month)
        target_from = date(filters.year, filters.month, 1)
        target_to = date(filters.year, filters.month, last_day)

    stmt = (
        select(AttendanceRecord)
        .join(Employee, AttendanceRecord.employee_id == Employee.id)
        .options(selectinload(AttendanceRecord.current_calculation))
        .order_by(AttendanceRecord.work_date.asc())
    )

    conditions = []
    if scoped_ids is not None:
        conditions.append(AttendanceRecord.employee_id.in_(scoped_ids))
    if filters.employee_id:
        conditions.append(AttendanceRecord.employee_id == filters.employee_id)
    if target_from:
        conditions.append(AttendanceRecord.work_date >= target_from)
    if target_to:
        conditions.append(AttendanceRecord.work_date <= target_to)
    if filters.country:
        conditions.append(Employee.country == filters.country)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    result = await session.execute(stmt)
    records = result.scalars().all()

    # Preload employees
    emp_ids = {r.employee_id for r in records}
    emp_map: dict[UUID, Employee] = {}
    if emp_ids:
        emp_res = await session.execute(select(Employee).where(Employee.id.in_(emp_ids)))
        emp_map = {e.id: e for e in emp_res.scalars().all()}

    # Group by (employee_id, YYYY-MM)
    grouped: dict[tuple[UUID, str], list[AttendanceRecord]] = defaultdict(list)
    for rec in records:
        month_str = rec.work_date.strftime("%Y-%m")
        grouped[(rec.employee_id, month_str)].append(rec)

    rows: list[dict[str, Any]] = []
    for (emp_id, month_str), recs in grouped.items():
        emp = emp_map.get(emp_id)
        days_pres = sum(1 for r in recs if r.business_status == "PRESENT")
        days_part = sum(1 for r in recs if r.business_status == "PARTIAL")
        days_abs = sum(1 for r in recs if r.business_status == "ABSENT")
        days_shortfall = 0
        total_worked_min = 0
        ot1_min = 0
        ot2_min = 0
        pending_review = sum(1 for r in recs if r.review_status == "PENDING_REVIEW")

        for r in recs:
            calc = r.current_calculation
            if calc:
                if calc.shortfall_minutes > 0 and not calc.grace_applied:
                    days_shortfall += 1
                total_worked_min += calc.worked_minutes
                ot1_min += calc.ot1_minutes
                ot2_min += calc.ot2_minutes

        total_worked_hrs = round(total_worked_min / 60.0, 2)
        ot1_hrs = round(ot1_min / 60.0, 2)
        ot2_hrs = round(ot2_min / 60.0, 2)

        rows.append(
            {
                "worker_id": emp.tally_id if emp else "",
                "worker_name": emp.name if emp else "",
                "month": month_str,
                "days_present": days_pres,
                "days_partial": days_part,
                "days_absent": days_abs,
                "days_shortfall": days_shortfall,
                "total_worked_hours": total_worked_hrs,
                "cumulative_worked_hours": total_worked_hrs,
                "ot1_total_hours": ot1_hrs,
                "ot2_total_hours": ot2_hrs,
                "days_pending_review": pending_review,
            }
        )

    rows.sort(key=lambda r: (r["worker_name"], r["month"]))
    return rows
