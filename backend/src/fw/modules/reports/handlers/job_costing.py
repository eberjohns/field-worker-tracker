"""Handler for Job Costing Report (Admin Only, DEC-29)."""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.modules.jobs.models import Worksite
from fw.modules.payroll.service import PayrollService
from fw.modules.reports.schemas import ReportFilterParams


async def fetch_job_costing(
    session: AsyncSession,
    filters: ReportFilterParams,
    scoped_ids: set[UUID] | None = None,
) -> list[dict[str, Any]]:
    """Query contract budget vs actual labor costs allocated by worked minutes."""
    as_of = filters.date_to or None
    items = await PayrollService.get_budget_vs_actual(
        session=session,
        country=filters.country,
        as_of_date=as_of,
    )

    ws_res = await session.execute(select(Worksite))
    ws_map = {w.id: w for w in ws_res.scalars().all()}

    rows: list[dict[str, Any]] = []
    for it in items:
        if filters.worksite_id and it.worksite_id != filters.worksite_id:
            continue

        ws = ws_map.get(it.worksite_id)
        start_d = ws.start_date if ws else None
        end_d = ws.end_date if ws else None

        rows.append(
            {
                "worksite_code": it.job_number or (ws.job_number if ws else ""),
                "worksite_name": it.job_name or (ws.job_name if ws else ""),
                "contract_start_date": start_d,
                "contract_end_date": end_d,
                "contract_budget": it.annual_labor_budget,
                "actual_labour_cost": it.actual_cost_allocated,
                "prorated_budget": it.prorated_budget,
                "variance_amount": it.variance,
                "variance_pct": float(it.variance_percent),
            }
        )

    rows.sort(key=lambda r: r["worksite_name"])
    return rows
