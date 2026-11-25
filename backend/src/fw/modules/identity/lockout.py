"""Login lockout after repeated wrong passwords (Batch 7, DEC-66).

Shared by the web login (`/auth/login`) and the mobile login (`/mobile/auth/login`):

- the lock is checked before the password, so a locked account never reveals whether a guess
  was right;
- each wrong password adds one to `users.failed_attempts`; at `login_max_failed_attempts`
  (default 5) the account is locked for `login_lockout_minutes` (default 15);
- a successful login resets the count; once a lock has expired the count starts again;
- an unknown user name costs the same password-hash work as a wrong password, so replies and
  timing don't reveal which accounts exist.

A failed login ends in an error, which rolls the request's transaction back, so the count and
the lock are committed here before the error is raised.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.clock import get_country_timezone
from fw.core.config import get_settings
from fw.core.errors import AppError
from fw.modules.identity.models import User

# identity sits beside audit in the layer contract, so the caller passes how to audit:
# (user, action, diff, reason).
AuditHook = Callable[[User, str, dict[str, Any], str], Awaitable[None]]


async def no_audit(user: User, action: str, diff: dict[str, Any], reason: str) -> None:
    """Default hook for callers (and unit tests) that don't audit."""


DEFAULT_MAX_FAILED_ATTEMPTS = 5
DEFAULT_LOCKOUT_MINUTES = 15
SETTING_MAX_FAILED_ATTEMPTS = "login_max_failed_attempts"
SETTING_LOCKOUT_MINUTES = "login_lockout_minutes"

_hasher = PasswordHasher()
_dummy_hash: str | None = None


@dataclass(frozen=True)
class LockoutPolicy:
    max_failed_attempts: int = DEFAULT_MAX_FAILED_ATTEMPTS
    lockout_minutes: int = DEFAULT_LOCKOUT_MINUTES

    @staticmethod
    def from_values(max_attempts: object, minutes: object) -> "LockoutPolicy":
        def as_int(value: object, default: int) -> int:
            try:
                number = int(value)  # type: ignore[call-overload]
            except (TypeError, ValueError):
                return default
            return number if number > 0 else default

        return LockoutPolicy(
            max_failed_attempts=as_int(max_attempts, DEFAULT_MAX_FAILED_ATTEMPTS),
            lockout_minutes=as_int(minutes, DEFAULT_LOCKOUT_MINUTES),
        )


def spend_password_check(password: str) -> None:
    """Verify against a throwaway hash so an unknown user takes as long as a wrong password."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = _hasher.hash("unknown-user-timing-equaliser")
    try:
        _hasher.verify(_dummy_hash, password)
    except VerificationError:
        pass


def _locked_error(user: User, policy: LockoutPolicy) -> AppError:
    locked_until = user.locked_until
    assert locked_until is not None
    if user.failed_attempts >= policy.max_failed_attempts:
        tz = get_country_timezone(get_settings().DEPLOYMENT_COUNTRY)
        local = locked_until.astimezone(tz)
        return AppError(
            code="ACCOUNT_LOCKED",
            message=(
                f"Too many failed sign-in attempts. Try again after {local:%H:%M} "
                f"({local:%d %b %Y}, site time) or ask Admin to unlock the account."
            ),
            status_code=403,
            extra={
                "reason": "TOO_MANY_ATTEMPTS",
                "locked_until": locked_until.isoformat(),
                "locked_until_local": local.strftime("%Y-%m-%d %H:%M"),
            },
        )
    return AppError(
        code="ACCOUNT_LOCKED",
        message="This account is locked. Please contact Admin.",
        status_code=403,
        extra={"reason": "LOCKED", "locked_until": locked_until.isoformat()},
    )


class LoginGuard:
    @staticmethod
    async def ensure_not_locked(
        session: AsyncSession, user: User, policy: LockoutPolicy, now: datetime
    ) -> None:
        """Raise ACCOUNT_LOCKED while locked. Before the password is checked."""
        if user.locked_until and user.locked_until > now:
            raise _locked_error(user, policy)
        if user.locked_until and user.failed_attempts >= policy.max_failed_attempts:
            # The lockout has run out: the count starts again.
            user.failed_attempts = 0
            user.locked_until = None
            await session.flush()

    @staticmethod
    async def record_failure(
        session: AsyncSession,
        user: User,
        policy: LockoutPolicy,
        now: datetime,
        channel: str,
        audit: AuditHook = no_audit,
    ) -> None:
        """Count a wrong password and commit it; raise ACCOUNT_LOCKED when this one locks."""
        user.failed_attempts = (user.failed_attempts or 0) + 1
        user.last_failed_login_at = now
        locked = user.failed_attempts >= policy.max_failed_attempts
        if locked:
            locked_until = now + timedelta(minutes=policy.lockout_minutes)
            user.locked_until = locked_until
            await audit(
                user,
                "LOCK_ACCOUNT",
                {
                    "failed_attempts": user.failed_attempts,
                    "locked_until": locked_until.isoformat(),
                    "channel": channel,
                },
                f"{user.failed_attempts} failed sign-in attempts ({channel})",
            )
        await session.flush()
        await session.commit()
        if locked:
            raise _locked_error(user, policy)

    @staticmethod
    def record_success(user: User) -> None:
        user.failed_attempts = 0
        user.last_failed_login_at = None

    @staticmethod
    async def lock_for_expired_default_password(
        session: AsyncSession,
        user: User,
        now: datetime,
        channel: str,
        audit: AuditHook = no_audit,
    ) -> AppError:
        """Lock (the existing 365-day lock), audit and commit; return the error to raise."""
        locked_until = now + timedelta(days=365)
        user.locked_until = locked_until
        await audit(
            user,
            "LOCK_ACCOUNT",
            {"locked_until": locked_until.isoformat(), "channel": channel},
            "Default password was not changed in time",
        )
        await session.flush()
        await session.commit()
        return AppError(
            code="ACCOUNT_LOCKED",
            message="Default password was not changed in time. Account is locked. Please contact Admin.",
            status_code=403,
            extra={
                "reason": "DEFAULT_PASSWORD_EXPIRED",
                "locked_until": locked_until.isoformat(),
            },
        )
