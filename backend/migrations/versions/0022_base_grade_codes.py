"""Base grade codes everywhere (DEC-58): suffix_label on revisions, actor_role on attribute history.

- ``salary_revisions.suffix_label``: display suffix for grade lines (G3C -> "G3C-2026"),
  backfilled with the year of ``effective_from``.
- ``employee_attribute_history.actor_role``: role of the user who made the change (ADR-026).
- Current-state grade columns are reduced to the base code, removing only suffixes recognised
  for certain: ``-YYYY``, ``-R<n>`` and a hyphen inside the code (``G5-C`` -> ``G5C``):
  ``salary_revision_lines.grade_code``, ``job_items.planned_grade_code``, ``employees.grade_code``.
  History tables are immutable and are not rewritten.
- Values that cannot be parsed are left unchanged and listed in the migration output
  (they surface as INVALID_GRADE_CODE / MISSING_GRADE_RATE in the app).
- Stops (no changes) if stripping would give two lines with the same grade in one revision.

Downgrade drops the two columns. It cannot restore the removed suffixes (data only).

Revision ID: 0022_base_grade_codes
Revises: 0021_employee_attribute_history
Create Date: 2026-11-23
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_base_grade_codes"
down_revision: str | Sequence[str] | None = "0021_employee_attribute_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy of fw.rules.grades (migrations must not change when app code changes).
_GRADE_RE = re.compile(r"^(G\d{1,2})-?([A-Z]?)(?:-(?:\d{4}|R\d{1,3}))?$")


def _base(raw: str | None) -> str | None:
    if raw is None:
        return None
    m = _GRADE_RE.match(raw.strip().upper())
    return (m.group(1) + m.group(2)) if m else None


def _strip_column(conn: sa.Connection, table: str, column: str) -> list[str]:
    """Rewrite parseable values to the base code; return the unparseable ones."""
    rows = conn.execute(
        sa.text(f"SELECT id, {column} FROM {table} WHERE {column} IS NOT NULL AND {column} <> ''")
    ).fetchall()
    bad: list[str] = []
    for row_id, value in rows:
        base = _base(value)
        if base is None:
            bad.append(value)
        elif base != value:
            conn.execute(
                sa.text(f"UPDATE {table} SET {column} = :v WHERE id = :id"),
                {"v": base, "id": row_id},
            )
    return bad


def upgrade() -> None:
    op.add_column("salary_revisions", sa.Column("suffix_label", sa.String(length=20)))
    op.add_column("employee_attribute_history", sa.Column("actor_role", sa.String(length=30)))

    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE salary_revisions SET suffix_label = CAST(EXTRACT(YEAR FROM effective_from) "
            "AS INTEGER)::text WHERE suffix_label IS NULL"
        )
    )

    # Duplicate check before touching revision lines.
    lines = conn.execute(
        sa.text(
            "SELECT l.revision_id, r.code, l.grade_code FROM salary_revision_lines l "
            "JOIN salary_revisions r ON r.id = l.revision_id"
        )
    ).fetchall()
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for rev_id, rev_code, grade in lines:
        groups[(str(rev_id), rev_code)].append(_base(grade) or grade)
    clashes = []
    for (_, rev_code), grades in groups.items():
        seen: set[str] = set()
        for g in grades:
            if g in seen:
                clashes.append(f"{rev_code}: {g}")
            seen.add(g)
    if clashes:
        raise RuntimeError(
            "0022: removing grade suffixes would duplicate revision lines; fix these first: "
            + ", ".join(sorted(set(clashes)))
        )

    unparseable: dict[str, list[str]] = {}
    for table, column in (
        ("salary_revision_lines", "grade_code"),
        ("job_items", "planned_grade_code"),
        ("employees", "grade_code"),
    ):
        bad = _strip_column(conn, table, column)
        if bad:
            unparseable[f"{table}.{column}"] = sorted(set(bad))
    if unparseable:
        print(f"0022: grade codes left unchanged (cannot parse for certain): {unparseable}")
    else:
        print("0022: all grade codes parsed; no unparseable values found.")


def downgrade() -> None:
    op.drop_column("employee_attribute_history", "actor_role")
    op.drop_column("salary_revisions", "suffix_label")
