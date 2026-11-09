import socket
from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from fw.core.db import async_session_factory, engine
from fw.main import app
from fw.modules.identity import AuthService, User, hash_password
from fw.modules.jobs.models import JobItem, Worksite
from fw.modules.org.models import Accommodation, Employee, Group, RegisteredDevice, Zone
from fw.modules.scheduling.models import ScheduledWork
from fw.modules.settings.models import TimeRule


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


@pytest.fixture(autouse=True)
async def cleanup_db_engine():
    yield
    await engine.dispose()


@db_required
@pytest.mark.asyncio
async def test_attendance_api_end_to_end():
    async with async_session_factory() as session:
        # Create test admin user & engineer user
        admin_emp_id = uuid4()
        admin_emp = Employee(
            id=admin_emp_id,
            tally_id=f"ADM_{admin_emp_id.hex[:6]}",
            name="Admin User",
            role="ADMIN",
            country="AE",
        )
        session.add(admin_emp)
        await session.flush()

        admin_user_id = uuid4()
        admin_user = User(
            id=admin_user_id,
            employee_id=admin_emp_id,
            username=f"admin_{admin_emp_id.hex[:6]}",
            credential_hash=hash_password("AdminPass123!"),
            role="ADMIN",
            is_active=True,
            must_change_password=False,
        )
        session.add(admin_user)

        # Create worker & device
        worker_id = uuid4()
        worker = Employee(
            id=worker_id,
            tally_id=f"WRK_{worker_id.hex[:6]}",
            name="Field Worker One",
            role="WORKER",
            country="AE",
            weekly_off_day="SUNDAY",
        )
        session.add(worker)
        await session.flush()

        worker_user = User(
            id=uuid4(),
            employee_id=worker_id,
            username=f"worker_{worker_id.hex[:6]}",
            credential_hash=hash_password("WorkerPass123!"),
            role="WORKER",
            is_active=True,
            must_change_password=False,
        )
        session.add(worker_user)

        device_id = uuid4()
        device = RegisteredDevice(
            id=device_id,
            employee_id=worker_id,
            device_identifier=f"dev_{worker_id.hex[:6]}",
            platform="ANDROID",
            is_active=True,
            last_seen_at=datetime.now(UTC),
        )
        session.add(device)

        # Create test Group & Zone
        grp_id = uuid4()
        group = Group(id=grp_id, code=f"GRP_{grp_id.hex[:4]}", name="Test Group")
        session.add(group)

        zone_id = uuid4()
        zone = Zone(id=zone_id, code=f"ZN_{zone_id.hex[:4]}", name="Test Zone")
        session.add(zone)
        await session.flush()

        # Create worksite with boundary polygon
        # [55.20, 25.10] to [55.21, 25.11]
        site_id = uuid4()
        poly_wkt = (
            "SRID=4326;POLYGON((55.20 25.10, 55.21 25.10, 55.21 25.11, 55.20 25.11, 55.20 25.10))"
        )
        site = Worksite(
            id=site_id,
            job_number=f"JN{site_id.hex[:6]}",
            job_name="Silicon Oasis Test Site",
            group_id=grp_id,
            zone_id=zone_id,
            country="AE",
            is_outdoor=True,
            boundary=poly_wkt,
            is_active=True,
        )
        session.add(site)

        job_item_id = uuid4()
        job_item = JobItem(
            id=job_item_id,
            worksite_id=site_id,
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
            break_override_minutes=30,
            is_active=True,
        )
        session.add(job_item)
        await session.flush()

        # Create accommodation polygon
        # [55.40, 25.15] to [55.41, 25.16]
        acc_id = uuid4()
        acc_poly_wkt = (
            "SRID=4326;POLYGON((55.40 25.15, 55.41 25.15, 55.41 25.16, 55.40 25.16, 55.40 25.15))"
        )
        acc = Accommodation(
            id=acc_id,
            accommodation_code=f"ACC_{acc_id.hex[:4]}",
            name="Warsan Camp Test",
            boundary=acc_poly_wkt,
            is_active=True,
        )
        session.add(acc)
        worker.accommodation_id = acc_id

        # Scheduled work today (8h assigned at site)
        work_date = date(2026, 11, 4)  # Wednesday (non-holiday)
        sw = ScheduledWork(
            id=uuid4(),
            employee_id=worker_id,
            work_date=work_date,
            worksite_id=site_id,
            job_item_id=job_item_id,
            assigned_hours=Decimal("8.0"),
            sequence=1,
            status="ACTIVE",
            source="DIRECT",
        )
        session.add(sw)

        # Time rule (5:00 / 6:00 / 0:30 / 15:30 / 17:00)
        tr = TimeRule(
            id=uuid4(),
            name="Company Standard Schedule",
            country="AE",
            scope_type="COMPANY",
            applies_to="ALL",
            start_date=date(2026, 1, 1),
            accommodation_start=time(5, 0),
            first_site_start=time(6, 0),
            break_minutes=30,
            last_site_end=time(15, 30),
            accommodation_end=time(17, 0),
            is_active=True,
        )
        session.add(tr)
        await session.commit()

    # Generate tokens
    admin_token = AuthService.create_access_token(admin_user)
    worker_token = AuthService.create_access_token(worker_user)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Ingest event batch for worker:
        # Camp exit 05:20, Site entry 06:20, Site exit 15:20, Camp entry 16:50 (Client's scenario H: 11:30 total, 08:30 worked, var -30m)
        batch_id = uuid4()
        now_utc = datetime(2026, 11, 4, 17, 0, tzinfo=UTC)
        events_payload = {
            "batch_id": str(batch_id),
            "device_clock_utc": now_utc.isoformat(),
            "events": [
                # Camp exit at 05:20 (point just outside camp: 55.405, 25.145)
                {
                    "event_id": str(uuid4()),
                    "event_type": "EXIT",
                    "event_timestamp_utc": datetime(2026, 11, 4, 5, 20, tzinfo=UTC).isoformat(),
                    "latitude": 25.145,
                    "longitude": 55.405,
                    "accuracy_meters": 10.0,
                    "accommodation_id": str(acc_id),
                },
                # First site entry at 06:20 (point inside site: 55.205, 25.105)
                {
                    "event_id": str(uuid4()),
                    "event_type": "ENTRY",
                    "event_timestamp_utc": datetime(2026, 11, 4, 6, 20, tzinfo=UTC).isoformat(),
                    "latitude": 25.105,
                    "longitude": 55.205,
                    "accuracy_meters": 10.0,
                    "job_id": str(site_id),
                },
                # Site exit at 15:20 (point outside site: 55.195, 25.095)
                {
                    "event_id": str(uuid4()),
                    "event_type": "EXIT",
                    "event_timestamp_utc": datetime(2026, 11, 4, 15, 20, tzinfo=UTC).isoformat(),
                    "latitude": 25.095,
                    "longitude": 55.195,
                    "accuracy_meters": 10.0,
                    "job_id": str(site_id),
                },
                # Camp return at 16:50 (point inside camp: 55.405, 25.155)
                {
                    "event_id": str(uuid4()),
                    "event_type": "ENTRY",
                    "event_timestamp_utc": datetime(2026, 11, 4, 16, 50, tzinfo=UTC).isoformat(),
                    "latitude": 25.155,
                    "longitude": 55.405,
                    "accuracy_meters": 10.0,
                    "accommodation_id": str(acc_id),
                },
            ],
        }

        # Submit batch as authenticated worker device
        res = await client.post(
            "/api/v1/mobile/events/batch",
            json=events_payload,
            headers={"Authorization": f"Bearer {worker_token}"},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert len(body["results"]) == 4
        assert all(r["status"] == "ACCEPTED" for r in body["results"])

        # 2. Replay identical batch -> Checklist item: "Replaying a batch creates no duplicates"
        replay_res = await client.post(
            "/api/v1/mobile/events/batch",
            json=events_payload,
            headers={"Authorization": f"Bearer {worker_token}"},
        )
        assert replay_res.status_code == 200
        replay_body = replay_res.json()
        assert all(r["status"] == "DUPLICATE" for r in replay_body["results"])

        # 3. Query attendance list as Admin -> record should be PENDING_REVIEW
        att_res = await client.get(
            f"/api/v1/attendance?employee_id={worker_id}&from_date=2026-11-04&to_date=2026-11-04",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert att_res.status_code == 200, att_res.text
        att_list = att_res.json()
        assert att_list["total"] == 1
        record = att_list["items"][0]
        rec_id = record["id"]

        assert record["business_status"] == "PRESENT"
        assert record["review_status"] == "PENDING_REVIEW"
        cur_calc = record["current_calculation"]
        assert cur_calc is not None
        assert cur_calc["worked_minutes"] == 510  # 08:30
        assert cur_calc["shift_span_minutes"] == 690  # 11:30
        assert (
            cur_calc["variation_minutes"] == 30
        )  # 510 - 480 required = +30 (and standard 8h -> 30m OT1)
        assert cur_calc["ot1_minutes"] == 30

        # 4. Check timeline endpoint
        timeline_res = await client.get(
            f"/api/v1/attendance/{rec_id}/timeline",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert timeline_res.status_code == 200
        timeline_data = timeline_res.json()
        assert len(timeline_data["timeline_items"]) >= 2

        # 5. Check Approvals Inbox (`GET /api/v1/approvals`)
        approvals_res = await client.get(
            "/api/v1/approvals",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert approvals_res.status_code == 200
        approvals_data = approvals_res.json()
        assert approvals_data["counts"]["attendance"] >= 1
        att_ids = [r["id"] for r in approvals_data["attendance_rows"]]
        assert rec_id in att_ids

        # 6. Supervisor adds comment
        comment_res = await client.post(
            f"/api/v1/attendance/{rec_id}/comments",
            json={
                "comment_type": "EXPLANATION",
                "comment_text": "Late morning departure due to traffic on Manama St.",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert comment_res.status_code == 200
        assert (
            comment_res.json()["comment_text"]
            == "Late morning departure due to traffic on Manama St."
        )

        # 7. Engineer rejects decision (must fail if comment missing)
        fail_dec = await client.post(
            f"/api/v1/attendance/{rec_id}/decisions",
            json={"decision": "REJECTED", "comment": None},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert fail_dec.status_code == 422

        # Engineer rejects with explanation
        rej_res = await client.post(
            f"/api/v1/attendance/{rec_id}/decisions",
            json={"decision": "REJECTED", "comment": "Please provide supervisor gate pass proof."},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert rej_res.status_code == 200

        # Check status is now REJECTED
        detail_res = await client.get(
            f"/api/v1/attendance/{rec_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert detail_res.json()["review_status"] == "REJECTED"

        # Supervisor adding another comment resets status to PENDING_REVIEW
        comm2 = await client.post(
            f"/api/v1/attendance/{rec_id}/comments",
            json={
                "comment_type": "ATTENDANCE_CORRECTION",
                "comment_text": "Gate pass #8812 verified and attached.",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert comm2.status_code == 200
        detail2 = await client.get(
            f"/api/v1/attendance/{rec_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert detail2.json()["review_status"] == "PENDING_REVIEW"

        # Engineer approves
        app_res = await client.post(
            f"/api/v1/attendance/{rec_id}/decisions",
            json={"decision": "APPROVED", "comment": "Approved per gate pass."},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert app_res.status_code == 200
        detail3 = await client.get(
            f"/api/v1/attendance/{rec_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert detail3.json()["review_status"] == "APPROVED"
