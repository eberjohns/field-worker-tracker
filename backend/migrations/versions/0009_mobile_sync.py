"""Mobile sync, consent records, and mobile event logs.

Revision ID: 0009_mobile_sync
Revises: 0008_leave_reassign_approvals
Create Date: 2026-11-08 14:00:00.000000

"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0009_mobile_sync"
down_revision: str | None = "0008_leave_reassign_approvals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. sync_changes
    op.create_table(
        "sync_changes",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=False),
        sa.Column("entity_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("op", sa.String(length=20), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("priority", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_sync_changes_employee_id_id",
        "sync_changes",
        ["employee_id", "id"],
    )

    # 2. consent_records
    op.create_table(
        "consent_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("registered_devices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_consent_records_employee_id", "consent_records", ["employee_id"])

    # 3. mobile_event_logs
    op.create_table(
        "mobile_event_logs",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "device_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("registered_devices.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("worksites.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "job_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("job_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "accommodation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accommodations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("event_timestamp_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location_captured_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column(
            "geom",
            geoalchemy2.types.Geometry(
                geometry_type="POINT",
                srid=4326,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=True,
            ),
            nullable=True,
        ),
        sa.Column("accuracy_meters", sa.Float(), nullable=True),
        sa.Column("is_mock_location", sa.Boolean(), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=True),
        sa.Column("device_clock_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "server_received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("is_processed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(
        "ix_mobile_event_logs_employee_time",
        "mobile_event_logs",
        ["employee_id", "event_timestamp_utc"],
    )
    op.create_index(
        "ix_mobile_event_logs_device_id",
        "mobile_event_logs",
        ["device_id"],
    )
    op.create_index(
        "ix_mobile_event_logs_event_type",
        "mobile_event_logs",
        ["event_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_mobile_event_logs_event_type", table_name="mobile_event_logs")
    op.drop_index("ix_mobile_event_logs_device_id", table_name="mobile_event_logs")
    op.drop_index("ix_mobile_event_logs_employee_time", table_name="mobile_event_logs")
    op.drop_table("mobile_event_logs")

    op.drop_index("ix_consent_records_employee_id", table_name="consent_records")
    op.drop_table("consent_records")

    op.drop_index("ix_sync_changes_employee_id_id", table_name="sync_changes")
    op.drop_table("sync_changes")
