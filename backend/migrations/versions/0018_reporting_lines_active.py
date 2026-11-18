"""Add is_active to reporting lines and change_source to employee_salary.

Revision ID: 0018_reporting_lines_active
Revises: 0017_single_standalone_admin
Create Date: 2026-11-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_reporting_lines_active"
down_revision: str | Sequence[str] | None = "0017_single_standalone_admin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add is_active, deactivated_at, deactivated_by to employee_reporting_lines
    op.add_column(
        "employee_reporting_lines",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "employee_reporting_lines",
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "employee_reporting_lines",
        sa.Column(
            "deactivated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )

    # 2. Replace uq_employee_manager_relationship with partial unique index for active rows
    op.drop_constraint("uq_employee_manager_relationship", "employee_reporting_lines", type_="unique")
    op.create_index(
        "uq_employee_manager_relationship_active",
        "employee_reporting_lines",
        ["employee_id", "manager_id", "relationship"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    # 3. Update ix_unique_single_supervisor to apply only to active rows
    op.drop_index("ix_unique_single_supervisor", table_name="employee_reporting_lines")
    op.create_index(
        "ix_unique_single_supervisor",
        "employee_reporting_lines",
        ["employee_id"],
        unique=True,
        postgresql_where=sa.text("relationship = 'SUPERVISOR' AND is_active = true"),
    )

    op.create_index("ix_reporting_lines_active", "employee_reporting_lines", ["is_active"])

    # 4. Add change_source to employee_salary
    op.add_column(
        "employee_salary",
        sa.Column("change_source", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("employee_salary", "change_source")

    op.drop_index("ix_reporting_lines_active", table_name="employee_reporting_lines")
    op.drop_index("ix_unique_single_supervisor", table_name="employee_reporting_lines")
    op.create_index(
        "ix_unique_single_supervisor",
        "employee_reporting_lines",
        ["employee_id"],
        unique=True,
        postgresql_where=sa.text("relationship = 'SUPERVISOR'"),
    )

    op.drop_index("uq_employee_manager_relationship_active", table_name="employee_reporting_lines")
    op.create_unique_constraint(
        "uq_employee_manager_relationship",
        "employee_reporting_lines",
        ["employee_id", "manager_id", "relationship"],
    )

    op.drop_column("employee_reporting_lines", "deactivated_by")
    op.drop_column("employee_reporting_lines", "deactivated_at")
    op.drop_column("employee_reporting_lines", "is_active")
