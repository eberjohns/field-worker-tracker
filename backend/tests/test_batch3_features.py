"""Integration tests for Batch 3: Role split, Leave Auto/Bulk Cover, Reassignment Batches,
Tally ID Changes & Guardrail, and Admin-Only Deactivation & Clean Reactivation (Option A).
"""

from __future__ import annotations

import asyncio
import socket
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, or_, select

from fw.core.db import async_session_factory, engine
from fw.main import app
from fw.modules.audit import AuditLog
from fw.modules.identity import AuthService, User, UserService, UserSession, hash_password
from fw.modules.jobs import JobItem, JobOccurrence, Worksite
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


ADMIN_PW = "AdminBatch3Pass!99"


async def seed_batch3_context():
    """Seed isolated entities for Batch 3 tests (fresh suffix per run)."""
    tag = uuid4().hex[:6].upper()
    async with async_session_factory() as session:
        # Single standalone system ADMIN001 (never stored in employees table)
        admin_user = await UserService.get_or_create_system_admin(session, password=ADMIN_PW)

        # Engineer
        eng_emp = Employee(
            id=uuid4(),
            tally_id=f"ENG_B3_{tag}",
            name=f"Engineer B3 {tag}",
            role="ENGINEER",
            country="AE",
            is_active=True,
        )
        session.add(eng_emp)
        await session.flush()
        eng_user = User(
            id=uuid4(),
            employee_id=eng_emp.id,
            username=f"ENG_B3_{tag}",
            credential_hash=hash_password("Pass1234!"),
            role="ENGINEER",
            is_active=True,
            must_change_password=False,
        )
        session.add(eng_user)

        # Superintendent
        supt_emp = Employee(
            id=uuid4(),
            tally_id=f"SPT_B3_{tag}",
            name=f"Superintendent B3 {tag}",
            role="SUPERINTENDENT",
            country="AE",
            is_active=True,
        )
        session.add(supt_emp)
        await session.flush()
        supt_user = User(
            id=uuid4(),
            employee_id=supt_emp.id,
            username=f"SPT_B3_{tag}",
            credential_hash=hash_password("Pass1234!"),
            role="SUPERINTENDENT",
            is_active=True,
            must_change_password=False,
        )
        session.add(supt_user)

        # Supervisor
        sup_emp = Employee(
            id=uuid4(),
            tally_id=f"SUP_B3_{tag}",
            name=f"Supervisor B3 {tag}",
            role="SUPERVISOR",
            country="AE",
            is_active=True,
        )
        session.add(sup_emp)
        await session.flush()
        sup_user = User(
            id=uuid4(),
            employee_id=sup_emp.id,
            username=f"SUP_B3_{tag}",
            credential_hash=hash_password("Pass1234!"),
            role="SUPERVISOR",
            is_active=True,
            must_change_password=False,
        )
        session.add(sup_user)

        # Worker A (off SUNDAY) and Worker B (cover worker, off WEDNESDAY)
        w1 = Employee(
            id=uuid4(),
            tally_id=f"W1_B3_{tag}",
            name=f"Worker One {tag}",
            role="WORKER",
            country="AE",
            weekly_off_day="SUNDAY",
            staff_grade_description="Landscape Gardener",
            is_active=True,
        )
        w2 = Employee(
            id=uuid4(),
            tally_id=f"W2_B3_{tag}",
            name=f"Worker Cover {tag}",
            role="WORKER",
            country="AE",
            weekly_off_day="WEDNESDAY",
            staff_grade_description="Landscape Gardener",
            is_active=True,
        )
        session.add_all([w1, w2])
        await session.flush()

        w1_user = User(
            id=uuid4(),
            employee_id=w1.id,
            username=w1.tally_id,
            credential_hash=hash_password("Pass1234!"),
            role="WORKER",
            is_active=True,
            must_change_password=False,
        )
        session.add(w1_user)

        # Reporting hierarchy: w1/w2 -> sup -> supt -> eng
        session.add_all(
            [
                EmployeeReportingLine(
                    employee_id=sup_emp.id, manager_id=supt_emp.id, relationship="SUPERINTENDENT"
                ),
                EmployeeReportingLine(
                    employee_id=sup_emp.id, manager_id=eng_emp.id, relationship="ENGINEER"
                ),
                EmployeeReportingLine(
                    employee_id=w1.id, manager_id=sup_emp.id, relationship="SUPERVISOR"
                ),
                EmployeeReportingLine(
                    employee_id=w2.id, manager_id=sup_emp.id, relationship="SUPERVISOR"
                ),
            ]
        )

        # Group, Zone, Worksite, JobItem
        grp = Group(id=uuid4(), code=f"GB3_{tag}", name=f"Group B3 {tag}", is_active=True)
        zn = Zone(id=uuid4(), code=f"ZB3_{tag}", name=f"Zone B3 {tag}", is_active=True)
        session.add_all([grp, zn])
        await session.flush()

        ws = Worksite(
            id=uuid4(),
            job_number=f"99A{str(uuid4().int)[:5]}",
            job_name=f"Batch3 Test Site {tag}",
            group_id=grp.id,
            zone_id=zn.id,
            country="AE",
            is_outdoor=True,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() + timedelta(days=180),
            is_active=True,
        )
        session.add(ws)
        await session.flush()

        ji = JobItem(
            id=uuid4(),
            worksite_id=ws.id,
            sub_item_code="01",
            staff_grade_description="Landscape Gardener",
            planned_grade_code="G2B",
            frequency_unit="WEEK",
            occurrences_per_period=6,
            period_interval=1,
            required_staff_count=1,
            hours_per_occurrence_per_staff=Decimal("8.0"),
            start_date=date.today() - timedelta(days=30),
            deployment_type="PERMANENT",
            is_active=True,
        )
        session.add(ji)
        await session.flush()

        # Active Base Roster Template assigning w1 Mon-Sat
        tpl = BaseRosterTemplate(
            id=uuid4(),
            job_item_id=ji.id,
            allocation_mode="DAY_OF_WEEK",
            start_date=date.today() - timedelta(days=14),
            is_active=True,
        )
        session.add(tpl)
        await session.flush()
        for dow in ["MON", "TUE", "WED", "THU", "FRI", "SAT"]:
            session.add(
                BaseRosterEntry(
                    id=uuid4(),
                    template_id=tpl.id,
                    employee_id=w1.id,
                    weekday_mask=dow,
                    assigned_hours=Decimal("8.0"),
                    sequence=1,
                )
            )

        await session.commit()

        return {
            "tag": tag,
            "admin_token": AuthService.create_access_token(admin_user),
            "eng_token": AuthService.create_access_token(eng_user),
            "supt_token": AuthService.create_access_token(supt_user),
            "sup_token": AuthService.create_access_token(sup_user),
            "w1_token": AuthService.create_access_token(w1_user),
            "admin_user_id": admin_user.id,
            "eng_emp_id": eng_emp.id,
            "supt_emp_id": supt_emp.id,
            "sup_emp_id": sup_emp.id,
            "w1_id": w1.id,
            "w1_tally": w1.tally_id,
            "w2_id": w2.id,
            "worksite_id": ws.id,
            "job_item_id": ji.id,
            "group_id": grp.id,
            "zone_id": zn.id,
            "template_id": tpl.id,
        }


