"""Integration tests for mobile authentication, device binding, and password enforcement."""

import socket
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from fw.core.db import async_session_factory, engine
from fw.main import app
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
async def test_mobile_login_device_binding_and_password_workflow():
    transport = ASGITransport(app=app)
    emp_id = uuid4()
    tally_id = f"WRK{str(uuid4())[:6]}"

    async with async_session_factory() as session:
        emp = Employee(
            id=emp_id,
            tally_id=tally_id,
            name="Test Worker",
            role="WORKER",
            country="AE",
            is_active=True,
            staff_grade_description="Gardener",
        )
        session.add(emp)
        await session.commit()

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. First login with default password "Welcome123!"
            login_payload = {
                "tally_id": tally_id,
                "password": "Welcome123!",
                "device": {
                    "device_identifier": "device-phone-1",
                    "platform": "ANDROID",
                    "device_model": "Samsung A14",
                    "app_version": "1.0.0",
                    "os_version": "14",
                    "push_token": "fcm-token-1",
                },
            }
            res = await client.post("/api/v1/mobile/auth/login", json=login_payload)
            assert res.status_code == 200, res.text
            data = res.json()
            assert data["must_change_password"] is True
            token1 = data["access_token"]
            refresh_token1 = data["refresh_token"]
            assert refresh_token1 is not None

            # 2. Second device attempts login -> Refused with 403 DEVICE_MISMATCH
            mismatch_payload = {
                "tally_id": tally_id,
                "password": "Welcome123!",
                "device": {
                    "device_identifier": "device-phone-2",
                    "platform": "IOS",
                    "device_model": "iPhone 15",
                    "app_version": "1.0.0",
                    "os_version": "17",
                    "push_token": "apns-token-2",
                },
            }
            res2 = await client.post("/api/v1/mobile/auth/login", json=mismatch_payload)
            assert res2.status_code == 403
            assert res2.json()["code"] == "DEVICE_MISMATCH"

            # 3. Accessing sync before changing password -> 403 PASSWORD_CHANGE_REQUIRED
            sync_res = await client.get(
                "/api/v1/mobile/sync/snapshot",
                headers={"Authorization": f"Bearer {token1}"},
            )
            assert sync_res.status_code == 403
            assert sync_res.json()["code"] == "PASSWORD_CHANGE_REQUIRED"

            # 4. Change password using POST /api/v1/mobile/auth/change-password
            change_res = await client.post(
                "/api/v1/mobile/auth/change-password",
                headers={"Authorization": f"Bearer {token1}"},
                json={"old_password": "Welcome123!", "new_password": "NewSecretPass123!"},
            )
            assert change_res.status_code == 200
            assert change_res.json()["status"] == "PASSWORD_CHANGED"

            # 5. Now re-login with new password from bound device
            login_payload["password"] = "NewSecretPass123!"
            res_new_login = await client.post("/api/v1/mobile/auth/login", json=login_payload)
            assert res_new_login.status_code == 200
            new_data = res_new_login.json()
            assert new_data["must_change_password"] is False
            valid_token = new_data["access_token"]

            # 6. Snapshot now succeeds
            snapshot_res = await client.get(
                "/api/v1/mobile/sync/snapshot",
                headers={"Authorization": f"Bearer {valid_token}"},
            )
            assert snapshot_res.status_code == 200
            snapshot_data = snapshot_res.json()
            assert "entities" in snapshot_data
            assert "cursor" in snapshot_data

            # 7. Consent recording works
            consent_res = await client.post(
                "/api/v1/mobile/consent",
                headers={"Authorization": f"Bearer {valid_token}"},
                json={
                    "policy_version": 1,
                    "consented_at_utc": datetime.now(UTC).isoformat(),
                },
            )
            assert consent_res.status_code == 200
            assert consent_res.json()["status"] == "CONSENT_RECORDED"

            # 8. Heartbeat works
            heartbeat_res = await client.post(
                "/api/v1/mobile/heartbeat",
                headers={"Authorization": f"Bearer {valid_token}"},
                json={
                    "app_version": "1.0.1",
                    "cursor": 0,
                    "location_permission_state": "ALWAYS",
                },
            )
            assert heartbeat_res.status_code == 200
            assert "server_time_utc" in heartbeat_res.json()

    finally:
        async with async_session_factory() as session:
            await session.execute(
                delete(RegisteredDevice).where(RegisteredDevice.employee_id == emp_id)
            )
            await session.execute(delete(User).where(User.employee_id == emp_id))
            await session.execute(delete(Employee).where(Employee.id == emp_id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
@db_required
async def test_admin_device_reset_allows_rebinding():
    transport = ASGITransport(app=app)
    emp_id = uuid4()
    admin_emp_id = uuid4()
    admin_user_id = uuid4()
    tally_id = f"WRK{str(uuid4())[:6]}"
    admin_tally_id = f"ADM{str(uuid4())[:6]}"

    async with async_session_factory() as session:
        emp = Employee(
            id=emp_id,
            tally_id=tally_id,
            name="Worker To Reset",
            role="WORKER",
            country="AE",
            is_active=True,
        )
        session.add(emp)

        admin_emp = Employee(
            id=admin_emp_id,
            tally_id=admin_tally_id,
            name="Admin Employee",
            role="ADMIN",
            country="AE",
            is_active=True,
        )
        session.add(admin_emp)
        await session.flush()

        admin = User(
            id=admin_user_id,
            username=admin_tally_id,
            credential_hash="fakehash",
            role="ADMIN",
            is_active=True,
            must_change_password=False,
            employee_id=admin_emp_id,
        )
        session.add(admin)
        await session.commit()

    admin_token = AuthService.create_access_token(admin)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Login device 1
            res1 = await client.post(
                "/api/v1/mobile/auth/login",
                json={
                    "tally_id": tally_id,
                    "password": "Welcome123!",
                    "device": {
                        "device_identifier": "first-device-id",
                        "platform": "ANDROID",
                    },
                },
            )
            assert res1.status_code == 200

            # Second device login fails
            res2 = await client.post(
                "/api/v1/mobile/auth/login",
                json={
                    "tally_id": tally_id,
                    "password": "Welcome123!",
                    "device": {
                        "device_identifier": "second-device-id",
                        "platform": "ANDROID",
                    },
                },
            )
            assert res2.status_code == 403
            assert res2.json()["code"] == "DEVICE_MISMATCH"

            # Admin checks device list
            dev_list_res = await client.get(
                "/api/v1/devices",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert dev_list_res.status_code == 200
            devices = [d for d in dev_list_res.json() if d["employee_id"] == str(emp_id)]
            assert len(devices) == 1
            device_id = devices[0]["device_id"]
            assert devices[0]["is_active"] is True

            # Admin resets device binding
            reset_res = await client.post(
                f"/api/v1/devices/{device_id}/reset",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert reset_res.status_code == 200
            assert reset_res.json()["status"] == "DEVICE_RESET"

            # Second device can now log in and binds
            res3 = await client.post(
                "/api/v1/mobile/auth/login",
                json={
                    "tally_id": tally_id,
                    "password": "Welcome123!",
                    "device": {
                        "device_identifier": "second-device-id",
                        "platform": "ANDROID",
                        "device_model": "Google Pixel 8",
                    },
                },
            )
            assert res3.status_code == 200
            assert res3.json()["employee"]["tally_id"] == tally_id

    finally:
        async with async_session_factory() as session:
            await session.execute(
                delete(RegisteredDevice).where(RegisteredDevice.employee_id == emp_id)
            )
            await session.execute(delete(User).where(User.id == admin_user_id))
            await session.execute(delete(User).where(User.employee_id == emp_id))
            await session.execute(delete(Employee).where(Employee.id == emp_id))
            await session.execute(delete(Employee).where(Employee.id == admin_emp_id))
            await session.commit()
        await engine.dispose()
