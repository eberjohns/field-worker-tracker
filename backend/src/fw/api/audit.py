from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.modules.audit import AuditLogRead, AuditService
from fw.modules.identity import User, require_role

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=list[AuditLogRead])
async def list_audit_logs(
    actor_user_id: UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> list[AuditLogRead]:
    logs = await AuditService.list_logs(
        session=session,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        from_time=from_time,
        to_time=to_time,
        limit=limit,
        offset=offset,
    )
    return [AuditLogRead.model_validate(log) for log in logs]
