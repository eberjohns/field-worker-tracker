from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class EventType(StrEnum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    PING = "PING"
    LOCATION_DISABLED = "LOCATION_DISABLED"
    LOCATION_ENABLED = "LOCATION_ENABLED"


class EventStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    REJECTED = "REJECTED"


class RejectReason(StrEnum):
    INVALID_SCHEMA = "INVALID_SCHEMA"
    INVALID_COORDINATES = "INVALID_COORDINATES"
    TIMESTAMP_IN_FUTURE = "TIMESTAMP_IN_FUTURE"
    TIMESTAMP_TOO_OLD = "TIMESTAMP_TOO_OLD"


class MobileEventItem(BaseModel):
    event_id: UUID
    event_type: EventType
    event_timestamp_utc: datetime
    location_captured_at_utc: datetime | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    accuracy_meters: float | None = None
    is_mock_location: bool | None = None
    sequence_number: int | None = None
    job_id: UUID | None = None
    job_item_id: UUID | None = None
    accommodation_id: UUID | None = None


class EventBatchRequest(BaseModel):
    batch_id: UUID
    device_clock_utc: datetime
    events: list[MobileEventItem] = Field(..., max_length=200)


class EventResultItem(BaseModel):
    event_id: UUID
    status: EventStatus
    reason: RejectReason | None = None


class EventBatchResponse(BaseModel):
    batch_id: UUID
    server_time_utc: datetime
    latest_cursor: int
    results: list[EventResultItem]
