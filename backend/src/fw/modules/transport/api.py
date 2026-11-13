from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.modules.identity import User, require_role
from fw.modules.transport.schemas import (
    CopyRunsRequest,
    CopyRunsResponse,
    DriverRead,
    PublishRunResponse,
    SuggestRunsRequest,
    SuggestRunsResponse,
    TransportRunCreate,
    TransportRunRead,
    TransportRunUpdate,
    UnassignedWorkerRead,
    VehicleCreate,
    VehicleRead,
    VehicleUpdate,
)
from fw.modules.transport.service import TransportService

router = APIRouter(tags=["transport"])
service = TransportService()

READ_ROLES = ["ADMIN", "ENGINEER", "SUPERVISOR", "SUPERINTENDENT"]
WRITE_ROLES = ["ADMIN", "ENGINEER", "SUPERVISOR"]


# -----------------------------------------------------------------------------
# Vehicles
# -----------------------------------------------------------------------------
@router.get("/vehicles", response_model=list[VehicleRead])
async def list_vehicles(
    active_only: bool = True,
    current_user: User = Depends(require_role(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> list[VehicleRead]:
    return await service.list_vehicles(session, active_only=active_only)


@router.post("/vehicles", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
async def create_vehicle(
    data: VehicleCreate,
    current_user: User = Depends(require_role(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> VehicleRead:
    return await service.create_vehicle(session, data, actor_user_id=current_user.id)


@router.patch("/vehicles/{vehicle_id}", response_model=VehicleRead)
async def update_vehicle(
    vehicle_id: UUID,
    data: VehicleUpdate,
    current_user: User = Depends(require_role(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> VehicleRead:
    return await service.update_vehicle(session, vehicle_id, data, actor_user_id=current_user.id)


# -----------------------------------------------------------------------------
# Drivers
# -----------------------------------------------------------------------------
@router.get("/drivers", response_model=list[DriverRead])
async def list_drivers(
    week_start: date | None = None,
    current_user: User = Depends(require_role(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> list[DriverRead]:
    return await service.list_drivers(session, week_start=week_start)


# -----------------------------------------------------------------------------
# Transport Runs Actions (Must be defined before /{run_id})
# -----------------------------------------------------------------------------
@router.get("/transport-runs/unassigned-workers", response_model=list[UnassignedWorkerRead])
async def list_unassigned_workers(
    run_date: date = Query(..., description="Target work date"),
    direction: str = Query("MORNING", pattern="^(MORNING|EVENING)$"),
    current_user: User = Depends(require_role(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> list[UnassignedWorkerRead]:
    return await service.list_unassigned_workers(session, run_date=run_date, direction=direction)


@router.post("/transport-runs/suggest", response_model=SuggestRunsResponse)
async def suggest_runs(
    request: SuggestRunsRequest,
    current_user: User = Depends(require_role(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> SuggestRunsResponse:
    return await service.suggest_runs(session, request, actor_user_id=current_user.id)


@router.post("/transport-runs/copy", response_model=CopyRunsResponse)
async def copy_runs(
    request: CopyRunsRequest,
    current_user: User = Depends(require_role(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> CopyRunsResponse:
    return await service.copy_runs(session, request, actor_user_id=current_user.id)


# -----------------------------------------------------------------------------
# Transport Runs CRUD
# -----------------------------------------------------------------------------
@router.get("/transport-runs", response_model=list[TransportRunRead])
async def list_runs(
    run_date: date = Query(..., description="Target run date"),
    direction: str | None = Query(None, pattern="^(MORNING|EVENING)$"),
    current_user: User = Depends(require_role(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> list[TransportRunRead]:
    return await service.list_runs(session, run_date=run_date, direction=direction)


@router.post(
    "/transport-runs", response_model=TransportRunRead, status_code=status.HTTP_201_CREATED
)
async def create_run(
    data: TransportRunCreate,
    current_user: User = Depends(require_role(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> TransportRunRead:
    return await service.create_run(session, data, actor_user_id=current_user.id)


@router.get("/transport-runs/{run_id}", response_model=TransportRunRead)
async def get_run(
    run_id: UUID,
    current_user: User = Depends(require_role(*READ_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> TransportRunRead:
    return await service.get_run(session, run_id)


@router.patch("/transport-runs/{run_id}", response_model=TransportRunRead)
async def update_run(
    run_id: UUID,
    data: TransportRunUpdate,
    current_user: User = Depends(require_role(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> TransportRunRead:
    return await service.update_run(session, run_id, data, actor_user_id=current_user.id)


@router.delete("/transport-runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run(
    run_id: UUID,
    current_user: User = Depends(require_role(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_run(session, run_id, actor_user_id=current_user.id)


@router.post("/transport-runs/{run_id}/publish", response_model=PublishRunResponse)
async def publish_run(
    run_id: UUID,
    current_user: User = Depends(require_role(*WRITE_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> PublishRunResponse:
    return await service.publish_run(session, run_id, actor_user_id=current_user.id)
