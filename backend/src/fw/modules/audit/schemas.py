from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditLogCreate(BaseModel):
    actor_user_id: UUID | None = None
    actor_role: str | None = None
    action: str
    entity_type: str
    entity_id: str
    diff: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None
    ip: str | None = None


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: UUID | None = None
    actor_role: str | None = None
    actor_name: str | None = None
    action: str
    entity_type: str
    entity_id: str
    entity_label: str | None = None
    diff: dict[str, Any]
    diff_labels: dict[str, str] = Field(default_factory=dict)
    reason: str | None = None
    ip: str | None = None
    created_at: datetime
