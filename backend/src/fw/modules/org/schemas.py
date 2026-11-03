from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GroupCreate(BaseModel):
    code: str
    name: str


class GroupUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    version: int


class GroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    is_active: bool
    version: int


class ZoneCreate(BaseModel):
    code: str
    name: str


class ZoneUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    version: int


class ZoneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    is_active: bool
    version: int


class AccommodationCreate(BaseModel):
    accommodation_code: str
    name: str
    address: str | None = None
    rep_latitude: Decimal | None = None
    rep_longitude: Decimal | None = None


class AccommodationUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    rep_latitude: Decimal | None = None
    rep_longitude: Decimal | None = None
    is_active: bool | None = None
    version: int


class AccommodationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    accommodation_code: str
    name: str
    address: str | None = None
    rep_latitude: Decimal | None = None
    rep_longitude: Decimal | None = None
    is_active: bool
    version: int


class EmployeeCreate(BaseModel):
    tally_id: str
    name: str
    phone: str | None = None
    email: str | None = None
    role: str
    grade_code: str | None = None
    staff_grade_description: str | None = None
    accommodation_id: UUID | None = None
    weekly_off_day: str | None = None
    is_driver: bool = False
    country: str = "AE"
    break_override_minutes: int | None = None
    join_date: date | None = None
    employment_end_date: date | None = None


class EmployeeUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    role: str | None = None
    grade_code: str | None = None
    staff_grade_description: str | None = None
    accommodation_id: UUID | None = None
    weekly_off_day: str | None = None
    is_driver: bool | None = None
    country: str | None = None
    break_override_minutes: int | None = None
    join_date: date | None = None
    employment_end_date: date | None = None
    is_active: bool | None = None
    version: int


class EmployeeBulkUpdateItem(BaseModel):
    accommodation_id: UUID | None = None
    break_override_minutes: int | None = None
    weekly_off_day: str | None = None


class EmployeeBulkUpdateRequest(BaseModel):
    employee_ids: list[UUID]
    changes: EmployeeBulkUpdateItem


class EmployeeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tally_id: str
    name: str
    phone: str | None = None
    email: str | None = None
    role: str
    grade_code: str | None = None
    staff_grade_description: str | None = None
    accommodation_id: UUID | None = None
    weekly_off_day: str | None = None
    is_driver: bool
    country: str
    break_override_minutes: int | None = None
    join_date: date | None = None
    employment_end_date: date | None = None
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class ReportingLineCreate(BaseModel):
    manager_id: UUID
    relationship: str = Field(..., description="SUPERVISOR, SUPERINTENDENT, or ENGINEER")
    notes: str | None = None


class ReportingLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    manager_id: UUID
    relationship: str
    notes: str | None = None
    created_at: datetime


class GradeChangeRequest(BaseModel):
    new_grade_code: str
    effective_from: date
    reason: str


class GradeHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    old_grade_code: str | None = None
    new_grade_code: str
    effective_from: date
    changed_by_user_id: UUID
    reason: str
    created_at: datetime


class EmployeeDocumentCreate(BaseModel):
    document_type: str
    expiry_date: date
    start_date: date | None = None


class EmployeeDocumentUpdate(BaseModel):
    expiry_date: date | None = None
    start_date: date | None = None
    is_active: bool | None = None


class EmployeeDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    document_type: str
    expiry_date: date
    start_date: date | None = None
    is_active: bool


class RegisteredDeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    device_identifier: str
    platform: str
    device_model: str | None = None
    app_version: str | None = None
    os_version: str | None = None
    push_token: str | None = None
    registered_at: datetime
    last_seen_at: datetime | None = None
    last_acked_cursor: int
    location_permission_state: str | None = None
    revoked_at: datetime | None = None
    is_active: bool


class HierarchyTreeNode(BaseModel):
    employee: EmployeeRead
    relationship: str | None = None
    subordinates: list[Any] = Field(default_factory=list)

