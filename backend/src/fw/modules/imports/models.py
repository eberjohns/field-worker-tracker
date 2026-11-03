"""Database models for bulk import batches and row-level preview/commit states."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fw.core.db import Base


class ImportBatch(Base):
    """Import batch representing an uploaded workbook."""

    __tablename__ = "import_batches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('UPLOADED', 'PREVIEWED', 'COMMITTED', 'FAILED', 'ROLLED_BACK')",
            name="ck_import_batches_status",
        ),
        Index("ix_import_batches_status", "status"),
        Index("ix_import_batches_created_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(50), default="FULL_WORKBOOK", nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    template_version: Mapped[str] = mapped_column(String(20), default="v1.0", nullable=False)
    uploaded_by_user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), default="UPLOADED", nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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

    rows: Mapped[list["ImportRow"]] = relationship(
        "ImportRow",
        back_populates="batch",
        cascade="all, delete-orphan",
    )


class ImportRow(Base):
    """Row-level parsed and classified import record."""

    __tablename__ = "import_rows"
    __table_args__ = (
        CheckConstraint(
            "action IN ('NEW', 'UPDATED', 'UNCHANGED', 'REACTIVATED', 'CLASH', 'ERROR', 'SKIPPED')",
            name="ck_import_rows_action",
        ),
        CheckConstraint(
            "status IN ('OK', 'WARNING', 'ERROR', 'INFO')",
            name="ck_import_rows_status",
        ),
        Index("ix_import_rows_batch_sheet_status", "batch_id", "sheet", "status"),
        Index("ix_import_rows_batch_natural_key", "batch_id", "natural_key"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("import_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sheet: Mapped[str] = mapped_column(String(50), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    natural_key: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    codes: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    messages: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    diff: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    normalized: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    raw_row: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    batch: Mapped[ImportBatch] = relationship("ImportBatch", back_populates="rows")
