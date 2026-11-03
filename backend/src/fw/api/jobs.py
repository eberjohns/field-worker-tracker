"""API endpoints for Worksites, Job Items, Boundaries, and Occurrences (Phase 04)."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.modules.identity import User, get_current_user, require_role
from fw.modules.jobs import (
    BoundaryCopyRequest,
    BoundaryCopyToRequest,
    BoundaryQueueResponse,
    BoundaryUpdateRequest,
    GenerateOccurrencesRequest,
    JobItemCreate,
    JobItemResponse,
    JobItemUpdate,
    JobItemValidationResponse,
    JobOccurrenceResponse,
    JobOccurrenceUpdate,
    JobsService,
    WorksiteCreate,
    WorksiteDetailResponse,
    WorksiteResponse,
    WorksiteUpdate,
)

router = APIRouter(tags=["jobs"])


# --- Worksites ---
@router.get("/worksites", response_model=list[WorksiteResponse])
async def list_worksites(
    q: str | None = Query(None, description="Search by job number or name"),
    group_id: UUID | None = None,
    zone_id: UUID | None = None,
    country: str | None = None,
    has_boundary: bool | None = None,
    is_active: bool | None = True,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[WorksiteResponse]:
    """List worksites with optional filtering."""
    return await JobsService.list_worksites(
        session=session,
        q=q,
        group_id=group_id,
        zone_id=zone_id,
        country=country,
        has_boundary=has_boundary,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )


@router.post("/worksites", response_model=WorksiteResponse, status_code=status.HTTP_201_CREATED)
async def create_worksite(
    payload: WorksiteCreate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> WorksiteResponse:
    """Create a worksite record (Admin only)."""
    return await JobsService.create_worksite(
        session=session,
        payload=payload,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )


@router.get("/worksites/{worksite_id}", response_model=WorksiteDetailResponse)
async def get_worksite_detail(
    worksite_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorksiteDetailResponse:
    """Get full details of a worksite including items and boundary GeoJSON."""
    return await JobsService.get_worksite(session=session, worksite_id=worksite_id)


@router.patch("/worksites/{worksite_id}", response_model=WorksiteResponse)
async def update_worksite(
    worksite_id: UUID,
    payload: WorksiteUpdate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> WorksiteResponse:
    """Update worksite metadata with optimistic locking (Admin only)."""
    return await JobsService.update_worksite(
        session=session,
        worksite_id=worksite_id,
        payload=payload,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )


# --- Boundaries & Queue ---
@router.get("/boundary-queue", response_model=BoundaryQueueResponse)
async def get_boundary_queue(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> BoundaryQueueResponse:
    """Get boundary setup queue with progress and unset entities (D6)."""
    return await JobsService.get_boundary_queue(
        session=session,
        limit=limit,
        offset=offset,
    )


@router.put("/worksites/{worksite_id}/boundary", response_model=WorksiteDetailResponse)
async def update_worksite_boundary(
    worksite_id: UUID,
    payload: BoundaryUpdateRequest,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> WorksiteDetailResponse:
    """Set or update worksite polygon boundary."""
    return await JobsService.update_worksite_boundary(
        session=session,
        worksite_id=worksite_id,
        geojson_dict=payload.boundary,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )


@router.post("/worksites/{worksite_id}/copy-boundary", response_model=WorksiteDetailResponse)
async def copy_boundary_from(
    worksite_id: UUID,
    payload: BoundaryCopyRequest,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> WorksiteDetailResponse:
    """Copy boundary polygon from source worksite into this worksite."""
    return await JobsService.copy_boundary(
        session=session,
        target_worksite_id=worksite_id,
        source_worksite_id=payload.source_worksite_id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )


@router.post("/worksites/{worksite_id}/copy-boundary-to", response_model=list[WorksiteResponse])
async def copy_boundary_to_targets(
    worksite_id: UUID,
    payload: BoundaryCopyToRequest,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> list[WorksiteResponse]:
    """Copy this worksite's boundary to one or more target worksites."""
    return await JobsService.copy_boundary_to_multiple(
        session=session,
        source_worksite_id=worksite_id,
        target_worksite_ids=payload.target_worksite_ids,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )


@router.put("/accommodations/{accommodation_id}/boundary", status_code=status.HTTP_204_NO_CONTENT)
async def update_accommodation_boundary(
    accommodation_id: UUID,
    payload: BoundaryUpdateRequest,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Update accommodation camp boundary polygon."""
    await JobsService.update_accommodation_boundary(
        session=session,
        accommodation_id=accommodation_id,
        geojson_dict=payload.boundary,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )


# --- Job Items ---
@router.post(
    "/worksites/{worksite_id}/job-items",
    response_model=JobItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_job_item(
    worksite_id: UUID,
    payload: JobItemCreate,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> JobItemResponse:
    """Create a job item under a worksite."""
    return await JobsService.create_job_item(
        session=session,
        worksite_id=worksite_id,
        payload=payload,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )


@router.patch("/job-items/{job_item_id}", response_model=JobItemResponse)
async def update_job_item(
    job_item_id: UUID,
    payload: JobItemUpdate,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> JobItemResponse:
    """Update a job item with optimistic locking."""
    return await JobsService.update_job_item(
        session=session,
        job_item_id=job_item_id,
        payload=payload,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )


@router.post(
    "/job-items/{job_item_id}/generate-occurrences", response_model=list[JobOccurrenceResponse]
)
async def generate_occurrences(
    job_item_id: UUID,
    payload: GenerateOccurrencesRequest = GenerateOccurrencesRequest(),
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> list[JobOccurrenceResponse]:
    """Trigger occurrence generation for a job item across rolling horizon."""
    return await JobsService.generate_job_occurrences(
        session=session,
        job_item_id=job_item_id,
        from_date=payload.from_date,
        to_date=payload.to_date,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )


@router.get("/job-items/{job_item_id}/validation", response_model=JobItemValidationResponse)
async def get_job_item_validation(
    job_item_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> JobItemValidationResponse:
    """Get validation calculations for job item validation panel."""
    return await JobsService.get_job_item_validation(session=session, job_item_id=job_item_id)


# --- Occurrences ---
@router.get("/occurrences", response_model=list[JobOccurrenceResponse])
async def list_occurrences(
    job_item_id: UUID | None = None,
    worksite_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    status: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[JobOccurrenceResponse]:
    """List job occurrences with filtering."""
    return await JobsService.list_occurrences(
        session=session,
        job_item_id=job_item_id,
        worksite_id=worksite_id,
        from_date=from_date,
        to_date=to_date,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.patch("/occurrences/{occurrence_id}", response_model=JobOccurrenceResponse)
async def update_occurrence(
    occurrence_id: UUID,
    payload: JobOccurrenceUpdate,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> JobOccurrenceResponse:
    """Update occurrence due date or status."""
    return await JobsService.update_occurrence(
        session=session,
        occurrence_id=occurrence_id,
        payload=payload,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
