"""Build the scaled MOCK dataset in the local ``fw_perf`` database (Batch 9 step 1).

From the repo root:

    uv run --directory backend python ../tools/perf/seed_perf_dataset.py --recreate

Refuses any database not named ``*_perf``, any non-local host and ``APP_ENV=production``
(``perf_db.py``). ``fw_db`` and ``fw_test`` are never touched.

What goes through the app's own code: occurrences (``JobsService.generate_job_occurrences``),
attendance values (the pure engine ``fw.rules.attendance.engine``) and the October payroll draft
(``PayrollService.generate_draft_run``, which also generates its month-end reports). Master data,
scheduled work, attendance rows, site visits and phone events are bulk-inserted with realistic
shapes, because the event pipeline would take hours at this size. They exist to load the pages,
not to be correct. MOCK DATA ONLY (see ``perf_dataset.py``).
"""

from __future__ import annotations

import argparse
import asyncio
import bisect
import os
import random
import sys
import time as wallclock
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

import perf_db  # noqa: E402
from perf_dataset import (  # noqa: E402
    GRADE_BASIC,
    GRADE_CODES,
    STAFF_TYPES,
    WEEKLY_OFF,
    Dataset,
    Scale,
    build_dataset,
    on_leave,
    work_dates,
)

ADMIN_USERNAME = "PERFADMIN"
ADMIN_PASSWORD_ENV = "FW_PERF_ADMIN_PASSWORD"
DEFAULT_ADMIN_PASSWORD = "PerfAdmin-local-1"  # local fw_perf only; mock data
HISTORY_START = date(2026, 9, 1)
TZ = {"AE": ZoneInfo("Asia/Dubai"), "SA": ZoneInfo("Asia/Riyadh")}
CHUNK = 5000
PING_MINUTES = 5


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def complete(table: Any, row: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Fill the bookkeeping columns this table has and the row left out."""
    cols = table.c
    if "id" in cols and cols["id"].primary_key and "id" not in row:
        row["id"] = uuid4()
    for name, value in (("created_at", now), ("updated_at", now), ("version", 1), ("is_active", True)):
        if name in cols and name not in row:
            row[name] = value
    return row


async def bulk(session: Any, model: Any, rows: list[dict[str, Any]], label: str | None) -> None:
    from sqlalchemy import insert

    table = model.__table__
    now = datetime.now(UTC)
    for i in range(0, len(rows), CHUNK):
        part = [complete(table, r, now) for r in rows[i : i + CHUNK]]
        await session.execute(insert(table), part)
    await session.commit()
    if label:
        log(f"  {label}: {len(rows):,}")


def point(lon: float, lat: float) -> Any:
    from geoalchemy2 import WKTElement

    return WKTElement(f"POINT({lon:.6f} {lat:.6f})", srid=4326)


async def seed_base(session: Any, password: str) -> UUID:
    from sqlalchemy import select, text

    from fw.modules.identity import User, hash_password
    from fw.modules.payroll import PayrollService, SalaryRevision, SalaryRevisionLine
    from fw.rules.lookups import SEED_STAFF_TYPES, value_key

    values = sorted(set(SEED_STAFF_TYPES) | set(STAFF_TYPES) | {"Supervisor", "Superintendent"})
    await session.execute(
        text(
            "INSERT INTO lookup_values (id, list_key, value, value_key, source, is_active, "
            "version, created_at, updated_at) VALUES (gen_random_uuid(), "
            "'staff_grade_description', :v, :vk, 'SEED', true, 1, now(), now()) "
            "ON CONFLICT (list_key, value_key) DO NOTHING"
        ),
        [{"v": v, "vk": value_key(v)} for v in values],
    )
    for country in ("AE", "SA"):
        rev = SalaryRevision(
            code=f"PERF-{country}",
            name=f"Perf revision {country} (mock)",
            country=country,
            effective_from=date(2026, 1, 1),
            status="ACTIVE",
        )
        for code in GRADE_CODES:
            basic = Decimal(GRADE_BASIC[code])
            rev.lines.append(
                SalaryRevisionLine(
                    grade_code=code,
                    basic_salary=basic,
                    special_allowance=Decimal("150"),
                    fixed_ot_amount=Decimal("100"),
                    visa_provision=Decimal("132"),
                    air_ticket_provision=Decimal("65"),
                    uniform_provision=Decimal("30"),
                    medical_provision=Decimal("65"),
                    accommodation_provision=Decimal("550"),
                )
            )
        session.add(rev)
    await session.flush()
    await PayrollService.refresh_grade_list(session)

    admin = (await session.execute(select(User).where(User.username == ADMIN_USERNAME))).scalar_one_or_none()
    if admin is None:
        admin = User(
            username=ADMIN_USERNAME,
            credential_hash=hash_password(password),
            role="ADMIN",
            is_active=True,
            must_change_password=False,
        )
        session.add(admin)
    await session.commit()
    return admin.id


async def seed_master(session: Any, ds: Dataset, user_hash: str) -> dict[str, Any]:
    from geoalchemy2 import WKTElement

    from fw.modules.identity import User
    from fw.modules.jobs import JobItem, Worksite
    from fw.modules.jobs.models import WorksiteSupervisor
    from fw.modules.org import Employee, Group, RegisteredDevice, Zone
    from fw.modules.payroll import EmployeeSalary

    group_ids = [uuid4() for _ in range(ds.scale.groups)]
    zone_ids = [uuid4() for _ in range(ds.scale.zones)]
    await bulk(
        session,
        Group,
        [{"id": g, "code": f"{701 + i}", "name": f"Perf Group {i + 1:02d}"} for i, g in enumerate(group_ids)],
        "groups",
    )
    await bulk(
        session,
        Zone,
        [{"id": z, "code": f"PZ{i + 1:02d}", "name": f"Perf Zone {i + 1:02d}"} for i, z in enumerate(zone_ids)],
        "zones",
    )

    site_ids = [uuid4() for _ in ds.sites]
    await bulk(
        session,
        Worksite,
        [
            {
                "id": site_ids[s.index],
                "job_number": s.job_number,
                "job_name": s.job_name,
                "renewal_reference": "R1",
                "group_id": group_ids[s.group_index],
                "zone_id": zone_ids[s.zone_index],
                "customer_type": "Commercial",
                "is_outdoor": True,
                "country": s.country,
                "start_date": date(2026, 1, 1),
                "boundary": WKTElement(s.wkt, srid=4326),
                "rep_latitude": Decimal(str(s.lat)),
                "rep_longitude": Decimal(str(s.lon)),
                "budget_amount": s.budget,
                "salary_revision_code": f"PERF-{s.country}",
            }
            for s in ds.sites
        ],
        "worksites",
    )

    item_ids = [uuid4() for _ in ds.items]
    await bulk(
        session,
        JobItem,
        [
            {
                "id": item_ids[it.index],
                "worksite_id": site_ids[it.site_index],
                "sub_item_code": it.sub_item_code,
                "staff_grade_description": it.staff_type,
                "planned_grade_code": it.grade_code,
                "frequency_unit": "WEEK",
                "occurrences_per_period": Decimal(len(it.weekdays)),
                "period_interval": 1,
                "weekday_pattern": it.weekdays,
                "required_staff_count": it.required_staff,
                "hours_per_occurrence_per_staff": it.hours,
                "start_date": date(2026, 1, 1),
                "deployment_type": "PERMANENT",
            }
            for it in ds.items
        ],
        "job items",
    )

    emp_ids = [uuid4() for _ in ds.employees]
    await bulk(
        session,
        Employee,
        [
            {
                "id": emp_ids[e.index],
                "tally_id": e.tally_id,
                "name": e.name,
                "role": e.role,
                "grade_code": e.grade_code,
                "staff_grade_description": e.staff_type,
                "weekly_off_day": WEEKLY_OFF,
                "is_driver": False,
                "country": e.country,
                "join_date": date(2025, 1, 1),
                "consent_status": "ACCEPTED",
            }
            for e in ds.employees
        ],
        "employees",
    )
    await bulk(
        session,
        EmployeeSalary,
        [
            {
                "employee_id": emp_ids[e.index],
                "effective_from": date(2026, 1, 1),
                "standard_hours": Decimal("8.0"),
                "basic_salary": e.basic,
                "special_allowance": Decimal("150.00"),
                "fixed_ot_amount": Decimal("100.00"),
                "bonus": Decimal("0.00"),
                "telephone_allowance": Decimal("25.00"),
                "housing_transport_allowance": Decimal("300.00"),
                "change_source": "PERF_SEED",
            }
            for e in ds.employees
        ],
        "salaries",
    )
    await bulk(
        session,
        User,
        [
            {
                "employee_id": emp_ids[e.index],
                "username": e.tally_id,
                "credential_hash": user_hash,
                "role": e.role,
                "is_active": True,
                "must_change_password": False,
                "failed_attempts": 0,
            }
            for e in ds.employees
            if e.role != "WORKER"
        ],
        "supervisor and engineer users",
    )
    device_ids = {e.index: uuid4() for e in ds.workers}
    now = datetime.now(UTC)
    await bulk(
        session,
        RegisteredDevice,
        [
            {
                "id": device_ids[e.index],
                "employee_id": emp_ids[e.index],
                "device_identifier": f"PERF-{e.tally_id}",
                "platform": "ANDROID",
                "app_version": "perf",
                "registered_at": now,
                "last_seen_at": now,
                "last_acked_cursor": 0,
            }
            for e in ds.workers
        ],
        "devices",
    )
    await bulk(
        session,
        WorksiteSupervisor,
        [
            {"worksite_id": site_ids[site], "supervisor_id": emp_ids[sup]}
            for site, sups in ds.supervisors_by_site.items()
            for sup in sups
        ],
        "worksite supervisors",
    )
    return {
        "site_ids": site_ids,
        "item_ids": item_ids,
        "emp_ids": emp_ids,
        "device_ids": device_ids,
    }


async def seed_occurrences(session: Any, item_ids: list[UUID]) -> dict[UUID, list[tuple[date, date, UUID]]]:
    """The real generator, item by item, from the start of the history."""
    from sqlalchemy import select

    from fw.modules.jobs import JobsService
    from fw.modules.jobs.models import JobOccurrence

    started = wallclock.perf_counter()
    for n, item_id in enumerate(item_ids, start=1):
        await JobsService.generate_job_occurrences(session, item_id, from_date=HISTORY_START)
        if n % 100 == 0 or n == len(item_ids):
            await session.commit()
            log(f"  occurrences: {n:,}/{len(item_ids):,} items ({wallclock.perf_counter() - started:.0f} s)")
    rows = (
        await session.execute(
            select(JobOccurrence.job_item_id, JobOccurrence.window_start, JobOccurrence.window_end, JobOccurrence.id)
        )
    ).all()
    by_item: dict[UUID, list[tuple[date, date, UUID]]] = defaultdict(list)
    for item_id, start, end, occ_id in rows:
        by_item[item_id].append((start, end, occ_id))
    for windows in by_item.values():
        windows.sort()
    log(f"  occurrences: {len(rows):,} rows")
    return by_item


def occurrence_for(windows: list[tuple[date, date, UUID]], day: date) -> UUID | None:
    i = bisect.bisect_right(windows, (day, date.max, UUID(int=2**128 - 1))) - 1
    if i >= 0 and windows[i][0] <= day <= windows[i][1]:
        return windows[i][2]
    return None


async def seed_planning(
    session: Any,
    ds: Dataset,
    ids: dict[str, Any],
    occ: dict[UUID, list[tuple[date, date, UUID]]],
    schedule_to: date,
) -> list[dict[str, Any]]:
    from fw.modules.scheduling import BaseRosterEntry, BaseRosterTemplate
    from fw.modules.scheduling.models import ScheduledWork, StandingAssignment

    emp_ids, item_ids, site_ids = ids["emp_ids"], ids["item_ids"], ids["site_ids"]
    await bulk(
        session,
        StandingAssignment,
        [
            {
                "employee_id": emp_ids[a.employee_index],
                "job_item_id": item_ids[a.item_index],
                "start_date": HISTORY_START,
                "weekday_pattern": a.weekdays,
                "hours_per_day": a.hours,
            }
            for a in ds.assignments
        ],
        "standing assignments",
    )

    template_ids: dict[int, UUID] = {}
    templates: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    for a in ds.assignments:
        if a.item_index not in template_ids:
            template_ids[a.item_index] = uuid4()
            templates.append(
                {
                    "id": template_ids[a.item_index],
                    "job_item_id": item_ids[a.item_index],
                    "allocation_mode": "DAY_OF_WEEK",
                    "start_date": HISTORY_START,
                }
            )
        for day in a.weekdays:
            entries.append(
                {
                    "template_id": template_ids[a.item_index],
                    "employee_id": emp_ids[a.employee_index],
                    "weekday_mask": day,
                    "assigned_hours": a.hours,
                    "sequence": 1,
                }
            )
    await bulk(session, BaseRosterTemplate, templates, "base roster templates")
    await bulk(session, BaseRosterEntry, entries, "base roster entries")

    work: list[dict[str, Any]] = []
    for a in ds.assignments:
        item = ds.items[a.item_index]
        for day in work_dates(a.weekdays, HISTORY_START, schedule_to):
            work.append(
                {
                    "id": uuid4(),
                    "employee_id": emp_ids[a.employee_index],
                    "work_date": day,
                    "occurrence_id": occurrence_for(occ.get(item_ids[a.item_index], []), day),
                    "job_item_id": item_ids[a.item_index],
                    "worksite_id": site_ids[item.site_index],
                    "assigned_hours": a.hours,
                    "sequence": 1,
                    "status": "CANCELLED" if on_leave(ds, a.employee_index, day) else "ACTIVE",
                    "source": "STANDING",
                    "is_late_approval": False,
                    "is_weekly_off_cover": False,
                    "_employee_index": a.employee_index,
                    "_site_index": item.site_index,
                }
            )
    await bulk(
        session,
        ScheduledWork,
        [{k: v for k, v in w.items() if not k.startswith("_")} for w in work],
        "scheduled work",
    )
    return work


async def seed_leave(session: Any, ds: Dataset, ids: dict[str, Any], admin_id: UUID) -> None:
    from fw.modules.scheduling.models import LeaveRequest

    now = datetime.now(UTC)
    await bulk(
        session,
        LeaveRequest,
        [
            {
                "employee_id": ids["emp_ids"][w],
                "leave_type": "ANNUAL",
                "from_date": first,
                "to_date": first + timedelta(days=6),
                "status": "APPROVED",
                "reason": "Perf mock leave",
                "recorded_by_user_id": admin_id,
                "approved_by_user_id": admin_id,
                "approved_at": now,
            }
            for w, first in sorted(ds.leave_weeks.items())
        ],
        "leave requests",
    )


def _schedule() -> Any:
    from fw.rules.time_rules import ResolvedTimeSchedule

    return ResolvedTimeSchedule(
        accommodation_start=None,
        first_site_start=time(7, 0),
        break_minutes=30,
        last_site_end=time(15, 30),
        accommodation_end=None,
        planned_total_minutes=510,
        planned_worked_minutes=480,
        standard_hours_change_minutes=0,
        has_accommodation=False,
        winning_rule_id=None,
        winning_rule_name="Perf standard day",
    )


def _event(
    ev_id: UUID,
    emp: UUID,
    device: UUID,
    site: UUID,
    item: UUID,
    kind: str,
    at: datetime,
    lon: float,
    lat: float,
    seq: int,
) -> dict[str, Any]:
    return {
        "event_id": ev_id,
        "employee_id": emp,
        "device_id": device,
        "job_id": site,
        "job_item_id": item,
        "event_type": kind,
        "event_timestamp_utc": at,
        "location_captured_at_utc": at,
        "latitude": Decimal(f"{lat:.6f}"),
        "longitude": Decimal(f"{lon:.6f}"),
        "geom": point(lon, lat),
        "accuracy_meters": 8.0,
        "is_mock_location": False,
        "sequence_number": seq,
        "server_received_at": at + timedelta(seconds=20),
        "is_processed": True,
        "processing_status": "ACCEPTED",
        "server_site_id": site,
        "server_verdict": "INSIDE",
        "distance_to_polygon_m": 0.0,
        "flags": [],
    }


async def seed_activity(
    session: Any,
    ds: Dataset,
    ids: dict[str, Any],
    work: list[dict[str, Any]],
    rng: random.Random,
    attendance_to: date,
    event_days: int,
    pending_max: int,
) -> None:
    from sqlalchemy import text

    from fw.modules.attendance.models import AttendanceCalculation, AttendanceRecord, PendingVisit, SiteVisit
    from fw.modules.events.models import EmployeeLastPosition, MobileEventLog
    from fw.rules.attendance.engine import DailyCalculationInputs, ScheduledAssignment, compute_daily_attendance
    from fw.rules.attendance.visits import ConstructedVisit

    schedule = _schedule()
    now = datetime.now(UTC)
    ping_from = attendance_to - timedelta(days=event_days - 1)
    events: list[dict[str, Any]] = []
    visits: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    calcs: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    last_event: dict[UUID, dict[str, Any]] = {}
    events_written = 0

    async def flush_events(force: bool = False) -> None:
        # Events go in as they are built, so the full dataset never sits in memory.
        nonlocal events_written
        if events and (force or len(events) >= 4 * CHUNK):
            await bulk(session, MobileEventLog, events, None)
            events_written += len(events)
            events.clear()

    past = [w for w in work if w["status"] == "ACTIVE" and w["work_date"] <= attendance_to]
    past.sort(key=lambda w: (w["work_date"], w["_employee_index"]))
    today = datetime.now(TZ["AE"]).date()
    todays = [w for w in work if w["status"] == "ACTIVE" and w["work_date"] == today]

    for w in past:
        emp_i, site_i = w["_employee_index"], w["_site_index"]
        emp, site_id, day = w["employee_id"], w["worksite_id"], w["work_date"]
        device = ids["device_ids"][emp_i]
        site = ds.sites[site_i]
        tz = TZ[site.country]
        record_id, calc_id = uuid4(), uuid4()
        assignment = ScheduledAssignment(scheduled_work_id=w["id"], worksite_id=site_id, assigned_hours=8.0)
        constructed: list[Any] = []
        source_ids: list[UUID] = []
        if rng.random() >= ds.scale.absent_rate:
            entry = datetime.combine(day, time(7, 0), tz) + timedelta(minutes=rng.randint(-10, 20))
            leave = datetime.combine(day, time(15, 30), tz) + timedelta(minutes=rng.randint(-20, 15))
            entry_at, exit_at = entry.astimezone(UTC), leave.astimezone(UTC)
            entry_id, exit_id = uuid4(), uuid4()
            source_ids = [entry_id, exit_id]
            events.append(
                _event(entry_id, emp, device, site_id, w["job_item_id"], "ENTRY", entry_at, site.lon, site.lat, 1)
            )
            seq = 2
            if day >= ping_from:
                t = entry_at + timedelta(minutes=PING_MINUTES)
                while t < exit_at:
                    jlon = site.lon + rng.uniform(-0.0003, 0.0003)
                    jlat = site.lat + rng.uniform(-0.0003, 0.0003)
                    events.append(_event(uuid4(), emp, device, site_id, w["job_item_id"], "PING", t, jlon, jlat, seq))
                    seq += 1
                    t += timedelta(minutes=PING_MINUTES)
            exit_event = _event(
                exit_id, emp, device, site_id, w["job_item_id"], "EXIT", exit_at, site.lon, site.lat, seq
            )
            events.append(exit_event)
            last_event[emp] = exit_event
            await flush_events()
            minutes = int((exit_at - entry_at).total_seconds() // 60)
            v = ConstructedVisit(
                work_date=day,
                place_type="SITE",
                worksite_id=site_id,
                accommodation_id=None,
                entry_event_id=entry_id,
                exit_event_id=exit_id,
                entry_at=entry_at,
                exit_at=exit_at,
                exit_inferred=False,
                last_inside_at=exit_at,
                counts_as_completed=True,
                duration_minutes=minutes,
            )
            constructed.append(v)
            visits.append(
                {
                    "employee_id": emp,
                    "work_date": day,
                    "place_type": "SITE",
                    "worksite_id": site_id,
                    "entry_event_id": entry_id,
                    "exit_event_id": exit_id,
                    "entry_at": entry_at,
                    "exit_at": exit_at,
                    "exit_inferred": False,
                    "last_inside_at": exit_at,
                    "counts_as_completed": True,
                    "duration_minutes": minutes,
                    "flags": [],
                }
            )
        elif len(pending) < pending_max:
            pending.append(
                {
                    "scheduled_work_id": w["id"],
                    "occurrence_id": w["occurrence_id"],
                    "worksite_id": site_id,
                    "employee_id": emp,
                    "due_date": day,
                    "detected_on": day + timedelta(days=1),
                    "status": "OPEN",
                }
            )

        result = compute_daily_attendance(
            DailyCalculationInputs(
                employee_id=emp,
                tally_id=ds.employees[emp_i].tally_id,
                work_date=day,
                is_driver=False,
                has_accommodation=False,
                standard_hours=8.0,
                schedule=schedule,
                assignments=[assignment],
                visits=constructed,
                gaps=[],
                is_public_holiday=False,
                is_weekly_off=False,
            )
        )
        records.append(
            {
                "id": record_id,
                "employee_id": emp,
                "work_date": day,
                "current_calculation_id": None,
                "business_status": result.business_status,
                "review_status": result.review_status,
                "locked": False,
            }
        )
        calcs.append(
            {
                "id": calc_id,
                "attendance_record_id": record_id,
                "version_no": 1,
                "input_hash": result.input_hash,
                "calculated_at": now,
                "engine_version": "perf-seed",
                "reason": "PERF_SEED",
                **{
                    k: getattr(result, k)
                    for k in (
                        "planned_accommodation_departure",
                        "planned_first_site_start",
                        "planned_break_minutes",
                        "planned_last_site_end",
                        "planned_accommodation_return",
                        "planned_total_minutes",
                        "planned_worked_minutes",
                        "standard_hours_minutes",
                        "accommodation_departure_at",
                        "first_site_entry_at",
                        "break_minutes_used",
                        "break_source",
                        "last_site_exit_at",
                        "accommodation_return_at",
                        "elapsed_site_minutes",
                        "shift_span_minutes",
                        "unaccounted_minutes",
                        "worked_minutes",
                        "required_minutes",
                        "variation_minutes",
                        "shortfall_minutes",
                        "grace_minutes",
                        "grace_applied",
                        "satisfied",
                        "productive_minutes",
                        "transit_minutes",
                        "offsite_minutes",
                        "idle_minutes",
                        "ot1_minutes",
                        "ot2_minutes",
                        "ot_threshold_minutes",
                        "day_type",
                        "assigned_count",
                        "completed_count",
                        "business_status",
                        "flags",
                        "review_reasons",
                    )
                },
                "visits_snapshot": [
                    {
                        "place_type": v.place_type,
                        "worksite_id": str(v.worksite_id),
                        "accommodation_id": None,
                        "entry_at": v.entry_at.isoformat(),
                        "exit_at": v.exit_at.isoformat() if v.exit_at else None,
                        "exit_inferred": False,
                        "duration_minutes": v.duration_minutes,
                        "counts_as_completed": True,
                        "flags": [],
                    }
                    for v in constructed
                ],
                "gaps_snapshot": [],
                "inputs_snapshot": {
                    "standard_hours": 8.0,
                    "required_minutes": result.required_minutes,
                    "assigned_count": result.assigned_count,
                    "is_driver": False,
                    "has_accommodation": False,
                    "break_minutes_used": result.break_minutes_used,
                    "break_source": result.break_source,
                },
                "source_event_ids": source_ids,
            }
        )

    # Today: in the field since about 07:00 site time, pinging until now (the live map).
    for w in todays:
        emp_i, site_i = w["_employee_index"], w["_site_index"]
        emp, site_id = w["employee_id"], w["worksite_id"]
        device = ids["device_ids"][emp_i]
        site = ds.sites[site_i]
        start = datetime.combine(today, time(7, 0), TZ[site.country]).astimezone(UTC)
        start += timedelta(minutes=rng.randint(-10, 20))
        if start >= now:
            continue
        ev = _event(uuid4(), emp, device, site_id, w["job_item_id"], "ENTRY", start, site.lon, site.lat, 1)
        events.append(ev)
        seq, t = 2, start + timedelta(minutes=PING_MINUTES)
        while t < now and t < start + timedelta(hours=8, minutes=30):
            ev = _event(
                uuid4(),
                emp,
                device,
                site_id,
                w["job_item_id"],
                "PING",
                t,
                site.lon + rng.uniform(-0.0003, 0.0003),
                site.lat + rng.uniform(-0.0003, 0.0003),
                seq,
            )
            events.append(ev)
            seq += 1
            t += timedelta(minutes=PING_MINUTES)
        last_event[emp] = ev
        await flush_events()

    await flush_events(force=True)
    log(f"  phone events: {events_written:,}")
    await bulk(session, SiteVisit, visits, "site visits")
    await bulk(session, AttendanceRecord, records, "attendance records")
    await bulk(session, AttendanceCalculation, calcs, "attendance calculations")
    await session.execute(
        text(
            "UPDATE attendance_records r SET current_calculation_id = c.id "
            "FROM attendance_calculations c "
            "WHERE c.attendance_record_id = r.id AND r.current_calculation_id IS NULL"
        )
    )
    await session.commit()
    await bulk(session, PendingVisit, pending, "pending visits")
    await bulk(
        session,
        EmployeeLastPosition,
        [
            {
                "employee_id": emp,
                "last_event_id": ev["event_id"],
                "event_type": ev["event_type"],
                "latitude": ev["latitude"],
                "longitude": ev["longitude"],
                "accuracy_meters": ev["accuracy_meters"],
                "event_timestamp_utc": ev["event_timestamp_utc"],
                "received_at_utc": ev["server_received_at"],
                "server_verdict": "INSIDE",
                "server_site_id": ev["server_site_id"],
                "tracking_enabled": True,
                "last_contact_at": ev["server_received_at"],
            }
            for emp, ev in last_event.items()
        ],
        "last positions",
    )


async def seed_payroll(session: Any, admin_id: UUID) -> None:
    """The real October draft (AE); its PayrollRunCreated listener writes the month-end reports."""
    from fw.modules.payroll import PayrollService
    from fw.modules.payroll.schemas import PayrollRunCreate

    started = wallclock.perf_counter()
    try:
        await PayrollService.generate_draft_run(
            session,
            PayrollRunCreate(period_start=date(2026, 10, 1), period_end=date(2026, 10, 31), country="AE"),
            user_id=admin_id,
            actor_role="ADMIN",
        )
        await session.commit()
        log(f"  payroll draft October AE ({wallclock.perf_counter() - started:.0f} s)")
    except Exception as exc:  # report it and keep the rest of the dataset
        await session.rollback()
        log(f"  payroll draft FAILED: {type(exc).__name__}: {exc}")


async def print_counts(session: Any) -> dict[str, int]:
    from sqlalchemy import text

    tables = (
        "groups zones worksites job_items job_occurrences employees employee_salary users "
        "registered_devices worksite_supervisors standing_assignments base_roster_templates "
        "base_roster_entries scheduled_work leave_requests mobile_event_logs site_visits "
        "attendance_records attendance_calculations pending_visits employee_last_position "
        "payroll_runs payroll_records generated_reports"
    ).split()
    counts: dict[str, int] = {}
    for t in tables:
        counts[t] = int((await session.execute(text(f"SELECT count(*) FROM {t}"))).scalar() or 0)
    width = max(len(t) for t in tables)
    for t in tables:
        print(f"  {t:<{width}}  {counts[t]:>10,}")
    return counts


async def run(args: argparse.Namespace) -> None:
    if args.recreate:
        log(f"Recreating {perf_db.PERF_DATABASE} (drop, create, migrate)")
        await perf_db.recreate_perf_database()

    from sqlalchemy import func, select

    import fw.main  # noqa: F401  # every model mapped and the app's event listeners registered
    from fw.core.clock import site_today
    from fw.core.db import async_session_factory, engine
    from fw.modules.identity import hash_password
    from fw.modules.jobs import Worksite

    scale = Scale() if args.scale == 1 else Scale().scaled(args.scale)
    ds = build_dataset(scale, seed=args.seed, history_start=HISTORY_START)
    rng = random.Random(args.seed + 1)
    today = site_today()
    attendance_to = today - timedelta(days=1)
    schedule_to = args.schedule_to or (today + timedelta(days=13 * 31))
    password = os.environ.get(ADMIN_PASSWORD_ENV, DEFAULT_ADMIN_PASSWORD)
    log(
        f"Dataset: {len(ds.employees)} employees ({len(ds.workers)} workers), {len(ds.sites)} worksites, "
        f"{len(ds.items)} job items; history from {HISTORY_START}, attendance to {attendance_to}, "
        f"scheduled work to {schedule_to}"
    )
    started = wallclock.perf_counter()
    async with async_session_factory() as session:
        if (await session.execute(select(func.count()).select_from(Worksite))).scalar():
            sys.exit(f"{perf_db.PERF_DATABASE} already has worksites; run with --recreate.")
        log("Base: lookups, salary revisions, admin")
        admin_id = await seed_base(session, password)
        log("Master data")
        ids = await seed_master(session, ds, hash_password(password))
        log("Occurrences (JobsService.generate_job_occurrences)")
        occ = await seed_occurrences(session, ids["item_ids"])
        log("Planning")
        work = await seed_planning(session, ds, ids, occ, schedule_to)
        await seed_leave(session, ds, ids, admin_id)
        log("Activity: phone events, site visits, attendance (pure engine)")
        await seed_activity(session, ds, ids, work, rng, attendance_to, args.event_days, args.pending_max)
        if not args.skip_payroll:
            log("Payroll (PayrollService.generate_draft_run)")
            await seed_payroll(session, admin_id)
        log(f"Done in {wallclock.perf_counter() - started:.0f} s. Row counts:")
        await print_counts(session)
    await engine.dispose()
    print(
        f"\nLogin: {ADMIN_USERNAME} (password from {ADMIN_PASSWORD_ENV}, "
        f"else the local default in this script). Supervisors/engineers log in with their Tally ID "
        "and the same password."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--recreate", action="store_true", help="drop, create and migrate fw_perf first")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scale", type=float, default=1.0, help="e.g. 0.05 for a quick small run")
    parser.add_argument("--event-days", type=int, default=7, help="days of 5-minute pings before today")
    parser.add_argument("--pending-max", type=int, default=400)
    parser.add_argument(
        "--schedule-to",
        type=date.fromisoformat,
        default=None,
        help="last scheduled work date (default: today + 13 months, like standing assignments)",
    )
    parser.add_argument("--skip-payroll", action="store_true")
    args = parser.parse_args()
    perf_db.point_at_perf_database()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
