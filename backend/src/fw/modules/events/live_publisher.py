"""Live position publisher and SSE stream ticket management."""

import asyncio
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import asyncpg
import structlog
from sqlalchemy import update

from fw.core.config import get_settings
from fw.core.db import async_session_factory
from fw.modules.events.models import EmployeeLastPosition, StreamTicket

logger = structlog.get_logger(__name__)


class StreamTicketManager:
    """Manages short-lived (30s) single-use tickets for SSE stream authentication in PostgreSQL."""

    def __init__(self, expiry_seconds: int = 30) -> None:
        self._expiry_seconds = expiry_seconds

    async def create_ticket(
        self,
        user_id: UUID,
        role: str,
        employee_id: UUID | None = None,
    ) -> str:
        ticket = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(seconds=self._expiry_seconds)
        async with async_session_factory() as session:
            db_ticket = StreamTicket(
                ticket=ticket,
                user_id=user_id,
                role=role,
                employee_id=employee_id,
                created_at=datetime.now(UTC),
                expires_at=expires_at,
            )
            session.add(db_ticket)
            await session.commit()
        return ticket

    async def consume_ticket(self, ticket: str) -> dict[str, Any] | None:
        """Atomically validate and consume a single-use ticket."""
        now = datetime.now(UTC)
        async with async_session_factory() as session:
            stmt = (
                update(StreamTicket)
                .where(
                    StreamTicket.ticket == ticket,
                    StreamTicket.consumed_at.is_(None),
                    StreamTicket.expires_at > now,
                )
                .values(consumed_at=now)
                .returning(
                    StreamTicket.user_id,
                    StreamTicket.role,
                    StreamTicket.employee_id,
                )
            )
            res = await session.execute(stmt)
            row = res.first()
            await session.commit()
            if not row:
                return None
            return {
                "user_id": row.user_id,
                "role": row.role,
                "employee_id": row.employee_id,
            }


