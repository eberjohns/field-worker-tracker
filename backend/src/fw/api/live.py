"""Live map streaming and position polling API endpoints."""

import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import async_session_factory, get_db
from fw.core.errors import AppError
from fw.modules.events import (
    EventsService,
    LivePositionsResponse,
    MobileEventLog,
    StreamTicketResponse,
)
from fw.modules.events.live_publisher import (
    live_position_broadcaster,
    stream_ticket_manager,
)
from fw.modules.identity import User, get_current_user
from fw.modules.jobs import Worksite
from fw.modules.org import Group, OrgService, Zone
from fw.modules.scheduling.models import ScheduledWork

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/live", tags=["live"])


@router.post("/stream-ticket", response_model=StreamTicketResponse)
async def generate_stream_ticket(
    current_user: User = Depends(get_current_user),
) -> StreamTicketResponse:
    """Generate a 30-second one-time ticket to authenticate an EventSource connection."""
    ticket = await stream_ticket_manager.create_ticket(
        user_id=current_user.id,
        role=current_user.role,
        employee_id=current_user.employee_id,
    )
    return StreamTicketResponse(ticket=ticket, expires_in_seconds=30)


@router.get("/stream")
async def live_position_stream(
    request: Request,
    ticket: str = Query(..., description="One-time 30s ticket from /live/stream-ticket"),
) -> StreamingResponse:
    """Server-Sent Events endpoint streaming real-time position updates and state changes."""
    ticket_data = await stream_ticket_manager.consume_ticket(ticket)
    if not ticket_data:
        raise AppError(
            code="INVALID_TICKET",
            message="Stream ticket is invalid or expired",
            status_code=401,
        )

    user_id = ticket_data["user_id"]
    role = ticket_data["role"]
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Determine reporting scope and audit log stream access
    scoped_ids: set[UUID] | None = None
    async with async_session_factory() as session:
        # Fetch user
        user = await session.get(User, user_id)
        if user and role != "ADMIN":
            scoped_list = await OrgService.get_scoped_employee_ids(session, user)
            scoped_ids = set(scoped_list) if scoped_list else set()

        await EventsService.log_live_access(
            session=session,
            user_id=user_id,
            access_type="STREAM",
            filters={"role": role, "stream": True},
            client_ip=client_ip,
            user_agent=user_agent,
        )
        await session.commit()

    subscriber_id = f"{user_id}_{datetime.now(UTC).timestamp()}"
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    await live_position_broadcaster.register_subscriber(
        subscriber_id=subscriber_id,
        queue=queue,
        scoped_employee_ids=scoped_ids,
        is_admin=(role == "ADMIN"),
    )

    async def event_generator():
        try:
            # Initial connection acknowledgement
            yield f"event: ready\ndata: {json.dumps({'status': 'connected', 'as_of': datetime.now(UTC).isoformat()})}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    # Wait up to 20 seconds for an update, then send heartbeat
                    item = await asyncio.wait_for(queue.get(), timeout=20.0)
                    ev_type = item.get("type", "message")
                    data_str = json.dumps(item.get("data", {}))
                    yield f"event: {ev_type}\ndata: {data_str}\n\n"
                except TimeoutError:
                    # 20-second heartbeat per architecture specification
                    yield f": heartbeat {datetime.now(UTC).isoformat()}\n\n"
        finally:
            await live_position_broadcaster.unregister_subscriber(subscriber_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/positions", response_model=LivePositionsResponse)
async def get_live_positions(
    request: Request,
    supervisor_id: UUID | None = Query(None, description="Filter by supervisor"),
    group_id: UUID | None = Query(None, description="Filter by group"),
    state: str | None = Query(None, description="Filter by live state (ACTIVE, OFFLINE, NOT_SCHEDULED)"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> LivePositionsResponse:
    """Get last known verified positions of in-scope workers with calculated live state."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # 1. Audit log polling view
    await EventsService.log_live_access(
        session=session,
        user_id=current_user.id,
        access_type="POLL",
        filters={
            "supervisor_id": str(supervisor_id) if supervisor_id else None,
            "group_id": str(group_id) if group_id else None,
            "state": state,
        },
        client_ip=client_ip,
        user_agent=user_agent,
    )

    # 2. Scope resolution
    scoped_ids: set[UUID] | None = None
    if current_user.role != "ADMIN":
        scoped_list = await OrgService.get_scoped_employee_ids(session, current_user)
        scoped_ids = set(scoped_list) if scoped_list else set()

    # 3. Determine today's date in local time zone (Asia/Dubai default)
    now = datetime.now(UTC)
    local_today = now.astimezone(ZoneInfo("Asia/Dubai")).date()

    # 4. Fetch today's scheduled work
    sched_stmt = (
        select(
            ScheduledWork.employee_id,
            ScheduledWork.worksite_id,
            ScheduledWork.assigned_hours,
            Worksite.job_name.label("worksite_name"),
            Worksite.group_id,
            Group.name.label("group_name"),
            Zone.name.label("zone_name"),
        )
        .outerjoin(Worksite, ScheduledWork.worksite_id == Worksite.id)
        .outerjoin(Group, Worksite.group_id == Group.id)
        .outerjoin(Zone, Worksite.zone_id == Zone.id)
        .where(
            ScheduledWork.work_date == local_today,
            ScheduledWork.status == "ACTIVE",
        )
    )
    sched_rows = (await session.execute(sched_stmt)).all()

    scheduled_employee_ids: set[UUID] = set()
    today_assignments_by_emp: dict[UUID, list[dict[str, Any]]] = {}
    for emp_id, site_id, hours, site_name, g_id, g_name, z_name in sched_rows:
        scheduled_employee_ids.add(emp_id)
        if emp_id not in today_assignments_by_emp:
            today_assignments_by_emp[emp_id] = []
        today_assignments_by_emp[emp_id].append(
            {
                "worksite_id": str(site_id),
                "worksite_name": site_name or "Unknown Worksite",
                "assigned_hours": float(hours) if hours is not None else 0.0,
                "group_id": g_id,
                "group_name": g_name,
                "zone_name": z_name,
            }
        )

    # 5. Query live positions
    return await EventsService.get_live_positions(
        session=session,
        user=current_user,
        scoped_employee_ids=scoped_ids,
        scheduled_employee_ids=scheduled_employee_ids,
        today_assignments_by_emp=today_assignments_by_emp,
        supervisor_id=supervisor_id,
        group_id=group_id,
        state_filter=state,
        as_of=now,
    )


@router.get("/trail/{employee_id}")
async def get_worker_day_trail(
    employee_id: UUID,
    date: str | None = Query(None, description="Date YYYY-MM-DD (defaults to today)"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Retrieve chronological event trail for a worker on a given date (for route drawing)."""
    # Scope check
    if current_user.role != "ADMIN":
        scoped_list = await OrgService.get_scoped_employee_ids(session, current_user)
        if scoped_list and employee_id not in scoped_list and current_user.employee_id != employee_id:
            raise AppError(code="FORBIDDEN", message="Worker outside your scope", status_code=403)

    target_date = datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now(UTC).astimezone(ZoneInfo("Asia/Dubai")).date()

    # Query enriched events for this employee with valid coordinates
    stmt = (
        select(MobileEventLog)
        .where(
            MobileEventLog.employee_id == employee_id,
            MobileEventLog.latitude.is_not(None),
            MobileEventLog.longitude.is_not(None),
        )
        .order_by(MobileEventLog.event_timestamp_utc.asc())
    )
    events = (await session.execute(stmt)).scalars().all()

    # Filter to events falling on the target local date
    tz = ZoneInfo("Asia/Dubai")
    trail = []
    for ev in events:
        local_ev_date = ev.event_timestamp_utc.astimezone(tz).date()
        if local_ev_date == target_date:
            trail.append(
                {
                    "event_id": str(ev.event_id),
                    "event_type": ev.event_type,
                    "latitude": float(ev.latitude) if ev.latitude is not None else None,
                    "longitude": float(ev.longitude) if ev.longitude is not None else None,
                    "accuracy_meters": ev.accuracy_meters,
                    "event_timestamp_utc": ev.event_timestamp_utc.isoformat(),
                    "server_verdict": ev.server_verdict,
                    "server_site_id": str(ev.server_site_id) if ev.server_site_id else None,
                }
            )
    return trail
