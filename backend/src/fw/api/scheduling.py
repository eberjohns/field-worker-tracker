"""FastAPI routes for Planner: standing assignments, daily scheduled work, roster, and coverage."""

import email
from datetime import date
from email import policy
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.modules.identity import User, get_current_user, require_role
from fw.modules.scheduling import (
    ApprovalsInboxResponse,
    BasePlannerResponse,
    BaseRosterTemplateCreate,
    BaseRosterTemplateRead,
    CandidateRecommendationRead,
    CoverageResponse,
    LeaveDecisionRequest,
    LeaveRequestCreate,
    LeaveRequestResponse,
    LeaveTakenWorkerSummary,
    OperationalCoverageResponse,
    OperationalRosterResponse,
    OperationalShiftCreate,
    ReassignmentDecisionRequest,
    ReassignmentPreviewRequest,
    ReassignmentPreviewResponse,
    ReassignmentRequestCreate,
    ReassignmentResponse,
    RosterResponse,
    ScheduledWorkBatchCreate,
    ScheduledWorkCreate,
    ScheduledWorkRead,
    ScheduledWorkReorderRequest,
    ScheduledWorkUpdate,
    ScheduledWorkValidateRequest,
    SchedulingService,
    StaffingGapsResponse,
    StandingAssignmentCreate,
    StandingAssignmentEndRequest,
    StandingAssignmentRead,
    ValidationReportRead,
    WorkerAllocationResponse,
)

router = APIRouter(tags=["scheduling"])


# -------------------------------------------------------------------------
# Weekly Roster & Excel Export
# -------------------------------------------------------------------------


