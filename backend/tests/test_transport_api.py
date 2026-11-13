"""Tests for Phase 10: Transport, Vehicles, Drivers, and Transport Runs Sync."""

import socket
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from fw.core.db import async_session_factory
from fw.core.events import ScheduledWorkChanged, event_bus
from fw.main import app
from fw.modules.identity import AuthService, User
from fw.modules.jobs import JobItem, Worksite
from fw.modules.org import Accommodation, Employee, Group, Zone
from fw.modules.scheduling import ScheduledWork
from fw.modules.sync import SyncService
from fw.modules.transport import (
    Vehicle,
)


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


async def _get_or_create_group_and_zone(session) -> tuple[uuid.UUID, uuid.UUID]:
    group = (
        await session.execute(select(Group).where(Group.code == "GRP_TRANS_10"))
    ).scalar_one_or_none()
    if not group:
        group = Group(
            id=uuid.uuid4(),
            code="GRP_TRANS_10",
            name="Transport Test Group",
            is_active=True,
        )
        session.add(group)

    zone = (
        await session.execute(select(Zone).where(Zone.code == "ZONE_TRANS_10"))
    ).scalar_one_or_none()
    if not zone:
        zone = Zone(
            id=uuid.uuid4(),
            code="ZONE_TRANS_10",
            name="Transport Test Zone",
            is_active=True,
        )
        session.add(zone)

    await session.flush()
    return group.id, zone.id


@pytest.fixture
async def admin_client():
    if not is_db_available():
        pytest.skip("PostgreSQL not available on localhost:5432")

    async with async_session_factory() as session:
        user = (
            await session.execute(select(User).where(User.username == "ADMIN001"))
        ).scalar_one_or_none()

        if not user:
            admin_id = uuid.uuid4()
            emp_id = uuid.uuid4()
            emp = Employee(
                id=emp_id,
                tally_id=f"ADM{str(uuid.uuid4())[:6]}",
                name="Admin User",
                role="ADMIN",
                country="AE",
                is_active=True,
            )
            session.add(emp)
            await session.flush()

            user = User(
                id=admin_id,
                employee_id=emp_id,
                username="ADMIN001",
                credential_hash="fakehash",
                role="ADMIN",
                is_active=True,
                must_change_password=False,
            )
            session.add(user)
            await session.commit()

        token = AuthService.create_access_token(user)

    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
        yield client


