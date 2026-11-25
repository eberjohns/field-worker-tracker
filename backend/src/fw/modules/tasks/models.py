from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from fw.core.db import Base

JOB_QUEUED = "QUEUED"
JOB_RUNNING = "RUNNING"
JOB_SUCCEEDED = "SUCCEEDED"
JOB_FAILED = "FAILED"
JOB_INTERRUPTED = "INTERRUPTED"
ACTIVE_STATUSES = (JOB_QUEUED, JOB_RUNNING)


class BackgroundJob(Base):
    """A long operation run outside the request that started it, with its progress
    (docs/07-data-model.md). The first kind is the payroll draft (Batch 9 step 4)."""

    __tablename__ = "background_jobs"
    __table_args__ = (
        Index("ix_background_jobs_kind_status", "kind", "status"),
        # At most one active job per dedupe key, even with two requests at the same moment.
        Index(
            "uq_background_jobs_active_key",
            "dedupe_key",
            unique=True,
            postgresql_where=text("status IN ('QUEUED', 'RUNNING')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    # One active job per key (for example "payroll_draft:AE:2026-10-01").
    dedupe_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=JOB_QUEUED)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    phase: Mapped[str | None] = mapped_column(String(50), nullable=True)
    progress_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Written at least every few seconds while the job runs; a RUNNING job whose heartbeat is
    # older than HEARTBEAT_STALE_AFTER is reported as INTERRUPTED (its process stopped).
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
