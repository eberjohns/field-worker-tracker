"""Generated reports archive, exports queue, and report permissions.

Revision ID: 0013_reports_history
Revises: 0012_payroll_and_budget
Create Date: 2026-11-16 11:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_reports_history"
down_revision: str | None = "0012_payroll_and_budget"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Check if generated_reports already exists from aborted transaction
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "generated_reports" not in tables:
        op.create_table(
            "generated_reports",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("report_key", sa.String(50), nullable=False),
            sa.Column("country", sa.String(10), nullable=False, server_default="AE"),
            sa.Column("period_start", sa.Date(), nullable=True),
            sa.Column("period_end", sa.Date(), nullable=True),
            sa.Column("kind", sa.String(30), nullable=False, server_default="MONTH_END"),
            sa.Column(
                "params",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("file_name", sa.String(255), nullable=False),
            sa.Column("file_ref", sa.String(500), nullable=False),
            sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
            sa.Column("file_hash", sa.String(64), nullable=True),
            sa.Column(
                "payroll_run_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("payroll_runs.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(30), nullable=False, server_default="DRAFT"),
            sa.Column(
                "visible_roles",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column("generated_by", sa.String(100), nullable=False, server_default="system"),
            sa.Column(
                "generated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )
        op.create_index(
            "ix_generated_reports_lookup",
            "generated_reports",
            ["report_key", "country", "period_start"],
        )
        op.create_index(
            "ix_generated_reports_kind_period",
            "generated_reports",
            ["kind", "period_start", "period_end"],
        )
        op.create_index(
            "ix_generated_reports_payroll_run_id",
            "generated_reports",
            ["payroll_run_id"],
        )

    if "report_exports" not in tables:
        op.create_table(
            "report_exports",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("report_key", sa.String(50), nullable=False),
            sa.Column("format", sa.String(10), nullable=False, server_default="xlsx"),
            sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
            sa.Column(
                "params",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "requested_by_user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("file_name", sa.String(255), nullable=True),
            sa.Column("file_ref", sa.String(500), nullable=True),
            sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
            sa.Column("file_hash", sa.String(64), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            "ix_report_exports_status",
            "report_exports",
            ["status", "created_at"],
        )
        op.create_index(
            "ix_report_exports_user",
            "report_exports",
            ["requested_by_user_id", "created_at"],
        )


def downgrade() -> None:
    op.drop_table("report_exports")
    op.drop_table("generated_reports")
