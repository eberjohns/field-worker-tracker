"""SQLAlchemy 2.0 async models for Standing Assignments and Scheduled Work."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fw.core.db import Base, ModelBase


class StandingAssignment(ModelBase):
    """Standing team assignment for a worker on a job item (the Year Plan)."""

    __tablename__ = "standing_assignments"
    __table_args__ = (
        CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_standing_assignments_date_order",
        ),
        Index("ix_standing_assignments_dates", "start_date", "end_date"),
        Index("ix_standing_assignments_is_active", "is_active"),
    )

    employee_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    job_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("job_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    weekday_pattern: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    hours_per_day: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])
    job_item = relationship("JobItem", foreign_keys=[job_item_id])


class ScheduledWork(Base):
    """Daily concrete scheduled work assignment for one worker on one work date."""

    __tablename__ = "scheduled_work"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE', 'CANCELLED', 'REASSIGNED', 'COMPLETED')",
            name="ck_scheduled_work_status",
        ),
        CheckConstraint(
            "source IN ('STANDING', 'DIRECT', 'EXCEPTION', 'FOLLOW_UP')",
            name="ck_scheduled_work_source",
        ),
        CheckConstraint("assigned_hours > 0", name="ck_scheduled_work_assigned_hours_positive"),
        CheckConstraint("sequence > 0", name="ck_scheduled_work_sequence_positive"),
        Index("ix_scheduled_work_work_date", "work_date"),
        Index("ix_scheduled_work_worksite_date", "worksite_id", "work_date"),
        Index("ix_scheduled_work_emp_date", "employee_id", "work_date"),
        Index("ix_scheduled_work_job_item", "job_item_id"),
        Index("ix_scheduled_work_occurrence", "occurrence_id"),
        Index("ix_scheduled_work_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    occurrence_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("job_occurrences.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("job_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    worksite_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("worksites.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    sequence: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="STANDING", nullable=False)
    original_scheduled_work_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("scheduled_work.id", ondelete="SET NULL"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
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

    # Relationships
    employee = relationship("Employee", foreign_keys=[employee_id])
    job_item = relationship("JobItem", foreign_keys=[job_item_id])
    worksite = relationship("Worksite", foreign_keys=[worksite_id])
    occurrence = relationship("JobOccurrence", foreign_keys=[occurrence_id])

