"""Tests for Phase 09: Live map, pending visits, alerts, and documents."""

import socket
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from fw.core.db import async_session_factory
from fw.modules.attendance import (
    PendingVisit,
    PendingVisitsService,
)
from fw.modules.events import (
    EmployeeLastPosition,
    EventEnrichmentService,
    EventsService,
    LiveLocationAccessLog,
    MobileEventLog,
)
from fw.modules.events.live_publisher import stream_ticket_manager
from fw.modules.identity import User
from fw.modules.jobs import JobItem, Worksite
from fw.modules.notifications import NotificationService
from fw.modules.notifications.models import Alert
from fw.modules.org import Employee, EmployeeDocument, Group, OrgService, RegisteredDevice, Zone
from fw.modules.scheduling import LeaveRequest, ScheduledWork


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


def _make_employee(name: str, role: str = "WORKER", country: str = "AE") -> Employee:
    return Employee(
        id=uuid.uuid4(),
        name=name,
        tally_id=f"T-{uuid.uuid4().hex[:6]}",
        role=role,
        country=country,
        is_active=True,
    )


def _make_device(emp_id: uuid.UUID) -> RegisteredDevice:
    return RegisteredDevice(
        id=uuid.uuid4(),
        employee_id=emp_id,
        device_identifier=f"dev-{uuid.uuid4().hex[:8]}",
        platform="ANDROID",
        is_active=True,
    )


def _make_user(emp: Employee, role: str = "ADMIN") -> User:
    return User(
        id=uuid.uuid4(),
        employee_id=emp.id,
        username=f"usr_{uuid.uuid4().hex[:6]}",
        credential_hash="hash",
        role=role,
        is_active=True,
        must_change_password=False,
    )


async def _make_worksite(session) -> Worksite:
    group = Group(
        id=uuid.uuid4(), name=f"Group-{uuid.uuid4().hex[:4]}", code=f"G{uuid.uuid4().hex[:3]}"
    )
    zone = Zone(
        id=uuid.uuid4(), name=f"Zone-{uuid.uuid4().hex[:4]}", code=f"Z{uuid.uuid4().hex[:3]}"
    )
    session.add_all([group, zone])
    await session.flush()

    site = Worksite(
        id=uuid.uuid4(),
        job_number=f"JN-{uuid.uuid4().hex[:6]}",
        job_name="Test Landscape Project",
        group_id=group.id,
        zone_id=zone.id,
        country="AE",
    )
    session.add(site)
    await session.flush()
    return site


@db_required
@pytest.mark.asyncio
async def test_late_upload_never_overwrites_newer_position():
    """Verify checklist requirement: A late upload never overwrites a newer position."""
    async with async_session_factory() as session:
        emp = _make_employee("Live Worker")
        session.add(emp)
        await session.flush()
        device = _make_device(emp.id)
        session.add(device)
        await session.flush()

        t_now = datetime.now(UTC)
        t_newer = t_now - timedelta(minutes=10)
        t_older = t_now - timedelta(hours=2)

        # 1. Ingest newer event
        newer_event = MobileEventLog(
            event_id=uuid.uuid4(),
            employee_id=emp.id,
            device_id=device.id,
            event_type="PING",
            event_timestamp_utc=t_newer,
            latitude=Decimal("25.204800"),
            longitude=Decimal("55.270800"),
            accuracy_meters=10.0,
            server_received_at=t_now,
            processing_status="ENRICHED",
            server_verdict="INSIDE",
        )
        session.add(newer_event)
        await session.flush()

        await EventEnrichmentService._update_last_position(session, newer_event)
        await session.flush()

        # Check stored position
        pos_res = await session.execute(
            select(EmployeeLastPosition).where(EmployeeLastPosition.employee_id == emp.id)
        )
        pos = pos_res.scalar_one()
        assert pos.event_timestamp_utc == t_newer
        assert pos.latitude == Decimal("25.204800")
        assert pos.longitude == Decimal("55.270800")

        # 2. Ingest older event (late upload from offline phone)
        older_event = MobileEventLog(
            event_id=uuid.uuid4(),
            employee_id=emp.id,
            device_id=device.id,
            event_type="PING",
            event_timestamp_utc=t_older,
            latitude=Decimal("24.000000"),
            longitude=Decimal("54.000000"),
            accuracy_meters=50.0,
            server_received_at=t_now,
            processing_status="ENRICHED",
            server_verdict="OUTSIDE",
        )
        session.add(older_event)
        await session.flush()

        # Update last position with late upload
        await EventEnrichmentService._update_last_position(session, older_event)
        await session.flush()

        # Assert position was NOT overwritten by older event
        pos_res2 = await session.execute(
            select(EmployeeLastPosition).where(EmployeeLastPosition.employee_id == emp.id)
        )
        pos_after = pos_res2.scalar_one()
        assert pos_after.event_timestamp_utc == t_newer
        assert pos_after.latitude == Decimal("25.204800")
        assert pos_after.longitude == Decimal("55.270800")
        assert pos_after.event_type == "PING"


