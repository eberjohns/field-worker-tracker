"""Public interface for archive and retention module."""

from fw.modules.archive.api import archive_router, retention_router
from fw.modules.archive.models import ArchiveRecord
from fw.modules.archive.schemas import (
    AnonymisationRequest,
    AnonymisationResult,
    ArchiveRecordResponse,
    ArchiveTriggerRequest,
    ArchiveVerificationResult,
    RetentionPurgeRequest,
    RetentionPurgeResult,
)
from fw.modules.archive.service import ArchiveService

__all__ = [
    "AnonymisationRequest",
    "AnonymisationResult",
    "ArchiveRecord",
    "ArchiveRecordResponse",
    "ArchiveService",
    "ArchiveTriggerRequest",
    "ArchiveVerificationResult",
    "RetentionPurgeRequest",
    "RetentionPurgeResult",
    "archive_router",
    "retention_router",
]

