"""Job budget routes (DEC-59). Money is Admin only (DEC-47); other roles get hours."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.core.errors import AppError
from fw.modules.budget.repository import BudgetRepository
from fw.modules.budget.schemas import NewWorksiteBudgetPreview, WorksiteBudgetVsActualItem
from fw.modules.budget.service import BudgetService
from fw.modules.identity import User, get_current_user, require_role
from fw.modules.jobs import JobItemBudget, JobItemCreate
from fw.modules.scheduling import AccessScope

router = APIRouter(tags=["budget"])


async def _visible_worksite_or_404(session: AsyncSession, user: User, worksite_id: UUID):  # noqa: ANN202
    scope = await AccessScope.resolve(session, user)
    rows = await BudgetRepository.worksites_with_items(
        session, worksite_ids=[worksite_id], active_only=user.role != "ADMIN"
    )
    if not rows or not scope.can_view_worksite(worksite_id):
        raise AppError(code="NOT_FOUND", message="Worksite not found.", status_code=404)
    return rows[0]


@router.get("/payroll/budget-vs-actual", response_model=list[WorksiteBudgetVsActualItem])
async def get_budget_vs_actual(
    country: str | None = None,
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    as_of: date | None = None,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> list[WorksiteBudgetVsActualItem]:
    """Planned vs actual hours and cost for all active worksites.

    Default range: each worksite's current contract year. ``as_of`` alone: the contract year up
    to that date. Planned cost is pro-rated by day; actual cost is approved payroll allocations.
    """
    return await BudgetService.planned_vs_actual(
        session, is_admin=True, country=country, date_from=date_from, date_to=date_to, as_of=as_of
    )


@router.get("/worksites/{worksite_id}/planned-vs-actual", response_model=WorksiteBudgetVsActualItem)
async def get_worksite_planned_vs_actual(
    worksite_id: UUID,
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorksiteBudgetVsActualItem:
    """Planned vs actual for one worksite, per job item and month. Hours for every role that
    can see the worksite (DEC-57); money only for Admin."""
    await _visible_worksite_or_404(session, current_user, worksite_id)
    rows = await BudgetService.planned_vs_actual(
        session,
        is_admin=current_user.role == "ADMIN",
        worksite_ids=[worksite_id],
        date_from=date_from,
        date_to=date_to,
    )
    if not rows:
        raise AppError(code="NOT_FOUND", message="Worksite not found.", status_code=404)
    return rows[0]


@router.post("/worksites/{worksite_id}/job-items/budget-preview", response_model=JobItemBudget)
async def preview_job_item_budget(
    worksite_id: UUID,
    payload: JobItemCreate,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> JobItemBudget:
    """Man-hours (and, for Admin, cost) of an unsaved job item on a worksite. Saves nothing."""
    ws = await _visible_worksite_or_404(session, current_user, worksite_id)
    return await BudgetService.preview_item(
        session, payload, is_admin=current_user.role == "ADMIN", worksite=ws
    )


@router.post("/job-items/budget-preview", response_model=JobItemBudget)
async def preview_new_worksite_item_budget(
    payload: NewWorksiteBudgetPreview,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> JobItemBudget:
    """Same, for a job item of a worksite that is not saved yet (Add Worksite form)."""
    return await BudgetService.preview_item(
        session,
        payload.item,
        is_admin=current_user.role == "ADMIN",
        country=payload.country,
        salary_revision_code=payload.salary_revision_code,
        contract_start=payload.contract_start,
        contract_end=payload.contract_end,
    )
