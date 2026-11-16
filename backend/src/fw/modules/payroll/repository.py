"""Repository for Payroll, Salary Revisions, and Job Cost Allocations."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fw.modules.attendance.models import AttendanceCalculation, AttendanceRecord
from fw.modules.jobs.models import JobItem, JobOccurrence, Worksite
from fw.modules.org.models import Employee
from fw.modules.payroll.models import (
    EmployeeSalary,
    PayrollRecord,
    PayrollRun,
    SalaryRevision,
)
from fw.modules.scheduling.models import LeaveRequest, ScheduledWork


class PayrollRepository:
    # --- Salary Revisions ---

    @staticmethod
    async def get_revision_by_code(
        session: AsyncSession,
        code: str,
    ) -> SalaryRevision | None:
        stmt = (
            select(SalaryRevision)
            .where(SalaryRevision.code == code)
            .options(selectinload(SalaryRevision.lines))
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_revision_by_id(
        session: AsyncSession,
        revision_id: UUID,
    ) -> SalaryRevision | None:
        stmt = (
            select(SalaryRevision)
            .where(SalaryRevision.id == revision_id)
            .options(selectinload(SalaryRevision.lines))
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_revisions(
        session: AsyncSession,
        country: str | None = None,
    ) -> list[SalaryRevision]:
        stmt = select(SalaryRevision).options(selectinload(SalaryRevision.lines))
        if country:
            stmt = stmt.where(SalaryRevision.country == country)
        stmt = stmt.order_by(SalaryRevision.effective_from.desc(), SalaryRevision.code.asc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_active_revision_for_worksite(
        session: AsyncSession,
        country: str,
        revision_code: str | None = None,
    ) -> SalaryRevision | None:
        """Find the active salary revision.

        If revision_code is explicitly assigned to the worksite, return it.
        Otherwise return the latest active revision for the country.
        """
        if revision_code:
            rev = await PayrollRepository.get_revision_by_code(session, revision_code)
            if rev and rev.status == "ACTIVE":
                return rev

        stmt = (
            select(SalaryRevision)
            .where(SalaryRevision.country == country, SalaryRevision.status == "ACTIVE")
            .options(selectinload(SalaryRevision.lines))
            .order_by(SalaryRevision.effective_from.desc())
            .limit(1)
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def create_revision(
        session: AsyncSession,
        revision: SalaryRevision,
    ) -> SalaryRevision:
        session.add(revision)
        await session.flush()
        return revision

    # --- Payroll Runs ---

    @staticmethod
    async def get_run_by_id(
        session: AsyncSession,
        run_id: UUID,
    ) -> PayrollRun | None:
        stmt = (
            select(PayrollRun)
            .where(PayrollRun.id == run_id)
            .options(
                selectinload(PayrollRun.records).selectinload(PayrollRecord.employee),
                selectinload(PayrollRun.records).selectinload(PayrollRecord.cost_allocations),
            )
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_latest_run_for_period(
        session: AsyncSession,
        period_start: date,
        period_end: date,
        country: str,
    ) -> PayrollRun | None:
        stmt = (
            select(PayrollRun)
            .where(
                PayrollRun.period_start == period_start,
                PayrollRun.period_end == period_end,
                PayrollRun.country == country,
            )
            .order_by(PayrollRun.run_no.desc(), PayrollRun.created_at.desc())
            .limit(1)
            .options(
                selectinload(PayrollRun.records).selectinload(PayrollRecord.employee),
            )
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_runs(
        session: AsyncSession,
        country: str | None = None,
        status: str | None = None,
    ) -> list[PayrollRun]:
        stmt = (
            select(PayrollRun)
            .options(selectinload(PayrollRun.records))
            .order_by(PayrollRun.period_start.desc(), PayrollRun.run_no.desc())
        )
        if country:
            stmt = stmt.where(PayrollRun.country == country)
        if status:
            stmt = stmt.where(PayrollRun.status == status)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def create_run(
        session: AsyncSession,
        run: PayrollRun,
    ) -> PayrollRun:
        session.add(run)
        await session.flush()
        return run

    @staticmethod
    async def delete_draft_run(
        session: AsyncSession,
        run_id: UUID,
    ) -> None:
        """Delete earlier draft run records before re-run."""
        await session.execute(delete(PayrollRun).where(PayrollRun.id == run_id))
        await session.flush()

    # --- Payroll Records & Queries ---

    @staticmethod
    async def list_records_for_run(
        session: AsyncSession,
        run_id: UUID,
        scoped_employee_ids: list[UUID] | None = None,
    ) -> list[PayrollRecord]:
        stmt = (
            select(PayrollRecord)
            .where(PayrollRecord.payroll_run_id == run_id)
            .options(selectinload(PayrollRecord.employee))
            .order_by(PayrollRecord.created_at.asc())
        )
        if scoped_employee_ids is not None:
            stmt = stmt.where(PayrollRecord.employee_id.in_(scoped_employee_ids))
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_worker_approved_records(
        session: AsyncSession,
        employee_id: UUID,
    ) -> list[PayrollRecord]:
        """Fetch all approved monthly payroll records for a worker."""
        stmt = (
            select(PayrollRecord)
            .join(PayrollRun, PayrollRecord.payroll_run_id == PayrollRun.id)
            .where(
                PayrollRecord.employee_id == employee_id,
                PayrollRun.status == "APPROVED",
            )
            .options(
                selectinload(PayrollRecord.payroll_run),
                selectinload(PayrollRecord.employee),
            )
            .order_by(PayrollRun.period_start.desc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def lock_attendance_records(
        session: AsyncSession,
        period_start: date,
        period_end: date,
        country: str,
    ) -> int:
        """Lock attendance records for the month upon payroll approval.

        Prevents any further daily recalculations from overwriting finalized versions.
        """
        stmt = (
            update(AttendanceRecord)
            .where(
                AttendanceRecord.work_date >= period_start,
                AttendanceRecord.work_date <= period_end,
                AttendanceRecord.employee_id.in_(
                    select(Employee.id).where(Employee.country == country)
                ),
            )
            .values(locked=True)
        )
        res = await session.execute(stmt)
        return int(getattr(res, "rowcount", 0) or 0)

    # --- Payroll Engine Aggregations ---

    @staticmethod
    async def get_active_employees_for_country(
        session: AsyncSession,
        country: str,
    ) -> list[Employee]:
        stmt = (
            select(Employee)
            .where(Employee.country == country, Employee.is_active == True)  # noqa: E712
            .order_by(Employee.tally_id.asc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_latest_salary_for_employee(
        session: AsyncSession,
        employee_id: UUID,
        as_of_date: date,
    ) -> EmployeeSalary | None:
        stmt = (
            select(EmployeeSalary)
            .where(
                EmployeeSalary.employee_id == employee_id,
                EmployeeSalary.effective_from <= as_of_date,
            )
            .order_by(EmployeeSalary.effective_from.desc(), EmployeeSalary.created_at.desc())
            .limit(1)
        )
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def get_attendance_calculations_for_period(
        session: AsyncSession,
        period_start: date,
        period_end: date,
        country: str,
    ) -> list[tuple[AttendanceRecord, AttendanceCalculation]]:
        """Fetch all current daily attendance calculations for the period."""
        stmt = (
            select(AttendanceRecord, AttendanceCalculation)
            .join(
                AttendanceCalculation,
                AttendanceRecord.current_calculation_id == AttendanceCalculation.id,
            )
            .join(Employee, AttendanceRecord.employee_id == Employee.id)
            .where(
                AttendanceRecord.work_date >= period_start,
                AttendanceRecord.work_date <= period_end,
                Employee.country == country,
            )
        )
        res = await session.execute(stmt)
        return [(row[0], row[1]) for row in res.all()]

    @staticmethod
    async def get_leave_requests_for_period(
        session: AsyncSession,
        period_start: date,
        period_end: date,
        country: str,
    ) -> list[LeaveRequest]:
        """Fetch approved leave requests intersecting the period."""
        stmt = (
            select(LeaveRequest)
            .join(Employee, LeaveRequest.employee_id == Employee.id)
            .where(
                Employee.country == country,
                LeaveRequest.status == "APPROVED",
                LeaveRequest.from_date <= period_end,
                LeaveRequest.to_date >= period_start,
            )
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_scheduled_work_for_period(
        session: AsyncSession,
        period_start: date,
        period_end: date,
        country: str,
    ) -> list[ScheduledWork]:
        stmt = (
            select(ScheduledWork)
            .join(Employee, ScheduledWork.employee_id == Employee.id)
            .where(
                Employee.country == country,
                ScheduledWork.work_date >= period_start,
                ScheduledWork.work_date <= period_end,
                ScheduledWork.status == "ACTIVE",
            )
            .options(selectinload(ScheduledWork.occurrence))
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_worksites_and_items(
        session: AsyncSession,
        country: str | None = None,
    ) -> list[Worksite]:
        stmt = (
            select(Worksite)
            .where(Worksite.is_active == True)  # noqa: E712
            .options(
                selectinload(Worksite.items).selectinload(JobItem.occurrences),
            )
            .order_by(Worksite.job_number.asc())
        )
        if country:
            stmt = stmt.where(Worksite.country == country)
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_allocated_minutes_per_worksite_for_employee(
        session: AsyncSession,
        employee_id: UUID,
        period_start: date,
        period_end: date,
    ) -> dict[UUID, int]:
        """Aggregate worked minutes per worksite from scheduled work and attendance visits."""
        stmt = (
            select(
                JobItem.worksite_id,
                func.sum(ScheduledWork.assigned_hours),
            )
            .join(JobOccurrence, ScheduledWork.occurrence_id == JobOccurrence.id)
            .join(JobItem, JobOccurrence.job_item_id == JobItem.id)
            .where(
                ScheduledWork.employee_id == employee_id,
                ScheduledWork.work_date >= period_start,
                ScheduledWork.work_date <= period_end,
                ScheduledWork.status == "ACTIVE",
            )
            .group_by(JobItem.worksite_id)
        )
        res = await session.execute(stmt)
        allocations: dict[UUID, int] = {}
        for worksite_id, total_hours in res.all():
            if worksite_id and total_hours:
                allocations[worksite_id] = int(Decimal(str(total_hours)) * Decimal("60"))
        return allocations
