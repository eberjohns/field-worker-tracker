"""Google Maps usage counters and their soft limits (Batch 8, ADR-033).

Creates ``map_usage_counters`` (one row per environment, month and kind) and adds two company
settings, ``map_loads_soft_limit_month`` (7200) and ``geocodes_soft_limit_month`` (2400): 80 % of
the starting daily quotas over 30 days. Additive only; no existing data changes.

Revision ID: 0028_map_usage_counters
Revises: 0027_background_jobs
Create Date: 2026-11-25
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0028_map_usage_counters"
down_revision: str | None = "0027_background_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOFT_LIMITS = [("map_loads_soft_limit_month", 7200), ("geocodes_soft_limit_month", 2400)]


def upgrade() -> None:
    op.create_table(
        "map_usage_counters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("environment", "month", "kind", name="uq_map_usage_env_month_kind"),
    )
    conn = op.get_bind()
    for key, value in SOFT_LIMITS:
        exists = conn.execute(
            sa.text(
                "SELECT 1 FROM company_setting_values WHERE setting_key = :k AND country IS NULL"
            ),
            {"k": key},
        ).first()
        if exists:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO company_setting_values "
                "(id, setting_key, country, value, unit, effective_from, created_at) "
                "VALUES (:id, :k, NULL, CAST(:v AS JSONB), 'per month', :f, :c)"
            ),
            {
                "id": uuid.uuid4(),
                "k": key,
                "v": json.dumps(value),
                "f": date(2026, 1, 1),
                "c": datetime.now(UTC),
            },
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM company_setting_values WHERE setting_key IN "
        "('map_loads_soft_limit_month', 'geocodes_soft_limit_month')"
    )
    op.drop_table("map_usage_counters")
