"""Create worksite_supervisors table for multi-supervisor worksite scoping.

Revision ID: 0020_worksite_supervisors
Revises: 0019_stream_tickets
Create Date: 2026-11-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_worksite_supervisors"
down_revision: str | Sequence[str] | None = "0019_stream_tickets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "worksite_supervisors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("worksite_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supervisor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(["worksite_id"], ["worksites.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supervisor_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("worksite_id", "supervisor_id", name="uq_worksite_supervisor"),
    )
    op.create_index(
        "ix_worksite_supervisors_worksite",
        "worksite_supervisors",
        ["worksite_id"],
        unique=False,
    )
    op.create_index(
        "ix_worksite_supervisors_supervisor",
        "worksite_supervisors",
        ["supervisor_id"],
        unique=False,
    )
    op.create_index(
        "ix_worksite_supervisors_is_active",
        "worksite_supervisors",
        ["is_active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_worksite_supervisors_is_active", table_name="worksite_supervisors")
    op.drop_index("ix_worksite_supervisors_supervisor", table_name="worksite_supervisors")
    op.drop_index("ix_worksite_supervisors_worksite", table_name="worksite_supervisors")
    op.drop_table("worksite_supervisors")
