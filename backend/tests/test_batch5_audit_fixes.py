"""Tests for Batch 5 audit fixes: OT2 calculation, worker scheduler, stream tickets, and device revocation."""

from datetime import UTC, date, datetime, time
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from fw.core.db import async_session_factory
from fw.main import create_app
from fw.modules.audit.models import AuditLog
from fw.modules.events.live_publisher import stream_ticket_manager
from fw.modules.events.models import StreamTicket
from fw.modules.identity import AuthService, User
from fw.modules.notifications.models import Alert
from fw.modules.org.models import Employee, RegisteredDevice
from fw.rules.attendance.engine import (
    ConstructedVisit,
    DailyCalculationInputs,
    ScheduledAssignment,
    compute_daily_attendance,
)
from fw.rules.scheduling.reassignment import validate_reassignment_notice
from fw.rules.time_rules import ResolvedTimeSchedule
from fw.worker import WorkerScheduler


def make_schedule(break_m: int = 30) -> ResolvedTimeSchedule:
    return ResolvedTimeSchedule(
        accommodation_start=time(5, 0),
        first_site_start=time(6, 0),
        break_minutes=break_m,
        last_site_end=time(15, 30),
        accommodation_end=time(17, 0),
        planned_total_minutes=720,
        planned_worked_minutes=540,
        standard_hours_change_minutes=0,
        has_accommodation=True,
        winning_rule_id=None,
        winning_rule_name="Default Rule",
    )


def test_ot2_on_worker_weekly_off():
    """DEC-01: All worked hours on the worker's own weekly off day are OT2."""
    work_date = date(2026, 11, 15)  # Sunday
    site1 = uuid4()
    visits = [
        ConstructedVisit(
            work_date=work_date,
            place_type="SITE",
            worksite_id=site1,
            accommodation_id=None,
            entry_event_id=uuid4(),
            exit_event_id=uuid4(),
            entry_at=datetime(2026, 11, 15, 6, 0, tzinfo=UTC),
            exit_at=datetime(2026, 11, 15, 14, 30, tzinfo=UTC),
            exit_inferred=False,
            last_inside_at=datetime(2026, 11, 15, 14, 30, tzinfo=UTC),
            counts_as_completed=True,
            duration_minutes=510,
        )
    ]
    calc = compute_daily_attendance(
        DailyCalculationInputs(
            employee_id=uuid4(),
            tally_id="1001",
            work_date=work_date,
            is_driver=False,
            has_accommodation=True,
            standard_hours=8.0,
            schedule=make_schedule(break_m=30),
            assignments=[],
            visits=visits,
            gaps=[],
            is_public_holiday=False,
            is_weekly_off=True,
            has_approved_leave=False,
        )
    )
    assert calc.worked_minutes == 480
    assert calc.ot2_minutes == 480
    assert calc.ot1_minutes == 0
    assert calc.day_type == "OT2_DAY"


def test_ot2_on_public_holiday():
    """DEC-01: All worked hours on a public holiday are OT2."""
    work_date = date(2026, 12, 2)  # UAE National Day (Wednesday)
    site1 = uuid4()
    visits = [
        ConstructedVisit(
            work_date=work_date,
            place_type="SITE",
            worksite_id=site1,
            accommodation_id=None,
            entry_event_id=uuid4(),
            exit_event_id=uuid4(),
            entry_at=datetime(2026, 12, 2, 7, 0, tzinfo=UTC),
            exit_at=datetime(2026, 12, 2, 16, 0, tzinfo=UTC),
            exit_inferred=False,
            last_inside_at=datetime(2026, 12, 2, 16, 0, tzinfo=UTC),
            counts_as_completed=True,
            duration_minutes=540,
        )
    ]
    calc = compute_daily_attendance(
        DailyCalculationInputs(
            employee_id=uuid4(),
            tally_id="1002",
            work_date=work_date,
            is_driver=False,
            has_accommodation=True,
            standard_hours=8.0,
            schedule=make_schedule(break_m=60),
            assignments=[
                ScheduledAssignment(
                    scheduled_work_id=uuid4(), worksite_id=site1, assigned_hours=8.0
                )
            ],
            visits=visits,
            gaps=[],
            is_public_holiday=True,
            is_weekly_off=False,
            has_approved_leave=False,
        )
    )
    assert calc.worked_minutes == 480
    assert calc.ot2_minutes == 480
    assert calc.ot1_minutes == 0
    assert calc.day_type == "OT2_DAY"


