"""Integration tests for worksite-based scope (DEC-57) on top of the crew chain (DEC-10).

Scenario (all created fresh per test):
- Supervisor A with worker WA in A's crew; Supervisor B with worker WB in B's crew.
- Engineer E is linked to Supervisor A, so E's crew is {E, A, WA}.
- Worksite SA is assigned to A, SB to B, SU has no supervisor.
- Today WA works on SB (B's site) and WB works on SA (A's site): both are cross-crew.
"""

import io
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import openpyxl
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from fw.core.clock import site_today
from fw.core.db import async_session_factory
from fw.main import create_app
from fw.modules.attendance.models import AttendanceRecord
from fw.modules.identity import User
from fw.modules.identity.service import AuthService, hash_password
from fw.modules.jobs.models import JobItem, Worksite, WorksiteSupervisor
from fw.modules.org.models import Employee, EmployeeReportingLine, Group, Zone
from fw.modules.scheduling.models import ScheduledWork, StandingAssignment
from tests.test_batch6_features import db_required, get_admin_user_and_token

pytestmark = [db_required, pytest.mark.asyncio]


@dataclass
class Scenario:
    admin_token: str
    sup_a: Employee
    sup_a_token: str
    sup_b: Employee
    sup_b_token: str
    eng: Employee
    eng_token: str
    wa: Employee
    wb: Employee
    site_a: Worksite
    site_b: Worksite
    site_u: Worksite
    item_u: JobItem
    rec_wa: AttendanceRecord
    rec_wb: AttendanceRecord


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _person(session, role: str, label: str) -> tuple[Employee, str]:
    emp = Employee(
        tally_id=f"T{uuid4().hex[:7]}",
        name=f"{label} {uuid4().hex[:4]}",
        role=role,
        is_active=True,
        country="AE",
    )
    session.add(emp)
    await session.flush()
    token = ""
    if role != "WORKER":
        user = User(
            username=f"u_{uuid4().hex[:10]}",
            credential_hash=hash_password("Password123!"),
            role=role,
            is_active=True,
            employee_id=emp.id,
        )
        session.add(user)
        await session.flush()
        token = AuthService.create_access_token(user)
    return emp, token


async def _site(session, name: str) -> tuple[Worksite, JobItem]:
    grp = Group(name=f"G {uuid4().hex[:6]}", code=f"G{uuid4().hex[:6]}")
    zn = Zone(name=f"Z {uuid4().hex[:6]}", code=f"Z{uuid4().hex[:6]}")
    session.add_all([grp, zn])
    await session.flush()
    ws = Worksite(
        job_number=f"26A{uuid4().int % 100000:05d}",
        job_name=name,
        group_id=grp.id,
        zone_id=zn.id,
        country="AE",
        is_active=True,
        budget_amount=Decimal("1000.00"),
    )
    session.add(ws)
    await session.flush()
    item = JobItem(
        worksite_id=ws.id,
        sub_item_code="A",
        staff_grade_description="Helper",
        planned_grade_code="G1A",
        frequency_unit="WEEK",
        occurrences_per_period=Decimal("6.0"),
        period_interval=1,
        required_staff_count=1,
        hours_per_occurrence_per_staff=Decimal("8.0"),
        start_date=site_today("AE") - timedelta(days=60),
        deployment_type="PERMANENT",
        is_active=True,
    )
    session.add(item)
    await session.flush()
    return ws, item


