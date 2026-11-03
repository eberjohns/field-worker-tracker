from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.modules.identity import User, require_role
from fw.modules.org import OrgService, RegisteredDeviceRead

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("/{device_id}/revoke", response_model=RegisteredDeviceRead)
async def revoke_device(
    device_id: UUID,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> RegisteredDeviceRead:
    device = await OrgService.revoke_device(
        session=session,
        device_id=device_id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    return RegisteredDeviceRead.model_validate(device)
