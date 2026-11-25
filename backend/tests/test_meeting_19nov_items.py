"""19 Nov meeting items 5, 6, 7 and 11 (handover §4 item 6)."""

import io
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import openpyxl
import pytest
from httpx import ASGITransport, AsyncClient

from fw.core.clock import site_today
from fw.core.db import async_session_factory
from fw.main import app
from fw.modules.identity import User, hash_password
from fw.modules.jobs import JobItem, Worksite
from fw.modules.org import Employee, Group, Zone
from fw.modules.scheduling import (
    BaseRosterEntry,
    BaseRosterTemplate,
    LeaveRequest,
    ScheduledWork,
    SchedulingService,
    unmaterialised_template_slots,
)
from fw.rules.password import is_default_password_expired
from fw.rules.scheduling.leave import cover_weekly_off_affected
from fw.rules.scheduling.operational import OperationalShiftInput, resolve_operational_cell
from tests.test_batch6_features import get_admin_user_and_token


async def _admin() -> tuple[User, dict[str, str]]:
    async with async_session_factory() as session:
        user, token = await get_admin_user_and_token(session)
    return user, {"Authorization": f"Bearer {token}"}


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _worker(name: str = "Meeting Worker", off: str = "FRIDAY") -> Employee:
    async with async_session_factory() as session:
        emp = Employee(
            id=uuid4(),
            tally_id=f"M9{uuid4().hex[:6].upper()}",
            name=name,
            role="WORKER",
            country="AE",
            is_active=True,
            staff_grade_description="Landscape Gardener",
            grade_code="G2B",
            weekly_off_day=off or None,
            join_date=date.today() - timedelta(days=400),
        )
        session.add(emp)
        await session.commit()
        return emp


async def _site_item(deployment: str = "REMOTE") -> tuple[Worksite, JobItem]:
    async with async_session_factory() as session:
        group = Group(id=uuid4(), name=f"G-{uuid4().hex[:6]}", code=f"G{uuid4().hex[:4]}")
        zone = Zone(id=uuid4(), name=f"Z-{uuid4().hex[:6]}", code=f"Z{uuid4().hex[:4]}")
        session.add_all([group, zone])
        await session.flush()
        ws = Worksite(
            id=uuid4(),
            job_number=f"M9{uuid4().hex[:6].upper()}",
            job_name="Meeting Items Site",
            group_id=group.id,
            zone_id=zone.id,
            country="AE",
            is_active=True,
        )
        session.add(ws)
        await session.flush()
        item = JobItem(
            id=uuid4(),
            worksite_id=ws.id,
            sub_item_code="01",
            staff_grade_description="Landscape Gardener",
            planned_grade_code="G2B",
            frequency_unit="WEEK",
            occurrences_per_period=6,
            period_interval=1,
            required_staff_count=2,
            hours_per_occurrence_per_staff=Decimal("4.0"),
            start_date=date.today() - timedelta(days=30),
            deployment_type=deployment,
            is_active=True,
        )
        session.add(item)
        await session.commit()
        return ws, item


async def _template(item: JobItem, emp: Employee, mask: str = "ALL") -> None:
    async with async_session_factory() as session:
        tpl = BaseRosterTemplate(
            id=uuid4(),
            job_item_id=item.id,
            allocation_mode="DAY_OF_WEEK",
            start_date=date.today() - timedelta(days=14),
            is_active=True,
        )
        session.add(tpl)
        await session.flush()
        session.add(
            BaseRosterEntry(
                id=uuid4(),
                template_id=tpl.id,
                employee_id=emp.id,
                weekday_mask=mask,
                assigned_hours=Decimal("4.0"),
                sequence=1,
            )
        )
        await session.commit()


async def _leave(emp: Employee, start: date, end: date, status: str = "APPROVED") -> None:
    admin, _ = await _admin()
    async with async_session_factory() as session:
        session.add(
            LeaveRequest(
                id=uuid4(),
                employee_id=emp.id,
                leave_type="ANNUAL",
                from_date=start,
                to_date=end,
                status=status,
                reason="test",
                recorded_by_user_id=admin.id,
                is_active=True,
            )
        )
        await session.commit()


# ---- Item 7: an Admin reset restarts the default-password window --------------------------


def test_default_password_expiry_counts_from_issue() -> None:
    now = datetime.now(UTC)
    assert is_default_password_expired(True, now - timedelta(days=8), now, max_days=7)
    assert not is_default_password_expired(True, now - timedelta(days=1), now, max_days=7)


