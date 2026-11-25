from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BackgroundJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    status: str
    params: dict[str, Any]
    phase: str | None
    progress_done: int
    progress_total: int
    result: dict[str, Any] | None
    error_code: str | None
    error_message: str | None
    created_by_user_id: UUID | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
