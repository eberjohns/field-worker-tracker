"""Pydantic schemas for archive and retention operations."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ArchiveRecordResponse(BaseModel):
    """Schema for archive metadata response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    year: int
    file_name: str
    file_size_bytes: int
    sha256_checksum: str
    encryption_algo: str
    record_count: int
    status: str
    archived_at: datetime
    verified_at: datetime | None = None
    purged_at: datetime | None = None
    purged_record_count: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ArchiveTriggerRequest(BaseModel):
    """Request to generate yearly archive."""

    year: int = Field(..., ge=2020, le=2100, description="Calendar year to archive")
    purge_live_events: bool = Field(
        default=True,
        description="Whether to purge the archived raw events/visits from live database after verification",
    )


class ArchiveVerificationResult(BaseModel):
    """Response from verifying an archive package."""

    archive_id: UUID
    verified: bool
    record_count: int
    sha256_checksum: str
    message: str


class RetentionPurgeRequest(BaseModel):
    """Request parameters for retention cleanup jobs."""

    purge_sync_older_than_days: int = Field(
        default=60, ge=30, le=365, description="Retention for mobile sync changes (default 60 days)"
    )
    purge_notifications_older_than_months: int = Field(
        default=6, ge=1, le=24, description="Retention for notification logs (default 6 months)"
    )


class RetentionPurgeResult(BaseModel):
    """Summary of purged records from retention run."""

    sync_changes_purged: int
    notification_logs_purged: int
    stream_tickets_purged: int = 0
    completed_at: datetime


class AnonymisationRequest(BaseModel):
    """Request to run employee anonymisation."""

    older_than_years: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Minimum years since end of employment before anonymising (default 2 years)",
    )
    employee_ids: list[UUID] | None = Field(
        default=None, description="Optional specific list of employee IDs to anonymise"
    )


class AnonymisationResult(BaseModel):
    """Result summary of employee anonymisation."""

    anonymised_employees_count: int
    anonymised_employee_ids: list[UUID]
    completed_at: datetime
