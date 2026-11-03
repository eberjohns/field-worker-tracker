from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4


@dataclass
class AuditEntry:
    actor_id: str
    action: str
    entity_type: str
    entity_id: str
    diff: dict[str, Any]
    reason: str | None = None
    id: UUID = uuid4()
    created_at: datetime = datetime.now(UTC)


class AuditLogger(Protocol):
    """Protocol for recording state changes in the audit log."""

    async def record(self, entry: AuditEntry, session: Any = None) -> None:
        """Record an audit entry within the current transaction."""
        ...
