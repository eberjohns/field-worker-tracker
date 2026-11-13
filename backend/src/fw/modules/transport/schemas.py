from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VehicleBase(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)
    type: str = Field(default="VAN", pattern="^(BUS|VAN|OTHER)$")
    notes: str | None = None


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    type: str | None = Field(default=None, pattern="^(BUS|VAN|OTHER)$")
    notes: str | None = None
    is_active: bool | None = None


class VehicleRead(VehicleBase):
    id: UUID
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DriverRead(BaseModel):
    employee_id: UUID
    tally_id: str
    name: str
    phone: str | None = None
    accommodation_id: UUID | None = None
    accommodation_name: str | None = None
    runs_this_week: int = 0
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class PassengerCreate(BaseModel):
    employee_id: UUID


class PassengerRead(BaseModel):
    id: UUID
    employee_id: UUID
    tally_id: str
    name: str
    phone: str | None = None
    worksite_id: UUID | None = None
    worksite_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class StopCreate(BaseModel):
    sequence: int
    stop_type: str = Field(default="SITE", pattern="^(SITE|ACCOMMODATION)$")
    worksite_id: UUID | None = None
    accommodation_id: UUID | None = None
    planned_time: time | str | None = None
    passengers: list[PassengerCreate] = Field(default_factory=list)


class StopRead(BaseModel):
    id: UUID
    sequence: int
    stop_type: str
    worksite_id: UUID | None = None
    worksite_name: str | None = None
    worksite_address: str | None = None
    accommodation_id: UUID | None = None
    accommodation_name: str | None = None
    planned_time: str | None = None
    passengers: list[PassengerRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class TransportRunCreate(BaseModel):
    run_date: date
    direction: str = Field(default="MORNING", pattern="^(MORNING|EVENING)$")
    driver_id: UUID
    vehicle_id: UUID | None = None
    stops: list[StopCreate] = Field(default_factory=list)


class TransportRunUpdate(BaseModel):
    driver_id: UUID | None = None
    vehicle_id: UUID | None = None
    status: str | None = Field(default=None, pattern="^(DRAFT|PUBLISHED)$")
    needs_update: bool | None = None
    stops: list[StopCreate] | None = None


class TransportRunRead(BaseModel):
    id: UUID
    run_date: date
    direction: str
    driver_id: UUID
    driver_name: str
    driver_phone: str | None = None
    driver_tally_id: str | None = None
    vehicle_id: UUID | None = None
    vehicle_label: str | None = None
    status: str
    needs_update: bool
    version: int
    stops: list[StopRead] = Field(default_factory=list)
    total_passengers: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UnassignedWorkerRead(BaseModel):
    employee_id: UUID
    tally_id: str
    name: str
    phone: str | None = None
    accommodation_id: UUID | None = None
    accommodation_name: str | None = None
    worksite_id: UUID | None = None
    worksite_name: str | None = None
    job_number: str | None = None
    assigned_hours: float | None = None


class SuggestRunsRequest(BaseModel):
    run_date: date
    direction: str = Field(default="MORNING", pattern="^(MORNING|EVENING)$")


class SuggestRunsResponse(BaseModel):
    suggested_runs: list[TransportRunRead] = Field(default_factory=list)
    unassigned_workers: list[UnassignedWorkerRead] = Field(default_factory=list)


class CopyRunsRequest(BaseModel):
    source_date: date
    target_date: date
    direction: str | None = Field(default=None, pattern="^(MORNING|EVENING)$")


class OmittedPassenger(BaseModel):
    employee_id: UUID
    tally_id: str
    name: str
    reason: str


class CopyRunsResponse(BaseModel):
    created_runs: list[TransportRunRead] = Field(default_factory=list)
    omitted_passengers: list[OmittedPassenger] = Field(default_factory=list)


class PublishRunResponse(BaseModel):
    id: UUID
    status: str
    version: int
    synced_recipients_count: int
