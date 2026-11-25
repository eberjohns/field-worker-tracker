"""Login lockout (Batch 7, DEC-66).

Adds ``users.last_failed_login_at`` (the failed-attempt count reuses the existing
``users.failed_attempts``, the lock reuses ``users.locked_until``) and two company settings:
``login_max_failed_attempts`` (5) and ``login_lockout_minutes`` (15). Additive only.

Revision ID: 0029_login_lockout
Revises: 0028_map_usage_counters
Create Date: 2026-11-25
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0029_login_lockout"
down_revision: str | None = "0028_map_usage_counters"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SETTINGS = [
    ("login_max_failed_attempts", 5, "attempts"),
    ("login_lockout_minutes", 15, "minutes"),
]


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("last_failed_login_at", sa.DateTime(timezone=True), nullable=True)
    )
    conn = op.get_bind()
    for key, value, unit in SETTINGS:
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
                "VALUES (:id, :k, NULL, CAST(:v AS JSONB), :u, :f, :c)"
            ),
            {
                "id": uuid.uuid4(),
                "k": key,
                "v": json.dumps(value),
                "u": unit,
                "f": date(2026, 1, 1),
                "c": datetime.now(UTC),
            },
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM company_setting_values WHERE setting_key IN "
        "('login_max_failed_attempts', 'login_lockout_minutes')"
    )
    op.drop_column("users", "last_failed_login_at")
