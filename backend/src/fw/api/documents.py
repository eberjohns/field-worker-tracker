"""API routes for employee document validity and expiration tracking."""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.modules.identity import User, get_current_user, require_role
from fw.modules.notifications import NotificationService
from fw.modules.org import (
    ExpiringDocumentsResponse,
    OrgService,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/expiring", response_model=ExpiringDocumentsResponse)
async def list_expiring_documents(
    within_days: int | None = Query(
        None, description="Lead days threshold (defaults to company setting)"
    ),
    document_type: str | None = Query(
        None,
        description="Filter by document type (VISA, PASSPORT, EMIRATES_ID, LABOUR_CARD, DRIVING_LICENCE)",
    ),
    supervisor_id: UUID | None = Query(None, description="Filter by supervisor"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ExpiringDocumentsResponse:
    """Retrieve expiring and expired documents with validity indicators."""
    return await OrgService.get_expiring_documents(
        session=session,
        user=current_user,
        within_days=within_days,
        document_type=document_type,
        supervisor_id=supervisor_id,
    )


@router.post("/check-alerts")
async def trigger_document_expiry_alerts(
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Admin-triggered job to scan documents and raise DOC_EXPIRY alerts."""
    count = await NotificationService.check_document_expiry_alerts(session)
    return {"alerts_created": count}
