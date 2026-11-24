"""Demo activity generator: fills the demo import with realistic activity (MOCK people only).

After a clean reset (``tools/reset_database.py``) and a committed import of
``tools/demo_data/FieldWorkerTracker_Demo_Import.xlsx``, this plays the days from ``--from`` to
``--to`` (default: yesterday, site time) through the real pipeline, so the live map, attendance,
pending visits, payroll and the reports have content:

1. Plan: Base Planner templates from ``demo_assignments.json`` (``save_base_template``), then one
   Operational Planner shift per planned worker-day (``create_operational_shift``) from ``--from``
   to ``--to`` + 30 days, public holidays skipped as the planner does. Every shift is first checked
   with the scheduler's own validation; any error stops the run.
2. Devices and consent: each worker (driver included) logs in once through the mobile login
   service with a ``DEMO-<tally>`` device and accepts the current consent version.
3. Events: a day per worker (camp, transit, ENTRY/EXIT per site in plan order, pings every
   8-12 minutes, the break on site, camp again), submitted through the same service as
   ``POST /mobile/events/batch`` with the app clock frozen at that day's evening.
4. Day close: ``AttendanceService.recalculate_day`` for every planned worker, then pending-visit
   detection and reminders, as the worker process does.
5. Reviews: engineer 2901 approves every PENDING_REVIEW day older than 7 days (DEC-10 checked).
6. Payroll: the October 2026 draft (``treat_leaves_as_paid=false``), not approved.

It never writes attendance, site visit, pending visit or payroll rows itself.

Usage (from the repo root)::

    uv run --directory backend python ../tools/seed_demo_activity.py
        [--from 2026-10-01] [--to YYYY-MM-DD] [--seed 42] [--dry-run] [--reset-generated]

Refused when ``APP_ENV`` is production or the database is not on this machine.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]
BACKEND_SRC = REPO / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from geoalchemy2.shape import to_shape  # noqa: E402
from shapely.geometry import LineString, Point  # noqa: E402
from shapely.geometry.base import BaseGeometry  # noqa: E402
from sqlalchemy import delete, false, or_, select, text, update  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from fw.core.clock import FrozenClock, get_system_clock, set_system_clock  # noqa: E402
from fw.core.config import get_settings  # noqa: E402
from fw.core.errors import AppError  # noqa: E402

DEMO_DIR = REPO / "tools" / "demo_data"
ASSIGNMENTS_FILE = DEMO_DIR / "demo_assignments.json"
DEMO_WORKBOOK = DEMO_DIR / "FieldWorkerTracker_Demo_Import.xlsx"

SITE_TZ = ZoneInfo("Asia/Dubai")
COUNTRY = "AE"
WEEKDAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
ID_NAMESPACE = UUID("8d6f1c52-3b7e-4f0a-9c1d-5e2a7b9c0d11")  # deterministic event and batch ids

DEVICE_PREFIX = "DEMO-"
SHIFT_REASON = "Demo plan (generated)"
REASSIGN_REASON = "Demo: works his weekly off at Le Pont (generated)"
REVIEW_COMMENT = "Reviewed (demo data)"
PAYROLL_NOTES = "Demo payroll draft (generated)"
ENGINEER_TALLY = "2901"
PLAN_AHEAD_DAYS = 30
REVIEW_AFTER_DAYS = 7
MAX_BATCH = 200
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

# Planted scenarios (see demo-data-generator-prompt.md). D is the last generated day.
P1_TALLY, P2_TALLY, P3_TALLY, P4_TALLY = "2001", "2007", "2012", "2013"
P5_TALLY, P6_TALLY, P7_TALLY, P8_TALLY = "2010", "2019", "2011", "2008"
P9_TALLY, P11_TALLY, P12_TALLY = "2020", "2024", "2008"
P5_SUPERVISOR_TALLY = "2702"
P5_TARGET = ("22A11702", "A")  # Le Pont
P6_SKIPPED_JOB = "22A14107"
TABLES = (
    "base_roster_templates",
    "base_roster_entries",
    "scheduled_work",
    "reassignment_requests",
    "users",
    "registered_devices",
    "consent_records",
    "mobile_event_logs",
    "site_visits",
    "tracking_gaps",
    "attendance_records",
    "attendance_calculations",
    "attendance_approvals",
    "pending_visits",
    "alerts",
    "payroll_runs",
    "payroll_records",
)


# --------------------------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Assignment:
    tally_id: str
    job_number: str
    sub_item_code: str
    weekdays: tuple[str, ...]
    deployment_type: str


def load_assignments(path: Path = ASSIGNMENTS_FILE) -> list[Assignment]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        Assignment(
            tally_id=str(a["tally_id"]),
            job_number=str(a["job_number"]),
            sub_item_code=str(a["sub_item_code"]),
            weekdays=tuple(str(w).upper()[:3] for w in a["weekdays"]),
            deployment_type=str(a.get("deployment_type") or "PERMANENT"),
        )
        for a in raw["assignments"]
    ]


def items_for_day(assignments: list[Assignment], tally: str, dow: str) -> list[Assignment]:
    """The worker's items on that weekday, in visit order (the order of the file)."""
    return [a for a in assignments if a.tally_id == tally and dow in a.weekdays]


@dataclass
class Options:
    date_from: date
    date_to: date
    seed: int = 42
    dry_run: bool = False
    reset_generated: bool = False
    plan_ahead_days: int = PLAN_AHEAD_DAYS
    payroll: bool = True
    quiet: bool = False


@dataclass
class Scenario:
    code: str
    tally: str
    day: date
    what: str
    note: str = ""
    attendance_id: UUID | None = None
    outcome: str = ""


@dataclass
class Summary:
    rows_before: dict[str, int] = field(default_factory=dict)
    rows_after: dict[str, int] = field(default_factory=dict)
    removed: dict[str, int] = field(default_factory=dict)
    leaves_imported: int = 0
    templates_saved: int = 0
    shifts_created: int = 0
    shifts_existing: int = 0
    devices_registered: int = 0
    consents_recorded: int = 0
    events: Counter[str] = field(default_factory=Counter)
    refused: Counter[str] = field(default_factory=Counter)
    worker_days: int = 0
    day_close_calculations: int = 0
    pending_visits_detected: int = 0
    reviews_approved: int = 0
    reviews_refused: int = 0
    payroll_run_id: UUID | None = None
    scenarios: list[Scenario] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class GeneratorError(RuntimeError):
    """A refusal the generator reports and stops on (never bypassed)."""


def app_error_text(exc: AppError) -> str:
    return f"{getattr(exc, 'code', '')} {getattr(exc, 'detail', '') or exc}".strip()


# --------------------------------------------------------------------------------------------
# Guards
# --------------------------------------------------------------------------------------------


def target_problems() -> list[str]:
    """Why this database is refused (empty when it is fine)."""
    settings = get_settings()
    out: list[str] = []
    if (settings.APP_ENV or "").lower() == "production":
        out.append("APP_ENV is production")
    host = make_url(settings.DATABASE_URL).host or "localhost"
    if host not in LOCAL_HOSTS:
        out.append(f"the database is on {host!r}; only a database on this machine is allowed")
    return out


def database_label() -> str:
    url = make_url(get_settings().DATABASE_URL)
    return f"{url.host or 'localhost'}:{url.port or 5432}/{url.database}"


# --------------------------------------------------------------------------------------------
# Context loaded from the import
# --------------------------------------------------------------------------------------------


@dataclass
class Context:
    admin: Any
    engineer: Any
    p5_requester: Any
    employees: dict[str, Any]  # tally -> Employee
    by_id: dict[UUID, Any]
    items: dict[tuple[str, str], Any]  # (job_number, sub_item_code) -> JobItem
    worksites: dict[UUID, Any]
    site_polys: dict[UUID, BaseGeometry]
    camp_polys: dict[UUID, BaseGeometry]
    holidays: set[date]
    leave_days: dict[UUID, set[date]]
    workers: list[str]  # tallies with assignments, sorted

    def emp(self, tally: str) -> Any:
        return self.employees[tally]


