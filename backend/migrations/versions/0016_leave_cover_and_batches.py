"""Add leave cover_employee_id, reassignment batch_id/batch_note, and scheduled_work is_weekly_off_cover.

Revision ID: 0016_leave_cover_and_batches
Revises: 0015_salary_break_minutes
Create Date: 2026-11-18 13:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_leave_cover_and_batches"
down_revision: str | None = "0015_salary_break_minutes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    lr_cols = {c["name"] for c in inspector.get_columns("leave_requests")}
    if "cover_employee_id" not in lr_cols:
        op.add_column(
            "leave_requests",
            sa.Column(
                "cover_employee_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("employees.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index("ix_leave_requests_cover_emp", "leave_requests", ["cover_employee_id"])

    rr_cols = {c["name"] for c in inspector.get_columns("reassignment_requests")}
    if "batch_id" not in rr_cols:
        op.add_column(
            "reassignment_requests",
            sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_index("ix_reassignment_requests_batch_id", "reassignment_requests", ["batch_id"])
    if "batch_note" not in rr_cols:
        op.add_column("reassignment_requests", sa.Column("batch_note", sa.Text(), nullable=True))

    sw_cols = {c["name"] for c in inspector.get_columns("scheduled_work")}
    if "is_weekly_off_cover" not in sw_cols:
        op.add_column(
            "scheduled_work",
            sa.Column(
                "is_weekly_off_cover",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    sw_cols = {c["name"] for c in inspector.get_columns("scheduled_work")}
    if "is_weekly_off_cover" in sw_cols:
        op.drop_column("scheduled_work", "is_weekly_off_cover")

    rr_cols = {c["name"] for c in inspector.get_columns("reassignment_requests")}
    if "batch_note" in rr_cols:
        op.drop_column("reassignment_requests", "batch_note")
    if "batch_id" in rr_cols:
        rr_indexes = {idx["name"] for idx in inspector.get_indexes("reassignment_requests")}
        if "ix_reassignment_requests_batch_id" in rr_indexes:
            op.drop_index("ix_reassignment_requests_batch_id", table_name="reassignment_requests")
        op.drop_column("reassignment_requests", "batch_id")

    lr_cols = {c["name"] for c in inspector.get_columns("leave_requests")}
    if "cover_employee_id" in lr_cols:
        lr_indexes = {idx["name"] for idx in inspector.get_indexes("leave_requests")}
        if "ix_leave_requests_cover_emp" in lr_indexes:
            op.drop_index("ix_leave_requests_cover_emp", table_name="leave_requests")
        op.drop_column("leave_requests", "cover_employee_id")
