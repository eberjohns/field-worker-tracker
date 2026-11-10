from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from fw.core.db import Base


class MobileEventLog(Base):
    """Raw mobile location event log (immutable fact store + server verdict)."""

    __tablename__ = "mobile_event_logs"
    __table_args__ = (
        Index("ix_mobile_event_logs_employee_time", "employee_id", "event_timestamp_utc"),
        Index("ix_mobile_event_logs_device_id", "device_id"),
        Index("ix_mobile_event_logs_event_type", "event_type"),
        Index("ix_mobile_event_logs_processing_status", "processing_status"),
    )

    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    employee_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
    )
    device_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("registered_devices.id", ondelete="RESTRICT"),
        nullable=False,
    )
    job_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("worksites.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_item_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("job_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    accommodation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("accommodations.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_timestamp_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location_captured_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    geom: Mapped[Geometry | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326),
        nullable=True,
    )
    accuracy_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_mock_location: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    sequence_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    device_clock_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    server_received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    is_processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Phase 08 server enrichment fields
    batch_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    device_clock_skew_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processing_status: Mapped[str] = mapped_column(String(30), nullable=False, default="ACCEPTED")
    error_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    server_site_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("worksites.id", ondelete="SET NULL"),
        nullable=True,
    )
    server_accommodation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("accommodations.id", ondelete="SET NULL"),
        nullable=True,
    )
    server_verdict: Mapped[str | None] = mapped_column(String(30), nullable=True)
    distance_to_polygon_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    flags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)


class EmployeeLastPosition(Base):
    """Last known verified position per employee (used for live monitoring)."""

    __tablename__ = "employee_last_position"

    employee_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        primary_key=True,
    )
    last_event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("mobile_event_logs.event_id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    accuracy_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    event_timestamp_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    server_verdict: Mapped[str | None] = mapped_column(String(30), nullable=True)
    server_site_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("worksites.id", ondelete="SET NULL"),
        nullable=True,
    )
    tracking_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_contact_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LiveLocationAccessLog(Base):
    """Access log for live location stream and polling views (privacy audit trail)."""

    __tablename__ = "live_location_access_logs"
    __table_args__ = (
        Index("ix_live_location_access_logs_user", "user_id"),
        Index("ix_live_location_access_logs_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    access_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'STREAM' | 'POLL'
    filters: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    client_ip: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
