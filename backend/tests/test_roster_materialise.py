"""Base Planner templates become scheduled work (owner decision 25 Nov 2026, ADR-032).

Covers: the rolling window and idempotency, manual edits surviving a template change, leave and
weekly off, item and template end dates, holidays and the over-8 h warning, the Operational
Planner's remove/restore and replace/undo on template rows, and the daily job running twice.
"""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.clock import site_today
from fw.main import app  # noqa: F401  (registers every model)
from fw.modules.identity import UserService
from fw.modules.jobs import JobItem, Worksite
from fw.modules.org import Employee, Group, Zone
from fw.modules.scheduling import LeaveRequest, ScheduledWork, SchedulingService
from fw.modules.scheduling.materialise import RosterMaterialiser, materialise_weeks
from fw.modules.scheduling.models import BaseRosterEntry, BaseRosterTemplate
from fw.modules.scheduling.schemas import (
    BaseRosterEntryCreate,
    BaseRosterTemplateCreate,
    OperationalShiftCreate,
)
from fw.modules.settings import PublicHoliday
from fw.rules.scheduling import INT_TO_WEEKDAY
from fw.worker import WorkerScheduler
from tests.ids import unique_job_number

WEEKDAY_NAMES = ("MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY")


def _today() -> date:
    return site_today("AE")


def _off_name(day: date) -> str:
    return WEEKDAY_NAMES[day.weekday()]


async def _item(
    session: AsyncSession,
    *,
    end_date: date | None = None,
    deployment: str = "REMOTE",
) -> JobItem:
    sfx = uuid4().hex[:6]
    grp = Group(code=f"M{sfx}", name=f"Mat group {sfx}")
    zn = Zone(code=f"M{sfx}", name=f"Mat zone {sfx}")
    session.add_all([grp, zn])
    await session.flush()
    ws = Worksite(
        job_number=unique_job_number("31A"),
        job_name=f"Materialise site {sfx}",
        group_id=grp.id,
        zone_id=zn.id,
        country="AE",
        start_date=_today() - timedelta(days=60),
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
        required_staff_count=2,
        hours_per_occurrence_per_staff=Decimal("8"),
        start_date=_today() - timedelta(days=60),
        end_date=end_date,
        deployment_type=deployment,
        is_active=True,
    )
    session.add(item)
    await session.commit()
    return item


async def _employee(
    session: AsyncSession, *, weekly_off: str = "FRIDAY", active: bool = True
) -> Employee:
    emp = Employee(
        tally_id=f"MAT{uuid4().hex[:7]}",
        name="Materialise Worker",
        role="WORKER",
        country="AE",
        weekly_off_day=weekly_off,
        staff_grade_description="Gardener Helper",
        grade_code="G1A",
        join_date=date(2025, 1, 1),
        is_active=active,
    )
    session.add(emp)
    await session.commit()
    return emp


async def _save(
    session: AsyncSession,
    item: JobItem,
    entries: list[tuple[UUID, Decimal]],
    *,
    end: date | None = None,
) -> None:
    await SchedulingService(session).save_base_template(
        BaseRosterTemplateCreate(
            job_item_id=item.id,
            allocation_mode="UNIFORM",
            start_date=_today() - timedelta(days=30),
            end_date=end,
            entries=[
                BaseRosterEntryCreate(employee_id=e, weekday_mask="ALL", assigned_hours=h)
                for e, h in entries
            ],
        )
    )


async def _rows(session: AsyncSession, item: JobItem, emp: Employee | None = None) -> list:
    stmt = select(ScheduledWork).where(ScheduledWork.job_item_id == item.id)
    if emp is not None:
        stmt = stmt.where(ScheduledWork.employee_id == emp.id)
    stmt = stmt.order_by(ScheduledWork.work_date).execution_options(populate_existing=True)
    return list((await session.execute(stmt)).scalars().all())


async def _window(session: AsyncSession) -> list[date]:
    weeks = await materialise_weeks(session)
    t = _today()
    return [t + timedelta(days=i) for i in range(1, 7 * weeks + 1)]


async def test_window_filled_from_tomorrow_and_idempotent(db_session: AsyncSession) -> None:
    item = await _item(db_session)
    off_day = _today() + timedelta(days=3)
    emp = await _employee(db_session, weekly_off=_off_name(off_day))

    await _save(db_session, item, [(emp.id, Decimal("8"))])

    window = await _window(db_session)
    expected = [d for d in window if d.weekday() != off_day.weekday()]
    rows = await _rows(db_session, item)
    assert [r.work_date for r in rows] == expected
    assert all(r.source == "TEMPLATE" and r.status == "ACTIVE" for r in rows)
    assert all(r.version == 1 and r.sequence == 1 for r in rows)
    assert _today() not in {r.work_date for r in rows}

    again = await RosterMaterialiser.run(db_session, job_item_ids=[item.id])
    await db_session.commit()
    assert (again.created, again.updated, again.removed) == (0, 0, 0)
    assert len(await _rows(db_session, item)) == len(expected)


