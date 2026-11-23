"""Managed lists (DEC-60, ADR-030): staff types and grade codes.

Here rather than in ``fw.modules.lookups`` because the list also shows values in use on
employees, job items and revision lines, which live in higher modules.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.modules.identity import User, get_current_user, require_role
from fw.modules.jobs import JobsService
from fw.modules.lookups import (
    LookupService,
    LookupValueCreate,
    LookupValueCreated,
    LookupValueRead,
    LookupValueUpdate,
    LookupWarning,
)
from fw.modules.org import OrgService
from fw.modules.payroll import PayrollService
from fw.rules.lookups import GRADE_CODE, NO_REVISION_LINE, sort_values, value_key

router = APIRouter(tags=["lookups"])


async def _in_use(session: AsyncSession, list_key: str) -> list[str]:
    if list_key == GRADE_CODE:
        return await PayrollService.list_grade_codes(session)
    return await OrgService.get_unique_staff_grades(session) + (
        await JobsService.get_unique_staff_grades(session)
    )


async def lookup_options(session: AsyncSession, list_key: str) -> list[str]:
    """Dropdown values: the active list plus any value in use that is not in the list at all."""
    rows = await LookupService.list_values(session, list_key, include_inactive=True)
    known = {r.value_key for r in rows}
    values = [r.value for r in rows if r.is_active]
    for v in await _in_use(session, list_key):
        if value_key(v) not in known:
            known.add(value_key(v))
            values.append(v)
    return sort_values(list_key, values)


@router.get("/lookups/{list_key}", response_model=list[LookupValueRead])
async def list_lookup_values(
    list_key: str,
    include_inactive: bool = Query(False),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[LookupValueRead]:
    """Values of a managed list (any signed-in role; codes and names only, no money).

    Values in use that are not in the list are appended with ``id`` null and source ``IN_USE``.
    """
    rows = await LookupService.list_values(session, list_key, include_inactive=True)
    out = [LookupValueRead.model_validate(r) for r in rows if include_inactive or r.is_active]
    known = {r.value_key for r in rows}
    extra = [v for v in await _in_use(session, list_key) if value_key(v) not in known]
    for v in sort_values(list_key, {value_key(v): v for v in extra}.values()):
        out.append(LookupValueRead(id=None, value=v, is_active=True, source="IN_USE"))
    order = {v: i for i, v in enumerate(sort_values(list_key, [o.value for o in out]))}
    return sorted(out, key=lambda o: order[o.value])


@router.post(
    "/lookups/{list_key}",
    response_model=LookupValueCreated,
    status_code=status.HTTP_201_CREATED,
)
async def add_lookup_value(
    list_key: str,
    payload: LookupValueCreate,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> LookupValueCreated:
    """Add a value ("Other – add new…"). Duplicates are refused; near matches need
    ``confirm_near_match``. A new grade without a line in an active revision gets a warning."""
    row = await LookupService.add_value(
        session,
        list_key,
        payload.value,
        payload.confirm_near_match,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    warnings: list[LookupWarning] = []
    if list_key == GRADE_CODE:
        country = payload.country.upper() if payload.country else None
        missing = await PayrollService.active_revisions_without_grade(session, row.value, country)
        if missing:
            warnings.append(
                LookupWarning(
                    code=NO_REVISION_LINE,
                    message=(
                        f"No line for {row.value} in revision {', '.join(missing)} yet: job items "
                        "with this grade are left out of the budget until the revision has one."
                    ),
                )
            )
    return LookupValueCreated(**LookupValueRead.model_validate(row).model_dump(), warnings=warnings)


@router.patch("/lookups/{list_key}/{value_id}", response_model=LookupValueRead)
async def update_lookup_value(
    list_key: str,
    value_id: UUID,
    payload: LookupValueUpdate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> LookupValueRead:
    """Deactivate or reactivate a value (Admin). Values are never deleted; records keep theirs."""
    row = await LookupService.set_active(
        session,
        list_key,
        value_id,
        payload.is_active,
        payload.version,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    return LookupValueRead.model_validate(row)
