"""Import batches, rows, and employee salary structures (Phase 03)

Revision ID: 0004_import_and_salary
Revises: 0003_settings_and_time_rules
Create Date: 2026-11-03 17:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004_import_and_salary"
down_revision: str | None = "0003_settings_and_time_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. import_batches
    op.create_table(
        "import_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(length=50), nullable=False, server_default="FULL_WORKBOOK"),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("template_version", sa.String(length=20), nullable=False, server_default="v1.0"),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="UPLOADED"),
        sa.Column(
            "summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"
        ),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('UPLOADED', 'PREVIEWED', 'COMMITTED', 'FAILED', 'ROLLED_BACK')",
            name="ck_import_batches_status",
        ),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_import_batches_status", "import_batches", ["status"])
    op.create_index("ix_import_batches_file_hash", "import_batches", ["file_hash"])
    op.create_index("ix_import_batches_created_at", "import_batches", ["created_at"])

    # 2. import_rows
    op.create_table(
        "import_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sheet", sa.String(length=50), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("natural_key", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("codes", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column(
            "messages", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"
        ),
        sa.Column(
            "diff", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"
        ),
        sa.Column(
            "normalized",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "raw_row", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "action IN ('NEW', 'UPDATED', 'UNCHANGED', 'REACTIVATED', 'CLASH', 'ERROR', 'SKIPPED')",
            name="ck_import_rows_action",
        ),
        sa.CheckConstraint(
            "status IN ('OK', 'WARNING', 'ERROR', 'INFO')",
            name="ck_import_rows_status",
        ),
        sa.ForeignKeyConstraint(["batch_id"], ["import_batches.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_import_rows_batch_id", "import_rows", ["batch_id"])
    op.create_index(
        "ix_import_rows_batch_sheet_status", "import_rows", ["batch_id", "sheet", "status"]
    )
    op.create_index("ix_import_rows_batch_natural_key", "import_rows", ["batch_id", "natural_key"])

    # 3. employee_salary
    op.create_table(
        "employee_salary",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column(
            "standard_hours", sa.Numeric(precision=4, scale=1), nullable=False, server_default="8.0"
        ),
        sa.Column("basic_salary", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "special_allowance",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "fixed_ot_amount",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "bonus", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0.00"
        ),
        sa.Column(
            "telephone_allowance",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column(
            "housing_transport_allowance",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("employee_id", "effective_from", name="uq_employee_salary_effective"),
    )
    op.create_index("ix_employee_salary_employee_id", "employee_salary", ["employee_id"])
    op.create_index("ix_employee_salary_effective_from", "employee_salary", ["effective_from"])
    op.create_index(
        "ix_employee_salary_lookup", "employee_salary", ["employee_id", "effective_from"]
    )


def downgrade() -> None:
    op.drop_table("employee_salary")
    op.drop_table("import_rows")
    op.drop_table("import_batches")
