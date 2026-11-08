"""Pydantic schemas for alerts and notifications."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AlertResponse(BaseModel):
    """API representation of an alert."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    alert_type: str
    employee_id: UUID | None = None
    target_user_id: UUID | None = None
    target_role: str | None = None
    ref_type: str
    ref_id: UUID | None = None
    title: str
    message: str
    status: str
    details: dict[str, Any] = {}
    resolved_at: datetime | None = None
    created_at: datetime


class AlertResolveRequest(BaseModel):
    """Optional payload when resolving an alert."""

    note: str | None = None

