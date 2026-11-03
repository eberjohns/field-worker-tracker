"""Pydantic schemas for bulk imports, row-level diffs, and preview/commit states."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ImportBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    filename: str
    file_hash: str
    template_version: str
    uploaded_by_user_id: UUID
    status: str
    summary: dict[str, Any] = Field(default_factory=dict)
    committed_at: datetime | None = None
    created_at: datetime


class ImportRowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_id: UUID
    sheet: str
    row_number: int
    natural_key: str
    action: str  # NEW, UPDATED, UNCHANGED, REACTIVATED, CLASH, ERROR, SKIPPED
    status: str  # OK, WARNING, ERROR, INFO
    codes: list[str] = Field(default_factory=list)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    diff: dict[str, Any] = Field(default_factory=dict)
    normalized: dict[str, Any] = Field(default_factory=dict)


class ImportPreviewResponse(BaseModel):
    batch_id: UUID
    filename: str
    template_version: str
    status: str
    can_commit: bool
    summary: dict[str, Any] = Field(default_factory=dict)
    rows: list[ImportRowRead] = Field(default_factory=list)


class ImportCommitResponse(BaseModel):
    batch_id: UUID
    status: str
    committed_at: datetime
    summary: dict[str, Any] = Field(default_factory=dict)


class ImportRollbackResponse(BaseModel):
    batch_id: UUID
    status: str
    summary: dict[str, Any] = Field(default_factory=dict)
