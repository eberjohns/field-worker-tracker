"""API routes for pending visits follow-up workflow."""

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.modules.attendance import (
    PendingVisitCloseRequest,
    PendingVisitExplainRequest,
    PendingVisitListResponse,
    PendingVisitRescheduleRequest,
    PendingVisitsService,
)
from fw.modules.identity import User, get_current_user, require_role

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/pending-visits", tags=["pending-visits"])


@router.get("", response_model=PendingVisitListResponse)
async def list_pending_visits(
    status: str | None = Query(None, description="Filter by status (OPEN, EXPLAINED, RESCHEDULED, CLOSED)"),
    from_date: date | None = Query(None, description="Filter due_date >= from_date"),
    to_date: date | None = Query(None, description="Filter due_date <= to_date"),
    worksite_id: UUID | None = Query(None, description="Filter by worksite"),
    supervisor_id: UUID | None = Query(None, description="Filter by supervisor"),
    employee_id: UUID | None = Query(None, description="Filter by employee"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> PendingVisitListResponse:
    """List pending visits with filtering and escalation status."""
    return await PendingVisitsService.get_pending_visits(
        session=session,
        user=current_user,
        status=status,
        from_date=from_date,
        to_date=to_date,
        worksite_id=worksite_id,
        supervisor_id=supervisor_id,
        employee_id=employee_id,
    )


@router.post("/{id}/explain")
async def explain_pending_visit(
    id: UUID,
    payload: PendingVisitExplainRequest,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER", "SUPERVISOR")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Supervisor/Engineer adds a pending visit explanation comment; moves status to EXPLAINED."""
    await PendingVisitsService.explain_pending_visit(
        session=session,
        pending_visit_id=id,
        user=current_user,
        explanation=payload.explanation,
    )
    return {"message": "Pending visit explained successfully", "status": "EXPLAINED"}


@router.post("/{id}/reschedule")
async def reschedule_pending_visit(
    id: UUID,
    payload: PendingVisitRescheduleRequest,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Engineer reschedules pending visit, creating Scheduled Work with source FOLLOW_UP."""
    await PendingVisitsService.reschedule_pending_visit(
        session=session,
        pending_visit_id=id,
        user=current_user,
        work_date=payload.work_date,
        employee_ids=payload.employee_ids,
    )
    return {"message": "Pending visit rescheduled successfully", "status": "RESCHEDULED"}


@router.post("/{id}/close")
async def close_pending_visit(
    id: UUID,
    payload: PendingVisitCloseRequest,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Engineer closes pending visit with a required explanation reason."""
    await PendingVisitsService.close_pending_visit(
        session=session,
        pending_visit_id=id,
        user=current_user,
        reason=payload.reason,
    )
    return {"message": "Pending visit closed successfully", "status": "CLOSED"}


@router.post("/detect")
async def trigger_detect_pending_visits(
    target_date: date | None = Query(None, description="Date to run day-close detection on (defaults to yesterday)"),
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Trigger day-close pending visit detection job on demand."""
    if not target_date:
        today = datetime.now(UTC).astimezone(ZoneInfo("Asia/Dubai")).date()
        target_date = today
    count = await PendingVisitsService.detect_pending_visits(session=session, target_date=target_date)
    return {"detected_count": count, "target_date": str(target_date)}
