import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.config import get_settings
from fw.core.errors import AppError
from fw.modules.identity.models import User, UserSession
from fw.modules.identity.schemas import LoginRequest, PasswordChangeRequest, UserUpdate
from fw.rules.password import is_default_password_expired, validate_password_strength

hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return hasher.verify(hashed, password)
    except VerifyMismatchError:
        return False


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthService:
    @staticmethod
    async def authenticate(
        session: AsyncSession,
        request: LoginRequest,
        default_password_max_days: int = 7,
    ) -> tuple[User, str, str]:
        """Authenticate user by username (tally_id) and password.

        Returns (user, access_token, raw_refresh_token).
        """
        settings = get_settings()
        now = datetime.now(UTC)

        # DEV-ONLY SHORTCUT (Development Phase Convenience):
        # In local environment only, submitting blank username & password logs in as active ADMIN.
        is_dev_blank_admin = (
            settings.APP_ENV == "local"
            and not request.username.strip()
            and not request.password.strip()
        )

        if is_dev_blank_admin:
            query = (
                select(User)
                .where(User.role == "ADMIN", User.is_active.is_(True))
                .order_by(User.created_at.asc())
            )
            result = await session.execute(query)
            user = result.scalar_one_or_none()
            if not user:
                raise AppError(
                    code="UNAUTHENTICATED",
                    message="No active ADMIN user found for dev blank login.",
                    status_code=401,
                )
        else:
            query = select(User).where(User.username == request.username)
            result = await session.execute(query)
            user = result.scalar_one_or_none()

            if not user or not verify_password(request.password, user.credential_hash):
                raise AppError(
                    code="UNAUTHENTICATED",
                    message="Invalid username or password.",
                    status_code=401,
                )

        if not user.is_active:
            raise AppError(
                code="ACCOUNT_INACTIVE",
                message="This account is deactivated.",
                status_code=403,
            )

        if user.locked_until and user.locked_until > now:
            raise AppError(
                code="ACCOUNT_LOCKED",
                message="This account is locked. Please contact Admin.",
                status_code=403,
            )

        # Check default password expiry
        if is_default_password_expired(
            user.must_change_password,
            user.created_at,
            now,
            max_days=default_password_max_days,
        ):
            # Lock the account
            user.locked_until = now + timedelta(days=365)
            await session.flush()
            raise AppError(
                code="ACCOUNT_LOCKED",
                message="Default password was not changed within the allowed timeframe. Account is locked.",
                status_code=403,
            )

        # Update last login
        user.last_login_at = now
        await session.flush()

        # Generate tokens
        access_token = AuthService.create_access_token(user)
        raw_refresh_token = secrets.token_urlsafe(32)
        refresh_session = UserSession(
            user_id=user.id,
            token_hash=_hash_token(raw_refresh_token),
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_DAYS),
        )
        session.add(refresh_session)
        await session.flush()

        return user, access_token, raw_refresh_token

    @staticmethod
    def create_access_token(user: User) -> str:
        settings = get_settings()
        now = datetime.now(UTC)
        payload = {
            "sub": str(user.id),
            "employee_id": str(user.employee_id),
            "username": user.username,
            "role": user.role,
            "must_change_password": user.must_change_password,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=settings.ACCESS_TOKEN_MINUTES)).timestamp()),
        }
        return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

    @staticmethod
    async def change_password(
        session: AsyncSession,
        user: User,
        request: PasswordChangeRequest,
        default_password: str = "ChangeMe123!",
    ) -> User:
        if not verify_password(request.current_password, user.credential_hash):
            raise AppError(
                code="INVALID_CURRENT_PASSWORD",
                message="Current password is incorrect.",
                status_code=400,
            )

        validate_password_strength(request.new_password, default_password=default_password)

        user.credential_hash = hash_password(request.new_password)
        user.must_change_password = False
        user.password_changed_at = datetime.now(UTC)
        user.locked_until = None
        user.version += 1
        await session.flush()

        return user

    @staticmethod
    async def refresh_tokens(
        session: AsyncSession,
        raw_refresh_token: str,
    ) -> tuple[User, str, str]:
        settings = get_settings()
        now = datetime.now(UTC)
        token_hash = _hash_token(raw_refresh_token)

        query = (
            select(UserSession, User)
            .join(User, UserSession.user_id == User.id)
            .where(UserSession.token_hash == token_hash)
        )
        result = await session.execute(query)
        row = result.first()

        if not row:
            raise AppError(code="INVALID_TOKEN", message="Session not found.", status_code=401)

        user_session, user = row
        if user_session.revoked_at is not None or user_session.expires_at < now:
            raise AppError(
                code="TOKEN_EXPIRED", message="Session expired or revoked.", status_code=401
            )

        if not user.is_active:
            raise AppError(code="ACCOUNT_INACTIVE", message="Account inactive.", status_code=403)

        # Revoke old session and rotate
        user_session.revoked_at = now

        new_raw_token = secrets.token_urlsafe(32)
        new_session = UserSession(
            user_id=user.id,
            token_hash=_hash_token(new_raw_token),
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_DAYS),
        )
        session.add(new_session)
        await session.flush()

        new_access_token = AuthService.create_access_token(user)
        return user, new_access_token, new_raw_token

    @staticmethod
    async def revoke_session(session: AsyncSession, raw_refresh_token: str) -> None:
        token_hash = _hash_token(raw_refresh_token)
        query = select(UserSession).where(UserSession.token_hash == token_hash)
        result = await session.execute(query)
        user_session = result.scalar_one_or_none()
        if user_session and user_session.revoked_at is None:
            user_session.revoked_at = datetime.now(UTC)
            await session.flush()


