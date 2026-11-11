"""Live location access logs and escalation settings.

Revision ID: 0011_live_map_and_alerts
Revises: 0010_events_and_attendance
Create Date: 2026-11-10 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_live_map_and_alerts"
down_revision: str | None = "0010_events_and_attendance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create live_location_access_logs table
    op.create_table(
        "live_location_access_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("access_type", sa.String(length=20), nullable=False),
        sa.Column(
            "filters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("client_ip", sa.String(length=50), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_live_location_access_logs_user",
        "live_location_access_logs",
        ["user_id"],
    )
    op.create_index(
        "ix_live_location_access_logs_created_at",
        "live_location_access_logs",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_live_location_access_logs_created_at",
        table_name="live_location_access_logs",
    )
    op.drop_index(
        "ix_live_location_access_logs_user",
        table_name="live_location_access_logs",
    )
    op.drop_table("live_location_access_logs")
