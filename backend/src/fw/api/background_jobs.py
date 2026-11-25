"""Background job status (Batch 9 step 4): the page polls a job it started."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.core.errors import AppError
from fw.modules.identity import User, get_current_user
from fw.modules.tasks import BackgroundJobRead, BackgroundJobService

router = APIRouter(prefix="/background-jobs", tags=["background-jobs"])


@router.get("", response_model=list[BackgroundJobRead])
async def list_background_jobs(
    kind: str | None = None,
    active: bool = Query(False, description="Only QUEUED or RUNNING jobs"),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[BackgroundJobRead]:
    """Recent jobs, newest first: all of them for an Admin, otherwise the caller's own."""
    jobs = await BackgroundJobService.list_recent(
        session,
        kind=kind,
        active_only=active,
        user_id=None if current_user.role == "ADMIN" else current_user.id,
        limit=limit,
    )
    return [BackgroundJobRead.model_validate(j) for j in jobs]


@router.get("/{job_id}", response_model=BackgroundJobRead)
async def get_background_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> BackgroundJobRead:
    """One job's status and progress. An Admin sees any job; others only their own."""
    job = await BackgroundJobService.get(session, job_id)
    if job is None or (current_user.role != "ADMIN" and job.created_by_user_id != current_user.id):
        raise AppError(code="NOT_FOUND", message="Background job not found", status_code=404)
    return BackgroundJobRead.model_validate(job)
