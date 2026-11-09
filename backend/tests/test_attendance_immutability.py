from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.exc import DBAPIError

from fw.core.db import async_session_factory, engine
from fw.main import app  # noqa: F401
from fw.modules.events.models import MobileEventLog
from fw.modules.org.models import Employee, RegisteredDevice


@pytest.fixture(autouse=True)
async def cleanup_db_engine():
    yield
    await engine.dispose()


@pytest.mark.asyncio
async def test_mobile_event_logs_append_only_trigger():
    """Verify that mobile_event_logs cannot be deleted and device fields cannot be modified."""
    async with async_session_factory() as session:
        # Create test employee & device
        emp_id = uuid4()
        emp = Employee(
            id=emp_id,
            tally_id=f"TEST_{emp_id.hex[:6]}",
            name="Immutability Tester",
            role="WORKER",
            country="AE",
        )
        session.add(emp)

        dev_id = uuid4()
        device = RegisteredDevice(
            id=dev_id,
            employee_id=emp_id,
            device_identifier=f"dev_{emp_id.hex[:6]}",
            platform="ANDROID",
            last_seen_at=datetime.now(UTC),
        )
        session.add(device)
        await session.flush()

        event_id = uuid4()
        now = datetime.now(UTC)
        log = MobileEventLog(
            event_id=event_id,
            employee_id=emp_id,
            device_id=dev_id,
            event_type="PING",
            event_timestamp_utc=now,
            latitude=Decimal("25.1"),
            longitude=Decimal("55.2"),
            accuracy_meters=15.0,
            server_received_at=now,
            processing_status="ACCEPTED",
        )
        session.add(log)
        await session.commit()

    # 1. Test DELETE is blocked by trigger
    async with async_session_factory() as session:
        with pytest.raises((DBAPIError, Exception)) as exc_info:
            await session.execute(delete(MobileEventLog).where(MobileEventLog.event_id == event_id))
            await session.commit()
        assert "cannot be deleted" in str(exc_info.value)
        await session.rollback()

    # 2. Test UPDATE on device column (latitude) is blocked by trigger
    async with async_session_factory() as session:
        with pytest.raises((DBAPIError, Exception)) as exc_info:
            await session.execute(
                update(MobileEventLog)
                .where(MobileEventLog.event_id == event_id)
                .values(latitude=Decimal("26.0"))
            )
            await session.commit()
        assert "immutable" in str(exc_info.value)
        await session.rollback()

    # 3. Test UPDATE on server enrichment column (server_verdict) is ALLOWED
    async with async_session_factory() as session:
        await session.execute(
            update(MobileEventLog)
            .where(MobileEventLog.event_id == event_id)
            .values(
                server_verdict="INSIDE",
                processing_status="ENRICHED",
                distance_to_polygon_m=0.0,
                flags=["ENRICHED_TEST"],
            )
        )
        await session.commit()

        # Verify update succeeded
        check_res = await session.execute(
            select(MobileEventLog.server_verdict, MobileEventLog.processing_status).where(
                MobileEventLog.event_id == event_id
            )
        )
        row = check_res.first()
        assert row is not None
        verdict, status = row
        assert verdict == "INSIDE"
        assert status == "ENRICHED"
