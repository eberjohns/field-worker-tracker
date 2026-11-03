from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from fw.core.errors import AppError
from fw.modules.identity.models import User
from fw.modules.identity.schemas import UserUpdate
from fw.modules.identity.service import UserService
from fw.modules.org.models import Employee
from fw.modules.org.schemas import EmployeeUpdate
from fw.modules.org.service import OrgService


@pytest.mark.asyncio
async def test_employee_update_optimistic_locking_conflict() -> None:
    session = AsyncMock()
    emp_id = uuid4()

    mock_employee = Employee(
        id=emp_id,
        tally_id="WRK001",
        name="Old Name",
        role="WORKER",
        version=2,  # Current version in DB is 2
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_employee
    session.execute.return_value = mock_result

    # Client sends stale version 1
    update_data = EmployeeUpdate(name="New Name", version=1)

    with pytest.raises(AppError) as exc:
        await OrgService.update_employee(
            session=session,
            employee_id=emp_id,
            data=update_data,
            scoped_ids=None,
            actor_user_id=uuid4(),
            actor_role="ADMIN",
        )

    assert exc.value.code == "VERSION_CONFLICT"
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_user_update_optimistic_locking_conflict() -> None:
    session = AsyncMock()
    user_id = uuid4()

    mock_user = User(
        id=user_id,
        employee_id=uuid4(),
        username="WRK001",
        credential_hash="hash",
        role="WORKER",
        version=3,
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    session.execute.return_value = mock_result

    # Client sends stale version 2
    update_data = UserUpdate(role="SUPERVISOR", version=2)

    with pytest.raises(AppError) as exc:
        await UserService.update_user(
            session=session,
            user_id=user_id,
            update_data=update_data,
        )

    assert exc.value.code == "VERSION_CONFLICT"
    assert exc.value.status_code == 409