def test_ot1_on_unassigned_non_off_day():
    """DEC-01: Worked hours on an unassigned non-off day are OT1 for all hours."""
    work_date = date(2026, 11, 4)  # Wednesday, no assignment, not weekly off
    site1 = uuid4()
    visits = [
        ConstructedVisit(
            work_date=work_date,
            place_type="SITE",
            worksite_id=site1,
            accommodation_id=None,
            entry_event_id=uuid4(),
            exit_event_id=uuid4(),
            entry_at=datetime(2026, 11, 4, 8, 0, tzinfo=UTC),
            exit_at=datetime(2026, 11, 4, 14, 0, tzinfo=UTC),
            exit_inferred=False,
            last_inside_at=datetime(2026, 11, 4, 14, 0, tzinfo=UTC),
            counts_as_completed=True,
            duration_minutes=360,
        )
    ]
    calc = compute_daily_attendance(
        DailyCalculationInputs(
            employee_id=uuid4(),
            tally_id="1003",
            work_date=work_date,
            is_driver=False,
            has_accommodation=True,
            standard_hours=8.0,
            schedule=make_schedule(break_m=30),
            assignments=[],
            visits=visits,
            gaps=[],
            is_public_holiday=False,
            is_weekly_off=False,
            has_approved_leave=False,
        )
    )
    assert calc.worked_minutes == 330
    assert calc.ot1_minutes == 330
    assert calc.ot2_minutes == 0
    assert calc.day_type == "UNASSIGNED"
    assert "UNSCHEDULED_WORK" in calc.flags


def test_ot1_on_normal_assigned_day():
    """DEC-01: On normal assigned days, OT1 applies only to hours beyond standard hours."""
    work_date = date(2026, 11, 5)  # Thursday
    site1 = uuid4()
    visits = [
        ConstructedVisit(
            work_date=work_date,
            place_type="SITE",
            worksite_id=site1,
            accommodation_id=None,
            entry_event_id=uuid4(),
            exit_event_id=uuid4(),
            entry_at=datetime(2026, 11, 5, 6, 0, tzinfo=UTC),
            exit_at=datetime(2026, 11, 5, 16, 0, tzinfo=UTC),
            exit_inferred=False,
            last_inside_at=datetime(2026, 11, 5, 16, 0, tzinfo=UTC),
            counts_as_completed=True,
            duration_minutes=600,
        )
    ]
    calc = compute_daily_attendance(
        DailyCalculationInputs(
            employee_id=uuid4(),
            tally_id="1004",
            work_date=work_date,
            is_driver=False,
            has_accommodation=True,
            standard_hours=8.0,  # 480 min standard
            schedule=make_schedule(break_m=30),
            assignments=[
                ScheduledAssignment(
                    scheduled_work_id=uuid4(), worksite_id=site1, assigned_hours=8.0
                )
            ],
            visits=visits,
            gaps=[],
            is_public_holiday=False,
            is_weekly_off=False,
            has_approved_leave=False,
        )
    )
    assert calc.worked_minutes == 570  # 600 - 30 break
    assert calc.ot1_minutes == 90  # 570 - 480
    assert calc.ot2_minutes == 0
    assert calc.day_type == "NORMAL"


def test_reassignment_notice_rule_site_local_date():
    """At 01:00 local time, same-day reassignment has 0 days notice and is rejected."""
    target_date = date(2026, 11, 20)
    # Submitted on target_date (e.g. 01:00 local time) -> notice is 0 days (< 3 days required)
    is_valid, err_msg = validate_reassignment_notice(
        date_from=target_date,
        today_work_date=target_date,
        min_notice_days=3,
    )
    assert is_valid is False
    assert err_msg is not None
    assert "requires at least 3 days notice" in err_msg


