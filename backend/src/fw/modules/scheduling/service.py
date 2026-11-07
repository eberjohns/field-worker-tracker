"""SchedulingService orchestrating standing assignments, daily scheduled work, roster, and coverage."""

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import func, select, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fw.core.errors import AppError
from fw.modules.audit import AuditService
from fw.modules.jobs import JobItem, JobOccurrence, Worksite
from fw.modules.org import Employee, EmployeeReportingLine
from fw.modules.scheduling.models import (
    BaseRosterEntry,
    BaseRosterTemplate,
    ScheduledWork,
    StandingAssignment,
)
from fw.modules.scheduling.schemas import (
    AssignedWorkerSummary,
    BasePlannerItemRow,
    BasePlannerResponse,
    BasePlannerWorksiteRow,
    BaseRosterEntryRead,
    BaseRosterTemplateCreate,
    BaseRosterTemplateRead,
    CandidateRecommendationRead,
    CoverageDayCell,
    CoverageItemRow,
    CoverageResponse,
    CoverageWorksiteRow,
    OperationalCellWorker,
    OperationalCoverageResponse,
    OperationalDayCell,
    OperationalJobItemRow,
    OperationalRosterDayCell,
    OperationalRosterResponse,
    OperationalRosterWorkerRow,
    OperationalShiftCreate,
    OperationalWorksiteRow,
    RosterDayCell,
    RosterResponse,
    RosterSiteChip,
    RosterWorkerRow,
    ScheduledWorkBatchCreate,
    ScheduledWorkCreate,
    ScheduledWorkRead,
    ScheduledWorkReorderRequest,
    ScheduledWorkUpdate,
    ScheduledWorkValidateRequest,
    StandingAssignmentCreate,
    StandingAssignmentEndRequest,
    StandingAssignmentRead,
    ValidationIssueRead,
    ValidationReportRead,
    WorkerAllocationResponse,
)
from fw.modules.settings import CompanySettingValue, PublicHoliday, TimeRule
from fw.rules.scheduling import (
    INT_TO_WEEKDAY,
    BlueprintEntry,
    CandidateWorker,
    DayMarker,
    EffectiveStandardHours,
    EmployeeValidationContext,
    ExcelRosterDayCell,
    ExcelRosterWorkerRow,
    ExistingAssignmentContext,
    JobItemValidationContext,
    OperationalShiftInput,
    ResolvedTemplateSlot,
    TargetJobItem,
    VisitRecord,
    WorkerDayContext,
    build_roster_excel_bytes,
    calculate_allocation_summary,
    calculate_pacing_windows,
    compute_effective_standard_hours,
    evaluate_period_quota,
    evaluate_worker_day_marker,
    generate_assignment_dates,
    rank_candidates_for_job,
    resolve_base_template_slots,
    resolve_operational_cell,
    validate_assignment,
)
from fw.rules.time_rules import (
    TimeRuleAppliesTo,
    TimeRuleDefinition,
    TimeRuleScope,
    WorkerContext,
    resolve_time_schedule,
)

# Table representation for employee salary without importing payroll module
employee_salary_table = sa.table(
    "employee_salary",
    sa.column("employee_id", postgresql.UUID),
    sa.column("effective_from", sa.Date),
    sa.column("standard_hours", sa.Numeric),
)