async def load_context(
    session: AsyncSession, assignments: list[Assignment], start: date, end: date
) -> Context:
    from fw.modules.identity import User
    from fw.modules.jobs import JobItem, Worksite
    from fw.modules.org import Accommodation, Employee
    from fw.modules.scheduling import LeaveRequest, SchedulingService

    workers = sorted({a.tally_id for a in assignments})
    tallies = set(workers) | {ENGINEER_TALLY, P5_SUPERVISOR_TALLY}
    emps = (
        (await session.execute(select(Employee).where(Employee.tally_id.in_(tallies))))
        .scalars()
        .all()
    )
    employees = {e.tally_id: e for e in emps}
    missing = sorted(tallies - set(employees))
    if missing:
        raise GeneratorError(
            "The demo import is not in this database (missing employees "
            + ", ".join(missing)
            + "). Reset, then import tools/demo_data/FieldWorkerTracker_Demo_Import.xlsx first."
        )

    job_numbers = {a.job_number for a in assignments} | {P5_TARGET[0]}
    rows = (
        await session.execute(
            select(JobItem, Worksite)
            .join(Worksite, JobItem.worksite_id == Worksite.id)
            .where(Worksite.job_number.in_(job_numbers))
        )
    ).all()
    items = {(ws.job_number, it.sub_item_code): it for it, ws in rows}
    worksites = {ws.id: ws for _, ws in rows}
    wanted = {(a.job_number, a.sub_item_code) for a in assignments} | {P5_TARGET}
    missing_items = sorted(f"{j}{s}" for j, s in wanted - set(items))
    if missing_items:
        raise GeneratorError(
            "The demo import is incomplete (missing job items "
            + ", ".join(missing_items)
            + "). Import the demo workbook first."
        )
    site_polys = {
        ws.id: to_shape(cast(Any, ws.boundary))
        for ws in worksites.values()
        if ws.boundary is not None
    }
    no_boundary = sorted(ws.job_number for ws in worksites.values() if ws.id not in site_polys)
    if no_boundary:
        raise GeneratorError("Worksites without a boundary: " + ", ".join(no_boundary))

    accs = (await session.execute(select(Accommodation))).scalars().all()
    camp_polys = {a.id: to_shape(cast(Any, a.boundary)) for a in accs if a.boundary is not None}
    for tally in workers:
        acc_id = employees[tally].accommodation_id
        if acc_id is None or acc_id not in camp_polys:
            raise GeneratorError(f"Worker {tally} has no accommodation with a boundary")

    async def user_for(tally: str) -> Any:
        user = (
            await session.execute(select(User).where(User.username == tally))
        ).scalar_one_or_none()
        if user is None:
            raise GeneratorError(f"No user account for {tally}; the import provisions one")
        return user

    admin = await find_admin(session)

    holidays = set(await SchedulingService(session).get_public_holidays(COUNTRY, start, end))
    worker_ids = [employees[t].id for t in workers]
    leaves = (
        (
            await session.execute(
                select(LeaveRequest).where(
                    LeaveRequest.employee_id.in_(worker_ids),
                    LeaveRequest.status == "APPROVED",
                    LeaveRequest.to_date >= start,
                    LeaveRequest.from_date <= end,
                )
            )
        )
        .scalars()
        .all()
    )
    leave_days: dict[UUID, set[date]] = defaultdict(set)
    for lr in leaves:
        d = lr.from_date
        while d <= lr.to_date:
            leave_days[lr.employee_id].add(d)
            d += timedelta(days=1)

    return Context(
        admin=admin,
        engineer=await user_for(ENGINEER_TALLY),
        p5_requester=await user_for(P5_SUPERVISOR_TALLY),
        employees=employees,
        by_id={e.id: e for e in emps},
        items=items,
        worksites=worksites,
        site_polys=site_polys,
        camp_polys=camp_polys,
        holidays=holidays,
        leave_days=dict(leave_days),
        workers=workers,
    )


# --------------------------------------------------------------------------------------------
# Scenario dates
# --------------------------------------------------------------------------------------------


async def find_admin(session: AsyncSession) -> Any:
    from fw.modules.identity import User

    admin = (
        await session.execute(select(User).where(User.username == "ADMIN001"))
    ).scalar_one_or_none()
    if admin is None:
        admin = (
            (
                await session.execute(
                    select(User)
                    .where(User.role == "ADMIN", User.is_active.is_(True))
                    .order_by(User.created_at)
                )
            )
            .scalars()
            .first()
        )
    if admin is None:
        raise GeneratorError("No active Admin user (reset_database.py creates ADMIN001)")
    return admin


def demo_leave_rows(path: Path = DEMO_WORKBOOK) -> list[tuple[str, str, date, date, str]]:
    """The Leave sheet of the demo workbook: (tally_id, leave_type, from, to, reason)."""
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(wb["Leave"].iter_rows(values_only=True))
    header_at = next(i for i, r in enumerate(rows) if r and r[0] == "#")
    header = [str(c or "") for c in rows[header_at]]
    col = {name: header.index(name) for name in ("tally_id", "leave_type", "from_date", "to_date")}
    out: list[tuple[str, str, date, date, str]] = []
    for r in rows[header_at + 1 :]:
        if not r or r[col["tally_id"]] is None:
            continue

        def as_date(v: Any) -> date:
            return v.date() if isinstance(v, datetime) else date.fromisoformat(str(v)[:10])

        reason = r[header.index("reason")] if "reason" in header else None
        out.append(
            (
                str(r[col["tally_id"]]).strip(),
                str(r[col["leave_type"]]).strip().upper(),
                as_date(r[col["from_date"]]),
                as_date(r[col["to_date"]]),
                str(reason or "Imported leave"),
            )
        )
    return out


async def ensure_demo_leave(session: AsyncSession, admin: Any, summary: Summary) -> None:
    """The master import does not read the Leave sheet yet (OUT_OF_SCOPE_PHASE_03), so the
    demo's leave rows go through the Admin leave import (``POST /leave-requests/import``),
    unless they are already there."""
    import io

    import openpyxl

    from fw.modules.org import Employee
    from fw.modules.scheduling import LeaveRequest, SchedulingService

    missing: list[tuple[str, str, date, date, str]] = []
    for tally, leave_type, d_from, d_to, reason in demo_leave_rows():
        found = (
            await session.execute(
                select(LeaveRequest.id)
                .join(Employee, Employee.id == LeaveRequest.employee_id)
                .where(
                    Employee.tally_id == tally,
                    LeaveRequest.leave_type == leave_type,
                    LeaveRequest.from_date == d_from,
                    LeaveRequest.to_date == d_to,
                    LeaveRequest.status == "APPROVED",
                )
            )
        ).first()
        if found is None:
            missing.append((tally, leave_type, d_from, d_to, reason))
    if not missing:
        return
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["tally_id", "leave_type", "from_date", "to_date", "reason"])
    for tally, leave_type, d_from, d_to, reason in missing:
        ws.append([tally, leave_type, d_from.isoformat(), d_to.isoformat(), reason])
    buf = io.BytesIO()
    wb.save(buf)
    result = await SchedulingService(session).import_leaves_from_excel(
        buf.getvalue(), current_user=admin
    )
    if result.get("errors"):
        raise GeneratorError("Leave import refused rows: " + "; ".join(result["errors"]))
    summary.leaves_imported += int(result.get("created", 0))


def dow(d: date) -> str:
    return WEEKDAYS[d.weekday()]


def is_off(employee: Any, d: date) -> bool:
    return (employee.weekly_off_day or "").strip().upper()[:3] == dow(d)


def plans_to_work(
    ctx: Context, assignments: list[Assignment], tally: str, d: date, *, ignore_leave: bool = False
) -> bool:
    emp = ctx.emp(tally)
    if d in ctx.holidays or is_off(emp, d):
        return False
    if not ignore_leave and d in ctx.leave_days.get(emp.id, set()):
        return False
    return bool(items_for_day(assignments, tally, dow(d)))


def place(
    ctx: Context,
    assignments: list[Assignment],
    tally: str,
    wanted: date,
    start: date,
    end: date,
) -> tuple[date | None, str]:
    """The scenario date: ``wanted`` if the worker works then, else the nearest earlier working
    day; when that falls before ``start``, the first working day on or after ``start``."""
    d = wanted
    while d >= start:
        if plans_to_work(ctx, assignments, tally, d):
            note = "" if d == wanted else f"moved from {wanted} (not a working day for {tally})"
            return d, note
        d -= timedelta(days=1)
    d = start
    while d <= end:
        if plans_to_work(ctx, assignments, tally, d):
            return d, f"moved from {wanted} into the generated range"
        d += timedelta(days=1)
    return None, f"no working day for {tally} in the generated range"


def latest_weekday(on_or_before: date, weekdays: set[str]) -> date:
    d = on_or_before
    while dow(d) not in weekdays:
        d -= timedelta(days=1)
    return d