async def _build() -> Scenario:
    today = site_today("AE")
    async with async_session_factory() as session:
        _, admin_token = await get_admin_user_and_token(session)
        sup_a, sup_a_token = await _person(session, "SUPERVISOR", "Sup A")
        sup_b, sup_b_token = await _person(session, "SUPERVISOR", "Sup B")
        eng, eng_token = await _person(session, "ENGINEER", "Eng")
        wa, _ = await _person(session, "WORKER", "WA")
        wb, _ = await _person(session, "WORKER", "WB")
        session.add_all(
            [
                EmployeeReportingLine(
                    employee_id=wa.id, manager_id=sup_a.id, relationship="SUPERVISOR"
                ),
                EmployeeReportingLine(
                    employee_id=wb.id, manager_id=sup_b.id, relationship="SUPERVISOR"
                ),
                EmployeeReportingLine(
                    employee_id=sup_a.id, manager_id=eng.id, relationship="ENGINEER"
                ),
            ]
        )
        site_a, item_a = await _site(session, "Site A")
        site_b, item_b = await _site(session, "Site B")
        site_u, item_u = await _site(session, "Site U")
        session.add_all(
            [
                WorksiteSupervisor(worksite_id=site_a.id, supervisor_id=sup_a.id),
                WorksiteSupervisor(worksite_id=site_b.id, supervisor_id=sup_b.id),
            ]
        )
        for emp, ws, item in ((wa, site_b, item_b), (wb, site_a, item_a)):
            session.add(
                ScheduledWork(
                    work_date=today,
                    employee_id=emp.id,
                    job_item_id=item.id,
                    worksite_id=ws.id,
                    assigned_hours=Decimal("8.00"),
                    status="ACTIVE",
                )
            )
        rec_wa = AttendanceRecord(employee_id=wa.id, work_date=today)
        rec_wb = AttendanceRecord(employee_id=wb.id, work_date=today)
        session.add_all([rec_wa, rec_wb])
        await session.commit()
        return Scenario(
            admin_token=admin_token,
            sup_a=sup_a,
            sup_a_token=sup_a_token,
            sup_b=sup_b,
            sup_b_token=sup_b_token,
            eng=eng,
            eng_token=eng_token,
            wa=wa,
            wb=wb,
            site_a=site_a,
            site_b=site_b,
            site_u=site_u,
            item_u=item_u,
            rec_wa=rec_wa,
            rec_wb=rec_wb,
        )


@pytest.fixture
async def ctx():
    scenario = await _build()
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, scenario


