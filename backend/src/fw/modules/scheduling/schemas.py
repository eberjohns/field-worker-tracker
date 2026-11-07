"""Pydantic v2 schemas for the Scheduling module."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StandingAssignmentCreate(BaseModel):
    employee_id: UUID
    job_item_id: UUID
    start_date: date
    end_date: date | None = None
    weekday_pattern: list[str] | None = None
    hours_per_day: Decimal | None = Field(default=None, ge=Decimal("0.5"), le=Decimal("24.0"))


class StandingAssignmentUpdate(BaseModel):
    end_date: date | None = None
    weekday_pattern: list[str] | None = None
    hours_per_day: Decimal | None = Field(default=None, ge=Decimal("0.5"), le=Decimal("24.0"))
    is_active: bool | None = None
    version: int


class StandingAssignmentEndRequest(BaseModel):
    end_date: date
    version: int


class StandingAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    employee_name: str | None = None
    job_item_id: UUID
    job_number: str | None = None
    sub_item_code: str | None = None
    start_date: date
    end_date: date | None = None
    weekday_pattern: list[str] | None = None
    hours_per_day: Decimal | None = None
    is_active: bool
    version: int
    created_at: datetime


class ScheduledWorkCreate(BaseModel):
    employee_id: UUID
    job_item_id: UUID
    work_date: date
    occurrence_id: UUID | None = None
    assigned_hours: Decimal = Field(gt=Decimal("0.0"), le=Decimal("24.0"))
    sequence: int | None = Field(default=None, ge=1)
    source: str = "DIRECT"
    acknowledge_warnings: bool = False


class ScheduledWorkBatchCreate(BaseModel):
    employee_ids: list[UUID]
    job_item_id: UUID
    work_date: date
    occurrence_id: UUID | None = None
    assigned_hours: Decimal | None = None
    as_standing_assignment: bool = False
    acknowledge_warnings: bool = False


class ScheduledWorkUpdate(BaseModel):
    assigned_hours: Decimal | None = Field(default=None, gt=Decimal("0.0"), le=Decimal("24.0"))
    sequence: int | None = Field(default=None, ge=1)
    status: str | None = None
    version: int
    acknowledge_warnings: bool = False


class ScheduledWorkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    employee_name: str | None = None
    work_date: date
    occurrence_id: UUID | None = None
    job_item_id: UUID
    worksite_id: UUID
    job_number: str | None = None
    sub_item_code: str | None = None
    assigned_hours: Decimal
    sequence: int
    status: str
    source: str
    version: int
    created_at: datetime


class ScheduledWorkReorderRequest(BaseModel):
    employee_id: UUID
    work_date: date
    ordered_ids: list[UUID]


class ScheduledWorkValidateRequest(BaseModel):
    employee_id: UUID
    job_item_id: UUID
    work_date: date
    assigned_hours: Decimal = Field(gt=Decimal("0.0"), le=Decimal("24.0"))
    sequence: int | None = Field(default=None, ge=1)
    occurrence_id: UUID | None = None
    exclude_scheduled_work_id: UUID | None = None


class ValidationIssueRead(BaseModel):
    code: str
    severity: str
    message: str


class ValidationReportRead(BaseModel):
    is_valid: bool
    issues: list[ValidationIssueRead]
    errors: list[ValidationIssueRead]
    warnings: list[ValidationIssueRead]
    infos: list[ValidationIssueRead]


# --- Roster Schemas ---


class RosterSiteChip(BaseModel):
    scheduled_work_id: UUID
    worksite_id: UUID
    job_number: str
    job_name: str
    job_item_id: UUID
    sub_item_code: str
    deployment_type: str
    assigned_hours: Decimal
    sequence: int
    has_boundary: bool


class RosterDayCell(BaseModel):
    work_date: date
    weekday: str
    chips: list[RosterSiteChip]
    marker: str | None = None  # SKIPPED, WEEKLY_OFF, ON_LEAVE, TO_BE_COVERED, FREE
    day_total_hours: Decimal
    is_over_standard: bool
    is_under_standard: bool


class RosterWorkerRow(BaseModel):
    employee_id: UUID
    name: str
    tally_id: str
    grade_code: str | None = None
    staff_grade_description: str | None = None
    weekly_off_day: str | None = None
    standard_hours: Decimal
    effective_daily_standard_hours: Decimal
    days: list[RosterDayCell]  # 7 days Mon-Sun
    week_allocated_hours: Decimal
    week_standard_hours: Decimal
    week_is_over: bool
    week_is_under: bool
    supervisor_id: UUID | None = None
    supervisor_name: str | None = None
    remarks: str | None = None


class RosterResponse(BaseModel):
    week_start: date
    week_end: date
    total_workers: int
    workers: list[RosterWorkerRow]


# --- Coverage Schemas ---


class AssignedWorkerSummary(BaseModel):
    employee_id: UUID
    name: str
    tally_id: str
    scheduled_work_id: UUID
    source: str = "DIRECT"
    standing_assignment_id: UUID | None = None
    standing_assignment_version: int | None = None


class CoverageDayCell(BaseModel):
    work_date: date
    weekday: str
    required_staff_count: int
    assigned_staff_count: int
    is_to_be_covered: bool
    is_excess: bool = False
    is_quota_met: bool = False
    is_holiday: bool = False
    holiday_name: str | None = None
    assigned_workers: list[str]
    assigned_details: list[AssignedWorkerSummary] = Field(default_factory=list)


class CoverageItemRow(BaseModel):
    job_item_id: UUID
    sub_item_code: str
    staff_grade_description: str
    planned_grade_code: str
    deployment_type: str
    required_staff_count: int
    hours_per_occurrence: Decimal
    frequency_unit: str = "WEEK"
    occurrences_per_period: Decimal = Decimal("6.0")
    days: list[CoverageDayCell]


class CoverageWorksiteRow(BaseModel):
    worksite_id: UUID
    job_number: str
    job_name: str
    customer_type: str | None = None
    is_outdoor: bool = True
    items: list[CoverageItemRow]


class CoverageResponse(BaseModel):
    week_start: date
    week_end: date
    worksites: list[CoverageWorksiteRow]


# --- Worker Allocation Schemas ---


class WorkerAllocationResponse(BaseModel):
    employee_id: UUID
    employee_name: str
    base_standard_hours: Decimal
    effective_daily_standard_hours: Decimal
    today_allocated_hours: Decimal
    today_standard_hours: Decimal
    today_diff: Decimal
    today_is_over: bool
    today_is_under: bool
    week_allocated_hours: Decimal
    week_standard_hours: Decimal
    week_diff: Decimal
    week_is_over: bool
    week_is_under: bool
    month_allocated_hours: Decimal
    month_standard_hours: Decimal
    month_diff: Decimal
    month_is_over: bool
    month_is_under: bool


# --- Candidate Suggestions ---


class CandidateRecommendationRead(BaseModel):
    employee_id: UUID
    name: str
    tally_id: str
    grade_code: str | None = None
    staff_grade_description: str | None = None
    weekly_off_day: str | None = None
    standard_hours: Decimal
    exact_staff_type_match: bool
    ranking_score: float
    reasons: list[str]
    warnings: list[str]
    today_allocated_hours: Decimal
    weekly_allocated_hours: Decimal
    monthly_allocated_hours: Decimal
    supervisor_id: UUID | None = None
    supervisor_name: str | None = None
    shares_site_group: bool = False
    is_blocked: bool = False
    blocked_reason: str | None = None


# --- Base Planner Schemas ---


class BaseRosterEntryCreate(BaseModel):
    employee_id: UUID
    weekday_mask: str = "ALL"  # "ALL" or "MON".."SUN"
    assigned_hours: Decimal = Field(gt=Decimal("0.0"), le=Decimal("24.0"))
    sequence: int = Field(default=1, ge=1)


class BaseRosterEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    template_id: UUID
    employee_id: UUID
    employee_name: str | None = None
    tally_id: str | None = None
    weekly_off_day: str | None = None
    weekday_mask: str
    assigned_hours: Decimal
    sequence: int


class BaseRosterTemplateCreate(BaseModel):
    job_item_id: UUID
    allocation_mode: str = "UNIFORM"  # "UNIFORM" | "DAY_OF_WEEK"
    start_date: date
    end_date: date | None = None
    entries: list[BaseRosterEntryCreate]


class BaseRosterTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_item_id: UUID
    allocation_mode: str
    start_date: date
    end_date: date | None = None
    is_active: bool
    version: int
    entries: list[BaseRosterEntryRead] = Field(default_factory=list)


class BasePlannerItemRow(BaseModel):
    job_item_id: UUID
    sub_item_code: str
    staff_grade_description: str
    planned_grade_code: str
    deployment_type: str
    required_staff_count: int
    hours_per_occurrence: Decimal
    frequency_unit: str
    occurrences_per_period: Decimal
    weekday_pattern: list[str] | None = None
    start_date: date | None = None
    end_date: date | None = None
    template: BaseRosterTemplateRead | None = None


class BasePlannerWorksiteRow(BaseModel):
    worksite_id: UUID
    job_number: str
    job_name: str
    customer_type: str | None = None
    is_outdoor: bool = True
    start_date: date | None = None
    end_date: date | None = None
    budget_amount: Decimal | None = None
    items: list[BasePlannerItemRow]


class BasePlannerResponse(BaseModel):
    worksites: list[BasePlannerWorksiteRow]


# --- Operational Planner Schemas ---


class OperationalShiftCreate(BaseModel):
    job_item_id: UUID
    work_date: date
    employee_id: UUID
    original_employee_id: UUID | None = None
    assigned_hours: Decimal | None = None
    override_reason: str | None = None
    source: str = "DIRECT"  # "DIRECT" | "OVERRIDE"
    status: str = "ACTIVE"  # "ACTIVE" | "CANCELLED"
    acknowledge_warnings: bool = False


class OperationalCellWorker(BaseModel):
    employee_id: UUID
    employee_name: str
    tally_id: str | None = None
    assigned_hours: Decimal
    display_type: str  # "BLUEPRINT" | "OVERRIDE" | "DIRECT" | "TO_BE_COVERED" | "REMOVED"
    opacity_class: str  # "muted" | "solid" | "warning" | "removed"
    original_employee_id: UUID | None = None
    original_employee_name: str | None = None
    shift_id: UUID | None = None
    reason: str | None = None
    is_public_holiday: bool = False
    is_rest_day: bool = False
    tags: list[str] = Field(default_factory=list)


class OperationalDayCell(BaseModel):
    work_date: date
    weekday: str
    required_staff_count: int
    assigned_staff_count: int
    is_public_holiday: bool = False
    holiday_name: str | None = None
    is_recommended_target: bool = False
    is_quota_met: bool = False
    is_excess: bool = False
    is_to_be_covered: bool = False
    workers: list[OperationalCellWorker] = Field(default_factory=list)


class OperationalJobItemRow(BaseModel):
    job_item_id: UUID
    sub_item_code: str
    staff_grade_description: str
    planned_grade_code: str
    deployment_type: str
    required_staff_count: int
    hours_per_occurrence: Decimal
    frequency_unit: str
    occurrences_per_period: Decimal
    quota_target: int
    quota_assigned: int
    quota_satisfied: bool
    days: list[OperationalDayCell]


class OperationalWorksiteRow(BaseModel):
    worksite_id: UUID
    job_number: str
    job_name: str
    customer_type: str | None = None
    is_outdoor: bool = True
    start_date: date | None = None
    end_date: date | None = None
    budget_amount: Decimal | None = None
    items: list[OperationalJobItemRow]


class OperationalCoverageResponse(BaseModel):
    week_start: date
    week_end: date
    worksites: list[OperationalWorksiteRow]


class OperationalRosterDayCell(BaseModel):
    work_date: date
    weekday: str
    is_working_day: bool = True
    is_weekly_off: bool = False
    is_public_holiday: bool = False
    holiday_name: str | None = None
    leave_type: str | None = None
    allocated_hours: Decimal = Decimal("0.0")
    shifts: list[OperationalCellWorker] = Field(default_factory=list)


class OperationalRosterWorkerRow(BaseModel):
    employee_id: UUID
    tally_id: str
    name: str
    staff_grade_description: str | None = None
    weekly_off_day: str | None = None
    supervisor_id: UUID | None = None
    supervisor_name: str | None = None
    assigned_job_numbers: list[str] = Field(default_factory=list)
    total_week_hours: Decimal
    standard_week_hours: Decimal
    days: list[OperationalRosterDayCell]


class OperationalRosterResponse(BaseModel):
    week_start: date
    week_end: date
    workers: list[OperationalRosterWorkerRow]


