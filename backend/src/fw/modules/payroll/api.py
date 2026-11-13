"""FastAPI router for Month-End Payroll, Salary Revisions, and Job Budget."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.core.errors import AppError
from fw.modules.identity import User, get_current_user, require_role
from fw.modules.org import ScopeService
from fw.modules.payroll.schemas import (
    PayrollRecordRead,
    PayrollRunCreate,
    PayrollRunDetailRead,
    PayrollRunIssuesResponse,
    PayrollRunRead,
    SalaryRevisionCreate,
    SalaryRevisionDetailRead,
    SalaryRevisionImportDiffResponse,
    SalaryRevisionLineCreate,
    SalaryRevisionRead,
    WorkerMobilePayrollSlip,
    WorksiteBudgetVsActualItem,
)
from fw.modules.payroll.service import PayrollService

router = APIRouter(tags=["payroll"])


# --- Payroll Runs & Approvals ---


@router.post(
    "/payroll/runs",
    response_model=PayrollRunDetailRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_payroll_run(
    payload: PayrollRunCreate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> PayrollRunDetailRead:
    """Generate or re-run a DRAFT payroll run for a month."""
    return await PayrollService.generate_draft_run(
        session=session,
        payload=payload,
        user_id=current_user.id,
        actor_role=current_user.role,
    )


@router.get("/payroll/runs", response_model=list[PayrollRunRead])
async def list_payroll_runs(
    country: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> list[PayrollRunRead]:
    """List payroll runs with status, totals, and run counts."""
    return await PayrollService.list_runs(
        session=session,
        country=country,
        status=status_filter,
    )


@router.get("/payroll/runs/{run_id}", response_model=PayrollRunDetailRead)
async def get_payroll_run(
    run_id: UUID,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> PayrollRunDetailRead:
    """Get payroll run detail with worker records."""
    scoped_employee_ids: list[UUID] | None = None
    if current_user.role == "ENGINEER":
        scoped_set = await ScopeService.get_scoped_employee_ids(session, current_user)
        scoped_employee_ids = list(scoped_set) if scoped_set is not None else None

    return await PayrollService.get_payroll_run_detail(
        session=session,
        run_id=run_id,
        scoped_employee_ids=scoped_employee_ids,
    )


@router.get("/payroll/runs/{run_id}/issues", response_model=PayrollRunIssuesResponse)
async def get_payroll_run_issues(
    run_id: UUID,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> PayrollRunIssuesResponse:
    """List issues needing review before approval (unapproved OT, missing salary structures)."""
    return await PayrollService.get_run_issues(session=session, run_id=run_id)


@router.post("/payroll/runs/{run_id}/approve", response_model=PayrollRunRead)
async def approve_payroll_run(
    run_id: UUID,
    notes: str | None = None,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> PayrollRunRead:
    """Approve a DRAFT payroll run: freeze it, snapshot records, and lock month attendance."""
    return await PayrollService.approve_run(
        session=session,
        run_id=run_id,
        user_id=current_user.id,
        reason=notes,
    )


@router.get("/payroll/records", response_model=list[PayrollRecordRead])
async def list_payroll_records(
    run_id: UUID,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> list[PayrollRecordRead]:
    """List payroll records for a run, scoped to user."""
    scoped_employee_ids: list[UUID] | None = None
    if current_user.role == "ENGINEER":
        scoped_set = await ScopeService.get_scoped_employee_ids(session, current_user)
        scoped_employee_ids = list(scoped_set) if scoped_set is not None else None

    detail = await PayrollService.get_payroll_run_detail(
        session=session,
        run_id=run_id,
        scoped_employee_ids=scoped_employee_ids,
    )
    return detail.records


@router.get("/mobile/me/payroll", response_model=list[WorkerMobilePayrollSlip])
@router.get("/payroll/my-records", response_model=list[WorkerMobilePayrollSlip])
async def get_my_payroll_records(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[WorkerMobilePayrollSlip]:
    """Worker's own approved monthly payroll records (employer provisions stripped)."""
    if not current_user.employee_id:
        raise AppError(
            code="NO_EMPLOYEE_LINKED",
            message="User account is not linked to an employee profile.",
            status_code=400,
        )

    return await PayrollService.get_worker_approved_slips(
        session=session,
        employee_id=current_user.employee_id,
    )


# --- Salary Revisions ---


@router.get("/salary-revisions", response_model=list[SalaryRevisionRead])
async def list_salary_revisions(
    country: str | None = None,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> list[SalaryRevisionRead]:
    """List all salary revisions."""
    return await PayrollService.list_revisions(session=session, country=country)


@router.get("/salary-revisions/{code}", response_model=SalaryRevisionDetailRead)
async def get_salary_revision_detail(
    code: str,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> SalaryRevisionDetailRead:
    """Get full details of a salary revision with grade lines and calculated planned rates."""
    return await PayrollService.get_revision_detail(session=session, code=code)


@router.post(
    "/salary-revisions",
    response_model=SalaryRevisionDetailRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_salary_revision(
    payload: SalaryRevisionCreate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> SalaryRevisionDetailRead:
    """Create a new salary revision with grade lines."""
    return await PayrollService.create_revision(
        session=session,
        payload=payload,
        user_id=current_user.id,
    )


@router.post("/salary-revisions/diff", response_model=SalaryRevisionImportDiffResponse)
async def diff_salary_revision(
    target_revision_code: str,
    incoming_lines: list[SalaryRevisionLineCreate],
    base_revision_code: str | None = None,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> SalaryRevisionImportDiffResponse:
    """Produce a side-by-side diff comparing incoming revision lines against a base revision."""
    return await PayrollService.diff_salary_revision_import(
        session=session,
        target_revision_code=target_revision_code,
        base_revision_code=base_revision_code,
        incoming_lines=incoming_lines,
    )


# --- Job Budget vs Actual ---


@router.get("/payroll/budget-vs-actual", response_model=list[WorksiteBudgetVsActualItem])
async def get_budget_vs_actual(
    country: str | None = None,
    as_of: date | None = None,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> list[WorksiteBudgetVsActualItem]:
    """Calculate dynamic contract budget from assigned revision lines and items vs actual allocated cost."""
    return await PayrollService.get_budget_vs_actual(
        session=session,
        country=country,
        as_of_date=as_of,
    )


@router.put("/payroll/worksites/{worksite_id}/revision")
async def update_worksite_revision(
    worksite_id: UUID,
    revision_code: str | None = Query(None, description="Salary revision code to bind, or empty/null to clear"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN")),
):
    """Bind a specific salary revision code to a worksite for job budget calculation."""
    from fw.modules.jobs.models import Worksite

    ws = await session.get(Worksite, worksite_id)
    if not ws:
        raise AppError("WORKSITE_NOT_FOUND", "Worksite not found", status_code=404)
    ws.salary_revision_code = revision_code.strip() if revision_code and revision_code.strip() else None
    await session.commit()
    return {"worksite_id": str(worksite_id), "salary_revision_code": ws.salary_revision_code}



# --- Automated Background Runner ---


@router.post("/payroll/auto-run-check", response_model=list[PayrollRunRead])
async def trigger_auto_draft_check(
    as_of: date | None = None,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> list[PayrollRunRead]:
    """Check for completed previous calendar months past delay days and auto-generate draft."""
    return await PayrollService.check_auto_draft_runs(session=session, as_of_date=as_of)
