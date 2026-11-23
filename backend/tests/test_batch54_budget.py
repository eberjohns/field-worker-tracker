"""Batch 5.4: job budget and man-hours, planned vs actual (DEC-59, ADR-029)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

import openpyxl
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, func, select

from fw.core.db import async_session_factory
from fw.main import create_app
from fw.modules.attendance import AttendanceCalculation, AttendanceRecord, SiteVisit
from fw.modules.budget import BudgetService
from fw.modules.events import MobileEventLog
from fw.modules.jobs.models import JobItem, Worksite
from fw.modules.org.models import Group, RegisteredDevice, Zone
from fw.modules.payroll.models import (
    JobCostAllocation,
    PayrollRecord,
    PayrollRun,
    SalaryRevision,
    SalaryRevisionLine,
)
from fw.modules.scheduling import ScheduledWork
from fw.rules.grades import try_base_grade_code
from fw.rules.jobs import (
    MISSING_GRADE_RATE,
    GradeLine,
    ItemSchedule,
    contract_year_containing,
    grade_hourly_rate,
    grade_monthly_cost,
    month_ranges,
    plan_item,
    split_by_weights,
)
from fw.rules.payroll import (
    calculate_final_total_staff_cost,
    calculate_gratuity,
    calculate_hr_overhead,
    calculate_leave_salary,
    calculate_per_month_provision,
    calculate_salary_portion,
    calculate_total_staff_cost,
)
from tests.ids import unique_job_number
from tests.test_batch6_features import db_required, get_admin_user_and_token
from tests.test_dec57_scope import _person

DEMO = Path(__file__).resolve().parents[2] / "tools/demo_data/FieldWorkerTracker_Demo_Import.xlsx"
Y = date(2026, 1, 1)
Y_END = date(2026, 12, 31)


def _sched(
    unit: str = "WEEK",
    occ: str = "1",
    interval: int = 1,
    staff: int = 1,
    hours: str = "8",
    start: date | None = Y,
    end: date | None = None,
) -> ItemSchedule:
    return ItemSchedule(unit, Decimal(occ), interval, staff, Decimal(hours), start, end)


# --- The rule -----------------------------------------------------------------------------------


def test_weekly_monthly_full_contract_year() -> None:
    weekly = plan_item(_sched("WEEK", "2", staff=3, hours="4"), None, Y, Y_END, Y, None)
    assert weekly.activities_per_year == Decimal("104.000")
    assert weekly.hours == Decimal("1248.000")  # 104 x 3 x 4: a full contract year is exact
    monthly = plan_item(_sched("MONTH", "1"), Decimal("10"), Y, Y_END, Y, None)
    assert monthly.hours == Decimal("96.000") and monthly.cost == Decimal("960.00")


def test_fortnightly_counts_half_of_weekly() -> None:
    """The old budget ignored period_interval and counted fortnightly items twice."""
    weekly = plan_item(_sched("WEEK"), None, Y, Y_END, Y, None)
    fortnightly = plan_item(_sched("WEEK", interval=2), None, Y, Y_END, Y, None)
    assert fortnightly.activities_per_year == Decimal("26.000")
    assert fortnightly.hours * 2 == weekly.hours


def test_partial_year_item_and_contract_end() -> None:
    # Item starts 1 Jul: 184 of 365 days.
    half = plan_item(_sched(start=date(2026, 7, 1)), None, Y, Y_END, Y, None)
    assert half.active_days == 184
    assert half.hours == (Decimal("416") * Decimal(184) / Decimal(365)).quantize(Decimal("0.001"))
    # Worksite contract ends 31 Mar: 90 days.
    short = plan_item(_sched(), None, Y, Y_END, Y, date(2026, 3, 31))
    assert short.active_days == 90
    # Outside the period entirely.
    none = plan_item(_sched(start=date(2027, 2, 1)), Decimal("10"), Y, Y_END, Y, None)
    assert none.hours == 0 and none.cost == Decimal("0.00")


def test_leap_contract_year_and_monthly_split() -> None:
    start = date(2028, 1, 1)  # 366-day contract year
    full = plan_item(_sched(), None, start, date(2028, 12, 31), start, None)
    assert full.hours == Decimal("416.000")
    months = [
        plan_item(_sched(start=start), None, a, b, start, None).hours
        for a, b in month_ranges(start, date(2028, 12, 31))
    ]
    assert len(months) == 12 and abs(sum(months) - Decimal("416")) < Decimal("0.01")


def test_contract_year_from_start_date() -> None:
    assert contract_year_containing(date(2026, 11, 23), date(2024, 3, 15)) == (
        date(2026, 3, 15),
        date(2027, 3, 14),
    )
    assert contract_year_containing(date(2026, 2, 1), date(2024, 3, 15)) == (
        date(2025, 3, 15),
        date(2026, 3, 14),
    )
    assert contract_year_containing(date(2026, 5, 5), None) == (Y, Y_END)


def test_missing_grade_rate_gives_hours_but_no_cost() -> None:
    plan = plan_item(_sched(), None, Y, Y_END, Y, None)
    assert plan.cost is None and plan.warnings == [MISSING_GRADE_RATE]
    assert plan.hours == Decimal("416.000")


def test_grade_cost_matches_payroll_final_cost_when_provisions_equal() -> None:
    """With the settings provisions (842) on the line, plan and payroll cost a month the same."""
    line = GradeLine(
        basic_salary=Decimal("1500"),
        special_allowance=Decimal("300"),
        fixed_ot_amount=Decimal("200"),
        bonus=Decimal("50"),
        telephone_allowance=Decimal("25"),
        housing_transport_allowance=Decimal("100"),
        visa_provision=Decimal("132"),
        air_ticket_provision=Decimal("65"),
        uniform_provision=Decimal("30"),
        accommodation_provision=Decimal("550"),
        medical_provision=Decimal("65"),
    )
    oh = Decimal("0.05")
    # Payroll's actual cost for one person, no overtime and no shortfall:
    portion = calculate_salary_portion(
        basic=line.basic_salary,
        special_allowance=line.special_allowance,
        fixed_ot=line.fixed_ot_amount,
        bonus=line.bonus,
        telephone_allowance=line.telephone_allowance,
        housing_transport_allowance=line.housing_transport_allowance,
    )
    per_month = calculate_per_month_provision(
        Decimal("842"),
        calculate_gratuity(line.basic_salary),
        calculate_leave_salary(line.basic_salary),
    )
    staff = calculate_total_staff_cost(portion, per_month)
    payroll_final = calculate_final_total_staff_cost(staff, calculate_hr_overhead(staff, oh))
    assert grade_monthly_cost(line, oh).final_cost == payroll_final
    assert grade_hourly_rate(line, oh, Decimal("208")) == (payroll_final / Decimal("208")).quantize(
        Decimal("0.0001")
    )


def test_split_by_weights_keeps_the_total() -> None:
    shares = split_by_weights(Decimal("100.00"), {"a": Decimal("1"), "b": Decimal("2")})
    assert sum(shares.values()) == Decimal("100.00")
    assert shares["b"] == Decimal("66.67")


# --- Demo workbook: no missing grade rates, fortnightly counted once --------------------------


def _rows(wb: openpyxl.Workbook, sheet: str) -> list[dict[str, Any]]:
    rows = list(wb[sheet].iter_rows(values_only=True))
    head = rows[3]
    out = []
    for r in rows[4:]:
        if not r or r[0] == "#" or not any(r[1:]):
            continue
        out.append({str(h): v for h, v in zip(head, r, strict=False) if h})
    return out


def test_demo_workbook_every_job_item_grade_has_a_revision_rate() -> None:
    wb = openpyxl.load_workbook(DEMO, read_only=True)
    revs = [
        r for r in _rows(wb, "Salary_Revisions") if str(r.get("status") or "ACTIVE") == "ACTIVE"
    ]
    settings = {str(r["setting_key"]): r["value"] for r in _rows(wb, "Company_Settings")}
    default_code = settings.get("default_salary_revision_code")
    rev_codes = {str(r["revision_code"]) for r in revs}
    code = (
        str(default_code)
        if default_code in rev_codes
        else str(max(revs, key=lambda r: str(r["effective_from"]))["revision_code"])
    )
    grades = {
        try_base_grade_code(str(r["grade_code"]))
        for r in _rows(wb, "Salary_Revision_Lines")
        if str(r["revision_code"]) == code
    }
    items = _rows(wb, "Job_Items")
    missing = sorted(
        {
            f"{r['job_number']}/{r['sub_item_code']}:{r['planned_grade_code']}"
            for r in items
            if try_base_grade_code(str(r["planned_grade_code"])) not in grades
        }
    )
    assert missing == [], f"MISSING_GRADE_RATE in demo data: {missing}"
    fortnightly = [r for r in items if r.get("period_interval") == 2]
    assert len(fortnightly) == 1
    f = fortnightly[0]
    plan = plan_item(
        _sched(
            str(f["frequency_unit"]),
            str(f["occurrences_per_period"]),
            2,
            int(f["required_staff_count"]),
            str(f["hours_per_occurrence_per_staff"]),
        ),  # type: ignore[arg-type]
        None,
        Y,
        Y_END,
        Y,
        None,
    )
    weekly_equiv = plan_item(
        _sched(
            str(f["frequency_unit"]),
            str(f["occurrences_per_period"]),
            1,
            int(f["required_staff_count"]),
            str(f["hours_per_occurrence_per_staff"]),
        ),  # type: ignore[arg-type]
        None,
        Y,
        Y_END,
        Y,
        None,
    )
    assert plan.hours * 2 == weekly_equiv.hours


# --- Database fixtures --------------------------------------------------------------------------


async def _worksite(
    session,
    *,
    start: date,
    country: str = "SA",
    revision: str | None = None,
    provisions_equal: bool = True,
) -> tuple[Worksite, SalaryRevision]:
    grp = Group(name=f"G {uuid4().hex[:6]}", code=f"G{uuid4().hex[:6]}")
    zn = Zone(name=f"Z {uuid4().hex[:6]}", code=f"Z{uuid4().hex[:6]}")
    session.add_all([grp, zn])
    await session.flush()
    prov = (
        dict(
            visa_provision=Decimal("132"),
            air_ticket_provision=Decimal("65"),
            uniform_provision=Decimal("30"),
            accommodation_provision=Decimal("550"),
            medical_provision=Decimal("65"),
        )
        if provisions_equal
        else dict(
            visa_provision=Decimal("200"),
            air_ticket_provision=Decimal("75"),
            uniform_provision=Decimal("30"),
            accommodation_provision=Decimal("850"),
            medical_provision=Decimal("65"),
            transportation_provision=Decimal("500"),
        )
    )
    rev = SalaryRevision(
        code=revision or f"B54{uuid4().hex[:6].upper()}",
        name="5.4 test",
        country=country,
        effective_from=start,
        status="ACTIVE",
        suffix_label=str(start.year),
    )
    rev.lines.append(SalaryRevisionLine(grade_code="G1A", basic_salary=Decimal("1500.00"), **prov))
    session.add(rev)
    ws = Worksite(
        job_number=unique_job_number("26A"),
        job_name=f"Budget 5.4 {uuid4().hex[:4]}",
        group_id=grp.id,
        zone_id=zn.id,
        country=country,
        is_active=True,
        start_date=start,
        salary_revision_code=rev.code,
    )
    session.add(ws)
    await session.flush()
    return ws, rev


def _item(
    ws: Worksite, code: str, hours: str, sgd: str = "Helper", grade: str = "G1A", interval: int = 1
) -> JobItem:
    return JobItem(
        worksite_id=ws.id,
        sub_item_code=code,
        staff_grade_description=sgd,
        planned_grade_code=grade,
        frequency_unit="WEEK",
        occurrences_per_period=Decimal("1.0"),
        period_interval=interval,
        required_staff_count=1,
        hours_per_occurrence_per_staff=Decimal(hours),
        start_date=ws.start_date,
        deployment_type="PERMANENT",
        is_active=True,
    )


async def _attended(
    session, emp_id, device_id, ws_id, day: date, minutes: int, *, approved: bool
) -> None:
    ev = MobileEventLog(
        event_id=uuid4(),
        employee_id=emp_id,
        device_id=device_id,
        event_type="SITE_ENTRY",
        event_timestamp_utc=datetime(day.year, day.month, day.day, 5, tzinfo=UTC),
    )
    session.add(ev)
    await session.flush()
    rec = AttendanceRecord(
        employee_id=emp_id,
        work_date=day,
        review_status="AUTO" if approved else "PENDING_REVIEW",
    )
    session.add(rec)
    await session.flush()
    calc = AttendanceCalculation(
        attendance_record_id=rec.id,
        version_no=1,
        input_hash=uuid4().hex,
        review_reasons=[] if approved else ["LATE_ARRIVAL"],
    )
    session.add(calc)
    await session.flush()
    rec.current_calculation_id = calc.id
    t0 = datetime(day.year, day.month, day.day, 5, tzinfo=UTC)
    session.add(
        SiteVisit(
            employee_id=emp_id,
            work_date=day,
            place_type="SITE",
            worksite_id=ws_id,
            entry_event_id=ev.event_id,
            entry_at=t0,
            last_inside_at=t0,
            counts_as_completed=True,
            duration_minutes=minutes,
        )
    )


def _work(emp_id, item: JobItem, day: date, hours: str, seq: int = 1) -> ScheduledWork:
    return ScheduledWork(
        employee_id=emp_id,
        work_date=day,
        job_item_id=item.id,
        worksite_id=item.worksite_id,
        assigned_hours=Decimal(hours),
        status="ACTIVE",
        source="STANDING",
        sequence=seq,
    )


MARCH = (date(2026, 3, 1), date(2026, 3, 31))


@db_required
@pytest.mark.asyncio
async def test_planned_vs_actual_hours_and_cost() -> None:
    async with async_session_factory() as session:
        ws, _rev = await _worksite(session, start=Y)
        a = _item(ws, "A", "8")
        b = _item(ws, "B", "4")
        c = _item(ws, "C", "8", sgd="Project Manager")  # budget-only staff type
        session.add_all([a, b, c])
        emp, _ = await _person(session, "WORKER", "Pva")
        emp.country = "SA"
        dev = RegisteredDevice(
            employee_id=emp.id,
            device_identifier=f"d{uuid4().hex[:8]}",
            platform="ANDROID",
            is_active=True,
        )
        session.add(dev)
        await session.flush()
        session.add_all(
            [
                _work(emp.id, a, date(2026, 3, 2), "8"),
                _work(emp.id, b, date(2026, 3, 2), "4", seq=2),
                _work(emp.id, a, date(2026, 3, 3), "8"),
            ]
        )
        # 10 h approved on 2 Mar (split 2:1 over A and B); 3 Mar pending review (left out);
        # 2 h approved on 4 Mar with nothing scheduled (unplanned).
        await _attended(session, emp.id, dev.id, ws.id, date(2026, 3, 2), 600, approved=True)
        await _attended(session, emp.id, dev.id, ws.id, date(2026, 3, 3), 480, approved=False)
        await _attended(session, emp.id, dev.id, ws.id, date(2026, 3, 4), 120, approved=True)
        run = PayrollRun(
            period_start=MARCH[0],
            period_end=MARCH[1],
            country="SA",
            status="APPROVED",
            run_no=1,
            calculation_version="v1.0",
        )
        session.add(run)
        await session.flush()
        rec = PayrollRecord(payroll_run_id=run.id, employee_id=emp.id)
        session.add(rec)
        await session.flush()
        session.add(
            JobCostAllocation(
                payroll_record_id=rec.id,
                worksite_id=ws.id,
                worked_minutes=720,
                allocated_amount=Decimal("1000.00"),
            )
        )
        # An allocation in April is outside the range.
        run2 = PayrollRun(
            period_start=date(2026, 4, 1),
            period_end=date(2026, 4, 30),
            country="SA",
            status="APPROVED",
            run_no=1,
            calculation_version="v1.0",
        )
        session.add(run2)
        await session.flush()
        rec2 = PayrollRecord(payroll_run_id=run2.id, employee_id=emp.id)
        session.add(rec2)
        await session.flush()
        session.add(
            JobCostAllocation(
                payroll_record_id=rec2.id,
                worksite_id=ws.id,
                worked_minutes=60,
                allocated_amount=Decimal("999.00"),
            )
        )
        await session.commit()
        ws_id, a_id, b_id, c_id = ws.id, a.id, b.id, c.id

    async with async_session_factory() as session:
        [row] = await BudgetService.planned_vs_actual(
            session, is_admin=True, worksite_ids=[ws_id], date_from=MARCH[0], date_to=MARCH[1]
        )
    items = {i.job_item_id: i for i in row.items}
    planned_a = (Decimal("416") * Decimal(31) / Decimal(365)).quantize(Decimal("0.001"))
    assert items[a_id].planned_hours == planned_a
    assert items[a_id].actual_hours == Decimal("6.667")
    assert items[b_id].actual_hours == Decimal("3.333")
    assert row.unplanned_hours == Decimal("2.000")
    # Budget-only: actual = planned (hours and cost).
    assert items[c_id].is_budget_only
    assert items[c_id].actual_hours == items[c_id].planned_hours
    assert items[c_id].actual_cost == items[c_id].planned_cost
    # March allocation split 2:1 by approved hours; April's is outside the range.
    assert items[a_id].actual_cost == Decimal("666.67")
    assert items[b_id].actual_cost == Decimal("333.33")
    c_cost = items[c_id].planned_cost
    assert c_cost is not None and row.actual_cost is not None and row.planned_cost is not None
    assert row.actual_cost == Decimal("1000.00") + c_cost
    assert (
        row.actual_hours
        == Decimal("6.667") + Decimal("3.333") + Decimal("2.000") + items[c_id].planned_hours
    )
    assert row.hours_diff == row.actual_hours - row.planned_hours
    assert row.cost_diff == row.actual_cost - row.planned_cost
    assert len(row.months) == 1 and row.months[0].actual_hours == row.actual_hours
    assert not [w for w in row.warnings if w.code == "PROVISIONS_DIFFER_FROM_PAYROLL"]
    # Legacy fields follow the period: prorated_budget is the planned cost for the range.
    assert row.prorated_budget == row.planned_cost and row.variance == row.cost_diff

    # Other roles: hours only.
    async with async_session_factory() as session:
        [masked] = await BudgetService.planned_vs_actual(
            session, is_admin=False, worksite_ids=[ws_id], date_from=MARCH[0], date_to=MARCH[1]
        )
    assert masked.planned_cost is None and masked.actual_cost is None
    assert masked.prorated_budget is None and masked.annual_labor_budget is None
    assert all(i.planned_cost is None and i.hourly_rate is None for i in masked.items)
    assert masked.actual_hours == row.actual_hours


@db_required
@pytest.mark.asyncio
async def test_provision_difference_note() -> None:
    async with async_session_factory() as session:
        ws, rev = await _worksite(session, start=Y, provisions_equal=False)
        session.add(_item(ws, "A", "8"))
        await session.commit()
        ws_id = ws.id
    async with async_session_factory() as session:
        [row] = await BudgetService.planned_vs_actual(session, is_admin=True, worksite_ids=[ws_id])
    notes = [w for w in row.warnings if w.code == "PROVISIONS_DIFFER_FROM_PAYROLL"]
    assert len(notes) == 1
    assert notes[0].plan_provisions == Decimal("1720.00")
    assert notes[0].payroll_provisions == Decimal("842.00")
    assert "1720.00" in notes[0].message and "842.00" in notes[0].message


@db_required
@pytest.mark.asyncio
async def test_query_count_does_not_grow_with_worksites() -> None:
    ids = []
    async with async_session_factory() as session:
        for _ in range(5):
            ws, _r = await _worksite(session, start=Y)
            session.add(_item(ws, "A", "8"))
            ids.append(ws.id)
        await session.commit()

    async def count(worksite_ids) -> int:
        n = 0
        async with async_session_factory() as session:
            engine = session.bind.sync_engine  # type: ignore[union-attr]

            def _cnt(*_a, **_k) -> None:
                nonlocal n
                n += 1

            event.listen(engine, "before_cursor_execute", _cnt)
            try:
                await BudgetService.planned_vs_actual(
                    session,
                    is_admin=True,
                    worksite_ids=worksite_ids,
                    date_from=MARCH[0],
                    date_to=MARCH[1],
                )
            finally:
                event.remove(engine, "before_cursor_execute", _cnt)
        return n

    assert await count(ids[:1]) == await count(ids)


@db_required
@pytest.mark.asyncio
async def test_job_item_budget_on_detail_preview_and_roles() -> None:
    async with async_session_factory() as session:
        ws, _r = await _worksite(session, start=Y, country="AE")
        session.add(_item(ws, "A", "8"))
        _, eng_token = await _person(session, "ENGINEER", "Eng54")
        _, sup_token = await _person(session, "SUPERVISOR", "Sup54")
        _, admin_token = await get_admin_user_and_token(session)
        await session.commit()
        ws_id = ws.id
        before = (await session.execute(select(func.count()).select_from(JobItem))).scalar_one()
    admin = {"Authorization": f"Bearer {admin_token}"}
    body = {
        "sub_item_code": "Z",
        "staff_grade_description": "Gardener Helper",
        "planned_grade_code": "G1A",
        "frequency_unit": "WEEK",
        "occurrences_per_period": "2",
        "period_interval": 2,
        "required_staff_count": 2,
        "hours_per_occurrence_per_staff": "4",
        "start_date": str(Y),
        "deployment_type": "PERMANENT",
    }
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        d = (await c.get(f"/api/v1/worksites/{ws_id}", headers=admin)).json()
        assert d["items"][0]["budget"]["annual_hours"] is not None
        assert d["items"][0]["budget"]["annual_cost"] is not None
        assert d["budget_totals"]["total_cost"] is not None

        r = await c.post(
            f"/api/v1/worksites/{ws_id}/job-items/budget-preview", headers=admin, json=body
        )
        assert r.status_code == 200, r.text
        p = r.json()
        # 2 per fortnight = 52 a year x 2 staff x 4 h
        assert Decimal(p["activities_per_year"]) == Decimal("52")
        assert Decimal(p["full_year_hours"]) == Decimal("416")
        assert p["hourly_rate"] is not None and p["annual_cost"] is not None

        r = await c.post(
            "/api/v1/job-items/budget-preview",
            headers={"Authorization": f"Bearer {eng_token}"},
            json={"country": "AE", "contract_start": str(Y), "item": body},
        )
        assert r.status_code == 200, r.text
        e = r.json()
        assert Decimal(e["annual_hours"]) > 0
        assert e["hourly_rate"] is None and e["annual_cost"] is None
        assert all(w["code"] == "MISSING_GRADE_RATE" for w in e["warnings"])

        r = await c.post(
            "/api/v1/job-items/budget-preview",
            headers={"Authorization": f"Bearer {sup_token}"},
            json={"country": "AE", "item": body},
        )
        assert r.status_code == 403

        r = await c.get(
            "/api/v1/payroll/budget-vs-actual", headers={"Authorization": f"Bearer {eng_token}"}
        )
        assert r.status_code == 403
    async with async_session_factory() as session:
        after = (await session.execute(select(func.count()).select_from(JobItem))).scalar_one()
    assert after == before  # preview saves nothing


@db_required
@pytest.mark.asyncio
async def test_missing_rate_setting_is_422_for_admin_money() -> None:
    async with async_session_factory() as session:
        ws, _r = await _worksite(session, start=date(2019, 1, 1))  # before any seeded setting
        session.add(_item(ws, "A", "8"))
        await session.commit()
        ws_id = ws.id
    async with async_session_factory() as session:
        from fw.core.errors import AppError

        with pytest.raises(AppError) as exc:
            await BudgetService.planned_vs_actual(
                session,
                is_admin=True,
                worksite_ids=[ws_id],
                date_from=date(2019, 1, 1),
                date_to=date(2019, 1, 31),
            )
        assert exc.value.code == "SETTING_MISSING"
        # Hours still work for other roles.
        [row] = await BudgetService.planned_vs_actual(
            session,
            is_admin=False,
            worksite_ids=[ws_id],
            date_from=date(2019, 1, 1),
            date_to=date(2019, 1, 31),
        )
        assert row.planned_hours > 0
