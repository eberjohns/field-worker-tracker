"""SQLAlchemy 2.0 async models for Worksites, Job Items, and Job Occurrences."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fw.core.db import Base, ModelBase


class Worksite(ModelBase):
    """Worksite / parent job (e.g. 12A14301 Dubai Marina Landscape)."""

    __tablename__ = "worksites"
    __table_args__ = (
        CheckConstraint("country IN ('AE', 'SA')", name="ck_worksites_country_valid"),
        Index("ix_worksites_is_active", "is_active"),
    )

    job_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    job_name: Mapped[str] = mapped_column(String(255), nullable=False)
    renewal_reference: Mapped[str | None] = mapped_column(String(50), nullable=True)
    group_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    zone_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("zones.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    customer_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_outdoor: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    contract_group_ref: Mapped[str | None] = mapped_column(String(50), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    boundary: Mapped[Geometry | None] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326),
        nullable=True,
    )
    rep_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    rep_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    budget_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    salary_revision_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Relationships
    items: Mapped[list["JobItem"]] = relationship(
        "JobItem",
        back_populates="worksite",
        lazy="selectin",
        order_by="JobItem.sub_item_code",
    )


class JobItem(ModelBase):
    """Job Item under a worksite with structured recurrence (BR-JB-02 to BR-JB-06)."""

    __tablename__ = "job_items"
    __table_args__ = (
        CheckConstraint(
            "frequency_unit IN ('WEEK', 'MONTH', 'QUARTER', 'YEAR')",
            name="ck_job_items_frequency_unit",
        ),
        CheckConstraint(
            "deployment_type IN ('PERMANENT', 'REMOTE')",
            name="ck_job_items_deployment_type",
        ),
        UniqueConstraint("worksite_id", "sub_item_code", name="uq_job_items_worksite_sub_item"),
        Index("ix_job_items_is_active", "is_active"),
    )

    worksite_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("worksites.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sub_item_code: Mapped[str] = mapped_column(String(50), nullable=False)
    staff_grade_description: Mapped[str] = mapped_column(String(100), nullable=False)
    planned_grade_code: Mapped[str] = mapped_column(String(50), nullable=False)
    frequency_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    occurrences_per_period: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    period_interval: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    weekday_pattern: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    required_staff_count: Mapped[int] = mapped_column(Integer, nullable=False)
    hours_per_occurrence_per_staff: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    declared_activities_per_year: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 3), nullable=True
    )
    declared_total_hours_per_year: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3), nullable=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    deployment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    break_override_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    worksite: Mapped[Worksite] = relationship("Worksite", back_populates="items")
    occurrences: Mapped[list["JobOccurrence"]] = relationship(
        "JobOccurrence",
        back_populates="job_item",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="JobOccurrence.window_start, JobOccurrence.slot_index",
    )


class JobOccurrence(Base):
    """Job occurrence generated from job item frequency over rolling horizon."""

    __tablename__ = "job_occurrences"
    __table_args__ = (
        CheckConstraint(
            "status IN ('GENERATED', 'ASSIGNED', 'COMPLETED', 'CANCELLED')",
            name="ck_job_occurrences_status",
        ),
        CheckConstraint(
            "source IN ('GENERATED', 'MANUAL')",
            name="ck_job_occurrences_source",
        ),
        UniqueConstraint(
            "job_item_id", "window_start", "slot_index", name="uq_job_occurrences_slot"
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_item_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("job_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    window_start: Mapped[date] = mapped_column(Date, nullable=False)
    window_end: Mapped[date] = mapped_column(Date, nullable=False)
    slot_index: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="GENERATED", nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(20), default="GENERATED", nullable=False)
    required_staff_count: Mapped[int] = mapped_column(Integer, nullable=False)
    required_hours_per_staff: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    job_item: Mapped[JobItem] = relationship("JobItem", back_populates="occurrences")
