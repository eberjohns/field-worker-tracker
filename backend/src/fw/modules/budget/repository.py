"""Bulk loaders for the job budget (DEC-59). A fixed number of queries, never one per worksite."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fw.modules.attendance import AttendanceCalculation, AttendanceRecord, SiteVisit
from fw.modules.jobs import Worksite
from fw.modules.payroll import JobCostAllocation, PayrollRecord, PayrollRun, SalaryRevision
from fw.modules.scheduling import ScheduledWork
from fw.modules.settings import CompanySettingValue


class BudgetRepository:
    @staticmethod
    async def worksites_with_items(
        session: AsyncSession,
        worksite_ids: list[UUID] | None = None,
        country: str | None = None,
        active_only: bool = True,
    ) -> list[Worksite]:
        stmt = select(Worksite).options(selectinload(Worksite.items)).order_by(Worksite.job_number)
        if worksite_ids is not None:
            stmt = stmt.where(Worksite.id.in_(worksite_ids))
        if country:
            stmt = stmt.where(Worksite.country == country)
        if active_only:
            stmt = stmt.where(Worksite.is_active.is_(True))
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def active_revisions(session: AsyncSession) -> list[SalaryRevision]:
        stmt = (
            select(SalaryRevision)
            .where(SalaryRevision.status == "ACTIVE")
            .options(selectinload(SalaryRevision.lines))
        )
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def settings_rows(session: AsyncSession, keys: list[str]) -> list[CompanySettingValue]:
        stmt = select(CompanySettingValue).where(CompanySettingValue.setting_key.in_(keys))
        return list((await session.execute(stmt)).scalars().all())

    @staticmethod
    async def approved_visit_minutes(
        session: AsyncSession, worksite_ids: list[UUID], date_from: date, date_to: date
    ) -> list[tuple[UUID, UUID, date, int]]:
        """(employee_id, worksite_id, work_date, minutes) for site visits on approved days.

        "Approved" is payroll's rule: review APPROVED, or not REJECTED with no review reasons.
        """
        if not worksite_ids:
            return []
        calc = AttendanceCalculation
        stmt = (
            select(
                SiteVisit.employee_id,
                SiteVisit.worksite_id,
                SiteVisit.work_date,
                func.sum(SiteVisit.duration_minutes),
            )
            .join(
                AttendanceRecord,
                and_(
                    AttendanceRecord.employee_id == SiteVisit.employee_id,
                    AttendanceRecord.work_date == SiteVisit.work_date,
                ),
            )
            .outerjoin(calc, calc.id == AttendanceRecord.current_calculation_id)
            .where(
                SiteVisit.place_type == "SITE",
                SiteVisit.worksite_id.in_(worksite_ids),
                SiteVisit.work_date >= date_from,
                SiteVisit.work_date <= date_to,
                or_(
                    AttendanceRecord.review_status == "APPROVED",
                    and_(
                        AttendanceRecord.review_status != "REJECTED",
                        calc.id.is_not(None),
                        func.coalesce(func.cardinality(calc.review_reasons), 0) == 0,
                    ),
                ),
            )
            .group_by(SiteVisit.employee_id, SiteVisit.worksite_id, SiteVisit.work_date)
        )
        rows = (await session.execute(stmt)).all()
        out: list[tuple[UUID, UUID, date, int]] = []
        for emp, ws_id, work_date, minutes in rows:
            if ws_id is not None:
                out.append((emp, ws_id, work_date, int(minutes or 0)))
        return out

    @staticmethod
    async def scheduled_hours(
        session: AsyncSession, worksite_ids: list[UUID], date_from: date, date_to: date
    ) -> list[tuple[UUID, UUID, date, UUID, Decimal]]:
        """(employee_id, worksite_id, work_date, job_item_id, assigned_hours) of active work."""
        if not worksite_ids:
            return []
        stmt = (
            select(
                ScheduledWork.employee_id,
                ScheduledWork.worksite_id,
                ScheduledWork.work_date,
                ScheduledWork.job_item_id,
                func.sum(ScheduledWork.assigned_hours),
            )
            .where(
                ScheduledWork.worksite_id.in_(worksite_ids),
                ScheduledWork.work_date >= date_from,
                ScheduledWork.work_date <= date_to,
                ScheduledWork.status == "ACTIVE",
            )
            .group_by(
                ScheduledWork.employee_id,
                ScheduledWork.worksite_id,
                ScheduledWork.work_date,
                ScheduledWork.job_item_id,
            )
        )
        rows = (await session.execute(stmt)).all()
        return [(r[0], r[1], r[2], r[3], Decimal(str(r[4] or 0))) for r in rows]

    @staticmethod
    async def approved_allocations(
        session: AsyncSession, worksite_ids: list[UUID], date_from: date, date_to: date
    ) -> list[tuple[UUID, date, date, Decimal]]:
        """(worksite_id, run period_start, run period_end, amount) from APPROVED payroll runs
        whose period overlaps the range."""
        if not worksite_ids:
            return []
        stmt = (
            select(
                JobCostAllocation.worksite_id,
                PayrollRun.period_start,
                PayrollRun.period_end,
                func.sum(JobCostAllocation.allocated_amount),
            )
            .join(PayrollRecord, JobCostAllocation.payroll_record_id == PayrollRecord.id)
            .join(PayrollRun, PayrollRecord.payroll_run_id == PayrollRun.id)
            .where(
                JobCostAllocation.worksite_id.in_(worksite_ids),
                PayrollRun.status == "APPROVED",
                PayrollRun.period_start <= date_to,
                PayrollRun.period_end >= date_from,
            )
            .group_by(JobCostAllocation.worksite_id, PayrollRun.period_start, PayrollRun.period_end)
        )
        rows = (await session.execute(stmt)).all()
        return [(r[0], r[1], r[2], Decimal(str(r[3] or 0))) for r in rows]
