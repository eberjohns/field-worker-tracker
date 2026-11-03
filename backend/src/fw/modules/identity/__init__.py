"""Public interface for identity module."""

from fw.modules.identity.dependencies import get_current_user, require_role
from fw.modules.identity.models import User, UserSession
from fw.modules.identity.schemas import (
    LoginRequest,
    PasswordChangeRequest,
    ResetPasswordResponse,
    TokenResponse,
    UserRead,
    UserUpdate,
)
from fw.modules.identity.service import AuthService, UserService, hash_password, verify_password

__all__ = [
    "AuthService",
    "LoginRequest",
    "PasswordChangeRequest",
    "ResetPasswordResponse",
    "TokenResponse",
    "User",
    "UserRead",
    "UserSession",
    "UserService",
    "UserUpdate",
    "get_current_user",
    "hash_password",
    "require_role",
    "verify_password",
]
