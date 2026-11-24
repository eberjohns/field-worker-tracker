"""FWT Core module - configuration, database, clock, logging, domain events, errors."""

from fw.core.clock import (
    Clock,
    FrozenClock,
    SystemClock,
    get_country_timezone,
    site_now,
    site_today,
)
from fw.core.config import Settings, get_settings
from fw.core.db import Base, async_session_factory, get_db
from fw.core.errors import AppError, ProblemDetailsException
from fw.core.events import (
    AccommodationBoundaryChanged,
    DomainEvent,
    EmployeeProfileChanged,
    EventBus,
    HolidayChanged,
    LocationDisabledRecorded,
    LocationEnabledRecorded,
    ScheduledWorkChanged,
    ScheduledWorkRemoved,
    SyncChangesCommitted,
    TimeRuleChanged,
    WorksiteBoundaryChanged,
    event_bus,
)

__all__ = [
    "AccommodationBoundaryChanged",
    "AppError",
    "Base",
    "Clock",
    "DomainEvent",
    "EmployeeProfileChanged",
    "EventBus",
    "FrozenClock",
    "HolidayChanged",
    "LocationDisabledRecorded",
    "LocationEnabledRecorded",
    "ProblemDetailsException",
    "ScheduledWorkChanged",
    "ScheduledWorkRemoved",
    "Settings",
    "SyncChangesCommitted",
    "SystemClock",
    "TimeRuleChanged",
    "WorksiteBoundaryChanged",
    "async_session_factory",
    "event_bus",
    "get_country_timezone",
    "get_db",
    "get_settings",
    "site_now",
    "site_today",
]