@db_required
@pytest.mark.asyncio
async def test_active_offline_states_follow_live_active_window_minutes():
    """Verify checklist requirement: Active/offline states follow live_active_window_minutes."""
    async with async_session_factory() as session:
        admin_emp = _make_employee("Admin Staff", role="ADMIN")
        session.add(admin_emp)
        await session.flush()
        admin = _make_user(admin_emp, role="ADMIN")
        session.add(admin)

        emp_active = _make_employee("Active Worker")
        emp_offline = _make_employee("Offline Worker")
        emp_disabled = _make_employee("Disabled Worker")
        session.add_all([emp_active, emp_offline, emp_disabled])
        await session.flush()

        dev_act = _make_device(emp_active.id)
        dev_off = _make_device(emp_offline.id)
        dev_dis = _make_device(emp_disabled.id)
        session.add_all([dev_act, dev_off, dev_dis])
        await session.flush()

        now = datetime.now(UTC)

        # Seed events for foreign key validity
        ev_act = MobileEventLog(
            event_id=uuid.uuid4(),
            employee_id=emp_active.id,
            device_id=dev_act.id,
            event_type="PING",
            event_timestamp_utc=now - timedelta(minutes=5),
            latitude=Decimal("25.200000"),
            longitude=Decimal("55.270000"),
            server_received_at=now - timedelta(minutes=5),
        )
        ev_off = MobileEventLog(
            event_id=uuid.uuid4(),
            employee_id=emp_offline.id,
            device_id=dev_off.id,
            event_type="PING",
            event_timestamp_utc=now - timedelta(minutes=45),
            latitude=Decimal("25.210000"),
            longitude=Decimal("55.280000"),
            server_received_at=now - timedelta(minutes=45),
        )
        ev_dis = MobileEventLog(
            event_id=uuid.uuid4(),
            employee_id=emp_disabled.id,
            device_id=dev_dis.id,
            event_type="LOCATION_DISABLED",
            event_timestamp_utc=now - timedelta(minutes=2),
            latitude=Decimal("25.220000"),
            longitude=Decimal("55.290000"),
            server_received_at=now - timedelta(minutes=2),
        )
        session.add_all([ev_act, ev_off, ev_dis])
        await session.flush()

        # emp_active: received 5 minutes ago (within 15 min window)
        pos_act = EmployeeLastPosition(
            employee_id=emp_active.id,
            last_event_id=ev_act.event_id,
            event_type="PING",
            latitude=Decimal("25.200000"),
            longitude=Decimal("55.270000"),
            accuracy_meters=10.0,
            event_timestamp_utc=now - timedelta(minutes=5),
            received_at_utc=now - timedelta(minutes=5),
            tracking_enabled=True,
            last_contact_at=now - timedelta(minutes=5),
        )

        # emp_offline: received 45 minutes ago (exceeds 15 min window)
        pos_off = EmployeeLastPosition(
            employee_id=emp_offline.id,
            last_event_id=ev_off.event_id,
            event_type="PING",
            latitude=Decimal("25.210000"),
            longitude=Decimal("55.280000"),
            accuracy_meters=15.0,
            event_timestamp_utc=now - timedelta(minutes=45),
            received_at_utc=now - timedelta(minutes=45),
            tracking_enabled=True,
            last_contact_at=now - timedelta(minutes=45),
        )

        # emp_disabled: tracking disabled
        pos_dis = EmployeeLastPosition(
            employee_id=emp_disabled.id,
            last_event_id=ev_dis.event_id,
            event_type="LOCATION_DISABLED",
            latitude=Decimal("25.220000"),
            longitude=Decimal("55.290000"),
            accuracy_meters=20.0,
            event_timestamp_utc=now - timedelta(minutes=2),
            received_at_utc=now - timedelta(minutes=2),
            tracking_enabled=False,
            last_contact_at=now - timedelta(minutes=2),
        )
        session.add_all([pos_act, pos_off, pos_dis])
        await session.flush()

        scheduled_emp_ids = {emp_active.id, emp_offline.id, emp_disabled.id}

        resp = await EventsService.get_live_positions(
            session=session,
            user=admin,
            scoped_employee_ids=None,
            scheduled_employee_ids=scheduled_emp_ids,
            today_assignments_by_emp={},
            as_of=now,
        )

        state_by_id = {item.employee_id: item.live_state for item in resp.items}
        assert state_by_id[emp_active.id] == "ACTIVE"
        assert state_by_id[emp_offline.id] == "NO_RECENT_SIGNAL"
        assert state_by_id[emp_disabled.id] == "LOCATION_DISABLED"


