from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PlatformEnum(StrEnum):
    ANDROID = "ANDROID"
    IOS = "IOS"


class LocationPermissionState(StrEnum):
    ALWAYS = "ALWAYS"
    WHILE_IN_USE = "WHILE_IN_USE"
    DENIED = "DENIED"
    RESTRICTED = "RESTRICTED"


class MobileDeviceRegistration(BaseModel):
    model_config = ConfigDict(extra="ignore")

    device_identifier: str
    platform: PlatformEnum
    device_model: str | None = None
    app_version: str | None = None
    os_version: str | None = None
    push_token: str | None = None


class MobileLoginRequest(BaseModel):
    tally_id: str
    password: str
    device: MobileDeviceRegistration


class MobileEmployeeInfo(BaseModel):
    employee_id: UUID
    tally_id: str
    name: str
    role: str


class MobileLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int = 900
    server_time_utc: datetime
    must_change_password: bool
    employee: MobileEmployeeInfo


class MobileChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class MobileRefreshRequest(BaseModel):
    refresh_token: str


class MobileDeviceUpdateRequest(BaseModel):
    push_token: str | None = None
    app_version: str | None = None
    os_version: str | None = None
    location_permission_state: LocationPermissionState | None = None


class MobileConsentRequest(BaseModel):
    policy_version: int
    consented_at_utc: datetime


class MobilePolicyResponse(BaseModel):
    version: int
    language: str
    title: str
    body: str
    published_at: datetime


class MobileHeartbeatRequest(BaseModel):
    app_version: str
    cursor: int
    location_permission_state: LocationPermissionState | None = None


class MobileHeartbeatResponse(BaseModel):
    server_time_utc: datetime
    latest_cursor: int
    min_app_version: str = "1.0.0"
    has_pending_changes: bool


# Sync Entities
class ProfileSupervisor(BaseModel):
    name: str | None = None
    phone: str | None = None


class ProfilePayload(BaseModel):
    employee_id: UUID
    tally_id: str
    name: str
    role: str
    staff_grade_description: str | None = None
    weekly_off_day: str | None = None
    is_driver: bool = False
    supervisor: ProfileSupervisor | None = None
    accommodation_id: UUID | None = None


class SettingsPayload(BaseModel):
    geofence_circle_radius_m: int = 300
    approach_polling_interval_s: int = 60
    confirmation_polling_interval_s: int = 300
    schedule_sync_window_days: int = 30
    location_policy_version: int = 1
    alarm_lead_minutes: int = 30
    timezone: str = "Asia/Dubai"
    upcoming: list[dict[str, Any]] = Field(default_factory=list)


class DayPlanPlannedTimes(BaseModel):
    accommodation_start: str
    first_site_start: str
    break_minutes: int
    last_site_end: str
    accommodation_end: str


class DayPlanPayload(BaseModel):
    work_date: str
    status: str  # WORKING, OFF, SKIPPED, LEAVE, FREE
    marker: str | None = None  # WEEKLY_OFF, PUBLIC_HOLIDAY
    planned: DayPlanPlannedTimes | None = None
    standard_hours: int = 8
    alarm_time: str | None = None


class GeofenceCircle(BaseModel):
    center: dict[str, float]  # {"lat": float, "lng": float}
    radius_m: float


class AccommodationPayload(BaseModel):
    accommodation_id: UUID
    name: str
    address: str | None = None
    boundary: dict[str, Any] | None = None
    geofence_circle: GeofenceCircle | None = None


class JobPayload(BaseModel):
    job_id: UUID
    job_number: str
    job_name: str
    boundary: dict[str, Any] | None = None
    geofence_circle: GeofenceCircle | None = None
    boundary_missing: bool = False


class JobItemSummary(BaseModel):
    staff_grade_description: str | None = None
    deployment_type: str = "PERMANENT"
    required_staff_count: int = 1
    hours_per_occurrence_per_staff: float = 9.0


class ScheduleItemPayload(BaseModel):
    scheduled_work_id: UUID
    work_date: str
    sequence: int
    assigned_hours: float
    status: str
    job_id: UUID
    job_item_id: UUID
    sub_item_code: str | None = None
    occurrence_id: UUID | None = None
    job_item_summary: JobItemSummary | None = None
    source: str = "PLANNED"
    is_reassignment: bool = False


class TransportPassengerSyncPayload(BaseModel):
    name: str
    tally_id: str


class TransportDriverSyncPayload(BaseModel):
    name: str
    phone: str | None = None


class TransportStopSyncPayload(BaseModel):
    sequence: int
    stop_type: str
    job_id: UUID | None = None
    accommodation_id: UUID | None = None
    name: str
    planned_time: str | None = None
    passengers: list[TransportPassengerSyncPayload] = Field(default_factory=list)


class TransportRunPayload(BaseModel):
    run_id: UUID
    run_date: str
    direction: str
    vehicle_label: str | None = None
    driver: TransportDriverSyncPayload
    stops: list[TransportStopSyncPayload] = Field(default_factory=list)


class SnapshotEntity(BaseModel):
    entity_type: str
    entity_id: str
    entity_version: int
    payload: dict[str, Any] | None = None


class SyncSnapshotResponse(BaseModel):
    cursor: int
    generated_at: datetime
    server_time_utc: datetime
    window: dict[str, str]
    entities: list[SnapshotEntity]


class SyncChangeItem(BaseModel):
    cursor: int
    entity_type: str
    entity_id: str
    entity_version: int
    op: str
    priority: int
    payload: dict[str, Any] | None = None


class SyncChangesResponse(BaseModel):
    from_cursor: int
    next_cursor: int
    has_more: bool
    resync_required: bool
    server_time_utc: datetime
    changes: list[SyncChangeItem]


class SyncAckRequest(BaseModel):
    cursor: int


class SyncAckResponse(BaseModel):
    status: str = "ACKNOWLEDGED"
    last_acked_cursor: int
    server_time_utc: datetime


class DeviceStatusRead(BaseModel):
    device_id: UUID
    employee_id: UUID
    tally_id: str
    employee_name: str
    platform: str
    device_model: str | None = None
    app_version: str | None = None
    os_version: str | None = None
    last_seen_at: datetime | None = None
    last_acked_cursor: int
    current_cursor: int
    sync_lag: int
    location_permission_state: str | None = None
    is_active: bool
    revoked_at: datetime | None = None