async def teardown_batch3_context(ctx: dict, extra_emp_ids: list | None = None):
    emp_ids = [
        ctx["eng_emp_id"],
        ctx["supt_emp_id"],
        ctx["sup_emp_id"],
        ctx["w1_id"],
        ctx["w2_id"],
        *(extra_emp_ids or []),
    ]
    async with async_session_factory() as session:
        await session.execute(
            delete(ScheduledWork).where(ScheduledWork.job_item_id == ctx["job_item_id"])
        )
        await session.execute(
            delete(ScheduledWork).where(
                or_(
                    ScheduledWork.employee_id.in_(emp_ids),
                    ScheduledWork.original_employee_id.in_(emp_ids),
                )
            )
        )
        await session.execute(
            delete(ReassignmentRequest).where(
                or_(
                    ReassignmentRequest.original_employee_id.in_(emp_ids),
                    ReassignmentRequest.new_employee_id.in_(emp_ids),
                    ReassignmentRequest.target_job_item_id == ctx["job_item_id"],
                )
            )
        )
        await session.execute(
            delete(LeaveRequest).where(
                or_(
                    LeaveRequest.employee_id.in_(emp_ids),
                    LeaveRequest.cover_employee_id.in_(emp_ids),
                )
            )
        )
        tpls = (
            (
                await session.execute(
                    select(BaseRosterTemplate.id).where(
                        BaseRosterTemplate.job_item_id == ctx["job_item_id"]
                    )
                )
            )
            .scalars()
            .all()
        )
        if tpls:
            await session.execute(
                delete(BaseRosterEntry).where(BaseRosterEntry.template_id.in_(tpls))
            )
            await session.execute(delete(BaseRosterTemplate).where(BaseRosterTemplate.id.in_(tpls)))
        await session.execute(
            delete(JobOccurrence).where(JobOccurrence.job_item_id == ctx["job_item_id"])
        )
        await session.execute(delete(JobItem).where(JobItem.id == ctx["job_item_id"]))
        await session.execute(delete(Worksite).where(Worksite.id == ctx["worksite_id"]))
        await session.execute(delete(Group).where(Group.id == ctx["group_id"]))
        await session.execute(delete(Zone).where(Zone.id == ctx["zone_id"]))
        await session.execute(
            delete(EmployeeReportingLine).where(
                or_(
                    EmployeeReportingLine.employee_id.in_(emp_ids),
                    EmployeeReportingLine.manager_id.in_(emp_ids),
                )
            )
        )
        users = (
            (await session.execute(select(User.id).where(User.employee_id.in_(emp_ids))))
            .scalars()
            .all()
        )
        if users:
            await session.execute(delete(UserSession).where(UserSession.user_id.in_(users)))
            await session.execute(delete(AuditLog).where(AuditLog.actor_user_id.in_(users)))
            await session.execute(delete(User).where(User.id.in_(users)))
        await session.execute(
            delete(AuditLog).where(AuditLog.entity_id.in_([str(eid) for eid in emp_ids]))
        )
        await session.execute(delete(Employee).where(Employee.id.in_(emp_ids)))
        await session.commit()


