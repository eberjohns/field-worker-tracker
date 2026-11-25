"""Batch 7: login lockout (DEC-66), device-mismatch alert, push removal (DEC-64),
interval-safe settings and the template's real Company_Settings defaults."""

import io
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import openpyxl
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from fw.adapters.push import NullPushProvider, get_push_provider
from fw.core.db import async_session_factory
from fw.main import app
from fw.modules.audit.models import AuditLog
from fw.modules.identity import AuthService, User, hash_password
from fw.modules.imports.generator import generate_import_template_bytes
from fw.modules.notifications.models import Alert
from fw.modules.org import Employee, RegisteredDevice
from fw.modules.settings import CompanySettingValue, SettingsService
from fw.modules.settings.defaults import DEFAULT_COMPANY_SETTINGS
from fw.modules.sync import SyncService
from tests.test_batch6_features import get_admin_user_and_token

PASSWORD = "Correct-Horse-42"


async def _make_user(role: str = "ENGINEER") -> User:
    """A non-admin user with its own employee (only ADMIN001 may be standalone)."""
    async with async_session_factory() as session:
        emp = Employee(
            id=uuid4(),
            tally_id=f"E7{uuid4().hex[:6].upper()}",
            name="Batch Seven User",
            role=role,
            country="AE",
            is_active=True,
            staff_grade_description="Engineer",
        )
        session.add(emp)
        await session.flush()
        user = User(
            username=f"T7{uuid4().hex[:8].upper()}",
            credential_hash=hash_password(PASSWORD),
            role=role,
            employee_id=emp.id,
            is_active=True,
            must_change_password=False,
            password_changed_at=datetime.now(UTC),
        )
        session.add(user)
        await session.commit()
        return user


async def _reload(user_id) -> User:
    async with async_session_factory() as session:
        user = await session.get(User, user_id)
        assert user is not None
        return user


async def _admin_headers() -> dict[str, str]:
    async with async_session_factory() as session:
        _, token = await get_admin_user_and_token(session)
    return {"Authorization": f"Bearer {token}"}


async def _web_login(client: AsyncClient, username: str, password: str):
    return await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )


@pytest.mark.asyncio
async def test_five_wrong_passwords_lock_and_correct_password_stays_locked() -> None:
    user = await _make_user()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(4):
            res = await _web_login(client, user.username, "wrong-password")
            assert res.status_code == 401
            assert res.json()["code"] == "UNAUTHENTICATED"
        res = await _web_login(client, user.username, "wrong-password")
        assert res.status_code == 403, res.text
        body = res.json()
        assert body["code"] == "ACCOUNT_LOCKED"
        assert body["reason"] == "TOO_MANY_ATTEMPTS"
        assert body["locked_until_local"]

        stored = await _reload(user.id)
        assert stored.failed_attempts == 5
        assert stored.locked_until is not None
        assert stored.last_failed_login_at is not None

        # The lock is checked before the password.
        res = await _web_login(client, user.username, PASSWORD)
        assert res.status_code == 403
        assert res.json()["code"] == "ACCOUNT_LOCKED"

    async with async_session_factory() as session:
        locks = (
            (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.entity_id == str(user.id), AuditLog.action == "LOCK_ACCOUNT"
                    )
                )
            )
            .scalars()
            .all()
        )
    assert len(locks) == 1


@pytest.mark.asyncio
async def test_lock_expiry_allows_login_and_resets_count() -> None:
    user = await _make_user()
    async with async_session_factory() as session:
        row = await session.get(User, user.id)
        assert row is not None
        row.failed_attempts = 5
        row.locked_until = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await _web_login(client, user.username, PASSWORD)
        assert res.status_code == 200, res.text
    stored = await _reload(user.id)
    assert stored.failed_attempts == 0
    assert stored.locked_until is None


@pytest.mark.asyncio
async def test_one_wrong_after_expiry_does_not_relock() -> None:
    user = await _make_user()
    async with async_session_factory() as session:
        row = await session.get(User, user.id)
        assert row is not None
        row.failed_attempts = 5
        row.locked_until = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await _web_login(client, user.username, "wrong-password")
        assert res.status_code == 401
    stored = await _reload(user.id)
    assert stored.failed_attempts == 1


