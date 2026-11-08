"""Service layer for Notifications and Alerts."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.errors import AppError
from fw.modules.identity.models import User
from fw.modules.notifications.models import Alert
from fw.modules.org.service import OrgService


class NotificationService:
    """Service for creating, querying, and resolving alerts."""

    @staticmethod
    async def create_alert(
        session: AsyncSession,
        alert_type: str,
        title: str,
        message: str,
        ref_type: str,
        ref_id: UUID | None = None,
        employee_id: UUID | None = None,
        target_user_id: UUID | None = None,
        target_role: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> Alert:
        """Create a new open alert."""
        alert = Alert(
            alert_type=alert_type,
            title=title,
            message=message,
            ref_type=ref_type,
            ref_id=ref_id,
            employee_id=employee_id,
            target_user_id=target_user_id,
            target_role=target_role,
            details=details or {},
            status="OPEN",
        )
        session.add(alert)
        await session.flush()
        return alert

    @staticmethod
    async def resolve_alert(
        session: AsyncSession,
        alert_id: UUID,
        resolved_by: User,
    ) -> Alert:
        """Mark an alert as resolved."""
        stmt = select(Alert).where(Alert.id == alert_id)
        alert = (await session.execute(stmt)).scalar_one_or_none()
        if not alert:
            raise AppError(code="NOT_FOUND", message="Alert not found", status_code=404)

        if alert.status == "RESOLVED":
            return alert

        alert.status = "RESOLVED"
        alert.resolved_at = datetime.now(UTC)
        alert.resolved_by_user_id = resolved_by.id
        await session.flush()
        return alert

    @staticmethod
    async def resolve_alerts_for_ref(
        session: AsyncSession,
        ref_type: str,
        ref_id: UUID,
        resolved_by_user_id: UUID | None = None,
    ) -> int:
        """Resolve all open alerts pointing to a specific reference object."""
        stmt = select(Alert).where(
            Alert.ref_type == ref_type,
            Alert.ref_id == ref_id,
            Alert.status == "OPEN",
        )
        alerts = (await session.execute(stmt)).scalars().all()
        now = datetime.now(UTC)
        count = 0
        for a in alerts:
            a.status = "RESOLVED"
            a.resolved_at = now
            a.resolved_by_user_id = resolved_by_user_id
            count += 1
        if count > 0:
            await session.flush()
        return count

    @staticmethod
    async def get_open_alerts(
        session: AsyncSession,
        user: User,
    ) -> list[Alert]:
        """Fetch open alerts visible to the given user based on their role and reporting scope."""
        if user.role == "ADMIN":
            stmt = select(Alert).where(Alert.status == "OPEN").order_by(Alert.created_at.desc())
            return list((await session.execute(stmt)).scalars().all())

        # Scoped to reporting tree
        scoped_ids = await OrgService.get_scoped_employee_ids(session, user)

        conditions = [
            Alert.target_user_id == user.id,
            Alert.target_role == user.role,
        ]
        if scoped_ids:
            conditions.append(Alert.employee_id.in_(scoped_ids))
        elif user.employee_id:
            conditions.append(Alert.employee_id == user.employee_id)

        stmt = (
            select(Alert)
            .where(Alert.status == "OPEN", or_(*conditions))
            .order_by(Alert.created_at.desc())
        )
        return list((await session.execute(stmt)).scalars().all())
