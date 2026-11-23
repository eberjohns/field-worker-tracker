"""FastAPI router for Month-End Payroll, Salary Revisions, and Job Budget."""

import email
import io
from datetime import date
from email import policy
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.core.errors import AppError
from fw.modules.identity import User, get_current_user, require_role
from fw.modules.lookups import LookupService
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
)
from fw.modules.payroll.service import PayrollService
from fw.rules.lookups import GRADE_CODE, sort_values, value_key

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
    current_user: User = Depends(require_role("ADMIN")),  # DEC-47: salary and cost
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
    current_user: User = Depends(require_role("ADMIN")),  # DEC-47: salary and cost
    session: AsyncSession = Depends(get_db),
) -> PayrollRunDetailRead:
    """Get payroll run detail with worker records."""
    return await PayrollService.get_payroll_run_detail(
        session=session,
        run_id=run_id,
        scoped_employee_ids=None,
    )


@router.get("/payroll/runs/{run_id}/issues", response_model=PayrollRunIssuesResponse)
async def get_payroll_run_issues(
    run_id: UUID,
    current_user: User = Depends(require_role("ADMIN")),  # DEC-47: salary and cost
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
    current_user: User = Depends(require_role("ADMIN")),  # DEC-47: salary and cost
    session: AsyncSession = Depends(get_db),
) -> list[PayrollRecordRead]:
    """List payroll records for a run (Admin only)."""
    detail = await PayrollService.get_payroll_run_detail(
        session=session,
        run_id=run_id,
        scoped_employee_ids=None,
    )
    return detail.records


@router.get(
    "/mobile/me/payroll",
    response_model=WorkerMobilePayrollSlip | list[WorkerMobilePayrollSlip],
    tags=["mobile", "payroll"],
)
async def get_mobile_payroll(
    period: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkerMobilePayrollSlip | list[WorkerMobilePayrollSlip]:
    """Worker's own approved monthly payroll records (employer provisions stripped).

    If period=YYYY-MM is provided, returns that specific month's approved slip (or 404).
    If period is omitted, returns the list of all approved slips.
    """
    if not current_user.employee_id:
        raise AppError(
            code="NO_EMPLOYEE_LINKED",
            message="User account is not linked to an employee profile.",
            status_code=400,
        )

    slips = await PayrollService.get_worker_approved_slips(
        session=session,
        employee_id=current_user.employee_id,
        period=period,
    )
    if period:
        if not slips:
            raise AppError(
                code="PAYROLL_NOT_FOUND",
                message=f"No approved payroll slip found for period '{period}'.",
                status_code=404,
            )
        return slips[0]
    return slips


@router.get(
    "/payroll/my-records",
    response_model=list[WorkerMobilePayrollSlip],
    tags=["payroll"],
)
async def get_my_payroll_records(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[WorkerMobilePayrollSlip]:
    """Worker's own approved monthly payroll records for web view."""
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


@router.get("/grades", response_model=list[str])
async def list_grade_codes(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[str]:
    """Grade codes for dropdowns: the managed list plus codes in use (DEC-58, DEC-60).

    Deprecated: use ``GET /lookups/grade_code``.
    """
    in_use = await PayrollService.list_grade_codes(session=session)
    rows = await LookupService.list_values(session, GRADE_CODE, include_inactive=True)
    known = {r.value_key for r in rows}
    values = [r.value for r in rows if r.is_active] + [
        c for c in in_use if value_key(c) not in known
    ]
    return sort_values(GRADE_CODE, values)


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
    current_user: User = Depends(require_role("ADMIN")),  # DEC-47: salary and cost
    session: AsyncSession = Depends(get_db),
) -> SalaryRevisionDetailRead:
    """Get full details of a salary revision with grade lines and calculated planned rates."""
    return await PayrollService.get_revision_detail(session=session, code=code)


@router.get("/salary-revisions/{code}/export-template")
async def export_salary_revision_template(
    code: str,
    current_user: User = Depends(require_role("ADMIN")),  # DEC-47: salary and cost
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Download professionally formatted Excel (.xlsx) template pre-populated with revision lines."""
    xlsx_bytes = await PayrollService.export_salary_revision_template(
        session=session, revision_code=code
    )
    filename = f"salary_revision_{code}_template.xlsx"
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


@router.post("/salary-revisions/preview-file", response_model=SalaryRevisionImportDiffResponse)
async def preview_salary_revision_file(
    request: Request,
    target_revision_code: str | None = Query(None, description="Target revision code to create"),
    base_revision_code: str | None = Query(None, description="Base revision code for comparison"),
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> SalaryRevisionImportDiffResponse:
    """Upload Excel (.xlsx/.xls) or CSV template to parse and calculate side-by-side diff against base revision."""
    content_type = request.headers.get("content-type", "")
    body = await request.body()
    if not body:
        raise AppError(code="EMPTY_FILE", message="Uploaded file is empty", status_code=400)

    filename = "template.xlsx"
    file_bytes = body
    target_code = target_revision_code or "NEW-REVISION"
    base_code = base_revision_code

    if "multipart/form-data" in content_type:
        msg = email.message_from_bytes(
            f"Content-Type: {content_type}\r\n\r\n".encode() + body, policy=policy.default
        )
        for part in msg.iter_parts():
            fn = part.get_filename()
            name = part.get_param("name", header="content-disposition")
            if fn:
                filename = fn
                raw_payload = part.get_payload(decode=True)
                if isinstance(raw_payload, bytes):
                    file_bytes = raw_payload
                elif isinstance(raw_payload, str):
                    file_bytes = raw_payload.encode()
            elif name == "target_revision_code":
                text = part.get_content()
                if text and text.strip():
                    target_code = text.strip()
            elif name == "base_revision_code":
                text = part.get_content()
                if text and text.strip():
                    base_code = text.strip()

    if not file_bytes:
        raise AppError(code="EMPTY_FILE", message="No valid file found in upload", status_code=400)

    return await PayrollService.preview_salary_revision_file(
        session=session,
        file_content=file_bytes,
        filename=filename,
        target_revision_code=target_code,
        base_revision_code=base_code,
    )


@router.put("/payroll/worksites/{worksite_id}/revision")
async def update_worksite_revision(
    worksite_id: UUID,
    revision_code: str | None = Query(
        None, description="Salary revision code to bind, or empty/null to clear"
    ),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN")),
):
    """Bind a specific salary revision code to a worksite for job budget calculation."""
    from fw.modules.jobs.models import Worksite

    ws = await session.get(Worksite, worksite_id)
    if not ws:
        raise AppError("WORKSITE_NOT_FOUND", "Worksite not found", status_code=404)
    ws.salary_revision_code = (
        revision_code.strip() if revision_code and revision_code.strip() else None
    )
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
