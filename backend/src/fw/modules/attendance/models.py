from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fw.core.db import Base


class SiteVisit(Base):
    """Derived visit records at worksites or accommodations."""

    __tablename__ = "site_visits"
    __table_args__ = (
        Index("ix_site_visits_employee_date", "employee_id", "work_date"),
        Index("ix_site_visits_worksite_date", "worksite_id", "work_date"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    place_type: Mapped[str] = mapped_column(String(20), nullable=False)  # SITE | ACCOMMODATION
    worksite_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("worksites.id", ondelete="SET NULL"),
        nullable=True,
    )
    accommodation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("accommodations.id", ondelete="SET NULL"),
        nullable=True,
    )
    entry_event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("mobile_event_logs.event_id", ondelete="RESTRICT"),
        nullable=False,
    )
    exit_event_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("mobile_event_logs.event_id", ondelete="SET NULL"),
        nullable=True,
    )
    entry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_inferred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_inside_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    counts_as_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    flags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class TrackingGap(Base):
    """Derived tracking gap records between LOCATION_DISABLED and LOCATION_ENABLED."""

    __tablename__ = "tracking_gaps"
    __table_args__ = (Index("ix_tracking_gaps_employee_date", "employee_id", "work_date"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    disabled_event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("mobile_event_logs.event_id", ondelete="RESTRICT"),
        nullable=False,
    )
    enabled_event_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("mobile_event_logs.event_id", ondelete="SET NULL"),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    disabled_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    disabled_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    disabled_location_captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resumed_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    resumed_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    distance_between_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_inside_site_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("worksites.id", ondelete="SET NULL"),
        nullable=True,
    )
    end_inside_site_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("worksites.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_inferred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class AttendanceRecord(Base):
    """Daily attendance summary record for an employee on a work date."""

    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint("employee_id", "work_date", name="uq_attendance_records_employee_date"),
        Index("ix_attendance_records_date", "work_date"),
        Index("ix_attendance_records_review_status", "review_status"),
        Index("ix_attendance_records_business_status", "business_status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    current_calculation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "attendance_calculations.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_attendance_records_current_calc",
        ),
        nullable=True,
    )
    business_status: Mapped[str] = mapped_column(String(30), default="ABSENT", nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), default="AUTO", nullable=False)
    locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    current_calculation: Mapped["AttendanceCalculation | None"] = relationship(
        "AttendanceCalculation",
        foreign_keys=[current_calculation_id],
        post_update=True,
    )
    calculations: Mapped[list["AttendanceCalculation"]] = relationship(
        "AttendanceCalculation",
        back_populates="attendance_record",
        foreign_keys="AttendanceCalculation.attendance_record_id",
        order_by="AttendanceCalculation.version_no.desc()",
    )
    comments: Mapped[list["AttendanceComment"]] = relationship(
        "AttendanceComment",
        back_populates="attendance_record",
        order_by="AttendanceComment.created_at.asc()",
    )
    approvals: Mapped[list["AttendanceApproval"]] = relationship(
        "AttendanceApproval",
        back_populates="attendance_record",
        order_by="AttendanceApproval.created_at.desc()",
    )


class AttendanceCalculation(Base):
    """Immutable versioned calculation snapshots for daily attendance."""

    __tablename__ = "attendance_calculations"
    __table_args__ = (
        UniqueConstraint(
            "attendance_record_id", "version_no", name="uq_attendance_calc_record_version"
        ),
        Index("ix_attendance_calc_record", "attendance_record_id"),
        Index("ix_attendance_calc_hash", "input_hash"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    attendance_record_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("attendance_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    engine_version: Mapped[str] = mapped_column(String(20), default="1.0.0", nullable=False)
    reason: Mapped[str] = mapped_column(String(50), default="NEW_EVENTS", nullable=False)

    # Planned values from resolved time rules
    planned_accommodation_departure: Mapped[time | None] = mapped_column(Time, nullable=True)
    planned_first_site_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    planned_break_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    planned_last_site_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    planned_accommodation_return: Mapped[time | None] = mapped_column(Time, nullable=True)
    planned_total_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    planned_worked_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    standard_hours_minutes: Mapped[int] = mapped_column(Integer, default=480, nullable=False)

    # Actual values from verified site visits & pings
    accommodation_departure_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    first_site_entry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    break_minutes_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    break_source: Mapped[str] = mapped_column(String(50), default="RULE", nullable=False)
    last_site_exit_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    accommodation_return_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Durations & variations
    elapsed_site_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shift_span_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unaccounted_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    worked_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    required_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    variation_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shortfall_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    grace_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    grace_applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    satisfied: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Movement breakdown
    productive_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    transit_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    offsite_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idle_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Overtime
    ot1_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ot2_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ot_threshold_minutes: Mapped[int] = mapped_column(Integer, default=480, nullable=False)
    day_type: Mapped[str] = mapped_column(String(30), default="NORMAL", nullable=False)

    # Counts & status
    assigned_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    business_status: Mapped[str] = mapped_column(String(30), default="ABSENT", nullable=False)
    flags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    review_reasons: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)

    # Snapshots
    visits_snapshot: Mapped[dict[str, Any] | list[Any]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    gaps_snapshot: Mapped[dict[str, Any] | list[Any]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    inputs_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    source_event_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)), default=list, nullable=False
    )

    attendance_record: Mapped["AttendanceRecord"] = relationship(
        "AttendanceRecord",
        back_populates="calculations",
        foreign_keys=[attendance_record_id],
    )


class AttendanceComment(Base):
    """Operational comments and explanations attached to daily attendance records."""

    __tablename__ = "attendance_comments"
    __table_args__ = (Index("ix_attendance_comments_attendance_id", "attendance_id"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    attendance_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("attendance_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    comment_type: Mapped[str] = mapped_column(String(50), nullable=False)
    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    scheduled_work_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("scheduled_work.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    attendance_record: Mapped["AttendanceRecord"] = relationship(
        "AttendanceRecord",
        back_populates="comments",
    )


class AttendanceApproval(Base):
    """Approval or rejection decisions on attendance records by Engineers/Admin."""

    __tablename__ = "attendance_approvals"
    __table_args__ = (
        Index("ix_attendance_approvals_attendance_id", "attendance_id"),
        Index("ix_attendance_approvals_calc_id", "calculation_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    attendance_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("attendance_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewer_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # APPROVED | REJECTED
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    calculation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("attendance_calculations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    attendance_record: Mapped["AttendanceRecord"] = relationship(
        "AttendanceRecord",
        back_populates="approvals",
    )


class PendingVisit(Base):
    """Scheduled work occurrences that ended without counted visits (follow-up queue)."""

    __tablename__ = "pending_visits"
    __table_args__ = (
        Index("ix_pending_visits_status_due", "status", "due_date"),
        Index("ix_pending_visits_employee", "employee_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    scheduled_work_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("scheduled_work.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    occurrence_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("job_occurrences.id", ondelete="SET NULL"),
        nullable=True,
    )
    worksite_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("worksites.id", ondelete="CASCADE"),
        nullable=False,
    )
    employee_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    detected_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="OPEN", nullable=False)
    explanation_comment_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("attendance_comments.id", ondelete="SET NULL"),
        nullable=True,
    )
    rescheduled_to_scheduled_work_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("scheduled_work.id", ondelete="SET NULL"),
        nullable=True,
    )
    closed_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    closed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
