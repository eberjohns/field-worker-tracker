"""Managed lists (DEC-60, ADR-030): staff types and grade codes.

Every screen that sets a staff type or a grade code validates against the active list here; the
import pipeline reads the lists once per preview.

- Staff types: Admin adds and deactivates them in Settings > Managed Lists; never deleted, never
  added by import.
- Grade codes: the base codes with a line in an ACTIVE salary revision. Payroll keeps this list
  through ``sync_grades`` after every change to revisions; nothing else adds or deactivates a grade
  (owner decision 23 Nov 2026). Payroll sits above this module, so org and jobs can validate
  grades here without reading payroll tables.
"""

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.errors import AppError
from fw.modules.audit import AuditService
from fw.modules.lookups.models import LookupValue
from fw.modules.lookups.repository import LookupRepository
from fw.rules.grades import InvalidGradeCodeError
from fw.rules.lookups import (
    GRADE_CODE,
    GRADE_FROM_REVISION_ONLY,
    INVALID_STAFF_GRADE_DESCRIPTION,
    LIST_KEYS,
    LOOKUP_DUPLICATE,
    LOOKUP_NEAR_MATCH,
    LOOKUP_VALUE_INACTIVE,
    SEED_STAFF_TYPES,
    SOURCE_REVISION,
    SOURCE_SCREEN,
    SOURCE_SEED,
    STAFF_GRADE_DESCRIPTION,
    UNKNOWN_GRADE_CODE,
    clean_value,
    did_you_mean,
    near_matches,
    sort_values,
    value_key,
)

_LABEL = {STAFF_GRADE_DESCRIPTION: "Staff Grade Description", GRADE_CODE: "Grade code"}


def _check_list_key(list_key: str) -> None:
    if list_key not in LIST_KEYS:
        raise AppError(
            code="UNKNOWN_LIST",
            message=f"Unknown list '{list_key}'. Lists: {', '.join(LIST_KEYS)}.",
            status_code=404,
        )


def _refuse_grade_edits(list_key: str) -> None:
    if list_key == GRADE_CODE:
        raise AppError(
            code=GRADE_FROM_REVISION_ONLY,
            message=(
                "Grade codes come from salary revisions: add a line for the grade to a salary "
                "revision instead."
            ),
            status_code=422,
        )


def _grade_not_listed(code: str) -> AppError:
    return AppError(
        code=UNKNOWN_GRADE_CODE,
        message=(
            f"Grade code '{code}' has no line in an active salary revision. "
            "Add it to a revision first."
        ),
        status_code=422,
        extra={"field": GRADE_CODE, "suggestions": []},
    )


def _clean_or_422(list_key: str, raw: str | None) -> str | None:
    try:
        return clean_value(list_key, raw)
    except InvalidGradeCodeError as exc:
        raise AppError(code=exc.code, message=str(exc), status_code=422) from exc