@pytest.mark.asyncio
async def test_admin_reset_of_old_account_lets_user_log_in() -> None:
    _, headers = await _admin()
    emp = await _worker("Old Account Person")
    async with async_session_factory() as session:
        user = User(
            username=f"M9{uuid4().hex[:8].upper()}",
            credential_hash=hash_password("Whatever-123"),
            role="SUPERVISOR",
            employee_id=emp.id,
            is_active=True,
            must_change_password=True,
            password_changed_at=None,
            created_at=datetime.now(UTC) - timedelta(days=90),
        )
        session.add(user)
        await session.commit()
        user_id, username = user.id, user.username

    async with _client() as client:
        res = await client.post(f"/api/v1/users/{user_id}/reset-password", headers=headers)
        assert res.status_code == 200, res.text
        settings = await client.get("/api/v1/settings/values/default_password", headers=headers)
        default_pw = "ChangeMe123!"
        if settings.status_code == 200 and settings.json().get("value"):
            default_pw = str(settings.json()["value"])
        login = await client.post(
            "/api/v1/auth/login", json={"username": username, "password": default_pw}
        )
        assert login.status_code == 200, login.text

        users = await client.get("/api/v1/users?limit=1000", headers=headers)
        mine = next(u for u in users.json() if u["id"] == str(user_id))
        assert mine["employee_name"] == "Old Account Person"


# ---- Item 11: template-only workers are scheduled on the Live Map ----------------------------


@pytest.mark.asyncio
async def test_template_only_worker_is_scheduled_today() -> None:
    _, headers = await _admin()
    emp = await _worker(off="")
    _, item = await _site_item()
    await _template(item, emp)
    today = site_today()

    async with async_session_factory() as session:
        slots = await unmaterialised_template_slots(session, today, {emp.id})
    assert [s.employee_id for s in slots] == [emp.id]

    async with _client() as client:
        res = await client.get("/api/v1/live/positions", headers=headers)
        assert res.status_code == 200, res.text
        mine = [w for w in res.json()["items"] if w["employee_id"] == str(emp.id)]
        assert mine and mine[0]["live_state"] != "NOT_SCHEDULED"

    # Any scheduled work that day (even cancelled) means the planner decided: no template slot.
    async with async_session_factory() as session:
        session.add(
            ScheduledWork(
                id=uuid4(),
                employee_id=emp.id,
                job_item_id=item.id,
                worksite_id=item.worksite_id,
                work_date=today,
                assigned_hours=Decimal("4.0"),
                sequence=1,
                status="CANCELLED",
                source="DIRECT",
                version=1,
            )
        )
        await session.commit()
        assert await unmaterialised_template_slots(session, today, {emp.id}) == []


# ---- Item 5: leave labels, warnings, cover choices -----------------------------------------


def test_extra_staff_on_leave_shows_leave_gap_until_covered() -> None:
    d = date(2026, 12, 1)
    worker, cover, shift_id = uuid4(), uuid4(), uuid4()
    direct = OperationalShiftInput(
        id=shift_id,
        work_date=d,
        employee_id=worker,
        source="DIRECT",
        original_employee_id=None,
        override_reason=None,
        assigned_hours=4.0,
    )
    cells = resolve_operational_cell(d, [], {worker}, [direct])
    assert [(c.display_type, c.employee_id) for c in cells] == [("TO_BE_COVERED", worker)]
    assert "Extra Staff" in cells[0].tags

    covering = OperationalShiftInput(
        id=uuid4(),
        work_date=d,
        employee_id=cover,
        source="OVERRIDE",
        original_employee_id=worker,
        override_reason="Leave Cover",
        assigned_hours=4.0,
    )
    cells = resolve_operational_cell(d, [], {worker}, [direct, covering])
    assert [(c.display_type, c.employee_id) for c in cells] == [("OVERRIDE", cover)]


def test_off_day_warning_only_when_the_leave_hits_the_covers_off_day() -> None:
    mon = date(2026, 11, 30)  # a Monday
    assert not cover_weekly_off_affected(mon, mon + timedelta(days=2), "FRI", "SAT")
    assert cover_weekly_off_affected(mon, mon + timedelta(days=5), "FRI", "SAT")
    assert not cover_weekly_off_affected(mon, mon + timedelta(days=20), "FRIDAY", "FRI")
    assert not cover_weekly_off_affected(mon, mon + timedelta(days=20), "FRI", None)


