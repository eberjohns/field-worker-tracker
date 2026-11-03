from dataclasses import dataclass
from typing import Any

import pytest

from fw.core.events import DomainEvent, EventBus


@dataclass
class EmployeeRegistered(DomainEvent):
    employee_id: str = "EMP-001"


@pytest.mark.asyncio
async def test_domain_event_bus():
    bus = EventBus()
    sync_called = []
    post_commit_called = []

    async def sync_handler(event: DomainEvent, session: Any) -> None:
        sync_called.append(event)

    async def post_commit_handler(event: DomainEvent) -> None:
        post_commit_called.append(event)

    bus.subscribe_sync(EmployeeRegistered, sync_handler)
    bus.subscribe_post_commit(EmployeeRegistered, post_commit_handler)

    event = EmployeeRegistered(employee_id="EMP-999")
    await bus.publish(event)
    assert len(sync_called) == 1
    assert sync_called[0].employee_id == "EMP-999"

    await bus.publish_post_commit(event)
    assert len(post_commit_called) == 1
    assert post_commit_called[0].employee_id == "EMP-999"
