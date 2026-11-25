"""/dashboard/summary returns non-zero pending-visit and live counts (the fields the web cards read)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from fw.core.clock import site_today
from fw.core.db import async_session_factory
from fw.main import create_app
from fw.modules.attendance.models import PendingVisit
from fw.modules.events import EmployeeLastPosition, MobileEventLog
from fw.modules.jobs.models import WorksiteSupervisor
from fw.modules.org import RegisteredDevice
from fw.modules.scheduling.models import ScheduledWork
from tests.test_batch6_features import db_required
from tests.test_dec57_scope import _person, _site

pytestmark = [db_required, pytest.mark.asyncio]


async def test_summary_counts_open_visits_escalations_and_live_workers() -> None:
    today = site_today("AE")
    now = datetime.now(UTC)
    async with async_session_factory() as session:
        sup, sup_token = await _person(session, "SUPERVISOR", "Dash Sup")
        worker, _ = await _person(session, "WORKER", "Dash Worker")
        site, item = await _site(session, "Dash Site")
        session.add(WorksiteSupervisor(worksite_id=site.id, supervisor_id=sup.id))

        def work(day):
            return ScheduledWork(
                work_date=day,
                employee_id=worker.id,
                job_item_id=item.id,
                worksite_id=site.id,
                assigned_hours=Decimal("8.00"),
                status="ACTIVE",
            )

        sw_today, sw_old = work(today), work(today - timedelta(days=20))
        session.add_all([sw_today, sw_old])
        await session.flush()
        # One visit due today (open) and one 20 days overdue (open and escalated).
        for sw in (sw_today, sw_old):
            session.add(
                PendingVisit(
                    scheduled_work_id=sw.id,
                    worksite_id=site.id,
                    employee_id=worker.id,
                    due_date=sw.work_date,
                    detected_on=sw.work_date,
                    status="OPEN",
                )
            )
        device = RegisteredDevice(
            employee_id=worker.id,
            device_identifier=f"dev-{uuid4().hex[:8]}",
            platform="ANDROID",
            is_active=True,
        )
        session.add(device)
        await session.flush()
        event = MobileEventLog(
            event_id=uuid4(),
            employee_id=worker.id,
            device_id=device.id,
            event_type="PING",
            event_timestamp_utc=now - timedelta(minutes=2),
            latitude=Decimal("25.200000"),
            longitude=Decimal("55.270000"),
            server_received_at=now - timedelta(minutes=2),
        )
        session.add(event)
        await session.flush()
        session.add(
            EmployeeLastPosition(
                employee_id=worker.id,
                last_event_id=event.event_id,
                event_type="PING",
                latitude=Decimal("25.200000"),
                longitude=Decimal("55.270000"),
                accuracy_meters=10.0,
                event_timestamp_utc=now - timedelta(minutes=2),
                received_at_utc=now - timedelta(minutes=2),
                tracking_enabled=True,
                last_contact_at=now - timedelta(minutes=2),
            )
        )
        await session.commit()

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {sup_token}"}
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Field names the web mapper reads (web/src/features/dashboard/summary.ts).
    assert body["pending_visits_count"] == 2
    assert body["pending_visits_escalated_count"] == 1
    assert body["live_workers"]["active"] == 1
    assert body["live_workers"]["total"] >= 1
    assert body["attendance"]["total_scheduled"] == 1


async def test_pending_visits_limit_caps_items_but_not_counts() -> None:
    """Dashboard preview (Batch 10 B): ?limit returns the newest N; counts cover every visit."""
    today = site_today("AE")
    async with async_session_factory() as session:
        sup, sup_token = await _person(session, "SUPERVISOR", "Preview Sup")
        worker, _ = await _person(session, "WORKER", "Preview Worker")
        site, item = await _site(session, "Preview Site")
        session.add(WorksiteSupervisor(worksite_id=site.id, supervisor_id=sup.id))
        days = [today - timedelta(days=n) for n in (1, 5, 9)]
        works = [
            ScheduledWork(
                work_date=d,
                employee_id=worker.id,
                job_item_id=item.id,
                worksite_id=site.id,
                assigned_hours=Decimal("8.00"),
                status="ACTIVE",
            )
            for d in days
        ]
        session.add_all(works)
        await session.flush()
        for sw in works:
            session.add(
                PendingVisit(
                    scheduled_work_id=sw.id,
                    worksite_id=site.id,
                    employee_id=worker.id,
                    due_date=sw.work_date,
                    detected_on=sw.work_date,
                    status="OPEN",
                )
            )
        await session.commit()

    app = create_app()
    headers = {"Authorization": f"Bearer {sup_token}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        limited = await client.get(
            "/api/v1/pending-visits",
            params={"status": "OPEN", "worksite_id": str(site.id), "limit": 2},
            headers=headers,
        )
        full = await client.get(
            "/api/v1/pending-visits",
            params={"status": "OPEN", "worksite_id": str(site.id)},
            headers=headers,
        )
        bad = await client.get("/api/v1/pending-visits", params={"limit": 0}, headers=headers)
    assert limited.status_code == 200, limited.text
    body = limited.json()
    assert [i["due_date"] for i in body["items"]] == [str(days[0]), str(days[1])]
    assert body["open_count"] == 3
    assert body["total_count"] == 3
    assert len(full.json()["items"]) == 3
    assert bad.status_code == 422
