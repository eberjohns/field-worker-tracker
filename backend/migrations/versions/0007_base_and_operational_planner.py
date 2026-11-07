"""Base Roster Templates, Entries and Operational Overrides (Rebuilt Planner)

Revision ID: 0007_base_op_planner
Revises: 0006_planner_and_scheduling
Create Date: 2026-11-07 17:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007_base_op_planner"
down_revision: str | None = "0006_planner_and_scheduling"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. base_roster_templates
    op.create_table(
        "base_roster_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("job_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("allocation_mode", sa.String(20), nullable=False, server_default="UNIFORM"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_base_roster_templates_date_order",
        ),
        sa.CheckConstraint(
            "allocation_mode IN ('UNIFORM', 'DAY_OF_WEEK')",
            name="ck_base_roster_templates_mode",
        ),
    )
    op.create_index(
        "ix_base_roster_templates_job_item",
        "base_roster_templates",
        ["job_item_id", "is_active"],
    )

    # 2. base_roster_entries
    op.create_table(
        "base_roster_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("base_roster_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("weekday_mask", sa.String(20), nullable=False),
        sa.Column("assigned_hours", sa.Numeric(5, 2), nullable=False),
        sa.Column("sequence", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_base_roster_entries_lookup",
        "base_roster_entries",
        ["template_id", "weekday_mask"],
    )

    # 3. Add columns to scheduled_work
    op.add_column(
        "scheduled_work",
        sa.Column(
            "original_employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "scheduled_work",
        sa.Column("override_reason", sa.String(100), nullable=True),
    )

    # 4. Update check constraint on scheduled_work source
    op.drop_constraint("ck_scheduled_work_source", "scheduled_work", type_="check")
    op.create_check_constraint(
        "ck_scheduled_work_source",
        "scheduled_work",
        "source IN ('TEMPLATE', 'STANDING', 'DIRECT', 'OVERRIDE', 'EXCEPTION', 'FOLLOW_UP')",
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM scheduled_work WHERE source NOT IN ('STANDING', 'DIRECT', 'EXCEPTION', 'FOLLOW_UP')"
        )
    )
    op.drop_constraint("ck_scheduled_work_source", "scheduled_work", type_="check")
    op.create_check_constraint(
        "ck_scheduled_work_source",
        "scheduled_work",
        "source IN ('STANDING', 'DIRECT', 'EXCEPTION', 'FOLLOW_UP')",
    )
    op.drop_column("scheduled_work", "override_reason")
    op.drop_column("scheduled_work", "original_employee_id")
    op.drop_index("ix_base_roster_entries_lookup", table_name="base_roster_entries")
    op.drop_table("base_roster_entries")
    op.drop_index("ix_base_roster_templates_job_item", table_name="base_roster_templates")
    op.drop_table("base_roster_templates")