class LookupService:
    @staticmethod
    async def list_values(
        session: AsyncSession, list_key: str, include_inactive: bool = False
    ) -> list[LookupValue]:
        """List values, sorted (grades in natural order)."""
        _check_list_key(list_key)
        rows = await LookupRepository.list_values(session, list_key, include_inactive)
        order = {v: i for i, v in enumerate(sort_values(list_key, [r.value for r in rows]))}
        return sorted(rows, key=lambda r: order[r.value])

    @staticmethod
    async def active_values(session: AsyncSession, list_key: str) -> list[str]:
        return [r.value for r in await LookupService.list_values(session, list_key)]

    @staticmethod
    async def lists_for_import(session: AsyncSession) -> dict[str, dict[str, LookupValue]]:
        """Both lists keyed by ``value_key``, active and inactive, in one query."""
        out: dict[str, dict[str, LookupValue]] = {k: {} for k in LIST_KEYS}
        for row in await LookupRepository.list_all(session, LIST_KEYS):
            out[row.list_key][row.value_key] = row
        return out

    @staticmethod
    async def ensure_value(
        session: AsyncSession,
        list_key: str,
        raw: str | None,
        current: str | None = None,
    ) -> str | None:
        """Validate a value chosen on screen; returns the list's spelling.

        Blank -> None. A value equal to ``current`` (the record's value today) is always accepted,
        even if it was deactivated since; a new value must be active in the list.
        """
        _check_list_key(list_key)
        cleaned = _clean_or_422(list_key, raw)
        if cleaned is None:
            return None
        if current is not None and value_key(current) == value_key(cleaned):
            return current
        rows = await LookupRepository.list_values(session, list_key, include_inactive=True)
        by_key = {r.value_key: r for r in rows}
        row = by_key.get(value_key(cleaned))
        if list_key == GRADE_CODE and (row is None or not row.is_active):
            raise _grade_not_listed(cleaned)
        if row is None:
            hints = near_matches(list_key, cleaned, [r.value for r in rows if r.is_active])
            raise AppError(
                code=INVALID_STAFF_GRADE_DESCRIPTION,
                message=(
                    f"{_LABEL[list_key]} '{cleaned}' is not in the list.{did_you_mean(hints)} "
                    "An Admin can add it under Settings > Managed Lists."
                ),
                status_code=422,
                extra={"field": list_key, "suggestions": hints},
            )
        if not row.is_active:
            raise AppError(
                code=LOOKUP_VALUE_INACTIVE,
                message=f"{_LABEL[list_key]} '{row.value}' has been deactivated.",
                status_code=422,
                extra={"field": list_key},
            )
        return row.value

    @staticmethod
    async def add_value(
        session: AsyncSession,
        list_key: str,
        raw: str,
        confirm_near_match: bool,
        actor_user_id: UUID | None,
        actor_role: str | None,
        source: str = SOURCE_SCREEN,
    ) -> LookupValue:
        """Add a staff type (Admin, Settings): no duplicates; near matches need confirmation.

        Grade codes are refused: they come from salary revisions.
        """
        _check_list_key(list_key)
        _refuse_grade_edits(list_key)
        cleaned = _clean_or_422(list_key, raw)
        if cleaned is None:
            raise AppError(code="VALUE_REQUIRED", message="Enter a value.", status_code=422)
        rows = await LookupRepository.list_values(session, list_key, include_inactive=True)
        by_key = {r.value_key: r for r in rows}
        dup = by_key.get(value_key(cleaned))
        if dup is not None:
            state = "" if dup.is_active else " (deactivated: ask an Admin to reactivate it)"
            raise AppError(
                code=LOOKUP_DUPLICATE,
                message=f"'{dup.value}' is already in the list{state}.",
                status_code=409,
                extra={
                    "existing": dup.value,
                    "existing_id": str(dup.id),
                    "is_active": dup.is_active,
                },
            )
        if not confirm_near_match:
            hints = near_matches(list_key, cleaned, [r.value for r in rows if r.is_active])
            if hints:
                raise AppError(
                    code=LOOKUP_NEAR_MATCH,
                    message=f"Did you mean {hints[0]}? Choose it, or add '{cleaned}' anyway.",
                    status_code=422,
                    extra={"value": cleaned, "suggestions": hints},
                )
        row = LookupValue(
            list_key=list_key,
            value=cleaned,
            value_key=value_key(cleaned),
            source=source,
            created_by_user_id=actor_user_id,
        )
        session.add(row)
        await session.flush()
        await AuditService.log_action(
            session=session,
            action="LOOKUP_VALUE_ADDED",
            entity_type="lookup_value",
            entity_id=str(row.id),
            diff={"list_key": list_key, "value": cleaned, "source": source},
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
        return row

    @staticmethod
    async def set_active(
        session: AsyncSession,
        list_key: str,
        value_id: UUID,
        is_active: bool,
        version: int,
        actor_user_id: UUID | None,
        actor_role: str | None,
    ) -> LookupValue:
        """Deactivate or reactivate a staff type (Admin). Existing records keep their value."""
        _check_list_key(list_key)
        _refuse_grade_edits(list_key)
        row = await LookupRepository.get(session, list_key, value_id)
        if row is None:
            raise AppError(code="NOT_FOUND", message="Value not found.", status_code=404)
        if row.version != version:
            raise AppError(
                code="VERSION_CONFLICT",
                message="The value was changed by someone else. Reload and try again.",
                status_code=409,
            )
        if row.is_active == is_active:
            return row
        row.is_active = is_active
        row.deactivated_at = None if is_active else datetime.now(UTC)
        row.deactivated_by_user_id = None if is_active else actor_user_id
        row.version += 1
        await session.flush()
        await AuditService.log_action(
            session=session,
            action="LOOKUP_VALUE_REACTIVATED" if is_active else "LOOKUP_VALUE_DEACTIVATED",
            entity_type="lookup_value",
            entity_id=str(row.id),
            diff={"list_key": list_key, "value": row.value},
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
        return row

    @staticmethod
    async def sync_grades(
        session: AsyncSession,
        codes: Iterable[str],
        actor_user_id: UUID | None = None,
        actor_role: str | None = None,
    ) -> dict[str, list[str]]:
        """Make the active grade list exactly ``codes`` (base codes in ACTIVE revisions).

        Called by payroll after every change to salary revisions. Codes not in ``codes`` are
        deactivated (records keep them), returning codes are reactivated, new ones are added with
        source REVISION. Audited when anything changes. Returns what changed.
        """
        wanted = {value_key(c): c for c in codes}
        rows = await LookupRepository.list_values(session, GRADE_CODE, include_inactive=True)
        by_key = {r.value_key: r for r in rows}
        now = datetime.now(UTC)
        changes: dict[str, list[str]] = {"added": [], "reactivated": [], "deactivated": []}
        for key, code in wanted.items():
            row = by_key.get(key)
            if row is None:
                session.add(
                    LookupValue(
                        list_key=GRADE_CODE,
                        value=code,
                        value_key=key,
                        source=SOURCE_REVISION,
                        created_by_user_id=actor_user_id,
                    )
                )
                changes["added"].append(code)
            elif not row.is_active:
                row.is_active = True
                row.deactivated_at = None
                row.deactivated_by_user_id = None
                row.version += 1
                changes["reactivated"].append(row.value)
        for key, row in by_key.items():
            if key not in wanted and row.is_active:
                row.is_active = False
                row.deactivated_at = now
                row.deactivated_by_user_id = actor_user_id
                row.version += 1
                changes["deactivated"].append(row.value)
        if any(changes.values()):
            await session.flush()
            await AuditService.log_action(
                session=session,
                action="GRADE_LIST_SYNCED",
                entity_type="lookup_value",
                entity_id=GRADE_CODE,
                diff={k: sort_values(GRADE_CODE, v) for k, v in changes.items() if v},
                actor_user_id=actor_user_id,
                actor_role=actor_role,
            )
        return changes

    @staticmethod
    async def reseed(session: AsyncSession) -> int:
        """ "Reset database": clear both lists and re-seed the staff types. The grade list
        comes back with the next salary revision."""
        await LookupRepository.delete_all(session)
        for value in sort_values(STAFF_GRADE_DESCRIPTION, SEED_STAFF_TYPES):
            session.add(
                LookupValue(
                    list_key=STAFF_GRADE_DESCRIPTION,
                    value=value,
                    value_key=value_key(value),
                    source=SOURCE_SEED,
                )
            )
        await session.flush()
        return len(SEED_STAFF_TYPES)