async def _ids(client: AsyncClient, url: str, token: str, key: str = "id") -> set[str]:
    resp = await client.get(url, headers=_h(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = body["items"] if isinstance(body, dict) and "items" in body else body
    return {str(i[key]) for i in items}


async def test_worksite_lists_and_detail_follow_assignments(ctx) -> None:
    client, s = ctx
    sup_sites = await _ids(client, "/api/v1/worksites?limit=500", s.sup_a_token)
    assert str(s.site_a.id) in sup_sites
    assert str(s.site_b.id) not in sup_sites and str(s.site_u.id) not in sup_sites

    eng_sites = await _ids(client, "/api/v1/worksites?limit=500", s.eng_token)
    assert str(s.site_a.id) in eng_sites and str(s.site_b.id) not in eng_sites

    for url in (f"/api/v1/worksites/{s.site_b.id}", f"/api/v1/worksites/{s.site_b.id}/supervisors"):
        resp = await client.get(url, headers=_h(s.sup_a_token))
        assert resp.status_code == 404, url
    assert (
        await client.get(f"/api/v1/worksites/{s.site_a.id}", headers=_h(s.sup_a_token))
    ).status_code == 200


async def test_unassigned_filter_and_dashboard_count_are_admin_views(ctx) -> None:
    client, s = ctx
    unassigned = await _ids(client, "/api/v1/worksites?unassigned=true&limit=500", s.admin_token)
    assert str(s.site_u.id) in unassigned and str(s.site_a.id) not in unassigned

    admin_dash = (await client.get("/api/v1/dashboard/summary", headers=_h(s.admin_token))).json()
    assert admin_dash["unassigned_worksites_count"] >= 1
    sup_dash = (await client.get("/api/v1/dashboard/summary", headers=_h(s.sup_a_token))).json()
    assert sup_dash["unassigned_worksites_count"] is None


async def test_destinations_list_every_active_job_item_without_costs(ctx) -> None:
    client, s = ctx
    resp = await client.get("/api/v1/job-items/destinations", headers=_h(s.sup_a_token))
    assert resp.status_code == 200
    rows = resp.json()
    worksite_ids = {r["worksite_id"] for r in rows}
    assert {str(s.site_a.id), str(s.site_b.id), str(s.site_u.id)} <= worksite_ids
    assert all("budget_amount" not in r for r in rows)


async def test_employee_directory_crew_full_site_workers_read_only(ctx) -> None:
    client, s = ctx
    resp = await client.get("/api/v1/employees?limit=500", headers=_h(s.sup_a_token))
    assert resp.status_code == 200
    by_id = {e["id"]: e for e in resp.json()}
    assert by_id[str(s.wa.id)]["read_only"] is False  # own crew, working elsewhere today
    assert by_id[str(s.wb.id)]["read_only"] is True  # B's crew on A's site
    assert str(s.sup_b.id) not in by_id

    detail = await client.get(f"/api/v1/employees/{s.wb.id}", headers=_h(s.sup_a_token))
    assert detail.status_code == 200 and detail.json()["read_only"] is True
    other = await client.get(f"/api/v1/employees/{s.sup_b.id}", headers=_h(s.sup_a_token))
    assert other.status_code == 403


async def test_attendance_follows_the_site_day(ctx) -> None:
    client, s = ctx
    today = site_today("AE").isoformat()
    url = f"/api/v1/attendance?from_date={today}&to_date={today}&limit=200"
    resp = await client.get(url, headers=_h(s.sup_a_token))
    assert resp.status_code == 200
    rows = {r["employee_id"]: r for r in resp.json()["items"]}
    # A sees WB (on A's site, read-only) but not A's own WA (on B's site today).
    assert rows[str(s.wb.id)]["read_only"] is True
    assert str(s.wa.id) not in rows

    b_rows = {
        r["employee_id"] for r in (await client.get(url, headers=_h(s.sup_b_token))).json()["items"]
    }
    assert str(s.wa.id) in b_rows and str(s.wb.id) not in b_rows

    assert (
        await client.get(f"/api/v1/attendance/{s.rec_wa.id}", headers=_h(s.sup_a_token))
    ).status_code == 403


async def test_cross_crew_worker_comment_allowed_decision_refused(ctx) -> None:
    client, s = ctx
    # Engineer E: crew {A, WA}; WB is on A's site today, so E sees WB read-only.
    comment = await client.post(
        f"/api/v1/attendance/{s.rec_wb.id}/comments",
        headers=_h(s.eng_token),
        json={"comment_type": "GENERAL", "comment_text": "Seen on site A"},
    )
    assert comment.status_code in (200, 201), comment.text
    decision = await client.post(
        f"/api/v1/attendance/{s.rec_wb.id}/decisions",
        headers=_h(s.eng_token),
        json={"decision": "APPROVED"},
    )
    assert decision.status_code == 403
    assert "READ_ONLY_SCOPE" in decision.text


async def test_live_trail_refuses_out_of_scope_worker(ctx) -> None:
    client, s = ctx
    resp = await client.get(f"/api/v1/live/trail/{s.wa.id}", headers=_h(s.sup_a_token))
    assert resp.status_code == 403
    resp = await client.get(f"/api/v1/live/trail/{s.wb.id}", headers=_h(s.sup_a_token))
    assert resp.status_code == 200


async def test_proposals_and_bulk_assign(ctx) -> None:
    client, s = ctx
    async with async_session_factory() as session:
        session.add(
            StandingAssignment(
                employee_id=s.wa.id,
                job_item_id=s.item_u.id,
                start_date=site_today("AE") - timedelta(days=5),
                is_active=True,
            )
        )
        await session.commit()

    assert (
        await client.get("/api/v1/worksites/supervisor-proposals", headers=_h(s.sup_a_token))
    ).status_code == 403
    resp = await client.get("/api/v1/worksites/supervisor-proposals", headers=_h(s.admin_token))
    assert resp.status_code == 200
    by_site = {p["worksite_id"]: p for p in resp.json()}
    proposal = by_site[str(s.site_u.id)]
    assert [p["supervisor_id"] for p in proposal["proposals"]] == [str(s.sup_a.id)]
    assert str(s.site_a.id) not in by_site  # assigned and nothing new to propose

    pairs = {"assignments": [{"worksite_id": str(s.site_u.id), "supervisor_id": str(s.sup_a.id)}]}
    first = await client.post(
        "/api/v1/worksites/supervisors/bulk-assign", headers=_h(s.admin_token), json=pairs
    )
    assert first.status_code == 200 and first.json() == {"assigned": 1, "already_assigned": 0}
    again = await client.post(
        "/api/v1/worksites/supervisors/bulk-assign", headers=_h(s.admin_token), json=pairs
    )
    assert again.json() == {"assigned": 0, "already_assigned": 1}
    assert str(s.site_u.id) in await _ids(client, "/api/v1/worksites?limit=500", s.sup_a_token)


async def test_role_change_ends_worksite_assignments(ctx) -> None:
    client, s = ctx
    async with async_session_factory() as session:
        version = (await session.get(Employee, s.sup_b.id)).version  # type: ignore[union-attr]
    resp = await client.patch(
        f"/api/v1/employees/{s.sup_b.id}",
        headers=_h(s.admin_token),
        json={"role": "WORKER", "version": version},
    )
    assert resp.status_code == 200, resp.text
    async with async_session_factory() as session:
        row = await session.scalar(
            select(WorksiteSupervisor).where(
                WorksiteSupervisor.worksite_id == s.site_b.id,
                WorksiteSupervisor.supervisor_id == s.sup_b.id,
            )
        )
        assert row is not None and row.is_active is False


def _ws_sup_workbook(rows: list[tuple[str, str]]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Worksite_Supervisors"
    for c, name in enumerate(["#", "job_number", "supervisor_tally_id", "notes"], start=1):
        ws.cell(row=4, column=c, value=name)
    for r, (job, tally) in enumerate(rows, start=5):
        ws.cell(row=r, column=2, value=job)
        ws.cell(row=r, column=3, value=tally)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


async def _upload(client: AsyncClient, token: str, content: bytes) -> dict:
    files = {
        "file": (
            "ws_sup.xlsx",
            content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    resp = await client.post(
        "/api/v1/imports?sheets=Worksite_Supervisors", headers=_h(token), files=files
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_worksite_supervisors_import_is_validated_and_idempotent(ctx) -> None:
    client, s = ctx
    bad = await _upload(
        client, s.admin_token, _ws_sup_workbook([(s.site_u.job_number, s.wa.tally_id)])
    )
    assert bad["can_commit"] is False
    preview = (
        await client.get(f"/api/v1/imports/{bad['batch_id']}/preview", headers=_h(s.admin_token))
    ).json()
    assert any("NOT_A_SUPERVISOR" in r["codes"] for r in preview["rows"])

    content = _ws_sup_workbook([(s.site_u.job_number, s.sup_b.tally_id)])
    first = await _upload(client, s.admin_token, content)
    assert first["can_commit"] is True
    commit = await client.post(
        f"/api/v1/imports/{first['batch_id']}/commit", headers=_h(s.admin_token)
    )
    assert commit.status_code == 200, commit.text
    assert str(s.site_u.id) in await _ids(client, "/api/v1/worksites?limit=500", s.sup_b_token)

    second = await _upload(client, s.admin_token, content)
    counts = second["summary"]["counts"]
    assert counts["NEW"] == 0 and counts["UNCHANGED"] == 1
    async with async_session_factory() as session:
        n = len(
            (
                await session.execute(
                    select(WorksiteSupervisor).where(
                        WorksiteSupervisor.worksite_id == s.site_u.id,
                        WorksiteSupervisor.supervisor_id == UUID(str(s.sup_b.id)),
                    )
                )
            )
            .scalars()
            .all()
        )
    assert n == 1
