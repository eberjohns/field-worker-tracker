from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class DomainEvent:
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def event_name(self) -> str:
        return self.__class__.__name__


@dataclass
class ScheduledWorkChanged(DomainEvent):
    employee_ids: list[UUID] = field(default_factory=list)
    work_date: Any = None


@dataclass
class HolidayChanged(DomainEvent):
    country: str = "AE"
    holiday_date: Any = None


@dataclass
class TimeRuleChanged(DomainEvent):
    country: str = "AE"
    effective_from: Any = None


@dataclass
class EmployeeProfileChanged(DomainEvent):
    employee_id: UUID | None = None


@dataclass
class WorksiteBoundaryChanged(DomainEvent):
    worksite_id: UUID | None = None


@dataclass
class AccommodationBoundaryChanged(DomainEvent):
    accommodation_id: UUID | None = None


@dataclass
class SyncChangesCommitted(DomainEvent):
    employee_id: UUID | None = None
    latest_cursor: int = 0
    priority: int = 0


@dataclass
class EventsIngested(DomainEvent):
    employee_id: UUID | None = None
    event_ids: list[UUID] = field(default_factory=list)
    affected_work_dates: list[Any] = field(default_factory=list)


@dataclass
class LocationDisabledRecorded(DomainEvent):
    employee_id: UUID | None = None
    captured_at: Any = None


@dataclass
class LocationEnabledRecorded(DomainEvent):
    employee_id: UUID | None = None
    captured_at: Any = None


SyncHandler = Callable[[Any, Any], Awaitable[None]]
PostCommitHandler = Callable[[Any], Awaitable[None]]


class EventBus:
    """In-process domain event bus.

    Supports synchronous handlers (executed within the caller's transaction/session)
    and asynchronous post-commit handlers (for debounced jobs, notifications, etc.).
    """

    def __init__(self) -> None:
        self._sync_handlers: dict[type[DomainEvent], list[SyncHandler]] = defaultdict(list)
        self._post_commit_handlers: dict[type[DomainEvent], list[PostCommitHandler]] = defaultdict(
            list
        )

    def subscribe_sync(self, event_type: type[DomainEvent], handler: SyncHandler) -> None:
        if handler not in self._sync_handlers[event_type]:
            self._sync_handlers[event_type].append(handler)

    def subscribe_post_commit(
        self, event_type: type[DomainEvent], handler: PostCommitHandler
    ) -> None:
        if handler not in self._post_commit_handlers[event_type]:
            self._post_commit_handlers[event_type].append(handler)

    async def publish(self, event: DomainEvent, session: Any = None) -> None:
        """Publish an event to all synchronous handlers."""
        handlers = self._sync_handlers.get(type(event), [])
        for handler in handlers:
            try:
                await handler(event, session)
            except Exception as e:
                logger.error(
                    "sync_event_handler_failed",
                    domain_event=event.event_name,
                    handler=handler.__name__,
                    error=str(e),
                )
                raise

    async def publish_post_commit(self, event: DomainEvent) -> None:
        """Publish an event to all post-commit handlers."""
        handlers = self._post_commit_handlers.get(type(event), [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(
                    "post_commit_event_handler_failed",
                    domain_event=event.event_name,
                    handler=handler.__name__,
                    error=str(e),
                )


# Global singleton event bus
event_bus = EventBus()
