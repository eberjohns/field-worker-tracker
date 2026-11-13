from datetime import UTC, date, datetime, time
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fw.core.db import Base, ModelBase


class Vehicle(ModelBase):
    """Transport vehicle (e.g. Hiace, Ertiga, Deira Bus)."""

    __tablename__ = "vehicles"

    label: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="VAN")  # BUS, VAN, OTHER
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    runs: Mapped[list["TransportRun"]] = relationship("TransportRun", back_populates="vehicle")


class TransportRun(ModelBase):
    """Daily transport run for a driver in a direction (MORNING or EVENING)."""

    __tablename__ = "transport_runs"
    __table_args__ = (
        Index(
            "uq_transport_runs_active_driver_date_dir",
            "run_date",
            "direction",
            "driver_id",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
        Index("ix_transport_runs_date_dir", "run_date", "direction"),
        Index("ix_transport_runs_driver", "driver_id"),
    )

    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)  # MORNING, EVENING
    driver_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    )
    vehicle_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("vehicles.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="DRAFT"
    )  # DRAFT, PUBLISHED
    needs_update: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    vehicle: Mapped[Vehicle | None] = relationship("Vehicle", back_populates="runs")
    stops: Mapped[list["TransportRunStop"]] = relationship(
        "TransportRunStop",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="TransportRunStop.sequence",
    )
    passengers: Mapped[list["TransportRunPassenger"]] = relationship(
        "TransportRunPassenger",
        back_populates="run",
        cascade="all, delete-orphan",
    )


class TransportRunStop(Base):
    """An ordered stop along a transport run (worksite or accommodation)."""

    __tablename__ = "transport_run_stops"
    __table_args__ = (Index("ix_transport_run_stops_run_seq", "run_id", "sequence"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("transport_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    stop_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="SITE"
    )  # SITE, ACCOMMODATION
    worksite_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("worksites.id", ondelete="SET NULL"),
        nullable=True,
    )
    accommodation_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accommodations.id", ondelete="SET NULL"),
        nullable=True,
    )
    planned_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationships
    run: Mapped[TransportRun] = relationship("TransportRun", back_populates="stops")
    passengers: Mapped[list["TransportRunPassenger"]] = relationship(
        "TransportRunPassenger",
        back_populates="stop",
        cascade="all, delete-orphan",
    )


class TransportRunPassenger(Base):
    """A passenger worker boarding/alighting at a stop on a run."""

    __tablename__ = "transport_run_passengers"
    __table_args__ = (
        Index("ix_transport_run_passengers_run_emp", "run_id", "employee_id"),
        Index("ix_transport_run_passengers_stop", "stop_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("transport_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    stop_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("transport_run_stops.id", ondelete="CASCADE"),
        nullable=False,
    )
    employee_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationships
    run: Mapped[TransportRun] = relationship("TransportRun", back_populates="passengers")
    stop: Mapped[TransportRunStop] = relationship("TransportRunStop", back_populates="passengers")
