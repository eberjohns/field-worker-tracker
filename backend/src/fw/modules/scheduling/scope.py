"""Worksite-based access scope (DEC-57) on top of the crew chain (DEC-10).

One place resolves what a user may see, so every list and record check applies the same
rule (`fw.rules.scope.employee_access`):

- Worksites: Admin all; a supervisor the worksites assigned to them; a superintendent or
  engineer the worksites assigned to supervisors in their reporting scope.
- Employees (DIRECTORY): crew + workers on my worksites (read-only).
- Leave and reassignment requests (REQUESTS): supervisors their own crew; superintendents
  and engineers their crew + workers on their worksites (read-only).
- Attendance, live map, pending visits, reports, dashboard (OPERATIONS): employee-days
  scheduled on my worksites ("site-days"), plus the whole crew for superintendents and
  engineers. A supervisor's crew working on another supervisor's site belongs to that
  site's supervisor.

Edits and approvals stay with the crew chain (``can_decide``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, and_, exists, false, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.clock import site_today
from fw.modules.identity import User
from fw.modules.jobs import JobItem, WorksiteSupervisor
from fw.modules.org import Employee, ScopeService
from fw.modules.scheduling.models import ScheduledWork, StandingAssignment
from fw.modules.settings import SettingsService
from fw.rules.scope import AccessLevel, ScopePurpose, employee_access, scope_supervisor_ids

# Scheduled work that places a worker on a site that day (cancelled/reassigned rows do not).
SITE_WORK_STATUSES = ("ACTIVE", "COMPLETED")
SITE_WORKER_WINDOW_SETTING = "scope_site_worker_window_days"
SITE_WORKER_WINDOW_DEFAULT_DAYS = 31


@dataclass
class AccessScope:
    """Resolved visibility for one user. Build it with ``AccessScope.resolve``."""

    role: str
    employee_id: UUID | None
    crew_ids: frozenset[UUID] = field(default_factory=frozenset)
    worksite_ids: frozenset[UUID] = field(default_factory=frozenset)
    _site_worker_cache: dict[date, frozenset[UUID]] = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------ resolve
    @classmethod
    async def resolve(cls, session: AsyncSession, user: User) -> AccessScope:
        role = (user.role or "").upper()
        if role == "ADMIN":
            return cls(role=role, employee_id=user.employee_id)
        crew = await ScopeService.get_scoped_employee_ids(session, user) or set()
        worksites: set[UUID] = set()
        if user.employee_id is not None and role in ("SUPERVISOR", "SUPERINTENDENT", "ENGINEER"):
            roles = {}
            if role != "SUPERVISOR" and crew:
                rows = await session.execute(
                    select(Employee.id, Employee.role).where(Employee.id.in_(crew))
                )
                roles = {str(eid): str(r or "") for eid, r in rows.all()}
            sup_ids = scope_supervisor_ids(
                str(user.employee_id), role, {str(c) for c in crew}, roles
            )
            if sup_ids:
                ws_rows = await session.execute(
                    select(WorksiteSupervisor.worksite_id).where(
                        WorksiteSupervisor.supervisor_id.in_([UUID(s) for s in sup_ids]),
                        WorksiteSupervisor.is_active.is_(True),
                    )
                )
                worksites = set(ws_rows.scalars().all())
        return cls(
            role=role,
            employee_id=user.employee_id,
            crew_ids=frozenset(crew),
            worksite_ids=frozenset(worksites),
        )

    @property
    def unrestricted(self) -> bool:
        return self.role == "ADMIN"

    # ---------------------------------------------------------------- worksites
    @property
    def worksite_filter(self) -> set[UUID] | None:
        """Worksite IDs to filter by, or None for no filter (Admin)."""
        return None if self.unrestricted else set(self.worksite_ids)

    def can_view_worksite(self, worksite_id: UUID) -> bool:
        return self.unrestricted or worksite_id in self.worksite_ids

    # ------------------------------------------------------------ crew decisions
    def can_decide(self, employee_id: UUID) -> bool:
        """Edits and approvals follow the crew chain (DEC-10). Role checks stay with callers."""
        return self.unrestricted or employee_id in self.crew_ids

    # ---------------------------------------------------- directory and requests
    async def site_worker_ids(self, session: AsyncSession, as_of: date | None = None) -> set[UUID]:
        """Workers on job items at my worksites: an active standing assignment on ``as_of``,
        or scheduled work within ± ``scope_site_worker_window_days`` of it."""
        if not self.worksite_ids:
            return set()
        day = as_of or site_today()
        if day in self._site_worker_cache:
            return set(self._site_worker_cache[day])
        window = await SettingsService.get_setting(
            session, SITE_WORKER_WINDOW_SETTING, default=SITE_WORKER_WINDOW_DEFAULT_DAYS
        )
        days = int(window if window is not None else SITE_WORKER_WINDOW_DEFAULT_DAYS)
        ws = list(self.worksite_ids)
        sa_rows = await session.execute(
            select(StandingAssignment.employee_id)
            .join(JobItem, StandingAssignment.job_item_id == JobItem.id)
            .where(
                JobItem.worksite_id.in_(ws),
                StandingAssignment.is_active.is_(True),
                StandingAssignment.start_date <= day,
                or_(StandingAssignment.end_date.is_(None), StandingAssignment.end_date >= day),
            )
        )
        sw_rows = await session.execute(
            select(ScheduledWork.employee_id).where(
                ScheduledWork.worksite_id.in_(ws),
                ScheduledWork.status.in_(SITE_WORK_STATUSES),
                ScheduledWork.work_date >= day - timedelta(days=days),
                ScheduledWork.work_date <= day + timedelta(days=days),
            )
        )
        result = set(sa_rows.scalars().all()) | set(sw_rows.scalars().all())
        self._site_worker_cache[day] = frozenset(result)
        return result

    async def _ids_for(self, session: AsyncSession, purpose: ScopePurpose) -> set[UUID] | None:
        if self.unrestricted:
            return None
        site_workers = await self.site_worker_ids(session)
        return {
            emp_id
            for emp_id in self.crew_ids | site_workers
            if employee_access(self.role, purpose, emp_id in self.crew_ids, emp_id in site_workers)
            is not None
        }

    async def directory_ids(self, session: AsyncSession) -> set[UUID] | None:
        """Employees list: crew + workers on my worksites. None = unrestricted."""
        return await self._ids_for(session, ScopePurpose.DIRECTORY)

    async def request_ids(self, session: AsyncSession) -> set[UUID] | None:
        """Leave/reassignment lists. None = unrestricted."""
        return await self._ids_for(session, ScopePurpose.REQUESTS)

    async def directory_access(
        self, session: AsyncSession, employee_id: UUID
    ) -> AccessLevel | None:
        on_site = employee_id in await self.site_worker_ids(session)
        return employee_access(
            self.role, ScopePurpose.DIRECTORY, employee_id in self.crew_ids, on_site
        )

    async def request_access(self, session: AsyncSession, employee_id: UUID) -> AccessLevel | None:
        on_site = employee_id in await self.site_worker_ids(session)
        return employee_access(
            self.role, ScopePurpose.REQUESTS, employee_id in self.crew_ids, on_site
        )

    # --------------------------------------------------------------- operations
    def _site_day_exists(self, employee_col: Any, date_col: Any) -> ColumnElement[bool]:
        if not self.worksite_ids:
            return false()
        return exists().where(
            ScheduledWork.employee_id == employee_col,
            ScheduledWork.work_date == date_col,
            ScheduledWork.worksite_id.in_(list(self.worksite_ids)),
            ScheduledWork.status.in_(SITE_WORK_STATUSES),
        )

    def operations_clause(self, employee_col: Any, date_col: Any) -> ColumnElement[bool] | None:
        """SQL filter for employee-day rows (site-day rule). None = no filter (Admin)."""
        if self.unrestricted:
            return None
        crew = list(self.crew_ids)
        if self.role == "SUPERVISOR":
            return self._site_day_exists(employee_col, date_col)
        if self.role in ("SUPERINTENDENT", "ENGINEER"):
            crew_clause = employee_col.in_(crew) if crew else false()
            return or_(crew_clause, self._site_day_exists(employee_col, date_col))
        return employee_col.in_(crew) if crew else false()

    def worksite_row_clause(
        self, employee_col: Any, worksite_col: Any
    ) -> ColumnElement[bool] | None:
        """SQL filter for rows that belong to one worksite (pending visits, scheduled work)."""
        if self.unrestricted:
            return None
        ws = list(self.worksite_ids)
        site_clause = worksite_col.in_(ws) if ws else false()
        if self.role == "SUPERVISOR":
            return site_clause
        crew = list(self.crew_ids)
        crew_clause = employee_col.in_(crew) if crew else false()
        if self.role in ("SUPERINTENDENT", "ENGINEER"):
            return or_(crew_clause, site_clause)
        return crew_clause

    async def operations_access(
        self, session: AsyncSession, employee_id: UUID, work_date: date
    ) -> AccessLevel | None:
        """Access to one employee-day (attendance record, trail, events)."""
        if self.unrestricted:
            return AccessLevel.FULL
        on_site = False
        if self.worksite_ids:
            on_site = bool(
                await session.scalar(
                    select(true()).where(
                        self._site_day_exists(employee_id, work_date)  # type: ignore[arg-type]
                    )
                )
            )
        return employee_access(
            self.role, ScopePurpose.OPERATIONS, employee_id in self.crew_ids, on_site
        )

    async def operations_ids_on(self, session: AsyncSession, day: date) -> set[UUID] | None:
        """Employees visible on operational views for one day (live map, dashboard)."""
        if self.unrestricted:
            return None
        on_site: set[UUID] = set()
        if self.worksite_ids:
            rows = await session.execute(
                select(ScheduledWork.employee_id).where(
                    ScheduledWork.work_date == day,
                    ScheduledWork.worksite_id.in_(list(self.worksite_ids)),
                    ScheduledWork.status.in_(SITE_WORK_STATUSES),
                )
            )
            on_site = set(rows.scalars().all())
        return {
            emp_id
            for emp_id in self.crew_ids | on_site
            if employee_access(
                self.role, ScopePurpose.OPERATIONS, emp_id in self.crew_ids, emp_id in on_site
            )
            is not None
        }

    async def site_days(
        self, session: AsyncSession, date_from: date, date_to: date, any_status: bool = False
    ) -> set[tuple[UUID, date]]:
        """(employee, date) pairs scheduled on my worksites in a period."""
        if not self.worksite_ids:
            return set()
        conds = [
            ScheduledWork.worksite_id.in_(list(self.worksite_ids)),
            ScheduledWork.work_date >= date_from,
            ScheduledWork.work_date <= date_to,
        ]
        if not any_status:
            conds.append(ScheduledWork.status.in_(SITE_WORK_STATUSES))
        rows = await session.execute(
            select(ScheduledWork.employee_id, ScheduledWork.work_date).where(and_(*conds))
        )
        return {(e, d) for e, d in rows.all()}

    def employee_day_access(
        self, employee_id: UUID, work_date: date, site_days: set[tuple[UUID, date]]
    ) -> AccessLevel | None:
        """In-memory version of ``operations_access`` using a precomputed ``site_days`` set."""
        if self.unrestricted:
            return AccessLevel.FULL
        return employee_access(
            self.role,
            ScopePurpose.OPERATIONS,
            employee_id in self.crew_ids,
            (employee_id, work_date) in site_days,
        )

    def is_read_only(self, employee_id: UUID) -> bool:
        """True when the viewer sees this employee only through a worksite, not the crew."""
        return not self.can_decide(employee_id)
