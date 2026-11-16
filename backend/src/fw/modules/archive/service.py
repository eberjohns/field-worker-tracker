"""Service layer for yearly archiving, verification, retention cleanup, and anonymisation."""

import gzip
import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.config import get_settings
from fw.core.errors import AppError
from fw.modules.archive.crypto import (
    compute_sha256,
    decrypt_payload,
    encrypt_payload,
)
from fw.modules.archive.models import ArchiveRecord
from fw.modules.archive.repository import ArchiveRepository
from fw.modules.archive.schemas import (
    AnonymisationResult,
    ArchiveVerificationResult,
    RetentionPurgeResult,
)
from fw.modules.audit import AuditService

logger = structlog.get_logger(__name__)


class ArchiveService:
    """Orchestrates creation, cryptographic verification, retention purge, and anonymisation."""

    @staticmethod
    async def create_yearly_archive(
        session: AsyncSession,
        year: int,
        purge_live_events: bool = True,
        actor_id: UUID | None = None,
    ) -> ArchiveRecord:
        """Export calendar year's events and visits, encrypt with AES-256-GCM, verify, and purge."""
        settings = get_settings()
        current_year = datetime.now(UTC).year
        if year > current_year:
            raise AppError(
                code="INVALID_ARCHIVE_YEAR",
                message=f"Cannot archive future year {year}.",
                status_code=400,
            )

        logger.info("Starting yearly archive", year=year, purge_live=purge_live_events)

        # 1. Query records
        events = await ArchiveRepository.query_year_events(session, year)
        visits = await ArchiveRepository.query_year_visits(session, year)

        payload_obj: dict[str, Any] = {
            "metadata": {
                "year": year,
                "event_count": len(events),
                "visit_count": len(visits),
                "generated_at": datetime.now(UTC).isoformat(),
            },
            "events": events,
            "visits": visits,
        }
        json_bytes = json.dumps(payload_obj, ensure_ascii=False).encode("utf-8")
        compressed_bytes = gzip.compress(json_bytes)

        # 2. Encrypt package with AES-256-GCM
        encrypted_package, checksum = encrypt_payload(
            compressed_bytes, settings.ARCHIVE_ENCRYPTION_KEY
        )

        # 3. Save to disk storage
        storage_dir = Path(settings.ARCHIVE_STORAGE_PATH)
        storage_dir.mkdir(parents=True, exist_ok=True)
        ts_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        file_name = f"fwt_archive_{year}_{ts_str}.enc"
        file_path = storage_dir / file_name

        with open(file_path, "wb") as f:
            f.write(encrypted_package)

        file_size = len(encrypted_package)

        # 4. Immediate restore verification drill on the package
        try:
            sample_decrypted = decrypt_payload(
                encrypted_package, settings.ARCHIVE_ENCRYPTION_KEY
            )
            sample_json = json.loads(gzip.decompress(sample_decrypted).decode("utf-8"))
            if sample_json.get("metadata", {}).get("year") != year:
                raise ValueError("Restored payload metadata mismatch.")
        except Exception as err:
            logger.error("Archive self-verification failed", year=year, error=str(err))
            if file_path.exists():
                os.remove(file_path)
            raise AppError(
                code="ARCHIVE_VERIFICATION_FAILED",
                message=f"Archive verification failed after encryption: {err}",
                status_code=500,
            ) from err

        # 5. Purge from live database if requested
        purged_counts: dict[str, int] = {}
        purged_at: datetime | None = None
        if purge_live_events:
            purged_counts = await ArchiveRepository.purge_year_records(session, year)
            purged_at = datetime.now(UTC)

        # 6. Save ArchiveRecord
        now = datetime.now(UTC)
        record = ArchiveRecord(
            year=year,
            file_name=file_name,
            file_path=str(file_path),
            file_size_bytes=file_size,
            sha256_checksum=checksum,
            encryption_algo="AES-256-GCM",
            record_count=len(events),
            status="COMPLETED",
            archived_at=now,
            verified_at=now,
            purged_at=purged_at,
            purged_record_count=purged_counts.get("events_purged", 0),
            details={
                "event_count": len(events),
                "visit_count": len(visits),
                "purged_details": purged_counts,
            },
        )
        await ArchiveRepository.create(session, record)

        # 7. Audit log
        if actor_id:
            await AuditService.log_action(
                session=session,
                action="YEARLY_ARCHIVE_CREATED",
                entity_type="ArchiveRecord",
                entity_id=str(record.id),
                diff={
                    "year": year,
                    "file_name": file_name,
                    "sha256": checksum,
                    "records_archived": len(events),
                    "purged": purge_live_events,
                },
                actor_user_id=actor_id,
                reason=f"Executed yearly archive for {year}",
            )

        await session.commit()
        return record

    @staticmethod
    async def verify_archive(
        session: AsyncSession,
        archive_id: UUID,
        actor_id: UUID | None = None,
    ) -> ArchiveVerificationResult:
        """Verify archive checksum and decrypt sample records to ensure integrity."""
        settings = get_settings()
        record = await ArchiveRepository.get_by_id(session, archive_id)
        if not record:
            raise AppError(code="ARCHIVE_NOT_FOUND", message="Archive record not found.", status_code=404)

        if not os.path.exists(record.file_path):
            raise AppError(
                code="ARCHIVE_FILE_MISSING",
                message=f"Archive file {record.file_name} not found on storage.",
                status_code=404,
            )

        with open(record.file_path, "rb") as f:
            encrypted_data = f.read()

        # Checksum check
        actual_checksum = compute_sha256(encrypted_data)
        if actual_checksum != record.sha256_checksum:
            raise AppError(
                code="CHECKSUM_MISMATCH",
                message=f"SHA-256 checksum mismatch for archive {record.id}. Corrupted file.",
                status_code=409,
            )

        # Decrypt check
        try:
            decrypted = decrypt_payload(encrypted_data, settings.ARCHIVE_ENCRYPTION_KEY)
            payload = json.loads(gzip.decompress(decrypted).decode("utf-8"))
            event_count = payload.get("metadata", {}).get("event_count", 0)
        except Exception as err:
            raise AppError(
                code="DECRYPTION_FAILED",
                message=f"Archive decryption failed: {err}",
                status_code=422,
            ) from err

        record.verified_at = datetime.now(UTC)
        record.status = "VERIFIED"

        if actor_id:
            await AuditService.log_action(
                session=session,
                action="ARCHIVE_VERIFIED",
                entity_type="ArchiveRecord",
                entity_id=str(record.id),
                diff={"verified_at": record.verified_at.isoformat(), "status": "VERIFIED"},
                actor_user_id=actor_id,
                reason="Archive integrity and checksum verification passed",
            )

        await session.commit()
        return ArchiveVerificationResult(
            archive_id=record.id,
            verified=True,
            record_count=event_count,
            sha256_checksum=actual_checksum,
            message="Archive integrity verified successfully.",
        )

    @staticmethod
    async def run_retention_purge(
        session: AsyncSession,
        sync_days: int = 60,
        notif_months: int = 6,
        actor_id: UUID | None = None,
    ) -> RetentionPurgeResult:
        """Purge sync changes (>60 days default) and resolved notifications (>6 months default)."""
        now = datetime.now(UTC)
        sync_cutoff = now - timedelta(days=sync_days)
        notif_cutoff = now - timedelta(days=notif_months * 30)

        sync_purged = await ArchiveRepository.purge_expired_sync_changes(session, sync_cutoff)
        notif_purged = await ArchiveRepository.purge_expired_alerts(session, notif_cutoff)

        if actor_id:
            await AuditService.log_action(
                session=session,
                action="RETENTION_PURGE_EXECUTED",
                entity_type="RetentionSchedule",
                entity_id="retention",
                diff={
                    "sync_changes_purged": sync_purged,
                    "notifications_purged": notif_purged,
                    "sync_cutoff": sync_cutoff.isoformat(),
                    "notif_cutoff": notif_cutoff.isoformat(),
                },
                actor_user_id=actor_id,
                reason="Routine retention policy schedule execution",
            )

        await session.commit()
        return RetentionPurgeResult(
            sync_changes_purged=sync_purged,
            notification_logs_purged=notif_purged,
            completed_at=datetime.now(UTC),
        )

    @staticmethod
    async def anonymise_expired_employees(
        session: AsyncSession,
        older_than_years: int = 2,
        employee_ids: list[UUID] | None = None,
        actor_id: UUID | None = None,
    ) -> AnonymisationResult:
        """Anonymise workers whose employment terminated > 2 years ago (UAE labour claim expiry)."""
        cutoff_date = date.today() - timedelta(days=older_than_years * 365)

        if employee_ids:
            from sqlalchemy import select
            from fw.modules.org import Employee
            stmt = select(Employee).where(
                Employee.id.in_(employee_ids),
                Employee.anonymised_at.is_(None),
            )
            res = await session.execute(stmt)
            employees = list(res.scalars().all())
        else:
            employees = await ArchiveRepository.get_terminations_for_anonymisation(
                session, cutoff_date
            )

        anonymised_ids: list[UUID] = []
        for emp in employees:
            await ArchiveRepository.anonymise_employee(session, emp)
            anonymised_ids.append(emp.id)

        if actor_id and anonymised_ids:
            await AuditService.log_action(
                session=session,
                action="EMPLOYEES_ANONYMISED",
                entity_type="Employee",
                entity_id="bulk",
                diff={"count": len(anonymised_ids), "anonymised_ids": [str(i) for i in anonymised_ids]},
                actor_user_id=actor_id,
                reason=f"Anonymised terminated employees older than {older_than_years} years per retention policy",
            )

        await session.commit()
        return AnonymisationResult(
            anonymised_employees_count=len(anonymised_ids),
            anonymised_employee_ids=anonymised_ids,
            completed_at=datetime.now(UTC),
        )
