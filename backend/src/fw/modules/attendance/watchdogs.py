from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.modules.events.models import MobileEventLog
from fw.modules.notifications.models import Alert
from fw.modules.org.models import EmployeeReportingLine, RegisteredDevice
from fw.modules.scheduling.models import ScheduledWork

logger = structlog.get_logger(__name__)


class AttendanceWatchdogs:
    """Watchdogs for worker inactivity and stale devices."""

    @staticmethod
    async def check_no_activity(
        session: AsyncSession,
        today_date: date,
        no_activity_alert_after_minutes: int = 60,
    ) -> int:
        """Raise NO_ACTIVITY alert for workers with scheduled work today who have not logged events."""
        raised_count = 0

        # Find all active scheduled workers for today
        sched_q = (
            select(ScheduledWork.employee_id)
            .where(
                ScheduledWork.work_date == today_date,
                ScheduledWork.status == "ACTIVE",
            )
            .distinct()
        )
        sched_res = await session.execute(sched_q)
        scheduled_worker_ids = set(sched_res.scalars().all())

        if not scheduled_worker_ids:
            return 0

        # Find workers who have emitted events today
        events_q = (
            select(MobileEventLog.employee_id)
            .where(
                MobileEventLog.employee_id.in_(scheduled_worker_ids),
                MobileEventLog.processing_status == "ENRICHED",
            )
            .distinct()
        )
        events_res = await session.execute(events_q)
        active_worker_ids = set(events_res.scalars().all())

        inactive_worker_ids = scheduled_worker_ids - active_worker_ids

        for emp_id in inactive_worker_ids:
            # Check if alert already open for today
            alert_q = select(Alert.id).where(
                Alert.alert_type == "NO_ACTIVITY",
                Alert.employee_id == emp_id,
                Alert.status == "OPEN",
            )
            alert_res = await session.execute(alert_q)
            if alert_res.scalar_one_or_none() is not None:
                continue

            # Fetch supervisor if linked
            sup_q = (
                select(EmployeeReportingLine.manager_id)
                .where(
                    EmployeeReportingLine.employee_id == emp_id,
                    EmployeeReportingLine.relationship == "SUPERVISOR",
                )
                .limit(1)
            )
            sup_res = await session.execute(sup_q)
            sup_id = sup_res.scalar_one_or_none()

            alert = Alert(
                alert_type="NO_ACTIVITY",
                title="No Activity Detected",
                message="Worker is scheduled today but no mobile location events have been received.",
                ref_type="ATTENDANCE",
                ref_id=emp_id,
                employee_id=emp_id,
                target_user_id=None,
                target_role="SUPERVISOR",
                status="OPEN",
                details={
                    "work_date": str(today_date),
                    "supervisor_id": str(sup_id) if sup_id else None,
                },
            )
            session.add(alert)
            raised_count += 1

        await session.flush()
        return raised_count

    @staticmethod
    async def check_stale_devices(
        session: AsyncSession,
        stale_device_hours: int = 24,
    ) -> int:
        """Raise STALE_DEVICE alerts for active registered devices with no contact past threshold."""
        now = datetime.now(UTC)
        cutoff = now - timedelta(hours=stale_device_hours)
        raised_count = 0

        dev_q = select(RegisteredDevice).where(
            RegisteredDevice.is_active.is_(True),
            RegisteredDevice.last_seen_at < cutoff,
        )
        dev_res = await session.execute(dev_q)
        stale_devices = dev_res.scalars().all()

        for dev in stale_devices:
            alert_q = select(Alert.id).where(
                Alert.alert_type == "STALE_DEVICE",
                Alert.ref_id == dev.id,
                Alert.status == "OPEN",
            )
            alert_res = await session.execute(alert_q)
            if alert_res.scalar_one_or_none() is not None:
                continue

            alert = Alert(
                alert_type="STALE_DEVICE",
                title="Stale Device",
                message=f"Device {dev.device_model or dev.device_identifier} has not contacted the server for over {stale_device_hours} hours.",
                ref_type="REGISTERED_DEVICE",
                ref_id=dev.id,
                employee_id=dev.employee_id,
                target_user_id=None,
                target_role="ADMIN",
                status="OPEN",
                details={
                    "last_seen_at": dev.last_seen_at.isoformat() if dev.last_seen_at else None,
                    "app_version": dev.app_version,
                },
            )
            session.add(alert)
            raised_count += 1

        await session.flush()
        return raised_count