@pytest.mark.asyncio
async def test_stream_tickets_db_and_single_use():
    """Verify stream tickets are stored in DB, consumed atomically, and expire."""
    async with async_session_factory() as session:
        user = (await session.execute(select(User).limit(1))).scalar_one_or_none()
        assert user is not None
        user_id = user.id

    # 1. Create ticket
    ticket = await stream_ticket_manager.create_ticket(
        user_id=user_id,
        role="ENGINEER",
        employee_id=None,
    )
    assert isinstance(ticket, str)
    assert len(ticket) > 20

    # Verify ticket in database
    async with async_session_factory() as session:
        db_ticket = await session.get(StreamTicket, ticket)
        assert db_ticket is not None
        assert db_ticket.user_id == user_id
        assert db_ticket.role == "ENGINEER"
        assert db_ticket.consumed_at is None
        assert db_ticket.expires_at > datetime.now(UTC)

    # 2. First consumption succeeds
    consumed = await stream_ticket_manager.consume_ticket(ticket)
    assert consumed is not None
    assert consumed["user_id"] == user_id
    assert consumed["role"] == "ENGINEER"

    # Verify ticket is marked consumed in DB
    async with async_session_factory() as session:
        db_ticket = await session.get(StreamTicket, ticket)
        assert db_ticket is not None
        assert db_ticket.consumed_at is not None

    # 3. Second consumption fails (single use)
    second_consumed = await stream_ticket_manager.consume_ticket(ticket)
    assert second_consumed is None


@pytest.mark.asyncio
async def test_worker_scheduler_watchdogs_and_alert():
    """Verify WorkerScheduler executes watchdog job and creates JOB_FAILURE alert on error."""
    scheduler = WorkerScheduler()

    # 1. Run watchdogs job
    res = await scheduler.run_watchdogs()
    assert res is not None
    assert "no_activity_alerts" in res
    assert "stale_device_alerts" in res

    # 2. Test failure alert creation
    job_name = "test_failing_task"
    await scheduler._raise_failure_alert(job_name, "Simulated database timeout error")

    async with async_session_factory() as session:
        stmt = (
            select(Alert).where(Alert.alert_type == "JOB_FAILURE").order_by(Alert.created_at.desc())
        )
        alert = (await session.execute(stmt)).scalars().first()
        assert alert is not None
        assert f"Background Job Failed: {job_name}" in alert.title
        assert "Simulated database timeout error" in alert.message
        assert alert.details.get("job_name") == job_name


@pytest.mark.asyncio
async def test_device_revocation_and_audit():
    """Verify POST /api/v1/devices/{id}/revoke revokes device and writes REVOKE_DEVICE audit log."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create test employee & device
        async with async_session_factory() as session:
            emp = Employee(
                tally_id=f"B5_{uuid4().hex[:6]}",
                name="Batch5 Device Test Worker",
                role="WORKER",
                is_active=True,
            )
            session.add(emp)
            await session.flush()

            device = RegisteredDevice(
                employee_id=emp.id,
                device_identifier=f"test-dev-{uuid4().hex[:8]}",
                platform="ANDROID",
                device_model="Test Phone 15",
                os_version="Android 14",
                app_version="1.0.0",
                is_active=True,
                last_seen_at=datetime.now(UTC),
            )
            session.add(device)
            await session.commit()
            device_id = device.id

            admin_user = (
                await session.execute(select(User).where(User.role == "ADMIN"))
            ).scalar_one_or_none()
            assert admin_user is not None
            admin_token = AuthService.create_access_token(admin_user)

        # Call revoke endpoint
        res = await client.post(
            f"/api/v1/devices/{device_id}/revoke",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "DEVICE_RESET"
        assert data["is_active"] is False

        # Verify DB state and audit log
        async with async_session_factory() as session:
            updated_dev = await session.get(RegisteredDevice, device_id)
            assert updated_dev is not None
            assert updated_dev.is_active is False
            assert updated_dev.revoked_at is not None

            audit_stmt = (
                select(AuditLog)
                .where(
                    AuditLog.action == "REVOKE_DEVICE",
                    AuditLog.entity_id == str(device_id),
                )
                .order_by(AuditLog.created_at.desc())
            )
            audit = (await session.execute(audit_stmt)).scalars().first()
            assert audit is not None
            assert audit.actor_user_id == admin_user.id
            assert audit.action == "REVOKE_DEVICE"
