"""Handler for Pending Visits Report (DEC-32)."""

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.modules.attendance.models import AttendanceComment, PendingVisit
from fw.modules.jobs.models import Worksite
from fw.modules.org.models import Employee
from fw.modules.reports.schemas import ReportFilterParams


async def fetch_pending_visits(
    session: AsyncSession,
    filters: ReportFilterParams,
    scoped_ids: set[UUID] | None,
) -> list[dict[str, Any]]:
    """Query pending site visit follow-up records."""
    stmt = select(PendingVisit).order_by(PendingVisit.due_date.asc())

    conditions = []
    if scoped_ids is not None:
        conditions.append(PendingVisit.employee_id.in_(scoped_ids))
    if filters.employee_id:
        conditions.append(PendingVisit.employee_id == filters.employee_id)
    if filters.worksite_id:
        conditions.append(PendingVisit.worksite_id == filters.worksite_id)
    if filters.date_from:
        conditions.append(PendingVisit.due_date >= filters.date_from)
    if filters.date_to:
        conditions.append(PendingVisit.due_date <= filters.date_to)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    result = await session.execute(stmt)
    pending_items = result.scalars().all()

    emp_ids = {p.employee_id for p in pending_items}
    emp_map: dict[UUID, Employee] = {}
    if emp_ids:
        eres = await session.execute(select(Employee).where(Employee.id.in_(emp_ids)))
        emp_map = {e.id: e for e in eres.scalars().all()}

    ws_ids = {p.worksite_id for p in pending_items}
    ws_map: dict[UUID, Worksite] = {}
    if ws_ids:
        wres = await session.execute(select(Worksite).where(Worksite.id.in_(ws_ids)))
        ws_map = {w.id: w for w in wres.scalars().all()}

    comment_ids = {p.explanation_comment_id for p in pending_items if p.explanation_comment_id}
    comment_map: dict[UUID, str] = {}
    if comment_ids:
        cres = await session.execute(
            select(AttendanceComment).where(AttendanceComment.id.in_(comment_ids))
        )
        comment_map = {c.id: c.comment_text for c in cres.scalars().all()}

    today = date.today()
    rows: list[dict[str, Any]] = []
    for p in pending_items:
        emp = emp_map.get(p.employee_id)
        ws = ws_map.get(p.worksite_id)
        age_days = (today - p.due_date).days if p.due_date else 0
        is_escalated = age_days > 3 and p.status == "OPEN"
        expl_text = (
            comment_map.get(p.explanation_comment_id, p.closed_reason or "")
            if p.explanation_comment_id
            else (p.closed_reason or "")
        )

        rows.append(
            {
                "worksite_code": ws.job_number if ws else "",
                "worksite_name": ws.job_name if ws else "Unknown",
                "job_item_name": "Job Assignment",
                "assigned_workers": emp.name if emp else "",
                "supervisor_name": "Supervisor",
                "due_date": p.due_date,
                "age_days": max(0, age_days),
                "status": p.status,
                "latest_explanation": expl_text,
                "is_escalated": "YES" if is_escalated else "NO",
            }
        )

    return rows