class SchedulingService:
    """Service handling all planning and scheduling domain operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # -------------------------------------------------------------------------
    # Helper: Resolve Standard Hours & Time Rules
    # -------------------------------------------------------------------------

    async def get_employee_base_standard_hours(
        self, employee_id: UUID, work_date: date
    ) -> Decimal:
        """Fetch employee standard hours from salary structure as of work_date (default 8.0)."""
        stmt = (
            select(employee_salary_table.c.standard_hours)
            .where(
                employee_salary_table.c.employee_id == employee_id,
                employee_salary_table.c.effective_from <= work_date,
            )
            .order_by(employee_salary_table.c.effective_from.desc())
            .limit(1)
        )
        res = (await self.session.execute(stmt)).scalar_one_or_none()
        return Decimal(str(res)) if res is not None else Decimal("8.0")

    async def get_employees_base_standard_hours(
        self, employee_ids: list[UUID], work_date: date
    ) -> dict[UUID, Decimal]:
        """Batch fetch employee standard hours from salary structure as of work_date (default 8.0)."""
        if not employee_ids:
            return {}
        salary_subq = (
            select(
                employee_salary_table.c.employee_id,
                employee_salary_table.c.standard_hours,
                func.row_number()
                .over(
                    partition_by=employee_salary_table.c.employee_id,
                    order_by=employee_salary_table.c.effective_from.desc(),
                )
                .label("rn"),
            )
            .where(
                employee_salary_table.c.employee_id.in_(employee_ids),
                employee_salary_table.c.effective_from <= work_date,
            )
            .subquery()
        )
        salary_stmt = select(
            salary_subq.c.employee_id, salary_subq.c.standard_hours
        ).where(salary_subq.c.rn == 1)
        salary_rows = (await self.session.execute(salary_stmt)).all()
        return {
            row[0]: Decimal(str(row[1]))
            for row in salary_rows
            if row[1] is not None
        }

    async def get_effective_standard_hours(
        self, employee: Employee, work_date: date
    ) -> EffectiveStandardHours:
        """Calculate effective standard hours combining salary and time rules (e.g. Ramadan)."""
        base_hours = await self.get_employee_base_standard_hours(employee.id, work_date)

        # Query active time rules for country
        tr_stmt = select(TimeRule).where(
            TimeRule.country == employee.country,
            TimeRule.is_active.is_(True),
            TimeRule.start_date <= work_date,
            sa.or_(TimeRule.end_date.is_(None), TimeRule.end_date >= work_date),
        )
        time_rules_db = (await self.session.execute(tr_stmt)).scalars().all()

        definitions: list[TimeRuleDefinition] = []
        for tr in time_rules_db:
            definitions.append(
                TimeRuleDefinition(
                    id=tr.id,
                    name=tr.name,
                    country=tr.country,
                    scope_type=TimeRuleScope(tr.scope_type),
                    scope_employee_id=tr.scope_employee_id,
                    applies_to=TimeRuleAppliesTo(tr.applies_to),
                    start_date=tr.start_date,
                    end_date=tr.end_date,
                    standard_hours_change_minutes=tr.standard_hours_change_minutes,
                    is_active=tr.is_active,
                )
            )

        worker_ctx = WorkerContext(
            employee_id=employee.id,
            country=employee.country,
            has_accommodation=bool(employee.accommodation_id),
            is_driver=employee.is_driver,
        )

        resolved = resolve_time_schedule(
            rules=definitions,
            worker=worker_ctx,
            target_date=work_date,
            is_outdoor=True,
        )

        return compute_effective_standard_hours(
            base_standard_hours=base_hours,
            adjustment_minutes=resolved.standard_hours_change_minutes,
        )

    async def get_budget_only_staff_types(self, country: str | None = None) -> set[str]:
        """Fetch budget-only staff types from company settings."""
        stmt = (
            select(CompanySettingValue.value)
            .where(
                CompanySettingValue.setting_key == "budget_only_staff_types",
                sa.or_(
                    CompanySettingValue.country == country,
                    CompanySettingValue.country.is_(None),
                ),
            )
            .order_by(CompanySettingValue.effective_from.desc())
            .limit(1)
        )
        val = (await self.session.execute(stmt)).scalar_one_or_none()
        if val and isinstance(val, list):
            return {str(x).strip().lower() for x in val}
        return set()

    async def get_public_holidays(
        self, country: str, from_date: date, to_date: date
    ) -> set[date]:
        """Fetch public holidays for country between from_date and to_date."""
        stmt = select(PublicHoliday.holiday_date).where(
            PublicHoliday.country == country,
            PublicHoliday.holiday_date >= from_date,
            PublicHoliday.holiday_date <= to_date,
        )
        dates = (await self.session.execute(stmt)).scalars().all()
        return set(dates)

    async def get_public_holidays_map(
        self, country: str, from_date: date, to_date: date
    ) -> dict[date, str]:
        """Fetch public holidays with names for country between from_date and to_date."""
        stmt = select(PublicHoliday.holiday_date, PublicHoliday.name).where(
            PublicHoliday.country == country,
            PublicHoliday.holiday_date >= from_date,
            PublicHoliday.holiday_date <= to_date,
        )
        rows = (await self.session.execute(stmt)).all()
        return {r[0]: r[1] for r in rows}

    # -------------------------------------------------------------------------
    # Standing Assignments (The Year Plan)
    # -------------------------------------------------------------------------

    async def create_standing_assignment(
        self,
        payload: StandingAssignmentCreate,
        current_user_id: UUID,
        horizon_months: int = 13,
    ) -> StandingAssignmentRead:
        """Create a standing assignment and materialize daily ScheduledWork for 13 months."""
        # 1. Fetch Employee and JobItem
        emp = await self.session.get(Employee, payload.employee_id)
        if not emp or not emp.is_active:
            raise AppError(code="NOT_FOUND", message=f"Active employee {payload.employee_id} not found.", status_code=404)
        if emp.role == "ADMIN" or emp.tally_id == "ADMIN001":
            raise AppError(code="VALIDATION_ERROR", message="System Administrator cannot be assigned to field work.", status_code=422)

        stmt = (
            select(JobItem)
            .where(JobItem.id == payload.job_item_id)
            .options(
                selectinload(JobItem.worksite),
                selectinload(JobItem.occurrences),
            )
        )
        item = (await self.session.execute(stmt)).scalar_one_or_none()
        if not item or not item.is_active:
            raise AppError(code="NOT_FOUND", message=f"Active job item {payload.job_item_id} not found.", status_code=404)

        # 2. Persist StandingAssignment
        assigned_pattern = payload.weekday_pattern or item.weekday_pattern
        if item.frequency_unit in ("MONTH", "QUARTER", "YEAR"):
            assigned_pattern = None
        elif item.frequency_unit == "WEEK" and item.occurrences_per_period == 1:
            assigned_pattern = [INT_TO_WEEKDAY[payload.start_date.weekday()]]

        # Deactivate or close any pre-existing active standing assignments for this employee and job_item
        existing_standing_stmt = select(StandingAssignment).where(
            StandingAssignment.employee_id == payload.employee_id,
            StandingAssignment.job_item_id == payload.job_item_id,
            StandingAssignment.is_active.is_(True),
        )
        existing_standing_rows = (await self.session.execute(existing_standing_stmt)).scalars().all()
        for old_st in existing_standing_rows:
            if old_st.start_date >= payload.start_date:
                old_st.is_active = False
            else:
                old_st.end_date = payload.start_date - timedelta(days=1)

        standing = StandingAssignment(
            employee_id=payload.employee_id,
            job_item_id=payload.job_item_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            weekday_pattern=assigned_pattern,
            hours_per_day=payload.hours_per_day or item.hours_per_occurrence_per_staff,
            created_by_user_id=current_user_id,
            is_active=True,
            version=1,
        )
        self.session.add(standing)
        await self.session.flush()

        # 3. Materialize daily ScheduledWork for 13-month rolling horizon
        horizon_end = payload.start_date + timedelta(days=horizon_months * 31)
        max_end = payload.end_date if payload.end_date else horizon_end
        target_end = min(max_end, horizon_end)
        if item.end_date:
            target_end = min(target_end, item.end_date)

        holidays = await self.get_public_holidays(item.worksite.country, payload.start_date, target_end)

        assigned_hours = standing.hours_per_day or item.hours_per_occurrence_per_staff
        created_count = 0

        # Existing active scheduled work for this employee and job_item
        existing_sw_stmt = select(ScheduledWork.work_date).where(
            ScheduledWork.employee_id == payload.employee_id,
            ScheduledWork.job_item_id == payload.job_item_id,
            ScheduledWork.work_date >= payload.start_date,
            ScheduledWork.work_date <= target_end,
            ScheduledWork.status == "ACTIVE",
        )
        existing_sw_dates = set((await self.session.execute(existing_sw_stmt)).scalars().all())

        is_periodic_interval = item.frequency_unit in ("MONTH", "QUARTER", "YEAR")

        if is_periodic_interval:
            # If occurrences haven't been generated yet, generate them now
            if not item.occurrences:
                from fw.modules.jobs.service import JobsService
                await JobsService.generate_job_occurrences(
                    session=self.session,
                    job_item_id=item.id,
                    from_date=payload.start_date,
                    to_date=target_end,
                    actor_user_id=current_user_id,
                )
                stmt_reload = select(JobOccurrence).where(JobOccurrence.job_item_id == item.id)
                loaded_occs = list((await self.session.execute(stmt_reload)).scalars().all())
            else:
                loaded_occs = item.occurrences

            # Materialize directly for periodic occurrences (1 visit per occurrence window, e.g. monthly)
            valid_occs = [
                occ for occ in loaded_occs
                if occ.window_end >= payload.start_date and occ.window_start <= target_end
            ]
            valid_occs.sort(key=lambda o: o.window_start)
            target_weekday = payload.start_date.weekday()
            target_nth = (payload.start_date.day - 1) // 7

            for occ in valid_occs:
                if occ.window_start <= payload.start_date <= occ.window_end:
                    target_date = payload.start_date
                else:
                    # Match same relative weekday (e.g. 1st Wednesday of the month)
                    days_in_win = (occ.window_end - occ.window_start).days + 1
                    matching_days = [
                        occ.window_start + timedelta(days=d)
                        for d in range(days_in_win)
                        if (occ.window_start + timedelta(days=d)).weekday() == target_weekday
                    ]
                    if matching_days:
                        clamped_idx = min(target_nth, len(matching_days) - 1)
                        target_date = matching_days[clamped_idx]
                    else:
                        target_date = occ.due_date or occ.window_start

                # Adjust for worker weekly off or public holiday
                while target_date <= occ.window_end:
                    weekday_code = INT_TO_WEEKDAY[target_date.weekday()]
                    if emp.weekly_off_day and weekday_code == emp.weekly_off_day:
                        target_date += timedelta(days=1)
                        continue
                    if target_date in holidays:
                        target_date += timedelta(days=1)
                        continue
                    break

                if target_date > occ.window_end or target_date in existing_sw_dates:
                    continue

                seq_stmt = (
                    select(func.coalesce(func.max(ScheduledWork.sequence), 0))
                    .where(
                        ScheduledWork.employee_id == payload.employee_id,
                        ScheduledWork.work_date == target_date,
                        ScheduledWork.status == "ACTIVE",
                    )
                )
                max_seq = (await self.session.execute(seq_stmt)).scalar() or 0
                next_seq = int(max_seq) + 1

                sw = ScheduledWork(
                    employee_id=payload.employee_id,
                    work_date=target_date,
                    occurrence_id=occ.id,
                    job_item_id=payload.job_item_id,
                    worksite_id=item.worksite_id,
                    assigned_hours=assigned_hours,
                    sequence=next_seq,
                    status="ACTIVE",
                    source="STANDING",
                    created_by_user_id=current_user_id,
                    version=1,
                )
                self.session.add(sw)
                existing_sw_dates.add(target_date)
                created_count += 1
        else:
            # Weekly or daily pattern
            slots = generate_assignment_dates(
                start_date=payload.start_date,
                end_date=target_end,
                weekday_pattern=standing.weekday_pattern,
                public_holidays=holidays,
                skip_public_holidays=True,
                weekly_off_day=emp.weekly_off_day,
            )
            for slot in slots:
                if not slot.is_working_day or slot.work_date in existing_sw_dates:
                    continue

                # Find or match occurrence for slot.work_date
                matching_occ_id: UUID | None = None
                for occ in item.occurrences:
                    if occ.window_start <= slot.work_date <= occ.window_end:
                        matching_occ_id = occ.id
                        break

                seq_stmt = (
                    select(func.coalesce(func.max(ScheduledWork.sequence), 0))
                    .where(
                        ScheduledWork.employee_id == payload.employee_id,
                        ScheduledWork.work_date == slot.work_date,
                        ScheduledWork.status == "ACTIVE",
                    )
                )
                max_seq = (await self.session.execute(seq_stmt)).scalar() or 0
                next_seq = int(max_seq) + 1

                sw = ScheduledWork(
                    employee_id=payload.employee_id,
                    work_date=slot.work_date,
                    occurrence_id=matching_occ_id,
                    job_item_id=payload.job_item_id,
                    worksite_id=item.worksite_id,
                    assigned_hours=assigned_hours,
                    sequence=next_seq,
                    status="ACTIVE",
                    source="STANDING",
                    created_by_user_id=current_user_id,
                    version=1,
                )
                self.session.add(sw)
                created_count += 1

        await self.session.flush()

        # Audit log
        await AuditService.log_action(
            session=self.session,
            action="CREATE",
            entity_type="StandingAssignment",
            entity_id=str(standing.id),
            actor_user_id=current_user_id,
            diff={
                "employee_id": str(payload.employee_id),
                "job_item_id": str(payload.job_item_id),
                "start_date": payload.start_date.isoformat(),
                "scheduled_work_rows_created": created_count,
            },
        )

        return StandingAssignmentRead(
            id=standing.id,
            employee_id=standing.employee_id,
            employee_name=emp.name,
            job_item_id=standing.job_item_id,
            job_number=item.worksite.job_number,
            sub_item_code=item.sub_item_code,
            start_date=standing.start_date,
            end_date=standing.end_date,
            weekday_pattern=standing.weekday_pattern,
            hours_per_day=standing.hours_per_day,
            is_active=standing.is_active,
            version=standing.version,
            created_at=standing.created_at,
        )

    async def end_standing_assignment(
        self,
        assignment_id: UUID,
        payload: StandingAssignmentEndRequest,
        current_user_id: UUID,
    ) -> StandingAssignmentRead:
        """End a standing assignment from end_date and cancel future scheduled work."""
        standing = await self.session.get(
            StandingAssignment,
            assignment_id,
            options=[
                selectinload(StandingAssignment.employee),
                selectinload(StandingAssignment.job_item).selectinload(JobItem.worksite),
            ],
        )
        if not standing or not standing.is_active:
            raise AppError(code="NOT_FOUND", message=f"Standing assignment {assignment_id} not found.", status_code=404)

        if standing.version != payload.version:
            raise AppError(code="CONFLICT", message="Standing assignment was modified by another user. Please reload.", status_code=409)

        if payload.end_date < standing.start_date:
            # Ending before start_date deactivates the standing assignment completely
            old_end = standing.end_date
            standing.is_active = False
            standing.end_date = standing.start_date
            standing.version += 1
            cancel_stmt = (
                update(ScheduledWork)
                .where(
                    ScheduledWork.employee_id == standing.employee_id,
                    ScheduledWork.job_item_id == standing.job_item_id,
                    ScheduledWork.source == "STANDING",
                    ScheduledWork.status == "ACTIVE",
                    ScheduledWork.work_date >= standing.start_date,
                )
                .values(status="CANCELLED", updated_at=datetime.now(UTC))
            )
            await self.session.execute(cancel_stmt)
        else:
            old_end = standing.end_date
            standing.end_date = payload.end_date
            standing.version += 1

            # Cancel uncompleted scheduled work created from this standing assignment after end_date
            cancel_stmt = (
                update(ScheduledWork)
                .where(
                    ScheduledWork.employee_id == standing.employee_id,
                    ScheduledWork.job_item_id == standing.job_item_id,
                    ScheduledWork.source == "STANDING",
                    ScheduledWork.status == "ACTIVE",
                    ScheduledWork.work_date > payload.end_date,
                )
                .values(status="CANCELLED", updated_at=datetime.now(UTC))
            )
            await self.session.execute(cancel_stmt)

        await AuditService.log_action(
            session=self.session,
            action="UPDATE",
            entity_type="StandingAssignment",
            entity_id=str(standing.id),
            actor_user_id=current_user_id,
            diff={
                "old_end_date": old_end.isoformat() if old_end else None,
                "new_end_date": payload.end_date.isoformat(),
            },
        )

        return StandingAssignmentRead(
            id=standing.id,
            employee_id=standing.employee_id,
            employee_name=standing.employee.name if standing.employee else None,
            job_item_id=standing.job_item_id,
            job_number=standing.job_item.worksite.job_number if standing.job_item else None,
            sub_item_code=standing.job_item.sub_item_code if standing.job_item else None,
            start_date=standing.start_date,
            end_date=standing.end_date,
            weekday_pattern=standing.weekday_pattern,
            hours_per_day=standing.hours_per_day,
            is_active=standing.is_active,
            version=standing.version,
            created_at=standing.created_at,
        )

    async def list_standing_assignments(
        self,
        job_item_id: UUID | None = None,
        employee_id: UUID | None = None,
    ) -> list[StandingAssignmentRead]:
        """List active standing assignments."""
        stmt = (
            select(StandingAssignment)
            .where(StandingAssignment.is_active.is_(True))
            .options(
                selectinload(StandingAssignment.employee),
                selectinload(StandingAssignment.job_item).selectinload(JobItem.worksite),
            )
            .order_by(StandingAssignment.start_date.desc())
        )
        if job_item_id:
            stmt = stmt.where(StandingAssignment.job_item_id == job_item_id)
        if employee_id:
            stmt = stmt.where(StandingAssignment.employee_id == employee_id)

        rows = (await self.session.execute(stmt)).scalars().all()
        return [
            StandingAssignmentRead(
                id=s.id,
                employee_id=s.employee_id,
                employee_name=s.employee.name if s.employee else None,
                job_item_id=s.job_item_id,
                job_number=s.job_item.worksite.job_number if s.job_item else None,
                sub_item_code=s.job_item.sub_item_code if s.job_item else None,
                start_date=s.start_date,
                end_date=s.end_date,
                weekday_pattern=s.weekday_pattern,
                hours_per_day=s.hours_per_day,
                is_active=s.is_active,
                version=s.version,
                created_at=s.created_at,
            )
            for s in rows
        ]

    # -------------------------------------------------------------------------
    # Scheduled Work (Daily Assignments) & Validation
    # -------------------------------------------------------------------------

    async def validate_scheduled_work_request(
        self,
        payload: ScheduledWorkValidateRequest,
        is_admin: bool = False,
    ) -> ValidationReportRead:
        """Run pure validation checks against proposed daily scheduled work."""
        emp = await self.session.get(Employee, payload.employee_id)
        if not emp:
            raise AppError(code="NOT_FOUND", message=f"Employee {payload.employee_id} not found.", status_code=404)
        if emp.role == "ADMIN" or emp.tally_id == "ADMIN001":
            raise AppError(code="VALIDATION_ERROR", message="System Administrator cannot be assigned to field work.", status_code=422)

        stmt = (
            select(JobItem)
            .where(JobItem.id == payload.job_item_id)
            .options(selectinload(JobItem.worksite))
        )
        item = (await self.session.execute(stmt)).scalar_one_or_none()
        if not item:
            raise AppError(code="NOT_FOUND", message=f"Job item {payload.job_item_id} not found.", status_code=404)

        # Existing active assignments on work_date
        existing_stmt = select(ScheduledWork).where(
            ScheduledWork.employee_id == payload.employee_id,
            ScheduledWork.work_date == payload.work_date,
            ScheduledWork.status == "ACTIVE",
        ).options(selectinload(ScheduledWork.job_item))
        existing_rows = (await self.session.execute(existing_stmt)).scalars().all()

        existing_contexts = [
            ExistingAssignmentContext(
                scheduled_work_id=str(r.id),
                job_item_id=str(r.job_item_id),
                worksite_id=str(r.worksite_id),
                occurrence_id=str(r.occurrence_id) if r.occurrence_id else None,
                deployment_type=r.job_item.deployment_type,
                assigned_hours=r.assigned_hours,
                sequence=r.sequence,
            )
            for r in existing_rows
        ]

        # Determine target sequence
        target_seq = payload.sequence
        if target_seq is None:
            max_seq = max([e.sequence for e in existing_contexts], default=0)
            target_seq = max_seq + 1

        # Budget only check
        budget_types = await self.get_budget_only_staff_types(item.worksite.country)
        is_budget = (item.staff_grade_description or "").strip().lower() in budget_types

        # Holiday check
        holidays = await self.get_public_holidays(
            item.worksite.country, payload.work_date, payload.work_date
        )
        is_holiday = payload.work_date in holidays

        # Effective standard hours
        eff_hours = await self.get_effective_standard_hours(emp, payload.work_date)

        emp_ctx = EmployeeValidationContext(
            employee_id=str(emp.id),
            is_active=emp.is_active,
            join_date=emp.join_date,
            employment_end_date=emp.employment_end_date,
            weekly_off_day=emp.weekly_off_day,
            grade_code=emp.grade_code,
            staff_grade_description=emp.staff_grade_description,
            standard_hours=eff_hours.effective_daily_standard_hours,
        )

        job_ctx = JobItemValidationContext(
            job_item_id=str(item.id),
            worksite_id=str(item.worksite_id),
            is_active=item.is_active,
            worksite_is_active=item.worksite.is_active,
            deployment_type=item.deployment_type,
            planned_grade_code=item.planned_grade_code,
            staff_grade_description=item.staff_grade_description,
            has_boundary=item.worksite.boundary is not None,
            start_date=item.start_date,
            end_date=item.end_date,
            is_budget_only=is_budget,
        )

        report = validate_assignment(
            employee=emp_ctx,
            job_item=job_ctx,
            target_date=payload.work_date,
            assigned_hours=payload.assigned_hours,
            target_sequence=target_seq,
            existing_assignments=existing_contexts,
            today=date.today(),
            is_admin=is_admin,
            is_public_holiday=is_holiday,
            is_on_leave=False,
            target_occurrence_id=str(payload.occurrence_id) if payload.occurrence_id else None,
            exclude_scheduled_work_id=str(payload.exclude_scheduled_work_id)
            if payload.exclude_scheduled_work_id
            else None,
        )

        def to_read_issue(issue) -> ValidationIssueRead:
            return ValidationIssueRead(
                code=issue.code.value,
                severity=issue.severity.value,
                message=issue.message,
            )

        return ValidationReportRead(
            is_valid=report.is_valid,
            issues=[to_read_issue(i) for i in report.issues],
            errors=[to_read_issue(i) for i in report.errors],
            warnings=[to_read_issue(i) for i in report.warnings],
            infos=[to_read_issue(i) for i in report.infos],
        )

    async def create_scheduled_work(
        self,
        payload: ScheduledWorkCreate,
        current_user_id: UUID,
        is_admin: bool = False,
    ) -> ScheduledWorkRead:
        """Create a direct daily scheduled work assignment."""
        validate_req = ScheduledWorkValidateRequest(
            employee_id=payload.employee_id,
            job_item_id=payload.job_item_id,
            work_date=payload.work_date,
            assigned_hours=payload.assigned_hours,
            sequence=payload.sequence,
            occurrence_id=payload.occurrence_id,
        )
        report = await self.validate_scheduled_work_request(validate_req, is_admin=is_admin)

        if not report.is_valid:
            error_msgs = "; ".join([e.message for e in report.errors])
            raise AppError(code="VALIDATION_ERROR", message=f"Assignment validation failed: {error_msgs}", status_code=422)

        if report.warnings and not payload.acknowledge_warnings:
            warning_msgs = "; ".join([w.message for w in report.warnings])
            raise AppError(
                code="WARNINGS_NEED_ACKNOWLEDGEMENT",
                message=f"Validation warnings need acknowledgment: {warning_msgs}",
                status_code=409,
            )

        item_stmt = (
            select(JobItem)
            .where(JobItem.id == payload.job_item_id)
            .options(selectinload(JobItem.worksite))
        )
        item = (await self.session.execute(item_stmt)).scalar_one_or_none()
        if not item:
            raise AppError(code="NOT_FOUND", message=f"Job item {payload.job_item_id} not found.", status_code=404)

        # Determine sequence if not provided
        target_seq = payload.sequence
        if target_seq is None:
            seq_stmt = (
                select(func.coalesce(func.max(ScheduledWork.sequence), 0))
                .where(
                    ScheduledWork.employee_id == payload.employee_id,
                    ScheduledWork.work_date == payload.work_date,
                    ScheduledWork.status == "ACTIVE",
                )
            )
            max_seq = (await self.session.execute(seq_stmt)).scalar() or 0
            target_seq = int(max_seq) + 1

        sw = ScheduledWork(
            employee_id=payload.employee_id,
            work_date=payload.work_date,
            occurrence_id=payload.occurrence_id,
            job_item_id=payload.job_item_id,
            worksite_id=item.worksite_id,
            assigned_hours=payload.assigned_hours,
            sequence=target_seq,
            status="ACTIVE",
            source=payload.source,
            created_by_user_id=current_user_id,
            version=1,
        )
        self.session.add(sw)
        await self.session.flush()

        await AuditService.log_action(
            session=self.session,
            action="CREATE",
            entity_type="ScheduledWork",
            entity_id=str(sw.id),
            actor_user_id=current_user_id,
            diff={
                "employee_id": str(payload.employee_id),
                "job_item_id": str(payload.job_item_id),
                "work_date": payload.work_date.isoformat(),
                "assigned_hours": str(payload.assigned_hours),
            },
        )

        emp = await self.session.get(Employee, sw.employee_id)

        return ScheduledWorkRead(
            id=sw.id,
            employee_id=sw.employee_id,
            employee_name=emp.name if emp else None,
            work_date=sw.work_date,
            occurrence_id=sw.occurrence_id,
            job_item_id=sw.job_item_id,
            worksite_id=sw.worksite_id,
            job_number=item.worksite.job_number,
            sub_item_code=item.sub_item_code,
            assigned_hours=sw.assigned_hours,
            sequence=sw.sequence,
            status=sw.status,
            source=sw.source,
            version=sw.version,
            created_at=sw.created_at,
        )

    async def update_scheduled_work(
        self,
        scheduled_work_id: UUID,
        payload: ScheduledWorkUpdate,
        current_user_id: UUID,
        is_admin: bool = False,
    ) -> ScheduledWorkRead:
        """Update or cancel scheduled work with optimistic locking."""
        sw = await self.session.get(
            ScheduledWork,
            scheduled_work_id,
            options=[
                selectinload(ScheduledWork.employee),
                selectinload(ScheduledWork.job_item).selectinload(JobItem.worksite),
            ],
        )
        if not sw:
            raise AppError(code="NOT_FOUND", message=f"Scheduled work {scheduled_work_id} not found.", status_code=404)

        if sw.version != payload.version:
            raise AppError(code="CONFLICT", message="Record has been modified by another user. Please reload.", status_code=409)

        if payload.status:
            sw.status = payload.status
        if payload.assigned_hours is not None:
            sw.assigned_hours = payload.assigned_hours
        if payload.sequence is not None:
            sw.sequence = payload.sequence

        sw.version += 1
        sw.updated_at = datetime.now(UTC)

        await self.session.flush()

        await AuditService.log_action(
            session=self.session,
            action="UPDATE",
            entity_type="ScheduledWork",
            entity_id=str(sw.id),
            actor_user_id=current_user_id,
            diff={
                "status": sw.status,
                "assigned_hours": str(sw.assigned_hours),
                "sequence": sw.sequence,
            },
        )

        return ScheduledWorkRead(
            id=sw.id,
            employee_id=sw.employee_id,
            employee_name=sw.employee.name if sw.employee else None,
            work_date=sw.work_date,
            occurrence_id=sw.occurrence_id,
            job_item_id=sw.job_item_id,
            worksite_id=sw.worksite_id,
            job_number=sw.job_item.worksite.job_number if sw.job_item else None,
            sub_item_code=sw.job_item.sub_item_code if sw.job_item else None,
            assigned_hours=sw.assigned_hours,
            sequence=sw.sequence,
            status=sw.status,
            source=sw.source,
            version=sw.version,
            created_at=sw.created_at,
        )

    async def reorder_scheduled_work(
        self,
        payload: ScheduledWorkReorderRequest,
        current_user_id: UUID,
    ) -> list[ScheduledWorkRead]:
        """Reorder daily visit sequence using two-step update to prevent unique constraint collisions."""
        stmt = (
            select(ScheduledWork)
            .where(
                ScheduledWork.employee_id == payload.employee_id,
                ScheduledWork.work_date == payload.work_date,
                ScheduledWork.status == "ACTIVE",
            )
            .options(
                selectinload(ScheduledWork.employee),
                selectinload(ScheduledWork.job_item).selectinload(JobItem.worksite),
            )
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        row_map = {r.id: r for r in rows}

        for target_id in payload.ordered_ids:
            if target_id not in row_map:
                raise AppError(code="NOT_FOUND", message=f"Scheduled work {target_id} not found on target date.", status_code=404)

        # Step 1: Temporarily offset sequences to avoid collision
        for idx, target_id in enumerate(payload.ordered_ids, start=1):
            row_map[target_id].sequence = 1000 + idx
        await self.session.flush()

        # Step 2: Set final positive sequence numbers
        for idx, target_id in enumerate(payload.ordered_ids, start=1):
            row_map[target_id].sequence = idx
            row_map[target_id].version += 1
        await self.session.flush()

        await AuditService.log_action(
            session=self.session,
            action="UPDATE",
            entity_type="ScheduledWorkReorder",
            entity_id=str(payload.employee_id),
            actor_user_id=current_user_id,
            diff={"work_date": payload.work_date.isoformat(), "order": [str(x) for x in payload.ordered_ids]},
        )

        return [
            ScheduledWorkRead(
                id=r.id,
                employee_id=r.employee_id,
                employee_name=r.employee.name if r.employee else None,
                work_date=r.work_date,
                occurrence_id=r.occurrence_id,
                job_item_id=r.job_item_id,
                worksite_id=r.worksite_id,
                job_number=r.job_item.worksite.job_number if r.job_item else None,
                sub_item_code=r.job_item.sub_item_code if r.job_item else None,
                assigned_hours=r.assigned_hours,
                sequence=r.sequence,
                status=r.status,
                source=r.source,
                version=r.version,
                created_at=r.created_at,
            )
            for r in rows
        ]

    # -------------------------------------------------------------------------
    # Candidate Recommendations (DEC-52)
    # -------------------------------------------------------------------------

    async def get_candidate_recommendations(
        self,
        occurrence_id: UUID | None = None,
        job_item_id: UUID | None = None,
        target_date: date | None = None,
    ) -> list[CandidateRecommendationRead]:
        """Rank worker candidates for a job assignment."""
        if occurrence_id:
            occ_stmt = (
                select(JobOccurrence)
                .where(JobOccurrence.id == occurrence_id)
                .options(selectinload(JobOccurrence.job_item).selectinload(JobItem.worksite))
            )
            occ = (await self.session.execute(occ_stmt)).scalar_one_or_none()
            if not occ:
                raise AppError(code="NOT_FOUND", message=f"Job occurrence {occurrence_id} not found.", status_code=404)
            item = occ.job_item
            t_date = target_date or occ.due_date or occ.window_start
            req_hours = occ.required_hours_per_staff
        elif job_item_id:
            item_stmt = (
                select(JobItem)
                .where(JobItem.id == job_item_id)
                .options(selectinload(JobItem.worksite))
            )
            item = (await self.session.execute(item_stmt)).scalar_one_or_none()
            if not item:
                raise AppError(code="NOT_FOUND", message=f"Job item {job_item_id} not found.", status_code=404)
            t_date = target_date or date.today()
            req_hours = item.hours_per_occurrence_per_staff
        else:
            raise AppError(code="VALIDATION_ERROR", message="Either occurrence_id or job_item_id must be provided.", status_code=422)

        job_target = TargetJobItem(
            job_item_id=str(item.id),
            worksite_id=str(item.worksite_id),
            planned_grade_code=item.planned_grade_code,
            staff_grade_description=item.staff_grade_description,
            deployment_type=item.deployment_type,
            required_hours=req_hours,
        )

        # Fetch active workers in country (excluding Admin system users)
        emp_stmt = select(Employee).where(
            Employee.country == item.worksite.country,
            Employee.is_active.is_(True),
            Employee.role != "ADMIN",
            Employee.tally_id != "ADMIN001",
        )
        employees = (await self.session.execute(emp_stmt)).scalars().all()

        budget_staff_types = await self.get_budget_only_staff_types(item.worksite.country)

        # Weekly date range around t_date (Mon-Sun)
        week_start = t_date - timedelta(days=t_date.weekday())
        week_end = week_start + timedelta(days=6)

        # Query all scheduled work for these employees this week
        sw_stmt = (
            select(ScheduledWork)
            .options(selectinload(ScheduledWork.job_item))
            .where(
                ScheduledWork.work_date >= week_start,
                ScheduledWork.work_date <= week_end,
                ScheduledWork.status == "ACTIVE",
            )
        )
        all_sw = (await self.session.execute(sw_stmt)).scalars().all()
        emp_weekly_hours: dict[UUID, Decimal] = {}
        emp_today_hours: dict[UUID, Decimal] = {}
        emp_today_assignments: dict[UUID, list[ScheduledWork]] = defaultdict(list)
        for sw_row in all_sw:
            emp_weekly_hours[sw_row.employee_id] = (
                emp_weekly_hours.get(sw_row.employee_id, Decimal("0")) + sw_row.assigned_hours
            )
            if sw_row.work_date == t_date:
                emp_today_hours[sw_row.employee_id] = (
                    emp_today_hours.get(sw_row.employee_id, Decimal("0")) + sw_row.assigned_hours
                )
                emp_today_assignments[sw_row.employee_id].append(sw_row)

        # Check who worked at this site in the last 14 days or is scheduled on this site this week
        two_weeks_ago = t_date - timedelta(days=14)
        recent_site_stmt = select(ScheduledWork.employee_id).where(
            ScheduledWork.worksite_id == item.worksite_id,
            ScheduledWork.work_date >= two_weeks_ago,
            ScheduledWork.work_date <= week_end,
            ScheduledWork.status == "ACTIVE",
        ).distinct()
        recent_emp_ids = set((await self.session.execute(recent_site_stmt)).scalars().all())

        # Find active supervisors on this site (crew currently assigned or recent on this worksite)
        active_site_supervisors: set[UUID] = set()
        if recent_emp_ids:
            site_sup_stmt = select(EmployeeReportingLine.manager_id).where(
                EmployeeReportingLine.employee_id.in_(recent_emp_ids),
                EmployeeReportingLine.relationship == "SUPERVISOR",
            ).distinct()
            active_site_supervisors = set((await self.session.execute(site_sup_stmt)).scalars().all())

        # Load supervisor information for all candidate employees
        reporting_stmt = (
            select(EmployeeReportingLine.employee_id, EmployeeReportingLine.manager_id, Employee.name)
            .join(Employee, EmployeeReportingLine.manager_id == Employee.id)
            .where(EmployeeReportingLine.relationship == "SUPERVISOR")
        )
        rep_rows = (await self.session.execute(reporting_stmt)).all()
        emp_to_supervisor: dict[UUID, tuple[UUID, str]] = {
            r[0]: (r[1], r[2]) for r in rep_rows
        }
        supervisors_with_subordinates = {r[1] for r in rep_rows}

        candidate_ids = [emp.id for emp in employees]
        base_std_map = await self.get_employees_base_standard_hours(candidate_ids, t_date)

        candidates: list[CandidateWorker] = []
        for emp in employees:
            is_budget = (emp.staff_grade_description or "").strip().lower() in budget_staff_types
            base_std = base_std_map.get(emp.id, Decimal("8.0"))

            sup_info = emp_to_supervisor.get(emp.id)
            if sup_info:
                sup_id = sup_info[0]
                sup_name = sup_info[1]
            elif (
                emp.id in supervisors_with_subordinates
                or emp.role == "SUPERVISOR"
                or "supervisor" in (emp.staff_grade_description or "").lower()
            ):
                sup_id = emp.id
                sup_name = f"{emp.name} (Crew Lead)"
            else:
                sup_id = None
                sup_name = None

            is_same_site_group = bool(sup_id and sup_id in active_site_supervisors)

            today_sw_list = emp_today_assignments.get(emp.id, [])
            has_permanent_today = any(
                sw.job_item and sw.job_item.deployment_type.upper() == "PERMANENT"
                for sw in today_sw_list
            )
            has_any_today = len(today_sw_list) > 0

            is_blocked = False
            blocked_reason: str | None = None

            if item.deployment_type.upper() == "PERMANENT" and has_any_today:
                other_item = today_sw_list[0].job_item
                other_code = other_item.sub_item_code if other_item else "another job"
                other_desc = f" ({other_item.staff_grade_description})" if other_item else ""
                is_blocked = True
                blocked_reason = f"Already assigned to {other_code}{other_desc} today (PERMANENT exclusivity)"
            elif item.deployment_type.upper() == "REMOTE" and has_permanent_today:
                perm_item = next((sw.job_item for sw in today_sw_list if sw.job_item and sw.job_item.deployment_type.upper() == "PERMANENT"), None)
                perm_code = perm_item.sub_item_code if perm_item else "PERMANENT"
                is_blocked = True
                blocked_reason = f"Already assigned to PERMANENT job {perm_code} today"

            candidates.append(
                CandidateWorker(
                    employee_id=str(emp.id),
                    name=emp.name,
                    tally_id=emp.tally_id,
                    is_active=emp.is_active,
                    join_date=emp.join_date,
                    employment_end_date=emp.employment_end_date,
                    grade_code=emp.grade_code,
                    staff_grade_description=emp.staff_grade_description,
                    weekly_off_day=emp.weekly_off_day,
                    standard_hours=base_std,
                    is_on_leave=False,
                    is_budget_only=is_budget,
                    worked_at_site_recently=emp.id in recent_emp_ids,
                    shares_supervisor=is_same_site_group,
                    weekly_allocated_hours=emp_weekly_hours.get(emp.id, Decimal("0.0")),
                    today_allocated_hours=emp_today_hours.get(emp.id, Decimal("0.0")),
                    supervisor_id=str(sup_id) if sup_id else None,
                    supervisor_name=sup_name,
                    is_blocked=is_blocked,
                    blocked_reason=blocked_reason,
                )
            )

        ranked = rank_candidates_for_job(candidates, job_target, t_date)

        return [
            CandidateRecommendationRead(
                employee_id=UUID(sc.worker.employee_id),
                name=sc.worker.name,
                tally_id=sc.worker.tally_id,
                grade_code=sc.worker.grade_code,
                staff_grade_description=sc.worker.staff_grade_description,
                weekly_off_day=sc.worker.weekly_off_day,
                standard_hours=sc.worker.standard_hours,
                exact_staff_type_match=sc.exact_staff_type_match,
                ranking_score=sc.ranking_score,
                reasons=sc.reasons,
                warnings=sc.warnings,
                today_allocated_hours=sc.worker.today_allocated_hours,
                weekly_allocated_hours=sc.worker.weekly_allocated_hours,
                monthly_allocated_hours=sc.worker.weekly_allocated_hours * Decimal("4"),
                supervisor_id=UUID(sc.supervisor_id) if sc.supervisor_id else None,
                supervisor_name=sc.supervisor_name,
                shares_site_group=sc.shares_site_group,
                is_blocked=sc.is_blocked,
                blocked_reason=sc.blocked_reason,
            )
            for sc in ranked
        ]

    # -------------------------------------------------------------------------
    # Allocation Endpoint (Feeds Side Panel)
    # -------------------------------------------------------------------------

    async def get_worker_allocation(
        self, employee_id: UUID, work_date: date | None = None
    ) -> WorkerAllocationResponse:
        """Fetch worker capacity allocation for today, this week, and this month."""
        emp = await self.session.get(Employee, employee_id)
        if not emp:
            raise AppError(code="NOT_FOUND", message=f"Employee {employee_id} not found.", status_code=404)

        t_date = work_date or date.today()
        eff_hours = await self.get_effective_standard_hours(emp, t_date)

        # Date boundaries
        week_start = t_date - timedelta(days=t_date.weekday())
        week_end = week_start + timedelta(days=6)
        month_start = date(t_date.year, t_date.month, 1)
        next_month = date(t_date.year + 1, 1, 1) if t_date.month == 12 else date(t_date.year, t_date.month + 1, 1)
        month_end = next_month - timedelta(days=1)

        # Aggregate hours
        today_stmt = select(func.coalesce(func.sum(ScheduledWork.assigned_hours), 0)).where(
            ScheduledWork.employee_id == employee_id,
            ScheduledWork.work_date == t_date,
            ScheduledWork.status == "ACTIVE",
        )
        today_h = Decimal(str((await self.session.execute(today_stmt)).scalar()))

        week_stmt = select(func.coalesce(func.sum(ScheduledWork.assigned_hours), 0)).where(
            ScheduledWork.employee_id == employee_id,
            ScheduledWork.work_date >= week_start,
            ScheduledWork.work_date <= week_end,
            ScheduledWork.status == "ACTIVE",
        )
        week_h = Decimal(str((await self.session.execute(week_stmt)).scalar()))

        month_stmt = select(func.coalesce(func.sum(ScheduledWork.assigned_hours), 0)).where(
            ScheduledWork.employee_id == employee_id,
            ScheduledWork.work_date >= month_start,
            ScheduledWork.work_date <= month_end,
            ScheduledWork.status == "ACTIVE",
        )
        month_h = Decimal(str((await self.session.execute(month_stmt)).scalar()))

        summary = calculate_allocation_summary(
            today_allocated=today_h,
            week_allocated=week_h,
            month_allocated=month_h,
            effective_hours=eff_hours,
        )

        return WorkerAllocationResponse(
            employee_id=emp.id,
            employee_name=emp.name,
            base_standard_hours=eff_hours.base_standard_hours,
            effective_daily_standard_hours=eff_hours.effective_daily_standard_hours,
            today_allocated_hours=summary.today_allocated,
            today_standard_hours=summary.today_standard,
            today_diff=summary.today_diff,
            today_is_over=summary.today_is_over,
            today_is_under=summary.today_is_under,
            week_allocated_hours=summary.week_allocated,
            week_standard_hours=summary.week_standard,
            week_diff=summary.week_diff,
            week_is_over=summary.week_is_over,
            week_is_under=summary.week_is_under,
            month_allocated_hours=summary.month_allocated,
            month_standard_hours=summary.month_standard,
            month_diff=summary.month_diff,
            month_is_over=summary.month_is_over,
            month_is_under=summary.month_is_under,
        )

    # -------------------------------------------------------------------------
    # Weekly Roster & Excel Export
    # -------------------------------------------------------------------------

    async def get_weekly_roster(
        self,
        week_start: date,
        supervisor_id: UUID | None = None,
        engineer_id: UUID | None = None,
        group_id: UUID | None = None,
        staff_type: str | None = None,
        grade_group: str | None = None,
        problems_only: bool = False,
    ) -> RosterResponse:
        """Fetch weekly roster grid (Workers x Days) with site chips and day markers."""
        week_end = week_start + timedelta(days=6)

        # Fetch employees matching scope and filters (excluding Admin system users)
        emp_stmt = (
            select(Employee)
            .where(
                Employee.is_active.is_(True),
                Employee.role != "ADMIN",
                Employee.tally_id != "ADMIN001",
            )
            .options(selectinload(Employee.accommodation))
        )
        if staff_type:
            emp_stmt = emp_stmt.where(Employee.staff_grade_description.ilike(f"%{staff_type}%"))
        if grade_group:
            emp_stmt = emp_stmt.where(Employee.grade_code.ilike(f"{grade_group}%"))

        employees = (await self.session.execute(emp_stmt)).scalars().all()

        # Query all active scheduled work for the week
        sw_stmt = (
            select(ScheduledWork)
            .where(
                ScheduledWork.work_date >= week_start,
                ScheduledWork.work_date <= week_end,
                ScheduledWork.status == "ACTIVE",
            )
            .options(
                selectinload(ScheduledWork.job_item),
                selectinload(ScheduledWork.worksite),
            )
            .order_by(ScheduledWork.sequence)
        )
        scheduled_rows = (await self.session.execute(sw_stmt)).scalars().all()

        # Map scheduled work by (employee_id, work_date)
        sw_by_emp_date: dict[tuple[UUID, date], list[ScheduledWork]] = {}
        for r in scheduled_rows:
            key = (r.employee_id, r.work_date)
            sw_by_emp_date.setdefault(key, []).append(r)

        # Public holidays for AE and SA
        holidays_ae = await self.get_public_holidays("AE", week_start, week_end)
        holidays_sa = await self.get_public_holidays("SA", week_start, week_end)

        # Batch-fetch base standard hours for all employees
        emp_ids = [e.id for e in employees]
        base_hours_by_emp = await self.get_employees_base_standard_hours(emp_ids, week_start)

        # Map supervisor reporting lines for all employees
        reporting_stmt = (
            select(EmployeeReportingLine.employee_id, EmployeeReportingLine.manager_id, Employee.name)
            .join(Employee, EmployeeReportingLine.manager_id == Employee.id)
            .where(EmployeeReportingLine.relationship == "SUPERVISOR")
        )
        rep_rows = (await self.session.execute(reporting_stmt)).all()
        emp_to_supervisor: dict[UUID, tuple[UUID, str]] = {
            r[0]: (r[1], r[2]) for r in rep_rows
        }
        supervisors_with_subordinates = {r[1] for r in rep_rows}

        # Batch-fetch active time rules for all relevant countries
        unique_countries = {emp.country for emp in employees if emp.country}
        time_rules_by_country: dict[str, list[TimeRuleDefinition]] = {}
        if unique_countries:
            tr_stmt = select(TimeRule).where(
                TimeRule.country.in_(unique_countries),
                TimeRule.is_active.is_(True),
                TimeRule.start_date <= week_start,
                sa.or_(TimeRule.end_date.is_(None), TimeRule.end_date >= week_start),
            )
            time_rules_db = (await self.session.execute(tr_stmt)).scalars().all()
            for tr in time_rules_db:
                tr_def = TimeRuleDefinition(
                    id=tr.id,
                    name=tr.name,
                    country=tr.country,
                    scope_type=TimeRuleScope(tr.scope_type),
                    scope_employee_id=tr.scope_employee_id,
                    applies_to=TimeRuleAppliesTo(tr.applies_to),
                    start_date=tr.start_date,
                    end_date=tr.end_date,
                    standard_hours_change_minutes=tr.standard_hours_change_minutes,
                    is_active=tr.is_active,
                )
                if tr.country:
                    time_rules_by_country.setdefault(tr.country, []).append(tr_def)

        worker_rows: list[RosterWorkerRow] = []

        for emp in employees:
            holidays = holidays_ae if emp.country == "AE" else holidays_sa
            base_hours = base_hours_by_emp.get(emp.id, Decimal("8.0"))
            definitions = time_rules_by_country.get(emp.country, [])
            worker_ctx = WorkerContext(
                employee_id=emp.id,
                country=emp.country,
                has_accommodation=bool(emp.accommodation_id),
                is_driver=emp.is_driver,
            )
            resolved = resolve_time_schedule(
                rules=definitions,
                worker=worker_ctx,
                target_date=week_start,
                is_outdoor=True,
            )
            eff_hours = compute_effective_standard_hours(
                base_standard_hours=base_hours,
                adjustment_minutes=resolved.standard_hours_change_minutes,
            )
            daily_std = eff_hours.effective_daily_standard_hours

            days: list[RosterDayCell] = []
            week_allocated = Decimal("0.0")

            for day_idx in range(7):
                current_date = week_start + timedelta(days=day_idx)
                weekday_name = INT_TO_WEEKDAY[current_date.weekday()]
                active_sw = sw_by_emp_date.get((emp.id, current_date), [])

                chips: list[RosterSiteChip] = []
                day_total = Decimal("0.0")
                marker: str | None = None

                if active_sw:
                    for s in active_sw:
                        day_total += s.assigned_hours
                        chips.append(
                            RosterSiteChip(
                                scheduled_work_id=s.id,
                                worksite_id=s.worksite_id,
                                job_number=s.worksite.job_number,
                                job_name=s.worksite.job_name,
                                job_item_id=s.job_item_id,
                                sub_item_code=s.job_item.sub_item_code,
                                deployment_type=s.job_item.deployment_type,
                                assigned_hours=s.assigned_hours,
                                sequence=s.sequence,
                                has_boundary=s.worksite.boundary is not None,
                            )
                        )
                else:
                    # Evaluate marker
                    m_ctx = WorkerDayContext(
                        employee_id=str(emp.id),
                        work_date=current_date,
                        weekly_off_day=emp.weekly_off_day,
                        has_active_assignments=False,
                        is_public_holiday=current_date in holidays,
                        is_on_leave=False,
                    )
                    eval_marker = evaluate_worker_day_marker(m_ctx)
                    marker = eval_marker.value if eval_marker else DayMarker.FREE.value

                week_allocated += day_total
                days.append(
                    RosterDayCell(
                        work_date=current_date,
                        weekday=weekday_name,
                        chips=chips,
                        marker=marker,
                        day_total_hours=day_total,
                        is_over_standard=day_total > daily_std,
                        is_under_standard=day_total < daily_std if active_sw else False,
                    )
                )

            week_std = daily_std * Decimal("6")  # 6 working days
            week_over = week_allocated > week_std
            week_under = week_allocated < week_std

            if problems_only and not (week_over or week_under):
                continue

            sup_info = emp_to_supervisor.get(emp.id)
            if sup_info:
                sup_id: UUID | None = sup_info[0]
                sup_name: str | None = sup_info[1]
            elif (
                emp.id in supervisors_with_subordinates
                or emp.role == "SUPERVISOR"
                or "supervisor" in (emp.staff_grade_description or "").lower()
            ):
                sup_id = emp.id
                sup_name = f"{emp.name} (Crew Lead)"
            else:
                sup_id = None
                sup_name = "Direct / Independent Staff"

            worker_rows.append(
                RosterWorkerRow(
                    employee_id=emp.id,
                    name=emp.name,
                    tally_id=emp.tally_id,
                    grade_code=emp.grade_code,
                    staff_grade_description=emp.staff_grade_description,
                    standard_hours=eff_hours.base_standard_hours,
                    effective_daily_standard_hours=daily_std,
                    days=days,
                    week_allocated_hours=week_allocated,
                    week_standard_hours=week_std,
                    week_is_over=week_over,
                    week_is_under=week_under,
                    supervisor_id=sup_id,
                    supervisor_name=sup_name,
                    remarks=f"Transport: {emp.accommodation.name}" if emp.accommodation else "Standard Transport",
                )
            )

        return RosterResponse(
            week_start=week_start,
            week_end=week_end,
            total_workers=len(worker_rows),
            workers=worker_rows,
        )

    async def export_roster_excel(self, week_start: date) -> bytes:
        """Generate Excel workbook bytes matching client's weekly layout."""
        roster = await self.get_weekly_roster(week_start=week_start)

        excel_rows: list[ExcelRosterWorkerRow] = []
        for w in roster.workers:
            daily_cells: list[ExcelRosterDayCell] = []
            for d in w.days:
                if d.chips:
                    chips_text = ", ".join(
                        [f"{c.job_number} {c.sub_item_code} ({c.assigned_hours:.1f}h)" for c in d.chips]
                    )
                    daily_cells.append(
                        ExcelRosterDayCell(
                            work_date=d.work_date,
                            display_text=chips_text,
                            hours=d.day_total_hours,
                            is_marker=False,
                        )
                    )
                else:
                    daily_cells.append(
                        ExcelRosterDayCell(
                            work_date=d.work_date,
                            display_text=d.marker or "FREE",
                            hours=Decimal("0.0"),
                            is_marker=True,
                        )
                    )

            excel_rows.append(
                ExcelRosterWorkerRow(
                    employee_name=w.name,
                    tally_id=w.tally_id,
                    grade_code=w.grade_code or "",
                    staff_grade_description=w.staff_grade_description or "",
                    standard_hours=w.standard_hours,
                    daily_cells=daily_cells,
                    total_allocated_hours=w.week_allocated_hours,
                    total_standard_hours=w.week_standard_hours,
                    remarks=w.remarks or "",
                )
            )

        return build_roster_excel_bytes(week_start=week_start, worker_rows=excel_rows)

    # -------------------------------------------------------------------------
    # Job Coverage View
    # -------------------------------------------------------------------------

    async def get_coverage_view(
        self, week_start: date, group_id: UUID | None = None
    ) -> CoverageResponse:
        """Fetch job-centred weekly coverage matrix (Worksites > Items > Days)."""
        week_end = week_start + timedelta(days=6)

        # Worksites query
        ws_stmt = (
            select(Worksite)
            .where(Worksite.is_active.is_(True))
            .options(
                selectinload(Worksite.items).selectinload(JobItem.occurrences),
            )
            .order_by(Worksite.job_number)
        )
        if group_id:
            ws_stmt = ws_stmt.where(Worksite.group_id == group_id)

        worksites = (await self.session.execute(ws_stmt)).scalars().all()

        # Query active scheduled work for the week
        sw_stmt = (
            select(ScheduledWork)
            .where(
                ScheduledWork.work_date >= week_start,
                ScheduledWork.work_date <= week_end,
                ScheduledWork.status == "ACTIVE",
            )
            .options(selectinload(ScheduledWork.employee))
        )
        scheduled_rows = (await self.session.execute(sw_stmt)).scalars().all()

        # Query active scheduled work across month boundary for periodic interval tracking
        month_query_start = week_start.replace(day=1)
        next_month = (week_end.replace(day=28) + timedelta(days=5)).replace(day=1)
        month_query_end = next_month - timedelta(days=1)
        sw_month_stmt = (
            select(ScheduledWork.job_item_id, ScheduledWork.work_date)
            .where(
                ScheduledWork.work_date >= month_query_start,
                ScheduledWork.work_date <= month_query_end,
                ScheduledWork.status == "ACTIVE",
            )
        )
        month_sw_rows = (await self.session.execute(sw_month_stmt)).all()
        sw_by_item_month: dict[tuple[UUID, int, int], set[date]] = defaultdict(set)
        for r in month_sw_rows:
            sw_by_item_month[(r[0], r[1].year, r[1].month)].add(r[1])

        # Query active standing assignments to link standing_assignment_id
        standing_stmt = select(
            StandingAssignment.id,
            StandingAssignment.employee_id,
            StandingAssignment.job_item_id,
            StandingAssignment.version,
        ).where(StandingAssignment.is_active.is_(True))
        standing_rows = (await self.session.execute(standing_stmt)).all()
        standing_map: dict[tuple[UUID, UUID], tuple[UUID, int]] = {
            (r[1], r[2]): (r[0], r[3]) for r in standing_rows
        }

        # Map scheduled work by (job_item_id, work_date)
        sw_by_item_date: dict[tuple[UUID, date], list[ScheduledWork]] = {}
        for r in scheduled_rows:
            key = (r.job_item_id, r.work_date)
            sw_by_item_date.setdefault(key, []).append(r)

        site_rows: list[CoverageWorksiteRow] = []

        for site in worksites:
            holidays_map = await self.get_public_holidays_map(site.country, week_start, week_end)
            holidays = set(holidays_map.keys())
            item_rows: list[CoverageItemRow] = []

            for item in site.items:
                if not item.is_active:
                    continue

                freq_unit = item.frequency_unit or "WEEK"
                occ_per_period = float(item.occurrences_per_period or 6.0)
                is_periodic_weekly = freq_unit == "WEEK" and occ_per_period < 6.0
                is_periodic_interval = freq_unit in ("MONTH", "QUARTER", "YEAR")

                # Determine week's target date for unstaffed periodic jobs (prioritize user configured weekday_pattern)
                week_target_date = None
                norm_item_pattern = {str(wp).strip().upper()[:3] for wp in (item.weekday_pattern or []) if wp}
                if norm_item_pattern:
                    for d in range(7):
                        cand_d = week_start + timedelta(days=d)
                        if INT_TO_WEEKDAY[cand_d.weekday()][:3] in norm_item_pattern:
                            week_target_date = cand_d
                            break
                if not week_target_date:
                    # For periodic weekly jobs without an explicit pattern, target is ALWAYS week_start (Monday)
                    week_target_date = week_start

                # Find assigned dates in this week, ordered by:
                # 1. Earliest created_at timestamp (earlier assigned slots retain requirement fulfillment)
                # 2. Calendar date as tie-breaker
                active_week_assigned_dates = [
                    week_start + timedelta(days=d)
                    for d in range(7)
                    if len(sw_by_item_date.get((item.id, week_start + timedelta(days=d)), [])) > 0
                ]

                def date_priority_key(
                    d: date,
                    item_id: UUID = item.id,
                ) -> tuple[datetime, date]:
                    sw_list = sw_by_item_date.get((item_id, d), [])
                    earliest_created = min(
                        (sw.created_at for sw in sw_list if sw.created_at),
                        default=datetime.max.replace(tzinfo=UTC),
                    )
                    return (earliest_created, d)

                week_assigned_dates = sorted(active_week_assigned_dates, key=date_priority_key)

                # Total shifts assigned for this item across the entire week
                total_week_shifts = sum(
                    len(sw_by_item_date.get((item.id, week_start + timedelta(days=d)), []))
                    for d in range(7)
                )

                days: list[CoverageDayCell] = []
                for day_idx in range(7):
                    c_date = week_start + timedelta(days=day_idx)
                    weekday_str = INT_TO_WEEKDAY[c_date.weekday()]

                    holiday_name = holidays_map.get(c_date)
                    is_holiday = holiday_name is not None

                    is_contract_active = (
                        c_date not in holidays
                        and (not item.end_date or c_date <= item.end_date)
                        and c_date >= item.start_date
                    )

                    assigned = sw_by_item_date.get((item.id, c_date), [])
                    assigned_count = len(assigned)
                    is_quota_met = False

                    if is_holiday:
                        required_count = 0
                        is_uncovered = False
                        is_excess = assigned_count > 0
                    elif is_periodic_interval:
                        month_assigned_dates = sorted(list(sw_by_item_month.get(
                            (item.id, c_date.year, c_date.month), set()
                        )))
                        quota = int(occ_per_period)
                        if month_assigned_dates:
                            if c_date in month_assigned_dates:
                                m_idx = month_assigned_dates.index(c_date)
                                if m_idx < quota:
                                    required_count = item.required_staff_count
                                    is_uncovered = assigned_count < required_count
                                    is_excess = assigned_count > required_count
                                else:
                                    required_count = 0
                                    is_uncovered = False
                                    is_excess = True
                            else:
                                required_count = 0
                                is_uncovered = False
                                is_excess = assigned_count > 0
                                is_quota_met = len(month_assigned_dates) >= quota
                        else:
                            # Month is not yet staffed
                            target_occ_date = None
                            for occ in item.occurrences:
                                if occ.window_start <= c_date <= occ.window_end:
                                    target_occ_date = occ.due_date or occ.window_start
                                    break
                            if not target_occ_date:
                                target_occ_date = c_date.replace(day=1)
                            while target_occ_date in holidays:
                                target_occ_date += timedelta(days=1)

                            if c_date == target_occ_date:
                                required_count = item.required_staff_count
                                is_uncovered = assigned_count < required_count
                                is_excess = assigned_count > required_count
                            else:
                                required_count = 0
                                is_uncovered = False
                                is_excess = assigned_count > 0
                    elif is_periodic_weekly:
                        quota = int(occ_per_period)
                        if week_assigned_dates:
                            if c_date in week_assigned_dates:
                                w_idx = week_assigned_dates.index(c_date)
                                if w_idx < quota:
                                    required_count = item.required_staff_count
                                    is_uncovered = assigned_count < required_count
                                    is_excess = assigned_count > required_count
                                else:
                                    required_count = 0
                                    is_uncovered = False
                                    is_excess = True
                            else:
                                required_count = 0
                                is_uncovered = False
                                is_excess = assigned_count > 0
                                is_quota_met = len(week_assigned_dates) >= quota
                        else:
                            # Unstaffed weekly periodic job -> show requirement on target day
                            if c_date == week_target_date:
                                required_count = item.required_staff_count
                                is_uncovered = assigned_count < required_count
                                is_excess = assigned_count > required_count
                            else:
                                required_count = 0
                                is_uncovered = False
                                is_excess = assigned_count > 0
                    else:
                        norm_sched_pattern = (
                            norm_item_pattern
                            if norm_item_pattern
                            else {"MON", "TUE", "WED", "THU", "FRI", "SAT"}
                        )
                        is_scheduled_day = (weekday_str[:3] in norm_sched_pattern) and is_contract_active

                        # Weekly quota in shifts: e.g. 6 days * 1 staff = 6
                        weekly_quota = int(occ_per_period) * item.required_staff_count

                        if is_scheduled_day:
                            required_count = item.required_staff_count
                            is_uncovered = assigned_count < required_count
                            is_excess = assigned_count > required_count
                        else:
                            # Off-day / Sunday assignment
                            if assigned_count > 0:
                                # If total week shifts do not exceed weekly quota (e.g. Sunday shift covering Friday holiday),
                                # this compensatory shift fulfills the weekly requirement and is NOT excess!
                                if total_week_shifts <= weekly_quota:
                                    required_count = min(assigned_count, item.required_staff_count)
                                    is_uncovered = False
                                    is_excess = assigned_count > item.required_staff_count
                                else:
                                    required_count = 0
                                    is_uncovered = False
                                    is_excess = True
                            else:
                                required_count = 0
                                is_uncovered = False
                                is_excess = False

                    assigned_details = [
                        AssignedWorkerSummary(
                            employee_id=a.employee_id,
                            name=a.employee.name if a.employee else "Unknown",
                            tally_id=a.employee.tally_id if a.employee else "",
                            scheduled_work_id=a.id,
                            source=a.source or "DIRECT",
                            standing_assignment_id=(
                                standing_map[(a.employee_id, a.job_item_id)][0]
                                if a.source == "STANDING" and (a.employee_id, a.job_item_id) in standing_map
                                else None
                            ),
                            standing_assignment_version=(
                                standing_map[(a.employee_id, a.job_item_id)][1]
                                if a.source == "STANDING" and (a.employee_id, a.job_item_id) in standing_map
                                else None
                            ),
                        )
                        for a in assigned
                        if a.employee
                    ]

                    days.append(
                        CoverageDayCell(
                            work_date=c_date,
                            weekday=weekday_str,
                            required_staff_count=required_count,
                            assigned_staff_count=assigned_count,
                            is_to_be_covered=is_uncovered,
                            is_excess=is_excess,
                            is_quota_met=is_quota_met,
                            is_holiday=is_holiday,
                            holiday_name=holiday_name,
                            assigned_workers=[a.employee.name for a in assigned if a.employee],
                            assigned_details=assigned_details,
                        )
                    )

                item_rows.append(
                    CoverageItemRow(
                        job_item_id=item.id,
                        sub_item_code=item.sub_item_code,
                        staff_grade_description=item.staff_grade_description,
                        planned_grade_code=item.planned_grade_code,
                        deployment_type=item.deployment_type,
                        required_staff_count=item.required_staff_count,
                        hours_per_occurrence=item.hours_per_occurrence_per_staff,
                        frequency_unit=item.frequency_unit,
                        occurrences_per_period=item.occurrences_per_period,
                        days=days,
                    )
                )

            if item_rows:
                site_rows.append(
                    CoverageWorksiteRow(
                        worksite_id=site.id,
                        job_number=site.job_number,
                        job_name=site.job_name,
                        customer_type=site.customer_type,
                        is_outdoor=site.is_outdoor,
                        items=item_rows,
                    )
                )

        return CoverageResponse(
            week_start=week_start,
            week_end=week_end,
            worksites=site_rows,
        )

    # -------------------------------------------------------------------------
    # Batch Scheduling and Direct Cancellation Helpers
    # -------------------------------------------------------------------------

    async def create_scheduled_work_batch(
        self,
        payload: ScheduledWorkBatchCreate,
        current_user_id: UUID,
        is_admin: bool = False,
    ) -> list[ScheduledWorkRead]:
        """Batch assign multiple workers to a job item for a date or standing horizon."""
        results: list[ScheduledWorkRead] = []

        item_stmt = (
            select(JobItem)
            .where(JobItem.id == payload.job_item_id)
            .options(
                selectinload(JobItem.worksite),
                selectinload(JobItem.occurrences),
            )
        )
        item = (await self.session.execute(item_stmt)).scalar_one_or_none()
        if not item:
            raise AppError(code="NOT_FOUND", message=f"Job item {payload.job_item_id} not found.", status_code=404)

        assigned_hours = payload.assigned_hours or item.hours_per_occurrence_per_staff

        for emp_id in payload.employee_ids:
            if payload.as_standing_assignment:
                standing_pattern = item.weekday_pattern
                standing_start = payload.work_date
                if item.frequency_unit in ("MONTH", "QUARTER", "YEAR"):
                    standing_pattern = None
                elif item.frequency_unit == "WEEK" and item.occurrences_per_period == 1:
                    standing_pattern = [INT_TO_WEEKDAY[payload.work_date.weekday()]]
                elif item.frequency_unit == "WEEK" or not item.frequency_unit:
                    # Anchor recurring weekly standing team to week's Monday
                    standing_start = payload.work_date - timedelta(days=payload.work_date.weekday())

                standing_req = StandingAssignmentCreate(
                    employee_id=emp_id,
                    job_item_id=payload.job_item_id,
                    start_date=standing_start,
                    weekday_pattern=standing_pattern,
                    hours_per_day=assigned_hours,
                )
                await self.create_standing_assignment(
                    payload=standing_req,
                    current_user_id=current_user_id,
                )
                # Fetch the active ScheduledWork on payload.work_date to return in results
                sw_stmt = (
                    select(ScheduledWork)
                    .where(
                        ScheduledWork.employee_id == emp_id,
                        ScheduledWork.job_item_id == payload.job_item_id,
                        ScheduledWork.work_date == payload.work_date,
                        ScheduledWork.status == "ACTIVE",
                    )
                    .options(
                        selectinload(ScheduledWork.employee),
                        selectinload(ScheduledWork.job_item).selectinload(JobItem.worksite),
                    )
                )
                sw_row = (await self.session.execute(sw_stmt)).scalar_one_or_none()
                if sw_row:
                    results.append(
                        ScheduledWorkRead(
                            id=sw_row.id,
                            employee_id=sw_row.employee_id,
                            employee_name=sw_row.employee.name if sw_row.employee else None,
                            work_date=sw_row.work_date,
                            occurrence_id=sw_row.occurrence_id,
                            job_item_id=sw_row.job_item_id,
                            worksite_id=sw_row.worksite_id,
                            job_number=sw_row.job_item.worksite.job_number if sw_row.job_item else None,
                            sub_item_code=sw_row.job_item.sub_item_code if sw_row.job_item else None,
                            assigned_hours=sw_row.assigned_hours,
                            sequence=sw_row.sequence,
                            status=sw_row.status,
                            source=sw_row.source,
                            version=sw_row.version,
                            created_at=sw_row.created_at,
                        )
                    )
                else:
                    # If recurring expansion skipped payload.work_date (e.g. Sunday shift to cover Friday holiday),
                    # create the direct ScheduledWork record on payload.work_date so the user's explicit action is fulfilled
                    sw_req = ScheduledWorkCreate(
                        employee_id=emp_id,
                        job_item_id=payload.job_item_id,
                        work_date=payload.work_date,
                        occurrence_id=payload.occurrence_id,
                        assigned_hours=assigned_hours,
                        acknowledge_warnings=True,
                    )
                    created_sw = await self.create_scheduled_work(
                        payload=sw_req,
                        current_user_id=current_user_id,
                        is_admin=is_admin,
                    )
                    results.append(created_sw)
            else:
                sw_req = ScheduledWorkCreate(
                    employee_id=emp_id,
                    job_item_id=payload.job_item_id,
                    work_date=payload.work_date,
                    occurrence_id=payload.occurrence_id,
                    assigned_hours=assigned_hours,
                    acknowledge_warnings=payload.acknowledge_warnings,
                )
                created = await self.create_scheduled_work(
                    payload=sw_req,
                    current_user_id=current_user_id,
                    is_admin=is_admin,
                )
                results.append(created)

        return results

    async def cancel_scheduled_work(
        self,
        scheduled_work_id: UUID,
        current_user_id: UUID,
    ) -> None:
        """Cancel an individual daily scheduled work record."""
        sw = await self.session.get(ScheduledWork, scheduled_work_id)
        if not sw or sw.status != "ACTIVE":
            return
        sw.status = "CANCELLED"
        sw.version += 1
        sw.updated_at = datetime.now(UTC)

        await AuditService.log_action(
            session=self.session,
            action="CANCEL",
            entity_type="ScheduledWork",
            entity_id=str(sw.id),
            actor_user_id=current_user_id,
            diff={"status": "CANCELLED"},
        )

    # -------------------------------------------------------------------------
    # Base Planner (Blueprint Recurring Engine)
    # -------------------------------------------------------------------------

    async def get_base_planner_worksites(
        self, group_id: UUID | None = None
    ) -> BasePlannerResponse:
        """Fetch worksites and job items with active base roster templates for the Base Planner."""
        ws_stmt = (
            select(Worksite)
            .where(Worksite.is_active.is_(True))
            .options(
                selectinload(Worksite.items),
            )
            .order_by(Worksite.job_number)
        )
        if group_id:
            ws_stmt = ws_stmt.where(Worksite.group_id == group_id)

        worksites = (await self.session.execute(ws_stmt)).scalars().all()

        # Collect all active job item IDs
        job_item_ids = [
            it.id for ws in worksites for it in ws.items if it.is_active
        ]

        # Query all active base roster templates for these items
        templates_by_item: dict[UUID, BaseRosterTemplate] = {}
        if job_item_ids:
            tmpl_stmt = (
                select(BaseRosterTemplate)
                .where(
                    BaseRosterTemplate.job_item_id.in_(job_item_ids),
                    BaseRosterTemplate.is_active.is_(True),
                )
                .options(selectinload(BaseRosterTemplate.entries))
            )
            templates = (await self.session.execute(tmpl_stmt)).scalars().all()
            for t in templates:
                templates_by_item[t.job_item_id] = t

        # Collect all employee IDs across templates to fetch names & tally IDs in bulk
        emp_ids = {
            entry.employee_id
            for t in templates_by_item.values()
            for entry in t.entries
        }
        emp_map: dict[UUID, Employee] = {}
        if emp_ids:
            emp_stmt = select(Employee).where(Employee.id.in_(emp_ids))
            emp_map = {e.id: e for e in (await self.session.execute(emp_stmt)).scalars().all()}

        ws_rows: list[BasePlannerWorksiteRow] = []
        for ws in worksites:
            active_items = [it for it in ws.items if it.is_active]
            if not active_items:
                continue

            item_rows: list[BasePlannerItemRow] = []
            for it in sorted(active_items, key=lambda x: x.sub_item_code):
                tmpl = templates_by_item.get(it.id)
                tmpl_read: BaseRosterTemplateRead | None = None
                if tmpl:
                    entry_reads = [
                        BaseRosterEntryRead(
                            id=e.id,
                            template_id=e.template_id,
                            employee_id=e.employee_id,
                            employee_name=emp_map.get(e.employee_id).name if e.employee_id in emp_map else None,
                            tally_id=emp_map.get(e.employee_id).tally_id if e.employee_id in emp_map else None,
                            weekly_off_day=emp_map.get(e.employee_id).weekly_off_day if e.employee_id in emp_map else None,
                            weekday_mask=e.weekday_mask,
                            assigned_hours=e.assigned_hours,
                            sequence=e.sequence,
                        )
                        for e in sorted(tmpl.entries, key=lambda x: (x.weekday_mask, x.sequence))
                    ]
                    tmpl_read = BaseRosterTemplateRead(
                        id=tmpl.id,
                        job_item_id=tmpl.job_item_id,
                        allocation_mode=tmpl.allocation_mode,
                        start_date=tmpl.start_date,
                        end_date=tmpl.end_date,
                        is_active=tmpl.is_active,
                        version=tmpl.version,
                        entries=entry_reads,
                    )

                item_rows.append(
                    BasePlannerItemRow(
                        job_item_id=it.id,
                        sub_item_code=it.sub_item_code,
                        staff_grade_description=it.staff_grade_description,
                        planned_grade_code=it.planned_grade_code,
                        deployment_type=it.deployment_type,
                        required_staff_count=it.required_staff_count,
                        hours_per_occurrence=it.hours_per_occurrence_per_staff,
                        frequency_unit=it.frequency_unit,
                        occurrences_per_period=it.occurrences_per_period,
                        weekday_pattern=it.weekday_pattern,
                        start_date=it.start_date,
                        end_date=it.end_date,
                        template=tmpl_read,
                    )
                )

            ws_rows.append(
                BasePlannerWorksiteRow(
                    worksite_id=ws.id,
                    job_number=ws.job_number,
                    job_name=ws.job_name,
                    customer_type=ws.customer_type,
                    is_outdoor=ws.is_outdoor,
                    start_date=ws.start_date,
                    end_date=ws.end_date,
                    budget_amount=ws.budget_amount,
                    items=item_rows,
                )
            )

        return BasePlannerResponse(worksites=ws_rows)

    async def get_base_template(self, job_item_id: UUID) -> BaseRosterTemplateRead | None:
        """Fetch the active Base Roster Template for a specific job item."""
        stmt = (
            select(BaseRosterTemplate)
            .where(
                BaseRosterTemplate.job_item_id == job_item_id,
                BaseRosterTemplate.is_active.is_(True),
            )
            .options(selectinload(BaseRosterTemplate.entries))
        )
        tmpl = (await self.session.execute(stmt)).scalar_one_or_none()
        if not tmpl:
            return None

        emp_ids = {e.employee_id for e in tmpl.entries}
        emp_map: dict[UUID, Employee] = {}
        if emp_ids:
            emp_stmt = select(Employee).where(Employee.id.in_(emp_ids))
            emp_map = {e.id: e for e in (await self.session.execute(emp_stmt)).scalars().all()}

        entries_read = [
            BaseRosterEntryRead(
                id=e.id,
                template_id=e.template_id,
                employee_id=e.employee_id,
                employee_name=emp_map.get(e.employee_id).name if e.employee_id in emp_map else None,
                tally_id=emp_map.get(e.employee_id).tally_id if e.employee_id in emp_map else None,
                weekly_off_day=emp_map.get(e.employee_id).weekly_off_day if e.employee_id in emp_map else None,
                weekday_mask=e.weekday_mask,
                assigned_hours=e.assigned_hours,
                sequence=e.sequence,
            )
            for e in sorted(tmpl.entries, key=lambda x: (x.weekday_mask, x.sequence))
        ]

        return BaseRosterTemplateRead(
            id=tmpl.id,
            job_item_id=tmpl.job_item_id,
            allocation_mode=tmpl.allocation_mode,
            start_date=tmpl.start_date,
            end_date=tmpl.end_date,
            is_active=tmpl.is_active,
            version=tmpl.version,
            entries=entries_read,
        )

    async def save_base_template(
        self,
        payload: BaseRosterTemplateCreate,
        current_user_id: UUID | None = None,
    ) -> BaseRosterTemplateRead:
        """Create or update the active Base Roster Template for a job item."""
        item = await self.session.get(JobItem, payload.job_item_id)
        if not item:
            raise AppError(code="NOT_FOUND", message=f"Job item {payload.job_item_id} not found", status_code=404)

        # Inactivate existing active templates
        existing_stmt = select(BaseRosterTemplate).where(
            BaseRosterTemplate.job_item_id == payload.job_item_id,
            BaseRosterTemplate.is_active.is_(True),
        )
        existing_templates = (await self.session.execute(existing_stmt)).scalars().all()
        for old_tmpl in existing_templates:
            old_tmpl.is_active = False
            old_tmpl.updated_at = datetime.now(UTC)

        # Create new template
        from uuid import uuid4
        new_template = BaseRosterTemplate(
            id=uuid4(),
            job_item_id=payload.job_item_id,
            allocation_mode=payload.allocation_mode.upper(),
            start_date=payload.start_date,
            end_date=payload.end_date,
            is_active=True,
            version=1,
            created_by_user_id=current_user_id,
        )
        self.session.add(new_template)
        await self.session.flush()

        # Add entries
        for entry in payload.entries:
            new_entry = BaseRosterEntry(
                id=uuid4(),
                template_id=new_template.id,
                employee_id=entry.employee_id,
                weekday_mask=entry.weekday_mask.upper(),
                assigned_hours=entry.assigned_hours,
                sequence=entry.sequence,
            )
            self.session.add(new_entry)

        await self.session.commit()

        await AuditService.log_action(
            session=self.session,
            action="CREATE",
            entity_type="BaseRosterTemplate",
            entity_id=str(new_template.id),
            actor_user_id=current_user_id,
            diff={
                "job_item_id": str(payload.job_item_id),
                "allocation_mode": payload.allocation_mode,
                "entries_count": len(payload.entries),
            },
        )

        return await self.get_base_template(payload.job_item_id)  # type: ignore[return-value]

    # -------------------------------------------------------------------------
    # Operational Planner (Live Calendar, Overrides & Leaves)
    # -------------------------------------------------------------------------

    async def get_operational_coverage(
        self, week_start: date, group_id: UUID | None = None
    ) -> OperationalCoverageResponse:
        """Fetch weekly operational coverage matrix with baseline blueprints and single-day overrides."""
        week_end = week_start + timedelta(days=6)

        # Worksites query
        ws_stmt = (
            select(Worksite)
            .where(Worksite.is_active.is_(True))
            .options(selectinload(Worksite.items))
            .order_by(Worksite.job_number)
        )
        if group_id:
            ws_stmt = ws_stmt.where(Worksite.group_id == group_id)

        worksites = (await self.session.execute(ws_stmt)).scalars().all()

        job_item_ids = [it.id for ws in worksites for it in ws.items if it.is_active]

        # Load active Base Roster Templates
        templates_by_item: dict[UUID, BaseRosterTemplate] = {}
        if job_item_ids:
            tmpl_stmt = (
                select(BaseRosterTemplate)
                .where(
                    BaseRosterTemplate.job_item_id.in_(job_item_ids),
                    BaseRosterTemplate.is_active.is_(True),
                )
                .options(selectinload(BaseRosterTemplate.entries))
            )
            templates = (await self.session.execute(tmpl_stmt)).scalars().all()
            for t in templates:
                templates_by_item[t.job_item_id] = t

        # Load single-day operational shifts for this week
        sw_stmt = (
            select(ScheduledWork)
            .where(
                ScheduledWork.work_date >= week_start,
                ScheduledWork.work_date <= week_end,
                ScheduledWork.status == "ACTIVE",
            )
            .options(selectinload(ScheduledWork.employee))
        )
        sw_rows = (await self.session.execute(sw_stmt)).scalars().all()
        sw_by_item_date: dict[tuple[UUID, date], list[ScheduledWork]] = defaultdict(list)
        sw_by_item_week: dict[UUID, list[ScheduledWork]] = defaultdict(list)
        for s in sw_rows:
            sw_by_item_date[(s.job_item_id, s.work_date)].append(s)
            sw_by_item_week[s.job_item_id].append(s)

        # Load public holidays for the week
        holidays_stmt = select(PublicHoliday).where(
            PublicHoliday.holiday_date >= week_start,
            PublicHoliday.holiday_date <= week_end,
        )
        holiday_rows = (await self.session.execute(holidays_stmt)).scalars().all()
        holidays_by_date: dict[date, PublicHoliday] = {h.holiday_date: h for h in holiday_rows}
        holiday_dates = set(holidays_by_date.keys())

        # Collect all employee IDs across templates and scheduled works to load info
        emp_ids: set[UUID] = set()
        for t in templates_by_item.values():
            for e in t.entries:
                emp_ids.add(e.employee_id)
        for s in sw_rows:
            emp_ids.add(s.employee_id)
            if s.original_employee_id:
                emp_ids.add(s.original_employee_id)

        emp_map: dict[UUID, Employee] = {}
        if emp_ids:
            emp_stmt = select(Employee).where(Employee.id.in_(emp_ids))
            emp_map = {e.id: e for e in (await self.session.execute(emp_stmt)).scalars().all()}

        worker_weekly_off_days = {
            e.id: (e.weekly_off_day or "").upper() for e in emp_map.values()
        }

        # Construct week dates list
        week_dates = [week_start + timedelta(days=i) for i in range(7)]

        ws_rows: list[OperationalWorksiteRow] = []

        for ws in worksites:
            active_items = [it for it in ws.items if it.is_active]
            if not active_items:
                continue

            item_rows: list[OperationalJobItemRow] = []
            for it in sorted(active_items, key=lambda x: x.sub_item_code):
                tmpl = templates_by_item.get(it.id)

                # 1. Resolve blueprint slots for the whole week
                blueprint_entries: list[BlueprintEntry] = []
                if tmpl:
                    blueprint_entries = [
                        BlueprintEntry(
                            employee_id=e.employee_id,
                            weekday_mask=e.weekday_mask,
                            assigned_hours=float(e.assigned_hours),
                            sequence=e.sequence,
                        )
                        for e in tmpl.entries
                    ]

                # Determine job active working days
                job_working_days: set[str] | None = None
                if it.weekday_pattern:
                    job_working_days = {w.upper() for w in it.weekday_pattern}
                elif it.frequency_unit == "WEEK" and int(it.occurrences_per_period) == 6:
                    job_working_days = {"MON", "TUE", "WED", "THU", "FRI", "SAT"}

                resolved_template_slots = resolve_base_template_slots(
                    allocation_mode=tmpl.allocation_mode if tmpl else "UNIFORM",
                    entries=blueprint_entries,
                    target_dates=week_dates,
                    public_holidays=holiday_dates,
                    worker_weekly_off_days=worker_weekly_off_days,
                    job_working_days=job_working_days,
                )
                slots_by_date: dict[date, list[ResolvedTemplateSlot]] = defaultdict(list)
                for slot in resolved_template_slots:
                    slots_by_date[slot.work_date].append(slot)

                # 2. Pacing windows and recommendation
                target_occurrences = int(it.occurrences_per_period) if it.frequency_unit == "WEEK" else 1
                pacing_windows = calculate_pacing_windows(
                    period_start=week_start,
                    period_end=week_end,
                    occurrences=target_occurrences if target_occurrences > 0 else 1,
                    scheduled_weekdays=it.weekday_pattern,
                    public_holidays=holiday_dates,
                )
                recommended_dates = {w.recommended_date for w in pacing_windows}

                # 3. Quota calculation for week
                # Collect all assigned visits (blueprint distinct dates + operational shifts distinct dates)
                all_visit_dates = set(slots_by_date.keys()).union(
                    {s.work_date for s in sw_by_item_week.get(it.id, [])}
                )
                from uuid import uuid4
                visit_records = [
                    VisitRecord(
                        id=uuid4(),
                        work_date=vd,
                        created_at=datetime(vd.year, vd.month, vd.day, tzinfo=UTC),
                    )
                    for vd in sorted(all_visit_dates)
                ]
                quota_result = evaluate_period_quota(
                    target_count=target_occurrences,
                    visits=visit_records,
                    period_start=week_start,
                    period_end=week_end,
                    period_name="Week",
                    windows=pacing_windows,
                )
                quota_status_by_date = {
                    v.work_date: v for v in quota_result.evaluated_visits
                }

                # 4. Resolve daily cells
                day_cells: list[OperationalDayCell] = []
                for d in week_dates:
                    dow = INT_TO_WEEKDAY[d.weekday()]
                    is_holiday = d in holiday_dates
                    holiday_obj = holidays_by_date.get(d)

                    base_slots = slots_by_date.get(d, [])
                    op_shifts_raw = sw_by_item_date.get((it.id, d), [])
                    op_inputs = [
                        OperationalShiftInput(
                            id=s.id,
                            work_date=s.work_date,
                            employee_id=s.employee_id,
                            source=s.source,
                            original_employee_id=s.original_employee_id,
                            override_reason=s.override_reason,
                            assigned_hours=float(s.assigned_hours),
                            sequence=s.sequence,
                        )
                        for s in op_shifts_raw
                    ]

                    # Mock approved leaves for now (until leaves module arrives)
                    approved_leaves: set[UUID] = set()

                    resolved_cell_workers = resolve_operational_cell(
                        work_date=d,
                        base_slots=base_slots,
                        approved_leave_worker_ids=approved_leaves,
                        operational_shifts=op_inputs,
                        is_public_holiday=is_holiday,
                        worker_weekly_off_days=worker_weekly_off_days,
                    )

                    cell_worker_schemas = [
                        OperationalCellWorker(
                            employee_id=w.employee_id,
                            employee_name=emp_map.get(w.employee_id).name if w.employee_id in emp_map else "Unknown",
                            tally_id=emp_map.get(w.employee_id).tally_id if w.employee_id in emp_map else None,
                            assigned_hours=Decimal(str(w.assigned_hours)),
                            display_type=w.display_type,
                            opacity_class=w.opacity_class,
                            original_employee_id=w.original_employee_id,
                            original_employee_name=emp_map.get(w.original_employee_id).name if w.original_employee_id and w.original_employee_id in emp_map else None,
                            shift_id=w.shift_id,
                            reason=w.reason,
                            is_public_holiday=w.is_public_holiday,
                            is_rest_day=w.is_rest_day,
                            tags=w.tags,
                        )
                        for w in resolved_cell_workers
                    ]

                    eval_v = quota_status_by_date.get(d)
                    is_quota_met = eval_v.is_required if eval_v else False
                    is_excess = eval_v.is_excess if eval_v else False
                    is_to_be_covered = any(w.display_type == "TO_BE_COVERED" for w in cell_worker_schemas)

                    req_staff = it.required_staff_count if (d in recommended_dates or is_quota_met) else 0

                    day_cells.append(
                        OperationalDayCell(
                            work_date=d,
                            weekday=dow,
                            required_staff_count=req_staff,
                            assigned_staff_count=len(cell_worker_schemas),
                            is_public_holiday=is_holiday,
                            holiday_name=holiday_obj.name if holiday_obj else None,
                            is_recommended_target=d in recommended_dates,
                            is_quota_met=is_quota_met,
                            is_excess=is_excess,
                            is_to_be_covered=is_to_be_covered,
                            workers=cell_worker_schemas,
                        )
                    )

                item_rows.append(
                    OperationalJobItemRow(
                        job_item_id=it.id,
                        sub_item_code=it.sub_item_code,
                        staff_grade_description=it.staff_grade_description,
                        planned_grade_code=it.planned_grade_code,
                        deployment_type=it.deployment_type,
                        required_staff_count=it.required_staff_count,
                        hours_per_occurrence=it.hours_per_occurrence_per_staff,
                        frequency_unit=it.frequency_unit,
                        occurrences_per_period=it.occurrences_per_period,
                        quota_target=quota_result.target_count,
                        quota_assigned=quota_result.assigned_count,
                        quota_satisfied=quota_result.is_quota_satisfied,
                        days=day_cells,
                    )
                )

            ws_rows.append(
                OperationalWorksiteRow(
                    worksite_id=ws.id,
                    job_number=ws.job_number,
                    job_name=ws.job_name,
                    customer_type=ws.customer_type,
                    is_outdoor=ws.is_outdoor,
                    start_date=ws.start_date,
                    end_date=ws.end_date,
                    budget_amount=ws.budget_amount,
                    items=item_rows,
                )
            )

        return OperationalCoverageResponse(
            week_start=week_start,
            week_end=week_end,
            worksites=ws_rows,
        )

    async def get_operational_roster(
        self, week_start: date, group_id: UUID | None = None
    ) -> OperationalRosterResponse:
        """Fetch weekly operational worker roster showing assignments across the week."""
        week_end = week_start + timedelta(days=6)
        week_dates = [week_start + timedelta(days=i) for i in range(7)]

        emp_stmt = select(Employee).where(Employee.is_active.is_(True)).order_by(Employee.name)
        employees = (await self.session.execute(emp_stmt)).scalars().all()

        # Load holidays
        holidays_stmt = select(PublicHoliday).where(
            PublicHoliday.holiday_date >= week_start,
            PublicHoliday.holiday_date <= week_end,
        )
        holiday_rows = (await self.session.execute(holidays_stmt)).scalars().all()
        holidays_by_date: dict[date, PublicHoliday] = {h.holiday_date: h for h in holiday_rows}
        holiday_dates = set(holidays_by_date.keys())

        # Load single-day operational shifts
        sw_stmt = (
            select(ScheduledWork)
            .where(
                ScheduledWork.work_date >= week_start,
                ScheduledWork.work_date <= week_end,
                ScheduledWork.status == "ACTIVE",
            )
            .options(
                selectinload(ScheduledWork.worksite),
                selectinload(ScheduledWork.job_item),
            )
        )
        sw_rows = (await self.session.execute(sw_stmt)).scalars().all()
        sw_by_emp_date: dict[tuple[UUID, date], list[ScheduledWork]] = defaultdict(list)
        for s in sw_rows:
            sw_by_emp_date[(s.employee_id, s.work_date)].append(s)

        # Load active Base Roster Templates
        tmpl_stmt = (
            select(BaseRosterTemplate)
            .where(BaseRosterTemplate.is_active.is_(True))
            .options(
                selectinload(BaseRosterTemplate.entries),
                selectinload(BaseRosterTemplate.job_item).selectinload(JobItem.worksite),
            )
        )
        active_templates = (await self.session.execute(tmpl_stmt)).scalars().all()

        # Index template entries by employee_id
        templates_by_emp: dict[UUID, list[tuple[BaseRosterTemplate, BaseRosterEntry]]] = defaultdict(list)
        for t in active_templates:
            for e in t.entries:
                templates_by_emp[e.employee_id].append((t, e))

        worker_rows: list[OperationalRosterWorkerRow] = []

        for emp in employees:
            off_dow = (emp.weekly_off_day or "").upper()
            total_week_hours = Decimal("0.0")
            day_cells: list[OperationalRosterDayCell] = []

            for d in week_dates:
                dow = INT_TO_WEEKDAY[d.weekday()]
                is_off = off_dow == dow
                is_holiday = d in holiday_dates
                holiday_obj = holidays_by_date.get(d)

                cell_workers: list[OperationalCellWorker] = []
                day_hours = Decimal("0.0")

                # Check single day operational shifts first
                direct_sw = sw_by_emp_date.get((emp.id, d), [])
                if direct_sw:
                    for s in direct_sw:
                        day_hours += s.assigned_hours
                        cell_workers.append(
                            OperationalCellWorker(
                                employee_id=emp.id,
                                employee_name=emp.name,
                                tally_id=emp.tally_id,
                                assigned_hours=s.assigned_hours,
                                display_type="DIRECT" if not s.original_employee_id else "OVERRIDE",
                                opacity_class="solid",
                                original_employee_id=s.original_employee_id,
                                shift_id=s.id,
                                reason=s.override_reason,
                                is_public_holiday=is_holiday,
                                is_rest_day=is_off,
                                tags=["Direct Shift"] if not s.original_employee_id else ["Cover Shift"],
                            )
                        )
                else:
                    # Check base templates
                    emp_templates = templates_by_emp.get(emp.id, [])
                    for _t, e in emp_templates:
                        if e.weekday_mask in ("ALL", dow):
                            day_hours += e.assigned_hours
                            cell_workers.append(
                                OperationalCellWorker(
                                    employee_id=emp.id,
                                    employee_name=emp.name,
                                    tally_id=emp.tally_id,
                                    assigned_hours=e.assigned_hours,
                                    display_type="BLUEPRINT",
                                    opacity_class="muted",
                                    shift_id=None,
                                    is_public_holiday=is_holiday,
                                    is_rest_day=is_off,
                                    tags=["Base Blueprint"],
                                )
                            )

                total_week_hours += day_hours

                day_cells.append(
                    OperationalRosterDayCell(
                        work_date=d,
                        weekday=dow,
                        is_working_day=not is_off,
                        is_weekly_off=is_off,
                        is_public_holiday=is_holiday,
                        holiday_name=holiday_obj.name if holiday_obj else None,
                        leave_type=None,
                        allocated_hours=day_hours,
                        shifts=cell_workers,
                    )
                )

            worker_rows.append(
                OperationalRosterWorkerRow(
                    employee_id=emp.id,
                    tally_id=emp.tally_id,
                    name=emp.name,
                    staff_grade_description=emp.staff_grade_description,
                    weekly_off_day=emp.weekly_off_day,
                    total_week_hours=total_week_hours,
                    standard_week_hours=Decimal("48.0"),
                    days=day_cells,
                )
            )

        return OperationalRosterResponse(
            week_start=week_start,
            week_end=week_end,
            workers=worker_rows,
        )

    async def create_operational_shift(
        self,
        payload: OperationalShiftCreate,
        current_user_id: UUID | None = None,
    ) -> ScheduledWorkRead:
        """Create a single-day operational shift or replacement cover."""
        item = await self.session.get(JobItem, payload.job_item_id)
        if not item:
            raise AppError(code="NOT_FOUND", message=f"Job item {payload.job_item_id} not found", status_code=404)

        from uuid import uuid4
        assigned_hours = payload.assigned_hours or item.hours_per_occurrence_per_staff

        shift = ScheduledWork(
            id=uuid4(),
            employee_id=payload.employee_id,
            job_item_id=payload.job_item_id,
            worksite_id=item.worksite_id,
            work_date=payload.work_date,
            assigned_hours=assigned_hours,
            sequence=1,
            status="ACTIVE",
            source=payload.source.upper(),
            original_employee_id=payload.original_employee_id,
            override_reason=payload.override_reason,
            created_by_user_id=current_user_id,
            version=1,
        )
        self.session.add(shift)
        await self.session.commit()

        await AuditService.log_action(
            session=self.session,
            action="CREATE",
            entity_type="ScheduledWork",
            entity_id=str(shift.id),
            actor_user_id=current_user_id,
            diff={
                "job_item_id": str(payload.job_item_id),
                "employee_id": str(payload.employee_id),
                "work_date": str(payload.work_date),
                "source": payload.source,
                "original_employee_id": str(payload.original_employee_id) if payload.original_employee_id else None,
            },
        )

        emp = await self.session.get(Employee, payload.employee_id)
        return ScheduledWorkRead(
            id=shift.id,
            employee_id=shift.employee_id,
            employee_name=emp.name if emp else None,
            work_date=shift.work_date,
            occurrence_id=shift.occurrence_id,
            job_item_id=shift.job_item_id,
            worksite_id=shift.worksite_id,
            assigned_hours=shift.assigned_hours,
            sequence=shift.sequence,
            status=shift.status,
            source=shift.source,
            version=shift.version,
            created_at=shift.created_at,
        )

    async def delete_operational_shift(
        self,
        shift_id: UUID,
        current_user_id: UUID | None = None,
    ) -> None:
        """Cancel an operational shift."""
        shift = await self.session.get(ScheduledWork, shift_id)
        if not shift:
            return
        shift.status = "CANCELLED"
        shift.version += 1
        shift.updated_at = datetime.now(UTC)
        await self.session.commit()

        await AuditService.log_action(
            session=self.session,
            action="CANCEL",
            entity_type="ScheduledWork",
            entity_id=str(shift_id),
            actor_user_id=current_user_id,
            diff={"status": "CANCELLED"},
        )

