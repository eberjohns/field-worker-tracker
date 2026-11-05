"""FastAPI routes for Planner: standing assignments, daily scheduled work, roster, and coverage."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.modules.identity import User, get_current_user, require_role
from fw.modules.scheduling import (
    CandidateRecommendationRead,
    CoverageResponse,
    RosterResponse,
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
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> list[CandidateRecommendationRead]:
    """Ranked worker candidates for an occurrence by grade group, exact staff type first."""
    service = SchedulingService(session)
    return await service.get_candidate_recommendations(occurrence_id=id, target_date=date)


@router.get("/job-items/{id}/recommendations", response_model=list[CandidateRecommendationRead])
async def get_job_item_recommendations(
    id: UUID,
    date: date | None = Query(None),
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> list[CandidateRecommendationRead]:
    """Ranked worker candidates for a job item by grade group, exact staff type first."""
    service = SchedulingService(session)
    return await service.get_candidate_recommendations(job_item_id=id, target_date=date)


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
