"""FastAPI router for alerts."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.modules.identity import User, get_current_user
from fw.modules.notifications.schemas import AlertResolveRequest, AlertResponse
from fw.modules.notifications.service import NotificationService

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[AlertResponse]:
    """List open alerts visible to current user (scoped)."""
    alerts = await NotificationService.get_open_alerts(session, current_user)
    return [AlertResponse.model_validate(a) for a in alerts]


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(
    alert_id: UUID,
    payload: AlertResolveRequest | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AlertResponse:
    """Resolve an open alert."""
    alert = await NotificationService.resolve_alert(session, alert_id, current_user)
    return AlertResponse.model_validate(alert)
