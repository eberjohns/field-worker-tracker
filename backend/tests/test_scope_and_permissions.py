from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from fw.core.errors import AppError
from fw.modules.identity.models import User
from fw.modules.org.models import EmployeeReportingLine
from fw.modules.org.service import OrgService, ScopeService


@pytest.mark.asyncio
async def test_admin_has_unrestricted_scope() -> None:
    session = AsyncMock()
    admin_user = User(
        id=uuid4(),
        employee_id=uuid4(),
        username="ADMIN001",
        role="ADMIN",
        credential_hash="hash",
    )

    scope = await ScopeService.get_scoped_employee_ids(session, admin_user)
    assert scope is None  # None signifies unrestricted access to all


@pytest.mark.asyncio
async def test_worker_scope_limited_to_self() -> None:
    session = AsyncMock()
    worker_emp_id = uuid4()
    worker_user = User(
        id=uuid4(),
        employee_id=worker_emp_id,
        username="WRK001",
        role="WORKER",
        credential_hash="hash",
    )

    scope = await ScopeService.get_scoped_employee_ids(session, worker_user)
    assert scope == {worker_emp_id}


@pytest.mark.asyncio
async def test_supervisor_and_engineer_transitive_scope() -> None:
    session = AsyncMock()
    engineer_emp_id = uuid4()
    supervisor_emp_id = uuid4()
    worker1_emp_id = uuid4()
    worker2_emp_id = uuid4()

    engineer_user = User(
        id=uuid4(),
        employee_id=engineer_emp_id,
        username="ENG001",
        role="ENGINEER",
        credential_hash="hash",
    )
    supervisor_user = User(
        id=uuid4(),
        employee_id=supervisor_emp_id,
        username="SUP001",
        role="SUPERVISOR",
        credential_hash="hash",
    )

    # Reporting chain: Supervisor reports to Engineer; Workers report to Supervisor
    lines = [
        EmployeeReportingLine(
            employee_id=supervisor_emp_id,
            manager_id=engineer_emp_id,
            relationship="ENGINEER",
        ),
        EmployeeReportingLine(
            employee_id=worker1_emp_id,
            manager_id=supervisor_emp_id,
            relationship="SUPERVISOR",
        ),
        EmployeeReportingLine(
            employee_id=worker2_emp_id,
            manager_id=supervisor_emp_id,
            relationship="SUPERVISOR",
        ),
    ]

    mock_result = MagicMock()
    mock_result.all.return_value = lines
    session.execute.return_value = mock_result

    # Engineer scope includes self, supervisor, and all workers
    eng_scope = await ScopeService.get_scoped_employee_ids(session, engineer_user)
    assert eng_scope == {engineer_emp_id, supervisor_emp_id, worker1_emp_id, worker2_emp_id}

    # Supervisor scope includes self and their direct workers
    sup_scope = await ScopeService.get_scoped_employee_ids(session, supervisor_user)
    assert sup_scope == {supervisor_emp_id, worker1_emp_id, worker2_emp_id}


@pytest.mark.asyncio
async def test_out_of_scope_access_raises_forbidden() -> None:
    session = AsyncMock()
    scoped_ids = {uuid4()}
    unauthorized_emp_id = uuid4()

    with pytest.raises(AppError) as exc:
        await OrgService.get_employee(
            session=session,
            employee_id=unauthorized_emp_id,
            scoped_ids=scoped_ids,
        )

    assert exc.value.code == "OUT_OF_SCOPE"
    assert exc.value.status_code == 403
