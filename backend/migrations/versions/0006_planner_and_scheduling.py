"""Standing assignments and scheduled work (Phase 05)

Revision ID: 0006_planner_and_scheduling
Revises: 0005_sites_boundaries_jobs
Create Date: 2026-11-05 09:00:00.000000

"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006_planner_and_scheduling"
down_revision: str | None = "0005_sites_boundaries_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. standing_assignments
    op.create_table(
        "standing_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "job_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("job_items.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("weekday_pattern", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("hours_per_day", sa.Numeric(5, 2), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
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
        sa.CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_standing_assignments_date_order",
        ),
    )
    op.create_index(
        "ix_standing_assignments_dates",
        "standing_assignments",
        ["start_date", "end_date"],
    )
    op.create_index(
        "ix_standing_assignments_is_active",
        "standing_assignments",
        ["is_active"],
    )

    # 2. scheduled_work
    op.create_table(
        "scheduled_work",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid4),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column(
            "occurrence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("job_occurrences.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "job_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("job_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "worksite_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("worksites.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("assigned_hours", sa.Numeric(5, 2), nullable=False),
        sa.Column("sequence", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
        sa.Column("source", sa.String(length=20), server_default="STANDING", nullable=False),
        sa.Column(
            "original_scheduled_work_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scheduled_work.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
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
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'CANCELLED', 'REASSIGNED', 'COMPLETED')",
            name="ck_scheduled_work_status",
        ),
        sa.CheckConstraint(
            "source IN ('STANDING', 'DIRECT', 'EXCEPTION', 'FOLLOW_UP')",
            name="ck_scheduled_work_source",
        ),
        sa.CheckConstraint("assigned_hours > 0", name="ck_scheduled_work_assigned_hours_positive"),
        sa.CheckConstraint("sequence > 0", name="ck_scheduled_work_sequence_positive"),
    )

    op.create_index("ix_scheduled_work_work_date", "scheduled_work", ["work_date"])
    op.create_index(
        "ix_scheduled_work_worksite_date", "scheduled_work", ["worksite_id", "work_date"]
    )
    op.create_index("ix_scheduled_work_emp_date", "scheduled_work", ["employee_id", "work_date"])
    op.create_index("ix_scheduled_work_job_item", "scheduled_work", ["job_item_id"])
    op.create_index("ix_scheduled_work_occurrence", "scheduled_work", ["occurrence_id"])
    op.create_index("ix_scheduled_work_status", "scheduled_work", ["status"])

    # Partial unique indexes for active work
    op.create_index(
        "uq_scheduled_work_emp_date_occ_active",
        "scheduled_work",
        ["employee_id", "work_date", "occurrence_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE' AND occurrence_id IS NOT NULL"),
    )
    op.create_index(
        "uq_scheduled_work_emp_date_seq_active",
        "scheduled_work",
        ["employee_id", "work_date", "sequence"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index("uq_scheduled_work_emp_date_seq_active", table_name="scheduled_work")
    op.drop_index("uq_scheduled_work_emp_date_occ_active", table_name="scheduled_work")
    op.drop_index("ix_scheduled_work_status", table_name="scheduled_work")
    op.drop_index("ix_scheduled_work_occurrence", table_name="scheduled_work")
    op.drop_index("ix_scheduled_work_job_item", table_name="scheduled_work")
    op.drop_index("ix_scheduled_work_emp_date", table_name="scheduled_work")
    op.drop_index("ix_scheduled_work_worksite_date", table_name="scheduled_work")
    op.drop_index("ix_scheduled_work_work_date", table_name="scheduled_work")
    op.drop_table("scheduled_work")

    op.drop_index("ix_standing_assignments_is_active", table_name="standing_assignments")
    op.drop_index("ix_standing_assignments_dates", table_name="standing_assignments")
    op.drop_table("standing_assignments")
