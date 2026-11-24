"""Roster materialisation setting and manual attendance times (owner decisions 25 Nov 2026).

- Seeds ``roster_materialise_weeks`` (4 weeks): how far ahead Base Planner templates become
  scheduled work. An existing value is kept.
- Creates ``attendance_manual_times``: times an Engineer or Admin enters for a day the phone did
  not record, with a required reason. One active row per employee and day.

Revision ID: 0026_materialise_manual_times
Revises: 0025_grade_list_from_revisions
Create Date: 2026-11-25
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0026_materialise_manual_times"
down_revision: str | None = "0025_grade_list_from_revisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        sa.text(
            "SELECT 1 FROM company_setting_values "
            "WHERE setting_key = 'roster_materialise_weeks' LIMIT 1"
        )
    ).first()
    if exists is None:
        settings_table = sa.table(
            "company_setting_values",
            sa.column("id", postgresql.UUID(as_uuid=True)),
            sa.column("setting_key", sa.String),
            sa.column("country", sa.String),
            sa.column("value", postgresql.JSONB),
            sa.column("unit", sa.String),
            sa.column("effective_from", sa.Date),
            sa.column("effective_to", sa.Date),
            sa.column("created_at", sa.DateTime(timezone=True)),
        )
        op.bulk_insert(
            settings_table,
            [
                {
                    "id": uuid.uuid4(),
                    "setting_key": "roster_materialise_weeks",
                    "country": None,
                    "value": 4,
                    "unit": "weeks",
                    "effective_from": date(2026, 1, 1),
                    "effective_to": None,
                    "created_at": datetime.now(UTC),
                }
            ],
        )

    op.create_table(
        "attendance_manual_times",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("first_site_entry_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_site_exit_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accommodation_departure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accommodation_return_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "uq_attendance_manual_times_active",
        "attendance_manual_times",
        ["employee_id", "work_date"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_index("uq_attendance_manual_times_active", table_name="attendance_manual_times")
    op.drop_table("attendance_manual_times")
    op.execute("DELETE FROM company_setting_values WHERE setting_key = 'roster_materialise_weeks'")
