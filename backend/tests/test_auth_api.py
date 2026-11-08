from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from fw.core.errors import AppError
from fw.modules.identity.models import User
from fw.modules.identity.schemas import LoginRequest, PasswordChangeRequest
from fw.modules.identity.service import AuthService, hash_password


@pytest.mark.asyncio
async def test_auth_service_successful_login() -> None:
    session = AsyncMock()
    user_id = uuid4()
    emp_id = uuid4()
    password = "CorrectPassword123!"

    user = User(
        id=user_id,
        employee_id=emp_id,
        username="WRK001",
        credential_hash=hash_password(password),
        role="WORKER",
        is_active=True,
        must_change_password=True,
        created_at=datetime.now(UTC),
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    session.execute.return_value = mock_result

    req = LoginRequest(username="WRK001", password=password)
    authenticated_user, token, refresh_token = await AuthService.authenticate(
        session=session,
        request=req,
    )

    assert authenticated_user.username == "WRK001"
    assert authenticated_user.must_change_password is True
    assert token is not None
    assert refresh_token is not None


@pytest.mark.asyncio
async def test_auth_service_invalid_credentials_rejected() -> None:
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    req = LoginRequest(username="WRK001", password="WrongPassword!")
    with pytest.raises(AppError) as exc:
        await AuthService.authenticate(session=session, request=req)

    assert exc.value.code == "UNAUTHENTICATED"
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_auth_service_default_password_lock_after_max_days() -> None:
    session = AsyncMock()
    now = datetime.now(UTC)
    created_10_days_ago = now - timedelta(days=10)

    locked_user = User(
        id=uuid4(),
        employee_id=uuid4(),
        username="WRK002",
        credential_hash=hash_password("DefaultPass123!"),
        role="WORKER",
        is_active=True,
        must_change_password=True,
        created_at=created_10_days_ago,
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = locked_user
    session.execute.return_value = mock_result

    req = LoginRequest(username="WRK002", password="DefaultPass123!")
    with pytest.raises(AppError) as exc:
        await AuthService.authenticate(
            session=session,
            request=req,
            default_password_max_days=7,
        )

    assert exc.value.code == "ACCOUNT_LOCKED"
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_auth_service_change_password_clears_must_change_flag() -> None:
    session = AsyncMock()
    user = User(
        id=uuid4(),
        employee_id=uuid4(),
        username="WRK003",
        credential_hash=hash_password("OldPassword123!"),
        role="WORKER",
        is_active=True,
        must_change_password=True,
        version=1,
    )

    req = PasswordChangeRequest(
        current_password="OldPassword123!",
        new_password="BrandNewPassword123!",
    )

    updated_user = await AuthService.change_password(
        session=session,
        user=user,
        request=req,
        default_password="DefaultPass123!",
    )

    assert updated_user.must_change_password is False
    assert updated_user.password_changed_at is not None
    assert updated_user.version == 2


@pytest.mark.asyncio
async def test_auth_service_blank_credentials_logs_in_admin_in_local_env() -> None:
    session = AsyncMock()
    admin_id = uuid4()
    admin_user = User(
        id=admin_id,
        employee_id=uuid4(),
        username="ADMIN001",
        credential_hash=hash_password("AnySecret123!"),
        role="ADMIN",
        is_active=True,
        must_change_password=False,
        created_at=datetime.now(UTC),
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = admin_user
    session.execute.return_value = mock_result

    req = LoginRequest(username="", password="")
    authenticated_user, token, refresh_token = await AuthService.authenticate(
        session=session,
        request=req,
    )

    assert authenticated_user.username == "ADMIN001"
    assert authenticated_user.role == "ADMIN"
    assert token is not None
    assert refresh_token is not None


@pytest.mark.asyncio
async def test_auth_service_blank_credentials_rejected_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fw.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "APP_ENV", "production")

    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    req = LoginRequest(username="", password="")
    with pytest.raises(AppError) as exc:
        await AuthService.authenticate(session=session, request=req)

    assert exc.value.code == "UNAUTHENTICATED"
    assert exc.value.status_code == 401
