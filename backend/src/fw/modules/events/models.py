from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from fw.core.db import Base


class MobileEventLog(Base):
    """Raw mobile location event log (immutable fact store)."""

    __tablename__ = "mobile_event_logs"
    __table_args__ = (
        Index("ix_mobile_event_logs_employee_time", "employee_id", "event_timestamp_utc"),
        Index("ix_mobile_event_logs_device_id", "device_id"),
        Index("ix_mobile_event_logs_event_type", "event_type"),
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