@db_required
@pytest.mark.asyncio
async def test_location_disabled_raises_alert_and_enabled_clears_it():
    """Verify checklist requirement: LOCATION_DISABLED raises an alert to in-scope supervisors; ENABLED clears it."""
    async with async_session_factory() as session:
        emp = _make_employee("Track Worker")
        session.add(emp)
        await session.flush()
        dev = _make_device(emp.id)
        session.add(dev)
        await session.flush()

        now = datetime.now(UTC)

        # 1. Ingest LOCATION_DISABLED event
        dis_event = MobileEventLog(
            event_id=uuid.uuid4(),
            employee_id=emp.id,
            device_id=dev.id,
            event_type="LOCATION_DISABLED",
            event_timestamp_utc=now,
            latitude=Decimal("25.200000"),
            longitude=Decimal("55.270000"),
            geom="SRID=4326;POINT(55.270000 25.200000)",
            accuracy_meters=10.0,
            server_received_at=now,
            processing_status="ACCEPTED",
        )
        session.add(dis_event)
        await session.flush()

        await EventEnrichmentService.enrich_events(
            session=session,
            event_ids=[dis_event.event_id],
            employee_id=emp.id,
            work_date=now.date(),
        )
        await session.flush()

        # Check that TRACKING_INTERRUPTED alert is OPEN
        alert_q = select(Alert).where(
            Alert.alert_type == "TRACKING_INTERRUPTED",
            Alert.employee_id == emp.id,
        )
        alert = (await session.execute(alert_q)).scalar_one_or_none()
        assert alert is not None
        assert alert.status == "OPEN"

        # 2. Ingest LOCATION_ENABLED event
        en_event = MobileEventLog(
            event_id=uuid.uuid4(),
            employee_id=emp.id,
            device_id=dev.id,
            event_type="LOCATION_ENABLED",
            event_timestamp_utc=now + timedelta(minutes=10),
            latitude=Decimal("25.200000"),
            longitude=Decimal("55.270000"),
            geom="SRID=4326;POINT(55.270000 25.200000)",
            accuracy_meters=10.0,
            server_received_at=now + timedelta(minutes=10),
            processing_status="ACCEPTED",
        )
        session.add(en_event)
        await session.flush()

        await EventEnrichmentService.enrich_events(
            session=session,
            event_ids=[en_event.event_id],
            employee_id=emp.id,
            work_date=now.date(),
        )
        await session.flush()

        # Verify alert is now RESOLVED
        alert_res2 = await session.execute(alert_q)
        alert_after = alert_res2.scalar_one()
        assert alert_after.status == "RESOLVED"
        assert alert_after.resolved_at is not None


