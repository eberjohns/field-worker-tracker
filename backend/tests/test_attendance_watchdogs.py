from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from fw.core.db import async_session_factory, engine
from fw.main import app  # noqa: F401
from fw.modules.attendance.watchdogs import AttendanceWatchdogs
from fw.modules.jobs.models import JobItem, Worksite
from fw.modules.notifications.models import Alert
from fw.modules.org.models import Employee, Group, RegisteredDevice, Zone
from fw.modules.scheduling.models import ScheduledWork


@pytest.fixture(autouse=True)
async def cleanup_db_engine():
    yield
    await engine.dispose()


@pytest.mark.asyncio
async def test_attendance_watchdogs():
    async with async_session_factory() as session:
        # Create worker
        worker_id = uuid4()
        worker = Employee(
            id=worker_id,
            tally_id=f"WDG_{worker_id.hex[:6]}",
            name="Watchdog Tester",
            role="WORKER",
            country="AE",
        )
        session.add(worker)

        # Create device with stale last_seen_at (48 hours ago)
        dev_id = uuid4()
        dev = RegisteredDevice(
            id=dev_id,
            employee_id=worker_id,
            device_identifier=f"dev_{dev_id.hex[:6]}",
            platform="ANDROID",
            is_active=True,
            last_seen_at=datetime.now(UTC) - timedelta(hours=48),
        )
        session.add(dev)

        # Create Group, Zone, Worksite, JobItem
        grp_id = uuid4()
        session.add(Group(id=grp_id, code=f"GRP_{grp_id.hex[:4]}", name="WDG Group"))
        zn_id = uuid4()
        session.add(Zone(id=zn_id, code=f"ZN_{zn_id.hex[:4]}", name="WDG Zone"))
        await session.flush()

        ws_id = uuid4()
        session.add(
            Worksite(
                id=ws_id,
                job_number=f"JN{ws_id.hex[:6]}",
                job_name="WDG Site",
                group_id=grp_id,
                zone_id=zn_id,
                country="AE",
                is_active=True,
            )
        )
        ji_id = uuid4()
        session.add(
            JobItem(
                id=ji_id,
                worksite_id=ws_id,
                sub_item_code="A",
                staff_grade_description="Gardener Expert",
                planned_grade_code="G2B",
                frequency_unit="WEEK",
                occurrences_per_period=Decimal("6.0"),
                period_interval=1,
                required_staff_count=1,
                hours_per_occurrence_per_staff=Decimal("8.0"),
                start_date=date(2026, 1, 1),
                deployment_type="PERMANENT",
                is_active=True,
            )
        )
        await session.flush()

        # Create scheduled work today (no events emitted)
        test_date = date(2026, 11, 20)
        sw = ScheduledWork(
            id=uuid4(),
            employee_id=worker_id,
            work_date=test_date,
            worksite_id=ws_id,
            job_item_id=ji_id,
            assigned_hours=Decimal("8.0"),
            sequence=1,
            status="ACTIVE",
            source="DIRECT",
        )
        session.add(sw)
        await session.commit()

    # 1. Run check_no_activity
    async with async_session_factory() as session:
        raised = await AttendanceWatchdogs.check_no_activity(session, test_date)
        assert raised >= 1

        # Check alert created
        alert_q = select(Alert).where(
            Alert.alert_type == "NO_ACTIVITY", Alert.employee_id == worker_id
        )
        res = await session.execute(alert_q)
        alert = res.scalar_one_or_none()
        assert alert is not None
        assert alert.ref_type == "ATTENDANCE"

    # 2. Run check_stale_devices
    async with async_session_factory() as session:
        stale_raised = await AttendanceWatchdogs.check_stale_devices(session, stale_device_hours=24)
        assert stale_raised >= 1

        # Check alert created
        stale_alert_q = select(Alert).where(
            Alert.alert_type == "STALE_DEVICE", Alert.ref_id == dev_id
        )
        stale_res = await session.execute(stale_alert_q)
        stale_alert = stale_res.scalar_one_or_none()
        assert stale_alert is not None
        assert stale_alert.ref_type == "REGISTERED_DEVICE"
