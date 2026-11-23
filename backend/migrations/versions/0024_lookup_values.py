"""Managed lists for staff types and grade codes (DEC-60, ADR-030).

Creates ``lookup_values`` and seeds it:
- staff types: the former controlled list plus every distinct value already on employees and
  job items (merged ignoring case and spaces; the controlled spelling wins);
- grade codes: every distinct base code already on employees, job items and salary revision
  lines (so G8-G25 from the revision appear).

The seed list is copied here on purpose: a migration must not change when the code does.

Revision ID: 0024_lookup_values
Revises: 0023_revision_line_allowances
Create Date: 2026-11-23
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024_lookup_values"
down_revision: str | None = "0023_revision_line_allowances"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SEED_STAFF_TYPES = [
    "Admin",
    "Commercial - QS",
    "Foreman With DL",
    "Foreman Without DL",
    "Gardener - Hand Watering",
    "Gardener Expert",
    "Gardener Helper",
    "HSE Engineer",
    "Irrigation Engineer",
    "Irrigation Technician",
    "Landscaping Engineer",
    "Palm Tree Technician",
    "Project Manager",
    "Superintendent",
    "Supervisor",
    "Team Leader",
]
_BASE_GRADE = re.compile(r"^G\d{1,2}[A-Z]?$")


def _key(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value).replace(" ", " ")).strip()
    return cleaned or None


def upgrade() -> None:
    op.create_table(
        "lookup_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("list_key", sa.String(50), nullable=False),
        sa.Column("value", sa.String(100), nullable=False),
        sa.Column("value_key", sa.String(100), nullable=False),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "deactivated_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("list_key", "value_key", name="uq_lookup_values_list_key_value_key"),
        sa.CheckConstraint(
            "list_key IN ('staff_grade_description', 'grade_code')",
            name="ck_lookup_values_list_key",
        ),
        sa.CheckConstraint(
            "source IN ('SEED', 'SCREEN', 'IMPORT')", name="ck_lookup_values_source"
        ),
    )
    op.create_index("ix_lookup_values_list_key_active", "lookup_values", ["list_key", "is_active"])

    bind = op.get_bind()
    staff: dict[str, str] = {_key(v): v for v in _SEED_STAFF_TYPES}
    for (raw,) in bind.execute(
        sa.text(
            "SELECT DISTINCT staff_grade_description FROM employees "
            "UNION SELECT DISTINCT staff_grade_description FROM job_items"
        )
    ):
        cleaned = _clean(raw)
        if cleaned and _key(cleaned) not in staff:
            staff[_key(cleaned)] = cleaned[:100]

    grades: set[str] = set()
    for (raw,) in bind.execute(
        sa.text(
            "SELECT DISTINCT grade_code FROM employees "
            "UNION SELECT DISTINCT planned_grade_code FROM job_items "
            "UNION SELECT DISTINCT grade_code FROM salary_revision_lines"
        )
    ):
        cleaned = (_clean(raw) or "").upper()
        if _BASE_GRADE.match(cleaned):
            grades.add(cleaned)

    now = datetime.now(UTC)
    rows = [
        {"list_key": "staff_grade_description", "value": v, "value_key": k}
        for k, v in staff.items()
    ] + [{"list_key": "grade_code", "value": g, "value_key": g.lower()} for g in grades]
    if rows:
        table = sa.table(
            "lookup_values",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("list_key", sa.String),
            sa.column("value", sa.String),
            sa.column("value_key", sa.String),
            sa.column("source", sa.String),
            sa.column("is_active", sa.Boolean),
            sa.column("version", sa.Integer),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        )
        op.bulk_insert(
            table,
            [
                {
                    **r,
                    "id": uuid.uuid4(),
                    "source": "SEED",
                    "is_active": True,
                    "version": 1,
                    "created_at": now,
                    "updated_at": now,
                }
                for r in rows
            ],
        )


def downgrade() -> None:
    op.drop_index("ix_lookup_values_list_key_active", table_name="lookup_values")
    op.drop_table("lookup_values")
