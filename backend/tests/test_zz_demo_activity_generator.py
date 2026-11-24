"""Demo activity generator (``tools/seed_demo_activity.py``): a 3-day run on the test database.

The file name starts with ``test_zz_`` so it runs last: it resets the test database and commits
the demo workbook, which replaces the settings, time rules and holidays other tests rely on.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date, time
from pathlib import Path
from types import ModuleType
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from fw.core.clock import get_system_clock
from fw.core.db import async_session_factory
from tests.test_batch6_features import db_required

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "tools" / "seed_demo_activity.py"
WORKBOOK = REPO / "tools" / "demo_data" / "FieldWorkerTracker_Demo_Import.xlsx"
DUBAI = ZoneInfo("Asia/Dubai")


def _load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("seed_demo_activity", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses look their module up while being created
    spec.loader.exec_module(module)
    return module


async def _reset_and_import_demo() -> None:
    from fw.api.settings import reset_to_bootstrap_state
    from fw.modules.identity import User
    from fw.modules.imports.service import ImportService

    async with async_session_factory() as session:
        await reset_to_bootstrap_state(session)
        await session.commit()
    async with async_session_factory() as session:
        admin = (
            await session.execute(select(User).where(User.username == "ADMIN001"))
        ).scalar_one()
        preview = await ImportService.parse_and_preview(
            session, WORKBOOK.read_bytes(), WORKBOOK.name, admin.id
        )
        await session.commit()
        assert preview.can_commit, preview.summary
        await ImportService.commit_batch(session, preview.batch_id, admin.id, "ADMIN")
        await session.commit()


@db_required
@pytest.mark.skipif(not WORKBOOK.is_file(), reason="demo workbook not present")
async def test_three_day_run_goes_through_the_pipeline() -> None:
    from fw.modules.attendance import AttendanceCalculation, AttendanceRecord, PendingVisit
    from fw.modules.events import MobileEventLog
    from fw.modules.reports.handlers.late_early_departure import fetch_late_early_departure
    from fw.modules.reports.schemas import ReportFilterParams

    tool = _load_tool()
    await _reset_and_import_demo()
    clock_before = get_system_clock()

    # Mon 5 - Wed 7 Oct 2026: D is Wednesday, so P1 (latest Mon/Wed/Fri) is 7 Oct; P7 (D-4)
    # falls before --from and moves to the first working day in range.
    opts = tool.Options(
        date_from=date(2026, 10, 5),
        date_to=date(2026, 10, 7),
        plan_ahead_days=0,
        payroll=False,
        quiet=True,
    )
    summary = await tool.run(opts)

    assert get_system_clock() is clock_before, "the generator must put the app clock back"
    assert summary.events.get("ACCEPTED", 0) > 0
    assert sum(summary.refused.values()) == 0, summary.refused
    assert summary.shifts_created > 0 and summary.devices_registered == 24

    async with async_session_factory() as session:
        records = (
            await session.execute(
                select(func.count())
                .select_from(AttendanceRecord)
                .where(AttendanceRecord.work_date.between(opts.date_from, opts.date_to))
            )
        ).scalar_one()
        events = (await session.execute(select(func.count()).select_from(MobileEventLog))).scalar()
        assert records > 0 and (events or 0) > 0

        scenarios = {s.code: s for s in summary.scenarios}
        p1, p7 = scenarios["P1"], scenarios["P7"]
        assert p1.day == date(2026, 10, 7)
        assert p7.day == date(2026, 10, 5) and "moved" in p7.note

        rec, calc = (
            await session.execute(
                select(AttendanceRecord, AttendanceCalculation)
                .join(
                    AttendanceCalculation,
                    AttendanceRecord.current_calculation_id == AttendanceCalculation.id,
                )
                .where(AttendanceRecord.id == p1.attendance_id)
            )
        ).one()
        assert rec.review_status == "PENDING_REVIEW"
        assert "SHORTFALL_BEYOND_GRACE" in (calc.flags or [])
        # 45 minutes late at the first site: planned 07:00, first entry 07:45 site time.
        assert calc.first_site_entry_at is not None
        first_entry = calc.first_site_entry_at.astimezone(DUBAI).time()
        assert time(7, 44) <= first_entry <= time(7, 46), first_entry

        absent = (
            await session.execute(
                select(AttendanceRecord).where(AttendanceRecord.id == p7.attendance_id)
            )
        ).scalar_one()
        assert absent.business_status == "ABSENT"

        # P9: the day closed before its events arrived (pending visits OPEN); the late upload
        # recalculates the day (version 2) and closes them as VISIT_CONFIRMED_LATE (DEC-32).
        p9 = scenarios["P9"]
        p9_rec, p9_calc = (
            await session.execute(
                select(AttendanceRecord, AttendanceCalculation)
                .join(
                    AttendanceCalculation,
                    AttendanceRecord.current_calculation_id == AttendanceCalculation.id,
                )
                .where(AttendanceRecord.id == p9.attendance_id)
            )
        ).one()
        assert p9_calc.version_no == 2
        p9_pending = (
            (
                await session.execute(
                    select(PendingVisit).where(
                        PendingVisit.employee_id == p9_rec.employee_id,
                        PendingVisit.due_date == p9.day,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert p9_pending, "the day close before the upload should have opened pending visits"
        assert {(pv.status, pv.closed_reason) for pv in p9_pending} == {
            ("CLOSED", "VISIT_CONFIRMED_LATE")
        }

        # The late arrival report compares site times (it used to compare the UTC clock time
        # with the planned site time: never late, and about four hours "early" every day).
        report = await fetch_late_early_departure(
            session,
            ReportFilterParams(date_from=p1.day, date_to=p1.day, employee_id=rec.employee_id),
            scope=None,
        )
        assert len(report) == 1
        assert report[0]["late_arrival_minutes"] == 45
        assert report[0]["early_dep_minutes"] == 0
