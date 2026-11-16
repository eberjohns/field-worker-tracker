"""Database models for reports and generated report history."""

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from fw.core.db import Base


class GeneratedReport(Base):
    """Archived generated report artifact (month-end or on-demand snapshot).

    DEC-46: Month-end reports auto-generated and every file kept,
    named <Company>_<Report>_<Country>_<Period>_generated-<datetime>.xlsx.
    Never deleted; every copy stays downloadable.
    """

    __tablename__ = "generated_reports"
    __table_args__ = (
        Index("ix_generated_reports_lookup", "report_key", "country", "period_start"),
        Index("ix_generated_reports_kind_period", "kind", "period_start", "period_end"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    report_key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(10), default="AE", nullable=False, index=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    kind: Mapped[str] = mapped_column(
        String(30), default="MONTH_END", nullable=False, index=True
    )  # MONTH_END | ON_DEMAND
    params: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA-256
    payroll_run_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("payroll_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="DRAFT", nullable=False
    )  # DRAFT | APPROVED | READY
    visible_roles: Mapped[list[str]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb"), nullable=False
    )
    generated_by: Mapped[str] = mapped_column(String(100), default="system", nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        nullable=False,
    )


class ReportExport(Base):
    """Asynchronous background report export job.

    Doc 12: Large exports run as background jobs (report_exports).
    """

    __tablename__ = "report_exports"
    __table_args__ = (
        Index("ix_report_exports_status", "status", "created_at"),
        Index("ix_report_exports_user", "requested_by_user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    report_key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    format: Mapped[str] = mapped_column(String(10), default="xlsx", nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="PENDING", nullable=False
    )  # PENDING | PROCESSING | COMPLETED | FAILED
    params: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb"), nullable=False
    )
    requested_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def sa_text(txt: str):
    """Helper for server defaults."""
    return text(txt)