class UserService:
    @staticmethod
    async def list_users(
        session: AsyncSession,
        role: str | None = None,
        is_active: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[User]:
        query = select(User).order_by(User.username.asc())
        if role:
            query = query.where(User.role == role)
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        query = query.limit(limit).offset(offset)
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(session: AsyncSession, user_id: UUID) -> User | None:
        query = select(User).where(User.id == user_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_employee_id(session: AsyncSession, employee_id: UUID) -> User | None:
        query = select(User).where(User.employee_id == employee_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def update_user(
        session: AsyncSession,
        user_id: UUID,
        update_data: UserUpdate,
    ) -> tuple[User, dict[str, str | bool]]:
        user = await UserService.get_by_id(session, user_id)
        if not user:
            raise AppError(code="NOT_FOUND", message="User not found.", status_code=404)

        if user.version != update_data.version:
            raise AppError(
                code="VERSION_CONFLICT",
                message="User was modified concurrently.",
                status_code=409,
            )

        diff: dict[str, str | bool] = {}
        if update_data.role is not None and update_data.role != user.role:
            diff["role"] = f"{user.role} -> {update_data.role}"
            user.role = update_data.role
        if update_data.is_active is not None and update_data.is_active != user.is_active:
            diff["is_active"] = f"{user.is_active} -> {update_data.is_active}"
            user.is_active = update_data.is_active

        user.version += 1
        await session.flush()
        return user, diff

    @staticmethod
    async def reset_password_to_default(
        session: AsyncSession,
        user_id: UUID,
        default_password: str,
    ) -> User:
        """Admin resets user password back to company default and forces password change."""
        user = await UserService.get_by_id(session, user_id)
        if not user:
            raise AppError(code="NOT_FOUND", message="User not found.", status_code=404)

        user.credential_hash = hash_password(default_password)
        user.must_change_password = True
        user.password_changed_at = None
        user.locked_until = None
        user.failed_attempts = 0
        user.version += 1
        await session.flush()

        # Revoke all sessions
        sessions_query = select(UserSession).where(
            UserSession.user_id == user.id,
            UserSession.revoked_at.is_(None),
        )
        sessions_res = await session.execute(sessions_query)
        for s in sessions_res.scalars().all():
            s.revoked_at = datetime.now(UTC)
        await session.flush()
        return user
