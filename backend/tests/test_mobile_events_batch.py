"""Integration tests for mobile event batch ingestion and validation."""

import socket
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, text

from fw.core.db import async_session_factory, engine
from fw.main import app
from fw.modules.events.models import MobileEventLog
from fw.modules.identity import AuthService, User
from fw.modules.org import Employee, RegisteredDevice


def is_db_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=0.5):
            return True
    except OSError:
        return False


db_required = pytest.mark.skipif(
    not is_db_available(),
    reason="Database integration tests require PostgreSQL running on localhost:5432",
)


@pytest.mark.asyncio
@db_required
async def test_mobile_events_batch_validation_and_ingestion():
    transport = ASGITransport(app=app)
    emp_id = uuid4()
    tally_id = f"WRK{str(uuid4())[:6]}"
    now = datetime.now(UTC)

    async with async_session_factory() as session:
        emp = Employee(
            id=emp_id,
            tally_id=tally_id,
            name="Events Worker",
            role="WORKER",
            country="AE",
            is_active=True,
        )
        session.add(emp)
        await session.flush()

        user = User(
            id=uuid4(),
            username=tally_id,
            credential_hash="fakehash",
            role="WORKER",
            is_active=True,
            must_change_password=False,
            employee_id=emp_id,
        )
        session.add(user)

        device = RegisteredDevice(
            employee_id=emp_id,
            device_identifier="device-event-1",
            platform="ANDROID",
            registered_at=now,
            is_active=True,
        )
        session.add(device)
        await session.commit()

    token = AuthService.create_access_token(user)

    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            batch_id = str(uuid4())
            valid_event_id = str(uuid4())
            duplicate_event_id = str(uuid4())
            future_event_id = str(uuid4())
            old_event_id = str(uuid4())
            invalid_coords_id = str(uuid4())

            # Seed pre-existing event for duplicate test
            async with async_session_factory() as session:
                existing_log = MobileEventLog(
                    event_id=duplicate_event_id,
                    employee_id=emp_id,
                    device_id=device.id,
                    event_type="PING",
                    event_timestamp_utc=now - timedelta(hours=1),
                    latitude=Decimal("25.100000"),
                    longitude=Decimal("55.200000"),
                    server_received_at=now,
                    is_processed=False,
                )
                session.add(existing_log)
                await session.commit()

            events_payload = {
                "batch_id": batch_id,
                "device_clock_utc": now.isoformat(),
                "events": [
                    {
                        "event_id": valid_event_id,
                        "event_type": "ENTRY",
                        "event_timestamp_utc": (now - timedelta(minutes=10)).isoformat(),
                        "latitude": 25.123456,
                        "longitude": 55.234567,
                        "accuracy_meters": 10.5,
                        "is_mock_location": False,
                        "sequence_number": 1,
                    },
                    {
                        "event_id": duplicate_event_id,
                        "event_type": "PING",
                        "event_timestamp_utc": (now - timedelta(hours=1)).isoformat(),
                        "latitude": 25.100000,
                        "longitude": 55.200000,
                    },
                    {
                        "event_id": future_event_id,
                        "event_type": "PING",
                        "event_timestamp_utc": (now + timedelta(hours=2)).isoformat(),
                        "latitude": 25.100000,
                        "longitude": 55.200000,
                    },
                    {
                        "event_id": old_event_id,
                        "event_type": "PING",
                        "event_timestamp_utc": (now - timedelta(days=10)).isoformat(),
                        "latitude": 25.100000,
                        "longitude": 55.200000,
                    },
                    {
                        "event_id": invalid_coords_id,
                        "event_type": "EXIT",
                        "event_timestamp_utc": (now - timedelta(minutes=5)).isoformat(),
                        "latitude": 125.0,  # Invalid latitude (> 90)
                        "longitude": 55.0,
                    },
                ],
            }

            res = await client.post("/api/v1/mobile/events/batch", json=events_payload)
            assert res.status_code == 200, res.text
            data = res.json()
            assert data["batch_id"] == batch_id
            assert "latest_cursor" in data

            results = {r["event_id"]: r for r in data["results"]}

            # 1. Valid event ACCEPTED
            assert results[valid_event_id]["status"] == "ACCEPTED"

            # 2. Existing event DUPLICATE
            assert results[duplicate_event_id]["status"] == "DUPLICATE"

            # 3. Future event REJECTED with TIMESTAMP_IN_FUTURE
            assert results[future_event_id]["status"] == "REJECTED"
            assert results[future_event_id]["reason"] == "TIMESTAMP_IN_FUTURE"

            # 4. Old event REJECTED with TIMESTAMP_TOO_OLD
            assert results[old_event_id]["status"] == "REJECTED"
            assert results[old_event_id]["reason"] == "TIMESTAMP_TOO_OLD"

            # 5. Invalid coordinates REJECTED with INVALID_COORDINATES
            assert results[invalid_coords_id]["status"] == "REJECTED"
            assert results[invalid_coords_id]["reason"] == "INVALID_COORDINATES"

    finally:
        async with async_session_factory() as session:
            await session.execute(text("SET LOCAL fwt.bypass_immutability = 'on';"))
            await session.execute(
                text("DELETE FROM employee_last_position WHERE employee_id = :emp_id;"),
                {"emp_id": emp_id},
            )
            await session.execute(
                delete(MobileEventLog).where(MobileEventLog.employee_id == emp_id)
            )
            await session.execute(
                delete(RegisteredDevice).where(RegisteredDevice.employee_id == emp_id)
            )
            await session.execute(delete(User).where(User.employee_id == emp_id))
            await session.execute(delete(Employee).where(Employee.id == emp_id))
            await session.commit()
        await engine.dispose()
