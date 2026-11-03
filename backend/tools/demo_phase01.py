"""Phase 01 Demo Script.

Verifies:
1. Log in as Admin.
2. Create a worker with two superintendents and one supervisor (DEC-10).
3. Log in as the supervisor and see only their team (scope isolation).
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fw.modules.identity.models import User
from fw.modules.identity.schemas import LoginRequest
from fw.modules.identity.service import AuthService, hash_password
from fw.modules.org.models import EmployeeReportingLine
from fw.modules.org.schemas import ReportingLineCreate
from fw.modules.org.service import OrgService, ScopeService


async def run_demo() -> None:
    print("=" * 60)
    print("PHASE 01 DEMO SCRIPT")
    print("=" * 60)

    session = AsyncMock()
    now = datetime.now(UTC)

    # 1. Log in as Admin
    admin_emp_id = uuid4()
    admin_user_id = uuid4()
    admin_user = User(
        id=admin_user_id,
        employee_id=admin_emp_id,
        username="ADMIN001",
        credential_hash=hash_password("AdminPass123!"),
        role="ADMIN",
        is_active=True,
        must_change_password=False,
        created_at=now,
    )

    mock_res_admin = MagicMock()
    mock_res_admin.scalar_one_or_none.return_value = admin_user
    session.execute.return_value = mock_res_admin

    print("[Step 1] Logging in as Admin (username: ADMIN001)...")
    auth_admin, token, _ = await AuthService.authenticate(
        session=session,
        request=LoginRequest(username="ADMIN001", password="AdminPass123!"),
    )
    print(f" -> Logged in successfully as {auth_admin.username} (Role: {auth_admin.role})")
    assert auth_admin.role == "ADMIN"

    # 2. Setup Supervisor, Superintendents, and Worker
    supt1_id = uuid4()
    supt2_id = uuid4()
    sup1_id = uuid4()
    worker_id = uuid4()

    # 3. Create links: Worker with TWO Superintendents and ONE Supervisor (DEC-10)
    print("\n[Step 2] Creating Worker with 1 Supervisor and 2 Superintendents (DEC-10)...")
    mock_all_lines = MagicMock()
    mock_all_lines.all.return_value = []
    session.execute.return_value = mock_all_lines

    await OrgService.add_reporting_line(
        session=session,
        employee_id=worker_id,
        data=ReportingLineCreate(manager_id=sup1_id, relationship="SUPERVISOR"),
        actor_user_id=admin_user_id,
        actor_role="ADMIN",
    )
    print(f" -> Assigned Supervisor link: manager={sup1_id} (rel=SUPERVISOR)")

    await OrgService.add_reporting_line(
        session=session,
        employee_id=worker_id,
        data=ReportingLineCreate(manager_id=supt1_id, relationship="SUPERINTENDENT"),
        actor_user_id=admin_user_id,
        actor_role="ADMIN",
    )
    print(f" -> Assigned 1st Superintendent link: manager={supt1_id} (rel=SUPERINTENDENT)")

    await OrgService.add_reporting_line(
        session=session,
        employee_id=worker_id,
        data=ReportingLineCreate(manager_id=supt2_id, relationship="SUPERINTENDENT"),
        actor_user_id=admin_user_id,
        actor_role="ADMIN",
    )
    print(f" -> Assigned 2nd Superintendent link: manager={supt2_id} (rel=SUPERINTENDENT)")

    # 4. Log in as Supervisor
    print("\n[Step 3] Logging in as Supervisor (username: SUP001)...")
    sup_user = User(
        id=uuid4(),
        employee_id=sup1_id,
        username="SUP001",
        credential_hash=hash_password("SupPass123!"),
        role="SUPERVISOR",
        is_active=True,
        must_change_password=False,
        created_at=now,
    )

    mock_res_sup = MagicMock()
    mock_res_sup.scalar_one_or_none.return_value = sup_user
    session.execute.return_value = mock_res_sup

    auth_sup, _, _ = await AuthService.authenticate(
        session=session,
        request=LoginRequest(username="SUP001", password="SupPass123!"),
    )
    print(f" -> Logged in successfully as {auth_sup.username} (Role: {auth_sup.role})")

    # 5. Resolve Supervisor's scope
    print("\n[Step 4] Checking Supervisor's reporting scope...")
    unrelated_worker_id = uuid4()
    active_lines = [
        EmployeeReportingLine(employee_id=worker_id, manager_id=sup1_id, relationship="SUPERVISOR"),
        EmployeeReportingLine(
            employee_id=unrelated_worker_id, manager_id=uuid4(), relationship="SUPERVISOR"
        ),
    ]

    mock_rep_lines = MagicMock()
    mock_rep_lines.all.return_value = active_lines
    session.execute.return_value = mock_rep_lines

    scoped_ids = await ScopeService.get_scoped_employee_ids(session, sup_user)
    print(f" -> Scoped Employee IDs for Supervisor: {scoped_ids}")

    assert scoped_ids is not None
    assert worker_id in scoped_ids, "Worker WRK999 MUST be in Supervisor's scope"
    assert unrelated_worker_id not in scoped_ids, (
        "Unrelated worker MUST NOT be in Supervisor's scope"
    )
    print(
        " -> SUCCESS: Supervisor sees ONLY their own team (WRK999) and cannot see unrelated workers!"
    )
    print("\n" + "=" * 60)
    print("ALL DEMO CHECKS PASSED PERFECTLY!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_demo())
