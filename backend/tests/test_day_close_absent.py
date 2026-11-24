"""ABSENT at day close, manual attendance times, and approved absences in payroll
(owner decisions 25 Nov 2026)."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.clock import site_today
from fw.main import app
from fw.modules.attendance import (
    AttendanceCalculation,
    AttendanceRecord,
    AttendanceService,
)
from fw.modules.attendance.day_close import DayCloseService
from fw.modules.attendance.schemas import AttendanceDecisionRequest
from fw.modules.audit.models import AuditLog
from fw.modules.identity import AuthService, User, UserService, hash_password
from fw.modules.jobs import JobItem, Worksite
from fw.modules.org import Employee, EmployeeReportingLine, Group, Zone
from fw.modules.payroll.models import EmployeeSalary
from fw.modules.scheduling import LeaveRequest, ScheduledWork
from fw.worker import WorkerScheduler
from tests.ids import unique_job_number
from tests.test_payroll_api import _cleanup_period

WEEKDAY_NAMES = ("MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY")


def _yesterday() -> date:
    return site_today("AE") - timedelta(days=1)


def _not_on(day: date) -> str:
    """A weekly off day that is not ``day``."""
    return WEEKDAY_NAMES[(day.weekday() + 3) % 7]


async def _item(session: AsyncSession) -> JobItem:
    sfx = uuid4().hex[:6]
    grp = Group(code=f"D{sfx}", name=f"Close group {sfx}")
    zn = Zone(code=f"D{sfx}", name=f"Close zone {sfx}")
    session.add_all([grp, zn])
    await session.flush()
    ws = Worksite(
        job_number=unique_job_number("32A"),
        job_name=f"Day close site {sfx}",
        group_id=grp.id,
        zone_id=zn.id,
        country="AE",
        start_date=date(2025, 1, 1),
        is_active=True,
    )
    session.add(ws)
    await session.flush()
    item = JobItem(
        worksite_id=ws.id,
        sub_item_code="A",
        staff_grade_description="Gardener Helper",
        planned_grade_code="G1A",
        frequency_unit="MONTH",
        occurrences_per_period=Decimal("20"),
        period_interval=1,
        required_staff_count=1,
        hours_per_occurrence_per_staff=Decimal("8"),
        start_date=date(2025, 1, 1),
        deployment_type="REMOTE",
        is_active=True,
    )
    session.add(item)
    await session.commit()
    return item


async def _employee(session: AsyncSession, weekly_off: str, role: str = "WORKER") -> Employee:
    emp = Employee(
        tally_id=f"DC{uuid4().hex[:8]}",
        name="Day Close Worker",
        role=role,
        country="AE",
        weekly_off_day=weekly_off,
        join_date=date(2025, 1, 1),
        is_active=True,
    )
    session.add(emp)
    await session.commit()
    return emp


async def _plan(session: AsyncSession, emp: Employee, item: JobItem, day: date) -> None:
    session.add(
        ScheduledWork(
            employee_id=emp.id,
            job_item_id=item.id,
            worksite_id=item.worksite_id,
            work_date=day,
            assigned_hours=Decimal("8"),
            sequence=1,
            status="ACTIVE",
            source="DIRECT",
        )
    )
    await session.commit()


async def _record(session: AsyncSession, emp: Employee, day: date) -> AttendanceRecord | None:
    return (
        await session.execute(
            select(AttendanceRecord)
            .where(AttendanceRecord.employee_id == emp.id, AttendanceRecord.work_date == day)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()


async def _calcs(session: AsyncSession, record: AttendanceRecord) -> list[AttendanceCalculation]:
    return list(
        (
            await session.execute(
                select(AttendanceCalculation)
                .where(AttendanceCalculation.attendance_record_id == record.id)
                .order_by(AttendanceCalculation.version_no)
            )
        )
        .scalars()
        .all()
    )


async def _user(session: AsyncSession, emp: Employee, role: str) -> tuple[User, str]:
    user = User(
        id=uuid4(),
        employee_id=emp.id,
        username=emp.tally_id,
        credential_hash=hash_password("Password123!"),
        role=role,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    return user, AuthService.create_access_token(user)


async def test_day_close_marks_planned_day_without_events_absent(db_session: AsyncSession) -> None:
    day = _yesterday()
    item = await _item(db_session)
    emp = await _employee(db_session, _not_on(day))
    await _plan(db_session, emp, item, day)
    admin = await UserService.get_or_create_system_admin(db_session)
    await db_session.commit()
    pending_before = await AttendanceService.count_attendance_reviews(db_session, admin)

    result = await DayCloseService.close_day(db_session, day, "AE")
    await db_session.commit()
    assert result["absent"] >= 1

    record = await _record(db_session, emp, day)
    assert record is not None
    assert (record.business_status, record.review_status) == ("ABSENT", "PENDING_REVIEW")
    (calc,) = await _calcs(db_session, record)
    assert calc.reason == "DAY_CLOSE"
    assert calc.required_minutes == 480 and calc.shortfall_minutes == 480
    assert "NO_ATTENDANCE_EVENTS" in (calc.flags or [])
    assert "No attendance data" in (calc.review_reasons or [])
    pending_after = await AttendanceService.count_attendance_reviews(db_session, admin)
    assert pending_after >= pending_before + 1

    # Running again the same day adds nothing.
    await DayCloseService.close_day(db_session, day, "AE")
    await db_session.commit()
    assert len(await _calcs(db_session, record)) == 1


async def test_day_close_exceptions_leave_weekly_off_and_unplanned(
    db_session: AsyncSession,
) -> None:
    day = _yesterday()
    item = await _item(db_session)
    admin = await UserService.get_or_create_system_admin(db_session)
    on_leave = await _employee(db_session, _not_on(day))
    off_today = await _employee(db_session, WEEKDAY_NAMES[day.weekday()])
    unplanned = await _employee(db_session, _not_on(day))
    await _plan(db_session, on_leave, item, day)
    await _plan(db_session, off_today, item, day)
    db_session.add(
        LeaveRequest(
            employee_id=on_leave.id,
            leave_type="SICK",
            from_date=day,
            to_date=day,
            reason="Sick",
            status="APPROVED",
            recorded_by_user_id=admin.id,
            approved_by_user_id=admin.id,
        )
    )
    await db_session.commit()

    await DayCloseService.close_day(db_session, day, "AE")
    await db_session.commit()
    for emp in (on_leave, off_today, unplanned):
        assert await _record(db_session, emp, day) is None


async def test_worker_day_close_job_twice(db_session: AsyncSession) -> None:
    day = _yesterday()
    item = await _item(db_session)
    emp = await _employee(db_session, _not_on(day))
    await _plan(db_session, emp, item, day)

    worker = WorkerScheduler()
    first = await worker.run_day_close("AE")
    second = await worker.run_day_close("AE")
    assert first is not None and first["absent"] >= 1
    assert second is not None and second["absent"] == 0
    record = await _record(db_session, emp, day)
    assert record is not None and len(await _calcs(db_session, record)) == 1


async def test_manual_times_new_version_audited_and_scoped(db_session: AsyncSession) -> None:
    day = _yesterday()
    item = await _item(db_session)
    emp = await _employee(db_session, _not_on(day))
    await _plan(db_session, emp, item, day)
    await DayCloseService.close_day(db_session, day, "AE")
    await db_session.commit()
    admin = await UserService.get_or_create_system_admin(db_session)
    await db_session.commit()
    admin_token = AuthService.create_access_token(admin)

    # An Engineer outside the worker's chain, an Engineer over the worker, and a Supervisor.
    eng_out = await _employee(db_session, _not_on(day), role="ENGINEER")
    eng_in = await _employee(db_session, _not_on(day), role="ENGINEER")
    db_session.add(
        EmployeeReportingLine(employee_id=emp.id, manager_id=eng_in.id, relationship="ENGINEER")
    )
    await db_session.commit()
    _, out_token = await _user(db_session, eng_out, "ENGINEER")
    _, in_token = await _user(db_session, eng_in, "ENGINEER")
    sup = await _employee(db_session, _not_on(day), role="SUPERVISOR")
    _, sup_token = await _user(db_session, sup, "SUPERVISOR")

    body = {
        "employee_id": str(emp.id),
        "work_date": day.isoformat(),
        "first_site_entry": "07:00",
        "last_site_exit": "15:30",
        "reason": "Phone battery died; supervisor confirmed on site all day",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:

        async def post(token: str, payload: dict) -> tuple[int, dict]:
            r = await c.post(
                "/api/v1/attendance/manual-times",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
            return r.status_code, r.json()

        assert (await post(admin_token, {**body, "reason": "   "}))[0] == 422
        assert (await post(admin_token, {**body, "reason": ""}))[0] == 422
        assert (await post(admin_token, {**body, "last_site_exit": "06:00"}))[0] == 422
        future = (site_today("AE") + timedelta(days=1)).isoformat()
        assert (await post(admin_token, {**body, "work_date": future}))[0] == 422
        assert (await post(out_token, body))[0] == 403
        assert (await post(sup_token, body))[0] == 403

        status, data = await post(in_token, body)
        assert status == 200, data
        calc = data["current_calculation"]
        assert calc["version_no"] == 2 and calc["reason"] == "MANUAL_CORRECTION"
        assert data["business_status"] == "PRESENT"
        assert data["review_status"] == "PENDING_REVIEW"
        assert "MANUAL_TIMES" in calc["flags"] and "Manual times" in calc["review_reasons"]
        # 07:00-15:30 is 510 minutes minus the usual break.
        assert calc["worked_minutes"] == 510 - calc["break_minutes_used"]

        # A second correction keeps every earlier version.
        status, data = await post(admin_token, {**body, "last_site_exit": "16:00"})
        assert status == 200 and data["current_calculation"]["version_no"] == 3

    record = await _record(db_session, emp, day)
    assert record is not None
    versions = await _calcs(db_session, record)
    assert [c.reason for c in versions] == ["DAY_CLOSE", "MANUAL_CORRECTION", "MANUAL_CORRECTION"]
    audits = (
        await db_session.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.action == "ATTENDANCE_MANUAL_TIMES",
                AuditLog.entity_id == str(record.id),
            )
        )
    ).scalar_one()
    assert audits == 2


async def test_payroll_deducts_approved_absence_only(db_session: AsyncSession) -> None:
    period_start, period_end = date(2026, 2, 1), date(2026, 2, 28)
    await _cleanup_period(db_session, period_start, period_end)
    item = await _item(db_session)
    approved_day, pending_day = date(2026, 2, 10), date(2026, 2, 11)
    emp = await _employee(db_session, "FRIDAY")  # 10 and 11 Feb 2026 are Tue and Wed
    db_session.add(
        EmployeeSalary(
            employee_id=emp.id,
            effective_from=date(2026, 1, 1),
            standard_hours=Decimal("8.0"),
            basic_salary=Decimal("2080.00"),  # basic / 208 = 10 an hour
        )
    )
    await db_session.commit()
    for day in (approved_day, pending_day):
        await _plan(db_session, emp, item, day)
        await DayCloseService.close_day(db_session, day, "AE")
    await db_session.commit()
    admin = await UserService.get_or_create_system_admin(db_session)
    await db_session.commit()
    approved_rec = await _record(db_session, emp, approved_day)
    assert approved_rec is not None and approved_rec.business_status == "ABSENT"
    await AttendanceService.record_decision(
        db_session,
        approved_rec.id,
        admin.id,
        AttendanceDecisionRequest(decision="APPROVED", comment="Absent, confirmed"),
    )
    await db_session.commit()

    token = AuthService.create_access_token(admin)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        headers = {"Authorization": f"Bearer {token}"}
        r = await c.post(
            "/api/v1/payroll/runs",
            headers=headers,
            json={
                "period_start": str(period_start),
                "period_end": str(period_end),
                "country": "AE",
            },
        )
        assert r.status_code == 201, r.text
        run = r.json()
        rec = next(x for x in run["records"] if x["employee_id"] == str(emp.id))
        # Only the approved absence: 8 h x 2080 / 208 = 80.00.
        assert Decimal(str(rec["shortfall_hours"])) == Decimal("8")
        assert Decimal(str(rec["missed_hours_deduction"])) == Decimal("80.00")

        issues = (await c.get(f"/api/v1/payroll/runs/{run['id']}/issues", headers=headers)).json()
    mine = [
        i
        for i in issues["issues"]
        if i["employee_id"] == str(emp.id) and i["issue_type"] == "PENDING_ABSENCE"
    ]
    assert [i["work_date"] for i in mine] == [pending_day.isoformat()]
    assert issues["pending_absence_count"] >= 1
