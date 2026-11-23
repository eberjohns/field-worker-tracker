"""Pydantic v2 schemas for Worksites, Job Items, and Occurrences."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# --- Job budget and man-hours (DEC-59, ADR-029) ---------------------------------------------
# Filled in by the budget module. Money fields are Admin only (DEC-47): null for other roles.


class BudgetWarning(BaseModel):
    """MISSING_GRADE_RATE, PROVISIONS_DIFFER_FROM_PAYROLL or SETTING_MISSING."""

    code: str
    job_item_id: UUID | None = None
    sub_item_code: str | None = None
    grade_code: str | None = None
    annual_hours: Decimal = Decimal("0.0")
    message: str
    plan_provisions: Decimal | None = None
    payroll_provisions: Decimal | None = None


class JobItemBudget(BaseModel):
    """Planned man-hours and cost of one job item for a period (default: current contract year)."""

    period_from: date
    period_to: date
    activities_per_year: Decimal
    full_year_hours: Decimal
    active_days: int
    annual_hours: Decimal
    hourly_rate: Decimal | None = None
    annual_cost: Decimal | None = None
    is_budget_only: bool = False
    revision_code: str | None = None
    warnings: list[BudgetWarning] = Field(default_factory=list)


class WorksiteBudgetTotals(BaseModel):
    period_from: date
    period_to: date
    revision_code: str | None = None
    total_hours: Decimal
    missing_rate_hours: Decimal = Decimal("0.0")
    total_cost: Decimal | None = None
    warnings: list[BudgetWarning] = Field(default_factory=list)


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
    salary_revision_code: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget_amount: Decimal | None = None


class WorksiteUpdate(BaseModel):
    job_name: str | None = None
    renewal_reference: str | None = None
    group_id: UUID | None = None
    zone_id: UUID | None = None
    customer_type: str | None = None
    is_outdoor: bool | None = None
    contract_group_ref: str | None = None
    salary_revision_code: str | None = None
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
    salary_revision_code: str | None = None
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


MAX_WIZARD_JOB_ITEMS = 50


class WorksiteCreate(WorksiteBase):
    """A worksite, optionally with its job items and supervisors (Batch 5.1 B wizard).

    Everything is created in one transaction: if any item or supervisor fails, nothing is saved.
    """

    job_items: list[JobItemCreate] = Field(default_factory=list, max_length=MAX_WIZARD_JOB_ITEMS)
    supervisor_ids: list[UUID] = Field(default_factory=list)


class JobNumberCheck(BaseModel):
    """Live check of a job number for the Add Worksite wizard (format and uniqueness)."""

    job_number: str
    valid: bool
    exists: bool = False
    message: str | None = None
    is_outdoor: bool | None = None
    kind: str | None = None


class JobItemChecksRequest(BaseModel):
    """Checks for a job item that is not saved yet (Add Worksite wizard rows)."""

    country: str = Field(..., pattern="^(AE|SA)$")
    item: JobItemCreate


class JobItemChecks(BaseModel):
    """The job item validation panel for an unsaved item (BR-JB-06, BR-JB-12)."""

    calculated_activities_per_year: Decimal
    calculated_annual_hours: Decimal
    expected_occurrences_count: int
    days_per_occurrence: int
    daily_hours_split: list[Decimal]
    eligible_workers_count: int


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
    budget: JobItemBudget | None = None


class WorksiteSupervisorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    worksite_id: UUID
    supervisor_id: UUID
    supervisor_name: str | None = None
    supervisor_tally_id: str | None = None
    is_active: bool
    created_at: datetime


class WorksiteSupervisorAssign(BaseModel):
    supervisor_id: UUID


class SupervisorProposal(BaseModel):
    """A supervisor whose crew works on a worksite but who is not assigned to it yet."""

    supervisor_id: UUID
    supervisor_name: str
    supervisor_tally_id: str
    crew_members_on_site: int = Field(
        ..., description="Crew members with active standing assignments here"
    )


class WorksiteSupervisorProposal(BaseModel):
    worksite_id: UUID
    job_number: str
    job_name: str
    assigned_supervisor_ids: list[UUID] = []
    proposals: list[SupervisorProposal] = []


class WorksiteSupervisorPair(BaseModel):
    worksite_id: UUID
    supervisor_id: UUID


class WorksiteSupervisorBulkAssign(BaseModel):
    assignments: list[WorksiteSupervisorPair] = Field(..., min_length=1, max_length=2000)


class WorksiteSupervisorBulkAssignResult(BaseModel):
    assigned: int
    already_assigned: int


class JobItemDestination(BaseModel):
    """Reassignment destination: names and codes only, no budget or cost figures."""

    job_item_id: UUID
    worksite_id: UUID
    job_number: str
    job_name: str
    country: str
    sub_item_code: str
    staff_grade_description: str
    deployment_type: str


class WorksiteDetailResponse(WorksiteResponse):
    boundary_geojson: dict[str, Any] | None = None
    items: list[JobItemResponse] = []
    job_items: list[JobItemResponse] = []
    supervisors: list[WorksiteSupervisorRead] = []
    budget_totals: WorksiteBudgetTotals | None = None


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


class BoundaryImportItem(BaseModel):
    entity_type: str = Field(..., description="WORKSITE or ACCOMMODATION")
    code: str = Field(..., description="Worksite job number or accommodation code")
    polygon: Any = Field(..., description="GeoJSON dict/string or WKT string")


class BoundaryImportRequest(BaseModel):
    items: list[BoundaryImportItem]


class BoundaryImportError(BaseModel):
    row: int
    code: str
    entity_type: str
    reason: str


class BoundaryImportResponse(BaseModel):
    total_rows: int
    updated_count: int
    skipped_count: int
    errors: list[BoundaryImportError]


class BoundaryExportItem(BaseModel):
    entity_type: str
    code: str
    name: str
    has_boundary: bool
    format: str
    polygon: str | None = None


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