@db_required
@pytest.mark.asyncio
async def test_role_controls_superintendent_edit_vs_supervisor_readonly():
    ctx = await seed_batch3_context()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            shift_date = (date.today() + timedelta(days=5)).isoformat()
            shift_payload = {
                "job_item_id": str(ctx["job_item_id"]),
                "work_date": shift_date,
                "employee_id": str(ctx["w2_id"]),
                "assigned_hours": 8.0,
                "source": "DIRECT",
                "status": "ACTIVE",
                "acknowledge_warnings": True,
            }

            # 1. Supervisor is BLOCKED (403) from directly writing Base Planner & Operational Planner
            sup_headers = {"Authorization": f"Bearer {ctx['sup_token']}"}
            res_sup_op = await client.post(
                "/api/v1/operational-planner/shifts", json=shift_payload, headers=sup_headers
            )
            assert res_sup_op.status_code == 403

            res_sup_base = await client.post(
                "/api/v1/base-planner/templates",
                json={
                    "job_item_id": str(ctx["job_item_id"]),
                    "allocation_mode": "DAY_OF_WEEK",
                    "start_date": date.today().isoformat(),
                    "entries": [],
                },
                headers=sup_headers,
            )
            assert res_sup_base.status_code == 403

            # 2. Superintendent is ALLOWED to write Operational Planner directly
            supt_headers = {"Authorization": f"Bearer {ctx['supt_token']}"}
            res_supt_op = await client.post(
                "/api/v1/operational-planner/shifts", json=shift_payload, headers=supt_headers
            )
            assert res_supt_op.status_code in (200, 201), res_supt_op.text
    finally:
        await teardown_batch3_context(ctx)


