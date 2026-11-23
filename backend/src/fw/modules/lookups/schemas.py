from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LookupValueRead(BaseModel):
    """One managed-list value. ``id`` is None for a value in use that is not in the list."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID | None = None
    value: str
    is_active: bool = True
    source: str = "SEED"
    version: int | None = None
    created_at: datetime | None = None


class LookupValueCreate(BaseModel):
    value: str = Field(..., min_length=1, max_length=100)
    confirm_near_match: bool = Field(
        False, description="Add even though a near match or known alias exists ('Add anyway')."
    )


class LookupValueUpdate(BaseModel):
    is_active: bool
    version: int
