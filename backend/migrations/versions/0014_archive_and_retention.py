"""Archive records, consent withdrawal, worker anonymisation, and retention.

Revision ID: 0014_archive_and_retention
Revises: 0013_reports_history
Create Date: 2026-11-16 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_archive_and_retention"
down_revision: str | None = "0013_reports_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. Archive records table
    if "archive_records" not in tables:
        op.create_table(
            "archive_records",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("file_name", sa.String(255), nullable=False),
            sa.Column("file_path", sa.String(500), nullable=False),
            sa.Column("file_size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("sha256_checksum", sa.String(64), nullable=False),
            sa.Column(
                "encryption_algo",
                sa.String(50),
                nullable=False,
                server_default="AES-256-GCM",
            ),
            sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(30), nullable=False, server_default="COMPLETED"),
            sa.Column(
                "archived_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("purged_record_count", sa.Integer(), nullable=True),
            sa.Column(
                "details",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )
        op.create_index(
            "ix_archive_records_year",
            "archive_records",
            ["year"],
        )
        op.create_index(
            "ix_archive_records_status",
            "archive_records",
            ["status"],
        )

    # 2. Add columns to employees table if missing
    emp_columns = [c["name"] for c in inspector.get_columns("employees")]
    if "consent_status" not in emp_columns:
        op.add_column(
            "employees",
            sa.Column(
                "consent_status",
                sa.String(20),
                nullable=False,
                server_default="ACCEPTED",
            ),
        )
    if "consent_withdrawn_at" not in emp_columns:
        op.add_column(
            "employees",
            sa.Column("consent_withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "anonymised_at" not in emp_columns:
        op.add_column(
            "employees",
            sa.Column("anonymised_at", sa.DateTime(timezone=True), nullable=True),
        )

    # 3. Add columns to consent_records if table exists
    if "consent_records" in tables:
        op.alter_column("consent_records", "device_id", nullable=True)
        cr_columns = [c["name"] for c in inspector.get_columns("consent_records")]
        if "status" not in cr_columns:
            op.add_column(
                "consent_records",
                sa.Column(
                    "status",
                    sa.String(20),
                    nullable=False,
                    server_default="ACCEPTED",
                ),
            )
        if "withdrawn_at" not in cr_columns:
            op.add_column(
                "consent_records",
                sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
            )
        if "withdrawal_reason" not in cr_columns:
            op.add_column(
                "consent_records",
                sa.Column("withdrawal_reason", sa.String(255), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "consent_records" in tables:
        op.alter_column("consent_records", "device_id", nullable=False)
        cr_columns = [c["name"] for c in inspector.get_columns("consent_records")]
        if "withdrawal_reason" in cr_columns:
            op.drop_column("consent_records", "withdrawal_reason")
        if "withdrawn_at" in cr_columns:
            op.drop_column("consent_records", "withdrawn_at")
        if "status" in cr_columns:
            op.drop_column("consent_records", "status")

    if "employees" in tables:
        emp_columns = [c["name"] for c in inspector.get_columns("employees")]
        if "anonymised_at" in emp_columns:
            op.drop_column("employees", "anonymised_at")
        if "consent_withdrawn_at" in emp_columns:
            op.drop_column("employees", "consent_withdrawn_at")
        if "consent_status" in emp_columns:
            op.drop_column("employees", "consent_status")

    if "archive_records" in tables:
        op.drop_index("ix_archive_records_status", table_name="archive_records")
        op.drop_index("ix_archive_records_year", table_name="archive_records")
        op.drop_table("archive_records")
