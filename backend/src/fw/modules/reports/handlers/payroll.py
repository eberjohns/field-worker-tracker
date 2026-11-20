"""Handler for Payroll Report (Admin Only)."""

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fw.modules.payroll.models import PayrollRecord, PayrollRun
from fw.modules.reports.schemas import ReportFilterParams
from fw.modules.scheduling import AccessScope


async def fetch_payroll(
    session: AsyncSession,
    filters: ReportFilterParams,
    scope: AccessScope | None = None,
) -> list[dict[str, Any]]:
    """Query payroll summary sheet for a payroll run or period."""
    run_stmt = select(PayrollRun).order_by(PayrollRun.period_start.desc(), PayrollRun.run_no.desc())
    if filters.payroll_run_id:
        run_stmt = run_stmt.where(PayrollRun.id == filters.payroll_run_id)
    elif filters.year and filters.month:
        import calendar
        from datetime import date

        _, last_day = calendar.monthrange(filters.year, filters.month)
        p_start = date(filters.year, filters.month, 1)
        p_end = date(filters.year, filters.month, last_day)
        run_stmt = run_stmt.where(
            PayrollRun.period_start == p_start, PayrollRun.period_end == p_end
        )
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
        basic = Decimal(str(snap.get("basic_salary", rec.salary_portion)))
        special = Decimal(str(snap.get("special_allowance", "0.00")))
        fot = Decimal(str(snap.get("fixed_ot_amount", "0.00")))
        bonus = Decimal(str(snap.get("bonus_amount", "0.00")))
        tel = Decimal(str(snap.get("telephone_allowance", "0.00")))
        housing = Decimal(str(snap.get("housing_allowance", "0.00")))

        rows.append(
            {
                "worker_id": emp.tally_id if emp else "",
                "worker_name": emp.name if emp else "",
                "grade": emp.staff_grade_description or "Standard" if emp else "Standard",
                "supervisor_name": "Supervisor",
                "group_name": "-",
                "zone_name": "-",
                "standard_hours": float(rec.standard_hours),
                "basic_salary": basic,
                "special_allowance": special,
                "fixed_ot_amount": fot,
                "bonus_amount": bonus,
                "telephone_allowance": tel,
                "housing_allowance": housing,
                "ot1_hours": float(rec.ot1_hours),
                "ot1_amount": rec.ot1_amount,
                "ot2_hours": float(rec.ot2_hours),
                "ot2_amount": rec.ot2_amount,
                "missed_hours_deduction": rec.missed_hours_deduction,
                "gross_pay": rec.gross_pay,
                "net_pay": rec.net_pay,
                "last_salary_change_date": None,
                "salary_delta": Decimal("0.00"),
            }
        )

    rows.sort(key=lambda r: r["worker_name"])
    return rows
