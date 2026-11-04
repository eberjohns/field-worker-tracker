"""Pydantic v2 schemas for Worksites, Job Items, and Occurrences."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorksiteBase(BaseModel):
    job_number: str = Field(
        ..., description="Job number matching 2 digits + letter (A/B/C) + 5 digits"
    )
    job_name: str
    renewal_reference: str | None = None
    group_id: UUID
    zone_id: UUID
    customer_type: str | None = None
    is_outdoor: bool | None = None
    country: str = Field(..., max_length=2)
    contract_group_ref: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget_amount: Decimal | None = None


class WorksiteCreate(WorksiteBase):
    pass


class WorksiteUpdate(BaseModel):
    job_name: str | None = None
    renewal_reference: str | None = None
    group_id: UUID | None = None
    zone_id: UUID | None = None
    customer_type: str | None = None
    is_outdoor: bool | None = None
    contract_group_ref: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget_amount: Decimal | None = None
    is_active: bool | None = None
    version: int = Field(..., description="Optimistic locking version")


class WorksiteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_number: str
    job_name: str
    renewal_reference: str | None = None
    group_id: UUID
    group_name: str | None = None
    zone_id: UUID
    zone_name: str | None = None
    customer_type: str | None = None
    is_outdoor: bool
    country: str
    contract_group_ref: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    has_boundary: bool
    rep_latitude: Decimal | None = None
    rep_longitude: Decimal | None = None
    budget_amount: Decimal | None = None
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class JobItemBase(BaseModel):
    sub_item_code: str
    staff_grade_description: str
    planned_grade_code: str
    frequency_unit: str = Field(..., description="WEEK, MONTH, QUARTER, YEAR")
    occurrences_per_period: Decimal
    period_interval: int = 1
    weekday_pattern: list[str] | None = None
    required_staff_count: int = Field(..., ge=1)
    hours_per_occurrence_per_staff: Decimal = Field(..., gt=0)
    declared_activities_per_year: Decimal | None = None
    declared_total_hours_per_year: Decimal | None = None
    start_date: date
    end_date: date | None = None
    deployment_type: str = Field(..., description="PERMANENT or REMOTE")
    break_override_minutes: int | None = None


class JobItemCreate(JobItemBase):
    pass


class JobItemUpdate(BaseModel):
    sub_item_code: str | None = None
    staff_grade_description: str | None = None
    planned_grade_code: str | None = None
    frequency_unit: str | None = None
    occurrences_per_period: Decimal | None = None
    period_interval: int | None = None
    weekday_pattern: list[str] | None = None
    required_staff_count: int | None = None
    hours_per_occurrence_per_staff: Decimal | None = None
    declared_activities_per_year: Decimal | None = None
    declared_total_hours_per_year: Decimal | None = None
    start_date: date | None = None
    end_date: date | None = None
    deployment_type: str | None = None
    break_override_minutes: int | None = None
    is_active: bool | None = None
    version: int = Field(..., description="Optimistic locking version")


class JobOccurrenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_item_id: UUID
    sub_item_code: str | None = None
    staff_grade_description: str | None = None
    planned_grade_code: str | None = None
    window_start: date
    window_end: date
    slot_index: int
    due_date: date | None
    status: str
    source: str
    required_staff_count: int
    required_hours_per_staff: Decimal
    needs_review: bool
    created_at: datetime


class JobOccurrenceUpdate(BaseModel):
    due_date: date | None = None
    status: str | None = None


class JobItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    worksite_id: UUID
    sub_item_code: str
    staff_grade_description: str
    planned_grade_code: str
    frequency_unit: str
    occurrences_per_period: Decimal
    period_interval: int
    weekday_pattern: list[str] | None = None
    required_staff_count: int
    hours_per_occurrence_per_staff: Decimal
    declared_activities_per_year: Decimal | None = None
    declared_total_hours_per_year: Decimal | None = None
    start_date: date
    end_date: date | None = None
    deployment_type: str
    break_override_minutes: int | None = None
    is_active: bool
    version: int
    expected_activities_per_year: Decimal
    expected_annual_hours: Decimal
    days_per_occurrence: int
    job_unit_day_split: list[Decimal]
    created_at: datetime


class WorksiteDetailResponse(WorksiteResponse):
    boundary_geojson: dict[str, Any] | None = None
    items: list[JobItemResponse] = []
    job_items: list[JobItemResponse] = []


class BoundaryUpdateRequest(BaseModel):
    boundary: dict[str, Any] = Field(
        ...,
        description="GeoJSON Polygon geometry (coordinates array: [ [ [lng, lat], ... ] ])",
    )


class BoundaryCopyRequest(BaseModel):
    source_worksite_id: UUID


class BoundaryCopyToRequest(BaseModel):
    target_worksite_ids: list[UUID]


class BoundaryQueueItemResponse(BaseModel):
    id: UUID
    entity_type: str = Field(..., description="WORKSITE or ACCOMMODATION")
    code: str
    name: str
    zone_name: str | None = None
    country: str
    has_boundary: bool
    rep_latitude: Decimal | None = None
    rep_longitude: Decimal | None = None
    boundary_geojson: dict[str, Any] | None = None


class BoundaryQueueResponse(BaseModel):
    total_count: int
    done_count: int
    unset_count: int
    worksites_total_count: int = 0
    worksites_done_count: int = 0
    worksites_unset_count: int = 0
    accommodations_total_count: int = 0
    accommodations_done_count: int = 0
    accommodations_unset_count: int = 0
    items: list[BoundaryQueueItemResponse]


class JobItemValidationResponse(BaseModel):
    job_item_id: UUID
    sub_item_code: str
    staff_grade_description: str
    declared_activities_per_year: Decimal | None
    calculated_activities_per_year: Decimal
    declared_total_hours_per_year: Decimal | None
    calculated_annual_hours: Decimal
    expected_occurrences_count: int
    days_per_occurrence: int
    daily_hours_split: list[Decimal]
    eligible_workers_count: int
    difference_note: str | None


class GenerateOccurrencesRequest(BaseModel):
    from_date: date | None = None
    to_date: date | None = None
