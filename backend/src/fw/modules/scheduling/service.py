"""SchedulingService orchestrating standing assignments, daily scheduled work, roster, and coverage."""

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
from fw.modules.org import Employee
from fw.modules.scheduling.models import ScheduledWork, StandingAssignment
from fw.modules.scheduling.schemas import (
    CandidateRecommendationRead,
    CoverageDayCell,
    CoverageItemRow,
    CoverageResponse,
    CoverageWorksiteRow,
    RosterDayCell,
    RosterResponse,
    RosterSiteChip,
    RosterWorkerRow,
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
    CandidateWorker,
    DayMarker,
    EffectiveStandardHours,
    EmployeeValidationContext,
    ExcelRosterDayCell,
    ExcelRosterWorkerRow,
    ExistingAssignmentContext,
    JobItemValidationContext,
    TargetJobItem,
    WorkerDayContext,
    build_roster_excel_bytes,
    calculate_allocation_summary,
    compute_effective_standard_hours,
    evaluate_worker_day_marker,
    generate_assignment_dates,
    rank_candidates_for_job,
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

        item = await self.session.get(
            JobItem,
            payload.job_item_id,
            options=[selectinload(JobItem.worksite), selectinload(JobItem.occurrences)],
        )
        if not item or not item.is_active:
            raise AppError(code="NOT_FOUND", message=f"Active job item {payload.job_item_id} not found.", status_code=404)

        # 2. Persist StandingAssignment
        standing = StandingAssignment(
            employee_id=payload.employee_id,
            job_item_id=payload.job_item_id,
            start_date=payload.start_date,
            end_date=payload.end_date,
            weekday_pattern=payload.weekday_pattern or item.weekday_pattern,
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

        slots = generate_assignment_dates(
            start_date=payload.start_date,
            end_date=target_end,
            weekday_pattern=standing.weekday_pattern,
            public_holidays=holidays,
            skip_public_holidays=True,
        )

        assigned_hours = standing.hours_per_day or item.hours_per_occurrence_per_staff
        created_count = 0

        # Create scheduled work rows on working days
        for slot in slots:
            if not slot.is_working_day:
                continue

            # Find or match occurrence for slot.work_date
            matching_occ_id: UUID | None = None
            for occ in item.occurrences:
                if occ.window_start <= slot.work_date <= occ.window_end:
                    matching_occ_id = occ.id
                    break

            # Next sequence for employee on that day
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
            raise AppError(code="VALIDATION_ERROR", message="End date cannot be earlier than start date.", status_code=422)

        old_end = standing.end_date
        standing.end_date = payload.end_date
        standing.version += 1

        # Cancel future uncompleted scheduled work created from this standing assignment
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

        item = await self.session.get(
            JobItem,
            payload.job_item_id,
            options=[selectinload(JobItem.worksite)],
        )
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

        item = await self.session.get(
            JobItem, payload.job_item_id, options=[selectinload(JobItem.worksite)]
        )
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
            occ = await self.session.get(
                JobOccurrence,
                occurrence_id,
                options=[selectinload(JobOccurrence.job_item).selectinload(JobItem.worksite)],
            )
            if not occ:
                raise AppError(code="NOT_FOUND", message=f"Job occurrence {occurrence_id} not found.", status_code=404)
            item = occ.job_item
            t_date = target_date or occ.due_date or occ.window_start
            req_hours = occ.required_hours_per_staff
        elif job_item_id:
            item = await self.session.get(
                JobItem, job_item_id, options=[selectinload(JobItem.worksite)]
            )
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

        # Fetch active workers in country
        emp_stmt = select(Employee).where(
            Employee.country == item.worksite.country,
            Employee.is_active.is_(True),
        )
        employees = (await self.session.execute(emp_stmt)).scalars().all()

        budget_staff_types = await self.get_budget_only_staff_types(item.worksite.country)

        # Weekly date range around t_date (Mon-Sun)
        week_start = t_date - timedelta(days=t_date.weekday())
        week_end = week_start + timedelta(days=6)

        # Query all scheduled work for these employees this week
        sw_stmt = select(ScheduledWork).where(
            ScheduledWork.work_date >= week_start,
            ScheduledWork.work_date <= week_end,
            ScheduledWork.status == "ACTIVE",
        )
        all_sw = (await self.session.execute(sw_stmt)).scalars().all()
        emp_weekly_hours: dict[UUID, Decimal] = {}
        emp_today_hours: dict[UUID, Decimal] = {}
        for sw_row in all_sw:
            emp_weekly_hours[sw_row.employee_id] = (
                emp_weekly_hours.get(sw_row.employee_id, Decimal("0")) + sw_row.assigned_hours
            )
            if sw_row.work_date == t_date:
                emp_today_hours[sw_row.employee_id] = (
                    emp_today_hours.get(sw_row.employee_id, Decimal("0")) + sw_row.assigned_hours
                )

        # Check who worked at this site in the last 14 days
        two_weeks_ago = t_date - timedelta(days=14)
        recent_site_stmt = select(ScheduledWork.employee_id).where(
            ScheduledWork.worksite_id == item.worksite_id,
            ScheduledWork.work_date >= two_weeks_ago,
            ScheduledWork.work_date <= t_date,
            ScheduledWork.status == "ACTIVE",
        ).distinct()
        recent_emp_ids = set((await self.session.execute(recent_site_stmt)).scalars().all())

        candidates: list[CandidateWorker] = []
        for emp in employees:
            is_budget = (emp.staff_grade_description or "").strip().lower() in budget_staff_types
            base_std = await self.get_employee_base_standard_hours(emp.id, t_date)

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
                    shares_supervisor=False,
                    weekly_allocated_hours=emp_weekly_hours.get(emp.id, Decimal("0.0")),
                    today_allocated_hours=emp_today_hours.get(emp.id, Decimal("0.0")),
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
                standard_hours=sc.worker.standard_hours,
                exact_staff_type_match=sc.exact_staff_type_match,
                ranking_score=sc.ranking_score,
                reasons=sc.reasons,
                warnings=sc.warnings,
                today_allocated_hours=sc.worker.today_allocated_hours,
                weekly_allocated_hours=sc.worker.weekly_allocated_hours,
                monthly_allocated_hours=sc.worker.weekly_allocated_hours * Decimal("4"),
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

        # Fetch employees matching scope and filters
        emp_stmt = select(Employee).where(Employee.is_active.is_(True))
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

        worker_rows: list[RosterWorkerRow] = []

        for emp in employees:
            holidays = holidays_ae if emp.country == "AE" else holidays_sa
            eff_hours = await self.get_effective_standard_hours(emp, week_start)
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

        # Query all active scheduled work for the week
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

        # Map scheduled work by (job_item_id, work_date)
        sw_by_item_date: dict[tuple[UUID, date], list[ScheduledWork]] = {}
        for r in scheduled_rows:
            key = (r.job_item_id, r.work_date)
            sw_by_item_date.setdefault(key, []).append(r)

        site_rows: list[CoverageWorksiteRow] = []

        for site in worksites:
            holidays = await self.get_public_holidays(site.country, week_start, week_end)
            item_rows: list[CoverageItemRow] = []

            for item in site.items:
                if not item.is_active:
                    continue

                days: list[CoverageDayCell] = []
                for day_idx in range(7):
                    c_date = week_start + timedelta(days=day_idx)
                    weekday_str = INT_TO_WEEKDAY[c_date.weekday()]

                    # Check if day is scheduled for this item
                    pattern = item.weekday_pattern or ["MON", "TUE", "WED", "THU", "FRI", "SAT"]
                    is_working_day = (
                        weekday_str in pattern
                        and c_date not in holidays
                        and (not item.end_date or c_date <= item.end_date)
                        and c_date >= item.start_date
                    )

                    assigned = sw_by_item_date.get((item.id, c_date), [])
                    assigned_count = len(assigned)
                    required_count = item.required_staff_count if is_working_day else 0

                    is_uncovered = is_working_day and (assigned_count < required_count)

                    days.append(
                        CoverageDayCell(
                            work_date=c_date,
                            weekday=weekday_str,
                            required_staff_count=required_count,
                            assigned_staff_count=assigned_count,
                            is_to_be_covered=is_uncovered,
                            assigned_workers=[a.employee.name for a in assigned if a.employee],
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
                        days=days,
                    )
                )

            if item_rows:
                site_rows.append(
                    CoverageWorksiteRow(
                        worksite_id=site.id,
                        job_number=site.job_number,
                        job_name=site.job_name,
                        items=item_rows,
                    )
                )

        return CoverageResponse(
            week_start=week_start,
            week_end=week_end,
            worksites=site_rows,
        )