async def test_manual_edits_survive_a_template_change(db_session: AsyncSession) -> None:
    item = await _item(db_session)
    far_off = _today() + timedelta(days=5)
    a = await _employee(db_session, weekly_off=_off_name(far_off))
    b = await _employee(db_session, weekly_off=_off_name(far_off))
    await _save(db_session, item, [(a.id, Decimal("8"))])

    d1, d2 = _today() + timedelta(days=1), _today() + timedelta(days=2)
    svc = SchedulingService(db_session)
    # Remove A for d1 (the template row itself becomes the REMOVED marker) ...
    removed = await svc.create_operational_shift(
        OperationalShiftCreate(
            job_item_id=item.id,
            work_date=d1,
            employee_id=a.id,
            status="CANCELLED",
            source="OVERRIDE",
            override_reason="Site closed",
        )
    )
    # ... and replace A by B on d2.
    cover = await svc.create_operational_shift(
        OperationalShiftCreate(
            job_item_id=item.id,
            work_date=d2,
            employee_id=b.id,
            original_employee_id=a.id,
            source="OVERRIDE",
            override_reason="Cover",
        )
    )

    a_rows = {r.work_date: r for r in await _rows(db_session, item, a)}
    assert a_rows[d1].id == removed.id and a_rows[d1].status == "CANCELLED"
    assert a_rows[d2].status == "REASSIGNED" and a_rows[d2].version == 2
    cover_row = await db_session.get(ScheduledWork, cover.id)
    assert cover_row is not None and cover_row.original_scheduled_work_id == a_rows[d2].id

    # The template changes: A to 6 h, B added at 4 h.
    await _save(db_session, item, [(a.id, Decimal("6")), (b.id, Decimal("4"))])
    a_rows = {r.work_date: r for r in await _rows(db_session, item, a)}
    assert a_rows[d1].status == "CANCELLED" and a_rows[d1].assigned_hours == Decimal("8")
    assert a_rows[d2].status == "REASSIGNED" and a_rows[d2].assigned_hours == Decimal("8")
    untouched = [r for d, r in a_rows.items() if d not in (d1, d2)]
    assert untouched and all(r.assigned_hours == Decimal("6") for r in untouched)
    assert all(r.version == 1 for r in untouched)
    b_rows = await _rows(db_session, item, b)
    by_day: dict[date, list] = {}
    for r in b_rows:
        by_day.setdefault(r.work_date, []).append(r)
    # On d2 B has only the cover row (never a second, template row for the same item and day).
    assert [r.id for r in by_day[d2]] == [cover.id]
    assert all(r.source == "TEMPLATE" for d, rs in by_day.items() if d != d2 for r in rs)

    # A leaves the template: untouched rows go, the edited ones stay.
    await _save(db_session, item, [(b.id, Decimal("4"))])
    left = {r.work_date: r.status for r in await _rows(db_session, item, a)}
    assert left == {d1: "CANCELLED", d2: "REASSIGNED"}


async def test_remove_restore_and_replacement_undo(db_session: AsyncSession) -> None:
    item = await _item(db_session)
    far_off = _today() + timedelta(days=5)
    a = await _employee(db_session, weekly_off=_off_name(far_off))
    b = await _employee(db_session, weekly_off=_off_name(far_off))
    await _save(db_session, item, [(a.id, Decimal("8"))])
    d1, d2 = _today() + timedelta(days=1), _today() + timedelta(days=2)
    svc = SchedulingService(db_session)

    removed = await svc.create_operational_shift(
        OperationalShiftCreate(
            job_item_id=item.id, work_date=d1, employee_id=a.id, status="CANCELLED"
        )
    )
    await svc.delete_operational_shift(removed.id)
    row = await db_session.get(ScheduledWork, removed.id, populate_existing=True)
    assert row is not None and row.status == "ACTIVE" and row.source == "TEMPLATE"

    cover = await svc.create_operational_shift(
        OperationalShiftCreate(
            job_item_id=item.id,
            work_date=d2,
            employee_id=b.id,
            original_employee_id=a.id,
            source="OVERRIDE",
        )
    )
    await svc.delete_operational_shift(cover.id)
    a_rows = {r.work_date: r for r in await _rows(db_session, item, a)}
    assert a_rows[d2].status == "ACTIVE"
    cover_row = await db_session.get(ScheduledWork, cover.id, populate_existing=True)
    assert cover_row is not None and cover_row.status == "CANCELLED"


