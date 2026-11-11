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


class MobileEventResponse(BaseModel):
    event_id: UUID
    employee_id: UUID
    device_id: UUID
    event_type: str
    event_timestamp_utc: datetime
    location_captured_at_utc: datetime | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    accuracy_meters: float | None = None
    is_mock_location: bool | None = None
    sequence_number: int | None = None
    server_received_at: datetime
    processing_status: str
    server_site_id: UUID | None = None
    server_accommodation_id: UUID | None = None
    server_verdict: str | None = None
    distance_to_polygon_m: float | None = None
    flags: list[str] = Field(default_factory=list)


class StreamTicketResponse(BaseModel):
    ticket: str
    expires_in_seconds: int = 30


class LivePositionItem(BaseModel):
    employee_id: UUID
    tally_id: str | None = None
    name: str
    role: str | None = None
    supervisor_id: UUID | None = None
    supervisor_name: str | None = None
    group_id: UUID | None = None
    group_name: str | None = None
    zone_id: UUID | None = None
    zone_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    accuracy_meters: float | None = None
    event_type: str
    event_timestamp_utc: datetime
    received_at_utc: datetime
    last_contact_at: datetime
    age_seconds: int
    contact_age_seconds: int
    tracking_enabled: bool = True
    server_verdict: str | None = None
    server_site_id: UUID | None = None
    server_site_name: str | None = None
    live_state: str  # ACTIVE | NO_RECENT_SIGNAL | LOCATION_DISABLED | NOT_SCHEDULED
    has_schedule_today: bool = False
    today_assignments: list[dict] = Field(default_factory=list)


class LivePositionsResponse(BaseModel):
    items: list[LivePositionItem]
    active_count: int
    offline_count: int
    disabled_count: int
    not_scheduled_count: int
    total_count: int
    as_of: datetime
