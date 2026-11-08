from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.modules.identity import User, require_role
from fw.modules.sync.schemas import DeviceStatusRead
from fw.modules.sync.service import SyncService

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=list[DeviceStatusRead])
async def list_devices(
    _current_user: User = Depends(require_role("ADMIN", "ENGINEER", "SUPERINTENDENT")),
    session: AsyncSession = Depends(get_db),
) -> list[DeviceStatusRead]:
    """List all registered devices with their sync lag and client versions."""
    return await SyncService.list_devices_status(session=session)


@router.post("/{device_id}/reset")
@router.post("/{device_id}/revoke")
async def reset_device_binding(
    device_id: UUID,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Admin resets or revokes a device binding so a worker can bind a new device on next login."""
    device = await SyncService.reset_device_binding(
        session=session,
        device_id=device_id,
        admin_user_id=current_user.id,
    )
    return {
        "status": "DEVICE_RESET",
        "id": str(device.id),
        "device_id": str(device.id),
        "employee_id": str(device.employee_id),
        "is_active": device.is_active,
    }
