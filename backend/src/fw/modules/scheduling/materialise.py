"""Base Planner templates become scheduled work (owner decision 25 Nov 2026; ADR-032).

The Base Planner saves recurring templates: a job item and its workers by weekday. Attendance,
pending visits, payroll and the phones all work from ``scheduled_work`` rows, so a plan made only
in the Base Planner used to produce no attendance requirement at all. The materialiser keeps a
rolling window filled, from tomorrow to ``roster_materialise_weeks`` ahead (default 4). It runs
from a daily job and whenever a template is saved or a leave decision changes a worker's days.
The rows it creates have ``source = TEMPLATE``.

The Operational Planner's own rules apply (``validate_assignment``):
- at most one row per employee, job item and date. If any row exists for that key (any source,
  any status), the slot is already planned or was changed by hand, and nothing is created;
- weekly off days and days of approved leave are skipped (leave gets its cover the usual way);
- template, job item and worksite (contract) dates apply. Inactive employees, items and
  worksites, budget-only staff types and PERMANENT clashes are skipped and logged;
- public holidays are scheduled as normal (the worked hours become OT2);
- more hours than the worker's standard day is logged as a warning, never blocking.

Only *untouched* template rows are ever changed: ``source = TEMPLATE``, ``status = ACTIVE`` and
``version = 1``. Every edit in the Operational Planner, a cover or a reassignment changes the
status or bumps the version, so manual changes survive a template change. From tomorrow onwards,
untouched rows the templates no longer produce are deleted (the phones get a DELETE), and changed
hours are updated in place.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy import and_, delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fw.core.clock import site_today
from fw.core.events import ScheduledWorkChanged, ScheduledWorkRemoved, event_bus
from fw.modules.jobs import JobItem, Worksite
from fw.modules.org import Employee
from fw.modules.scheduling.models import (
    BaseRosterEntry,
    BaseRosterTemplate,
    LeaveRequest,
    ScheduledWork,
)
from fw.modules.settings import SettingsService
from fw.rules.scheduling import (
    EmployeeValidationContext,
    ExistingAssignmentContext,
    IssueSeverity,
    JobItemValidationContext,
    ValidationCode,
    validate_assignment,
)
from fw.rules.scheduling.blueprint import INT_TO_WEEKDAY, is_entry_matching_date, is_same_weekday

logger = structlog.get_logger(__name__)

TEMPLATE_SOURCE = "TEMPLATE"
MATERIALISE_WEEKS_SETTING = "roster_materialise_weeks"
MATERIALISE_WEEKS_DEFAULT = 4
MATERIALISE_WEEKS_MAX = 26
# Serialises materialiser runs (the nightly job and a template save at the same moment would
# otherwise both pick the same free sequence number).
_ADVISORY_LOCK_KEY = 7_302_026


def untouched_template_condition() -> Any:
    """SQL condition for rows the materialiser may still change or delete."""
    return and_(
        ScheduledWork.source == TEMPLATE_SOURCE,
        ScheduledWork.status == "ACTIVE",
        ScheduledWork.version == 1,
    )


def is_untouched_template(row: ScheduledWork) -> bool:
    return row.source == TEMPLATE_SOURCE and row.status == "ACTIVE" and (row.version or 1) == 1


@dataclass
class MaterialiseSummary:
    """What one run did. ``skipped`` counts slots by reason (validation code or WEEKLY_OFF)."""

    weeks: int = MATERIALISE_WEEKS_DEFAULT
    window_from: date | None = None
    window_to: date | None = None
    created: int = 0
    updated: int = 0
    removed: int = 0
    kept_manual: int = 0
    warnings: int = 0
    skipped: dict[str, int] = field(default_factory=dict)
    employee_ids: set[UUID] = field(default_factory=set)

    def skip(self, reason: str) -> None:
        self.skipped[reason] = self.skipped.get(reason, 0) + 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "weeks": self.weeks,
            "window_from": self.window_from.isoformat() if self.window_from else None,
            "window_to": self.window_to.isoformat() if self.window_to else None,
            "created": self.created,
            "updated": self.updated,
            "removed": self.removed,
            "kept_manual": self.kept_manual,
            "warnings": self.warnings,
            "skipped": dict(sorted(self.skipped.items())),
        }


async def materialise_weeks(session: AsyncSession) -> int:
    """The ``roster_materialise_weeks`` setting, kept between 1 and 26."""
    raw = await SettingsService.get_setting(
        session, MATERIALISE_WEEKS_SETTING, default=MATERIALISE_WEEKS_DEFAULT
    )
    try:
        weeks = int(raw)
    except (TypeError, ValueError):
        weeks = MATERIALISE_WEEKS_DEFAULT
    return max(1, min(weeks, MATERIALISE_WEEKS_MAX))


Key = tuple[UUID, UUID, date]  # employee, job item, date


class RosterMaterialiser:
    """Keeps TEMPLATE scheduled work in step with the active Base Planner templates."""

    @staticmethod
    async def run(
        session: AsyncSession,
        *,
        job_item_ids: Collection[UUID] | None = None,
        employee_ids: Collection[UUID] | None = None,
        today: date | None = None,
    ) -> MaterialiseSummary:
        """Fill the window for the given job items or employees (both None: everything).

        ``today`` overrides each worksite country's own date (tests and the demo generator).
        The caller commits; phone sync changes are written in the same transaction.
        """
        from fw.modules.scheduling.service import SchedulingService  # avoids an import cycle

        await session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": _ADVISORY_LOCK_KEY}
        )
        weeks = await materialise_weeks(session)
        summary = MaterialiseSummary(weeks=weeks)
        today_cache: dict[str, date] = {}

        def window_for(country: str | None) -> tuple[date, date]:
            c = (country or "AE").upper()
            if c not in today_cache:
                today_cache[c] = today or site_today(c)
            t = today_cache[c]
            return t + timedelta(days=1), t + timedelta(days=7 * weeks)

        emp_filter = set(employee_ids) if employee_ids is not None else None
        item_filter = set(job_item_ids) if job_item_ids is not None else None

        # 1. Active templates in scope, with their items and worksites.
        tmpl_stmt = (
            select(BaseRosterTemplate)
            .where(BaseRosterTemplate.is_active.is_(True))
            .options(selectinload(BaseRosterTemplate.entries))
        )
        if item_filter is not None:
            tmpl_stmt = tmpl_stmt.where(BaseRosterTemplate.job_item_id.in_(item_filter))
        if emp_filter is not None:
            tmpl_stmt = tmpl_stmt.where(
                BaseRosterTemplate.id.in_(
                    select(BaseRosterEntry.template_id).where(
                        BaseRosterEntry.employee_id.in_(emp_filter)
                    )
                )
            )
        templates = list((await session.execute(tmpl_stmt)).scalars().all())

        items: dict[UUID, tuple[JobItem, Worksite]] = {}
        if templates:
            rows = (
                await session.execute(
                    select(JobItem, Worksite)
                    .join(Worksite, Worksite.id == JobItem.worksite_id)
                    .where(JobItem.id.in_({t.job_item_id for t in templates}))
                )
            ).all()
            items = {ji.id: (ji, ws) for ji, ws in rows}

        # 2. Untouched template rows from (about) tomorrow onwards in scope: update or delete.
        base_today = today or site_today()
        rm_stmt = (
            select(ScheduledWork, Worksite.country)
            .join(Worksite, Worksite.id == ScheduledWork.worksite_id)
            .where(untouched_template_condition(), ScheduledWork.work_date >= base_today)
        )
        if item_filter is not None:
            rm_stmt = rm_stmt.where(ScheduledWork.job_item_id.in_(item_filter))
        if emp_filter is not None:
            rm_stmt = rm_stmt.where(ScheduledWork.employee_id.in_(emp_filter))
        removal_candidates = [
            sw
            for sw, country in (await session.execute(rm_stmt)).all()
            if sw.work_date >= window_for(country)[0]
        ]

        # 3. Employees, their existing rows, leave and standard hours.
        entry_emp_ids = {
            e.employee_id
            for t in templates
            for e in t.entries
            if emp_filter is None or e.employee_id in emp_filter
        }
        all_emp_ids = entry_emp_ids | {sw.employee_id for sw in removal_candidates}
        employees: dict[UUID, Employee] = {}
        if all_emp_ids:
            employees = {
                e.id: e
                for e in (
                    await session.execute(select(Employee).where(Employee.id.in_(all_emp_ids)))
                )
                .scalars()
                .all()
            }

        windows = [window_for(ws.country) for _, ws in items.values()]
        lo = min((w[0] for w in windows), default=base_today + timedelta(days=1))
        hi = max((w[1] for w in windows), default=base_today + timedelta(days=7 * weeks))
        summary.window_from, summary.window_to = lo, hi

        existing_by_key: dict[Key, list[ScheduledWork]] = defaultdict(list)
        active_by_emp_day: dict[tuple[UUID, date], list[ScheduledWork]] = defaultdict(list)
        deployment_by_item: dict[UUID, str] = {}
        leave_days: set[tuple[UUID, date]] = set()
        if entry_emp_ids:
            existing = (
                await session.execute(
                    select(ScheduledWork, JobItem.deployment_type)
                    .join(JobItem, JobItem.id == ScheduledWork.job_item_id)
                    .where(
                        ScheduledWork.employee_id.in_(entry_emp_ids),
                        ScheduledWork.work_date >= lo,
                        ScheduledWork.work_date <= hi,
                    )
                )
            ).all()
            for sw, deployment in existing:
                existing_by_key[(sw.employee_id, sw.job_item_id, sw.work_date)].append(sw)
                deployment_by_item[sw.job_item_id] = deployment or "REMOTE"
                if sw.status == "ACTIVE":
                    active_by_emp_day[(sw.employee_id, sw.work_date)].append(sw)

            leaves = (
                await session.execute(
                    select(LeaveRequest).where(
                        LeaveRequest.employee_id.in_(entry_emp_ids),
                        LeaveRequest.status == "APPROVED",
                        LeaveRequest.is_active.is_(True),
                        LeaveRequest.from_date <= hi,
                        LeaveRequest.to_date >= lo,
                    )
                )
            ).scalars()
            for lv in leaves:
                d = max(lv.from_date, lo)
                while d <= min(lv.to_date, hi):
                    leave_days.add((lv.employee_id, d))
                    d += timedelta(days=1)

        helper = SchedulingService(session)
        budget_types = await helper.budget_only_types_by_country(
            {ws.country for _, ws in items.values()}
        )
        standard_hours = await helper.get_employees_base_standard_hours(list(entry_emp_ids), lo)

        # 4. The slots the templates ask for, validated like the Operational Planner does.
        desired: dict[Key, Decimal] = {}
        new_by_emp_day: dict[tuple[UUID, date], list[ExistingAssignmentContext]] = defaultdict(list)
        ordered = sorted(
            (t for t in templates if t.job_item_id in items),
            key=lambda t: (
                items[t.job_item_id][1].job_number,
                items[t.job_item_id][0].sub_item_code,
            ),
        )
        for tmpl in ordered:
            item, ws = items[tmpl.job_item_id]
            w_from, w_to = window_for(ws.country)
            start = max(d for d in (w_from, tmpl.start_date, item.start_date, ws.start_date) if d)
            end = min(d for d in (w_to, tmpl.end_date, item.end_date, ws.end_date) if d)
            if start > end:
                continue
            job_ctx = JobItemValidationContext(
                job_item_id=str(item.id),
                worksite_id=str(ws.id),
                is_active=item.is_active,
                worksite_is_active=ws.is_active,
                deployment_type=item.deployment_type or "REMOTE",
                planned_grade_code=item.planned_grade_code or "",
                staff_grade_description=item.staff_grade_description or "",
                has_boundary=ws.boundary is not None,
                start_date=item.start_date,
                end_date=item.end_date,
                is_budget_only=(item.staff_grade_description or "").strip().lower()
                in budget_types.get(ws.country, set()),
            )
            entries = sorted(tmpl.entries, key=lambda e: (e.sequence, e.weekday_mask))
            day = start
            while day <= end:
                dow = INT_TO_WEEKDAY[day.weekday()]
                for entry in entries:
                    if emp_filter is not None and entry.employee_id not in emp_filter:
                        continue
                    if not is_entry_matching_date(entry.weekday_mask, day):
                        continue
                    key: Key = (entry.employee_id, item.id, day)
                    if key in desired:
                        continue
                    emp = employees.get(entry.employee_id)
                    if emp is None:
                        summary.skip("EMPLOYEE_NOT_FOUND")
                        continue
                    found = existing_by_key.get(key, [])
                    own = next((r for r in found if is_untouched_template(r)), None)
                    if found and own is None:
                        # Planned or changed in the Operational Planner, a cover or a
                        # reassignment: never overwritten.
                        summary.kept_manual += 1
                        continue
                    if is_same_weekday(emp.weekly_off_day, dow):
                        summary.skip("WEEKLY_OFF")
                        continue
                    others = [
                        ExistingAssignmentContext(
                            scheduled_work_id=str(r.id),
                            job_item_id=str(r.job_item_id),
                            worksite_id=str(r.worksite_id),
                            occurrence_id=None,
                            deployment_type=deployment_by_item.get(r.job_item_id, "REMOTE"),
                            assigned_hours=r.assigned_hours,
                            sequence=r.sequence,
                        )
                        for r in active_by_emp_day.get((emp.id, day), [])
                        if own is None or r.id != own.id
                    ] + new_by_emp_day[(emp.id, day)]
                    sequence = (
                        own.sequence if own else max((o.sequence for o in others), default=0) + 1
                    )
                    hours = Decimal(str(entry.assigned_hours))
                    report = validate_assignment(
                        employee=EmployeeValidationContext(
                            employee_id=str(emp.id),
                            is_active=emp.is_active,
                            join_date=emp.join_date,
                            employment_end_date=emp.employment_end_date,
                            weekly_off_day=emp.weekly_off_day,
                            grade_code=emp.grade_code,
                            staff_grade_description=emp.staff_grade_description,
                            standard_hours=standard_hours.get(emp.id, Decimal("8.0")),
                        ),
                        job_item=job_ctx,
                        target_date=day,
                        assigned_hours=hours,
                        target_sequence=sequence,
                        existing_assignments=others,
                        today=w_from - timedelta(days=1),
                        is_admin=True,
                        is_on_leave=(emp.id, day) in leave_days,
                    )
                    errors = [i for i in report.issues if i.severity == IssueSeverity.ERROR]
                    if errors:
                        summary.skip(errors[0].code.value)
                        continue
                    if any(i.code == ValidationCode.OVER_STANDARD_HOURS for i in report.issues):
                        summary.warnings += 1
                        logger.warning(
                            "roster_materialise_over_standard_hours",
                            employee_id=str(emp.id),
                            job_item_id=str(item.id),
                            work_date=day.isoformat(),
                            message=next(
                                i.message
                                for i in report.issues
                                if i.code == ValidationCode.OVER_STANDARD_HOURS
                            ),
                        )
                    desired[key] = hours
                    new_by_emp_day[(emp.id, day)].append(
                        ExistingAssignmentContext(
                            scheduled_work_id=str(own.id) if own else f"new-{uuid4()}",
                            job_item_id=str(item.id),
                            worksite_id=str(ws.id),
                            occurrence_id=None,
                            deployment_type=item.deployment_type or "REMOTE",
                            assigned_hours=hours,
                            sequence=sequence,
                        )
                    )
                day += timedelta(days=1)

        # 5. Apply: create, update hours, delete what the templates no longer produce.
        now = datetime.now(UTC)
        changed_ids: list[UUID] = []
        changed_emps: set[UUID] = set()
        used_sequences: dict[tuple[UUID, date], set[int]] = defaultdict(set)
        for (emp_id, day), rows in active_by_emp_day.items():
            used_sequences[(emp_id, day)] = {r.sequence for r in rows}
        for (emp_id, item_id, day), hours in desired.items():
            own = next(
                (
                    r
                    for r in existing_by_key.get((emp_id, item_id, day), [])
                    if is_untouched_template(r)
                ),
                None,
            )
            if own is not None:
                if Decimal(str(own.assigned_hours)) != hours:
                    own.assigned_hours = hours
                    own.updated_at = now
                    summary.updated += 1
                    changed_ids.append(own.id)
                    changed_emps.add(emp_id)
                continue
            seqs = used_sequences[(emp_id, day)]
            sequence = max(seqs, default=0) + 1
            seqs.add(sequence)
            row = ScheduledWork(
                id=uuid4(),
                employee_id=emp_id,
                job_item_id=item_id,
                worksite_id=items[item_id][1].id,
                work_date=day,
                assigned_hours=hours,
                sequence=sequence,
                status="ACTIVE",
                source=TEMPLATE_SOURCE,
                version=1,
            )
            session.add(row)
            summary.created += 1
            changed_ids.append(row.id)
            changed_emps.add(emp_id)

        removed = [
            sw
            for sw in removal_candidates
            if (sw.employee_id, sw.job_item_id, sw.work_date) not in desired
        ]
        if removed:
            await session.execute(
                delete(ScheduledWork).where(ScheduledWork.id.in_([sw.id for sw in removed]))
            )
            summary.removed = len(removed)
        await session.flush()

        if removed:
            await event_bus.publish(
                ScheduledWorkRemoved(
                    items=[(sw.employee_id, sw.id, sw.version or 1) for sw in removed]
                ),
                session=session,
            )
        if changed_ids:
            await event_bus.publish(
                ScheduledWorkChanged(
                    employee_ids=sorted(changed_emps), scheduled_work_ids=changed_ids
                ),
                session=session,
            )
        summary.employee_ids = changed_emps | {sw.employee_id for sw in removed}
        if summary.created or summary.updated or summary.removed:
            logger.info("roster_materialised", **summary.as_dict())
        return summary
