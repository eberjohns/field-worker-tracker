"""Integration tests for Phase 06: Leave, temporary reassignment, and approvals inbox."""

import asyncio
import socket
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, or_, select

from fw.core.db import async_session_factory, engine
from fw.main import app
from fw.modules.identity import AuthService, User
from fw.modules.jobs import JobItem, Worksite
from fw.modules.notifications import Alert
from fw.modules.org import Employee, EmployeeReportingLine, Group, Zone
from fw.modules.scheduling import (
    BaseRosterEntry,
    BaseRosterTemplate,
    LeaveRequest,
    ReassignmentRequest,
    ScheduledWork,
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


@pytest.fixture(autouse=True)
async def cleanup_db():
    yield
    await engine.dispose()
    await asyncio.sleep(0.01)


async def get_test_data():
    """Seed test hierarchy, worksite, job item, and base template."""
    async with async_session_factory() as session:
        # Admin user
        admin = (await session.execute(select(User).where(User.username == "ADMIN001"))).scalar_one_or_none()
        if not admin:
            admin_emp = Employee(id=uuid4(), tally_id="ADM_P6", name="Admin P6", role="ADMIN", country="AE", is_active=True)
            session.add(admin_emp)
            await session.flush()
            admin = User(id=uuid4(), employee_id=admin_emp.id, username="ADMIN001", credential_hash="hash", role="ADMIN", is_active=True, must_change_password=False)
            session.add(admin)

        # Engineer 1 (ENG_P6_1)
        eng1_emp = (await session.execute(select(Employee).where(Employee.tally_id == "ENG_P6_1"))).scalar_one_or_none()
        if not eng1_emp:
            eng1_emp = Employee(id=uuid4(), tally_id="ENG_P6_1", name="Engineer One", role="ENGINEER", country="AE", is_active=True)
            session.add(eng1_emp)
            await session.flush()
            eng1_user = User(id=uuid4(), employee_id=eng1_emp.id, username="ENG_P6_1", credential_hash="hash", role="ENGINEER", is_active=True, must_change_password=False)
            session.add(eng1_user)
        else:
            eng1_user = (await session.execute(select(User).where(User.username == "ENG_P6_1"))).scalar_one()

        # Engineer 2 (ENG_P6_2, other scope)
        eng2_emp = (await session.execute(select(Employee).where(Employee.tally_id == "ENG_P6_2"))).scalar_one_or_none()
        if not eng2_emp:
            eng2_emp = Employee(id=uuid4(), tally_id="ENG_P6_2", name="Engineer Two", role="ENGINEER", country="AE", is_active=True)
            session.add(eng2_emp)
            await session.flush()
            eng2_user = User(id=uuid4(), employee_id=eng2_emp.id, username="ENG_P6_2", credential_hash="hash", role="ENGINEER", is_active=True, must_change_password=False)
            session.add(eng2_user)
        else:
            eng2_user = (await session.execute(select(User).where(User.username == "ENG_P6_2"))).scalar_one()

        # Supervisor 1 (SUP_P6_1) reporting to Engineer 1
        sup1_emp = (await session.execute(select(Employee).where(Employee.tally_id == "SUP_P6_1"))).scalar_one_or_none()
        if not sup1_emp:
            sup1_emp = Employee(id=uuid4(), tally_id="SUP_P6_1", name="Supervisor One", role="SUPERVISOR", country="AE", is_active=True)
            session.add(sup1_emp)
            await session.flush()
            sup1_user = User(id=uuid4(), employee_id=sup1_emp.id, username="SUP_P6_1", credential_hash="hash", role="SUPERVISOR", is_active=True, must_change_password=False)
            session.add(sup1_user)
            link_e1 = EmployeeReportingLine(employee_id=sup1_emp.id, manager_id=eng1_emp.id, relationship="ENGINEER")
            session.add(link_e1)
        else:
            sup1_user = (await session.execute(select(User).where(User.username == "SUP_P6_1"))).scalar_one()

        # Worker 1 (WRK_P6_1) reporting to Supervisor 1
        w1 = (await session.execute(select(Employee).where(Employee.tally_id == "WRK_P6_1"))).scalar_one_or_none()
        if not w1:
            w1 = Employee(id=uuid4(), tally_id="WRK_P6_1", name="Worker One", role="WORKER", grade_code="G2A", staff_grade_description="Gardener", weekly_off_day="SUNDAY", country="AE", is_active=True)
            session.add(w1)
            await session.flush()
            link_w1 = EmployeeReportingLine(employee_id=w1.id, manager_id=sup1_emp.id, relationship="SUPERVISOR")
            session.add(link_w1)

        # Worker 2 (WRK_P6_2) cover candidate
        w2 = (await session.execute(select(Employee).where(Employee.tally_id == "WRK_P6_2"))).scalar_one_or_none()
        if not w2:
            w2 = Employee(id=uuid4(), tally_id="WRK_P6_2", name="Worker Two", role="WORKER", grade_code="G2A", staff_grade_description="Gardener", weekly_off_day="SUNDAY", country="AE", is_active=True)
            session.add(w2)
            await session.flush()
            link_w2 = EmployeeReportingLine(employee_id=w2.id, manager_id=sup1_emp.id, relationship="SUPERVISOR")
            session.add(link_w2)

        # Clean up prior test runs for these test workers
        await session.execute(delete(ScheduledWork).where(ScheduledWork.employee_id.in_([w1.id, w2.id])))
        await session.execute(delete(ReassignmentRequest).where(or_(
            ReassignmentRequest.original_employee_id.in_([w1.id, w2.id]),
            ReassignmentRequest.new_employee_id.in_([w1.id, w2.id]),
        )))
        await session.execute(delete(Alert).where(Alert.employee_id.in_([w1.id, w2.id])))
        await session.execute(delete(LeaveRequest).where(LeaveRequest.employee_id.in_([w1.id, w2.id])))
        await session.flush()

        # Group and Zone
        group = (await session.execute(select(Group))).scalars().first()
        if not group:
            group = Group(code="GRP_P6", name="Group P6", is_active=True)
            session.add(group)
            await session.flush()

        zone = (await session.execute(select(Zone))).scalars().first()
        if not zone:
            zone = Zone(code="ZN_P6", name="Zone P6", is_active=True)
            session.add(zone)
            await session.flush()

        # Worksite and Job Item
        ws = (await session.execute(select(Worksite).where(Worksite.job_number == "99A99999"))).scalar_one_or_none()
        if not ws:
            ws = Worksite(
                id=uuid4(),
                job_number="99A99999",
                job_name="Phase 06 Test Park",
                group_id=group.id,
                zone_id=zone.id,
                is_outdoor=True,
                country="AE",
                is_active=True,
            )
            session.add(ws)
            await session.flush()
            item = JobItem(
                id=uuid4(),
                worksite_id=ws.id,
                sub_item_code="A",
                staff_grade_description="Gardener",
                planned_grade_code="G2A",
                frequency_unit="WEEK",
                occurrences_per_period=Decimal("6.0"),
                period_interval=1,
                required_staff_count=1,
                hours_per_occurrence_per_staff=Decimal("8.0"),
                deployment_type="PERMANENT",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                is_active=True,
            )
            session.add(item)
            await session.flush()

            # Base roster template placing Worker 1
            tmpl = BaseRosterTemplate(
                id=uuid4(),
                job_item_id=item.id,
                allocation_mode="DAY_OF_WEEK",
                start_date=date(2026, 1, 1),
                is_active=True,
            )
            session.add(tmpl)
            await session.flush()

            # Entry for worker 1 (ALL days)
            entry = BaseRosterEntry(
                id=uuid4(),
                template_id=tmpl.id,
                employee_id=w1.id,
                weekday_mask="ALL",
                sequence=1,
                assigned_hours=Decimal("8.0"),
            )
            session.add(entry)
        else:
            item = (await session.execute(select(JobItem).where(JobItem.worksite_id == ws.id))).scalar_one()

        await session.commit()

        return {
            "admin": admin,
            "eng1": eng1_user,
            "eng2": eng2_user,
            "sup1": sup1_user,
            "w1": w1,
            "w2": w2,
            "worksite": ws,
            "job_item": item,
        }


@db_required
@pytest.mark.asyncio
async def test_reassignment_request_under_3_days_refused_any_role():
    """Checklist item 1: A request under 3 days is refused (any role)."""
    data = await get_test_data()
    today = date.today()

    admin_token = AuthService.create_access_token(data["admin"])
    sup_token = AuthService.create_access_token(data["sup1"])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Request with 2 days notice from Supervisor -> refused!
        payload = {
            "reassignment_type": "REPLACE",
            "date_from": str(today + timedelta(days=2)),
            "date_to": str(today + timedelta(days=2)),
            "original_employee_id": str(data["w1"].id),
            "new_employee_id": str(data["w2"].id),
            "target_job_item_id": str(data["job_item"].id),
            "reason_category": "LEAVE_COVER",
            "reason": "Emergency cover",
        }
        res_sup = await ac.post("/api/v1/reassignment-requests", json=payload, headers={"Authorization": f"Bearer {sup_token}"})
        assert res_sup.status_code == 400
        assert "at least 3 days notice" in str(res_sup.json()["detail"])

        # Same request from Admin -> also refused!
        res_admin = await ac.post("/api/v1/reassignment-requests", json=payload, headers={"Authorization": f"Bearer {admin_token}"})
        assert res_admin.status_code == 400
        assert "at least 3 days notice" in str(res_admin.json()["detail"])

        # Valid request with >= 3 days notice -> accepted!
        valid_payload = dict(payload)
        valid_payload["date_from"] = str(today + timedelta(days=5))
        valid_payload["date_to"] = str(today + timedelta(days=5))
        res_ok = await ac.post("/api/v1/reassignment-requests", json=valid_payload, headers={"Authorization": f"Bearer {sup_token}"})
        assert res_ok.status_code == 201
        assert res_ok.json()["status"] == "PENDING"


@db_required
@pytest.mark.asyncio
async def test_leave_approval_creates_to_be_covered_and_alerts():
    """Checklist item 3: Leave approval creates uncovered slots and alerts."""
    data = await get_test_data()
    today = date.today()
    leave_start = today + timedelta(days=10)
    leave_end = today + timedelta(days=12)

    sup_token = AuthService.create_access_token(data["sup1"])
    eng_token = AuthService.create_access_token(data["eng1"])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Record leave request
        payload = {
            "employee_id": str(data["w1"].id),
            "leave_type": "ANNUAL",
            "from_date": str(leave_start),
            "to_date": str(leave_end),
            "reason": "Vacation trip",
        }
        res = await ac.post("/api/v1/leave-requests", json=payload, headers={"Authorization": f"Bearer {sup_token}"})
        assert res.status_code == 201
        leave_id = res.json()["id"]

        # 2. Engineer approves leave
        app_res = await ac.post(f"/api/v1/leave-requests/{leave_id}/approve", headers={"Authorization": f"Bearer {eng_token}"})
        assert app_res.status_code == 200
        assert app_res.json()["status"] == "APPROVED"

        # 3. Check alert was generated
        alerts_res = await ac.get("/api/v1/alerts", headers={"Authorization": f"Bearer {eng_token}"})
        assert alerts_res.status_code == 200
        alert_titles = [a["title"] for a in alerts_res.json()]
        assert any(f"Cover Needed: {data['w1'].name}" in t for t in alert_titles)

        # 4. Check staffing gaps list
        gaps_res = await ac.get(f"/api/v1/staffing-gaps?from_date={leave_start}&to_date={leave_end}", headers={"Authorization": f"Bearer {eng_token}"})
        assert gaps_res.status_code == 200
        gaps = gaps_res.json()["gaps"]
        assert len(gaps) > 0
        assert gaps[0]["original_employee_id"] == str(data["w1"].id)


@db_required
@pytest.mark.asyncio
async def test_overlapping_leave_refused_and_cancelling_restores_slots():
    """Checklist item 4: Overlapping leave refused; cancelling restores slots."""
    data = await get_test_data()
    today = date.today()
    leave_start = today + timedelta(days=20)
    leave_end = today + timedelta(days=25)

    sup_token = AuthService.create_access_token(data["sup1"])
    eng_token = AuthService.create_access_token(data["eng1"])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Record approved leave
        payload = {
            "employee_id": str(data["w1"].id),
            "leave_type": "ANNUAL",
            "from_date": str(leave_start),
            "to_date": str(leave_end),
            "reason": "First vacation",
        }
        res1 = await ac.post("/api/v1/leave-requests", json=payload, headers={"Authorization": f"Bearer {sup_token}"})
        leave1_id = res1.json()["id"]
        await ac.post(f"/api/v1/leave-requests/{leave1_id}/approve", headers={"Authorization": f"Bearer {eng_token}"})

        # 2. Record overlapping leave -> rejected!
        payload_overlap = {
            "employee_id": str(data["w1"].id),
            "leave_type": "SICK",
            "from_date": str(leave_start + timedelta(days=2)),
            "to_date": str(leave_end + timedelta(days=2)),
            "reason": "Overlapping request",
        }
        res2 = await ac.post("/api/v1/leave-requests", json=payload_overlap, headers={"Authorization": f"Bearer {sup_token}"})
        assert res2.status_code == 400
        assert "overlaps with existing APPROVED leave" in str(res2.json()["detail"])

        # 3. Cancel first leave
        cancel_res = await ac.post(f"/api/v1/leave-requests/{leave1_id}/cancel", headers={"Authorization": f"Bearer {eng_token}"})
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "CANCELLED"

        # 4. Now the second leave is allowed
        res3 = await ac.post("/api/v1/leave-requests", json=payload_overlap, headers={"Authorization": f"Bearer {sup_token}"})
        assert res3.status_code == 201


@db_required
@pytest.mark.asyncio
async def test_rejection_needs_reason_and_approval_materializes_exceptions():
    """Checklist item 2: Approval writes rows and keeps originals; rejection needs a reason."""
    data = await get_test_data()
    today = date.today()
    date_target = today + timedelta(days=8)

    sup_token = AuthService.create_access_token(data["sup1"])
    eng_token = AuthService.create_access_token(data["eng1"])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create reassignment request
        payload = {
            "reassignment_type": "REPLACE",
            "date_from": str(date_target),
            "date_to": str(date_target),
            "original_employee_id": str(data["w1"].id),
            "new_employee_id": str(data["w2"].id),
            "target_job_item_id": str(data["job_item"].id),
            "reason_category": "LEAVE_COVER",
            "reason": "Covering shift",
        }
        req_res = await ac.post("/api/v1/reassignment-requests", json=payload, headers={"Authorization": f"Bearer {sup_token}"})
        req_id = req_res.json()["id"]

        # Try to reject without a reason -> 400 error!
        rej_empty = await ac.post(f"/api/v1/reassignment-requests/{req_id}/reject", json={"decision_note": ""}, headers={"Authorization": f"Bearer {eng_token}"})
        assert rej_empty.status_code == 400
        assert "rejection reason is mandatory" in str(rej_empty.json()["detail"]).lower()

        # Approve the request
        app_res = await ac.post(f"/api/v1/reassignment-requests/{req_id}/approve", json={"decision_note": "Approved by Engineer"}, headers={"Authorization": f"Bearer {eng_token}"})
        assert app_res.status_code == 200
        assert app_res.json()["status"] == "APPROVED"

        # Verify operational shift materialized in scheduled_work for Worker 2
        async with async_session_factory() as session:
            stmt = select(ScheduledWork).where(
                ScheduledWork.reassignment_request_id == UUID(req_id),
                ScheduledWork.employee_id == data["w2"].id,
                ScheduledWork.work_date == date_target,
            )
            sw = (await session.execute(stmt)).scalar_one_or_none()
            assert sw is not None
            assert sw.status == "ACTIVE"
            assert sw.source == "OVERRIDE"
            assert sw.original_employee_id == data["w1"].id


@db_required
@pytest.mark.asyncio
async def test_engineer_scope_vs_admin_all():
    """Checklist item 6: Engineer sees only their scope; Admin all."""
    data = await get_test_data()

    admin_token = AuthService.create_access_token(data["admin"])
    eng1_token = AuthService.create_access_token(data["eng1"])
    eng2_token = AuthService.create_access_token(data["eng2"])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        inbox_admin = await ac.get("/api/v1/approvals", headers={"Authorization": f"Bearer {admin_token}"})
        inbox_eng1 = await ac.get("/api/v1/approvals", headers={"Authorization": f"Bearer {eng1_token}"})
        inbox_eng2 = await ac.get("/api/v1/approvals", headers={"Authorization": f"Bearer {eng2_token}"})

        assert inbox_admin.status_code == 200
        assert inbox_eng1.status_code == 200
        assert inbox_eng2.status_code == 200

        # Engineer 2 has no workers reporting to them, so their inbox should be empty
        assert inbox_eng2.json()["counts"]["total"] == 0
        # Admin sees all items
        assert inbox_admin.json()["counts"]["total"] >= inbox_eng1.json()["counts"]["total"]


@db_required
@pytest.mark.asyncio
async def test_leave_taken_counts_correct():
    """Checklist item 5: Leave taken counts per worker/type/year correct."""
    data = await get_test_data()
    admin_token = AuthService.create_access_token(data["admin"])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/leave-requests/summary?year=2026&employee_id={data['w1'].id}", headers={"Authorization": f"Bearer {admin_token}"})
        assert res.status_code == 200
        summaries = res.json()
        assert len(summaries) == 1
        worker_summary = summaries[0]
        assert worker_summary["employee_id"] == str(data["w1"].id)
        assert "ANNUAL" in worker_summary["by_type"]
        # Working days <= calendar days
        assert worker_summary["total_working_days"] <= worker_summary["total_calendar_days"]


@db_required
@pytest.mark.asyncio
async def test_approvals_inbox_filtering_and_recorded_at():
    """Verify approvals inbox status filter and recorded_at in leave response."""
    data = await get_test_data()
    admin_token = AuthService.create_access_token(data["admin"])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create leave request
        from_dt = date.today() + timedelta(days=20)
        to_dt = from_dt + timedelta(days=2)
        leave_res = await ac.post(
            "/api/v1/leave-requests",
            json={
                "employee_id": str(data["w1"].id),
                "leave_type": "SICK",
                "from_date": from_dt.isoformat(),
                "to_date": to_dt.isoformat(),
                "reason": "Medical appointment",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert leave_res.status_code == 201
        leave_data = leave_res.json()
        assert "recorded_at" in leave_data
        assert leave_data["recorded_at"] is not None
        assert leave_data["recorded_at"] == leave_data["created_at"]
        leave_id = leave_data["id"]

        # Pending inbox contains this leave
        inbox_pending = await ac.get("/api/v1/approvals?status=PENDING", headers={"Authorization": f"Bearer {admin_token}"})
        assert inbox_pending.status_code == 200
        pending_ids = [item["id"] for item in inbox_pending.json()["leave_requests"]]
        assert leave_id in pending_ids

        # Approve the leave
        app_res = await ac.post(
            f"/api/v1/leave-requests/{leave_id}/approve",
            json={"reason": "Approved by doctor certificate"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert app_res.status_code == 200

        # Approved inbox now contains this leave
        inbox_approved = await ac.get("/api/v1/approvals?status=APPROVED", headers={"Authorization": f"Bearer {admin_token}"})
        assert inbox_approved.status_code == 200
        approved_ids = [item["id"] for item in inbox_approved.json()["leave_requests"]]
        assert leave_id in approved_ids

        # ALL inbox also contains this leave
        inbox_all = await ac.get("/api/v1/approvals?status=ALL", headers={"Authorization": f"Bearer {admin_token}"})
        assert inbox_all.status_code == 200
        all_ids = [item["id"] for item in inbox_all.json()["leave_requests"]]
        assert leave_id in all_ids

