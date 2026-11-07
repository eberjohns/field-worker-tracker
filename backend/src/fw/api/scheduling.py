"""FastAPI routes for Planner: standing assignments, daily scheduled work, roster, and coverage."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.modules.identity import User, get_current_user, require_role
from fw.modules.scheduling import (
    BasePlannerResponse,
    BaseRosterTemplateCreate,
    BaseRosterTemplateRead,
    CandidateRecommendationRead,
    CoverageResponse,
    OperationalCoverageResponse,
    OperationalRosterResponse,
    OperationalShiftCreate,
    RosterResponse,
    ScheduledWorkBatchCreate,
    ScheduledWorkCreate,
    ScheduledWorkRead,
    ScheduledWorkReorderRequest,
    ScheduledWorkUpdate,
    ScheduledWorkValidateRequest,
    SchedulingService,
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
    work_date: date | None = Query(None, description="Target date for allocation (defaults to today)"),
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
    return await service.get_candidate_recommendations(occurrence_id=id, target_date=date, weekday=weekday)


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
    return await service.get_candidate_recommendations(job_item_id=id, target_date=date, weekday=weekday)


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


@router.post("/base-planner/templates", response_model=BaseRosterTemplateRead, status_code=status.HTTP_201_CREATED)
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


@router.post("/operational-planner/shifts", response_model=ScheduledWorkRead, status_code=status.HTTP_201_CREATED)
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

