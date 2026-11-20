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
    has_boundary: bool = False
    boundary_geojson: dict[str, Any] | None = None
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
    confirm_reuse: bool = False


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
    effective_from: date | None = None
    join_date: date | None = None
    employment_end_date: date | None = None
    is_active: bool | None = None
    version: int


class EmployeeBulkUpdateItem(BaseModel):
    accommodation_id: UUID | None = None
    break_override_minutes: int | None = None
    effective_from: date | None = None
    weekly_off_day: str | None = None


class EmployeeBulkUpdateRequest(BaseModel):
    employee_ids: list[UUID]
    changes: EmployeeBulkUpdateItem
    effective_from: date | None = None


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
    read_only: bool = Field(
        False,
        description="True when the caller sees this employee only through a worksite (DEC-57): view and comment only",
    )


class ReportingLineCreate(BaseModel):
    manager_id: UUID
    relationship: str = Field(..., description="SUPERVISOR, SUPERINTENDENT, or ENGINEER")
    notes: str | None = None


class ReportingLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    manager_id: UUID
    manager_name: str | None = None
    manager_tally_id: str | None = None
    relationship: str
    notes: str | None = None
    created_at: datetime
    is_active: bool = True
    is_direct: bool = True
    via_name: str | None = None


class HierarchyViolationItem(BaseModel):
    reporting_line_id: UUID
    employee_id: UUID
    employee_tally_id: str
    employee_name: str
    employee_role: str
    manager_id: UUID
    manager_tally_id: str
    manager_name: str
    manager_role: str
    relationship: str
    violation_code: str
    violation_message: str
    supervisor_id: UUID | None = None
    supervisor_tally_id: str | None = None
    supervisor_name: str | None = None
    supervisor_already_has_manager: bool = False
    can_move_to_supervisor: bool = False


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


class ExpiringDocumentItem(BaseModel):
    document_id: UUID
    employee_id: UUID
    employee_name: str
    tally_id: str | None = None
    supervisor_id: UUID | None = None
    supervisor_name: str | None = None
    document_type: str
    expiry_date: date
    days_remaining: int
    status: str  # OK | EXPIRING | EXPIRED
    is_active: bool = True


class ExpiringDocumentsResponse(BaseModel):
    items: list[ExpiringDocumentItem]
    expiring_count: int
    expired_count: int
    ok_count: int
    total_count: int


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


class TallyIdPreviousUse(BaseModel):
    employee_id: str
    employee_name: str | None = None
    new_tally_id: str | None = None
    changed_at: datetime | None = None


class TallyIdCheckResponse(BaseModel):
    tally_id: str
    available: bool
    in_use_by_employee_id: UUID | None = None
    in_use_by_name: str | None = None
    previously_used: bool = False
    previous_uses: list[TallyIdPreviousUse] = Field(default_factory=list)


class TallyIdChangeRequest(BaseModel):
    new_tally_id: str
    reason: str
    confirm_reuse: bool = False


class DeactivateRequest(BaseModel):
    confirmation_text: str
    admin_password: str
    effective_date: date | None = None
    reason: str


class ReactivateRequest(BaseModel):
    confirmation_text: str
    admin_password: str
    reason: str
    reactivate_items: bool = True


class EmployeeDeactivationImpactResponse(BaseModel):
    employee_id: UUID
    employee_name: str
    tally_id: str
    role: str
    effective_date: date
    future_active_shifts: int
    base_roster_slots: int
    active_standing_assignments: int
    pending_leave_requests: int
    pending_reassignment_requests: int
    active_direct_reports: int


class EntityLifecycleResponse(BaseModel):
    status: str
    entity_id: UUID
    is_active: bool
    effective_date: date | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    message: str


class EmployeeAttributeHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    attribute_name: str
    old_value: str | None = None
    new_value: str | None = None
    effective_from: date
    changed_by_user_id: UUID
    reason: str
    created_at: datetime


class EmployeeProfileDetailsUpdate(BaseModel):
    staff_grade_description: str | None = None
    grade_code: str | None = None
    is_driver: bool | None = None
    effective_from: date | None = None
    reason: str
