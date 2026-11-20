"""Create employee_attribute_history table for tracking grade, designation, and driver status changes.

Revision ID: 0021_employee_attribute_history
Revises: 0020_worksite_supervisors
Create Date: 2026-11-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021_employee_attribute_history"
down_revision: str | Sequence[str] | None = "0020_worksite_supervisors"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employee_attribute_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attribute_name", sa.String(length=50), nullable=False),
        sa.Column("old_value", sa.String(length=255), nullable=True),
        sa.Column("new_value", sa.String(length=255), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("changed_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_employee_attribute_history_employee",
        "employee_attribute_history",
        ["employee_id"],
        unique=False,
    )
    op.create_index(
        "ix_employee_attribute_history_attribute",
        "employee_attribute_history",
        ["attribute_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_employee_attribute_history_attribute", table_name="employee_attribute_history")
    op.drop_index("ix_employee_attribute_history_employee", table_name="employee_attribute_history")
    op.drop_table("employee_attribute_history")