@pytest.mark.asyncio
async def test_success_resets_count() -> None:
    user = await _make_user()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(3):
            await _web_login(client, user.username, "wrong-password")
        assert (await _reload(user.id)).failed_attempts == 3
        res = await _web_login(client, user.username, PASSWORD)
        assert res.status_code == 200
    assert (await _reload(user.id)).failed_attempts == 0


@pytest.mark.asyncio
async def test_unknown_user_gets_same_reply_as_wrong_password() -> None:
    user = await _make_user()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        wrong = await _web_login(client, user.username, "wrong-password")
        unknown = await _web_login(client, "NOSUCHUSER", "wrong-password")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["code"] == unknown.json()["code"]
    assert wrong.json()["detail"] == unknown.json()["detail"]


@pytest.mark.asyncio
async def test_admin_unlock() -> None:
    user = await _make_user()
    headers = await _admin_headers()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(5):
            await _web_login(client, user.username, "wrong-password")
        assert (await _web_login(client, user.username, PASSWORD)).status_code == 403

        # Only Admin may unlock.
        other = await _make_user(role="ENGINEER")
        res = await client.post(
            f"/api/v1/users/{user.id}/unlock",
            headers={"Authorization": f"Bearer {AuthService.create_access_token(other)}"},
        )
        assert res.status_code == 403

        res = await client.post(f"/api/v1/users/{user.id}/unlock", headers=headers)
        assert res.status_code == 200, res.text
        assert res.json()["locked_until"] is None
        assert res.json()["failed_attempts"] == 0

        assert (await _web_login(client, user.username, PASSWORD)).status_code == 200

    async with async_session_factory() as session:
        actions = (
            (
                await session.execute(
                    select(AuditLog.action).where(AuditLog.entity_id == str(user.id))
                )
            )
            .scalars()
            .all()
        )
    assert "LOCK_ACCOUNT" in actions
    assert "UNLOCK_ACCOUNT" in actions


@pytest.mark.asyncio
async def test_settings_change_the_policy() -> None:
    user = await _make_user()
    async with async_session_factory() as session:
        await SettingsService.set_setting(
            session, key="login_max_failed_attempts", value=2, effective_from=date(2026, 1, 1)
        )
        await session.commit()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            assert (await _web_login(c, user.username, "x")).status_code == 401
            res = await _web_login(c, user.username, "x")
            assert res.status_code == 403
            assert res.json()["code"] == "ACCOUNT_LOCKED"
    finally:
        async with async_session_factory() as session:
            await SettingsService.set_setting(
                session, key="login_max_failed_attempts", value=5, effective_from=date(2026, 1, 1)
            )
            await session.commit()


async def _make_worker() -> tuple[Employee, str]:
    async with async_session_factory() as session:
        emp = Employee(
            id=uuid4(),
            tally_id=f"W7{uuid4().hex[:6].upper()}",
            name="Batch Seven Worker",
            role="WORKER",
            country="AE",
            is_active=True,
            staff_grade_description="Gardener",
        )
        session.add(emp)
        await session.commit()
        default_pwd = await SyncService.get_default_password(session)
    return emp, default_pwd


def _mobile_payload(tally_id: str, password: str, device: str = "phone-a") -> dict:
    return {
        "tally_id": tally_id,
        "password": password,
        "device": {
            "device_identifier": device,
            "platform": "ANDROID",
            "device_model": "Pixel 8",
            "app_version": "1.0.0",
            "os_version": "15",
            "push_token": None,
        },
    }


@pytest.mark.asyncio
async def test_mobile_lockout_and_unknown_tally_id() -> None:
    emp, default_pwd = await _make_worker()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ok = await client.post(
            "/api/v1/mobile/auth/login", json=_mobile_payload(emp.tally_id, default_pwd)
        )
        assert ok.status_code == 200, ok.text

        unknown = await client.post(
            "/api/v1/mobile/auth/login", json=_mobile_payload("NOSUCH1", "wrong")
        )
        wrong = await client.post(
            "/api/v1/mobile/auth/login", json=_mobile_payload(emp.tally_id, "wrong")
        )
        assert unknown.status_code == wrong.status_code == 401
        assert unknown.json()["code"] == wrong.json()["code"] == "INVALID_CREDENTIALS"
        assert unknown.json()["detail"] == wrong.json()["detail"]

        for _ in range(3):
            await client.post(
                "/api/v1/mobile/auth/login", json=_mobile_payload(emp.tally_id, "wrong")
            )
        locked = await client.post(
            "/api/v1/mobile/auth/login", json=_mobile_payload(emp.tally_id, "wrong")
        )
        assert locked.status_code == 403
        assert locked.json()["code"] == "ACCOUNT_LOCKED"
        assert locked.json()["reason"] == "TOO_MANY_ATTEMPTS"

        still = await client.post(
            "/api/v1/mobile/auth/login", json=_mobile_payload(emp.tally_id, default_pwd)
        )
        assert still.status_code == 403
        assert still.json()["code"] == "ACCOUNT_LOCKED"


