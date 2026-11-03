from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.modules.audit import AuditService
from fw.modules.identity import (
    ResetPasswordResponse,
    User,
    UserRead,
    UserService,
    UserUpdate,
    require_role,
)
from fw.modules.settings import SettingsService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
async def list_users(
    role: str | None = None,
    is_active: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> list[UserRead]:
    users = await UserService.list_users(
        session=session,
        role=role,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return [UserRead.model_validate(u) for u in users]


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: UUID,
    request: UserUpdate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> UserRead:
    user, diff = await UserService.update_user(
        session=session,
        user_id=user_id,
        update_data=request,
    )
    if diff:
        await AuditService.log_action(
            session=session,
            action="UPDATE_USER",
            entity_type="user",
            entity_id=str(user.id),
            diff=diff,
            actor_user_id=current_user.id,
            actor_role=current_user.role,
        )
    return UserRead.model_validate(user)


@router.post("/{user_id}/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    user_id: UUID,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> ResetPasswordResponse:
    default_password = await SettingsService.get_setting(
        session,
        key="default_password",
        default="ChangeMe123!",
    )
    user = await UserService.reset_password_to_default(
        session=session,
        user_id=user_id,
        default_password=str(default_password),
    )
    await AuditService.log_action(
        session=session,
        action="RESET_PASSWORD",
        entity_type="user",
        entity_id=str(user.id),
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        reason="Admin reset password to company default",
    )
    return ResetPasswordResponse(
        message=f"User '{user.username}' password reset to company default.",
        must_change_password=True,
    )

