"""Leave requests, reassignment requests, and alerts.

Revision ID: 0008_leave_reassign_approvals
Revises: 0007_base_op_planner
Create Date: 2026-11-08 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0008_leave_reassign_approvals"
down_revision: str | None = "0007_base_op_planner"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. leave_requests
    op.create_table(
        "leave_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("leave_type", sa.String(30), nullable=False),
        sa.Column("from_date", sa.Date(), nullable=False),
        sa.Column("to_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="REQUESTED"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "recorded_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "approved_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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
            "leave_type IN ('ANNUAL', 'SICK', 'UNPAID', 'EMERGENCY', 'OTHER')",
            name="ck_leave_requests_leave_type",
        ),
        sa.CheckConstraint(
            "status IN ('REQUESTED', 'APPROVED', 'REJECTED', 'CANCELLED')",
            name="ck_leave_requests_status",
        ),
        sa.CheckConstraint("to_date >= from_date", name="ck_leave_requests_date_order"),
    )
    op.create_index("ix_leave_requests_emp_dates", "leave_requests", ["employee_id", "from_date", "to_date"])
    op.create_index("ix_leave_requests_status", "leave_requests", ["status"])
    op.create_index("ix_leave_requests_recorded_by", "leave_requests", ["recorded_by_user_id"])

    # 2. reassignment_requests
    op.create_table(
        "reassignment_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("reassignment_type", sa.String(20), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column(
            "original_employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "new_employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "original_scheduled_work_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scheduled_work.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "standing_assignment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("standing_assignments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "target_job_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("job_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("hours_per_day", sa.Numeric(5, 2), nullable=True),
        sa.Column("reason_category", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("is_late_approval", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_orphaned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "requested_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "decided_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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
            "reassignment_type IN ('REPLACE', 'MOVE', 'ADD', 'CANCEL')",
            name="ck_reassignment_requests_type",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED', 'EXPIRED')",
            name="ck_reassignment_requests_status",
        ),
        sa.CheckConstraint("date_to >= date_from", name="ck_reassignment_requests_date_order"),
    )
    op.create_index("ix_reassign_requests_dates", "reassignment_requests", ["date_from", "date_to"])
    op.create_index("ix_reassign_requests_status", "reassignment_requests", ["status"])
    op.create_index("ix_reassign_requests_orig_emp", "reassignment_requests", ["original_employee_id"])
    op.create_index("ix_reassign_requests_new_emp", "reassignment_requests", ["new_employee_id"])

    # 3. Add reassignment_request_id and is_late_approval to scheduled_work
    op.add_column(
        "scheduled_work",
        sa.Column(
            "reassignment_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("reassignment_requests.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "scheduled_work",
        sa.Column("is_late_approval", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_scheduled_work_reassign_id", "scheduled_work", ["reassignment_request_id"])

    # 4. alerts table
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "target_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("target_role", sa.String(30), nullable=True),
        sa.Column("ref_type", sa.String(50), nullable=False),
        sa.Column("ref_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "resolved_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint("status IN ('OPEN', 'RESOLVED')", name="ck_alerts_status"),
    )
    op.create_index("ix_alerts_status_type", "alerts", ["status", "alert_type"])
    op.create_index("ix_alerts_target_user", "alerts", ["target_user_id", "status"])
    op.create_index("ix_alerts_target_role", "alerts", ["target_role", "status"])


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_index("ix_scheduled_work_reassign_id", table_name="scheduled_work")
    op.drop_column("scheduled_work", "is_late_approval")
    op.drop_column("scheduled_work", "reassignment_request_id")
    op.drop_table("reassignment_requests")
    op.drop_table("leave_requests")
