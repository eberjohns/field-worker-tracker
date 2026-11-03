from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.core.errors import AppError
from fw.modules.audit import AuditService
from fw.modules.identity import (
    AuthService,
    LoginRequest,
    PasswordChangeRequest,
    TokenResponse,
    User,
    UserRead,
    get_current_user,
)
from fw.modules.org import ScopeService
from fw.modules.settings import SettingsService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    # Resolve default_password_max_days from settings
    max_days = await SettingsService.get_setting(
        session,
        key="default_password_max_days",
        default=7,
    )
    user, access_token, raw_refresh_token = await AuthService.authenticate(
        session=session,
        request=request,
        default_password_max_days=int(max_days),
    )

    # Set httpOnly refresh cookie
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=30 * 86400,
    )

    await AuditService.log_action(
        session=session,
        action="LOGIN",
        entity_type="user",
        entity_id=str(user.id),
        actor_user_id=user.id,
        actor_role=user.role,
        reason="Web login successful",
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        must_change_password=user.must_change_password,
        user=UserRead.model_validate(user),
    )


@router.post("/change-password", response_model=UserRead)
async def change_password(
    request: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> UserRead:
    default_password = await SettingsService.get_setting(
        session,
        key="default_password",
        default="ChangeMe123!",
    )
    updated_user = await AuthService.change_password(
        session=session,
        user=current_user,
        request=request,
        default_password=str(default_password),
    )
    await AuditService.log_action(
        session=session,
        action="CHANGE_PASSWORD",
        entity_type="user",
        entity_id=str(updated_user.id),
        actor_user_id=updated_user.id,
        actor_role=updated_user.role,
        reason="User changed own password",
    )
    return UserRead.model_validate(updated_user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    response: Response,
    refresh_token: str | None = Cookie(None),
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    if not refresh_token:
        raise AppError(code="UNAUTHENTICATED", message="Missing refresh token cookie.", status_code=401)

    user, new_access_token, new_raw_refresh = await AuthService.refresh_tokens(
        session=session,
        raw_refresh_token=refresh_token,
    )

    response.set_cookie(
        key="refresh_token",
        value=new_raw_refresh,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=30 * 86400,
    )

    return TokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        must_change_password=user.must_change_password,
        user=UserRead.model_validate(user),
    )


@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    if refresh_token:
        await AuthService.revoke_session(session, refresh_token)
    response.delete_cookie(key="refresh_token")

    await AuditService.log_action(
        session=session,
        action="LOGOUT",
        entity_type="user",
        entity_id=str(current_user.id),
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    return {"message": "Successfully logged out."}


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
    return {
        "user": UserRead.model_validate(current_user),
        "scope": {
            "unrestricted": current_user.role == "ADMIN",
            "scoped_employee_count": len(scoped_ids) if scoped_ids is not None else "ALL",
        },
    }

