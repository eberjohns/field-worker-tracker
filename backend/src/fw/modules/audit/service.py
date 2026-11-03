from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.modules.audit.models import AuditLog


class AuditService:
    @staticmethod
    async def log_action(
        session: AsyncSession,
        action: str,
        entity_type: str,
        entity_id: str,
        diff: dict[str, Any] | None = None,
        actor_user_id: UUID | None = None,
        actor_role: str | None = None,
        reason: str | None = None,
        ip: str | None = None,
    ) -> AuditLog:
        """Create an append-only audit log entry."""
        log = AuditLog(
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            diff=diff or {},
            reason=reason,
            ip=ip,
        )
        session.add(log)
        await session.flush()
        return log

    @staticmethod
    async def list_logs(
        session: AsyncSession,
        actor_user_id: UUID | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLog]:
        query = select(AuditLog).order_by(AuditLog.created_at.desc())
        if actor_user_id:
            query = query.where(AuditLog.actor_user_id == actor_user_id)
        if entity_type:
            query = query.where(AuditLog.entity_type == entity_type)
        if entity_id:
            query = query.where(AuditLog.entity_id == entity_id)
        if from_time:
            query = query.where(AuditLog.created_at >= from_time)
        if to_time:
            query = query.where(AuditLog.created_at <= to_time)
        query = query.limit(limit).offset(offset)
        result = await session.execute(query)
        return list(result.scalars().all())