def plan_scenarios(
    ctx: Context, assignments: list[Assignment], start: date, end: date
) -> list[Scenario]:
    d_last = end
    wanted: list[tuple[str, str, date, str]] = [
        (
            "P1",
            P1_TALLY,
            latest_weekday(d_last, {"MON", "WED", "FRI"}),
            "45 min late at the first site",
        ),
        ("P2", P2_TALLY, d_last, "7 min late (inside the 10 min grace)"),
        ("P3", P3_TALLY, d_last - timedelta(days=2), "leaves the last site 70 min early"),
        ("P4", P4_TALLY, d_last - timedelta(days=3), "stays 75 min after the planned end (OT1)"),
        ("P4", P4_TALLY, d_last - timedelta(days=10), "stays 75 min after the planned end (OT1)"),
        ("P6", P6_TALLY, d_last - timedelta(days=1), f"skips {P6_SKIPPED_JOB} (pending visit)"),
        ("P6", P6_TALLY, d_last - timedelta(days=9), f"skips {P6_SKIPPED_JOB} (escalated)"),
        ("P7", P7_TALLY, d_last - timedelta(days=4), "no events at all, no leave (absent)"),
        ("P8", P8_TALLY, d_last - timedelta(days=2), "location off 11:00-12:30 (tracking gap)"),
        ("P9", P9_TALLY, d_last - timedelta(days=3), "events uploaded on D-1 evening (late)"),
    ]
    out: list[Scenario] = []
    seen: set[tuple[str, date]] = set()
    for code, tally, want, what in wanted:
        day, note = place(ctx, assignments, tally, want, start, end)
        if day is None:
            out.append(Scenario(code, tally, want, what, note="skipped: " + note))
            continue
        if (code, day) in seen:
            continue
        seen.add((code, day))
        out.append(Scenario(code, tally, day, what, note))

    # P5: works his own weekly off (Tuesday) at Le Pont, planned by an approved reassignment.
    p5 = latest_weekday(d_last, {"TUE"})
    while p5 in ctx.holidays and p5 >= start:
        p5 -= timedelta(days=7)
    if p5 >= start:
        out.append(Scenario("P5", P5_TALLY, p5, "works his weekly off at Le Pont (OT2)"))
    else:
        out.append(
            Scenario(
                "P5",
                P5_TALLY,
                p5,
                "works his weekly off at Le Pont (OT2)",
                "skipped: before --from",
            )
        )
    out.sort(key=lambda s: (s.code, s.day))
    return out


# --------------------------------------------------------------------------------------------
# Step 1: plan
# --------------------------------------------------------------------------------------------


def template_entries(
    ctx: Context, assignments: list[Assignment], item_key: tuple[str, str]
) -> list[tuple[UUID, str, Decimal, int]]:
    item = ctx.items[item_key]
    out: list[tuple[UUID, str, Decimal, int]] = []
    for a in assignments:
        if (a.job_number, a.sub_item_code) != item_key:
            continue
        for wd in a.weekdays:
            day_items = items_for_day(assignments, a.tally_id, wd)
            seq = 1 + [(x.job_number, x.sub_item_code) for x in day_items].index(item_key)
            out.append(
                (ctx.emp(a.tally_id).id, wd, Decimal(item.hours_per_occurrence_per_staff), seq)
            )
    return sorted(out, key=lambda e: (str(e[0]), WEEKDAYS.index(e[1])))


