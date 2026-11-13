from collections.abc import Sequence
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fw.modules.jobs import Worksite
from fw.modules.org import Accommodation, Employee
from fw.modules.scheduling import ScheduledWork
from fw.modules.transport.models import (
    TransportRun,
    TransportRunPassenger,
    TransportRunStop,
    Vehicle,
)


class TransportRepository:
    """Async repository for transport vehicles, runs, stops, and passengers."""

    async def list_vehicles(
        self, session: AsyncSession, active_only: bool = True
    ) -> Sequence[Vehicle]:
        query = select(Vehicle)
        if active_only:
            query = query.where(Vehicle.is_active.is_(True))
        query = query.order_by(Vehicle.label.asc())
        result = await session.execute(query)
        return result.scalars().all()

    async def get_vehicle(self, session: AsyncSession, vehicle_id: UUID) -> Vehicle | None:
        return await session.get(Vehicle, vehicle_id)

    async def create_vehicle(self, session: AsyncSession, vehicle: Vehicle) -> Vehicle:
        session.add(vehicle)
        await session.flush()
        return vehicle

    async def list_drivers(
        self, session: AsyncSession, week_start: date | None = None
    ) -> list[dict]:
        """List active employees designated as drivers and their runs count this week."""
        emp_query = (
            select(Employee, Accommodation.name.label("accommodation_name"))
            .outerjoin(Accommodation, Employee.accommodation_id == Accommodation.id)
            .where(
                and_(
                    Employee.is_driver.is_(True),
                    Employee.is_active.is_(True),
                )
            )
            .order_by(Employee.name.asc())
        )
        emp_res = await session.execute(emp_query)
        rows = emp_res.all()

        drivers_data = []
        for emp, acc_name in rows:
            runs_count = 0
            if week_start:
                week_end = week_start + timedelta(days=6)
                count_query = select(func.count(TransportRun.id)).where(
                    and_(
                        TransportRun.driver_id == emp.id,
                        TransportRun.run_date >= week_start,
                        TransportRun.run_date <= week_end,
                        TransportRun.is_active.is_(True),
                    )
                )
                c_res = await session.execute(count_query)
                runs_count = c_res.scalar_one() or 0

            drivers_data.append(
                {
                    "employee_id": emp.id,
                    "tally_id": emp.tally_id,
                    "name": emp.name,
                    "phone": emp.phone,
                    "accommodation_id": emp.accommodation_id,
                    "accommodation_name": acc_name,
                    "runs_this_week": runs_count,
                    "is_active": emp.is_active,
                }
            )
        return drivers_data

    async def get_run(self, session: AsyncSession, run_id: UUID) -> TransportRun | None:
        query = (
            select(TransportRun)
            .options(
                selectinload(TransportRun.vehicle),
                selectinload(TransportRun.stops).selectinload(TransportRunStop.passengers),
                selectinload(TransportRun.passengers),
            )
            .where(
                and_(
                    TransportRun.id == run_id,
                    TransportRun.is_active.is_(True),
                )
            )
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def list_runs(
        self,
        session: AsyncSession,
        run_date: date,
        direction: str | None = None,
    ) -> Sequence[TransportRun]:
        query = (
            select(TransportRun)
            .options(
                selectinload(TransportRun.vehicle),
                selectinload(TransportRun.stops).selectinload(TransportRunStop.passengers),
                selectinload(TransportRun.passengers),
            )
            .where(
                and_(
                    TransportRun.run_date == run_date,
                    TransportRun.is_active.is_(True),
                )
            )
        )
        if direction:
            query = query.where(TransportRun.direction == direction)
        query = query.order_by(TransportRun.created_at.asc())
        result = await session.execute(query)
        return result.scalars().all()

    async def check_driver_conflict(
        self,
        session: AsyncSession,
        driver_id: UUID,
        run_date: date,
        direction: str,
        exclude_run_id: UUID | None = None,
    ) -> bool:
        """Return True if driver already has an active run on this date and direction."""
        query = select(TransportRun.id).where(
            and_(
                TransportRun.driver_id == driver_id,
                TransportRun.run_date == run_date,
                TransportRun.direction == direction,
                TransportRun.is_active.is_(True),
            )
        )
        if exclude_run_id:
            query = query.where(TransportRun.id != exclude_run_id)
        result = await session.execute(query)
        return result.first() is not None

    async def check_worker_conflict(
        self,
        session: AsyncSession,
        employee_id: UUID,
        run_date: date,
        direction: str,
        exclude_run_id: UUID | None = None,
    ) -> TransportRun | None:
        """Return the conflicting run if the employee is already a passenger in that direction."""
        query = (
            select(TransportRun)
            .join(TransportRunPassenger, TransportRun.id == TransportRunPassenger.run_id)
            .where(
                and_(
                    TransportRunPassenger.employee_id == employee_id,
                    TransportRun.run_date == run_date,
                    TransportRun.direction == direction,
                    TransportRun.is_active.is_(True),
                )
            )
        )
        if exclude_run_id:
            query = query.where(TransportRun.id != exclude_run_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def list_unassigned_workers(
        self,
        session: AsyncSession,
        run_date: date,
        direction: str = "MORNING",
    ) -> list[dict]:
        """Find active scheduled workers on run_date not assigned to any run in that direction."""
        # 1. IDs of workers already assigned to runs in this direction on run_date
        assigned_subq = (
            select(TransportRunPassenger.employee_id)
            .join(TransportRun, TransportRun.id == TransportRunPassenger.run_id)
            .where(
                and_(
                    TransportRun.run_date == run_date,
                    TransportRun.direction == direction,
                    TransportRun.is_active.is_(True),
                )
            )
            .scalar_subquery()
        )

        # 2. Scheduled work query for workers not in assigned_subq
        query = (
            select(
                Employee.id.label("employee_id"),
                Employee.tally_id,
                Employee.name,
                Employee.phone,
                Employee.accommodation_id,
                Accommodation.name.label("accommodation_name"),
                Worksite.id.label("worksite_id"),
                Worksite.job_name.label("worksite_name"),
                Worksite.job_number,
                ScheduledWork.assigned_hours,
            )
            .join(Employee, ScheduledWork.employee_id == Employee.id)
            .join(Worksite, ScheduledWork.worksite_id == Worksite.id)
            .outerjoin(Accommodation, Employee.accommodation_id == Accommodation.id)
            .where(
                and_(
                    ScheduledWork.work_date == run_date,
                    ScheduledWork.status == "ACTIVE",
                    Employee.is_active.is_(True),
                    ~Employee.id.in_(assigned_subq),
                )
            )
            .order_by(Worksite.job_name.asc(), Employee.name.asc())
        )
        result = await session.execute(query)
        rows = result.all()

        # Deduplicate per employee (in case worker has multiple work occurrences that day)
        seen_emps: set[UUID] = set()
        unassigned: list[dict] = []
        for r in rows:
            if r.employee_id in seen_emps:
                continue
            seen_emps.add(r.employee_id)
            unassigned.append(
                {
                    "employee_id": r.employee_id,
                    "tally_id": r.tally_id,
                    "name": r.name,
                    "phone": r.phone,
                    "accommodation_id": r.accommodation_id,
                    "accommodation_name": r.accommodation_name,
                    "worksite_id": r.worksite_id,
                    "worksite_name": r.worksite_name,
                    "job_number": r.job_number,
                    "assigned_hours": float(r.assigned_hours) if r.assigned_hours else None,
                }
            )
        return unassigned

    async def flag_runs_needing_update(
        self,
        session: AsyncSession,
        run_date: date,
        employee_ids: list[UUID],
    ) -> list[UUID]:
        """Flag all active published runs containing any of employee_ids as needing update."""
        if not employee_ids:
            return []

        query = (
            select(TransportRun)
            .join(TransportRunPassenger, TransportRun.id == TransportRunPassenger.run_id)
            .where(
                and_(
                    TransportRun.run_date == run_date,
                    TransportRun.status == "PUBLISHED",
                    TransportRun.is_active.is_(True),
                    TransportRunPassenger.employee_id.in_(employee_ids),
                )
            )
        )
        res = await session.execute(query)
        runs = res.scalars().all()
        flagged_ids = []
        for run in runs:
            if not run.needs_update:
                run.needs_update = True
                flagged_ids.append(run.id)
        if flagged_ids:
            await session.flush()
        return flagged_ids