async def test_leave_and_weekly_off_are_skipped(db_session: AsyncSession) -> None:
    item = await _item(db_session)
    off_day = _today() + timedelta(days=4)
    emp = await _employee(db_session, weekly_off=_off_name(off_day))
    admin = await UserService.get_or_create_system_admin(db_session)
    leave_from, leave_to = _today() + timedelta(days=1), _today() + timedelta(days=2)
    db_session.add(
        LeaveRequest(
            employee_id=emp.id,
            leave_type="ANNUAL",
            from_date=leave_from,
            to_date=leave_to,
            reason="Planned",
            status="APPROVED",
            recorded_by_user_id=admin.id,
            approved_by_user_id=admin.id,
        )
    )
    await db_session.commit()

    await _save(db_session, item, [(emp.id, Decimal("8"))])
    days = {r.work_date for r in await _rows(db_session, item)}
    assert leave_from not in days and leave_to not in days
    assert all(d.weekday() != off_day.weekday() for d in days)

    # Leave approved after the window was filled: the untouched rows on those days go.
    later_from, later_to = _today() + timedelta(days=8), _today() + timedelta(days=9)
    assert {later_from, later_to} & days
    pending = LeaveRequest(
        employee_id=emp.id,
        leave_type="SICK",
        from_date=later_from,
        to_date=later_to,
        reason="Surgery",
        status="REQUESTED",
        recorded_by_user_id=admin.id,
    )
    db_session.add(pending)
    await db_session.commit()
    await SchedulingService(db_session).approve_leave_request(pending.id, admin)
    days = {r.work_date for r in await _rows(db_session, item)}
    assert later_from not in days and later_to not in days


async def test_item_and_template_end_dates(db_session: AsyncSession) -> None:
    far_off = _today() + timedelta(days=6)
    item_end = _today() + timedelta(days=3)
    item = await _item(db_session, end_date=item_end)
    emp = await _employee(db_session, weekly_off=_off_name(far_off))
    await _save(db_session, item, [(emp.id, Decimal("8"))])
    days = [r.work_date for r in await _rows(db_session, item)]
    assert days and max(days) == item_end
    assert days == [_today() + timedelta(days=i) for i in range(1, 4)]

    item2 = await _item(db_session)
    tmpl_end = _today() + timedelta(days=2)
    await _save(db_session, item2, [(emp.id, Decimal("4"))], end=tmpl_end)
    assert max(r.work_date for r in await _rows(db_session, item2)) == tmpl_end


async def test_inactive_employee_gets_no_rows(db_session: AsyncSession) -> None:
    item = await _item(db_session)
    emp = await _employee(db_session, active=False)
    await _save(db_session, item, [(emp.id, Decimal("8"))])
    assert await _rows(db_session, item) == []


async def test_holidays_scheduled_and_long_days_only_warned(db_session: AsyncSession) -> None:
    item = await _item(db_session)
    far_off = _today() + timedelta(days=6)
    emp = await _employee(db_session, weekly_off=_off_name(far_off))
    holiday = _today() + timedelta(days=2)
    exists = (
        await db_session.execute(
            select(PublicHoliday).where(
                PublicHoliday.holiday_date == holiday, PublicHoliday.country == "AE"
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        db_session.add(PublicHoliday(holiday_date=holiday, country="AE", name="Test holiday"))
    tmpl = BaseRosterTemplate(
        job_item_id=item.id, allocation_mode="UNIFORM", start_date=_today(), is_active=True
    )
    db_session.add(tmpl)
    await db_session.flush()
    db_session.add(
        BaseRosterEntry(
            template_id=tmpl.id,
            employee_id=emp.id,
            weekday_mask="ALL",
            assigned_hours=Decimal("10"),
            sequence=1,
        )
    )
    await db_session.commit()

    summary = await RosterMaterialiser.run(db_session, job_item_ids=[item.id])
    await db_session.commit()
    days = {r.work_date for r in await _rows(db_session, item)}
    assert holiday in days  # worked hours on it become OT2 in attendance
    assert summary.created == len(days) and summary.warnings == summary.created


async def test_daily_job_twice_in_a_day_changes_nothing(db_session: AsyncSession) -> None:
    item = await _item(db_session)
    far_off = _today() + timedelta(days=6)
    emp = await _employee(db_session, weekly_off=_off_name(far_off))
    tmpl = BaseRosterTemplate(
        job_item_id=item.id, allocation_mode="UNIFORM", start_date=_today(), is_active=True
    )
    db_session.add(tmpl)
    await db_session.flush()
    db_session.add(
        BaseRosterEntry(
            template_id=tmpl.id,
            employee_id=emp.id,
            weekday_mask=INT_TO_WEEKDAY[(_today() + timedelta(days=1)).weekday()],
            assigned_hours=Decimal("8"),
            sequence=1,
        )
    )
    await db_session.commit()

    worker = WorkerScheduler()
    first = await worker.run_roster_materialise()
    second = await worker.run_roster_materialise()
    assert first is not None and second is not None
    assert (second["created"], second["updated"], second["removed"]) == (0, 0, 0)
    rows = await _rows(db_session, item)
    weeks = await materialise_weeks(db_session)
    assert len(rows) == weeks  # one weekday a week across the window
    assert len({(r.employee_id, r.work_date) for r in rows}) == len(rows)
