"""Repository for archive records and retention data pruning."""

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from fw.modules.archive.models import ArchiveRecord
from fw.modules.attendance import SiteVisit, TrackingGap
from fw.modules.events import MobileEventLog
from fw.modules.notifications import Alert
from fw.modules.org import Employee, EmployeeDocument
from fw.modules.sync import SyncChange


class ArchiveRepository:
    """Database repository for archive records, retention purges, and anonymisation."""

    @staticmethod
    async def create(session: AsyncSession, record: ArchiveRecord) -> ArchiveRecord:
        session.add(record)
        await session.flush()
        return record

    @staticmethod
    async def get_by_id(session: AsyncSession, archive_id: UUID) -> ArchiveRecord | None:
        stmt = select(ArchiveRecord).where(ArchiveRecord.id == archive_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_by_year(session: AsyncSession, year: int) -> ArchiveRecord | None:
        stmt = (
            select(ArchiveRecord)
            .where(ArchiveRecord.year == year)
            .order_by(ArchiveRecord.created_at.desc())
        )
        res = await session.execute(stmt)
        return res.scalars().first()

    @staticmethod
    async def list_archives(
        session: AsyncSession, limit: int = 50, offset: int = 0
    ) -> list[ArchiveRecord]:
        stmt = (
            select(ArchiveRecord)
            .order_by(ArchiveRecord.year.desc(), ArchiveRecord.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def query_year_events(
        session: AsyncSession, year: int, limit: int | None = None
    ) -> list[dict[str, Any]]:
        start_dt = datetime(year, 1, 1, 0, 0, 0, tzinfo=UTC)
        end_dt = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=UTC)

        stmt = (
            select(MobileEventLog)
            .where(
                MobileEventLog.event_timestamp_utc >= start_dt,
                MobileEventLog.event_timestamp_utc < end_dt,
            )
            .order_by(MobileEventLog.event_timestamp_utc.asc())
        )
        if limit:
            stmt = stmt.limit(limit)

        res = await session.execute(stmt)
        events = res.scalars().all()

        records: list[dict[str, Any]] = []
        for ev in events:
            records.append(
                {
                    "event_id": str(ev.event_id),
                    "employee_id": str(ev.employee_id),
                    "device_id": str(ev.device_id),
                    "event_type": ev.event_type,
                    "event_timestamp_utc": ev.event_timestamp_utc.isoformat(),
                    "latitude": float(ev.latitude) if ev.latitude is not None else None,
                    "longitude": float(ev.longitude) if ev.longitude is not None else None,
                    "accuracy_meters": ev.accuracy_meters,
                    "processing_status": ev.processing_status,
                    "server_verdict": ev.server_verdict,
                    "server_site_id": str(ev.server_site_id) if ev.server_site_id else None,
                }
            )
        return records

    @staticmethod
    async def query_year_visits(
        session: AsyncSession, year: int, limit: int | None = None
    ) -> list[dict[str, Any]]:
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)

        stmt = select(SiteVisit).where(
            SiteVisit.work_date >= start_date, SiteVisit.work_date <= end_date
        )
        if limit:
            stmt = stmt.limit(limit)

        res = await session.execute(stmt)
        visits = res.scalars().all()

        records: list[dict[str, Any]] = []
        for v in visits:
            records.append(
                {
                    "id": str(v.id),
                    "employee_id": str(v.employee_id),
                    "work_date": v.work_date.isoformat(),
                    "worksite_id": str(v.worksite_id),
                    "entry_at": v.entry_at.isoformat() if v.entry_at else None,
                    "exit_at": v.exit_at.isoformat() if v.exit_at else None,
                    "duration_minutes": v.duration_minutes,
                    "counts_as_completed": v.counts_as_completed,
                }
            )
        return records

    @staticmethod
    async def purge_year_records(session: AsyncSession, year: int) -> dict[str, int]:
        """Purge raw events and granular visits for the given archived year."""
        start_dt = datetime(year, 1, 1, 0, 0, 0, tzinfo=UTC)
        end_dt = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=UTC)
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)

        # Set administrative bypass for append-only trigger on mobile_event_logs
        await session.execute(text("SET LOCAL fwt.bypass_immutability = 'on'"))

        # 1. Purge tracking gaps for the year
        del_gaps = await session.execute(
            delete(TrackingGap).where(
                TrackingGap.work_date >= start_date, TrackingGap.work_date <= end_date
            )
        )
        gaps_count = int(getattr(del_gaps, "rowcount", 0) or 0)

        # 2. Purge site visits for the year (which reference mobile_event_logs)
        del_visits = await session.execute(
            delete(SiteVisit).where(
                SiteVisit.work_date >= start_date, SiteVisit.work_date <= end_date
            )
        )
        visits_count = int(getattr(del_visits, "rowcount", 0) or 0)

        # 3. Purge mobile_event_logs for the year
        del_events = await session.execute(
            delete(MobileEventLog).where(
                MobileEventLog.event_timestamp_utc >= start_dt,
                MobileEventLog.event_timestamp_utc < end_dt,
            )
        )
        events_count = int(getattr(del_events, "rowcount", 0) or 0)

        await session.flush()
        return {
            "events_purged": events_count,
            "visits_purged": visits_count,
            "gaps_purged": gaps_count,
        }

    @staticmethod
    async def purge_expired_sync_changes(session: AsyncSession, cutoff_datetime: datetime) -> int:
        stmt = delete(SyncChange).where(SyncChange.created_at < cutoff_datetime)
        res = await session.execute(stmt)
        await session.flush()
        return int(getattr(res, "rowcount", 0) or 0)

    @staticmethod
    async def purge_expired_alerts(session: AsyncSession, cutoff_datetime: datetime) -> int:
        stmt = delete(Alert).where(
            Alert.status == "RESOLVED",
            Alert.created_at < cutoff_datetime,
        )
        res = await session.execute(stmt)
        await session.flush()
        return int(getattr(res, "rowcount", 0) or 0)

    @staticmethod
    async def get_terminations_for_anonymisation(
        session: AsyncSession, cutoff_date: date
    ) -> list[Employee]:
        stmt = select(Employee).where(
            Employee.employment_end_date.is_not(None),
            Employee.employment_end_date <= cutoff_date,
            Employee.anonymised_at.is_(None),
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def anonymise_employee(session: AsyncSession, employee: Employee) -> None:
        short_id = str(employee.id)[:8]
        employee.name = f"Anonymised Worker {short_id}"
        employee.phone = None
        employee.email = None
        employee.anonymised_at = datetime.now(UTC)

        # Deactivate any employee documents
        del_docs_stmt = delete(EmployeeDocument).where(EmployeeDocument.employee_id == employee.id)
        await session.execute(del_docs_stmt)
        await session.flush()
