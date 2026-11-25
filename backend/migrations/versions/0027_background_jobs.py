"""Background jobs with progress (Batch 9 step 4).

Creates ``background_jobs``: a long operation (first: the payroll draft) run outside the request
that started it, with its status, progress, heartbeat and result. A partial unique index allows
one active (QUEUED or RUNNING) job per ``dedupe_key``. Additive only; no existing data changes.

Revision ID: 0027_background_jobs
Revises: 0026_materialise_manual_times
Create Date: 2026-11-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0027_background_jobs"
down_revision: str | None = "0026_materialise_manual_times"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("dedupe_key", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=False),
        sa.Column("phase", sa.String(50), nullable=True),
        sa.Column("progress_done", sa.Integer(), nullable=False),
        sa.Column("progress_total", sa.Integer(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_background_jobs_kind_status", "background_jobs", ["kind", "status"])
    op.create_index(
        "ix_background_jobs_created_by_user_id", "background_jobs", ["created_by_user_id"]
    )
    op.create_index(
        "uq_background_jobs_active_key",
        "background_jobs",
        ["dedupe_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('QUEUED', 'RUNNING')"),
    )


def downgrade() -> None:
    op.drop_index("uq_background_jobs_active_key", table_name="background_jobs")
    op.drop_index("ix_background_jobs_created_by_user_id", table_name="background_jobs")
    op.drop_index("ix_background_jobs_kind_status", table_name="background_jobs")
    op.drop_table("background_jobs")
