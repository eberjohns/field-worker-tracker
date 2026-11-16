"""Database models for employee salary structures and history."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fw.core.db import Base


class EmployeeSalary(Base):
    """Effective-dated employee salary structure record."""

    __tablename__ = "employee_salary"
    __table_args__ = (
        UniqueConstraint("employee_id", "effective_from", name="uq_employee_salary_effective"),
        Index("ix_employee_salary_lookup", "employee_id", "effective_from"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    standard_hours: Mapped[Decimal] = mapped_column(
        Numeric(4, 1), default=Decimal("8.0"), nullable=False
    )
    basic_salary: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    special_allowance: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    fixed_ot_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    bonus: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    telephone_allowance: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    housing_transport_allowance: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    import_batch_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("import_batches.id", ondelete="SET NULL"),
        nullable=True,
    )
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
    employee = relationship("Employee")
    import_batch = relationship("ImportBatch")


class SalaryRevision(Base):
    """Salary Revision record (job budget only) per DEC-29/DEC-37."""

    __tablename__ = "salary_revisions"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(10), default="AE", nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    lines: Mapped[list["SalaryRevisionLine"]] = relationship(
        "SalaryRevisionLine",
        back_populates="revision",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="SalaryRevisionLine.grade_code",
    )


class SalaryRevisionLine(Base):
    """Line item for a salary revision specifying grade base rate and provisions."""

    __tablename__ = "salary_revision_lines"
    __table_args__ = (
        UniqueConstraint("revision_id", "grade_code", name="uq_salary_revision_lines_rev_grade"),
        Index("ix_salary_revision_lines_lookup", "revision_id", "grade_code"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    revision_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("salary_revisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    grade_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    grade_group_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    basic_salary: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    special_allowance: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    fixed_ot_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    bonus: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    visa_provision: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    air_ticket_provision: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    uniform_provision: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    medical_provision: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    accommodation_provision: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    transportation_provision: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=True
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
    revision: Mapped["SalaryRevision"] = relationship("SalaryRevision", back_populates="lines")


class PayrollRun(Base):
    """Monthly payroll run header (DRAFT or APPROVED)."""

    __tablename__ = "payroll_runs"
    __table_args__ = (
        Index("ix_payroll_runs_lookup", "period_start", "period_end", "country", "status"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    country: Mapped[str] = mapped_column(String(10), default="AE", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    run_no: Mapped[int] = mapped_column(nullable=False, default=1)
    created_by: Mapped[str] = mapped_column(String(50), default="SYSTEM", nullable=False)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    calculation_version: Mapped[str] = mapped_column(String(50), default="1.0", nullable=False)
    totals_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    records: Mapped[list["PayrollRecord"]] = relationship(
        "PayrollRecord",
        back_populates="payroll_run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PayrollRecord(Base):
    """Per-worker calculation record for a payroll run (immutable when run is APPROVED)."""

    __tablename__ = "payroll_records"
    __table_args__ = (
        UniqueConstraint("payroll_run_id", "employee_id", name="uq_payroll_records_run_employee"),
        Index("ix_payroll_records_run", "payroll_run_id"),
        Index("ix_payroll_records_employee", "employee_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    payroll_run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("payroll_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    employee_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    )
    salary_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employee_salary.id", ondelete="SET NULL"),
        nullable=True,
    )
    standard_hours: Mapped[Decimal] = mapped_column(
        Numeric(4, 1), default=Decimal("8.0"), nullable=False
    )
    scheduled_hours: Mapped[Decimal] = mapped_column(
        Numeric(6, 1), default=Decimal("0.0"), nullable=False
    )
    worked_hours: Mapped[Decimal] = mapped_column(
        Numeric(6, 1), default=Decimal("0.0"), nullable=False
    )
    paid_leave_hours: Mapped[Decimal] = mapped_column(
        Numeric(6, 1), default=Decimal("0.0"), nullable=False
    )
    unpaid_leave_hours: Mapped[Decimal] = mapped_column(
        Numeric(6, 1), default=Decimal("0.0"), nullable=False
    )
    shortfall_hours: Mapped[Decimal] = mapped_column(
        Numeric(6, 1), default=Decimal("0.0"), nullable=False
    )
    missed_hours_deduction: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    ot1_hours: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), default=Decimal("0.00"), nullable=False
    )
    ot2_hours: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), default=Decimal("0.00"), nullable=False
    )
    salary_portion: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    ot1_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    ot2_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    gross_pay: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    net_pay: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    gratuity: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    leave_salary: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    provisions: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    per_month_provision: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    total_staff_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    hr_oh_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    final_total_staff_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
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
    payroll_run: Mapped["PayrollRun"] = relationship("PayrollRun", back_populates="records")
    employee = relationship("Employee")
    cost_allocations: Mapped[list["JobCostAllocation"]] = relationship(
        "JobCostAllocation",
        back_populates="payroll_record",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class JobCostAllocation(Base):
    """Proportional allocation of a worker's monthly final_total_staff_cost to worksites."""

    __tablename__ = "job_cost_allocations"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    payroll_record_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("payroll_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    worksite_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("worksites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    worked_minutes: Mapped[int] = mapped_column(nullable=False, default=0)
    allocated_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    payroll_record: Mapped["PayrollRecord"] = relationship(
        "PayrollRecord", back_populates="cost_allocations"
    )
    worksite = relationship("Worksite")
