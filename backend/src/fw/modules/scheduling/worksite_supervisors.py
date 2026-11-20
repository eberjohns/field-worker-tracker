"""Propose worksite supervisors from current crews (DEC-57).

For each active worksite, a supervisor is proposed when members of their crew (workers
whose active SUPERVISOR link points to them) hold an active standing assignment on one of
the worksite's job items today. Admin reviews the proposals and confirms the pairs to
assign; nothing is assigned automatically.
"""

from collections import defaultdict
from datetime import date
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from fw.core.clock import site_today
from fw.modules.jobs import (
    JobItem,
    JobsService,
    SupervisorProposal,
    Worksite,
    WorksiteSupervisor,
    WorksiteSupervisorBulkAssign,
    WorksiteSupervisorBulkAssignResult,
    WorksiteSupervisorProposal,
)
from fw.modules.org import Employee, EmployeeReportingLine
from fw.modules.scheduling.models import StandingAssignment


class WorksiteSupervisorProposalService:
    @staticmethod
    async def propose(
        session: AsyncSession, as_of: date | None = None
    ) -> list[WorksiteSupervisorProposal]:
        """Worksites that have unassigned crew supervisors or no supervisor at all."""
        day = as_of or site_today()
        supervisor = aliased(Employee)
        worker = aliased(Employee)
        crew_rows = await session.execute(
            select(
                JobItem.worksite_id,
                EmployeeReportingLine.manager_id,
                StandingAssignment.employee_id,
            )
            .join(JobItem, StandingAssignment.job_item_id == JobItem.id)
            .join(
                EmployeeReportingLine,
                EmployeeReportingLine.employee_id == StandingAssignment.employee_id,
            )
            .join(worker, worker.id == StandingAssignment.employee_id)
            .join(supervisor, supervisor.id == EmployeeReportingLine.manager_id)
            .where(
                StandingAssignment.is_active.is_(True),
                StandingAssignment.start_date <= day,
                or_(StandingAssignment.end_date.is_(None), StandingAssignment.end_date >= day),
                JobItem.is_active.is_(True),
                EmployeeReportingLine.relationship == "SUPERVISOR",
                EmployeeReportingLine.is_active.is_(True),
                worker.is_active.is_(True),
                supervisor.is_active.is_(True),
                supervisor.role == "SUPERVISOR",
            )
        )
        crew_on_site: dict[tuple[UUID, UUID], set[UUID]] = defaultdict(set)
        for ws_id, sup_id, emp_id in crew_rows.all():
            crew_on_site[(ws_id, sup_id)].add(emp_id)

        assigned_rows = await session.execute(
            select(WorksiteSupervisor.worksite_id, WorksiteSupervisor.supervisor_id).where(
                WorksiteSupervisor.is_active.is_(True)
            )
        )
        assigned: dict[UUID, set[UUID]] = defaultdict(set)
        for ws_id, sup_id in assigned_rows.all():
            assigned[ws_id].add(sup_id)

        sup_ids = {sup for (_, sup) in crew_on_site}
        sup_map: dict[UUID, Employee] = {}
        if sup_ids:
            res = await session.execute(select(Employee).where(Employee.id.in_(sup_ids)))
            sup_map = {e.id: e for e in res.scalars().all()}

        worksites = (
            (
                await session.execute(
                    select(Worksite)
                    .where(Worksite.is_active.is_(True))
                    .order_by(Worksite.job_number)
                )
            )
            .scalars()
            .all()
        )
        result: list[WorksiteSupervisorProposal] = []
        for ws in worksites:
            proposals = [
                SupervisorProposal(
                    supervisor_id=sup_id,
                    supervisor_name=sup_map[sup_id].name,
                    supervisor_tally_id=sup_map[sup_id].tally_id,
                    crew_members_on_site=len(members),
                )
                for (ws_id, sup_id), members in crew_on_site.items()
                if ws_id == ws.id and sup_id not in assigned[ws.id] and sup_id in sup_map
            ]
            if not proposals and assigned[ws.id]:
                continue
            proposals.sort(key=lambda p: (-p.crew_members_on_site, p.supervisor_name))
            result.append(
                WorksiteSupervisorProposal(
                    worksite_id=ws.id,
                    job_number=ws.job_number,
                    job_name=ws.job_name,
                    assigned_supervisor_ids=sorted(assigned[ws.id], key=str),
                    proposals=proposals,
                )
            )
        return result

    @staticmethod
    async def bulk_assign(
        session: AsyncSession,
        payload: WorksiteSupervisorBulkAssign,
        actor_user_id: UUID,
        actor_role: str,
    ) -> WorksiteSupervisorBulkAssignResult:
        """Assign the pairs Admin confirmed. All or nothing: one invalid pair fails the call."""
        assigned = 0
        already = 0
        seen: set[tuple[UUID, UUID]] = set()
        for pair in payload.assignments:
            key = (pair.worksite_id, pair.supervisor_id)
            if key in seen:
                continue
            seen.add(key)
            existing = await session.scalar(
                select(WorksiteSupervisor.id).where(
                    WorksiteSupervisor.worksite_id == pair.worksite_id,
                    WorksiteSupervisor.supervisor_id == pair.supervisor_id,
                    WorksiteSupervisor.is_active.is_(True),
                )
            )
            if existing:
                already += 1
                continue
            await JobsService.assign_worksite_supervisor(
                session=session,
                worksite_id=pair.worksite_id,
                supervisor_id=pair.supervisor_id,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
            )
            assigned += 1
        return WorksiteSupervisorBulkAssignResult(assigned=assigned, already_assigned=already)