@db_required
@pytest.mark.asyncio
async def test_pending_visit_lifecycle_and_reminders():
    """Verify checklist requirement: Pending visit lifecycle works and reminders fire."""
    async with async_session_factory() as session:
        today = datetime.now(UTC).date()
        target_date = today - timedelta(days=1)

        eng_emp = _make_employee("Engineer Staff", role="ENGINEER")
        session.add(eng_emp)
        await session.flush()
        user = _make_user(eng_emp, role="ENGINEER")

        site = await _make_worksite(session)
        job_item = JobItem(
            id=uuid.uuid4(),
            worksite_id=site.id,
            sub_item_code="01",
            staff_grade_description="Mason",
            planned_grade_code="M-1",
            frequency_unit="WEEK",
            occurrences_per_period=Decimal("1.00"),
            period_interval=1,
            required_staff_count=1,
            hours_per_occurrence_per_staff=Decimal("8.000"),
            start_date=target_date - timedelta(days=30),
            deployment_type="PERMANENT",
        )
        session.add(job_item)
        await session.flush()

        emp1 = _make_employee("Missed Worker")
        emp_on_leave = _make_employee("Leave Worker")
        session.add_all([user, emp1, emp_on_leave])
        await session.flush()

        # Scheduled work for emp1 (missed visit)
        sw1 = ScheduledWork(
            id=uuid.uuid4(),
            employee_id=emp1.id,
            worksite_id=site.id,
            job_item_id=job_item.id,
            work_date=target_date,
            assigned_hours=Decimal("8.00"),
            status="ACTIVE",
            source="STANDING",
        )
        # Scheduled work for emp_on_leave (has approved leave)
        sw_leave = ScheduledWork(
            id=uuid.uuid4(),
            employee_id=emp_on_leave.id,
            worksite_id=site.id,
            job_item_id=job_item.id,
            work_date=target_date,
            assigned_hours=Decimal("8.00"),
            status="ACTIVE",
            source="STANDING",
        )
        leave = LeaveRequest(
            id=uuid.uuid4(),
            employee_id=emp_on_leave.id,
            leave_type="ANNUAL",
            from_date=target_date - timedelta(days=1),
            to_date=target_date + timedelta(days=1),
            status="APPROVED",
            reason="Annual leave",
            recorded_by_user_id=user.id,
        )
        session.add_all([sw1, sw_leave, leave])
        await session.flush()

        # Run day-close detection
        detected = await PendingVisitsService.detect_pending_visits(session, target_date)
        assert detected == 1  # Only emp1 flagged, leave worker exempted!

        # Check pending visit row
        pv_q = select(PendingVisit).where(PendingVisit.scheduled_work_id == sw1.id)
        pv = (await session.execute(pv_q)).scalar_one()
        assert pv.status == "OPEN"
        assert pv.employee_id == emp1.id

        # Reminders test
        reminded = await PendingVisitsService.check_pending_visit_reminders(session)
        assert reminded >= 1

        # Explain pending visit
        await PendingVisitsService.explain_pending_visit(
            session=session,
            pending_visit_id=pv.id,
            user=user,
            explanation="Customer cancelled the inspection.",
        )
        assert pv.status == "EXPLAINED"
        assert pv.explanation_comment_id is not None

        # Reschedule pending visit
        new_date = today + timedelta(days=2)
        rescheduled = await PendingVisitsService.reschedule_pending_visit(
            session=session,
            pending_visit_id=pv.id,
            user=user,
            work_date=new_date,
            employee_ids=[emp1.id],
        )
        assert len(rescheduled) == 1
        assert rescheduled[0].source == "FOLLOW_UP"
        assert pv.status == "RESCHEDULED"

        # Close pending visit
        await PendingVisitsService.close_pending_visit(
            session=session,
            pending_visit_id=pv.id,
            user=user,
            reason="Work completed under another job",
        )
        assert pv.status == "CLOSED"
        assert pv.closed_reason == "Work completed under another job"


