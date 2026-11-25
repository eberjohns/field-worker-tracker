"""One query for the attendance-day reports (Batch 9 step 4).

The attendance reports used to load whole ORM rows, then each record's current calculation
with ``selectinload`` (in chunks of 500, so 28 extra queries for a month of 14,000 days) and
then every employee again. Here one SELECT reads only the columns a report uses:

    attendance_records  JOIN employees  LEFT JOIN attendance_calculations (the current one)
    [+ the latest comment, as a scalar subquery]

Each result row becomes three light objects (``rec``, ``calc`` or None, ``emp``) with the same
attribute names as the models, so the reports' row logic stays exactly as it was.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.progress import fetch_rows_in_parts, yield_every
from fw.modules.attendance.models import AttendanceCalculation, AttendanceComment, AttendanceRecord
from fw.modules.org.models import Employee
from fw.modules.reports.schemas import ReportFilterParams
from fw.modules.scheduling import AccessScope


@dataclass(slots=True)
class AttendanceDay:
    rec: Any
    calc: Any | None
    emp: Any
    latest_comment: str = ""


async def load_attendance_days(
    session: AsyncSession,
    filters: ReportFilterParams,
    scope: AccessScope | None,
    *,
    record_fields: Sequence[str],
    calc_fields: Sequence[str] = (),
    employee_fields: Sequence[str] = ("tally_id", "name"),
    date_from: date | None = None,
    date_to: date | None = None,
    newest_first: bool = True,
    latest_comment: bool = False,
    filter_sgd: bool = False,
) -> list[AttendanceDay]:
    """Attendance days in the filters and scope, newest first (then by name) or oldest first.

    Same filters as the reports had: DEC-57 site-day scope, employee, date range, country and,
    when ``filter_sgd``, the staff grade description. ``date_from``/``date_to`` default to the
    filters' range.
    """
    date_from = date_from if date_from is not None else filters.date_from
    date_to = date_to if date_to is not None else filters.date_to

    cols: list[Any] = [getattr(AttendanceRecord, f).label(f"r_{f}") for f in record_fields]
    cols.append(AttendanceCalculation.id.label("c__id"))
    cols += [getattr(AttendanceCalculation, f).label(f"c_{f}") for f in calc_fields]
    cols += [getattr(Employee, f).label(f"e_{f}") for f in employee_fields]
    if latest_comment:
        cols.append(
            select(AttendanceComment.comment_text)
            .where(AttendanceComment.attendance_id == AttendanceRecord.id)
            .order_by(AttendanceComment.created_at.desc())
            .limit(1)
            .correlate(AttendanceRecord)
            .scalar_subquery()
            .label("latest_comment")
        )

    stmt = (
        select(*cols)
        .select_from(AttendanceRecord)
        .join(Employee, AttendanceRecord.employee_id == Employee.id)
        .outerjoin(
            AttendanceCalculation,
            AttendanceRecord.current_calculation_id == AttendanceCalculation.id,
        )
    )
    if newest_first:
        stmt = stmt.order_by(AttendanceRecord.work_date.desc(), Employee.name.asc())
    else:
        stmt = stmt.order_by(AttendanceRecord.work_date.asc())

    conditions = []
    # DEC-57 site-day rule: employee-days scheduled on my worksites (+ crew for Supt/Eng)
    scope_clause = (
        scope.operations_clause(AttendanceRecord.employee_id, AttendanceRecord.work_date)
        if scope
        else None
    )
    if scope_clause is not None:
        conditions.append(scope_clause)
    if filters.employee_id:
        conditions.append(AttendanceRecord.employee_id == filters.employee_id)
    if date_from:
        conditions.append(AttendanceRecord.work_date >= date_from)
    if date_to:
        conditions.append(AttendanceRecord.work_date <= date_to)
    if filters.country:
        conditions.append(Employee.country == filters.country)
    if filter_sgd and filters.sgd:
        conditions.append(Employee.staff_grade_description == filters.sgd)
    if conditions:
        stmt = stmt.where(and_(*conditions))

    rows = await fetch_rows_in_parts(session, stmt)
    days: list[AttendanceDay] = []
    for row_no, r in enumerate(rows):
        row = r._mapping
        await yield_every(row_no)
        rec = SimpleNamespace(**{f: row[f"r_{f}"] for f in record_fields})
        calc = (
            SimpleNamespace(**{f: row[f"c_{f}"] for f in calc_fields})
            if row["c__id"] is not None
            else None
        )
        emp = SimpleNamespace(**{f: row[f"e_{f}"] for f in employee_fields})
        days.append(
            AttendanceDay(
                rec=rec,
                calc=calc,
                emp=emp,
                latest_comment=(row["latest_comment"] or "") if latest_comment else "",
            )
        )
    return days
