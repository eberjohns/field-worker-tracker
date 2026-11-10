from datetime import date, datetime, time
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AttendanceCalculationSnapshot(BaseModel):
    id: UUID
    version_no: int
    input_hash: str
    calculated_at: datetime
    engine_version: str
    reason: str

    # Planned
    planned_accommodation_departure: time | None = None
    planned_first_site_start: time | None = None
    planned_break_minutes: int
    planned_last_site_end: time | None = None
    planned_accommodation_return: time | None = None
    planned_total_minutes: int
    planned_worked_minutes: int
    standard_hours_minutes: int

    # Actual
    accommodation_departure_at: datetime | None = None
    first_site_entry_at: datetime | None = None
    break_minutes_used: int
    break_source: str
    last_site_exit_at: datetime | None = None
    accommodation_return_at: datetime | None = None

    # Durations & variations
    elapsed_site_minutes: int
    shift_span_minutes: int
    unaccounted_minutes: int
    worked_minutes: int
    required_minutes: int
    variation_minutes: int
    shortfall_minutes: int
    grace_minutes: int
    grace_applied: bool
    satisfied: bool

    # Movement
    productive_minutes: int
    transit_minutes: int
    offsite_minutes: int
    idle_minutes: int

    # Overtime
    ot1_minutes: int
    ot2_minutes: int
    ot_threshold_minutes: int
    day_type: str

    # Counts & status
    assigned_count: int
    completed_count: int
    business_status: str
    flags: list[str] = Field(default_factory=list)
    review_reasons: list[str] = Field(default_factory=list)

    # Snapshots
    visits_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    gaps_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    inputs_snapshot: dict[str, Any] = Field(default_factory=dict)
    source_event_ids: list[UUID] = Field(default_factory=list)


class AttendanceCommentResponse(BaseModel):
    id: UUID
    attendance_id: UUID
    author_user_id: UUID
    author_name: str
    comment_type: str
    comment_text: str
    scheduled_work_id: UUID | None = None
    created_at: datetime


class AttendanceApprovalResponse(BaseModel):
    id: UUID
    attendance_id: UUID
    reviewer_user_id: UUID
    reviewer_name: str
    decision: str
    comment: str | None = None
    calculation_id: UUID
    created_at: datetime


class AttendanceRecordResponse(BaseModel):
    id: UUID
    employee_id: UUID
    employee_name: str
    tally_id: str
    supervisor_name: str | None = None
    work_date: date
    business_status: str
    review_status: str
    locked: bool
    created_at: datetime
    updated_at: datetime
    current_calculation: AttendanceCalculationSnapshot | None = None
    comments: list[AttendanceCommentResponse] = Field(default_factory=list)
    approvals: list[AttendanceApprovalResponse] = Field(default_factory=list)


class AttendanceListResponse(BaseModel):
    items: list[AttendanceRecordResponse]
    total: int


class AttendanceTimelineItem(BaseModel):
    item_id: str
    item_type: str  # SITE_VISIT | ACCOMMODATION_VISIT | TRACKING_GAP | PING_BURST
    label: str
    place_name: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    duration_minutes: int
    is_inferred: bool
    flags: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class AttendanceTimelineResponse(BaseModel):
    attendance_id: UUID
    employee_id: UUID
    employee_name: str
    work_date: date
    timeline_items: list[AttendanceTimelineItem]


class AttendanceCommentCreateRequest(BaseModel):
    comment_type: str
    comment_text: str
    scheduled_work_id: UUID | None = None


class AttendanceDecisionRequest(BaseModel):
    decision: str  # APPROVED | REJECTED
    comment: str | None = None


class AttendanceRecalculateRequest(BaseModel):
    employee_id: UUID | None = None
    from_date: date
    to_date: date
    reason: str = "MANUAL"


class AttendanceRecalculateResponse(BaseModel):
    recalculated_count: int
    message: str


class PendingVisitExplainRequest(BaseModel):
    explanation: str


class PendingVisitRescheduleRequest(BaseModel):
    work_date: date
    employee_ids: list[UUID]


class PendingVisitCloseRequest(BaseModel):
    reason: str


class PendingVisitResponse(BaseModel):
    id: UUID
    scheduled_work_id: UUID
    occurrence_id: UUID | None = None
    worksite_id: UUID
    worksite_name: str
    job_item_id: UUID | None = None
    job_item_name: str | None = None
    employee_id: UUID
    employee_name: str
    tally_id: str | None = None
    supervisor_id: UUID | None = None
    supervisor_name: str | None = None
    due_date: date
    detected_on: date
    age_days: int
    status: str  # OPEN | EXPLAINED | RESCHEDULED | CLOSED
    is_escalated: bool
    explanation_comment_id: UUID | None = None
    latest_explanation: str | None = None
    rescheduled_to_scheduled_work_id: UUID | None = None
    closed_by_user_id: UUID | None = None
    closed_by_name: str | None = None
    closed_reason: str | None = None
    closed_at: datetime | None = None
    created_at: datetime


class PendingVisitListResponse(BaseModel):
    items: list[PendingVisitResponse]
    open_count: int
    explained_count: int
    rescheduled_count: int
    closed_count: int
    escalated_count: int
    total_count: int

