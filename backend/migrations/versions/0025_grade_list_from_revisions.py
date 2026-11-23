"""Grade list follows the active salary revisions (DEC-60 amended, owner decision 23 Nov 2026).

A grade code exists only by having a line in an ACTIVE salary revision; payroll keeps the
``grade_code`` rows of ``lookup_values`` in step (source ``REVISION``). This migration:
- allows the source ``REVISION``;
- rebuilds the grade rows: the base codes with a line in an ACTIVE revision become active rows
  (source REVISION); every other grade row is deactivated (records keep their value).

Revision ID: 0025_grade_list_from_revisions
Revises: 0024_lookup_values
Create Date: 2026-11-23
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0025_grade_list_from_revisions"
down_revision: str | None = "0024_lookup_values"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Copied on purpose (a migration must not change when the code does): DEC-58 base grade code.
_BASE_RE = re.compile(r"^G\d{1,2}[A-Z]?$")


def _key(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def upgrade() -> None:
    op.drop_constraint("ck_lookup_values_source", "lookup_values", type_="check")
    op.create_check_constraint(
        "ck_lookup_values_source",
        "lookup_values",
        "source IN ('SEED', 'SCREEN', 'IMPORT', 'REVISION')",
    )

    conn = op.get_bind()
    codes = {
        str(c).strip().upper()
        for c in conn.execute(
            sa.text(
                "SELECT DISTINCT l.grade_code FROM salary_revision_lines l "
                "JOIN salary_revisions r ON r.id = l.revision_id WHERE r.status = 'ACTIVE'"
            )
        ).scalars()
        if c and _BASE_RE.match(str(c).strip().upper())
    }
    wanted = {_key(c): c for c in codes}
    rows = conn.execute(
        sa.text("SELECT id, value_key, is_active FROM lookup_values WHERE list_key = 'grade_code'")
    ).all()
    now = datetime.now(UTC)
    existing = {r.value_key: r for r in rows}
    for key, row in existing.items():
        if key in wanted:
            conn.execute(
                sa.text(
                    "UPDATE lookup_values SET is_active = true, source = 'REVISION', "
                    "deactivated_at = NULL, deactivated_by_user_id = NULL, "
                    "version = version + 1, updated_at = :now WHERE id = :id"
                ),
                {"id": row.id, "now": now},
            )
        elif row.is_active:
            conn.execute(
                sa.text(
                    "UPDATE lookup_values SET is_active = false, deactivated_at = :now, "
                    "version = version + 1, updated_at = :now WHERE id = :id"
                ),
                {"id": row.id, "now": now},
            )
    for key, code in wanted.items():
        if key not in existing:
            conn.execute(
                sa.text(
                    "INSERT INTO lookup_values (id, list_key, value, value_key, source, "
                    "is_active, version, created_at, updated_at) VALUES (:id, 'grade_code', "
                    ":value, :key, 'REVISION', true, 1, :now, :now)"
                ),
                {"id": uuid.uuid4(), "value": code, "key": key, "now": now},
            )


def downgrade() -> None:
    # Rows stay as they are; REVISION rows are labelled IMPORT so the old CHECK holds.
    op.execute("UPDATE lookup_values SET source = 'IMPORT' WHERE source = 'REVISION'")
    op.drop_constraint("ck_lookup_values_source", "lookup_values", type_="check")
    op.create_check_constraint(
        "ck_lookup_values_source",
        "lookup_values",
        "source IN ('SEED', 'SCREEN', 'IMPORT')",
    )
