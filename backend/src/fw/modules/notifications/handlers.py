"""Event handlers for notifications module."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.events import DomainEvent, event_bus
from fw.modules.notifications.models import Alert
from fw.modules.notifications.service import NotificationService
from fw.modules.scheduling import (
    LeaveApprovedEvent,
    LeaveCancelledEvent,
    ReassignmentApprovedEvent,
)


async def handle_leave_approved(event: DomainEvent, session: AsyncSession) -> None:
    assert isinstance(event, LeaveApprovedEvent)
    await NotificationService.create_alert(
        session=session,
        alert_type="COVER_NEEDED",
        title=f"Cover Needed: {event.worker_name}",
        message=f"{event.worker_name} approved for leave {event.date_from} to {event.date_to}. Shifts require cover.",
        ref_type="LEAVE_REQUEST",
        ref_id=event.leave_id,
        employee_id=event.employee_id,
        target_role="SUPERVISOR",
        details={
            "employee_id": str(event.employee_id),
            "date_from": str(event.date_from),
            "date_to": str(event.date_to),
        },
    )


async def handle_leave_cancelled(event: DomainEvent, session: AsyncSession) -> None:
    assert isinstance(event, LeaveCancelledEvent)
    await NotificationService.resolve_alerts_for_ref(
        session=session,
        ref_type="LEAVE_REQUEST",
        ref_id=event.leave_id,
        resolved_by_user_id=event.cancelled_by_user_id,
    )


async def handle_reassignment_approved(event: DomainEvent, session: AsyncSession) -> None:
    assert isinstance(event, ReassignmentApprovedEvent)
    if event.leave_request_id:
        await NotificationService.resolve_alerts_for_ref(
            session=session,
            ref_type="LEAVE_REQUEST",
            ref_id=event.leave_request_id,
            resolved_by_user_id=event.approved_by_user_id,
        )
    if event.original_employee_id:
        stmt = select(Alert).where(
            Alert.alert_type == "COVER_NEEDED",
            Alert.employee_id == event.original_employee_id,
            Alert.status == "OPEN",
        )
        alerts = (await session.execute(stmt)).scalars().all()
        now = datetime.now(UTC)
        for a in alerts:
            a.status = "RESOLVED"
            a.resolved_at = now
            a.resolved_by_user_id = event.approved_by_user_id


def register_notification_handlers() -> None:
    """Register all synchronous event handlers for notifications."""
    event_bus.subscribe_sync(LeaveApprovedEvent, handle_leave_approved)  # type: ignore
    event_bus.subscribe_sync(LeaveCancelledEvent, handle_leave_cancelled)  # type: ignore
    event_bus.subscribe_sync(ReassignmentApprovedEvent, handle_reassignment_approved)  # type: ignore
