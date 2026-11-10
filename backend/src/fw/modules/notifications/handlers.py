"""Event handlers for notifications module."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.events import (
    DomainEvent,
    LocationDisabledRecorded,
    LocationEnabledRecorded,
    event_bus,
)
from fw.modules.notifications.models import Alert
from fw.modules.notifications.service import NotificationService
from fw.modules.org import Employee
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


async def handle_location_disabled(event: DomainEvent, session: AsyncSession) -> None:
    assert isinstance(event, LocationDisabledRecorded)
    if not event.employee_id:
        return

    # Check if TRACKING_INTERRUPTED is already open for this employee
    existing = await session.execute(
        select(Alert.id).where(
            Alert.alert_type == "TRACKING_INTERRUPTED",
            Alert.employee_id == event.employee_id,
            Alert.status == "OPEN",
        )
    )
    if existing.scalar_one_or_none() is not None:
        return

    emp = await session.get(Employee, event.employee_id)
    emp_name = emp.name if emp else "Field Worker"

    await NotificationService.create_alert(
        session=session,
        alert_type="TRACKING_INTERRUPTED",
        title=f"Tracking Interrupted: {emp_name}",
        message=f"Location tracking was disabled on {emp_name}'s device.",
        ref_type="LOCATION_EVENT",
        ref_id=event.event_id,
        employee_id=event.employee_id,
        target_role="SUPERVISOR",
        details={
            "employee_id": str(event.employee_id),
            "event_id": str(event.event_id) if event.event_id else None,
            "captured_at": str(event.captured_at) if event.captured_at else None,
        },
    )


async def handle_location_enabled(event: DomainEvent, session: AsyncSession) -> None:
    assert isinstance(event, LocationEnabledRecorded)
    if not event.employee_id:
        return

    # Resolve open TRACKING_INTERRUPTED alerts for this employee
    stmt = select(Alert).where(
        Alert.alert_type == "TRACKING_INTERRUPTED",
        Alert.employee_id == event.employee_id,
        Alert.status == "OPEN",
    )
    alerts = (await session.execute(stmt)).scalars().all()
    now = datetime.now(UTC)
    for a in alerts:
        a.status = "RESOLVED"
        a.resolved_at = now
    if alerts:
        await session.flush()


_HANDLERS_REGISTERED = False


def register_notification_handlers() -> None:
    """Register all synchronous event handlers for notifications."""
    global _HANDLERS_REGISTERED
    if _HANDLERS_REGISTERED:
        return
    _HANDLERS_REGISTERED = True

    event_bus.subscribe_sync(LeaveApprovedEvent, handle_leave_approved)  # type: ignore
    event_bus.subscribe_sync(LeaveCancelledEvent, handle_leave_cancelled)  # type: ignore
    event_bus.subscribe_sync(ReassignmentApprovedEvent, handle_reassignment_approved)  # type: ignore
    event_bus.subscribe_sync(LocationDisabledRecorded, handle_location_disabled)  # type: ignore
    event_bus.subscribe_sync(LocationEnabledRecorded, handle_location_enabled)  # type: ignore
