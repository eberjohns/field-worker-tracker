"""The salary components of a payroll record, read the same way everywhere.

A run stores the six components that make up ``salary_portion`` in ``snapshot["salary"]``.
Runs made before v1.16.0 stored only ``basic_salary`` there; for them each missing component
comes from the salary row the run used (``payroll_records.salary_id``), or the employee's row in
effect at the end of the period.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.modules.payroll.models import EmployeeSalary, PayrollRecord
from fw.modules.payroll.schemas import COUNTRY_CURRENCY

SALARY_COMPONENTS: tuple[str, ...] = (
    "basic_salary",
    "special_allowance",
    "fixed_ot_amount",
    "bonus",
    "telephone_allowance",
    "housing_transport_allowance",
)

_ZERO = Decimal("0.00")


def salary_snapshot(row: EmployeeSalary | None) -> dict[str, str]:
    """The six components of ``row`` as stored in a record snapshot (all 0 without a row)."""
    return {key: str(getattr(row, key) if row else _ZERO) for key in SALARY_COMPONENTS}


def salary_components(
    snapshot: Mapping[str, Any] | None, salary_row: EmployeeSalary | None
) -> dict[str, Decimal]:
    """Each component from ``snapshot["salary"]``, else the old top-level key, else the row."""
    snap = snapshot or {}
    nested = snap.get("salary") or {}
    out: dict[str, Decimal] = {}
    for key in SALARY_COMPONENTS:
        raw = nested.get(key, snap.get(key))
        if raw is None and salary_row is not None:
            raw = getattr(salary_row, key)
        out[key] = Decimal(str(raw)) if raw is not None else _ZERO
    return out


def _needs_row(snapshot: Mapping[str, Any] | None) -> bool:
    nested = (snapshot or {}).get("salary") or {}
    return any(key not in nested for key in SALARY_COMPONENTS)


async def salary_rows_for_records(
    session: AsyncSession, records: Iterable[PayrollRecord], period_end: date
) -> dict[UUID, EmployeeSalary]:
    """Salary rows for the records whose snapshot lacks a component, keyed by record id.

    One query for the rows the run used (``salary_id``); records without one fall back to the
    employee's row in effect at ``period_end``.
    """
    pending = [r for r in records if _needs_row(r.snapshot)]
    if not pending:
        return {}
    by_id: dict[UUID, EmployeeSalary] = {}
    ids = {r.salary_id for r in pending if r.salary_id}
    if ids:
        rows = (
            (await session.execute(select(EmployeeSalary).where(EmployeeSalary.id.in_(ids))))
            .scalars()
            .all()
        )
        by_id = {row.id: row for row in rows}

    out: dict[UUID, EmployeeSalary] = {}
    for rec in pending:
        row = by_id.get(rec.salary_id) if rec.salary_id else None
        if row is None:
            row = await session.scalar(
                select(EmployeeSalary)
                .where(
                    EmployeeSalary.employee_id == rec.employee_id,
                    EmployeeSalary.effective_from <= period_end,
                )
                .order_by(EmployeeSalary.effective_from.desc(), EmployeeSalary.created_at.desc())
                .limit(1)
            )
        if row is not None:
            out[rec.id] = row
    return out


def default_currency(country: str | None) -> str:
    """AE -> AED, SA -> SAR (the seeded ``currency`` settings); AED otherwise."""
    return COUNTRY_CURRENCY.get((country or "").upper(), "AED")