class LivePositionBroadcaster:
    """Broadcaster for live position updates to connected SSE clients.

    Maintains in-memory subscriber queues for local SSE clients, and listens on
    PostgreSQL channel `live_positions` to fan out updates across multiple processes.
    """

    def __init__(self) -> None:
        # subscriber_id -> {"queue": asyncio.Queue, "scoped_employee_ids": set[UUID] | None, "is_admin": bool}
        self._subscribers: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._recent_broadcasts: dict[UUID, tuple[str | None, str | None]] = {}
        self._listener_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    async def register_subscriber(
        self,
        subscriber_id: str,
        queue: asyncio.Queue,
        scoped_employee_ids: set[UUID] | None,
        is_admin: bool = False,
    ) -> None:
        async with self._lock:
            self._subscribers[subscriber_id] = {
                "queue": queue,
                "scoped_employee_ids": scoped_employee_ids,
                "is_admin": is_admin,
            }
        logger.debug("sse_subscriber_registered", subscriber_id=subscriber_id)

    async def unregister_subscriber(self, subscriber_id: str) -> None:
        async with self._lock:
            self._subscribers.pop(subscriber_id, None)
        logger.debug("sse_subscriber_unregistered", subscriber_id=subscriber_id)

    async def broadcast_position_update(
        self,
        employee_id: UUID,
        payload: dict[str, Any],
    ) -> None:
        """Broadcast a position update to local subscribers."""
        await self._fanout_position(employee_id, payload)

    async def _fanout_position(
        self,
        employee_id: UUID,
        payload: dict[str, Any],
    ) -> None:
        """Deliver position update to matching local subscriber queues, suppressing duplicates."""
        key = (payload.get("event_timestamp_utc"), payload.get("event_type"))
        async with self._lock:
            if self._recent_broadcasts.get(employee_id) == key:
                return
            self._recent_broadcasts[employee_id] = key
            if len(self._recent_broadcasts) > 10000:
                self._recent_broadcasts.clear()

            message = {
                "type": "position",
                "data": payload,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            for sub_id, sub_info in self._subscribers.items():
                if sub_info["is_admin"] or (
                    sub_info["scoped_employee_ids"] is not None
                    and employee_id in sub_info["scoped_employee_ids"]
                ):
                    try:
                        sub_info["queue"].put_nowait(message)
                    except asyncio.QueueFull:
                        logger.warning("sse_queue_full_skipping", subscriber_id=sub_id)

    async def broadcast_state_change(
        self,
        employee_id: UUID,
        live_state: str,
    ) -> None:
        """Broadcast an ACTIVE/NO_RECENT_SIGNAL/TRACKING_DISABLED state change."""
        message = {
            "type": "state",
            "data": {
                "employee_id": str(employee_id),
                "live_state": live_state,
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }
        async with self._lock:
            for sub_info in self._subscribers.values():
                if sub_info["is_admin"] or (
                    sub_info["scoped_employee_ids"] is not None
                    and employee_id in sub_info["scoped_employee_ids"]
                ):
                    try:
                        sub_info["queue"].put_nowait(message)
                    except asyncio.QueueFull:
                        pass

    def _on_pg_notify(self, connection: Any, pid: int, channel: str, payload: str) -> None:
        """Callback when PostgreSQL NOTIFY live_positions arrives."""
        asyncio.create_task(self._handle_pg_notification(payload))

    async def _handle_pg_notification(self, payload: str) -> None:
        """Handle incoming NOTIFY payload, resolving position and fanning out to local subscribers."""
        # 1. Try if payload is direct JSON
        try:
            data = json.loads(payload)
            if isinstance(data, dict) and "employee_id" in data:
                emp_id = UUID(str(data["employee_id"]))
                await self._fanout_position(emp_id, data)
                return
        except Exception:
            pass

        # 2. Try if payload is employee_id UUID
        try:
            emp_id = UUID(payload.strip())
            async with async_session_factory() as session:
                pos = await session.get(EmployeeLastPosition, emp_id)
                if pos:
                    pos_payload = {
                        "employee_id": str(pos.employee_id),
                        "latitude": float(pos.latitude) if pos.latitude is not None else None,
                        "longitude": float(pos.longitude) if pos.longitude is not None else None,
                        "accuracy_meters": pos.accuracy_meters,
                        "event_type": pos.event_type,
                        "event_timestamp_utc": pos.event_timestamp_utc.isoformat(),
                        "server_verdict": pos.server_verdict,
                        "server_site_id": str(pos.server_site_id) if pos.server_site_id else None,
                        "tracking_enabled": pos.tracking_enabled,
                        "last_contact_at": pos.last_contact_at.isoformat(),
                    }
                    await self._fanout_position(emp_id, pos_payload)
        except Exception as exc:
            logger.debug("handle_live_position_notification_failed", error=str(exc))

    async def _listen_loop(self) -> None:
        """Background loop that maintains PostgreSQL LISTEN connection on channel `live_positions`."""
        settings = get_settings()
        if "sqlite" in settings.DATABASE_URL.lower():
            logger.info("pg_listen_skipped_sqlite")
            return

        dsn = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        while not self._stop_event.is_set():
            conn = None
            try:
                conn = await asyncpg.connect(dsn)
                await conn.add_listener("live_positions", self._on_pg_notify)
                logger.info("pg_listen_live_positions_connected")
                await self._stop_event.wait()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("pg_listen_connection_error", error=str(exc))
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=5.0)
                except TimeoutError:
                    pass
            finally:
                if conn:
                    try:
                        await conn.remove_listener("live_positions", self._on_pg_notify)
                        await conn.close()
                    except Exception:
                        pass

    async def start_listener(self) -> None:
        """Start the background LISTEN loop."""
        if self._listener_task and not self._listener_task.done():
            return
        self._stop_event.clear()
        self._listener_task = asyncio.create_task(self._listen_loop())

    async def stop_listener(self) -> None:
        """Stop the background LISTEN loop."""
        self._stop_event.set()
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None


# Global singletons
stream_ticket_manager = StreamTicketManager(expiry_seconds=30)
live_position_broadcaster = LivePositionBroadcaster()
