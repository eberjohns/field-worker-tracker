"""Public interface for identity module."""

from fw.modules.identity.dependencies import get_current_user, require_role
from fw.modules.identity.lockout import (
    SETTING_LOCKOUT_MINUTES,
    SETTING_MAX_FAILED_ATTEMPTS,
    AuditHook,
    LockoutPolicy,
    LoginGuard,
    spend_password_check,
)
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
    "SETTING_LOCKOUT_MINUTES",
    "SETTING_MAX_FAILED_ATTEMPTS",
    "AuditHook",
    "AuthService",
    "LockoutPolicy",
    "LoginGuard",
    "spend_password_check",
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
