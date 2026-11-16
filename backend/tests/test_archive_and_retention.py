"""Tests for Phase 13 Hardening, Archive, Retention, DSAR, and Consent Withdrawal."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from fw.core.config import get_settings
from fw.core.db import async_session_factory
from fw.main import app
from fw.modules.archive.crypto import (
    compute_sha256,
    decrypt_payload,
    encrypt_payload,
)
from fw.modules.archive.dsar import generate_employee_dsar_excel
from fw.modules.archive.service import ArchiveService
from fw.modules.attendance import TrackingGap
from fw.modules.events import MobileEventLog
from fw.modules.identity import User
from fw.modules.notifications import Alert
from fw.modules.org import Employee, RegisteredDevice
from fw.modules.sync import ConsentRecord, SyncChange


@pytest.mark.asyncio
async def test_crypto_aes256_gcm_encrypt_decrypt():
    """Verify AES-256-GCM encryption, decryption, checksums, and tamper detection."""
    secret = "test-secret-key-for-archive-encryption-12345"
    data = b"Hello, Field Worker Tracker Archive Data 2025!"

    encrypted, checksum = encrypt_payload(data, secret)
    assert len(encrypted) > len(data)
    assert compute_sha256(encrypted) == checksum

    # Decrypt with correct secret
    decrypted = decrypt_payload(encrypted, secret)
    assert decrypted == data

    # Tamper detection
    tampered = bytearray(encrypted)
    tampered[-1] ^= 0xFF  # Flip bit in auth tag
    with pytest.raises(ValueError, match="Archive decryption failed"):
        decrypt_payload(bytes(tampered), secret)

    # Wrong key detection
    with pytest.raises(ValueError, match="Archive decryption failed"):
        decrypt_payload(encrypted, "wrong-secret-key-999")


@pytest.mark.asyncio
async def test_archive_creation_verification_and_purge():
    """Test full cycle of yearly archiving, sample integrity verification, and event purge."""
    test_year = 2024
    async with async_session_factory() as session:
        # 1. Seed dummy worker, events, and visits for test_year
        emp_id = uuid4()
        dev_id = uuid4()
        emp = Employee(
            id=emp_id,
            tally_id=f"ARCH_{emp_id.hex[:6]}",
            name="Archive Test Worker",
            role="WORKER",
            country="AE",
            is_active=True,
        )
        session.add(emp)
        await session.flush()

        device = RegisteredDevice(
            id=dev_id,
            employee_id=emp_id,
            device_identifier=f"dev_{dev_id.hex[:6]}",
            platform="ANDROID",
            device_model="Pixel 7",
            os_version="Android 14",
            app_version="1.0.0",
            is_active=True,
            last_seen_at=datetime.now(UTC),
        )
        session.add(device)
        await session.flush()

        event_time = datetime(test_year, 6, 15, 10, 0, 0, tzinfo=UTC)
        ev_id = uuid4()
        ev = MobileEventLog(
            event_id=ev_id,
            employee_id=emp_id,
            device_id=dev_id,
            event_type="ENTRY",
            event_timestamp_utc=event_time,
            latitude=Decimal("25.123456"),
            longitude=Decimal("55.123456"),
            accuracy_meters=5.0,
            processing_status="PROCESSED",
        )
        session.add(ev)
        await session.flush()

        gap = TrackingGap(
            id=uuid4(),
            employee_id=emp_id,
            work_date=date(test_year, 6, 15),
            disabled_event_id=ev_id,
            started_at=event_time,
            ended_at=event_time + timedelta(minutes=30),
            duration_minutes=30,
        )
        session.add(gap)

        await session.commit()

        # 2. Run archive creation with purge
        record = await ArchiveService.create_yearly_archive(
            session=session,
            year=test_year,
            purge_live_events=True,
        )

        assert record.year == test_year
        assert record.record_count >= 1
        assert record.status == "COMPLETED"
        assert record.purged_at is not None

        # 3. Verify archive integrity
        verify_res = await ArchiveService.verify_archive(session=session, archive_id=record.id)
        assert verify_res.verified is True
        assert verify_res.record_count >= 1

        # 4. Confirm live records for 2024 were purged
        ev_check = (
            await session.execute(
                select(MobileEventLog).where(
                    MobileEventLog.employee_id == emp_id,
                    MobileEventLog.event_timestamp_utc == event_time,
                )
            )
        ).scalar_one_or_none()
        assert ev_check is None

        gap_check = (
            await session.execute(
                select(TrackingGap).where(
                    TrackingGap.employee_id == emp_id,
                    TrackingGap.work_date == date(test_year, 6, 15),
                )
            )
        ).scalar_one_or_none()
        assert gap_check is None


@pytest.mark.asyncio
async def test_retention_purge_and_employee_anonymisation():
    """Test routine retention schedule cleanup and statutory employee anonymisation."""
    async with async_session_factory() as session:
        emp_id = uuid4()
        emp = Employee(
            id=emp_id,
            tally_id=f"TERM_{emp_id.hex[:6]}",
            name="John Doe Former Worker",
            phone="+971501112233",
            email="johndoe@example.com",
            role="WORKER",
            country="AE",
            employment_end_date=date.today() - timedelta(days=800),  # > 2 years
            is_active=False,
        )
        session.add(emp)

        # Seed expired sync change (>60 days old)
        old_sync = SyncChange(
            employee_id=emp_id,
            entity_type="WORKER",
            entity_id=str(emp_id),
            entity_version=1,
            op="UPSERT",
            payload={"test": 1},
            created_at=datetime.now(UTC) - timedelta(days=90),
        )
        session.add(old_sync)

        # Seed expired resolved alert (>6 months old)
        old_alert = Alert(
            id=uuid4(),
            alert_type="SYNC_LAG",
            ref_type="DEVICE",
            title="Old alert",
            message="Old alert msg",
            status="RESOLVED",
            created_at=datetime.now(UTC) - timedelta(days=200),
            resolved_at=datetime.now(UTC) - timedelta(days=199),
        )
        session.add(old_alert)
        await session.commit()

        # Run retention purge
        purge_res = await ArchiveService.run_retention_purge(
            session=session,
            sync_days=60,
            notif_months=6,
        )
        assert purge_res.sync_changes_purged >= 1
        assert purge_res.notification_logs_purged >= 1

        # Run employee anonymisation
        anon_res = await ArchiveService.anonymise_expired_employees(
            session=session,
            older_than_years=2,
            employee_ids=[emp_id],
        )
        assert anon_res.anonymised_employees_count == 1

        # Re-fetch employee
        refreshed = await session.get(Employee, emp_id)
        assert refreshed is not None
        assert refreshed.phone is None
        assert refreshed.email is None
        assert "Anonymised Worker" in refreshed.name
        assert refreshed.anonymised_at is not None


@pytest.mark.asyncio
async def test_consent_withdrawal_and_event_rejection():
    """Verify worker consent withdrawal stops tracking and rejects incoming event batches."""
    async with async_session_factory() as session:
        emp_id = uuid4()
        emp = Employee(
            id=emp_id,
            tally_id=f"CW_{emp_id.hex[:6]}",
            name="Consent Worker",
            role="WORKER",
            country="AE",
            is_active=True,
            consent_status="ACCEPTED",
        )
        session.add(emp)
        await session.flush()

        user_id = uuid4()
        user = User(
            id=user_id,
            username=f"CW_{emp_id.hex[:6]}",
            employee_id=emp_id,
            role="WORKER",
            credential_hash="mock",
            is_active=True,
            must_change_password=False,
        )
        session.add(user)

        dev_id = uuid4()
        device = RegisteredDevice(
            id=dev_id,
            employee_id=emp_id,
            device_identifier=f"dev_{emp_id.hex[:6]}",
            platform="ANDROID",
            device_model="Pixel 8",
            os_version="Android 14",
            app_version="1.0.0",
            is_active=True,
            last_seen_at=datetime.now(UTC),
        )
        session.add(device)
        await session.flush()
        await session.commit()

        # 1. Generate auth token for mobile worker
        settings = get_settings()
        token = jwt.encode(
            {"sub": str(user_id), "role": "WORKER", "exp": datetime.now(UTC) + timedelta(hours=1)},
            settings.JWT_SECRET,
            algorithm="HS256",
        )
        headers = {"Authorization": f"Bearer {token}"}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Withdraw consent
            res_withdraw = await client.post(
                "/api/v1/mobile/consent/withdraw",
                headers=headers,
                json={"reason": "Left field role"},
            )
            assert res_withdraw.status_code == 200
            assert res_withdraw.json()["status"] == "CONSENT_WITHDRAWN"

            # Check alert was created for Admin
            alert_stmt = select(Alert).where(
                Alert.employee_id == emp_id,
                Alert.alert_type == "CONSENT_WITHDRAWN",
            )
            alert = (await session.execute(alert_stmt)).scalar_one_or_none()
            assert alert is not None
            assert alert.status == "OPEN"

            # 2. Attempt to ingest location batch -> must fail with 403 CONSENT_WITHDRAWN
            now_iso = datetime.now(UTC).isoformat()
            batch_payload = {
                "batch_id": str(uuid4()),
                "device_clock_utc": now_iso,
                "events": [
                    {
                        "event_id": str(uuid4()),
                        "event_type": "ENTRY",
                        "event_timestamp_utc": now_iso,
                        "latitude": 25.1,
                        "longitude": 55.1,
                        "accuracy_meters": 10.0,
                    }
                ],
            }
            res_ingest = await client.post(
                "/api/v1/mobile/events/batch",
                headers=headers,
                json=batch_payload,
            )
            assert res_ingest.status_code == 403
            assert res_ingest.json()["code"] == "CONSENT_WITHDRAWN"


@pytest.mark.asyncio
async def test_employee_dsar_export():
    """Verify multi-sheet DSAR Excel export generates complete data workbook."""
    async with async_session_factory() as session:
        emp_id = uuid4()
        emp = Employee(
            id=emp_id,
            tally_id=f"DSAR_{emp_id.hex[:6]}",
            name="DSAR Worker Subject",
            role="WORKER",
            country="AE",
            phone="+971500001122",
            email="dsar@example.com",
            is_active=True,
        )
        session.add(emp)

        dev_id = uuid4()
        device = RegisteredDevice(
            id=dev_id,
            employee_id=emp_id,
            device_identifier=f"dev_{dev_id.hex[:6]}",
            platform="ANDROID",
            device_model="Samsung A53",
            os_version="Android 13",
            app_version="1.0.0",
            is_active=True,
            last_seen_at=datetime.now(UTC),
        )
        session.add(device)
        await session.flush()

        consent = ConsentRecord(
            employee_id=emp_id,
            device_id=dev_id,
            policy_version=1,
            consented_at=datetime.now(UTC),
            status="ACCEPTED",
            recorded_at=datetime.now(UTC),
        )
        session.add(consent)
        await session.commit()

        excel_bytes = await generate_employee_dsar_excel(session, emp_id)
        assert len(excel_bytes) > 1000  # Valid multi-sheet Excel file


@pytest.mark.asyncio
async def test_archive_api_endpoints_and_exports():
    """Verify Admin archive, retention, DSAR, and directory export HTTP endpoints."""
    async with async_session_factory() as session:
        # Create admin user
        admin_id = uuid4()
        admin_emp_id = uuid4()
        admin_emp = Employee(
            id=admin_emp_id,
            tally_id=f"ADM_{admin_id.hex[:6]}",
            name="Admin User",
            role="ADMIN",
            country="AE",
            is_active=True,
        )
        session.add(admin_emp)
        await session.flush()

        admin_user = User(
            id=admin_id,
            username=f"ADM_{admin_id.hex[:6]}",
            employee_id=admin_emp_id,
            role="ADMIN",
            credential_hash="mock",
            is_active=True,
            must_change_password=False,
        )
        session.add(admin_user)
        await session.commit()

        settings = get_settings()
        token = jwt.encode(
            {"sub": str(admin_id), "role": "ADMIN", "exp": datetime.now(UTC) + timedelta(hours=1)},
            settings.JWT_SECRET,
            algorithm="HS256",
        )
        headers = {"Authorization": f"Bearer {token}"}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Trigger yearly archive generation via API
            gen_res = await client.post(
                "/api/v1/admin/archives/generate",
                headers=headers,
                json={"year": 2023, "purge_live_events": False},
            )
            assert gen_res.status_code == 200
            archive_data = gen_res.json()
            archive_id = archive_data["id"]
            assert archive_data["year"] == 2023
            assert "sha256_checksum" in archive_data

            # 2. List archives
            list_res = await client.get("/api/v1/admin/archives", headers=headers)
            assert list_res.status_code == 200
            assert any(a["id"] == archive_id for a in list_res.json())

            # 3. Verify archive via API
            v_res = await client.post(
                f"/api/v1/admin/archives/{archive_id}/verify", headers=headers
            )
            assert v_res.status_code == 200
            assert v_res.json()["verified"] is True

            # 4. Download encrypted archive
            dl_res = await client.get(
                f"/api/v1/admin/archives/{archive_id}/download", headers=headers
            )
            assert dl_res.status_code == 200
            assert "X-Checksum-SHA256" in dl_res.headers
            assert len(dl_res.content) > 0

            # 5. Retention purge API
            ret_res = await client.post(
                "/api/v1/admin/retention/run",
                headers=headers,
                json={"purge_sync_older_than_days": 60, "purge_notifications_older_than_months": 6},
            )
            assert ret_res.status_code == 200

            # 6. DSAR export API
            dsar_res = await client.get(
                f"/api/v1/employees/{admin_emp_id}/export-dsar", headers=headers
            )
            assert dsar_res.status_code == 200
            assert "application/vnd.openxmlformats" in dsar_res.headers.get("content-type", "")

            # 7. Employee directory export API
            emp_exp_res = await client.get("/api/v1/employees/export", headers=headers)
            assert emp_exp_res.status_code == 200
            assert "application/vnd.openxmlformats" in emp_exp_res.headers.get("content-type", "")

            # 8. Worksites export API
            site_exp_res = await client.get("/api/v1/worksites/export", headers=headers)
            assert site_exp_res.status_code == 200
            assert "application/vnd.openxmlformats" in site_exp_res.headers.get("content-type", "")

            # 9. Admin withdraw consent for employee
            aw_res = await client.post(
                f"/api/v1/employees/{admin_emp_id}/withdraw-consent",
                headers=headers,
                json={"reason": "Admin test withdrawal"},
            )
            assert aw_res.status_code == 200
            assert aw_res.json()["status"] == "CONSENT_WITHDRAWN"
