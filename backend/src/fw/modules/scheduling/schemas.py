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
    standard_hours: Decimal
    effective_daily_standard_hours: Decimal
    days: list[RosterDayCell]  # 7 days Mon-Sun
    week_allocated_hours: Decimal
    week_standard_hours: Decimal
    week_is_over: bool
    week_is_under: bool
    remarks: str | None = None


class RosterResponse(BaseModel):
    week_start: date
    week_end: date
    total_workers: int
    workers: list[RosterWorkerRow]


# --- Coverage Schemas ---


class CoverageDayCell(BaseModel):
    work_date: date
    weekday: str
    required_staff_count: int
    assigned_staff_count: int
    is_to_be_covered: bool
    assigned_workers: list[str]


class CoverageItemRow(BaseModel):
    job_item_id: UUID
    sub_item_code: str
    staff_grade_description: str
    planned_grade_code: str
    deployment_type: str
    required_staff_count: int
    hours_per_occurrence: Decimal
    days: list[CoverageDayCell]


class CoverageWorksiteRow(BaseModel):
    worksite_id: UUID
    job_number: str
    job_name: str
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
    standard_hours: Decimal
    exact_staff_type_match: bool
    ranking_score: float
    reasons: list[str]
    warnings: list[str]
    today_allocated_hours: Decimal
    weekly_allocated_hours: Decimal
    monthly_allocated_hours: Decimal

