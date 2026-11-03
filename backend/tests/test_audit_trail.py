from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from fw.modules.audit.models import AuditLog
from fw.modules.audit.service import AuditService


@pytest.mark.asyncio
async def test_audit_service_log_action_records_entry() -> None:
    session = AsyncMock()
    actor_id = uuid4()

    entry = await AuditService.log_action(
        session=session,
        action="UPDATE_EMPLOYEE",
        entity_type="employee",
        entity_id="emp-123",
        diff={"name": {"old": "Old", "new": "New"}},
        actor_user_id=actor_id,
        actor_role="ADMIN",
        reason="Name correction",
        ip="127.0.0.1",
    )

    assert entry.action == "UPDATE_EMPLOYEE"
    assert entry.entity_type == "employee"
    assert entry.entity_id == "emp-123"
    assert entry.actor_user_id == actor_id
    assert entry.actor_role == "ADMIN"
    assert entry.diff == {"name": {"old": "Old", "new": "New"}}
    assert entry.reason == "Name correction"
    assert entry.ip == "127.0.0.1"

    session.add.assert_called_once_with(entry)
    session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_audit_service_list_logs_filter() -> None:
    session = AsyncMock()
    mock_log = AuditLog(
        id=1,
        actor_user_id=uuid4(),
        actor_role="ADMIN",
        action="CREATE_EMPLOYEE",
        entity_type="employee",
        entity_id="emp-456",
        diff={},
        created_at=datetime.now(UTC),
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_log]
    session.execute.return_value = mock_result

    logs = await AuditService.list_logs(session=session, entity_type="employee")
    assert len(logs) == 1
    assert logs[0].entity_id == "emp-456"