@db_required
@pytest.mark.asyncio
async def test_expiring_documents_list_and_alerts():
    """Verify checklist requirement: Expiring documents list and alert at configured lead days."""
    async with async_session_factory() as session:
        today = datetime.now(UTC).date()
        admin_emp = _make_employee("Admin Staff", role="ADMIN")
        session.add(admin_emp)
        await session.flush()
        admin = _make_user(admin_emp, role="ADMIN")

        emp = _make_employee("Doc Worker")
        session.add_all([admin, emp])
        await session.flush()

        # Document expiring in 15 days (default lead days 30)
        doc = EmployeeDocument(
            id=uuid.uuid4(),
            employee_id=emp.id,
            document_type="EMIRATES_ID",
            expiry_date=today + timedelta(days=15),
            is_active=True,
        )
        session.add(doc)
        await session.flush()

        # Trigger alert detection
        created_alerts = await NotificationService.check_document_expiry_alerts(session)
        assert created_alerts >= 1

        alert_q = select(Alert).where(
            Alert.alert_type == "DOC_EXPIRY",
            Alert.ref_id == doc.id,
        )
        alert = (await session.execute(alert_q)).scalar_one_or_none()
        assert alert is not None
        assert alert.status == "OPEN"
        assert "EMIRATES_ID" in alert.title

        # Query expiring documents endpoint service
        docs_resp = await OrgService.get_expiring_documents(
            session=session,
            user=admin,
            within_days=30,
        )
        doc_item = next(d for d in docs_resp.items if d.document_id == doc.id)
        assert doc_item.status == "EXPIRING"
        assert doc_item.days_remaining == 15


@db_required
@pytest.mark.asyncio
async def test_live_location_view_is_audit_logged():
    """Verify checklist requirement: Every view of live location is audit-logged."""
    async with async_session_factory() as session:
        sup_emp = _make_employee("Supervisor Staff", role="SUPERVISOR")
        session.add(sup_emp)
        await session.flush()
        user = _make_user(sup_emp, role="SUPERVISOR")
        session.add(user)
        await session.flush()

        # 1. Log poll access
        poll_log = await EventsService.log_live_access(
            session=session,
            user_id=user.id,
            access_type="POLL",
            filters={"state": "ACTIVE"},
            client_ip="192.168.1.100",
            user_agent="TestBrowser/1.0",
        )
        assert poll_log.id is not None
        assert poll_log.access_type == "POLL"

        # 2. Log stream access
        stream_log = await EventsService.log_live_access(
            session=session,
            user_id=user.id,
            access_type="STREAM",
            filters={"stream": True},
            client_ip="192.168.1.100",
            user_agent="TestBrowser/1.0",
        )
        assert stream_log.id is not None
        assert stream_log.access_type == "STREAM"

        # Query live_location_access_logs
        logs_res = await session.execute(
            select(LiveLocationAccessLog).where(LiveLocationAccessLog.user_id == user.id)
        )
        logs = logs_res.scalars().all()
        assert len(logs) == 2


@pytest.mark.asyncio
async def test_stream_ticket_lifecycle():
    """Verify stream ticket single-use and expiration."""
    user_id = uuid.uuid4()
    ticket = await stream_ticket_manager.create_ticket(user_id=user_id, role="ENGINEER")
    assert isinstance(ticket, str)
    assert len(ticket) >= 32

    # First consumption succeeds
    data = await stream_ticket_manager.consume_ticket(ticket)
    assert data is not None
    assert data["user_id"] == user_id
    assert data["role"] == "ENGINEER"

    # Second consumption fails (single-use!)
    data2 = await stream_ticket_manager.consume_ticket(ticket)
    assert data2 is None
