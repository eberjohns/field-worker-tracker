from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fw.core.db import Base, ModelBase


class Group(ModelBase):
    """Normalized Worksite Group (e.g. Dubai Parks, Mina Rashid)."""

    __tablename__ = "groups"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class Zone(ModelBase):
    """Normalized Worksite Zone (e.g. Zone A, Zone B)."""

    __tablename__ = "zones"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class Accommodation(ModelBase):
    """Worker accommodation camp / living quarters (docs/07-data-model.md)."""

    __tablename__ = "accommodations"

    accommodation_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    boundary: Mapped[Geometry | None] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=4326),
        nullable=True,
    )
    rep_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    rep_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)

    @property
    def has_boundary(self) -> bool:
        return self.boundary is not None


class Employee(ModelBase):
    """Employee record representing field workers and operations staff."""

    __tablename__ = "employees"
    __table_args__ = (
        CheckConstraint(
            "role IN ('WORKER', 'SUPERVISOR', 'SUPERINTENDENT', 'ENGINEER', 'ADMIN')",
            name="check_employees_role_valid",
        ),
        CheckConstraint(
            "country IN ('AE', 'SA')",
            name="check_employees_country_valid",
        ),
        CheckConstraint(
            "weekly_off_day IS NULL OR weekly_off_day IN ('MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY')",
            name="check_employees_weekly_off_day_valid",
        ),
        Index("ix_employees_country", "country"),
        Index("ix_employees_staff_grade_description", "staff_grade_description"),
        Index("ix_employees_grade_code", "grade_code"),
        Index("ix_employees_is_active", "is_active"),
    )

    tally_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    grade_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    staff_grade_description: Mapped[str | None] = mapped_column(String(100), nullable=True)
    accommodation_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accommodations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    weekly_off_day: Mapped[str | None] = mapped_column(String(15), nullable=True)
    is_driver: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    country: Mapped[str] = mapped_column(String(2), default="AE", nullable=False)
    break_override_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    join_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    employment_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    accommodation: Mapped[Accommodation | None] = relationship("Accommodation")


class EmployeeReportingLine(Base):
    """Direct reporting relationship link (employee, manager, relationship)."""

    __tablename__ = "employee_reporting_lines"
    __table_args__ = (
        CheckConstraint("employee_id <> manager_id", name="check_reporting_no_self_link"),
        CheckConstraint(
            "relationship IN ('SUPERVISOR', 'SUPERINTENDENT', 'ENGINEER')",
            name="check_reporting_relationship_valid",
        ),
        UniqueConstraint(
            "employee_id",
            "manager_id",
            "relationship",
            name="uq_employee_manager_relationship",
        ),
        Index(
            "ix_unique_single_supervisor",
            "employee_id",
            unique=True,
            postgresql_where=(mapped_column("relationship") == "SUPERVISOR"),
        ),
        Index("ix_reporting_lines_manager_rel", "manager_id", "relationship"),
        Index("ix_reporting_lines_employee", "employee_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    )
    manager_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    )
    relationship: Mapped[str] = mapped_column(String(20), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
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


class EmployeeGradeHistory(Base):
    """Immutable audit log of employee Grade Code changes (BR-EM-07)."""

    __tablename__ = "employee_grade_history"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    old_grade_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_grade_code: Mapped[str] = mapped_column(String(50), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    changed_by_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class EmployeeDocument(Base):
    """Employee document validity records (Visa, Passport, Emirates ID, etc.)."""

    __tablename__ = "employee_documents"
    __table_args__ = (
        CheckConstraint(
            "document_type IN ('VISA', 'PASSPORT', 'EMIRATES_ID', 'LABOUR_CARD', 'DRIVING_LICENCE', 'IQAMA')",
            name="check_document_type_valid",
        ),
        UniqueConstraint("employee_id", "document_type", name="uq_employee_document_type"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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


class RegisteredDevice(Base):
    """Mobile device bound to a worker (docs/07-data-model.md)."""

    __tablename__ = "registered_devices"
    __table_args__ = (
        CheckConstraint("platform IN ('ANDROID', 'IOS')", name="check_device_platform_valid"),
        Index(
            "ix_unique_active_device_per_employee",
            "employee_id",
            unique=True,
            postgresql_where=(mapped_column("is_active") == True),  # noqa: E712
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    employee_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    device_identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    device_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    push_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_acked_cursor: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    location_permission_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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
