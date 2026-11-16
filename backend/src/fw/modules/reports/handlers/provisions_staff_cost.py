"""Handler for Provisions and Staff Cost Report (Admin Only)."""

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fw.modules.payroll.models import PayrollRecord, PayrollRun
from fw.modules.reports.schemas import ReportFilterParams


async def fetch_provisions_staff_cost(
    session: AsyncSession,
    filters: ReportFilterParams,
    scoped_ids: set[UUID] | None = None,
) -> list[dict[str, Any]]:
    """Query employer cost, statutory provisions, and HR overhead."""
    run_stmt = select(PayrollRun).order_by(PayrollRun.period_start.desc(), PayrollRun.run_no.desc())
    if filters.payroll_run_id:
        run_stmt = run_stmt.where(PayrollRun.id == filters.payroll_run_id)
    elif filters.year and filters.month:
        import calendar
        from datetime import date

        _, last_day = calendar.monthrange(filters.year, filters.month)
        p_start = date(filters.year, filters.month, 1)
        p_end = date(filters.year, filters.month, last_day)
        run_stmt = run_stmt.where(PayrollRun.period_start == p_start, PayrollRun.period_end == p_end)
    elif filters.country:
        run_stmt = run_stmt.where(PayrollRun.country == filters.country)

    run_res = await session.execute(run_stmt)
    payroll_run = run_res.scalars().first()
    if not payroll_run:
        return []

    rec_stmt = (
        select(PayrollRecord)
        .where(PayrollRecord.payroll_run_id == payroll_run.id)
        .options(selectinload(PayrollRecord.employee))
    )
    if filters.employee_id:
        rec_stmt = rec_stmt.where(PayrollRecord.employee_id == filters.employee_id)

    rec_res = await session.execute(rec_stmt)
    records = rec_res.scalars().all()

    rows: list[dict[str, Any]] = []
    for rec in records:
        emp = rec.employee
        snap = rec.snapshot or {}
        prov_snap = snap.get("provisions_breakdown", {})

        visa_p = Decimal(str(prov_snap.get("visa", "0.00")))
        air_p = Decimal(str(prov_snap.get("air_ticket", "0.00")))
        uni_p = Decimal(str(prov_snap.get("uniform", "0.00")))
        acc_p = Decimal(str(prov_snap.get("accommodation", "0.00")))
        med_p = Decimal(str(prov_snap.get("medical", "0.00")))

        rows.append(
            {
                "worker_id": emp.tally_id if emp else "",
                "worker_name": emp.name if emp else "",
                "salary_portion": rec.salary_portion,
                "ot_amounts": rec.ot1_amount + rec.ot2_amount,
                "gratuity_provision": rec.gratuity,
                "leave_salary_provision": rec.leave_salary,
                "visa_provision": visa_p,
                "air_ticket_provision": air_p,
                "uniform_provision": uni_p,
                "accommodation_provision": acc_p,
                "medical_provision": med_p,
                "per_month_provision": rec.per_month_provision,
                "total_staff_cost": rec.total_staff_cost,
                "hr_oh_amount": rec.hr_oh_amount,
                "final_total_staff_cost": rec.final_total_staff_cost,
            }
        )

    rows.sort(key=lambda r: r["worker_name"])
    return rows
