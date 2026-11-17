"""Add break_minutes to employee_salary and salary_revision_lines.

Revision ID: 0015_salary_break_minutes
Revises: 0014_archive_and_retention
Create Date: 2026-11-17 18:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_salary_break_minutes"
down_revision: str | None = "0014_archive_and_retention"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    es_cols = {c["name"] for c in inspector.get_columns("employee_salary")}
    if "break_minutes" not in es_cols:
        op.add_column("employee_salary", sa.Column("break_minutes", sa.Integer(), nullable=True))

    srl_cols = {c["name"] for c in inspector.get_columns("salary_revision_lines")}
    if "break_minutes" not in srl_cols:
        op.add_column(
            "salary_revision_lines", sa.Column("break_minutes", sa.Integer(), nullable=True)
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    srl_cols = {c["name"] for c in inspector.get_columns("salary_revision_lines")}
    if "break_minutes" in srl_cols:
        op.drop_column("salary_revision_lines", "break_minutes")

    es_cols = {c["name"] for c in inspector.get_columns("employee_salary")}
    if "break_minutes" in es_cols:
        op.drop_column("employee_salary", "break_minutes")