async def ensure_templates(
    session: AsyncSession, ctx: Context, assignments: list[Assignment], summary: Summary
) -> None:
    from fw.modules.scheduling import (
        BaseRosterEntry,
        BaseRosterEntryCreate,
        BaseRosterTemplate,
        BaseRosterTemplateCreate,
        SchedulingService,
    )

    for item_key in sorted({(a.job_number, a.sub_item_code) for a in assignments}):
        item = ctx.items[item_key]
        ws = ctx.worksites[item.worksite_id]
        wanted = template_entries(ctx, assignments, item_key)
        current = (
            (
                await session.execute(
                    select(BaseRosterEntry)
                    .join(BaseRosterTemplate, BaseRosterEntry.template_id == BaseRosterTemplate.id)
                    .where(
                        BaseRosterTemplate.job_item_id == item.id,
                        BaseRosterTemplate.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        have = sorted(
            (
                (e.employee_id, e.weekday_mask, Decimal(e.assigned_hours), e.sequence)
                for e in current
            ),
            key=lambda e: (str(e[0]), WEEKDAYS.index(e[1]) if e[1] in WEEKDAYS else 9),
        )
        if have == wanted:
            continue
        payload = BaseRosterTemplateCreate(
            job_item_id=item.id,
            allocation_mode="DAY_OF_WEEK",
            start_date=ws.start_date or item.start_date,
            end_date=ws.end_date,
            entries=[
                BaseRosterEntryCreate(
                    employee_id=emp_id, weekday_mask=wd, assigned_hours=hours, sequence=seq
                )
                for emp_id, wd, hours, seq in wanted
            ],
        )
        try:
            await SchedulingService(session).save_base_template(
                payload, current_user_id=ctx.admin.id
            )
        except AppError as exc:
            raise GeneratorError(
                f"Base Planner refused the template for {item_key[0]}{item_key[1]}: "
                f"{app_error_text(exc)}"
            ) from exc
        summary.templates_saved += 1


async def ensure_shifts(
    session: AsyncSession,
    ctx: Context,
    assignments: list[Assignment],
    start: date,
    end: date,
    summary: Summary,
) -> None:
    """One Operational Planner shift per planned worker-day and item, in visit order."""
    from fw.modules.scheduling import (
        OperationalShiftCreate,
        ScheduledWork,
        ScheduledWorkValidateRequest,
        SchedulingService,
    )
    from fw.rules.scheduling.blueprint import BlueprintEntry, resolve_base_template_slots

    worker_ids = [ctx.emp(t).id for t in ctx.workers]
    existing = {
        (row.employee_id, row.job_item_id, row.work_date)
        for row in (
            await session.execute(
                select(
                    ScheduledWork.employee_id, ScheduledWork.job_item_id, ScheduledWork.work_date
                ).where(
                    ScheduledWork.employee_id.in_(worker_ids),
                    ScheduledWork.work_date >= start,
                    ScheduledWork.work_date <= end,
                    ScheduledWork.status == "ACTIVE",
                )
            )
        ).all()
    }
    dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    offs = {
        ctx.emp(t).id: (ctx.emp(t).weekly_off_day or "").strip().upper()[:3] for t in ctx.workers
    }
    # (employee, date) -> [(sequence, item_key, hours)]
    per_day: dict[tuple[UUID, date], list[tuple[int, tuple[str, str], Decimal]]] = defaultdict(list)
    for item_key in sorted({(a.job_number, a.sub_item_code) for a in assignments}):
        item = ctx.items[item_key]
        entries = [
            BlueprintEntry(employee_id=e, weekday_mask=wd, assigned_hours=float(h), sequence=s)
            for e, wd, h, s in template_entries(ctx, assignments, item_key)
        ]
        item_dates = [
            d
            for d in dates
            if d >= item.start_date and (item.end_date is None or d <= item.end_date)
        ]
        for slot in resolve_base_template_slots(
            allocation_mode="DAY_OF_WEEK",
            entries=entries,
            target_dates=item_dates,
            public_holidays=ctx.holidays,
            worker_weekly_off_days=offs,
            skip_public_holidays=True,
        ):
            if slot.is_worker_weekly_off:
                summary.notes.append(
                    f"skipped a planned slot on a weekly off: {ctx.by_id[slot.employee_id].tally_id} "
                    f"{item_key[0]}{item_key[1]} {slot.work_date}"
                )
                continue
            per_day[(slot.employee_id, slot.work_date)].append(
                (slot.sequence, item_key, Decimal(str(slot.assigned_hours)))
            )

    service = SchedulingService(session)
    refusals: list[str] = []
    for (emp_id, d), slots in sorted(per_day.items(), key=lambda kv: (kv[0][1], str(kv[0][0]))):
        for seq, item_key, hours in sorted(slots):
            item = ctx.items[item_key]
            if (emp_id, item.id, d) in existing:
                summary.shifts_existing += 1
                continue
            report = await service.validate_scheduled_work_request(
                ScheduledWorkValidateRequest(
                    employee_id=emp_id,
                    job_item_id=item.id,
                    work_date=d,
                    assigned_hours=hours,
                    sequence=seq,
                ),
                is_admin=True,
            )
            if report.errors:
                tally = ctx.by_id[emp_id].tally_id
                refusals.append(
                    f"{tally} {item_key[0]}{item_key[1]} {d}: "
                    + "; ".join(f"{i.code} {i.message}" for i in report.errors)
                )
                continue
            await service.create_operational_shift(
                OperationalShiftCreate(
                    job_item_id=item.id,
                    work_date=d,
                    employee_id=emp_id,
                    assigned_hours=hours,
                    override_reason=SHIFT_REASON,
                    source="DIRECT",
                    acknowledge_warnings=True,
                ),
                current_user_id=ctx.admin.id,
            )
            summary.shifts_created += 1
    if refusals:
        raise GeneratorError(
            f"The scheduler refused {len(refusals)} shift(s); nothing was bypassed:\n  "
            + "\n  ".join(refusals[:20])
        )


async def ensure_p5_reassignment(
    session: AsyncSession, ctx: Context, scenario: Scenario, clock: FrozenClock
) -> None:
    """P5: supervisor 2702 asks 4 days ahead to ADD 2010 at Le Pont on his weekly off;
    engineer 2901 approves it the same day. Both through the scheduling service."""
    from fw.modules.scheduling import (
        ReassignmentRequest,
        ReassignmentRequestCreate,
        SchedulingService,
    )

    emp = ctx.emp(P5_TALLY)
    item = ctx.items[P5_TARGET]
    found = (
        await session.execute(
            select(ReassignmentRequest).where(
                ReassignmentRequest.new_employee_id == emp.id,
                ReassignmentRequest.date_from == scenario.day,
                ReassignmentRequest.reason == REASSIGN_REASON,
                ReassignmentRequest.status == "APPROVED",
            )
        )
    ).scalar_one_or_none()
    if found is not None:
        return
    clock.set(site_dt(scenario.day - timedelta(days=4), time(10, 0)))
    service = SchedulingService(session)
    try:
        created = await service.create_reassignment_request(
            ReassignmentRequestCreate(
                reassignment_type="ADD",
                date_from=scenario.day,
                date_to=scenario.day,
                new_employee_id=emp.id,
                target_job_item_id=item.id,
                hours_per_day=Decimal(item.hours_per_occurrence_per_staff),
                reason_category="CAPACITY",
                reason=REASSIGN_REASON,
            ),
            current_user=ctx.p5_requester,
        )
        clock.set(site_dt(scenario.day - timedelta(days=4), time(11, 0)))
        await service.approve_reassignment_request(
            created.id, decision_note="Approved (demo)", current_user=ctx.engineer
        )
        await session.commit()
    except AppError as exc:
        raise GeneratorError(f"P5 reassignment refused: {app_error_text(exc)}") from exc


# --------------------------------------------------------------------------------------------
# Step 2: devices and consent
# --------------------------------------------------------------------------------------------


async def ensure_devices(session: AsyncSession, ctx: Context, summary: Summary) -> dict[str, UUID]:
    """Log each worker in once through the mobile login service (binds ``DEMO-<tally>``) and
    accept the current consent version. Returns tally -> registered device id."""
    from fw.modules.org import RegisteredDevice
    from fw.modules.sync import ConsentRecord, MobileLoginRequest, SyncService
    from fw.modules.sync.schemas import MobileDeviceRegistration, PlatformEnum

    default_password = await SyncService.get_default_password(session)
    fallback_password = os.environ.get("FW_DEMO_WORKER_PASSWORD")
    policy = await SyncService.get_consent_policy(session=session, language="en")
    devices: dict[str, UUID] = {}
    for tally in ctx.workers:
        emp = ctx.emp(tally)
        identifier = f"{DEVICE_PREFIX}{tally}"
        active = (
            await session.execute(
                select(RegisteredDevice).where(
                    RegisteredDevice.employee_id == emp.id, RegisteredDevice.is_active.is_(True)
                )
            )
        ).scalar_one_or_none()
        if active is not None and active.device_identifier != identifier:
            raise GeneratorError(
                f"Worker {tally} is bound to another device ({active.device_identifier}), for "
                "example the mobile simulator. Reset that binding (Admin, Devices page) and run "
                "again; the generator never takes over a device it did not create."
            )
        if active is None:
            device = MobileDeviceRegistration(
                device_identifier=identifier,
                platform=PlatformEnum.ANDROID,
                device_model="Demo phone",
                app_version="demo-generator",
                os_version="Android 14",
            )
            last_error: AppError | None = None
            for password in (default_password, fallback_password):
                if not password:
                    continue
                try:
                    _, _, _, _, active = await SyncService.authenticate_mobile_worker(
                        session,
                        MobileLoginRequest(tally_id=tally, password=password, device=device),
                    )
                    last_error = None
                    break
                except AppError as exc:
                    last_error = exc
            if last_error is not None or active is None:
                code = last_error.code if last_error else "LOGIN_FAILED"
                raise GeneratorError(
                    f"Mobile login refused for {tally} ({code}). The generator logs in with the "
                    "default password; if it was changed, set FW_DEMO_WORKER_PASSWORD."
                )
            summary.devices_registered += 1
        devices[tally] = active.id
        consented = (
            await session.execute(
                select(ConsentRecord.id).where(
                    ConsentRecord.employee_id == emp.id,
                    ConsentRecord.device_id == active.id,
                    ConsentRecord.policy_version == policy.version,
                    ConsentRecord.status == "ACCEPTED",
                )
            )
        ).first()
        if consented is None:
            await SyncService.record_consent(
                session=session,
                employee_id=emp.id,
                policy_version=policy.version,
                consented_at_utc=datetime.now(UTC),
            )
            summary.consents_recorded += 1
    await session.commit()
    return devices


# --------------------------------------------------------------------------------------------
# Step 3: a worker's day as phone events
# --------------------------------------------------------------------------------------------


def site_dt(d: date, t: time) -> datetime:
    return datetime.combine(d, t, tzinfo=SITE_TZ)


def inner(poly: BaseGeometry) -> BaseGeometry:
    """The polygon shrunk away from its edge, so a 25 m accuracy never looks borderline."""
    for metres in (40.0, 25.0, 12.0):
        shrunk = poly.buffer(-metres / 111_000.0)
        if not shrunk.is_empty and shrunk.area > 0:
            return shrunk
    return poly.representative_point()


def point_in(poly: BaseGeometry, rng: random.Random) -> tuple[float, float]:
    area = inner(poly)
    if area.geom_type == "Point":
        p = cast(Point, area)
        return p.y, p.x
    minx, miny, maxx, maxy = area.bounds
    for _ in range(200):
        p = Point(rng.uniform(minx, maxx), rng.uniform(miny, maxy))
        if area.covers(p):
            return p.y, p.x
    rp = area.representative_point()
    return rp.y, rp.x


def point_just_outside(
    poly: BaseGeometry,
    toward: BaseGeometry,
    rng: random.Random,
    others: list[BaseGeometry],
) -> tuple[float, float]:
    """Where the phone sends EXIT: 12-35 m outside the boundary, on the side facing the next
    stop, and inside no other polygon. An EXIT reported inside the polygon is not accepted as an
    exit (EXIT_INSIDE_POLYGON) and the visit would end at its last ping instead."""
    for attempt in range(40):
        ring_area = poly.buffer(rng.uniform(12.0, 35.0) / 111_000.0)
        parts = list(getattr(ring_area, "geoms", [ring_area]))
        ring = max(parts, key=lambda g: g.area).exterior
        if attempt == 0:
            at = ring.project(toward.centroid) + rng.uniform(-15.0, 15.0) / 111_000.0
            p = ring.interpolate(at)
        else:
            p = ring.interpolate(rng.random(), normalized=True)
        if not poly.covers(p) and not any(o.covers(p) for o in others):
            return p.y, p.x
    raise GeneratorError("could not place an EXIT point outside a boundary")


@dataclass
class Stop:
    kind: str  # CAMP | SITE
    poly: BaseGeometry
    ref_id: UUID  # accommodation or worksite id
    job_item_id: UUID | None = None


@dataclass
class DayEvents:
    tally: str
    day: date
    events: list[dict[str, Any]]


class DayBuilder:
    """Builds one worker-day of events with deterministic jitter."""

    def __init__(self, ctx: Context, seed: int, tally: str, d: date) -> None:
        self.ctx = ctx
        self.tally = tally
        self.day = d
        self.rng = random.Random(f"{seed}|{tally}|{d.isoformat()}")
        self.seed = seed
        self.events: list[dict[str, Any]] = []
        self.all_polys = list(ctx.site_polys.values()) + list(ctx.camp_polys.values())

    def at(self, minutes: float) -> datetime:
        """Site-local minutes after midnight -> aware UTC datetime."""
        whole = int(round(minutes * 60))
        return (site_dt(self.day, time(0, 0)) + timedelta(seconds=whole)).astimezone(UTC)

    def add(
        self,
        kind: str,
        minutes: float,
        latlng: tuple[float, float] | None = None,
        *,
        job_id: UUID | None = None,
        job_item_id: UUID | None = None,
        accommodation_id: UUID | None = None,
    ) -> None:
        n = len(self.events)
        ts = self.at(minutes)
        ev: dict[str, Any] = {
            "event_id": uuid5(ID_NAMESPACE, f"{self.seed}|{self.tally}|{self.day}|{n}"),
            "event_type": kind,
            "event_timestamp_utc": ts,
            "location_captured_at_utc": ts if latlng else None,
            "latitude": Decimal(f"{latlng[0]:.6f}") if latlng else None,
            "longitude": Decimal(f"{latlng[1]:.6f}") if latlng else None,
            "accuracy_meters": round(self.rng.uniform(5, 25), 1) if latlng else None,
            "is_mock_location": False,
            "sequence_number": n + 1,
            "job_id": job_id,
            "job_item_id": job_item_id,
            "accommodation_id": accommodation_id,
        }
        self.events.append(ev)

    def ping_every(self, poly: BaseGeometry, start: float, end: float, **refs: Any) -> None:
        t = start + self.rng.uniform(8, 12)
        while t < end - 2:
            self.add("PING", t, point_in(poly, self.rng), **refs)
            t += self.rng.uniform(8, 12)

    def transit(self, a: BaseGeometry, b: BaseGeometry, start: float, end: float) -> None:
        """Pings every 8-12 minutes on the way, only where no polygon covers the point."""
        line = LineString([a.centroid, b.centroid])
        t = start + self.rng.uniform(6, 10)
        while t < end - 3:
            frac = (t - start) / max(end - start, 1)
            p = line.interpolate(frac, normalized=True)
            jitter = 0.0004
            q = Point(
                p.x + self.rng.uniform(-jitter, jitter), p.y + self.rng.uniform(-jitter, jitter)
            )
            if not any(poly.covers(q) for poly in self.all_polys):
                self.add("PING", t, (q.y, q.x))
            t += self.rng.uniform(8, 12)

    def visit(
        self,
        stop: Stop,
        start: float,
        end: float,
        toward: BaseGeometry,
        gap: tuple[float, float] | None = None,
    ) -> None:
        refs: dict[str, Any] = (
            {"accommodation_id": stop.ref_id}
            if stop.kind == "CAMP"
            else {"job_id": stop.ref_id, "job_item_id": stop.job_item_id}
        )
        self.add("ENTRY", start, point_in(stop.poly, self.rng), **refs)
        if gap is None:
            self.ping_every(stop.poly, start, end, **refs)
        else:
            off, on = gap
            self.ping_every(stop.poly, start, off, **refs)
            self.add("LOCATION_DISABLED", off)
            self.add("LOCATION_ENABLED", on)
            self.ping_every(stop.poly, on, end, **refs)
        self.add("EXIT", end, self.outside(stop.poly, toward), **refs)

    def outside(self, poly: BaseGeometry, toward: BaseGeometry) -> tuple[float, float]:
        others = [p for p in self.all_polys if p is not poly]
        return point_just_outside(poly, toward, self.rng, others)


def build_day(
    ctx: Context,
    seed: int,
    tally: str,
    d: date,
    plan: list[tuple[UUID, UUID, Decimal]],  # (worksite_id, job_item_id, hours) in sequence
    *,
    late: float | None = None,
    early: float | None = None,
    stay: float = 0.0,
    skip_job: str | None = None,
    location_off: tuple[float, float] | None = None,
) -> DayEvents:
    """Camp -> sites in plan order -> camp. Minutes are site-local minutes after midnight."""
    emp = ctx.emp(tally)
    b = DayBuilder(ctx, seed, tally, d)
    rng = b.rng
    camp_id = emp.accommodation_id
    camp = Stop("CAMP", ctx.camp_polys[camp_id], camp_id)
    sites = [
        Stop("SITE", ctx.site_polys[ws_id], ws_id, item_id)
        for ws_id, item_id, _ in plan
        if not (skip_job and ctx.worksites[ws_id].job_number == skip_job)
    ]
    hours = [
        float(h)
        for ws_id, _, h in plan
        if not (skip_job and ctx.worksites[ws_id].job_number == skip_job)
    ]
    if not sites:
        return DayEvents(tally, d, [])

    driver = bool(emp.is_driver)
    if driver:
        leave_camp = 5 * 60 + 45 + rng.uniform(-5, 5)
        first_arrival = leave_camp + rng.uniform(25, 35)
        last_exit = 17 * 60 + rng.uniform(-5, 5)
        back_at_camp = 17 * 60 + 30 + rng.uniform(-5, 5)
    else:
        # Normal days stay inside the 10-minute grace: late + early <= 9 minutes.
        late_min = late if late is not None else rng.uniform(0, 5)
        early_min = early if early is not None else rng.uniform(0, max(0.0, 9 - late_min))
        leave_camp = 6 * 60 + 20 + rng.uniform(-10, 10)
        first_arrival = 7 * 60 + late_min
        leave_camp = min(leave_camp, first_arrival - 20)
        last_exit = 15 * 60 + 30 - early_min + stay
        back_at_camp = max(16 * 60 + rng.uniform(-10, 10), last_exit + 20)

    # Before leaving: two pings at camp, then EXIT the camp.
    b.add(
        "PING",
        leave_camp - 20 - rng.uniform(0, 5),
        point_in(camp.poly, rng),
        accommodation_id=camp_id,
    )
    b.add(
        "PING",
        leave_camp - 8 - rng.uniform(0, 3),
        point_in(camp.poly, rng),
        accommodation_id=camp_id,
    )
    b.add("EXIT", leave_camp, b.outside(camp.poly, sites[0].poly), accommodation_id=camp_id)
    b.transit(camp.poly, sites[0].poly, leave_camp, first_arrival)

    # Site time: the window minus transits, split by planned hours.
    transits = [rng.uniform(8, 15) for _ in range(len(sites) - 1)]
    window = last_exit - first_arrival - sum(transits)
    total_h = sum(hours) or 1.0
    t = first_arrival
    for i, site in enumerate(sites):
        span = window * hours[i] / total_h
        end = t + span
        gap = None
        if location_off and location_off[0] > t and location_off[1] < end:
            gap = location_off
        toward = sites[i + 1].poly if i < len(sites) - 1 else camp.poly
        b.visit(site, t, end, toward, gap)
        if i < len(sites) - 1:
            nxt = end + transits[i]
            b.transit(site.poly, sites[i + 1].poly, end, nxt)
            t = nxt
    b.transit(sites[-1].poly, camp.poly, last_exit, back_at_camp)
    b.add("ENTRY", back_at_camp, point_in(camp.poly, rng), accommodation_id=camp_id)
    b.add(
        "PING", back_at_camp + rng.uniform(5, 9), point_in(camp.poly, rng), accommodation_id=camp_id
    )
    b.add(
        "PING",
        back_at_camp + rng.uniform(14, 20),
        point_in(camp.poly, rng),
        accommodation_id=camp_id,
    )
    return DayEvents(tally, d, b.events)


async def submit(
    session: AsyncSession,
    ctx: Context,
    device_id: UUID,
    day_events: DayEvents,
    clock: FrozenClock,
    seed: int,
    summary: Summary,
) -> None:
    """Upload a day's events as the phone would, in batches of at most 200, with the app clock at
    the current frozen instant; then commit (the listeners enrich and calculate in the same call)."""
    from fw.modules.events import EventBatchRequest, EventsService, MobileEventItem

    emp = ctx.emp(day_events.tally)
    if emp.consent_status == "WITHDRAWN":  # the route refuses these; so does the generator
        summary.refused["CONSENT_WITHDRAWN"] += len(day_events.events)
        return
    events = day_events.events
    for i in range(0, len(events), MAX_BATCH):
        chunk = events[i : i + MAX_BATCH]
        batch = EventBatchRequest(
            batch_id=uuid5(
                ID_NAMESPACE, f"batch|{seed}|{day_events.tally}|{day_events.day}|{i // MAX_BATCH}"
            ),
            device_clock_utc=clock.now(),
            events=[MobileEventItem(**e) for e in chunk],
        )
        results = await EventsService.ingest_batch(
            session=session, employee_id=emp.id, device_id=device_id, batch=batch
        )
        for r in results:
            summary.events[r.status.value] += 1
            if r.reason is not None:
                summary.refused[r.reason.value] += 1
        await session.commit()


# --------------------------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------------------------


async def table_counts(session: AsyncSession) -> dict[str, int]:
    out: dict[str, int] = {}
    for table in TABLES:
        out[table] = int(
            (await session.execute(text(f"SELECT count(*) FROM {table}"))).scalar() or 0
        )
    return out


async def day_plan(
    session: AsyncSession, ctx: Context, emp_id: UUID, d: date
) -> list[tuple[UUID, UUID, Decimal]]:
    from fw.modules.scheduling import ScheduledWork

    rows = (
        (
            await session.execute(
                select(ScheduledWork)
                .where(
                    ScheduledWork.employee_id == emp_id,
                    ScheduledWork.work_date == d,
                    ScheduledWork.status == "ACTIVE",
                )
                .order_by(ScheduledWork.sequence, ScheduledWork.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [(r.worksite_id, r.job_item_id, Decimal(r.assigned_hours)) for r in rows]


def log(opts: Options, msg: str) -> None:
    if not opts.quiet:
        print(msg, flush=True)


async def run(opts: Options) -> Summary:
    """Generate the demo activity. Puts the app clock back as it was when done."""
    refused = target_problems()
    if refused:
        raise GeneratorError("Refused: " + "; ".join(refused))
    if opts.date_to < opts.date_from:
        raise GeneratorError("--to is before --from")

    import fw.main  # noqa: F401  # every model mapped, as in the app
    from fw.core.db import async_session_factory

    assignments = load_assignments()
    plan_end = opts.date_to + timedelta(days=opts.plan_ahead_days)
    summary = Summary()
    clock = FrozenClock(datetime.now(UTC))
    _register_listeners()

    async with async_session_factory() as session:
        if not opts.dry_run:
            await ensure_demo_leave(session, await find_admin(session), summary)
        ctx = await load_context(session, assignments, opts.date_from, plan_end)
        scenarios = plan_scenarios(ctx, assignments, opts.date_from, opts.date_to)
        summary.scenarios = scenarios
        if opts.dry_run:
            await _dry_run(session, ctx, assignments, opts, plan_end, summary)
            return summary
        if opts.reset_generated:
            summary.removed = await reset_generated(session, ctx, assignments, opts)
        summary.rows_before = await table_counts(session)

    previous_clock = get_system_clock()
    set_system_clock(clock)
    try:
        async with async_session_factory() as session:
            ctx = await load_context(session, assignments, opts.date_from, plan_end)
            log(opts, "1/6 Plan: Base Planner templates and Operational Planner shifts")
            await ensure_templates(session, ctx, assignments, summary)
            await ensure_shifts(session, ctx, assignments, opts.date_from, plan_end, summary)
            p5 = next((s for s in scenarios if s.code == "P5" and not s.note), None)
            if p5 is not None:
                await ensure_p5_reassignment(session, ctx, p5, clock)
            log(opts, f"   templates {summary.templates_saved}, shifts {summary.shifts_created}")

            log(opts, "2/6 Devices and consent")
            clock.set(site_dt(opts.date_from - timedelta(days=1), time(18, 0)))
            devices = await ensure_devices(session, ctx, summary)

            log(opts, "3-4/6 Events and day close, day by day")
            await play_days(session, ctx, assignments, devices, scenarios, opts, clock, summary)

            log(opts, "5/6 Reviews")
            clock.set(datetime.now(UTC))
            await approve_reviews(session, ctx, opts, summary)

            set_system_clock(previous_clock)  # payroll runs on the real clock
            if opts.payroll and opts.date_from <= date(2026, 10, 31):
                log(opts, "6/6 October payroll draft")
                await payroll_draft(session, ctx, summary)
            await fill_scenario_outcomes(session, ctx, summary)
            summary.rows_after = await table_counts(session)
    finally:
        set_system_clock(previous_clock)
    return summary


def _register_listeners() -> None:
    from fw.modules.attendance import register_attendance_listeners
    from fw.modules.jobs import register_jobs_listeners
    from fw.modules.notifications import register_notification_handlers
    from fw.modules.reports import register_reports_listeners
    from fw.modules.sync import register_sync_listeners

    register_sync_listeners()
    register_attendance_listeners()
    register_jobs_listeners()
    register_notification_handlers()
    register_reports_listeners()


async def play_days(
    session: AsyncSession,
    ctx: Context,
    assignments: list[Assignment],
    devices: dict[str, UUID],
    scenarios: list[Scenario],
    opts: Options,
    clock: FrozenClock,
    summary: Summary,
) -> None:
    from fw.modules.attendance import AttendanceService, PendingVisitsService
    from fw.modules.scheduling import ScheduledWork

    by_code_day = {(s.code, s.day): s for s in scenarios if not s.note.startswith("skipped")}
    p9 = next((s for s in scenarios if s.code == "P9" and (s.code, s.day) in by_code_day), None)
    deferred: list[DayEvents] = []
    worker_ids = {ctx.emp(t).id for t in ctx.workers}

    d = opts.date_from
    while d <= opts.date_to:
        clock.set(site_dt(d, time(20, 0)))
        for tally in ctx.workers:
            emp = ctx.emp(tally)
            if d in ctx.leave_days.get(emp.id, set()):
                continue  # P10: on leave, no events
            if (("P7", d) in by_code_day) and tally == P7_TALLY:
                continue
            plan = await day_plan(session, ctx, emp.id, d)
            if not plan:
                continue
            kwargs: dict[str, Any] = {}
            if tally == P1_TALLY and ("P1", d) in by_code_day:
                kwargs = {"late": 45.0, "early": 0.0}
            elif tally == P2_TALLY and ("P2", d) in by_code_day:
                kwargs = {"late": 7.0, "early": 0.0}
            elif tally == P3_TALLY and ("P3", d) in by_code_day:
                kwargs = {"late": 0.0, "early": 70.0}
            elif tally == P4_TALLY and ("P4", d) in by_code_day:
                kwargs = {"late": 0.0, "early": 0.0, "stay": 75.0}
            elif tally == P5_TALLY and ("P5", d) in by_code_day:
                kwargs = {"late": 0.0, "early": 0.0}
            elif tally == P6_TALLY and ("P6", d) in by_code_day:
                kwargs = {"skip_job": P6_SKIPPED_JOB}
            elif tally == P8_TALLY and ("P8", d) in by_code_day:
                kwargs = {"location_off": (11 * 60.0, 12 * 60 + 30.0)}
            day_events = build_day(ctx, opts.seed, tally, d, plan, **kwargs)
            summary.worker_days += 1
            if p9 is not None and tally == P9_TALLY and d == p9.day:
                deferred.append(day_events)
                continue
            await submit(session, ctx, devices[tally], day_events, clock, opts.seed, summary)

        # P9: that day's events reach the server on D-1 evening (or the last day).
        if p9 is not None and deferred:
            upload_day = max(p9.day + timedelta(days=1), opts.date_to - timedelta(days=1))
            if d == upload_day:
                clock.set(site_dt(d, time(20, 30)))
                for late in deferred:
                    await submit(session, ctx, devices[late.tally], late, clock, opts.seed, summary)
                deferred.clear()

        # Day close, as on the next morning: every planned worker is calculated, then the
        # pending-visit detection and reminders of the worker process.
        clock.set(site_dt(d + timedelta(days=1), time(0, 30)))
        planned = (
            (
                await session.execute(
                    select(ScheduledWork.employee_id)
                    .where(
                        ScheduledWork.work_date == d,
                        ScheduledWork.status == "ACTIVE",
                        ScheduledWork.employee_id.in_(worker_ids),
                    )
                    .distinct()
                )
            )
            .scalars()
            .all()
        )
        for emp_id in sorted(planned, key=str):
            rec = await AttendanceService.recalculate_day(
                session=session, employee_id=emp_id, work_date=d, reason="DAY_CLOSE"
            )
            if rec is not None:
                summary.day_close_calculations += 1
        await session.commit()
        summary.pending_visits_detected += await PendingVisitsService.detect_pending_visits(
            session=session, target_date=d, country=COUNTRY
        )
        await PendingVisitsService.check_pending_visit_reminders(session=session)
        await session.commit()
        log(opts, f"   {d} done")
        d += timedelta(days=1)


async def approve_reviews(
    session: AsyncSession, ctx: Context, opts: Options, summary: Summary
) -> None:
    """Engineer 2901 approves PENDING_REVIEW days older than 7 days, with the DEC-10 check the
    decision route applies."""
    from fw.modules.attendance import AttendanceRecord, AttendanceService
    from fw.modules.attendance.schemas import AttendanceDecisionRequest
    from fw.modules.scheduling import AccessScope

    cutoff = opts.date_to - timedelta(days=REVIEW_AFTER_DAYS)
    worker_ids = [ctx.emp(t).id for t in ctx.workers]
    scope = await AccessScope.resolve(session, ctx.engineer)
    rows = (
        (
            await session.execute(
                select(AttendanceRecord)
                .where(
                    AttendanceRecord.employee_id.in_(worker_ids),
                    AttendanceRecord.review_status == "PENDING_REVIEW",
                    AttendanceRecord.work_date >= opts.date_from,
                    AttendanceRecord.work_date <= cutoff,
                )
                .order_by(AttendanceRecord.work_date, AttendanceRecord.id)
            )
        )
        .scalars()
        .all()
    )
    for rec in rows:
        if not scope.can_decide(rec.employee_id):
            summary.reviews_refused += 1
            continue
        await AttendanceService.record_decision(
            session=session,
            attendance_id=rec.id,
            reviewer_user_id=ctx.engineer.id,
            request=AttendanceDecisionRequest(decision="APPROVED", comment=REVIEW_COMMENT),
        )
        summary.reviews_approved += 1
    await session.commit()
    if summary.reviews_refused:
        summary.notes.append(
            f"{summary.reviews_refused} review(s) left open: outside engineer 2901's crew chain"
        )


async def payroll_draft(session: AsyncSession, ctx: Context, summary: Summary) -> None:
    from fw.modules.payroll import PayrollRunCreate, PayrollService

    try:
        run = await PayrollService.generate_draft_run(
            session=session,
            payload=PayrollRunCreate(
                period_start=date(2026, 10, 1),
                period_end=date(2026, 10, 31),
                country=COUNTRY,
                notes=PAYROLL_NOTES,
                treat_leaves_as_paid=False,
            ),
            user_id=ctx.admin.id,
            actor_role="ADMIN",
        )
        await session.commit()
        summary.payroll_run_id = run.id
    except AppError as exc:
        await session.rollback()
        summary.notes.append(f"October payroll draft refused: {app_error_text(exc)}")


async def fill_scenario_outcomes(session: AsyncSession, ctx: Context, summary: Summary) -> None:
    from fw.modules.attendance import AttendanceCalculation, AttendanceRecord

    for s in summary.scenarios:
        if s.note.startswith("skipped"):
            continue
        row = (
            await session.execute(
                select(AttendanceRecord, AttendanceCalculation)
                .outerjoin(
                    AttendanceCalculation,
                    AttendanceRecord.current_calculation_id == AttendanceCalculation.id,
                )
                .where(
                    AttendanceRecord.employee_id == ctx.emp(s.tally).id,
                    AttendanceRecord.work_date == s.day,
                )
            )
        ).first()
        if row is None:
            s.outcome = "no attendance record"
            continue
        rec, calc = row
        s.attendance_id = rec.id
        parts = [rec.business_status, rec.review_status]
        if calc is not None:
            parts.append(f"v{calc.version_no}")
            if calc.flags:
                parts.append(",".join(calc.flags))
            if calc.ot1_minutes:
                parts.append(f"OT1 {calc.ot1_minutes} min")
            if calc.ot2_minutes:
                parts.append(f"OT2 {calc.ot2_minutes} min")
            if calc.shortfall_minutes:
                parts.append(f"short {calc.shortfall_minutes} min")
        s.outcome = " ".join(parts)


# --------------------------------------------------------------------------------------------
# Dry run and reset
# --------------------------------------------------------------------------------------------


async def _dry_run(
    session: AsyncSession,
    ctx: Context,
    assignments: list[Assignment],
    opts: Options,
    plan_end: date,
    summary: Summary,
) -> None:
    planned = 0
    worker_days = 0
    d = opts.date_from
    while d <= plan_end:
        for tally in ctx.workers:
            if plans_to_work(ctx, assignments, tally, d, ignore_leave=True):
                planned += len(items_for_day(assignments, tally, dow(d)))
                if d <= opts.date_to and plans_to_work(ctx, assignments, tally, d):
                    worker_days += 1
        d += timedelta(days=1)
    summary.shifts_created = planned
    summary.worker_days = worker_days
    summary.notes.append("dry run: nothing was written")
    if opts.reset_generated:
        summary.removed = await reset_generated(session, ctx, assignments, opts, dry_run=True)


async def reset_generated(
    session: AsyncSession,
    ctx: Context,
    assignments: list[Assignment],
    opts: Options,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """Remove what the generator created for the demo workers, in dependency order:
    attendance and pending visits from --from on, events and ``DEMO-`` devices, the generated
    shifts (tagged) and the P5 reassignment, and the generated Base Planner templates.
    Imported master data, users and anything else stay. Payroll is re-run by the generator."""
    from fw.modules.attendance import (
        AttendanceApproval,
        AttendanceCalculation,
        AttendanceComment,
        AttendanceRecord,
        PendingVisit,
        SiteVisit,
        TrackingGap,
    )
    from fw.modules.events import EmployeeLastPosition, MobileEventLog
    from fw.modules.notifications import Alert
    from fw.modules.org import RegisteredDevice
    from fw.modules.scheduling import (
        BaseRosterEntry,
        BaseRosterTemplate,
        ReassignmentRequest,
        ScheduledWork,
    )
    from fw.modules.sync import ConsentRecord

    worker_ids = [ctx.emp(t).id for t in ctx.workers]
    since = opts.date_from
    device_ids = list(
        (
            await session.execute(
                select(RegisteredDevice.id).where(
                    RegisteredDevice.employee_id.in_(worker_ids),
                    RegisteredDevice.device_identifier.like(f"{DEVICE_PREFIX}%"),
                )
            )
        ).scalars()
    )
    reassign_ids = list(
        (
            await session.execute(
                select(ReassignmentRequest.id).where(
                    ReassignmentRequest.reason == REASSIGN_REASON,
                    ReassignmentRequest.new_employee_id.in_(worker_ids),
                )
            )
        ).scalars()
    )
    shift_ids = list(
        (
            await session.execute(
                select(ScheduledWork.id).where(
                    ScheduledWork.employee_id.in_(worker_ids),
                    or_(
                        ScheduledWork.override_reason == SHIFT_REASON,
                        ScheduledWork.reassignment_request_id.in_(reassign_ids)
                        if reassign_ids
                        else false(),
                    ),
                )
            )
        ).scalars()
    )
    record_ids = list(
        (
            await session.execute(
                select(AttendanceRecord.id).where(
                    AttendanceRecord.employee_id.in_(worker_ids),
                    AttendanceRecord.work_date >= since,
                )
            )
        ).scalars()
    )
    item_ids = [ctx.items[(a.job_number, a.sub_item_code)].id for a in assignments]
    template_ids = []
    for tmpl in (
        (
            await session.execute(
                select(BaseRosterTemplate).where(
                    BaseRosterTemplate.job_item_id.in_(item_ids),
                    BaseRosterTemplate.created_by_user_id == ctx.admin.id,
                )
            )
        )
        .scalars()
        .all()
    ):
        emps = set(
            (
                await session.execute(
                    select(BaseRosterEntry.employee_id).where(
                        BaseRosterEntry.template_id == tmpl.id
                    )
                )
            ).scalars()
        )
        if emps <= set(worker_ids):
            template_ids.append(tmpl.id)

    def ids_in(col: Any, values: list[UUID]) -> Any:
        return col.in_(values) if values else false()

    steps: list[tuple[str, Any]] = [
        (
            "pending_visits",
            delete(PendingVisit).where(
                or_(
                    ids_in(PendingVisit.scheduled_work_id, shift_ids),
                    (PendingVisit.employee_id.in_(worker_ids)) & (PendingVisit.due_date >= since),
                )
            ),
        ),
        (
            "alerts",
            delete(Alert).where(
                Alert.employee_id.in_(worker_ids),
                Alert.alert_type.in_(("PENDING_VISIT", "TRACKING_INTERRUPTED", "NO_ACTIVITY")),
            ),
        ),
        (
            "attendance_approvals",
            delete(AttendanceApproval).where(ids_in(AttendanceApproval.attendance_id, record_ids)),
        ),
        (
            "attendance_comments",
            delete(AttendanceComment).where(ids_in(AttendanceComment.attendance_id, record_ids)),
        ),
        (
            "attendance_records (unlink)",
            update(AttendanceRecord)
            .where(ids_in(AttendanceRecord.id, record_ids))
            .values(current_calculation_id=None),
        ),
        (
            "attendance_calculations",
            delete(AttendanceCalculation).where(
                ids_in(AttendanceCalculation.attendance_record_id, record_ids)
            ),
        ),
        (
            "attendance_records",
            delete(AttendanceRecord).where(ids_in(AttendanceRecord.id, record_ids)),
        ),
        (
            "site_visits",
            delete(SiteVisit).where(
                SiteVisit.employee_id.in_(worker_ids), SiteVisit.work_date >= since
            ),
        ),
        (
            "tracking_gaps",
            delete(TrackingGap).where(
                TrackingGap.employee_id.in_(worker_ids), TrackingGap.work_date >= since
            ),
        ),
        (
            "employee_last_position",
            delete(EmployeeLastPosition).where(EmployeeLastPosition.employee_id.in_(worker_ids)),
        ),
        (
            "mobile_event_logs",
            delete(MobileEventLog).where(ids_in(MobileEventLog.device_id, device_ids)),
        ),
        (
            "consent_records",
            delete(ConsentRecord).where(ids_in(ConsentRecord.device_id, device_ids)),
        ),
        (
            "registered_devices",
            delete(RegisteredDevice).where(ids_in(RegisteredDevice.id, device_ids)),
        ),
        ("scheduled_work", delete(ScheduledWork).where(ids_in(ScheduledWork.id, shift_ids))),
        (
            "reassignment_requests",
            delete(ReassignmentRequest).where(ids_in(ReassignmentRequest.id, reassign_ids)),
        ),
        (
            "base_roster_entries",
            delete(BaseRosterEntry).where(ids_in(BaseRosterEntry.template_id, template_ids)),
        ),
        (
            "base_roster_templates",
            delete(BaseRosterTemplate).where(ids_in(BaseRosterTemplate.id, template_ids)),
        ),
    ]
    removed: dict[str, int] = {}
    if dry_run:
        removed = {
            "registered_devices": len(device_ids),
            "scheduled_work": len(shift_ids),
            "attendance_records": len(record_ids),
            "reassignment_requests": len(reassign_ids),
            "base_roster_templates": len(template_ids),
        }
        return removed
    # Phone events are append-only (trigger on mobile_event_logs). Like Settings > Reset database,
    # this transaction switches the guard off to remove the events of the DEMO- devices only.
    await session.execute(text("SET LOCAL fwt.bypass_immutability = 'on'"))
    for name, stmt in steps:
        res = await session.execute(stmt)
        removed[name] = int(getattr(res, "rowcount", 0) or 0)
    await session.commit()
    return removed


# --------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------


def print_summary(opts: Options, summary: Summary, names: dict[str, str]) -> None:
    print()
    print(
        f"Demo activity {opts.date_from} .. {opts.date_to} (seed {opts.seed}) on {database_label()}"
    )
    if summary.removed:
        print("Removed (--reset-generated):")
        for k, v in summary.removed.items():
            print(f"  {k:28s} {v:>8,}")
    if summary.rows_before or summary.rows_after:
        print("Rows created per table:")
        for t in TABLES:
            before, after = summary.rows_before.get(t, 0), summary.rows_after.get(t, 0)
            print(f"  {t:28s} {after - before:>+8,}   (now {after:,})")
    if summary.leaves_imported:
        print(f"Leave: {summary.leaves_imported} demo leave row(s) imported (Admin leave import)")
    print(
        f"Plan: {summary.templates_saved} template(s) saved, {summary.shifts_created} shift(s) "
        f"created, {summary.shifts_existing} already there"
    )
    print(
        f"Devices registered {summary.devices_registered}, consents recorded "
        f"{summary.consents_recorded}, worker-days played {summary.worker_days}"
    )
    print(
        "Events: "
        + (", ".join(f"{k} {v:,}" for k, v in sorted(summary.events.items())) or "none")
        + "; refused by reason: "
        + (", ".join(f"{k} {v}" for k, v in sorted(summary.refused.items())) or "none")
    )
    print(
        f"Day close: {summary.day_close_calculations} calculation(s), "
        f"{summary.pending_visits_detected} pending visit(s) detected; reviews approved "
        f"{summary.reviews_approved}"
    )
    if summary.payroll_run_id:
        print(f"October payroll draft: run {summary.payroll_run_id} (DRAFT, not approved)")
    print("Planted scenarios:")
    for s in summary.scenarios:
        who = f"{s.tally} {names.get(s.tally, '')}".strip()
        rec = f" record {s.attendance_id}" if s.attendance_id else ""
        note = f" [{s.note}]" if s.note else ""
        out = f" -> {s.outcome}" if s.outcome else ""
        print(f"  {s.code:3s} {s.day}  {who:28s} {s.what}{note}{out}{rec}")
    print(f"  P10 leave days (no events): {_leave_line(names)}")
    print(f"  P11 driver {P11_TALLY}: every working day, camp to camp")
    print(f"  P12 {P12_TALLY}: weekdays at 22A15201 (another supervisor's site), cross-crew view")
    for n in summary.notes:
        print(f"Note: {n}")


_LEAVE_TEXT: list[str] = []


def _leave_line(names: dict[str, str]) -> str:
    return "; ".join(_LEAVE_TEXT) or "none in range"


def parse_args(argv: Iterable[str] | None = None) -> Options:
    from fw.core.clock import site_today

    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    p.add_argument("--from", dest="date_from", type=date.fromisoformat, default=date(2026, 10, 1))
    p.add_argument("--to", dest="date_to", type=date.fromisoformat, default=None)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--dry-run", action="store_true", help="show what would happen; write nothing")
    p.add_argument(
        "--reset-generated",
        action="store_true",
        help="remove what an earlier run generated, then generate again",
    )
    p.add_argument(
        "--plan-ahead-days", type=int, default=PLAN_AHEAD_DAYS, help="shifts after --to (30)"
    )
    p.add_argument("--no-payroll", action="store_true", help="skip the October payroll draft")
    a = p.parse_args(list(argv) if argv is not None else None)
    date_to = a.date_to or (site_today(COUNTRY) - timedelta(days=1))
    if date_to >= site_today(COUNTRY):
        p.error("--to must be before today: today is played live from the mobile simulator")
    return Options(
        date_from=a.date_from,
        date_to=date_to,
        seed=a.seed,
        dry_run=a.dry_run,
        reset_generated=a.reset_generated,
        plan_ahead_days=a.plan_ahead_days,
        payroll=not a.no_payroll,
    )


async def _names_and_leave(opts: Options) -> dict[str, str]:
    from fw.core.db import async_session_factory
    from fw.modules.org import Employee
    from fw.modules.scheduling import LeaveRequest

    async with async_session_factory() as session:
        rows = (await session.execute(select(Employee.tally_id, Employee.name))).all()
        names = {t: n for t, n in rows}
        leaves = (
            await session.execute(
                select(
                    Employee.tally_id,
                    LeaveRequest.leave_type,
                    LeaveRequest.from_date,
                    LeaveRequest.to_date,
                )
                .join(Employee, Employee.id == LeaveRequest.employee_id)
                .where(
                    LeaveRequest.status == "APPROVED",
                    LeaveRequest.to_date >= opts.date_from,
                    LeaveRequest.from_date <= opts.date_to,
                    Employee.tally_id.in_({a.tally_id for a in load_assignments()}),
                )
                .order_by(LeaveRequest.from_date)
            )
        ).all()
        _LEAVE_TEXT[:] = [f"{t} {lt} {f}..{to}" for t, lt, f, to in leaves]
    return names


async def amain(argv: Iterable[str] | None = None) -> int:
    opts = parse_args(argv)
    try:
        summary = await run(opts)
    except GeneratorError as exc:
        print(f"Stopped: {exc}", file=sys.stderr)
        return 2
    names = await _names_and_leave(opts)
    print_summary(opts, summary, names)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
