from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from fw.core.errors import AppError
from fw.modules.identity.models import User, UserSession
from fw.modules.identity.service import UserService, verify_password


@pytest.mark.asyncio
async def test_admin_reset_password_to_default_success() -> None:
    session = AsyncMock()
    user_id = uuid4()
    emp_id = uuid4()

    mock_user = User(
        id=user_id,
        employee_id=emp_id,
        username="WRK001",
        credential_hash="some_old_hash",
        role="WORKER",
        is_active=True,
        must_change_password=False,
        password_changed_at=datetime.now(UTC),
        version=1,
    )

    mock_exec_result = MagicMock()
    mock_exec_result.scalar_one_or_none.return_value = mock_user

    mock_sessions_result = MagicMock()
    mock_sessions_result.scalars.return_value.all.return_value = [
        UserSession(user_id=user_id, token_hash="h1", expires_at=datetime.now(UTC))
    ]

    session.execute.side_effect = [mock_exec_result, mock_sessions_result]

    updated_user = await UserService.reset_password_to_default(
        session=session,
        user_id=user_id,
        default_password="DefaultPassword123!",
    )

    assert updated_user.must_change_password is True
    assert updated_user.password_changed_at is None
    assert updated_user.version == 2
    assert verify_password("DefaultPassword123!", updated_user.credential_hash)


@pytest.mark.asyncio
async def test_reset_password_user_not_found() -> None:
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    with pytest.raises(AppError) as exc:
        await UserService.reset_password_to_default(
            session=session,
            user_id=uuid4(),
            default_password="DefaultPassword123!",
        )
    assert exc.value.code == "NOT_FOUND"
    assert exc.value.status_code == 404
