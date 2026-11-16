"""Admin API endpoints for yearly archive viewer, downloads, integrity checks, and retention."""

import asyncio
import os
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.core.errors import AppError
from fw.modules.archive.models import ArchiveRecord
from fw.modules.archive.repository import ArchiveRepository
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
from fw.modules.identity import User, require_role

archive_router = APIRouter(prefix="/admin/archives", tags=["admin-archive"])
retention_router = APIRouter(prefix="/admin/retention", tags=["admin-retention"])


# --- ARCHIVES ---


@archive_router.get("", response_model=list[ArchiveRecordResponse])
async def list_archives(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> list[ArchiveRecord]:
    """List yearly archive records with SHA-256 checksums, encryption algorithm, and status."""
    return await ArchiveRepository.list_archives(session, limit=limit, offset=offset)


@archive_router.post("/generate", response_model=ArchiveRecordResponse)
async def generate_archive(
    req: ArchiveTriggerRequest,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> ArchiveRecord:
    """Trigger yearly data archive, compute SHA-256, encrypt with AES-256-GCM, and optionally purge live records."""
    return await ArchiveService.create_yearly_archive(
        session=session,
        year=req.year,
        purge_live_events=req.purge_live_events,
        actor_id=current_user.id,
    )


@archive_router.get("/{archive_id}", response_model=ArchiveRecordResponse)
async def get_archive_record(
    archive_id: UUID,
    _user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> ArchiveRecord:
    """Retrieve details for a single archive record."""
    record = await ArchiveRepository.get_by_id(session, archive_id)
    if not record:
        raise AppError(
            code="ARCHIVE_NOT_FOUND", message="Archive record not found.", status_code=404
        )
    return record


@archive_router.get("/{archive_id}/download")
async def download_encrypted_archive(
    archive_id: UUID,
    _user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download the encrypted yearly archive file with integrity headers."""
    record = await ArchiveRepository.get_by_id(session, archive_id)
    if not record:
        raise AppError(
            code="ARCHIVE_NOT_FOUND", message="Archive record not found.", status_code=404
        )

    file_exists = await asyncio.to_thread(os.path.exists, record.file_path)
    if not file_exists:
        raise AppError(
            code="ARCHIVE_FILE_MISSING",
            message=f"Archive file {record.file_name} not found on server.",
            status_code=404,
        )

    headers = {
        "X-Checksum-SHA256": record.sha256_checksum,
        "X-Encryption-Algo": record.encryption_algo,
        "Content-Disposition": f'attachment; filename="{record.file_name}"',
    }
    return FileResponse(
        path=record.file_path,
        media_type="application/octet-stream",
        filename=record.file_name,
        headers=headers,
    )


@archive_router.post("/{archive_id}/verify", response_model=ArchiveVerificationResult)
async def verify_archive_integrity(
    archive_id: UUID,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> ArchiveVerificationResult:
    """Verify archive SHA-256 checksum and sample decryption to ensure file is uncorrupted and recoverable."""
    return await ArchiveService.verify_archive(
        session=session,
        archive_id=archive_id,
        actor_id=current_user.id,
    )


# --- RETENTION & ANONYMISATION ---


@retention_router.post("/run", response_model=RetentionPurgeResult)
async def run_retention_purge(
    req: RetentionPurgeRequest,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> RetentionPurgeResult:
    """Execute scheduled retention cleanup: purge sync_changes (>60d) and notifications (>6mo)."""
    return await ArchiveService.run_retention_purge(
        session=session,
        sync_days=req.purge_sync_older_than_days,
        notif_months=req.purge_notifications_older_than_months,
        actor_id=current_user.id,
    )


@retention_router.post("/anonymise", response_model=AnonymisationResult)
async def run_employee_anonymisation(
    req: AnonymisationRequest,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> AnonymisationResult:
    """Anonymise workers whose employment ended past the statutory retention window (default 2 years)."""
    return await ArchiveService.anonymise_expired_employees(
        session=session,
        older_than_years=req.older_than_years,
        employee_ids=req.employee_ids,
        actor_id=current_user.id,
    )