@pytest.mark.asyncio
@db_required
async def test_vehicles_crud(admin_client: AsyncClient):
    # 1. Create Vehicle
    create_resp = await admin_client.post(
        "/api/v1/vehicles",
        json={"label": "Hiace Bus 01", "type": "VAN", "notes": "14 seater"},
    )
    assert create_resp.status_code == 201
    veh_data = create_resp.json()
    veh_id = veh_data["id"]
    assert veh_data["label"] == "Hiace Bus 01"
    assert veh_data["is_active"] is True

    # 2. List Vehicles
    list_resp = await admin_client.get("/api/v1/vehicles")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert any(v["id"] == veh_id for v in items)

    # 3. Update Vehicle
    patch_resp = await admin_client.patch(
        f"/api/v1/vehicles/{veh_id}",
        json={"label": "Hiace Bus 01 Renamed", "notes": "Updated note"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["label"] == "Hiace Bus 01 Renamed"
    assert patch_resp.json()["notes"] == "Updated note"


@pytest.mark.asyncio
@db_required
async def test_drivers_list(admin_client: AsyncClient):
    async with async_session_factory() as session:
        driver_emp = Employee(
            id=uuid.uuid4(),
            name="Test Driver Rashid",
            tally_id=f"D-{uuid.uuid4().hex[:6]}",
            role="WORKER",
            is_driver=True,
            country="AE",
            is_active=True,
        )
        session.add(driver_emp)
        await session.commit()

    resp = await admin_client.get("/api/v1/drivers")
    assert resp.status_code == 200
    drivers = resp.json()
    assert any(d["employee_id"] == str(driver_emp.id) for d in drivers)


@pytest.mark.asyncio
@db_required
async def test_worker_cannot_be_on_two_morning_runs(admin_client: AsyncClient):
    test_date = date.today() + timedelta(days=20)

    async with async_session_factory() as session:
        gid, zid = await _get_or_create_group_and_zone(session)
        # Create 2 drivers
        driver1 = Employee(
            id=uuid.uuid4(),
            name="Driver One",
            tally_id=f"D1-{uuid.uuid4().hex[:4]}",
            role="WORKER",
            is_driver=True,
            country="AE",
            is_active=True,
        )
        driver2 = Employee(
            id=uuid.uuid4(),
            name="Driver Two",
            tally_id=f"D2-{uuid.uuid4().hex[:4]}",
            role="WORKER",
            is_driver=True,
            country="AE",
            is_active=True,
        )
        # Create passenger worker
        worker = Employee(
            id=uuid.uuid4(),
            name="Passenger Worker",
            tally_id=f"W-{uuid.uuid4().hex[:4]}",
            role="WORKER",
            is_driver=False,
            country="AE",
            is_active=True,
        )
        # Create worksite
        site = Worksite(
            id=uuid.uuid4(),
            job_number=f"JOB-{uuid.uuid4().hex[:5]}",
            job_name="Site Alpha",
            group_id=gid,
            zone_id=zid,
            country="AE",
            is_active=True,
        )
        session.add_all([driver1, driver2, worker, site])
        await session.commit()

    # Create Run 1 with Worker
    run1_resp = await admin_client.post(
        "/api/v1/transport-runs",
        json={
            "run_date": test_date.isoformat(),
            "direction": "MORNING",
            "driver_id": str(driver1.id),
            "stops": [
                {
                    "sequence": 1,
                    "stop_type": "SITE",
                    "worksite_id": str(site.id),
                    "passengers": [{"employee_id": str(worker.id)}],
                }
            ],
        },
    )
    assert run1_resp.status_code == 201

    # Attempt to assign the same worker to Run 2 in MORNING on same date
    run2_resp = await admin_client.post(
        "/api/v1/transport-runs",
        json={
            "run_date": test_date.isoformat(),
            "direction": "MORNING",
            "driver_id": str(driver2.id),
            "stops": [
                {
                    "sequence": 1,
                    "stop_type": "SITE",
                    "worksite_id": str(site.id),
                    "passengers": [{"employee_id": str(worker.id)}],
                }
            ],
        },
    )
    # Must reject with 409 Conflict
    assert run2_resp.status_code == 409
    error_data = run2_resp.json()
    assert error_data["code"] == "WORKER_RUN_CONFLICT"


@pytest.mark.asyncio
@db_required
async def test_driver_cannot_have_overlapping_runs(admin_client: AsyncClient):
    test_date = date.today() + timedelta(days=21)

    async with async_session_factory() as session:
        gid, zid = await _get_or_create_group_and_zone(session)
        driver = Employee(
            id=uuid.uuid4(),
            name="Driver Solo",
            tally_id=f"DS-{uuid.uuid4().hex[:4]}",
            role="WORKER",
            is_driver=True,
            country="AE",
            is_active=True,
        )
        site = Worksite(
            id=uuid.uuid4(),
            job_number=f"JOB-{uuid.uuid4().hex[:5]}",
            job_name="Site Beta",
            group_id=gid,
            zone_id=zid,
            country="AE",
            is_active=True,
        )
        session.add_all([driver, site])
        await session.commit()

    # Run 1
    resp1 = await admin_client.post(
        "/api/v1/transport-runs",
        json={
            "run_date": test_date.isoformat(),
            "direction": "MORNING",
            "driver_id": str(driver.id),
            "stops": [
                {"sequence": 1, "stop_type": "SITE", "worksite_id": str(site.id), "passengers": []}
            ],
        },
    )
    assert resp1.status_code == 201

    # Overlapping Run 2 with same driver on same date/direction
    resp2 = await admin_client.post(
        "/api/v1/transport-runs",
        json={
            "run_date": test_date.isoformat(),
            "direction": "MORNING",
            "driver_id": str(driver.id),
            "stops": [
                {"sequence": 1, "stop_type": "SITE", "worksite_id": str(site.id), "passengers": []}
            ],
        },
    )
    assert resp2.status_code == 409
    assert resp2.json()["code"] == "DRIVER_ALREADY_ASSIGNED"


@pytest.mark.asyncio
@db_required
async def test_unassigned_scheduled_workers_listed(admin_client: AsyncClient):
    test_date = date.today() + timedelta(days=22)

    async with async_session_factory() as session:
        gid, zid = await _get_or_create_group_and_zone(session)
        acc = Accommodation(
            id=uuid.uuid4(),
            accommodation_code=f"ACC-{uuid.uuid4().hex[:4]}",
            name="Sonapur Camp 1",
            is_active=True,
        )
        worker = Employee(
            id=uuid.uuid4(),
            name="Unassigned Field Guy",
            tally_id=f"U-{uuid.uuid4().hex[:4]}",
            role="WORKER",
            accommodation_id=acc.id,
            country="AE",
            is_active=True,
        )
        site = Worksite(
            id=uuid.uuid4(),
            job_number=f"JOB-{uuid.uuid4().hex[:5]}",
            job_name="Marina Tower Landscaping",
            group_id=gid,
            zone_id=zid,
            country="AE",
            is_active=True,
        )
        item = JobItem(
            id=uuid.uuid4(),
            worksite_id=site.id,
            sub_item_code="A",
            planned_grade_code="GDN",
            staff_grade_description="Gardener",
            frequency_unit="WEEK",
            occurrences_per_period=Decimal("1"),
            period_interval=1,
            required_staff_count=1,
            hours_per_occurrence_per_staff=Decimal("8"),
            start_date=test_date - timedelta(days=10),
            deployment_type="PERMANENT",
        )
        sw = ScheduledWork(
            id=uuid.uuid4(),
            employee_id=worker.id,
            worksite_id=site.id,
            job_item_id=item.id,
            work_date=test_date,
            assigned_hours=Decimal("8.00"),
            status="ACTIVE",
            source="STANDING",
        )
        session.add_all([acc, worker, site, item, sw])
        await session.commit()

    resp = await admin_client.get(
        f"/api/v1/transport-runs/unassigned-workers?run_date={test_date.isoformat()}&direction=MORNING"
    )
    assert resp.status_code == 200
    unassigned = resp.json()
    assert any(u["employee_id"] == str(worker.id) for u in unassigned)


@pytest.mark.asyncio
@db_required
async def test_publish_and_mobile_sync_privacy(admin_client: AsyncClient):
    test_date = date.today() + timedelta(days=23)

    async with async_session_factory() as session:
        gid, zid = await _get_or_create_group_and_zone(session)
        driver = Employee(
            id=uuid.uuid4(),
            name="Sync Driver Ali",
            tally_id=f"D-{uuid.uuid4().hex[:4]}",
            role="WORKER",
            phone="+971501112233",
            is_driver=True,
            country="AE",
            is_active=True,
        )
        pass1 = Employee(
            id=uuid.uuid4(),
            name="Passenger One",
            tally_id=f"TALLY-P1-{uuid.uuid4().hex[:4]}",
            role="WORKER",
            country="AE",
            is_active=True,
        )
        pass2 = Employee(
            id=uuid.uuid4(),
            name="Passenger Two",
            tally_id=f"TALLY-P2-{uuid.uuid4().hex[:4]}",
            role="WORKER",
            country="AE",
            is_active=True,
        )
        vehicle = Vehicle(
            id=uuid.uuid4(),
            label="White Coaster",
            type="BUS",
            is_active=True,
        )
        site1 = Worksite(
            id=uuid.uuid4(),
            job_number=f"JOB-S1-{uuid.uuid4().hex[:4]}",
            job_name="Site One Park",
            group_id=gid,
            zone_id=zid,
            country="AE",
            is_active=True,
        )
        site2 = Worksite(
            id=uuid.uuid4(),
            job_number=f"JOB-S2-{uuid.uuid4().hex[:4]}",
            job_name="Site Two Villa",
            group_id=gid,
            zone_id=zid,
            country="AE",
            is_active=True,
        )
        session.add_all([driver, pass1, pass2, vehicle, site1, site2])
        await session.commit()

    # Create run
    run_resp = await admin_client.post(
        "/api/v1/transport-runs",
        json={
            "run_date": test_date.isoformat(),
            "direction": "MORNING",
            "driver_id": str(driver.id),
            "vehicle_id": str(vehicle.id),
            "stops": [
                {
                    "sequence": 1,
                    "stop_type": "SITE",
                    "worksite_id": str(site1.id),
                    "passengers": [{"employee_id": str(pass1.id)}],
                },
                {
                    "sequence": 2,
                    "stop_type": "SITE",
                    "worksite_id": str(site2.id),
                    "passengers": [{"employee_id": str(pass2.id)}],
                },
            ],
        },
    )
    assert run_resp.status_code == 201
    run_id = run_resp.json()["id"]

    # Publish run
    pub_resp = await admin_client.post(f"/api/v1/transport-runs/{run_id}/publish")
    assert pub_resp.status_code == 200
    assert pub_resp.json()["status"] == "PUBLISHED"

    # Verify Mobile Snapshot for DRIVER
    async with async_session_factory() as session:
        driver_snap = await SyncService.build_snapshot(session, driver.id, window_days=30)
        driver_run_entities = [e for e in driver_snap.entities if e.entity_type == "TRANSPORT_RUN"]
        assert len(driver_run_entities) >= 1
        driver_run = next(e for e in driver_run_entities if e.entity_id == str(run_id))
        assert driver_run.payload is not None
        # Driver sees all stops (2 stops)
        assert len(driver_run.payload["stops"]) == 2
        # Driver sees all passenger names across stops
        all_pass_names = [p["name"] for st in driver_run.payload["stops"] for p in st["passengers"]]
        assert "Passenger One" in all_pass_names
        assert "Passenger Two" in all_pass_names

        # Verify Mobile Snapshot for PASSENGER 1 (Privacy check)
        p1_snap = await SyncService.build_snapshot(session, pass1.id, window_days=30)
        p1_run_entities = [e for e in p1_snap.entities if e.entity_type == "TRANSPORT_RUN"]
        assert len(p1_run_entities) >= 1
        p1_run = next(e for e in p1_run_entities if e.entity_id == str(run_id))
        assert p1_run.payload is not None
        # Passenger sees vehicle and driver
        assert p1_run.payload["vehicle_label"] == "White Coaster"
        assert p1_run.payload["driver"]["name"] == "Sync Driver Ali"
        # Passenger sees ONLY their own stop (1 stop, not 2)
        assert len(p1_run.payload["stops"]) == 1
        assert p1_run.payload["stops"][0]["job_id"] == str(site1.id)
        # Passenger sees ONLY their own name, NOT passenger 2!
        p1_stop_passengers = p1_run.payload["stops"][0]["passengers"]
        assert len(p1_stop_passengers) == 1
        assert p1_stop_passengers[0]["name"] == "Passenger One"


@pytest.mark.asyncio
@db_required
async def test_schedule_reassignment_flags_needs_update(admin_client: AsyncClient):
    test_date = date.today() + timedelta(days=24)

    async with async_session_factory() as session:
        gid, zid = await _get_or_create_group_and_zone(session)
        driver = Employee(
            id=uuid.uuid4(),
            name="Driver Hassan",
            tally_id=f"D-{uuid.uuid4().hex[:4]}",
            role="WORKER",
            is_driver=True,
            country="AE",
            is_active=True,
        )
        worker = Employee(
            id=uuid.uuid4(),
            name="Moved Worker",
            tally_id=f"M-{uuid.uuid4().hex[:4]}",
            role="WORKER",
            country="AE",
            is_active=True,
        )
        site = Worksite(
            id=uuid.uuid4(),
            job_number=f"JOB-{uuid.uuid4().hex[:4]}",
            job_name="Original Worksite",
            group_id=gid,
            zone_id=zid,
            country="AE",
            is_active=True,
        )
        session.add_all([driver, worker, site])
        await session.commit()

    # Create & publish run
    run_resp = await admin_client.post(
        "/api/v1/transport-runs",
        json={
            "run_date": test_date.isoformat(),
            "direction": "MORNING",
            "driver_id": str(driver.id),
            "stops": [
                {
                    "sequence": 1,
                    "stop_type": "SITE",
                    "worksite_id": str(site.id),
                    "passengers": [{"employee_id": str(worker.id)}],
                }
            ],
        },
    )
    run_id = run_resp.json()["id"]
    await admin_client.post(f"/api/v1/transport-runs/{run_id}/publish")

    # Verify needs_update is initially False
    get_res = await admin_client.get(f"/api/v1/transport-runs/{run_id}")
    assert get_res.json()["needs_update"] is False

    # Trigger ScheduledWorkChanged domain event for this worker and date
    async with async_session_factory() as session:
        await event_bus.publish(
            ScheduledWorkChanged(employee_ids=[worker.id], work_date=test_date),
            session=session,
        )
        await session.commit()

    # Verify run is now flagged needs_update = True
    get_res2 = await admin_client.get(f"/api/v1/transport-runs/{run_id}")
    assert get_res2.json()["needs_update"] is True


@pytest.mark.asyncio
@db_required
async def test_copy_runs_omits_unscheduled_worker(admin_client: AsyncClient):
    src_date = date.today() + timedelta(days=25)
    tgt_date = date.today() + timedelta(days=26)

    async with async_session_factory() as session:
        gid, zid = await _get_or_create_group_and_zone(session)
        driver = Employee(
            id=uuid.uuid4(),
            name="Driver Tariq",
            tally_id=f"D-{uuid.uuid4().hex[:4]}",
            role="WORKER",
            is_driver=True,
            country="AE",
            is_active=True,
        )
        worker_scheduled = Employee(
            id=uuid.uuid4(),
            name="Worker Active",
            tally_id=f"T-ACT-{uuid.uuid4().hex[:4]}",
            role="WORKER",
            country="AE",
            is_active=True,
        )
        worker_unscheduled = Employee(
            id=uuid.uuid4(),
            name="Worker Off",
            tally_id=f"T-OFF-{uuid.uuid4().hex[:4]}",
            role="WORKER",
            country="AE",
            is_active=True,
        )
        site = Worksite(
            id=uuid.uuid4(),
            job_number=f"JOB-G-{uuid.uuid4().hex[:4]}",
            job_name="Site Gamma",
            group_id=gid,
            zone_id=zid,
            country="AE",
            is_active=True,
        )
        item = JobItem(
            id=uuid.uuid4(),
            worksite_id=site.id,
            sub_item_code="A",
            planned_grade_code="MSN",
            staff_grade_description="Mason",
            frequency_unit="WEEK",
            occurrences_per_period=Decimal("1"),
            period_interval=1,
            required_staff_count=1,
            hours_per_occurrence_per_staff=Decimal("8"),
            start_date=src_date - timedelta(days=10),
            deployment_type="PERMANENT",
        )
        # Only worker_scheduled has ScheduledWork on tgt_date
        sw_tgt = ScheduledWork(
            id=uuid.uuid4(),
            employee_id=worker_scheduled.id,
            worksite_id=site.id,
            job_item_id=item.id,
            work_date=tgt_date,
            assigned_hours=Decimal("8.00"),
            status="ACTIVE",
            source="STANDING",
        )
        session.add_all([driver, worker_scheduled, worker_unscheduled, site, item, sw_tgt])
        await session.commit()

    # Create run on src_date with BOTH workers
    run_resp = await admin_client.post(
        "/api/v1/transport-runs",
        json={
            "run_date": src_date.isoformat(),
            "direction": "MORNING",
            "driver_id": str(driver.id),
            "stops": [
                {
                    "sequence": 1,
                    "stop_type": "SITE",
                    "worksite_id": str(site.id),
                    "passengers": [
                        {"employee_id": str(worker_scheduled.id)},
                        {"employee_id": str(worker_unscheduled.id)},
                    ],
                }
            ],
        },
    )
    assert run_resp.status_code == 201

    # Copy run from src_date to tgt_date
    copy_resp = await admin_client.post(
        "/api/v1/transport-runs/copy",
        json={"source_date": src_date.isoformat(), "target_date": tgt_date.isoformat()},
    )
    assert copy_resp.status_code == 200
    copy_data = copy_resp.json()

    # Verify created run has only worker_scheduled
    created_runs = copy_data["created_runs"]
    assert len(created_runs) == 1
    new_passengers = [p["employee_id"] for st in created_runs[0]["stops"] for p in st["passengers"]]
    assert str(worker_scheduled.id) in new_passengers
    assert str(worker_unscheduled.id) not in new_passengers

    # Verify omitted_passengers contains worker_unscheduled with reason
    omitted = copy_data["omitted_passengers"]
    assert any(
        o["employee_id"] == str(worker_unscheduled.id)
        and "Not scheduled on target date" in o["reason"]
        for o in omitted
    )


@pytest.mark.asyncio
@db_required
async def test_suggest_runs_endpoint(admin_client: AsyncClient):
    sug_date = date.today() + timedelta(days=28)

    async with async_session_factory() as session:
        gid, zid = await _get_or_create_group_and_zone(session)
        driver = Employee(
            id=uuid.uuid4(),
            name="Driver Suggest",
            tally_id=f"D-SUG-{uuid.uuid4().hex[:4]}",
            role="WORKER",
            is_driver=True,
            country="AE",
            is_active=True,
        )
        acc = Accommodation(
            id=uuid.uuid4(),
            accommodation_code=f"ACC-SUG-{uuid.uuid4().hex[:4]}",
            name="Muhaisnah Camp",
            is_active=True,
        )
        worker1 = Employee(
            id=uuid.uuid4(),
            name="Sug Worker 1",
            tally_id=f"W1-{uuid.uuid4().hex[:4]}",
            role="WORKER",
            accommodation_id=acc.id,
            country="AE",
            is_active=True,
        )
        worker2 = Employee(
            id=uuid.uuid4(),
            name="Sug Worker 2",
            tally_id=f"W2-{uuid.uuid4().hex[:4]}",
            role="WORKER",
            accommodation_id=acc.id,
            country="AE",
            is_active=True,
        )
        site = Worksite(
            id=uuid.uuid4(),
            job_number=f"JOB-SUG-{uuid.uuid4().hex[:4]}",
            job_name="Airport Landscaping",
            group_id=gid,
            zone_id=zid,
            country="AE",
            is_active=True,
        )
        item = JobItem(
            id=uuid.uuid4(),
            worksite_id=site.id,
            sub_item_code="A",
            planned_grade_code="GDN",
            staff_grade_description="Gardener",
            frequency_unit="WEEK",
            occurrences_per_period=Decimal("1"),
            period_interval=1,
            required_staff_count=2,
            hours_per_occurrence_per_staff=Decimal("8"),
            start_date=sug_date - timedelta(days=10),
            deployment_type="PERMANENT",
        )
        sw1 = ScheduledWork(
            id=uuid.uuid4(),
            employee_id=worker1.id,
            worksite_id=site.id,
            job_item_id=item.id,
            work_date=sug_date,
            assigned_hours=Decimal("8.00"),
            status="ACTIVE",
            source="STANDING",
        )
        sw2 = ScheduledWork(
            id=uuid.uuid4(),
            employee_id=worker2.id,
            worksite_id=site.id,
            job_item_id=item.id,
            work_date=sug_date,
            assigned_hours=Decimal("8.00"),
            status="ACTIVE",
            source="STANDING",
        )
        session.add_all([driver, acc, worker1, worker2, site, item, sw1, sw2])
        await session.commit()

    # Call suggest endpoint
    resp = await admin_client.post(
        "/api/v1/transport-runs/suggest",
        json={"run_date": sug_date.isoformat(), "direction": "MORNING"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["suggested_runs"]) >= 1
    run = data["suggested_runs"][0]
    assert run["driver_id"] is not None
    # Stop 1 is Accommodation, Stop 2 is Site
    assert len(run["stops"]) == 2
    assert run["stops"][0]["stop_type"] == "ACCOMMODATION"
    assert run["stops"][0]["accommodation_id"] == str(acc.id)
    assert run["stops"][1]["stop_type"] == "SITE"
    assert run["stops"][1]["worksite_id"] == str(site.id)
    # Passengers on stop 2 include both workers
    pass_ids = [p["employee_id"] for p in run["stops"][1]["passengers"]]
    assert str(worker1.id) in pass_ids
    assert str(worker2.id) in pass_ids
