"""Handler for Document Expiry Report."""

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.modules.org.models import Employee, EmployeeDocument, EmployeeReportingLine
from fw.modules.reports.schemas import ReportFilterParams


async def fetch_document_expiry(
    session: AsyncSession,
    filters: ReportFilterParams,
    scoped_ids: set[UUID] | None,
) -> list[dict[str, Any]]:
    """Query documents expiring soon or already expired."""
    stmt = (
        select(EmployeeDocument)
        .join(Employee, EmployeeDocument.employee_id == Employee.id)
        .where(EmployeeDocument.is_active.is_(True), Employee.is_active.is_(True))
        .order_by(EmployeeDocument.expiry_date.asc())
    )

    conditions = []
    if scoped_ids is not None:
        conditions.append(EmployeeDocument.employee_id.in_(scoped_ids))
    if filters.employee_id:
        conditions.append(EmployeeDocument.employee_id == filters.employee_id)
    if filters.country:
        conditions.append(Employee.country == filters.country)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    result = await session.execute(stmt)
    docs = result.scalars().all()

    emp_ids = {d.employee_id for d in docs}
    emp_map: dict[UUID, Employee] = {}
    if emp_ids:
        eres = await session.execute(select(Employee).where(Employee.id.in_(emp_ids)))
        emp_map = {e.id: e for e in eres.scalars().all()}

    mgr_stmt = (
        select(EmployeeReportingLine, Employee)
        .join(Employee, EmployeeReportingLine.manager_id == Employee.id)
        .where(EmployeeReportingLine.relationship == "SUPERVISOR")
    )
    mgr_res = await session.execute(mgr_stmt)
    supervisor_map: dict[UUID, str] = {row[0].employee_id: row[1].name for row in mgr_res.all()}

    today = date.today()
    rows: list[dict[str, Any]] = []
    for d in docs:
        if not d.expiry_date:
            continue

        days_remaining = (d.expiry_date - today).days
        status = "OK"
        if days_remaining < 0:
            status = "EXPIRED"
        elif days_remaining <= 30:
            status = "EXPIRING_SOON"

        emp = emp_map.get(d.employee_id)
        sup_name = supervisor_map.get(d.employee_id, "None")

        rows.append(
            {
                "worker_id": emp.tally_id if emp else "",
                "worker_name": emp.name if emp else "",
                "document_type": d.document_type,
                "document_number": d.document_type,
                "expiry_date": d.expiry_date,
                "days_remaining": days_remaining,
                "status": status,
                "supervisor_name": sup_name,
            }
        )

    rows.sort(key=lambda r: (r["days_remaining"], r["worker_name"]))
    return rows