@pytest.mark.asyncio
async def test_device_mismatch_raises_one_admin_alert_per_day() -> None:
    emp, default_pwd = await _make_worker()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first = await client.post(
                "/api/v1/mobile/auth/login",
                json=_mobile_payload(emp.tally_id, default_pwd, "phone-a"),
            )
            assert first.status_code == 200
            for _ in range(2):
                res = await client.post(
                    "/api/v1/mobile/auth/login",
                    json=_mobile_payload(emp.tally_id, default_pwd, "phone-b"),
                )
                assert res.status_code == 403
                assert res.json()["code"] == "DEVICE_MISMATCH"

        async with async_session_factory() as session:
            alerts = (
                (
                    await session.execute(
                        select(Alert).where(
                            Alert.alert_type == "DEVICE_MISMATCH_ATTEMPT",
                            Alert.employee_id == emp.id,
                        )
                    )
                )
                .scalars()
                .all()
            )
        assert len(alerts) == 1
        assert alerts[0].target_role == "ADMIN"
        assert alerts[0].status == "OPEN"
        assert alerts[0].details["attempts"] == 2
        assert alerts[0].details["last_attempt"]["device_model"] == "Pixel 8"
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(Alert).where(Alert.employee_id == emp.id))
            await session.execute(
                delete(RegisteredDevice).where(RegisteredDevice.employee_id == emp.id)
            )
            await session.commit()


@pytest.mark.asyncio
async def test_push_is_never_sent() -> None:
    provider = get_push_provider()
    assert isinstance(provider, NullPushProvider)
    assert await provider.send_silent("token", {"type": "SYNC"}) is False


@pytest.mark.asyncio
async def test_back_dated_setting_does_not_overlap() -> None:
    key = f"t7_setting_{uuid4().hex[:6]}"
    async with async_session_factory() as session:
        await SettingsService.set_setting(
            session, key=key, value=1, effective_from=date(2026, 1, 1)
        )
        await SettingsService.set_setting(
            session, key=key, value=2, effective_from=date(2026, 6, 1)
        )
        # A back-dated value between them, and a same-day value on a closed row.
        await SettingsService.set_setting(
            session, key=key, value=3, effective_from=date(2026, 3, 1)
        )
        await SettingsService.set_setting(
            session, key=key, value=4, effective_from=date(2026, 1, 1)
        )
        await session.commit()
        rows = (
            (
                await session.execute(
                    select(CompanySettingValue)
                    .where(CompanySettingValue.setting_key == key)
                    .order_by(CompanySettingValue.effective_from)
                )
            )
            .scalars()
            .all()
        )
        spans = [(r.effective_from, r.effective_to, r.value) for r in rows]
        await session.execute(
            delete(CompanySettingValue).where(CompanySettingValue.setting_key == key)
        )
        await session.commit()
    assert spans == [
        (date(2026, 1, 1), date(2026, 2, 28), 4),
        (date(2026, 3, 1), date(2026, 5, 31), 3),
        (date(2026, 6, 1), None, 2),
    ]


def test_template_company_settings_rows_are_real_defaults() -> None:
    wb = openpyxl.load_workbook(io.BytesIO(generate_import_template_bytes()))
    ws = wb["Company_Settings"]
    headers = [c.value for c in ws[4]]
    key_col = headers.index("setting_key")
    rows = [r for r in ws.iter_rows(min_row=5, values_only=True) if r[key_col]]
    assert rows, "Company_Settings has rows"
    assert all(r[0] in (None, "") for r in rows), "no EXAMPLE marker"
    keys = {(r[key_col], r[headers.index("country")]) for r in rows}
    assert keys == {(k, c) for k, c, _v, _u in DEFAULT_COMPANY_SETTINGS}
    assert not any(k == "ot2_weekdays" for k, _c in keys)
    assert ("login_max_failed_attempts", None) in keys
