"""Live position publisher and SSE stream ticket management."""

import asyncio
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import structlog

logger = structlog.get_logger(__name__)


class StreamTicketManager:
    """Manages short-lived (30s) single-use tickets for SSE stream authentication."""

    def __init__(self, expiry_seconds: int = 30) -> None:
        self._expiry_seconds = expiry_seconds
        # ticket -> {"user_id": UUID, "role": str, "employee_id": UUID | None, "expires_at": datetime}
        self._tickets: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def create_ticket(
        self,
        user_id: UUID,
        role: str,
        employee_id: UUID | None = None,
    ) -> str:
        ticket = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(seconds=self._expiry_seconds)
        async with self._lock:
            # Purge expired
            now = datetime.now(UTC)
            expired = [k for k, v in self._tickets.items() if v["expires_at"] < now]
            for k in expired:
                self._tickets.pop(k, None)

            self._tickets[ticket] = {
                "user_id": user_id,
                "role": role,
                "employee_id": employee_id,
                "expires_at": expires_at,
            }
        return ticket

    async def consume_ticket(self, ticket: str) -> dict[str, Any] | None:
        async with self._lock:
            data = self._tickets.pop(ticket, None)
            if not data:
                return None
            if data["expires_at"] < datetime.now(UTC):
                return None
            return data


class LivePositionBroadcaster:
    """Broadcaster for live position updates to connected SSE clients.

    Acts as the LivePositionPublisher adapter with in-memory subscriber queues
    and PostgreSQL NOTIFY support.
    """

    def __init__(self) -> None:
        # subscriber_id -> {"queue": asyncio.Queue, "scoped_employee_ids": set[UUID] | None, "is_admin": bool}
        self._subscribers: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

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
        """Broadcast a position update to all subscribers whose scope covers this employee."""
        message = {
            "type": "position",
            "data": payload,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        async with self._lock:
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


# Global singletons
stream_ticket_manager = StreamTicketManager(expiry_seconds=30)
live_position_broadcaster = LivePositionBroadcaster()
