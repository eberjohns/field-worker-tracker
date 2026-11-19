"""Background worker and task scheduler."""

import asyncio
import sys
from collections.abc import Callable, Coroutine
from datetime import UTC, date, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.clock import site_today
from fw.core.config import get_settings
from fw.core.db import async_session_factory
from fw.core.logging import setup_logging
from fw.modules.archive.repository import ArchiveRepository
from fw.modules.archive.service import ArchiveService
from fw.modules.attendance.pending_visits import PendingVisitsService
from fw.modules.attendance.watchdogs import AttendanceWatchdogs
from fw.modules.notifications.service import NotificationService
from fw.modules.settings.service import SettingsService

logger = structlog.get_logger("fw.worker")


class WorkerScheduler:
    """Production background job scheduler for periodic watchdogs, daily detection, and retention maintenance."""

    def __init__(self) -> None:
        self._stop_event = asyncio.Event()
        self._daily_jobs_run: dict[str, date] = {}
        self._last_watchdog_run: datetime | None = None

    async def _execute_job(
        self,
        job_name: str,
        coro_func: Callable[[AsyncSession], Coroutine[Any, Any, Any]],
    ) -> Any:
        """Run a job in an isolated DB session, logging start/completion and raising Admin alert on failure."""
        logger.info("job_started", job_name=job_name)
        async with async_session_factory() as session:
            try:
                result = await coro_func(session)
                await session.commit()
                logger.info("job_completed", job_name=job_name, result=str(result))
                return result
            except Exception as exc:
                await session.rollback()
                logger.error("job_failed", job_name=job_name, error=str(exc))
                # Raise admin alert on separate session so rollback doesn't discard alert
                await self._raise_failure_alert(job_name, str(exc))
                return None

    async def _raise_failure_alert(self, job_name: str, error_message: str) -> None:
        """Create a JOB_FAILURE alert for administrators."""
        try:
            async with async_session_factory() as alert_session:
                await NotificationService.create_alert(
                    session=alert_session,
                    alert_type="JOB_FAILURE",
                    title=f"Background Job Failed: {job_name}",
                    message=f"Scheduled background job '{job_name}' failed with error: {error_message}",
                    ref_type="BACKGROUND_JOB",
                    target_role="ADMIN",
                    details={"job_name": job_name, "error": error_message},
                )
                await alert_session.commit()
        except Exception as alert_exc:
            logger.error(
                "job_failure_alert_creation_failed", job_name=job_name, error=str(alert_exc)
            )

    async def run_watchdogs(self) -> dict[str, int]:
        """Check worker inactivity and stale devices."""

        async def _job(session: AsyncSession) -> dict[str, int]:
            country = get_settings().DEPLOYMENT_COUNTRY
            today = site_today(country)

            # Read thresholds from settings if available
            no_act_minutes = await SettingsService.get_setting(
                session, "no_activity_alert_after_minutes", default=60
            )
            stale_hours = await SettingsService.get_setting(
                session, "stale_device_hours", default=24
            )

            try:
                no_act_min_int = int(no_act_minutes) if no_act_minutes else 60
            except (ValueError, TypeError):
                no_act_min_int = 60

            try:
                stale_hrs_int = int(stale_hours) if stale_hours else 24
            except (ValueError, TypeError):
                stale_hrs_int = 24

            no_act_count = await AttendanceWatchdogs.check_no_activity(
                session=session,
                today_date=today,
                no_activity_alert_after_minutes=no_act_min_int,
            )
            stale_count = await AttendanceWatchdogs.check_stale_devices(
                session=session,
                stale_device_hours=stale_hrs_int,
            )
            return {"no_activity_alerts": no_act_count, "stale_device_alerts": stale_count}

        return await self._execute_job("watchdogs", _job)

    async def run_pending_visits(self, country: str) -> dict[str, int]:
        """Detect unvisited scheduled sites and send reminders."""

        async def _job(session: AsyncSession) -> dict[str, int]:
            today = site_today(country)
            detected = await PendingVisitsService.detect_pending_visits(
                session=session,
                target_date=today,
            )
            reminders = await PendingVisitsService.check_pending_visit_reminders(
                session=session,
            )
            return {"pending_visits_detected": detected, "reminders_sent": reminders}

        return await self._execute_job(f"pending_visits_{country}", _job)

    async def run_document_expiry(self) -> int:
        """Scan active employee documents and raise DOC_EXPIRY alerts."""

        async def _job(session: AsyncSession) -> int:
            return await NotificationService.check_document_expiry_alerts(session)

        return await self._execute_job("document_expiry", _job)

    async def run_retention_purge(self) -> dict[str, Any]:
        """Purge sync_changes (>60d) and expired alerts (>6mo) per DEC-38."""

        async def _job(session: AsyncSession) -> dict[str, Any]:
            result = await ArchiveService.run_retention_purge(
                session=session,
                sync_days=60,
                notif_months=6,
            )
            return {
                "sync_changes_purged": result.sync_changes_purged,
                "notifications_purged": result.notification_logs_purged,
            }

        return await self._execute_job("retention_purge", _job)

    async def run_yearly_archive(self) -> dict[str, Any]:
        """Archive and purge events for previous calendar year if not already archived."""

        async def _job(session: AsyncSession) -> dict[str, Any]:
            prev_year = datetime.now(UTC).year - 1
            existing = await ArchiveRepository.get_by_year(session, prev_year)
            if existing:
                return {"status": "SKIPPED_ALREADY_ARCHIVED", "year": prev_year}

            archive = await ArchiveService.create_yearly_archive(
                session=session,
                year=prev_year,
                purge_live_events=True,
            )
            return {
                "status": "ARCHIVED",
                "year": prev_year,
                "archive_id": str(archive.id),
                "record_count": archive.record_count,
            }

        return await self._execute_job("yearly_archive", _job)

    async def run_all_once(self) -> None:
        """Execute all scheduled jobs once (useful for tests and manual invocations)."""
        settings = get_settings()
        country = settings.DEPLOYMENT_COUNTRY
        await self.run_watchdogs()
        await self.run_pending_visits(country)
        await self.run_document_expiry()
        await self.run_retention_purge()
        await self.run_yearly_archive()

    async def start(self) -> None:
        """Start scheduler background loop."""
        logger.info("worker_scheduler_started")
        settings = get_settings()
        country = settings.DEPLOYMENT_COUNTRY

        # Run once on startup
        try:
            await self.run_all_once()
        except Exception as exc:
            logger.error("startup_jobs_failed", error=str(exc))

        while not self._stop_event.is_set():
            try:
                now_utc = datetime.now(UTC)
                today_site = site_today(country)

                # Periodic watchdogs every 15 minutes
                if (
                    self._last_watchdog_run is None
                    or (now_utc - self._last_watchdog_run).total_seconds() >= 900
                ):
                    await self.run_watchdogs()
                    self._last_watchdog_run = now_utc

                # Daily jobs run once per site local date
                if self._daily_jobs_run.get(country) != today_site:
                    await self.run_pending_visits(country)
                    await self.run_document_expiry()
                    await self.run_retention_purge()
                    await self.run_yearly_archive()
                    self._daily_jobs_run[country] = today_site

                # Sleep 60s before next tick
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=60.0)
                except TimeoutError:
                    pass
            except asyncio.CancelledError:
                break
            except Exception as loop_exc:
                logger.error("worker_scheduler_loop_error", error=str(loop_exc))
                await asyncio.sleep(5.0)

        logger.info("worker_scheduler_stopped")

    def stop(self) -> None:
        self._stop_event.set()


async def main() -> None:
    setup_logging()
    scheduler = WorkerScheduler()
    try:
        await scheduler.start()
    except asyncio.CancelledError:
        logger.info("worker_stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
