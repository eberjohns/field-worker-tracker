"""Handler for Daily Attendance Report."""

from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fw.modules.attendance.models import AttendanceCalculation, AttendanceRecord
from fw.modules.org.models import Employee
from fw.modules.reports.schemas import ReportFilterParams
from fw.modules.scheduling import AccessScope


async def fetch_daily_attendance(
    session: AsyncSession,
    filters: ReportFilterParams,
    scope: AccessScope | None,
) -> list[dict[str, Any]]:
    """Query daily attendance data comparing 5-point planned schedule against actuals."""
    stmt = (
        select(AttendanceRecord)
        .join(Employee, AttendanceRecord.employee_id == Employee.id)
        .options(
            selectinload(AttendanceRecord.current_calculation),
            selectinload(AttendanceRecord.comments),
            selectinload(AttendanceRecord.approvals),
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
    if filters.sgd:
        conditions.append(Employee.staff_grade_description == filters.sgd)

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

    rows: list[dict[str, Any]] = []
    for rec in records:
        emp = emp_map.get(rec.employee_id)
        calc: AttendanceCalculation | None = rec.current_calculation

        has_acc = bool(emp and emp.accommodation_id is not None)

        # Planned 7 cols
        pl_acc_st = (
            calc.planned_accommodation_departure.strftime("%H:%M")
            if calc and calc.planned_accommodation_departure
            else ("-" if has_acc else "n/a")
        )
        pl_first = (
            calc.planned_first_site_start.strftime("%H:%M")
            if calc and calc.planned_first_site_start
            else "-"
        )
        pl_break = calc.planned_break_minutes if calc else 0
        pl_last = (
            calc.planned_last_site_end.strftime("%H:%M")
            if calc and calc.planned_last_site_end
            else "-"
        )
        pl_acc_end = (
            calc.planned_accommodation_return.strftime("%H:%M")
            if calc and calc.planned_accommodation_return
            else ("-" if has_acc else "n/a")
        )
        pl_total = calc.planned_total_minutes if calc else 0
        pl_worked = calc.planned_worked_minutes if calc else 0

        # Actual 7 cols
        act_acc_st = (
            calc.accommodation_departure_at.strftime("%H:%M")
            if calc and calc.accommodation_departure_at
            else ("-" if has_acc else "n/a")
        )
        act_first = (
            calc.first_site_entry_at.strftime("%H:%M") if calc and calc.first_site_entry_at else "-"
        )
        act_break = calc.break_minutes_used if calc else 0
        act_last = (
            calc.last_site_exit_at.strftime("%H:%M") if calc and calc.last_site_exit_at else "-"
        )
        act_acc_end = (
            calc.accommodation_return_at.strftime("%H:%M")
            if calc and calc.accommodation_return_at
            else ("-" if has_acc else "n/a")
        )
        act_total = calc.shift_span_minutes if calc else 0
        act_worked = calc.worked_minutes if calc else 0

        # Variations
        var_total = act_total - pl_total if calc else 0
        var_worked = act_worked - pl_worked if calc else 0

        # Overtime
        ot1_hrs = round(calc.ot1_minutes / 60.0, 2) if calc else 0.0
        ot2_hrs = round(calc.ot2_minutes / 60.0, 2) if calc else 0.0

        # Comments & Approval
        latest_comment = rec.comments[-1].comment_text if rec.comments else ""
        approval_str = rec.review_status
        flags_str = ", ".join(calc.flags) if calc and calc.flags else ""

        rows.append(
            {
                "worker_id": emp.tally_id if emp else "",
                "worker_name": emp.name if emp else "",
                "work_date": rec.work_date,
                "status": rec.business_status,
                "planned_acc_start": pl_acc_st,
                "planned_first_site": pl_first,
                "planned_break": pl_break,
                "planned_last_site": pl_last,
                "planned_acc_end": pl_acc_end,
                "planned_total_time": pl_total,
                "planned_worked_time": pl_worked,
                "actual_acc_start": act_acc_st,
                "actual_first_site": act_first,
                "actual_break": act_break,
                "actual_last_site": act_last,
                "actual_acc_end": act_acc_end,
                "actual_total_time": act_total,
                "actual_worked_time": act_worked,
                "var_total_time": var_total,
                "var_worked_time": var_worked,
                "ot1_hours": ot1_hrs,
                "ot2_hours": ot2_hrs,
                "flags": flags_str,
                "comments": latest_comment,
                "approval": approval_str,
            }
        )

    return rows
