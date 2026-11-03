from datetime import UTC, date, datetime, time
from typing import Any
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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from fw.core.db import Base


class CompanySettingValue(Base):
    """Effective-dated company setting values (docs/07-data-model.md, BR-ST-04)."""

    __tablename__ = "company_setting_values"
    __table_args__ = (
        UniqueConstraint(
            "setting_key",
            "country",
            "effective_from",
            name="uq_setting_key_country_effective_from",
        ),
        Index("ix_company_settings_key_date", "setting_key", "effective_from"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    setting_key: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
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


class TimeRule(Base):
    """Time rules for planned schedules, breaks, and seasons (docs/07-data-model.md, D3)."""

    __tablename__ = "time_rules"
    __table_args__ = (
        Index("ix_time_rules_scope", "scope_type", "scope_employee_id"),
        Index("ix_time_rules_dates", "start_date", "end_date"),
        Index("ix_time_rules_country", "country"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    scope_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # COMPANY, TEAM, DRIVERS, EMPLOYEE
    scope_employee_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=True,
    )
    applies_to: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ALL"
    )  # ALL, OUTDOOR_ONLY, INDOOR_ONLY
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # 5-point schedule (nullable = inherit)
    accommodation_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    first_site_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    break_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_site_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    accommodation_end: Mapped[time | None] = mapped_column(Time, nullable=True)

    standard_hours_change_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

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


class PublicHoliday(Base):
    """Statutory and observed public holidays per country (docs/07-data-model.md)."""

    __tablename__ = "public_holidays"
    __table_args__ = (
        UniqueConstraint("holiday_date", "country", name="uq_public_holidays_date_country"),
        Index("ix_public_holidays_country_date", "country", "holiday_date"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)  # AE, SA
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


class ConsentPolicy(Base):
    """Versioned location consent policies per language (docs/07-data-model.md)."""

    __tablename__ = "consent_policies"
    __table_args__ = (
        UniqueConstraint("version", "language", name="uq_consent_policies_version_lang"),
        Index("ix_consent_policies_version_lang", "version", "language"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False)  # en, ar, etc.
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    published_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
