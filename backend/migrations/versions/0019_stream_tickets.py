"""Create stream_tickets table for multi-process SSE auth.

Revision ID: 0019_stream_tickets
Revises: 0018_reporting_lines_active
Create Date: 2026-11-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_stream_tickets"
down_revision: str | Sequence[str] | None = "0018_reporting_lines_active"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stream_tickets",
        sa.Column("ticket", sa.String(length=64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("ticket"),
    )
    op.create_index(
        "ix_stream_tickets_expires_at",
        "stream_tickets",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_stream_tickets_expires_at", table_name="stream_tickets")
    op.drop_table("stream_tickets")
