from collections.abc import Callable
from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.config import get_settings
from fw.core.db import get_db
from fw.core.errors import AppError
from fw.modules.identity.models import User
from fw.modules.identity.service import UserService


async def get_current_user(
    authorization: str | None = Header(None),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Validate Bearer token and return current authenticated User."""
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError(
            code="UNAUTHENTICATED",
            message="Missing or invalid Authorization header.",
            status_code=401,
        )

    token = authorization.split(" ", 1)[1]
    settings = get_settings()

    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"],
        )
    except jwt.PyJWTError as err:
        raise AppError(
            code="INVALID_TOKEN",
            message="Token is invalid or expired.",
            status_code=401,
        ) from err

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise AppError(
            code="INVALID_TOKEN",
            message="Invalid token payload.",
            status_code=401,
        )

    user = await UserService.get_by_id(session, UUID(user_id_str))
    if not user:
        raise AppError(code="USER_NOT_FOUND", message="User not found.", status_code=401)

    if not user.is_active:
        raise AppError(code="ACCOUNT_INACTIVE", message="Account inactive.", status_code=403)

    return user


def require_role(*allowed_roles: str) -> Callable[..., Any]:
    """Dependency factory checking that the current user possesses one of allowed_roles."""

    async def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise AppError(
                code="FORBIDDEN",
                message=f"Role '{user.role}' is not authorized to perform this action.",
                status_code=403,
            )
        return user

    return role_checker