@db_required
@pytest.mark.asyncio
async def test_leave_auto_cover_weekly_off_indication_and_bulk_cover():
    ctx = await seed_batch3_context()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Pick a holiday-free Monday-based week well in the future (avoiding Dec 2-3 UAE National Day)
            next_mon = date(2027, 1, 11)
            tue = next_mon + timedelta(days=1)
            thu = next_mon + timedelta(days=3)
            wed = next_mon + timedelta(days=2)

            sup_headers = {"Authorization": f"Bearer {ctx['sup_token']}"}
            supt_headers = {"Authorization": f"Bearer {ctx['supt_token']}"}

            # 1. Supervisor submits leave with optional cover_employee_id = w2 (whose off day is WEDNESDAY)
            res_create = await client.post(
                "/api/v1/leave-requests",
                json={
                    "employee_id": str(ctx["w1_id"]),
                    "leave_type": "ANNUAL",
                    "from_date": tue.isoformat(),
                    "to_date": thu.isoformat(),
                    "reason": "Annual family trip",
                    "cover_employee_id": str(ctx["w2_id"]),
                },
                headers=sup_headers,
            )
            assert res_create.status_code == 201, res_create.text
            leave_data = res_create.json()
            assert leave_data["cover_employee_id"] == str(ctx["w2_id"])
            assert leave_data["weekly_off_mismatch"] is True
            leave_id = leave_data["id"]

            # Supervisor cannot approve
            res_sup_app = await client.post(
                f"/api/v1/leave-requests/{leave_id}/approve", headers=sup_headers
            )
            assert res_sup_app.status_code == 403

            # Superintendent approves -> auto-assigns cover for Tue, Wed (weekly off!), Thu
            res_app = await client.post(
                f"/api/v1/leave-requests/{leave_id}/approve", headers=supt_headers
            )
            assert res_app.status_code == 200, res_app.text

            async with async_session_factory() as session:
                covers = (
                    (
                        await session.execute(
                            select(ScheduledWork).where(
                                ScheduledWork.employee_id == ctx["w2_id"],
                                ScheduledWork.original_employee_id == ctx["w1_id"],
                                ScheduledWork.work_date >= tue,
                                ScheduledWork.work_date <= thu,
                                ScheduledWork.status == "ACTIVE",
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                by_date = {c.work_date: c for c in covers}
                assert tue in by_date
                assert wed in by_date, "Cover worker MUST still be assigned on their weekly off day"
                assert thu in by_date
                assert by_date[wed].is_weekly_off_cover is True
                assert by_date[tue].is_weekly_off_cover is False

            # Operational coverage view tags Wednesday as "Weekly Off (Covering)"
            cov_res = await client.get(
                f"/api/v1/operational-planner/coverage?week_start={next_mon.isoformat()}",
                headers=supt_headers,
            )
            assert cov_res.status_code == 200
            cov_json = cov_res.json()
            ws_row = next(
                w for w in cov_json["worksites"] if w["worksite_id"] == str(ctx["worksite_id"])
            )
            item_row = ws_row["items"][0]
            wed_cell = next(d for d in item_row["days"] if d["work_date"] == wed.isoformat())
            cover_chip = next(
                w for w in wed_cell["workers"] if w["employee_id"] == str(ctx["w2_id"])
            )
            assert "Weekly Off (Covering)" in cover_chip["tags"]

            # 2. Bulk Cover on a separate approved leave without pre-set cover
            next_week_mon = next_mon + timedelta(days=7)
            next_week_wed = next_week_mon + timedelta(days=2)
            res_leave2 = await client.post(
                "/api/v1/leave-requests",
                json={
                    "employee_id": str(ctx["w1_id"]),
                    "leave_type": "ANNUAL",
                    "from_date": next_week_mon.isoformat(),
                    "to_date": next_week_wed.isoformat(),
                    "reason": "Second leave for bulk cover test",
                },
                headers=sup_headers,
            )
            assert res_leave2.status_code == 201
            leave2_id = res_leave2.json()["id"]
            assert (
                await client.post(
                    f"/api/v1/leave-requests/{leave2_id}/approve", headers=supt_headers
                )
            ).status_code == 200

            res_bulk = await client.post(
                f"/api/v1/leave-requests/{leave2_id}/bulk-cover",
                json={"cover_employee_id": str(ctx["w2_id"])},
                headers=supt_headers,
            )
            assert res_bulk.status_code == 200, res_bulk.text
            bulk_data = res_bulk.json()
            assert bulk_data["covered_count"] == 3
            assert next_week_wed.isoformat() in bulk_data["weekly_off_cover_dates"]
    finally:
        await teardown_batch3_context(ctx)


@db_required
@pytest.mark.asyncio
async def test_supervisor_reassignment_batch_approve_and_reject():
    ctx = await seed_batch3_context()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            sup_headers = {"Authorization": f"Bearer {ctx['sup_token']}"}
            supt_headers = {"Authorization": f"Bearer {ctx['supt_token']}"}
            d1 = (date.today() + timedelta(days=5)).isoformat()
            d2 = (date.today() + timedelta(days=6)).isoformat()

            # Create batch of 2 requests
            res_batch = await client.post(
                "/api/v1/reassignment-requests/batch",
                json={
                    "batch_note": "Week cover plan",
                    "items": [
                        {
                            "reassignment_type": "ADD",
                            "date_from": d1,
                            "date_to": d1,
                            "new_employee_id": str(ctx["w2_id"]),
                            "target_job_item_id": str(ctx["job_item_id"]),
                            "reason_category": "CAPACITY",
                            "reason": "Extra gardener day 1",
                        },
                        {
                            "reassignment_type": "ADD",
                            "date_from": d2,
                            "date_to": d2,
                            "new_employee_id": str(ctx["w2_id"]),
                            "target_job_item_id": str(ctx["job_item_id"]),
                            "reason_category": "CAPACITY",
                            "reason": "Extra gardener day 2",
                        },
                    ],
                },
                headers=sup_headers,
            )
            assert res_batch.status_code == 201, res_batch.text
            b1 = res_batch.json()
            assert b1["count"] == 2
            batch_id = b1["batch_id"]

            # Supervisor cannot approve batch
            assert (
                await client.post(
                    f"/api/v1/reassignment-batches/{batch_id}/approve", json={}, headers=sup_headers
                )
            ).status_code == 403

            # Superintendent approves entire batch
            res_app = await client.post(
                f"/api/v1/reassignment-batches/{batch_id}/approve",
                json={"decision_note": "Approved all"},
                headers=supt_headers,
            )
            assert res_app.status_code == 200, res_app.text
            app_data = res_app.json()
            assert all(it["status"] == "APPROVED" for it in app_data["items"])

            # Create a second batch and Reject All
            d3 = (date.today() + timedelta(days=8)).isoformat()
            res_b2 = await client.post(
                "/api/v1/reassignment-requests/batch",
                json={
                    "batch_note": "Cancel batch test",
                    "items": [
                        {
                            "reassignment_type": "ADD",
                            "date_from": d3,
                            "date_to": d3,
                            "new_employee_id": str(ctx["w2_id"]),
                            "target_job_item_id": str(ctx["job_item_id"]),
                            "reason_category": "OTHER",
                            "reason": "Not needed",
                        }
                    ],
                },
                headers=sup_headers,
            )
            assert res_b2.status_code == 201
            batch2_id = res_b2.json()["batch_id"]

            res_rej = await client.post(
                f"/api/v1/reassignment-batches/{batch2_id}/reject",
                json={"decision_note": "Not required"},
                headers=supt_headers,
            )
            assert res_rej.status_code == 200
            assert all(it["status"] == "REJECTED" for it in res_rej.json()["items"])
    finally:
        await teardown_batch3_context(ctx)


@db_required
@pytest.mark.asyncio
async def test_tally_id_change_and_previously_used_guardrail():
    ctx = await seed_batch3_context()
    extra_emp_ids = []
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_headers = {"Authorization": f"Bearer {ctx['admin_token']}"}
            eng_headers = {"Authorization": f"Bearer {ctx['eng_token']}"}
            old_tally = ctx["w1_tally"]
            new_tally = f"PERM_B3_{ctx['tag']}"

            # Non-admin blocked
            assert (
                await client.post(
                    f"/api/v1/employees/{ctx['w1_id']}/change-tally-id",
                    json={"new_tally_id": new_tally, "reason": "Test"},
                    headers=eng_headers,
                )
            ).status_code == 403

            # Admin changes tally_id
            res_chg = await client.post(
                f"/api/v1/employees/{ctx['w1_id']}/change-tally-id",
                json={"new_tally_id": new_tally, "reason": "Probation complete"},
                headers=admin_headers,
            )
            assert res_chg.status_code == 200, res_chg.text
            assert res_chg.json()["tally_id"] == new_tally

            # Verify linked User.username updated atomically
            async with async_session_factory() as session:
                u = (
                    await session.execute(select(User).where(User.employee_id == ctx["w1_id"]))
                ).scalar_one()
                assert u.username == new_tally

            # Check old tally_id -> previously_used=True, available=True
            res_chk = await client.get(
                f"/api/v1/employees/check-tally-id?tally_id={old_tally}", headers=admin_headers
            )
            assert res_chk.status_code == 200
            chk = res_chk.json()
            assert chk["available"] is True
            assert chk["previously_used"] is True
            assert len(chk["previous_uses"]) >= 1

            # Creating a new employee reusing old_tally WITHOUT confirm_reuse -> 409 guardrail
            res_dup = await client.post(
                "/api/v1/employees",
                json={
                    "tally_id": old_tally,
                    "name": "New Temp Worker",
                    "role": "WORKER",
                    "country": "AE",
                },
                headers=admin_headers,
            )
            assert res_dup.status_code == 409
            assert res_dup.json()["code"] == "TALLY_ID_PREVIOUSLY_USED"

            # Retrying WITH confirm_reuse=True succeeds
            res_ok = await client.post(
                "/api/v1/employees",
                json={
                    "tally_id": old_tally,
                    "name": "New Temp Worker",
                    "role": "WORKER",
                    "country": "AE",
                    "confirm_reuse": True,
                },
                headers=admin_headers,
            )
            assert res_ok.status_code == 201, res_ok.text
            extra_emp_ids.append(res_ok.json()["id"])
    finally:
        await teardown_batch3_context(ctx, extra_emp_ids=extra_emp_ids)


@db_required
@pytest.mark.asyncio
async def test_admin_deactivation_login_block_staffing_gap_and_clean_reactivation():
    ctx = await seed_batch3_context()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_headers = {"Authorization": f"Bearer {ctx['admin_token']}"}
            eng_headers = {"Authorization": f"Bearer {ctx['eng_token']}"}
            w1_headers = {"Authorization": f"Bearer {ctx['w1_token']}"}

            # Verify w1 can access /auth/me before deactivation
            assert (await client.get("/api/v1/auth/me", headers=w1_headers)).status_code == 200

            # Non-admin blocked from deactivating
            assert (
                await client.post(
                    f"/api/v1/employees/{ctx['w1_id']}/deactivate",
                    json={
                        "reason": "Left",
                        "confirmation_text": "DEACTIVATE",
                        "admin_password": ADMIN_PW,
                    },
                    headers=eng_headers,
                )
            ).status_code == 403

            # Wrong password rejected (403)
            assert (
                await client.post(
                    f"/api/v1/employees/{ctx['w1_id']}/deactivate",
                    json={
                        "reason": "Left",
                        "confirmation_text": "DEACTIVATE",
                        "admin_password": "WrongPassword!",
                    },
                    headers=admin_headers,
                )
            ).status_code == 403

            # Wrong confirmation text rejected (400)
            assert (
                await client.post(
                    f"/api/v1/employees/{ctx['w1_id']}/deactivate",
                    json={
                        "reason": "Left",
                        "confirmation_text": "NOPE",
                        "admin_password": ADMIN_PW,
                    },
                    headers=admin_headers,
                )
            ).status_code == 400

            # Seed an explicit future shift for w1
            future_day = date.today() + timedelta(days=2)
            res_shift = await client.post(
                "/api/v1/operational-planner/shifts",
                json={
                    "job_item_id": str(ctx["job_item_id"]),
                    "work_date": future_day.isoformat(),
                    "employee_id": str(ctx["w1_id"]),
                    "assigned_hours": 8.0,
                    "source": "DIRECT",
                    "status": "ACTIVE",
                    "acknowledge_warnings": True,
                },
                headers=admin_headers,
            )
            assert res_shift.status_code in (200, 201)

            # Impact preview works
            imp = await client.get(
                f"/api/v1/employees/{ctx['w1_id']}/deactivation-impact", headers=admin_headers
            )
            assert imp.status_code == 200
            assert imp.json()["base_roster_slots"] == 6
            assert imp.json()["future_active_shifts"] >= 1

            # Admin deactivates w1
            res_deact = await client.post(
                f"/api/v1/employees/{ctx['w1_id']}/deactivate",
                json={
                    "reason": "Resigned",
                    "effective_date": date.today().isoformat(),
                    "confirmation_text": "DEACTIVATE",
                    "admin_password": ADMIN_PW,
                },
                headers=admin_headers,
            )
            assert res_deact.status_code == 200, res_deact.text
            assert res_deact.json()["is_active"] is False

            # 1. Login immediately blocked (403 ACCOUNT_INACTIVE)
            res_me = await client.get("/api/v1/auth/me", headers=w1_headers)
            assert res_me.status_code == 403

            # 2. Non-admin cannot view deactivated employee (404 on detail; excluded from list)
            assert (
                await client.get(f"/api/v1/employees/{ctx['w1_id']}", headers=eng_headers)
            ).status_code == 404
            eng_list = (
                await client.get("/api/v1/employees?is_active=false", headers=eng_headers)
            ).json()
            assert all(e["id"] != str(ctx["w1_id"]) for e in eng_list)

            # 3. Admin CAN view deactivated employee
            assert (
                await client.get(f"/api/v1/employees/{ctx['w1_id']}", headers=admin_headers)
            ).status_code == 200

            # 4. Staffing gaps surfaces DEACTIVATED gap for vacated shift
            gaps_resp = (
                await client.get(
                    f"/api/v1/staffing-gaps?from_date={date.today().isoformat()}&to_date={(date.today() + timedelta(days=7)).isoformat()}",
                    headers=admin_headers,
                )
            ).json()
            gaps = gaps_resp.get("gaps", gaps_resp) if isinstance(gaps_resp, dict) else gaps_resp
            deact_gaps = [
                g
                for g in gaps
                if g["original_employee_id"] == str(ctx["w1_id"]) and g["gap_type"] == "DEACTIVATED"
            ]
            assert len(deact_gaps) >= 1

            # 5. Option A Clean Reactivation: restores active & login, does NOT restore cancelled shifts
            res_react = await client.post(
                f"/api/v1/employees/{ctx['w1_id']}/reactivate",
                json={
                    "reason": "Rehired",
                    "confirmation_text": "REACTIVATE",
                    "admin_password": ADMIN_PW,
                },
                headers=admin_headers,
            )
            assert res_react.status_code == 200, res_react.text
            assert res_react.json()["is_active"] is True
            assert (await client.get("/api/v1/auth/me", headers=w1_headers)).status_code == 200

            async with async_session_factory() as session:
                active_shifts = (
                    (
                        await session.execute(
                            select(ScheduledWork).where(
                                ScheduledWork.employee_id == ctx["w1_id"],
                                ScheduledWork.status == "ACTIVE",
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                assert len(active_shifts) == 0, (
                    "Option A clean reactivation must NOT restore old shifts"
                )
                roster_entries = (
                    (
                        await session.execute(
                            select(BaseRosterEntry).where(
                                BaseRosterEntry.employee_id == ctx["w1_id"]
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                assert len(roster_entries) == 0

            # 6. Worksite deactivation frees worker schedule + hides from non-admin + clean reactivation
            ws_shift_day = date.today() + timedelta(days=3)
            await client.post(
                "/api/v1/operational-planner/shifts",
                json={
                    "job_item_id": str(ctx["job_item_id"]),
                    "work_date": ws_shift_day.isoformat(),
                    "employee_id": str(ctx["w2_id"]),
                    "assigned_hours": 8.0,
                    "source": "DIRECT",
                    "status": "ACTIVE",
                    "acknowledge_warnings": True,
                },
                headers=admin_headers,
            )

            res_ws_deact = await client.post(
                f"/api/v1/worksites/{ctx['worksite_id']}/deactivate",
                json={
                    "reason": "Contract ended",
                    "effective_date": date.today().isoformat(),
                    "confirmation_text": "DEACTIVATE",
                    "admin_password": ADMIN_PW,
                },
                headers=admin_headers,
            )
            assert res_ws_deact.status_code == 200, res_ws_deact.text

            # Non-admin cannot view deactivated worksite
            assert (
                await client.get(f"/api/v1/worksites/{ctx['worksite_id']}", headers=eng_headers)
            ).status_code == 404

            # Worker w2's shift on that worksite is now CANCELLED (freed)
            async with async_session_factory() as session:
                w2_active = (
                    (
                        await session.execute(
                            select(ScheduledWork).where(
                                ScheduledWork.employee_id == ctx["w2_id"],
                                ScheduledWork.job_item_id == ctx["job_item_id"],
                                ScheduledWork.status == "ACTIVE",
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                assert len(w2_active) == 0

            # Clean reactivate worksite
            res_ws_react = await client.post(
                f"/api/v1/worksites/{ctx['worksite_id']}/reactivate?reactivate_items=true",
                json={
                    "reason": "Contract renewed",
                    "confirmation_text": "REACTIVATE",
                    "admin_password": ADMIN_PW,
                },
                headers=admin_headers,
            )
            assert res_ws_react.status_code == 200
            assert res_ws_react.json()["is_active"] is True
    finally:
        await teardown_batch3_context(ctx)


@db_required
@pytest.mark.asyncio
async def test_single_standalone_admin_guardrails():
    """Verify DB and API guardrails enforce a single standalone ADMIN001 outside employees."""
    from sqlalchemy.exc import IntegrityError

    ctx = await seed_batch3_context()
    try:
        # 1. Verify standalone ADMIN001 has no employee record & no ADMIN exists in employees
        async with async_session_factory() as session:
            admins = (
                (await session.execute(select(User).where(User.role == "ADMIN"))).scalars().all()
            )
            assert len(admins) == 1
            assert admins[0].employee_id is None
            admin_emps = (
                (await session.execute(select(Employee).where(Employee.role == "ADMIN")))
                .scalars()
                .all()
            )
            assert len(admin_emps) == 0

        # 2. DB guardrail: inserting a second ADMIN user fails with IntegrityError
        async with async_session_factory() as session:
            session.add(
                User(
                    id=uuid4(),
                    employee_id=None,
                    username=f"SECOND_ADM_{ctx['tag']}",
                    credential_hash="hash",
                    role="ADMIN",
                    is_active=True,
                )
            )
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()

        # 3. DB guardrail: inserting an Employee with role='ADMIN' fails with IntegrityError
        async with async_session_factory() as session:
            session.add(
                Employee(
                    id=uuid4(),
                    tally_id=f"BAD_ADM_{ctx['tag']}",
                    name="Illegal Admin Emp",
                    role="ADMIN",
                    country="AE",
                    is_active=True,
                )
            )
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()

        # 4. API guardrails: POST /employees blocks role=ADMIN & tally_id=ADMIN001
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_headers = {"Authorization": f"Bearer {ctx['admin_token']}"}

            r_role = await client.post(
                "/api/v1/employees",
                json={
                    "tally_id": f"ADM_TRY_{ctx['tag']}",
                    "name": "Second Admin",
                    "role": "ADMIN",
                    "country": "AE",
                },
                headers=admin_headers,
            )
            assert r_role.status_code == 400
            assert r_role.json()["code"] == "ADMIN_ROLE_RESERVED"

            r_tally = await client.post(
                "/api/v1/employees",
                json={
                    "tally_id": "ADMIN001",
                    "name": "Fake Admin001",
                    "role": "WORKER",
                    "country": "AE",
                },
                headers=admin_headers,
            )
            assert r_tally.status_code == 400
            assert r_tally.json()["code"] == "RESERVED_TALLY_ID"

            # 5. API guardrail: PATCH /users/{w1_user} cannot promote to ADMIN
            async with async_session_factory() as session:
                w1_u = (
                    await session.execute(select(User).where(User.employee_id == ctx["w1_id"]))
                ).scalar_one()
                w1_uid, w1_ver = w1_u.id, w1_u.version
                adm_u = (
                    await session.execute(select(User).where(User.role == "ADMIN"))
                ).scalar_one()
                adm_uid, adm_ver = adm_u.id, adm_u.version

            r_prom = await client.patch(
                f"/api/v1/users/{w1_uid}",
                json={"role": "ADMIN", "version": w1_ver},
                headers=admin_headers,
            )
            assert r_prom.status_code == 400
            assert r_prom.json()["code"] == "ADMIN_ROLE_RESERVED"

            # 6. API guardrail: PATCH /users/{admin} cannot deactivate ADMIN001
            r_deact = await client.patch(
                f"/api/v1/users/{adm_uid}",
                json={"is_active": False, "version": adm_ver},
                headers=admin_headers,
            )
            assert r_deact.status_code == 400
    finally:
        await teardown_batch3_context(ctx)


@db_required
@pytest.mark.asyncio
async def test_unified_default_password_and_staff_grades_union():
    """Verify unified default_password for mobile/web and staff-grades union (employees + job_items)."""
    from fw.modules.settings import SettingsService
    from fw.modules.sync import SyncService

    ctx = await seed_batch3_context()
    extra_ji_id = uuid4()
    unique_job_grade = f"Contract Specialist {ctx['tag']}"
    try:
        async with async_session_factory() as session:
            # Add a JobItem whose staff_grade_description does NOT exist on any Employee
            session.add(
                JobItem(
                    id=extra_ji_id,
                    worksite_id=ctx["worksite_id"],
                    sub_item_code="99",
                    staff_grade_description=unique_job_grade,
                    planned_grade_code="G5A",
                    frequency_unit="WEEK",
                    occurrences_per_period=1,
                    period_interval=1,
                    required_staff_count=1,
                    hours_per_occurrence_per_staff=Decimal("8.0"),
                    start_date=date.today() - timedelta(days=7),
                    deployment_type="PERMANENT",
                    is_active=True,
                )
            )
            await session.commit()

            # Verify SyncService.get_default_password reads unified default_password setting
            prev = await SettingsService.get_setting(session, key="default_password", default=None)
            await SettingsService.set_setting(
                session,
                key="default_password",
                value="UnifiedPass!99",
                effective_from=date(2026, 1, 1),
            )
            await session.flush()
            resolved = await SyncService.get_default_password(session)
            assert resolved == "UnifiedPass!99"
            # Roll back setting change so we don't mutate local DB state
            await session.rollback()
            _ = prev

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            admin_headers = {"Authorization": f"Bearer {ctx['admin_token']}"}
            res = await client.get("/api/v1/settings/staff-grades", headers=admin_headers)
            assert res.status_code == 200
            grades = res.json()
            assert "Landscape Gardener" in grades
            assert unique_job_grade in grades
    finally:
        async with async_session_factory() as session:
            await session.execute(delete(JobItem).where(JobItem.id == extra_ji_id))
            await session.commit()
        await teardown_batch3_context(ctx)
