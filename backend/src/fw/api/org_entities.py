from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.modules.identity import User, get_current_user, require_role
from fw.modules.org import (
    AccommodationCreate,
    AccommodationRead,
    AccommodationUpdate,
    GroupCreate,
    GroupRead,
    GroupUpdate,
    OrgService,
    ZoneCreate,
    ZoneRead,
    ZoneUpdate,
)

router = APIRouter(tags=["org_entities"])


# --- Groups ---
@router.get("/groups", response_model=list[GroupRead])
async def list_groups(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[GroupRead]:
    groups = await OrgService.list_groups(session)
    return [GroupRead.model_validate(g) for g in groups]


@router.post("/groups", response_model=GroupRead, status_code=201)
async def create_group(
    request: GroupCreate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> GroupRead:
    group = await OrgService.create_group(
        session, request, actor_user_id=current_user.id, actor_role=current_user.role
    )
    return GroupRead.model_validate(group)


@router.patch("/groups/{group_id}", response_model=GroupRead)
async def update_group(
    group_id: UUID,
    request: GroupUpdate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> GroupRead:
    group = await OrgService.update_group(
        session, group_id, request, actor_user_id=current_user.id, actor_role=current_user.role
    )
    return GroupRead.model_validate(group)


# --- Zones ---
@router.get("/zones", response_model=list[ZoneRead])
async def list_zones(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[ZoneRead]:
    zones = await OrgService.list_zones(session)
    return [ZoneRead.model_validate(z) for z in zones]


@router.post("/zones", response_model=ZoneRead, status_code=201)
async def create_zone(
    request: ZoneCreate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> ZoneRead:
    zone = await OrgService.create_zone(
        session, request, actor_user_id=current_user.id, actor_role=current_user.role
    )
    return ZoneRead.model_validate(zone)


@router.patch("/zones/{zone_id}", response_model=ZoneRead)
async def update_zone(
    zone_id: UUID,
    request: ZoneUpdate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> ZoneRead:
    zone = await OrgService.update_zone(
        session, zone_id, request, actor_user_id=current_user.id, actor_role=current_user.role
    )
    return ZoneRead.model_validate(zone)


# --- Accommodations ---
@router.get("/accommodations", response_model=list[AccommodationRead])
async def list_accommodations(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[AccommodationRead]:
    accs = await OrgService.list_accommodations(session)
    return [AccommodationRead.model_validate(a) for a in accs]


@router.post("/accommodations", response_model=AccommodationRead, status_code=201)
async def create_accommodation(
    request: AccommodationCreate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> AccommodationRead:
    acc = await OrgService.create_accommodation(
        session, request, actor_user_id=current_user.id, actor_role=current_user.role
    )
    return AccommodationRead.model_validate(acc)


@router.patch("/accommodations/{acc_id}", response_model=AccommodationRead)
async def update_accommodation(
    acc_id: UUID,
    request: AccommodationUpdate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> AccommodationRead:
    acc = await OrgService.update_accommodation(
        session, acc_id, request, actor_user_id=current_user.id, actor_role=current_user.role
    )
    return AccommodationRead.model_validate(acc)
