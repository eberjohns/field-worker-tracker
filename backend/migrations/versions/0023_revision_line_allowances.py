"""Telephone and housing/transport allowances on salary revision lines (DEC-59, ADR-029).

The job budget costs a grade the way payroll costs a person, so a revision line needs the two
allowances payroll includes in the salary portion. The client's revision sheet has no such
columns, so existing and imported lines default to 0.

Revision ID: 0023_revision_line_allowances
Revises: 0022_base_grade_codes
Create Date: 2026-11-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_revision_line_allowances"
down_revision: str | None = "0022_base_grade_codes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for col in ("telephone_allowance", "housing_transport_allowance"):
        op.add_column(
            "salary_revision_lines",
            sa.Column(col, sa.Numeric(14, 2), nullable=False, server_default="0.00"),
        )


def downgrade() -> None:
    op.drop_column("salary_revision_lines", "housing_transport_allowance")
    op.drop_column("salary_revision_lines", "telephone_allowance")
