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


@pytest.mark.asyncio
async def test_enrich_audit_logs_resolves_friendly_labels() -> None:
    from fw.api.audit import enrich_audit_logs

    session = AsyncMock()
    emp_id = uuid4()
    ji_id = uuid4()
    mock_log = AuditLog(
        id=10,
        actor_user_id=uuid4(),
        actor_role="ADMIN",
        action="CREATE",
        entity_type="StandingAssignment",
        entity_id=str(uuid4()),
        diff={"employee_id": str(emp_id), "job_item_id": str(ji_id)},
        created_at=datetime.now(UTC),
    )

    mock_emp_row = MagicMock()
    mock_emp_row.id = emp_id
    mock_emp_row.name = "Shanto Miah"
    mock_emp_row.tally_id = "1193"

    mock_ji_row = MagicMock()
    mock_ji_row.id = ji_id
    mock_ji_row.sub_item_code = "ITEM01"
    mock_ji_row.staff_grade_description = "Gardener"
    mock_ji_row.job_name = "Silicon Oasis"
    mock_ji_row.job_number = "12A14301"

    emp_result = MagicMock()
    emp_result.all.return_value = [mock_emp_row]
    ji_result = MagicMock()
    ji_result.all.return_value = [mock_ji_row]

    session.execute.side_effect = [emp_result, ji_result, MagicMock(all=lambda: [])]

    enriched = await enrich_audit_logs([mock_log], session)
    assert len(enriched) == 1
    assert enriched[0].diff_labels["employee_id"] == "Shanto Miah (1193)"
    assert enriched[0].diff_labels["job_item_id"] == "Silicon Oasis (12A14301) - Gardener"
    assert enriched[0].entity_label == "Shanto Miah (1193) @ Silicon Oasis (12A14301) - Gardener"