@pytest.mark.asyncio
async def test_staffing_gaps_include_extra_staff_on_leave() -> None:
    admin, _ = await _admin()
    emp = await _worker()
    _, item = await _site_item()
    day = date.today() + timedelta(days=10)
    async with async_session_factory() as session:
        session.add(
            ScheduledWork(
                id=uuid4(),
                employee_id=emp.id,
                job_item_id=item.id,
                worksite_id=item.worksite_id,
                work_date=day,
                assigned_hours=Decimal("4.0"),
                sequence=1,
                status="ACTIVE",
                source="DIRECT",
                version=1,
            )
        )
        await session.commit()
    await _leave(emp, day, day)
    async with async_session_factory() as session:
        gaps = await SchedulingService(session).get_staffing_gaps(day, day, admin)
    mine = [g for g in gaps.gaps if g.original_employee_id == emp.id]
    assert len(mine) == 1 and mine[0].job_item_id == item.id


@pytest.mark.asyncio
async def test_cover_availability_excludes_leave_and_permanent_work() -> None:
    _, headers = await _admin()
    on_leave, permanent, free = await _worker(), await _worker(), await _worker()
    _, perm_item = await _site_item("PERMANENT")
    await _template(perm_item, permanent)
    start = date.today() + timedelta(days=20)
    end = start + timedelta(days=6)
    await _leave(on_leave, start, start + timedelta(days=1), status="REQUESTED")

    async with _client() as client:
        res = await client.get(
            f"/api/v1/leave-requests/cover-availability?from_date={start}&to_date={end}",
            headers=headers,
        )
        assert res.status_code == 200, res.text
        unavailable = res.json()["unavailable"]
    assert unavailable.get(str(on_leave.id)) == "ON_LEAVE"
    assert unavailable.get(str(permanent.id)) == "ASSIGNED"
    assert str(free.id) not in unavailable


# ---- Item 6: assignments export and import -------------------------------------------------


def _sheet(rows: list[list[object]]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Assignments"
    ws.append(["Job Number", "Sub Item Code", "Work Date", "Tally ID", "Assigned Hours"])
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_assignments_import_checks_then_adds_and_export_round_trips() -> None:
    _, headers = await _admin()
    emp = await _worker(off="")
    ws, _item = await _site_item()
    day = date.today() + timedelta(days=3)
    content = _sheet(
        [
            [ws.job_number, "01", day, emp.tally_id, 4],
            [ws.job_number, "99", day, emp.tally_id, 4],
            [ws.job_number, "01", day, "NOBODY-X", 4],
        ]
    )
    upload = {"Content-Type": "application/octet-stream", **headers}
    url = "/api/v1/operational-planner/assignments/import"
    async with _client() as client:
        check = await client.post(f"{url}?dry_run=true", content=content, headers=upload)
        assert check.status_code == 200, check.text
        body = check.json()
        assert (body["would_create"], body["errors"], body["created"]) == (1, 2, 0)

        done = await client.post(f"{url}?dry_run=false", content=content, headers=upload)
        assert done.json()["created"] == 1, done.text

        again = await client.post(f"{url}?dry_run=false", content=content, headers=upload)
        assert (again.json()["created"], again.json()["existing"]) == (0, 1)

        exp = await client.get(
            f"/api/v1/operational-planner/assignments.xlsx?from_date={day}&to_date={day}",
            headers=headers,
        )
        assert exp.status_code == 200
        sheet = openpyxl.load_workbook(io.BytesIO(exp.content)).active
        assert sheet is not None
        rows = [r for r in sheet.iter_rows(min_row=2, values_only=True) if r[4] == emp.tally_id]
        assert len(rows) == 1 and rows[0][0] == ws.job_number and rows[0][2] == "01"

        too_long = await client.get(
            f"/api/v1/operational-planner/assignments.xlsx?from_date={day}"
            f"&to_date={day + timedelta(days=200)}",
            headers=headers,
        )
        assert too_long.status_code == 400


@pytest.mark.asyncio
async def test_assignments_import_is_not_for_supervisors() -> None:
    emp = await _worker()
    async with async_session_factory() as session:
        user = User(
            username=f"M9{uuid4().hex[:8].upper()}",
            credential_hash=hash_password("Whatever-123"),
            role="SUPERVISOR",
            employee_id=emp.id,
            is_active=True,
            must_change_password=False,
        )
        session.add(user)
        await session.commit()
        user_id: UUID = user.id
    from fw.modules.identity import AuthService

    async with async_session_factory() as session:
        sup = await session.get(User, user_id)
        assert sup is not None
        token = AuthService.create_access_token(sup)
    async with _client() as client:
        res = await client.post(
            "/api/v1/operational-planner/assignments/import",
            content=_sheet([]),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 403