@router.get("/roster", response_model=None)
async def get_weekly_roster(
    week_start: date = Query(..., description="Start date of the week (Monday)"),
    supervisor_id: UUID | None = Query(None),
    engineer_id: UUID | None = Query(None),
    group_id: UUID | None = Query(None),
    staff_type: str | None = Query(None),
    grade_group: str | None = Query(None),
    problems_only: bool = Query(False),
    format: str | None = Query(None, description="Set to 'xlsx' for Excel export"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> Response | RosterResponse:
    """Fetch weekly roster grid (Workers x Days) or export Excel spreadsheet."""
    service = SchedulingService(session)

    if format and format.lower() == "xlsx":
        excel_bytes = await service.export_roster_excel(week_start=week_start)
        filename = f"roster_{week_start.isoformat()}.xlsx"
        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return await service.get_weekly_roster(
        week_start=week_start,
        supervisor_id=supervisor_id,
        engineer_id=engineer_id,
        group_id=group_id,
        staff_type=staff_type,
        grade_group=grade_group,
        problems_only=problems_only,
    )


# -------------------------------------------------------------------------
# Job Coverage View
# -------------------------------------------------------------------------


@router.get("/schedule/coverage", response_model=CoverageResponse)
async def get_schedule_coverage(
    week_start: date = Query(..., description="Start date of the week (Monday)"),
    group_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CoverageResponse:
    """Job-centred coverage view: worksites > items > daily staffing and TO_BE_COVERED slots."""
    service = SchedulingService(session)
    return await service.get_coverage_view(week_start=week_start, group_id=group_id)


# -------------------------------------------------------------------------
# Worker Allocation (Capacity Side Panel)
# -------------------------------------------------------------------------


@router.get("/workers/{id}/allocation", response_model=WorkerAllocationResponse)
async def get_worker_allocation(
    id: UUID,
    work_date: date | None = Query(
        None, description="Target date for allocation (defaults to today)"
    ),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkerAllocationResponse:
    """Allocated hours per day/week/month against standard hours (feeds the side panel)."""
    service = SchedulingService(session)
    return await service.get_worker_allocation(employee_id=id, work_date=work_date)


# -------------------------------------------------------------------------
# Candidate Recommendations (DEC-52)
# -------------------------------------------------------------------------


@router.get("/occurrences/{id}/recommendations", response_model=list[CandidateRecommendationRead])
async def get_occurrence_recommendations(
    id: UUID,
    date: date | None = Query(None),
    weekday: str | None = Query(None),
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> list[CandidateRecommendationRead]:
    """Ranked worker candidates for an occurrence by grade group, exact staff type first."""
    service = SchedulingService(session)
    return await service.get_candidate_recommendations(
        occurrence_id=id, target_date=date, weekday=weekday
    )


@router.get("/job-items/{id}/recommendations", response_model=list[CandidateRecommendationRead])
async def get_job_item_recommendations(
    id: UUID,
    date: date | None = Query(None),
    weekday: str | None = Query(None),
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> list[CandidateRecommendationRead]:
    """Ranked worker candidates for a job item by grade group, exact staff type first."""
    service = SchedulingService(session)
    return await service.get_candidate_recommendations(
        job_item_id=id, target_date=date, weekday=weekday
    )


# -------------------------------------------------------------------------
# Standing Assignments (The Year Plan)
# -------------------------------------------------------------------------


@router.get("/standing-assignments", response_model=list[StandingAssignmentRead])
async def list_standing_assignments(
    job_item_id: UUID | None = Query(None),
    employee_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[StandingAssignmentRead]:
    """List active standing team assignments."""
    service = SchedulingService(session)
    return await service.list_standing_assignments(job_item_id=job_item_id, employee_id=employee_id)


@router.post(
    "/standing-assignments",
    response_model=StandingAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_standing_assignment(
    payload: StandingAssignmentCreate,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> StandingAssignmentRead:
    """Create standing assignment and materialize daily ScheduledWork for 13 months."""
    service = SchedulingService(session)
    return await service.create_standing_assignment(
        payload=payload, current_user_id=current_user.id
    )


@router.post("/standing-assignments/{id}/end", response_model=StandingAssignmentRead)
async def end_standing_assignment(
    id: UUID,
    payload: StandingAssignmentEndRequest,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> StandingAssignmentRead:
    """End a standing assignment from a date and cancel future unstarted scheduled work."""
    service = SchedulingService(session)
    return await service.end_standing_assignment(
        assignment_id=id, payload=payload, current_user_id=current_user.id
    )


# -------------------------------------------------------------------------
# Scheduled Work (Daily Assignments) & Validation
# -------------------------------------------------------------------------


@router.post("/scheduled-work/validate", response_model=ValidationReportRead)
async def validate_scheduled_work(
    payload: ScheduledWorkValidateRequest,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER", "SUPERINTENDENT", "SUPERVISOR")),
    session: AsyncSession = Depends(get_db),
) -> ValidationReportRead:
    """Dry-run validation for a proposed assignment (returns errors and warnings)."""
    service = SchedulingService(session)
    is_admin = current_user.role == "ADMIN"
    return await service.validate_scheduled_work_request(payload, is_admin=is_admin)


@router.post(
    "/scheduled-work",
    response_model=ScheduledWorkRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_scheduled_work(
    payload: ScheduledWorkCreate,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> ScheduledWorkRead:
    """Create direct scheduled work assignment (with warnings check)."""
    service = SchedulingService(session)
    is_admin = current_user.role == "ADMIN"
    return await service.create_scheduled_work(
        payload=payload, current_user_id=current_user.id, is_admin=is_admin
    )


@router.post(
    "/scheduled-work/batch",
    response_model=list[ScheduledWorkRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_scheduled_work_batch(
    payload: ScheduledWorkBatchCreate,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> list[ScheduledWorkRead]:
    """Batch assign multiple workers to a job item on a work date."""
    service = SchedulingService(session)
    is_admin = current_user.role == "ADMIN"
    return await service.create_scheduled_work_batch(
        payload=payload, current_user_id=current_user.id, is_admin=is_admin
    )


@router.delete("/scheduled-work/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_scheduled_work(
    id: UUID,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Cancel / unassign a scheduled work assignment."""
    service = SchedulingService(session)
    await service.cancel_scheduled_work(scheduled_work_id=id, current_user_id=current_user.id)


@router.patch("/scheduled-work/{id}", response_model=ScheduledWorkRead)
async def update_scheduled_work(
    id: UUID,
    payload: ScheduledWorkUpdate,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> ScheduledWorkRead:
    """Update assigned hours, sequence, or cancel scheduled work."""
    service = SchedulingService(session)
    is_admin = current_user.role == "ADMIN"
    return await service.update_scheduled_work(
        scheduled_work_id=id, payload=payload, current_user_id=current_user.id, is_admin=is_admin
    )


@router.post("/scheduled-work/reorder", response_model=list[ScheduledWorkRead])
async def reorder_scheduled_work(
    payload: ScheduledWorkReorderRequest,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> list[ScheduledWorkRead]:
    """Reorder multiple daily visits for an employee on a work date."""
    service = SchedulingService(session)
    return await service.reorder_scheduled_work(payload=payload, current_user_id=current_user.id)


# -------------------------------------------------------------------------
# Base Planner (Blueprint Recurring Engine) Endpoints
# -------------------------------------------------------------------------


@router.get("/base-planner/worksites", response_model=BasePlannerResponse)
async def get_base_planner_worksites(
    group_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> BasePlannerResponse:
    """Fetch worksites and items with base roster templates for Base Planner."""
    service = SchedulingService(session)
    return await service.get_base_planner_worksites(group_id=group_id)


@router.get("/base-planner/templates/{job_item_id}", response_model=BaseRosterTemplateRead | None)
async def get_base_template(
    job_item_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> BaseRosterTemplateRead | None:
    """Fetch active Base Roster Template for a job item."""
    service = SchedulingService(session)
    return await service.get_base_template(job_item_id)


@router.post(
    "/base-planner/templates",
    response_model=BaseRosterTemplateRead,
    status_code=status.HTTP_201_CREATED,
)
async def save_base_template(
    payload: BaseRosterTemplateCreate,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER", "SUPERVISOR")),
    session: AsyncSession = Depends(get_db),
) -> BaseRosterTemplateRead:
    """Create or update active Base Roster Template for a job item."""
    service = SchedulingService(session)
    return await service.save_base_template(payload, current_user_id=current_user.id)


# -------------------------------------------------------------------------
# Operational Planner Endpoints
# -------------------------------------------------------------------------


@router.get("/operational-planner/coverage", response_model=OperationalCoverageResponse)
async def get_operational_coverage(
    week_start: date = Query(..., description="Start date of the week (Monday)"),
    group_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> OperationalCoverageResponse:
    """Fetch weekly operational coverage matrix (job items x 7 days) with base blueprint & overrides."""
    service = SchedulingService(session)
    return await service.get_operational_coverage(week_start=week_start, group_id=group_id)


@router.get("/operational-planner/roster", response_model=OperationalRosterResponse)
async def get_operational_roster(
    week_start: date = Query(..., description="Start date of the week (Monday)"),
    group_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> OperationalRosterResponse:
    """Fetch weekly operational worker roster (workers x 7 days)."""
    service = SchedulingService(session)
    return await service.get_operational_roster(week_start=week_start, group_id=group_id)


@router.post(
    "/operational-planner/shifts",
    response_model=ScheduledWorkRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_operational_shift(
    payload: OperationalShiftCreate,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER", "SUPERVISOR")),
    session: AsyncSession = Depends(get_db),
) -> ScheduledWorkRead:
    """Create a single-day operational shift or cover replacement."""
    service = SchedulingService(session)
    return await service.create_operational_shift(payload, current_user_id=current_user.id)


@router.delete("/operational-planner/shifts/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_operational_shift(
    shift_id: UUID,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER", "SUPERVISOR")),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Cancel an operational shift."""
    service = SchedulingService(session)
    await service.delete_operational_shift(shift_id, current_user_id=current_user.id)


# -------------------------------------------------------------------------
# Leave Requests (Doc 08, D2, DEC-46)
# -------------------------------------------------------------------------


@router.post(
    "/leave-requests",
    response_model=LeaveRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_leave_request(
    payload: LeaveRequestCreate,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER", "SUPERVISOR")),
    session: AsyncSession = Depends(get_db),
) -> LeaveRequestResponse:
    """Record a new leave request (>= 3 days notice for supervisors)."""
    service = SchedulingService(session)
    return await service.create_leave_request(payload, current_user)


@router.get("/leave-requests/summary", response_model=list[LeaveTakenWorkerSummary])
async def get_leave_taken_summary(
    year: int = Query(..., description="Calendar year for leave taken count"),
    employee_id: UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[LeaveTakenWorkerSummary]:
    """Get leave taken summary per worker, leave type, and calendar year (working vs calendar days)."""
    service = SchedulingService(session)
    return await service.get_leave_taken_summary(
        year=year, employee_id=employee_id, current_user=current_user
    )


@router.get("/leave-requests/template.xlsx")
async def download_leave_template(
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Download sample Leave import template Excel file (Admin only)."""
    service = SchedulingService(session)
    file_bytes = service.generate_leave_template_excel()
    return Response(
        content=file_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=leave_import_template.xlsx"},
    )


@router.post("/leave-requests/import")
async def import_leaves_excel(
    request: Request,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Import leaves from Excel spreadsheet (Admin only)."""
    service = SchedulingService(session)
    content_type = request.headers.get("content-type", "")
    body = await request.body()
    if not body:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "EMPTY_FILE", "message": "Uploaded file is empty."},
        )

    file_bytes: bytes = body
    if "multipart/form-data" in content_type:
        msg = email.message_from_bytes(
            f"Content-Type: {content_type}\r\n\r\n".encode() + body,
            policy=policy.default,
        )
        for part in msg.iter_parts():
            fn = part.get_filename()
            if fn:
                raw_payload = part.get_payload(decode=True)
                if isinstance(raw_payload, bytes):
                    file_bytes = raw_payload
                elif isinstance(raw_payload, str):
                    file_bytes = raw_payload.encode()
                break

    return await service.import_leaves_from_excel(file_bytes, current_user)


@router.get("/leave-requests", response_model=list[LeaveRequestResponse])
async def list_leave_requests(
    employee_id: UUID | None = Query(None),
    status: str | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[LeaveRequestResponse]:
    """List leave requests in user's reporting scope."""
    service = SchedulingService(session)
    return await service.list_leave_requests(
        employee_id=employee_id,
        status=status,
        from_date=from_date,
        to_date=to_date,
        current_user=current_user,
    )


@router.get("/leave-requests/{leave_id}", response_model=LeaveRequestResponse)
async def get_leave_request(
    leave_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> LeaveRequestResponse:
    """Fetch single leave request by ID."""
    service = SchedulingService(session)
    return await service.get_leave_request(leave_id)


@router.post("/leave-requests/{leave_id}/approve", response_model=LeaveRequestResponse)
async def approve_leave_request(
    leave_id: UUID,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> LeaveRequestResponse:
    """Approve a leave request (Engineer or Admin)."""
    service = SchedulingService(session)
    return await service.approve_leave_request(leave_id, current_user)


@router.post("/leave-requests/{leave_id}/reject", response_model=LeaveRequestResponse)
async def reject_leave_request(
    leave_id: UUID,
    payload: LeaveDecisionRequest,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> LeaveRequestResponse:
    """Reject a leave request with mandatory reason."""
    service = SchedulingService(session)
    return await service.reject_leave_request(
        leave_id, reason=payload.reason, current_user=current_user
    )


@router.post("/leave-requests/{leave_id}/cancel", response_model=LeaveRequestResponse)
async def cancel_leave_request(
    leave_id: UUID,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER", "SUPERVISOR")),
    session: AsyncSession = Depends(get_db),
) -> LeaveRequestResponse:
    """Cancel an approved or requested leave."""
    service = SchedulingService(session)
    return await service.cancel_leave_request(leave_id, current_user)


# -------------------------------------------------------------------------
# Reassignment Requests (Doc 08, D2, DEC-43)
# -------------------------------------------------------------------------


@router.post(
    "/reassignment-requests",
    response_model=ReassignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_reassignment_request(
    payload: ReassignmentRequestCreate,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER", "SUPERINTENDENT", "SUPERVISOR")),
    session: AsyncSession = Depends(get_db),
) -> ReassignmentResponse:
    """Create a temporary reassignment request (strictly >= 3 days notice)."""
    service = SchedulingService(session)
    return await service.create_reassignment_request(payload, current_user)


@router.post("/reassignment-requests/preview", response_model=ReassignmentPreviewResponse)
async def preview_reassignment(
    payload: ReassignmentPreviewRequest,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER", "SUPERINTENDENT", "SUPERVISOR")),
    session: AsyncSession = Depends(get_db),
) -> ReassignmentPreviewResponse:
    """Preview worker hours impact and constraint warnings."""
    service = SchedulingService(session)
    return await service.preview_reassignment(payload, current_user)


@router.get("/reassignment-requests", response_model=list[ReassignmentResponse])
async def list_reassignment_requests(
    status: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[ReassignmentResponse]:
    """List reassignment requests in user scope."""
    service = SchedulingService(session)
    return await service.list_reassignment_requests(
        status=status,
        date_from=date_from,
        date_to=date_to,
        current_user=current_user,
    )


@router.get("/reassignment-requests/{request_id}", response_model=ReassignmentResponse)
async def get_reassignment_request(
    request_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ReassignmentResponse:
    """Fetch reassignment request by ID."""
    service = SchedulingService(session)
    return await service.get_reassignment_request(request_id)


@router.post("/reassignment-requests/{request_id}/approve", response_model=ReassignmentResponse)
async def approve_reassignment_request(
    request_id: UUID,
    payload: ReassignmentDecisionRequest | None = None,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> ReassignmentResponse:
    """Approve a reassignment request (Engineer or Admin)."""
    service = SchedulingService(session)
    return await service.approve_reassignment_request(
        request_id=request_id,
        decision_note=payload.decision_note if payload else None,
        current_user=current_user,
    )


@router.post("/reassignment-requests/{request_id}/reject", response_model=ReassignmentResponse)
async def reject_reassignment_request(
    request_id: UUID,
    payload: ReassignmentDecisionRequest,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> ReassignmentResponse:
    """Reject a reassignment request with mandatory reason."""
    service = SchedulingService(session)
    return await service.reject_reassignment_request(
        request_id=request_id,
        reason=payload.decision_note or "",
        current_user=current_user,
    )


@router.post("/reassignment-requests/{request_id}/cancel", response_model=ReassignmentResponse)
async def cancel_reassignment_request(
    request_id: UUID,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER", "SUPERINTENDENT", "SUPERVISOR")),
    session: AsyncSession = Depends(get_db),
) -> ReassignmentResponse:
    """Cancel a pending reassignment request."""
    service = SchedulingService(session)
    return await service.cancel_reassignment_request(request_id, current_user)


# -------------------------------------------------------------------------
# Approvals Inbox & Staffing Gaps (Doc 08, D2, DEC-43)
# -------------------------------------------------------------------------


@router.get("/approvals", response_model=ApprovalsInboxResponse)
async def get_approvals_inbox(
    status: str | None = Query(
        "PENDING", description="Filter status: PENDING, APPROVED, REJECTED, DECIDED, ALL"
    ),
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> ApprovalsInboxResponse:
    """Get approvals inbox items (leave requests, reassignments) in scope with badge counts."""
    service = SchedulingService(session)
    return await service.get_approvals_inbox(current_user=current_user, status=status)


@router.get("/staffing-gaps", response_model=StaffingGapsResponse)
async def get_staffing_gaps(
    from_date: date = Query(..., description="Start of date range"),
    to_date: date = Query(..., description="End of date range"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> StaffingGapsResponse:
    """Get staffing gaps (TO_BE_COVERED slots from leave) needing cover in scope."""
    service = SchedulingService(session)
    return await service.get_staffing_gaps(
        from_date=from_date, to_date=to_date, current_user=current_user
    )
