"""Integration tests for mobile sync change log, delta pulls, ack, compaction floor, and worker isolation."""

import socket
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from fw.core.db import async_session_factory, engine
from fw.core.events import HolidayChanged, event_bus
from fw.main import app
from fw.modules.identity import AuthService, User
from fw.modules.org import Employee, RegisteredDevice
from fw.modules.settings import CompanySettingValue
from fw.modules.sync.models import SyncChange
from fw.modules.sync.service import SyncService


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
async def test_mobile_sync_delta_ack_and_coalescing():
    transport = ASGITransport(app=app)
    emp_id = uuid4()
    tally_id = f"WRK{str(uuid4())[:6]}"
    today = datetime.now(UTC).date()

    async with async_session_factory() as session:
        emp = Employee(
            id=emp_id,
            tally_id=tally_id,
            name="Sync Worker",
            role="WORKER",
            country="AE",
            is_active=True,
            staff_grade_description="Technician",
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
            device_identifier="device-sync-1",
            platform="ANDROID",
            app_version="1.0.0",
            registered_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
            last_acked_cursor=0,
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
            # 1. Take initial snapshot
            snap_res = await client.get("/api/v1/mobile/sync/snapshot")
            assert snap_res.status_code == 200
            snap_data = snap_res.json()
            initial_cursor = snap_data["cursor"]

            # 2. Write 2 updates for the SAME entity (to verify coalescing) and 1 update for another
            async with async_session_factory() as session:
                await SyncService.write_sync_change(
                    session=session,
                    employee_id=emp_id,
                    entity_type="SCHEDULE_ITEM",
                    entity_id="item-101",
                    op="UPSERT",
                    payload={"sequence": 1, "version": 1},
                    entity_version=1,
                    priority=1,
                )
                await SyncService.write_sync_change(
                    session=session,
                    employee_id=emp_id,
                    entity_type="SCHEDULE_ITEM",
                    entity_id="item-101",
                    op="UPSERT",
                    payload={"sequence": 1, "version": 2, "note": "Updated time"},
                    entity_version=2,
                    priority=1,
                )
                await SyncService.write_sync_change(
                    session=session,
                    employee_id=emp_id,
                    entity_type="DAY_PLAN",
                    entity_id=today.isoformat(),
                    op="UPSERT",
                    payload={"work_date": today.isoformat(), "status": "WORKING"},
                    entity_version=1,
                    priority=1,
                )
                await session.commit()

            # 3. Pull delta changes
            changes_res = await client.get(
                f"/api/v1/mobile/sync/changes?cursor={initial_cursor}&limit=100"
            )
            assert changes_res.status_code == 200
            changes_data = changes_res.json()
            assert changes_data["resync_required"] is False
            changes = changes_data["changes"]

            # Coalescing check: item-101 should only appear ONCE with entity_version = 2
            item_101_changes = [c for c in changes if c["entity_id"] == "item-101"]
            assert len(item_101_changes) == 1
            assert item_101_changes[0]["entity_version"] == 2
            assert item_101_changes[0]["payload"]["note"] == "Updated time"

            # 4. Acknowledge sync
            next_cursor = changes_data["next_cursor"]
            ack_res = await client.post(
                "/api/v1/mobile/sync/ack",
                json={"cursor": next_cursor},
            )
            assert ack_res.status_code == 200
            assert ack_res.json()["last_acked_cursor"] == next_cursor

            # Verify device last_acked_cursor was updated in database
            async with async_session_factory() as session:
                dev = (
                    await session.execute(
                        select(RegisteredDevice).where(RegisteredDevice.employee_id == emp_id)
                    )
                ).scalar_one()
                assert dev.last_acked_cursor == next_cursor

    finally:
        async with async_session_factory() as session:
            await session.execute(delete(SyncChange).where(SyncChange.employee_id == emp_id))
            await session.execute(
                delete(RegisteredDevice).where(RegisteredDevice.employee_id == emp_id)
            )
            await session.execute(delete(User).where(User.employee_id == emp_id))
            await session.execute(delete(Employee).where(Employee.id == emp_id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
@db_required
async def test_cursor_too_old_triggers_resync():
    transport = ASGITransport(app=app)
    emp_id = uuid4()
    tally_id = f"WRK{str(uuid4())[:6]}"

    async with async_session_factory() as session:
        emp = Employee(
            id=emp_id,
            tally_id=tally_id,
            name="Floor Worker",
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
            device_identifier="device-floor-1",
            platform="ANDROID",
            registered_at=datetime.now(UTC),
            is_active=True,
        )
        session.add(device)

        # Set sync_cursor_floor setting to 500
        setting_val = CompanySettingValue(
            setting_key="sync_cursor_floor",
            country=None,
            value={"value": 500},
            effective_from=date(2026, 1, 1),
        )
        session.add(setting_val)
        await session.commit()

    token = AuthService.create_access_token(user)

    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            # Client has cursor = 100, which is below floor of 500
            res = await client.get("/api/v1/mobile/sync/changes?cursor=100")
            assert res.status_code == 200
            data = res.json()
            assert data["resync_required"] is True
            assert len(data["changes"]) == 0

    finally:
        async with async_session_factory() as session:
            await session.execute(
                delete(CompanySettingValue).where(
                    CompanySettingValue.setting_key == "sync_cursor_floor"
                )
            )
            await session.execute(
                delete(RegisteredDevice).where(RegisteredDevice.employee_id == emp_id)
            )
            await session.execute(delete(User).where(User.employee_id == emp_id))
            await session.execute(delete(Employee).where(Employee.id == emp_id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
@db_required
async def test_worker_isolation_and_holiday_update():
    """Verify data from other workers NEVER appears in a worker's sync, and holiday updates DAY_PLAN."""
    transport = ASGITransport(app=app)
    emp_a_id = uuid4()
    emp_b_id = uuid4()
    tally_a = f"WRK{str(uuid4())[:6]}"
    tally_b = f"WRK{str(uuid4())[:6]}"
    today = datetime.now(UTC).date()
    holiday_date = today + timedelta(days=2)

    async with async_session_factory() as session:
        emp_a = Employee(
            id=emp_a_id,
            tally_id=tally_a,
            name="Worker Alpha",
            role="WORKER",
            country="AE",
            is_active=True,
        )
        emp_b = Employee(
            id=emp_b_id,
            tally_id=tally_b,
            name="Worker Beta",
            role="WORKER",
            country="AE",
            is_active=True,
        )
        session.add_all([emp_a, emp_b])
        await session.flush()

        user_a = User(
            id=uuid4(),
            username=tally_a,
            credential_hash="fakehash",
            role="WORKER",
            is_active=True,
            must_change_password=False,
            employee_id=emp_a_id,
        )
        user_b = User(
            id=uuid4(),
            username=tally_b,
            credential_hash="fakehash",
            role="WORKER",
            is_active=True,
            must_change_password=False,
            employee_id=emp_b_id,
        )
        session.add_all([user_a, user_b])

        dev_a = RegisteredDevice(
            employee_id=emp_a_id,
            device_identifier="device-alpha",
            platform="ANDROID",
            registered_at=datetime.now(UTC),
            is_active=True,
        )
        dev_b = RegisteredDevice(
            employee_id=emp_b_id,
            device_identifier="device-beta",
            platform="ANDROID",
            registered_at=datetime.now(UTC),
            is_active=True,
        )
        session.add_all([dev_a, dev_b])

        # Write private schedule changes for Worker B only
        await SyncService.write_sync_change(
            session=session,
            employee_id=emp_b_id,
            entity_type="SCHEDULE_ITEM",
            entity_id="secret-item-b",
            op="UPSERT",
            payload={"secret_note": "For Beta Only"},
        )
        await session.commit()

        # Fire HolidayChanged domain event for AE
        event = HolidayChanged(country="AE", holiday_date=holiday_date)
        await event_bus.publish(event, session=session)
        await session.commit()

    token_a = AuthService.create_access_token(user_a)

    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": f"Bearer {token_a}"},
        ) as client:
            # Worker A pulls changes
            res_a = await client.get("/api/v1/mobile/sync/changes?cursor=0")
            assert res_a.status_code == 200
            changes_a = res_a.json()["changes"]

            # Isolation check: "secret-item-b" must NOT be in changes_a
            b_items = [c for c in changes_a if c["entity_id"] == "secret-item-b"]
            assert len(b_items) == 0, "Worker A saw private changes belonging to Worker B!"

            # Holiday check: DAY_PLAN for holiday_date should be updated with SKIPPED / PUBLIC_HOLIDAY
            holiday_plans = [
                c
                for c in changes_a
                if c["entity_type"] == "DAY_PLAN" and c["entity_id"] == holiday_date.isoformat()
            ]
            assert len(holiday_plans) >= 1
            assert holiday_plans[0]["payload"]["status"] == "SKIPPED"
            assert holiday_plans[0]["payload"]["marker"] == "PUBLIC_HOLIDAY"

    finally:
        async with async_session_factory() as session:
            await session.execute(
                delete(SyncChange).where(SyncChange.employee_id.in_([emp_a_id, emp_b_id]))
            )
            await session.execute(
                delete(RegisteredDevice).where(
                    RegisteredDevice.employee_id.in_([emp_a_id, emp_b_id])
                )
            )
            await session.execute(delete(User).where(User.employee_id.in_([emp_a_id, emp_b_id])))
            await session.execute(delete(Employee).where(Employee.id.in_([emp_a_id, emp_b_id])))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
@db_required
async def test_mobile_sync_snapshot_includes_base_planner_blueprint():
    """Verify that recurring Base Planner blueprint allocations (BaseRosterTemplate)

    sync to mobile snapshot as active SCHEDULE_ITEM, JOB with boundary, and WORKING DAY_PLAN,
    even when no single-day operational ScheduledWork rows exist.
    """
    from decimal import Decimal

    from fw.modules.jobs import JobItem, JobsService, Worksite
    from fw.modules.scheduling import BaseRosterEntry, BaseRosterTemplate

    transport = ASGITransport(app=app)
    emp_id = uuid4()
    tally_id = f"BP_{str(uuid4())[:6]}"
    today = datetime.now(UTC).date()
    tmpl_id = uuid4()

    async with async_session_factory() as session:
        # 1. Employee + User + Device
        emp = Employee(
            id=emp_id,
            tally_id=tally_id,
            name="Base Blueprint Worker",
            role="WORKER",
            country="AE",
            is_active=True,
            weekly_off_day="FRIDAY" if today.strftime("%A").upper() != "FRIDAY" else "SUNDAY",
            staff_grade_description="Gardener",
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
            device_identifier="device-bp-1",
            platform="ANDROID",
            app_version="1.0.0",
            registered_at=datetime.now(UTC),
            last_seen_at=datetime.now(UTC),
            last_acked_cursor=0,
            is_active=True,
        )
        session.add(device)

        # 2. Find or use active worksite + job item
        ws = (await session.execute(select(Worksite).where(Worksite.is_active.is_(True)))).scalars().first()
        assert ws is not None, "At least one worksite required in test db"

        # Ensure boundary exists on worksite
        polygon_geojson = {
            "type": "Polygon",
            "coordinates": [
                [
                    [55.2400, 25.1100],
                    [55.2500, 25.1100],
                    [55.2500, 25.1200],
                    [55.2400, 25.1200],
                    [55.2400, 25.1100],
                ]
            ],
        }
        await JobsService.update_worksite_boundary(
            session=session,
            worksite_id=ws.id,
            geojson_dict=polygon_geojson,
            actor_role="ADMIN",
        )

        ji = (await session.execute(select(JobItem).where(JobItem.worksite_id == ws.id, JobItem.is_active.is_(True)))).scalars().first()
        assert ji is not None, "At least one job item required"

        # 3. Create Base Planner Blueprint Template + Entry (NO ScheduledWork!)
        tmpl = BaseRosterTemplate(
            id=tmpl_id,
            job_item_id=ji.id,
            allocation_mode="DAY_OF_WEEK",
            start_date=today,
            is_active=True,
            version=1,
        )
        session.add(tmpl)
        await session.flush()

        entry = BaseRosterEntry(
            id=uuid4(),
            template_id=tmpl.id,
            employee_id=emp_id,
            weekday_mask="ALL",
            assigned_hours=Decimal("8.0"),
            sequence=1,
        )
        session.add(entry)
        await session.commit()

    token = AuthService.create_access_token(user)

    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            res = await client.get("/api/v1/mobile/sync/snapshot")
            assert res.status_code == 200, res.text
            snapshot = res.json()
            entities = snapshot["entities"]

            # Assert JOB entity with boundary polygon is present
            job_entities = [e for e in entities if e["entity_type"] == "JOB" and e["entity_id"] == str(ws.id)]
            assert len(job_entities) == 1, f"Expected JOB entity {ws.id} in snapshot"
            assert job_entities[0]["payload"]["boundary"] is not None
            assert job_entities[0]["payload"]["boundary"]["type"] == "Polygon"

            # Assert SCHEDULE_ITEM entities were generated from Base Blueprint
            sched_items = [e for e in entities if e["entity_type"] == "SCHEDULE_ITEM" and e["payload"]["job_id"] == str(ws.id)]
            assert len(sched_items) > 0, "Expected SCHEDULE_ITEM entities from base blueprint"

            # Assert DAY_PLAN for today is WORKING
            day_plans = [e for e in entities if e["entity_type"] == "DAY_PLAN" and e["entity_id"] == today.isoformat()]
            assert len(day_plans) == 1
            assert day_plans[0]["payload"]["status"] == "WORKING"
            assert day_plans[0]["payload"]["planned"] is not None
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(BaseRosterEntry).where(BaseRosterEntry.template_id == tmpl_id))
            await session.execute(delete(BaseRosterTemplate).where(BaseRosterTemplate.id == tmpl_id))
            await session.execute(delete(RegisteredDevice).where(RegisteredDevice.employee_id == emp_id))
            await session.execute(delete(User).where(User.employee_id == emp_id))
            await session.execute(delete(Employee).where(Employee.id == emp_id))
            await session.commit()
        await engine.dispose()
