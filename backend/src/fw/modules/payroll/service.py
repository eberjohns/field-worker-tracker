"""Payroll Service implementing month-end runs, approvals, revisions, and budget costing."""

import csv
import io
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.errors import AppError
from fw.core.events import PayrollRunApproved, PayrollRunCreated, event_bus
from fw.modules.audit import AuditService
from fw.modules.org import Employee
from fw.modules.payroll.models import (
    EmployeeSalary,
    JobCostAllocation,
    PayrollRecord,
    PayrollRun,
    SalaryRevision,
    SalaryRevisionLine,
)
from fw.modules.payroll.repository import PayrollRepository
from fw.modules.payroll.schemas import (
    EmployeeSalaryCreate,
    EmployeeSalaryHistoryResponse,
    EmployeeSalaryRead,
    PayrollIssueItem,
    PayrollRecordRead,
    PayrollRunCreate,
    PayrollRunDetailRead,
    PayrollRunIssuesResponse,
    PayrollRunRead,
    SalaryRevisionCreate,
    SalaryRevisionDetailRead,
    SalaryRevisionImportDiffResponse,
    SalaryRevisionLineCreate,
    SalaryRevisionLineDiff,
    SalaryRevisionLineRead,
    SalaryRevisionRead,
    SalaryStructureListItem,
    WorkerMobilePayrollSlip,
    WorksiteBudgetVsActualItem,
)
from fw.modules.settings.service import SettingsService
from fw.rules.payroll import (
    calculate_final_total_staff_cost,
    calculate_gratuity,
    calculate_gross_pay,
    calculate_hourly_ot_rate,
    calculate_hr_overhead,
    calculate_leave_salary,
    calculate_missed_hours_deduction,
    calculate_per_month_provision,
    calculate_provisions,
    calculate_revision_planned_hourly_cost,
    calculate_salary_difference,
    calculate_salary_portion,
    calculate_total_staff_cost,
    compute_next_payroll_month_start,
    round_money,
)


class PayrollSalaryService:
    """Service for employee salary structures and history."""

    @staticmethod
    async def get_salary_history(
        session: AsyncSession,
        employee_id: UUID,
    ) -> EmployeeSalaryHistoryResponse | None:
        """Fetch full salary structure history and change difference for an employee."""
        emp = await session.get(Employee, employee_id)
        if not emp:
            return None

        from sqlalchemy import select

        hist_stmt = (
            select(EmployeeSalary)
            .where(EmployeeSalary.employee_id == employee_id)
            .order_by(EmployeeSalary.effective_from.asc(), EmployeeSalary.created_at.asc())
        )
        res = await session.execute(hist_stmt)
        rows = list(res.scalars().all())

        history_items: list[EmployeeSalaryRead] = []
        prev_portion: Decimal | None = None

        for r in rows:
            portion = calculate_salary_portion(
                basic=r.basic_salary,
                special_allowance=r.special_allowance,
                fixed_ot=r.fixed_ot_amount,
                bonus=r.bonus,
                telephone_allowance=r.telephone_allowance,
                housing_transport_allowance=r.housing_transport_allowance,
            )
            diff = calculate_salary_difference(portion, prev_portion)
            prev_portion = portion

            history_items.append(
                EmployeeSalaryRead(
                    id=r.id,
                    employee_id=r.employee_id,
                    tally_id=emp.tally_id,
                    employee_name=emp.name,
                    effective_from=r.effective_from,
                    standard_hours=r.standard_hours,
                    basic_salary=r.basic_salary,
                    special_allowance=r.special_allowance,
                    fixed_ot_amount=r.fixed_ot_amount,
                    break_minutes=r.break_minutes,
                    bonus=r.bonus,
                    telephone_allowance=r.telephone_allowance,
                    housing_transport_allowance=r.housing_transport_allowance,
                    change_source=r.change_source,
                    salary_portion=portion,
                    difference=diff,
                    created_at=r.created_at,
                )
            )

        current_item = history_items[-1] if history_items else None
        last_change_date = current_item.effective_from if current_item else None
        last_diff = current_item.difference if current_item else Decimal("0.00")

        return EmployeeSalaryHistoryResponse(
            employee_id=emp.id,
            tally_id=emp.tally_id,
            employee_name=emp.name,
            current_salary=current_item,
            last_change_date=last_change_date,
            last_change_difference=last_diff,
            history=list(reversed(history_items)),
        )

    @staticmethod
    async def create_salary_revision(
        session: AsyncSession,
        employee_id: UUID,
        payload: EmployeeSalaryCreate,
        user_id: UUID | None = None,
        reason: str | None = None,
    ) -> EmployeeSalaryRead:
        emp = await session.get(Employee, employee_id)
        if not emp:
            raise AppError(code="NOT_FOUND", message="Employee not found", status_code=404)

        effective_date = payload.effective_from or compute_next_payroll_month_start(
            datetime.now(UTC).date()
        )

        break_mins = payload.break_minutes
        if break_mins is None:
            from fw.modules.org.models import EmployeeReportingLine

            sup_stmt = (
                select(Employee.break_override_minutes)
                .join(
                    EmployeeReportingLine,
                    EmployeeReportingLine.manager_id == Employee.id,
                )
                .where(
                    EmployeeReportingLine.employee_id == employee_id,
                    EmployeeReportingLine.relationship == "SUPERVISOR",
                    EmployeeReportingLine.is_active.is_(True),
                )
                .limit(1)
            )
            sup_break = (await session.execute(sup_stmt)).scalar_one_or_none()
            if sup_break and sup_break > 0:
                break_mins = sup_break

        row = EmployeeSalary(
            employee_id=employee_id,
            effective_from=effective_date,
            standard_hours=payload.standard_hours,
            basic_salary=payload.basic_salary,
            special_allowance=payload.special_allowance,
            fixed_ot_amount=payload.fixed_ot_amount,
            bonus=payload.bonus,
            telephone_allowance=payload.telephone_allowance,
            housing_transport_allowance=payload.housing_transport_allowance,
            break_minutes=break_mins,
            created_by_user_id=user_id,
        )
        session.add(row)
        await session.flush()

        portion = calculate_salary_portion(
            basic=row.basic_salary,
            special_allowance=row.special_allowance,
            fixed_ot=row.fixed_ot_amount,
            bonus=row.bonus,
            telephone_allowance=row.telephone_allowance,
            housing_transport_allowance=row.housing_transport_allowance,
        )

        await AuditService.log_action(
            session=session,
            actor_user_id=user_id,
            action="SALARY_STRUCTURE_CREATED",
            entity_type="employee_salary",
            entity_id=str(row.id),
            diff={"employee_id": str(employee_id), "effective_from": str(effective_date)},
            reason=reason or "Salary structure change created",
        )

        return EmployeeSalaryRead(
            id=row.id,
            employee_id=row.employee_id,
            tally_id=emp.tally_id,
            employee_name=emp.name,
            effective_from=row.effective_from,
            standard_hours=row.standard_hours,
            basic_salary=row.basic_salary,
            special_allowance=row.special_allowance,
            fixed_ot_amount=row.fixed_ot_amount,
            break_minutes=row.break_minutes,
            bonus=row.bonus,
            telephone_allowance=row.telephone_allowance,
            housing_transport_allowance=row.housing_transport_allowance,
            change_source=row.change_source,
            salary_portion=portion,
            difference=Decimal("0.00"),
            created_at=row.created_at,
        )

    @staticmethod
    async def create_or_update_salary(
        session: AsyncSession,
        employee_id: UUID,
        data: EmployeeSalaryCreate,
        actor_user_id: UUID | None = None,
        actor_role: str = "ADMIN",
        batch_id: UUID | None = None,
    ) -> EmployeeSalaryRead:
        """Create or update an effective-dated salary structure."""
        effective_from = data.effective_from or compute_next_payroll_month_start(date.today())

        from sqlalchemy import select

        stmt = select(EmployeeSalary).where(
            EmployeeSalary.employee_id == employee_id,
            EmployeeSalary.effective_from == effective_from,
        )
        res = await session.execute(stmt)
        existing = res.scalar_one_or_none()

        if existing:
            existing.standard_hours = data.standard_hours
            existing.basic_salary = data.basic_salary
            existing.special_allowance = data.special_allowance
            existing.fixed_ot_amount = data.fixed_ot_amount
            existing.bonus = data.bonus
            existing.telephone_allowance = data.telephone_allowance
            existing.housing_transport_allowance = data.housing_transport_allowance
            if data.break_minutes is not None:
                existing.break_minutes = data.break_minutes
            elif existing.break_minutes is None:
                from fw.modules.org.models import EmployeeReportingLine

                sup_stmt = (
                    select(Employee.break_override_minutes)
                    .join(
                        EmployeeReportingLine,
                        EmployeeReportingLine.manager_id == Employee.id,
                    )
                    .where(
                        EmployeeReportingLine.employee_id == employee_id,
                        EmployeeReportingLine.relationship == "SUPERVISOR",
                        EmployeeReportingLine.is_active.is_(True),
                    )
                    .limit(1)
                )
                sup_break = (await session.execute(sup_stmt)).scalar_one_or_none()
                if sup_break and sup_break > 0:
                    existing.break_minutes = sup_break
            if data.change_source is not None:
                existing.change_source = data.change_source
            if batch_id:
                existing.import_batch_id = batch_id
            target = existing
            action = "UPDATE"
        else:
            break_mins = data.break_minutes
            if break_mins is None:
                from fw.modules.org.models import EmployeeReportingLine

                sup_stmt = (
                    select(Employee.break_override_minutes)
                    .join(
                        EmployeeReportingLine,
                        EmployeeReportingLine.manager_id == Employee.id,
                    )
                    .where(
                        EmployeeReportingLine.employee_id == employee_id,
                        EmployeeReportingLine.relationship == "SUPERVISOR",
                        EmployeeReportingLine.is_active.is_(True),
                    )
                    .limit(1)
                )
                sup_break = (await session.execute(sup_stmt)).scalar_one_or_none()
                if sup_break and sup_break > 0:
                    break_mins = sup_break

            target = EmployeeSalary(
                employee_id=employee_id,
                effective_from=effective_from,
                standard_hours=data.standard_hours,
                basic_salary=data.basic_salary,
                special_allowance=data.special_allowance,
                fixed_ot_amount=data.fixed_ot_amount,
                break_minutes=break_mins,
                bonus=data.bonus,
                telephone_allowance=data.telephone_allowance,
                housing_transport_allowance=data.housing_transport_allowance,
                change_source=data.change_source,
                import_batch_id=batch_id,
                created_by_user_id=actor_user_id,
            )
            session.add(target)
            action = "CREATE"

        await session.flush()

        if actor_user_id:
            await AuditService.log_action(
                session=session,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
                action=f"SALARY_{action}",
                entity_type="EMPLOYEE_SALARY",
                entity_id=str(target.id),
                diff={
                    "effective_from": str(effective_from),
                    "basic_salary": str(data.basic_salary),
                },
                reason="Salary structure change",
            )

        history_resp = await PayrollSalaryService.get_salary_history(session, employee_id)
        assert history_resp is not None
        for item in history_resp.history:
            if item.id == target.id:
                return item

        portion = calculate_salary_portion(
            target.basic_salary,
            target.special_allowance,
            target.fixed_ot_amount,
            target.bonus,
            target.telephone_allowance,
            target.housing_transport_allowance,
        )
        return EmployeeSalaryRead(
            id=target.id,
            employee_id=target.employee_id,
            effective_from=target.effective_from,
            standard_hours=target.standard_hours,
            basic_salary=target.basic_salary,
            special_allowance=target.special_allowance,
            fixed_ot_amount=target.fixed_ot_amount,
            bonus=target.bonus,
            telephone_allowance=target.telephone_allowance,
            housing_transport_allowance=target.housing_transport_allowance,
            salary_portion=portion,
            difference=Decimal("0.00"),
            created_at=target.created_at,
        )

    @staticmethod
    async def list_salary_structures(
        session: AsyncSession,
        country: str | None = None,
        as_of: date | None = None,
        scoped_employee_ids: list[UUID] | None = None,
    ) -> list[SalaryStructureListItem]:
        from sqlalchemy import select

        stmt = select(Employee).where(Employee.is_active == True)  # noqa: E712
        if country:
            stmt = stmt.where(Employee.country == country)
        if scoped_employee_ids is not None:
            stmt = stmt.where(Employee.id.in_(scoped_employee_ids))
        stmt = stmt.order_by(Employee.tally_id.asc())

        res = await session.execute(stmt)
        employees = list(res.scalars().all())

        items: list[SalaryStructureListItem] = []
        today = as_of or datetime.now(UTC).date()

        for emp in employees:
            salary = await PayrollRepository.get_latest_salary_for_employee(session, emp.id, today)
            if salary:
                portion = calculate_salary_portion(
                    basic=salary.basic_salary,
                    special_allowance=salary.special_allowance,
                    fixed_ot=salary.fixed_ot_amount,
                    bonus=salary.bonus,
                    telephone_allowance=salary.telephone_allowance,
                    housing_transport_allowance=salary.housing_transport_allowance,
                )
                items.append(
                    SalaryStructureListItem(
                        employee_id=emp.id,
                        tally_id=emp.tally_id,
                        name=emp.name,
                        role=emp.role,
                        country=emp.country,
                        standard_hours=salary.standard_hours,
                        salary_portion=portion,
                        basic_salary=salary.basic_salary,
                        break_minutes=salary.break_minutes,
                        effective_from=salary.effective_from,
                        last_change_date=salary.effective_from,
                        difference=Decimal("0.00"),
                    )
                )
            else:
                items.append(
                    SalaryStructureListItem(
                        employee_id=emp.id,
                        tally_id=emp.tally_id,
                        name=emp.name,
                        role=emp.role,
                        country=emp.country,
                        standard_hours=Decimal("8.0"),
                        salary_portion=Decimal("0.00"),
                        basic_salary=Decimal("0.00"),
                        effective_from=emp.join_date or today,
                        last_change_date=None,
                        difference=Decimal("0.00"),
                    )
                )
        return items

    @staticmethod
    async def propagate_crew_break_to_worker(
        session: AsyncSession,
        worker_id: UUID,
        break_minutes: int | None,
        effective_from: date,
        actor_user_id: UUID | None = None,
        actor_role: str = "ADMIN",
    ) -> None:
        """Propagate supervisor crew break to a worker's effective-dated salary structure.

        Rules:
        a) Future-dated salary rows: set new break on all rows where effective_from > chosen date.
        b) Same-date row: if row exists with effective_from == chosen date, update break_minutes.
        c) Locked periods: reject effective date inside a month with APPROVED payroll run.
        d) Mark created/updated row with change_source = 'CREW_BREAK'.
        e) Recalculate unlocked past attendance dates if effective_from < today.
        """
        worker = await session.get(Employee, worker_id)
        if not worker:
            return

        # Query all salary rows for worker
        stmt = (
            select(EmployeeSalary)
            .where(EmployeeSalary.employee_id == worker_id)
            .order_by(EmployeeSalary.effective_from.asc())
        )
        res = await session.execute(stmt)
        all_salaries = list(res.scalars().all())

        same_date_row = next((s for s in all_salaries if s.effective_from == effective_from), None)
        future_rows = [s for s in all_salaries if s.effective_from > effective_from]
        prior_rows = [s for s in all_salaries if s.effective_from < effective_from]
        row_in_force = same_date_row or (prior_rows[-1] if prior_rows else None)

        future_needs_update = any(s.break_minutes != break_minutes for s in future_rows)

        # Idempotency and baseline check
        if row_in_force:
            if same_date_row:
                if same_date_row.break_minutes == break_minutes and not future_needs_update:
                    return
            else:
                if row_in_force.break_minutes == break_minutes and not future_needs_update:
                    return
        else:
            # Worker has no salary row on or before effective date: only update future rows (if any) and return; do not invent amounts.
            if not future_needs_update:
                return

        # Check c: Locked period check via PayrollRun
        pay_run_stmt = (
            select(PayrollRun.id)
            .where(
                PayrollRun.country == worker.country,
                PayrollRun.status == "APPROVED",
                PayrollRun.period_start <= effective_from,
                PayrollRun.period_end >= effective_from,
            )
            .limit(1)
        )
        approved_run = (await session.execute(pay_run_stmt)).scalars().first()
        if approved_run:
            raise AppError(
                code="PAYROLL_PERIOD_LOCKED",
                message=f"Cannot apply crew break to {effective_from}: period is locked by an approved payroll run.",
                status_code=422,
            )

        # Check if attendance is locked for finalized payroll
        from fw.modules.attendance.models import AttendanceRecord

        att_locked_stmt = (
            select(AttendanceRecord.id)
            .where(
                AttendanceRecord.employee_id == worker_id,
                AttendanceRecord.work_date >= effective_from,
                AttendanceRecord.locked.is_(True),
            )
            .limit(1)
        )
        if (await session.execute(att_locked_stmt)).scalars().first():
            raise AppError(
                code="PAYROLL_PERIOD_LOCKED",
                message=f"Cannot apply crew break to {effective_from}: attendance is locked for finalized payroll.",
                status_code=422,
            )

        if same_date_row:
            same_date_row.break_minutes = break_minutes
            if same_date_row.change_source == "CREW_BREAK":
                same_date_row.change_source = "CREW_BREAK"
        elif prior_rows:
            latest_prior = prior_rows[-1]
            if latest_prior.break_minutes != break_minutes:
                new_sal = EmployeeSalary(
                    employee_id=worker_id,
                    effective_from=effective_from,
                    standard_hours=latest_prior.standard_hours,
                    basic_salary=latest_prior.basic_salary,
                    special_allowance=latest_prior.special_allowance,
                    fixed_ot_amount=latest_prior.fixed_ot_amount,
                    bonus=latest_prior.bonus,
                    telephone_allowance=latest_prior.telephone_allowance,
                    housing_transport_allowance=latest_prior.housing_transport_allowance,
                    break_minutes=break_minutes,
                    change_source="CREW_BREAK",
                    created_by_user_id=actor_user_id,
                )
                session.add(new_sal)
        else:
            # Worker has no salary row on or before effective date. Do not invent amounts!
            pass

        # Update all future rows
        for fut in future_rows:
            if fut.break_minutes != break_minutes:
                fut.break_minutes = break_minutes

        await session.flush()

        await AuditService.log_action(
            session=session,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            action="CREW_BREAK_PROPAGATED",
            entity_type="employee_salary",
            entity_id=str(worker_id),
            diff={"break_minutes": break_minutes, "effective_from": str(effective_from)},
            reason="Supervisor crew break propagation",
        )

        # Recalculate past attendance for dates from effective_from up to yesterday (if effective_from < today)
        today = date.today()
        if effective_from < today:
            from fw.modules.attendance import AttendanceRecord, AttendanceService

            curr_date = effective_from
            while curr_date < today:
                att_q = select(AttendanceRecord).where(
                    AttendanceRecord.employee_id == worker_id,
                    AttendanceRecord.work_date == curr_date,
                    AttendanceRecord.locked.is_(False),
                )
                att_rec = (await session.execute(att_q)).scalar_one_or_none()
                if att_rec:
                    await AttendanceService.recalculate_day(
                        session=session,
                        employee_id=worker_id,
                        work_date=curr_date,
                        reason="CREW_BREAK_PROPAGATION",
                    )
                curr_date += timedelta(days=1)

    @staticmethod
    async def propagate_crew_break_to_supervisor_crew(
        session: AsyncSession,
        supervisor_id: UUID,
        break_minutes: int | None,
        effective_from: date,
        actor_user_id: UUID | None = None,
        actor_role: str = "ADMIN",
    ) -> int:
        """Find all active workers reporting to supervisor_id and propagate the crew break."""
        from fw.modules.org.models import EmployeeReportingLine

        stmt = select(EmployeeReportingLine.employee_id).where(
            EmployeeReportingLine.manager_id == supervisor_id,
            EmployeeReportingLine.relationship == "SUPERVISOR",
            EmployeeReportingLine.is_active == True,  # noqa: E712
        )
        worker_ids = (await session.execute(stmt)).scalars().all()
        for wid in worker_ids:
            await PayrollSalaryService.propagate_crew_break_to_worker(
                session=session,
                worker_id=wid,
                break_minutes=break_minutes,
                effective_from=effective_from,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
            )
        return len(worker_ids)


class PayrollService:
    """Service managing month-end payroll runs, approvals, and budget costing."""

    @staticmethod
    async def generate_draft_run(
        session: AsyncSession,
        payload: PayrollRunCreate,
        user_id: UUID | None = None,
        actor_role: str | None = None,
    ) -> PayrollRunDetailRead:
        """Generate or re-run a DRAFT monthly payroll run.

        Picks up approved attendance records, salary structures, leave, and settings.
        """
        # 1. Check if an approved run already exists
        existing_run = await PayrollRepository.get_latest_run_for_period(
            session, payload.period_start, payload.period_end, payload.country
        )
        if existing_run and existing_run.status == "APPROVED":
            raise AppError(
                code="PAYROLL_ALREADY_APPROVED",
                message=f"Payroll for {payload.period_start} to {payload.period_end} ({payload.country}) is already APPROVED and locked.",
                status_code=409,
            )

        run_no = 1
        if existing_run and existing_run.status == "DRAFT":
            run_no = existing_run.run_no + 1
            # Delete earlier draft records and run to replace with new run_no
            await PayrollRepository.delete_draft_run(session, existing_run.id)

        # 2. Resolve effective settings for the country as of period_end
        async def get_setting_dec(key: str, default: Decimal) -> Decimal:
            val = await SettingsService.get_setting(
                session=session,
                key=key,
                as_of=payload.period_end,
                country=payload.country,
                default=default,
            )
            return Decimal(str(val)) if val is not None else default

        ot_divisor = await get_setting_dec("ot_divisor", Decimal("208"))
        ot1_multiplier = await get_setting_dec("ot1_multiplier", Decimal("1.25"))
        ot2_multiplier = await get_setting_dec("ot2_multiplier", Decimal("1.50"))
        hr_oh_rate = await get_setting_dec("hr_overhead_rate", Decimal("0.05"))

        visa_prov = await get_setting_dec("visa_provision", Decimal("100.00"))
        air_prov = await get_setting_dec("air_ticket_provision", Decimal("75.00"))
        uniform_prov = await get_setting_dec("uniform_provision", Decimal("25.00"))
        accom_prov = await get_setting_dec("accommodation_provision", Decimal("300.00"))
        medical_prov = await get_setting_dec("medical_provision", Decimal("50.00"))

        company_provisions = calculate_provisions(
            visa=visa_prov,
            air_ticket=air_prov,
            uniform=uniform_prov,
            accommodation=accom_prov,
            medical=medical_prov,
        )

        # 3. Create PayrollRun header
        run = PayrollRun(
            period_start=payload.period_start,
            period_end=payload.period_end,
            country=payload.country,
            status="DRAFT",
            run_no=run_no,
            created_by="USER" if user_id else "SYSTEM",
            created_by_user_id=user_id,
            calculation_version="1.0",
            notes=payload.notes,
        )
        await PayrollRepository.create_run(session, run)

        # 4. Fetch period data
        employees = await PayrollRepository.get_active_employees_for_country(
            session, payload.country
        )
        attendance_pairs = await PayrollRepository.get_attendance_calculations_for_period(
            session, payload.period_start, payload.period_end, payload.country
        )
        leave_requests = await PayrollRepository.get_leave_requests_for_period(
            session, payload.period_start, payload.period_end, payload.country
        )
        scheduled_items = await PayrollRepository.get_scheduled_work_for_period(
            session, payload.period_start, payload.period_end, payload.country
        )

        # Group attendance calculations and leave by employee
        att_by_emp: dict[UUID, list[tuple]] = {}
        for record, calc in attendance_pairs:
            att_by_emp.setdefault(record.employee_id, []).append((record, calc))

        leave_by_emp: dict[UUID, list] = {}
        for leave in leave_requests:
            leave_by_emp.setdefault(leave.employee_id, []).append(leave)

        sched_by_emp: dict[UUID, list] = {}
        for item in scheduled_items:
            sched_by_emp.setdefault(item.employee_id, []).append(item)

        records_to_create: list[PayrollRecord] = []
        cost_allocations_to_create: list[JobCostAllocation] = []

        # Totals accumulators
        t_scheduled_hours = Decimal("0.0")
        t_worked_hours = Decimal("0.0")
        t_ot1_hours = Decimal("0.0")
        t_ot2_hours = Decimal("0.0")
        t_ot1_amount = Decimal("0.00")
        t_ot2_amount = Decimal("0.00")
        t_gross = Decimal("0.00")
        t_net = Decimal("0.00")
        t_prov = Decimal("0.00")
        t_staff_cost = Decimal("0.00")
        t_final_cost = Decimal("0.00")

        for emp in employees:
            salary = await PayrollRepository.get_latest_salary_for_employee(
                session, emp.id, payload.period_end
            )
            std_hours = salary.standard_hours if salary else Decimal("8.0")
            basic_sal = salary.basic_salary if salary else Decimal("0.00")
            salary_id = salary.id if salary else None

            # Calculate fixed salary portion
            if salary:
                salary_portion = calculate_salary_portion(
                    basic=salary.basic_salary,
                    special_allowance=salary.special_allowance,
                    fixed_ot=salary.fixed_ot_amount,
                    bonus=salary.bonus,
                    telephone_allowance=salary.telephone_allowance,
                    housing_transport_allowance=salary.housing_transport_allowance,
                )
            else:
                salary_portion = Decimal("0.00")

            # Compute hours from attendance and schedule
            emp_sched = sched_by_emp.get(emp.id, [])
            scheduled_hours = sum(
                (Decimal(str(s.assigned_hours)) for s in emp_sched),
                Decimal("0.0"),
            )

            emp_leaves = leave_by_emp.get(emp.id, [])
            approved_leave_dates: set[date] = set()
            for lv in emp_leaves:
                start_d = max(lv.from_date, payload.period_start)
                end_d = min(lv.to_date, payload.period_end)
                cur_ld = start_d
                while cur_ld <= end_d:
                    approved_leave_dates.add(cur_ld)
                    cur_ld += timedelta(days=1)

            emp_att = att_by_emp.get(emp.id, [])
            worked_hours = Decimal("0.0")
            ot1_hours = Decimal("0.0")
            ot2_hours = Decimal("0.0")
            shortfall_hours = Decimal("0.0")
            source_calc_ids: list[str] = []

            for rec, calc in emp_att:
                source_calc_ids.append(str(calc.id))
                # Productive/worked hours
                worked_m = Decimal(str(calc.worked_minutes or 0))
                worked_hours += round_money(worked_m / Decimal("60"))

                # Shortfall minutes (skip leave days if run treats leaves as paid)
                if calc.shortfall_minutes and calc.shortfall_minutes > 0:
                    if not (payload.treat_leaves_as_paid and rec.work_date in approved_leave_dates):
                        shortfall_hours += round_money(
                            Decimal(str(calc.shortfall_minutes)) / Decimal("60")
                        )

                # Overtime: ONLY calculate if approved
                # (review_status == 'APPROVED' or auto-approved when review_reasons is empty)
                is_approved = rec.review_status == "APPROVED" or (
                    not calc.review_reasons and rec.review_status != "REJECTED"
                )
                if is_approved:
                    if calc.ot1_minutes and calc.ot1_minutes > 0:
                        ot1_hours += round_money(Decimal(str(calc.ot1_minutes)) / Decimal("60"))
                    if calc.ot2_minutes and calc.ot2_minutes > 0:
                        ot2_hours += round_money(Decimal(str(calc.ot2_minutes)) / Decimal("60"))

            # Leave hours
            paid_leave_hours = Decimal("0.0")
            unpaid_leave_hours = Decimal("0.0")

            for lv in emp_leaves:
                # Count days in period
                start_d = max(lv.from_date, payload.period_start)
                end_d = min(lv.to_date, payload.period_end)
                if end_d >= start_d:
                    days_count = Decimal(str((end_d - start_d).days + 1))
                    h = days_count * std_hours
                    if (
                        payload.treat_leaves_as_paid
                        or getattr(lv, "is_paid", False)
                        or lv.leave_type in ("ANNUAL", "SICK")
                    ):
                        paid_leave_hours += h
                    else:
                        unpaid_leave_hours += h

            # Missed hours deduction
            missed_unpaid_hours = unpaid_leave_hours + shortfall_hours
            missed_deduction = calculate_missed_hours_deduction(
                basic_salary=basic_sal,
                missed_hours=missed_unpaid_hours,
                divisor=ot_divisor,
            )

            # OT rates and amounts
            ot1_rate = calculate_hourly_ot_rate(basic_sal, ot1_multiplier, ot_divisor)
            ot2_rate = calculate_hourly_ot_rate(basic_sal, ot2_multiplier, ot_divisor)
            ot1_amount = round_money(ot1_hours * ot1_rate)
            ot2_amount = round_money(ot2_hours * ot2_rate)

            # Gross & Net
            gross_pay = calculate_gross_pay(
                salary_portion=salary_portion,
                ot1_amount=ot1_amount,
                ot2_amount=ot2_amount,
                missed_hours_deduction=missed_deduction,
            )
            net_pay = gross_pay  # zero deductions per DEC-30

            # Employer provisions & cost
            gratuity = calculate_gratuity(basic_sal)
            leave_salary = calculate_leave_salary(basic_sal)
            per_month_prov = calculate_per_month_provision(
                provisions_sum=company_provisions,
                gratuity=gratuity,
                leave_salary=leave_salary,
            )
            total_staff_cost = calculate_total_staff_cost(gross_pay, per_month_prov)
            hr_oh = calculate_hr_overhead(total_staff_cost, hr_oh_rate)
            final_cost = calculate_final_total_staff_cost(total_staff_cost, hr_oh)

            snapshot = {
                "settings": {
                    "ot_divisor": str(ot_divisor),
                    "ot1_multiplier": str(ot1_multiplier),
                    "ot2_multiplier": str(ot2_multiplier),
                    "hr_overhead_rate": str(hr_oh_rate),
                    "treat_leaves_as_paid": payload.treat_leaves_as_paid,
                    "provisions": {
                        "visa": str(visa_prov),
                        "air_ticket": str(air_prov),
                        "uniform": str(uniform_prov),
                        "accommodation": str(accom_prov),
                        "medical": str(medical_prov),
                    },
                },
                "salary": {
                    "standard_hours": str(std_hours),
                    "basic_salary": str(basic_sal),
                    "salary_portion": str(salary_portion),
                },
                "attendance_calculation_ids": source_calc_ids,
                "ot1_rate": str(ot1_rate),
                "ot2_rate": str(ot2_rate),
                "missed_hours": str(missed_unpaid_hours),
                "missed_hours_deduction": str(missed_deduction),
            }

            rec = PayrollRecord(
                payroll_run_id=run.id,
                employee_id=emp.id,
                salary_id=salary_id,
                standard_hours=std_hours,
                scheduled_hours=scheduled_hours,
                worked_hours=worked_hours,
                paid_leave_hours=paid_leave_hours,
                unpaid_leave_hours=unpaid_leave_hours,
                shortfall_hours=shortfall_hours,
                missed_hours_deduction=missed_deduction,
                ot1_hours=ot1_hours,
                ot2_hours=ot2_hours,
                salary_portion=salary_portion,
                ot1_amount=ot1_amount,
                ot2_amount=ot2_amount,
                gross_pay=gross_pay,
                net_pay=net_pay,
                gratuity=gratuity,
                leave_salary=leave_salary,
                provisions=company_provisions,
                per_month_provision=per_month_prov,
                total_staff_cost=total_staff_cost,
                hr_oh_amount=hr_oh,
                final_total_staff_cost=final_cost,
                snapshot=snapshot,
            )
            records_to_create.append(rec)

            # Job cost allocations: proportional allocation by worked minutes
            worksite_minutes = (
                await PayrollRepository.get_allocated_minutes_per_worksite_for_employee(
                    session, emp.id, payload.period_start, payload.period_end
                )
            )
            total_emp_minutes = sum(worksite_minutes.values())
            for ws_id, minutes in worksite_minutes.items():
                if total_emp_minutes > 0:
                    fraction = Decimal(str(minutes)) / Decimal(str(total_emp_minutes))
                    allocated_val = round_money(final_cost * fraction)
                else:
                    allocated_val = Decimal("0.00")

                cost_allocations_to_create.append(
                    JobCostAllocation(
                        payroll_record_id=rec.id,
                        worksite_id=ws_id,
                        worked_minutes=minutes,
                        allocated_amount=allocated_val,
                    )
                )

            # Totals
            t_scheduled_hours += scheduled_hours
            t_worked_hours += worked_hours
            t_ot1_hours += ot1_hours
            t_ot2_hours += ot2_hours
            t_ot1_amount += ot1_amount
            t_ot2_amount += ot2_amount
            t_gross += gross_pay
            t_net += net_pay
            t_prov += per_month_prov
            t_staff_cost += total_staff_cost
            t_final_cost += final_cost

        session.add_all(records_to_create)
        session.add_all(cost_allocations_to_create)

        totals_dict = {
            "worker_count": len(employees),
            "scheduled_hours_total": str(t_scheduled_hours),
            "worked_hours_total": str(t_worked_hours),
            "ot1_hours_total": str(t_ot1_hours),
            "ot2_hours_total": str(t_ot2_hours),
            "ot1_amount_total": str(t_ot1_amount),
            "ot2_amount_total": str(t_ot2_amount),
            "gross_pay_total": str(t_gross),
            "net_pay_total": str(t_net),
            "provisions_total": str(t_prov),
            "total_staff_cost_total": str(t_staff_cost),
            "final_total_staff_cost_total": str(t_final_cost),
            "treat_leaves_as_paid": payload.treat_leaves_as_paid,
        }
        run.totals_snapshot = totals_dict
        await session.flush()

        await AuditService.log_action(
            session=session,
            actor_user_id=user_id,
            action="PAYROLL_DRAFT_GENERATED",
            entity_type="payroll_runs",
            entity_id=str(run.id),
            diff={"run_no": run.run_no, "country": run.country, "totals": totals_dict},
            reason=f"Draft payroll run #{run.run_no} generated",
        )

        return await PayrollService.get_payroll_run_detail(session, run.id)

    @staticmethod
    async def get_payroll_run_detail(
        session: AsyncSession,
        run_id: UUID,
        scoped_employee_ids: list[UUID] | None = None,
    ) -> PayrollRunDetailRead:
        run = await PayrollRepository.get_run_by_id(session, run_id)
        if not run:
            raise AppError(code="NOT_FOUND", message="Payroll run not found", status_code=404)

        records = await PayrollRepository.list_records_for_run(
            session, run_id, scoped_employee_ids=scoped_employee_ids
        )

        record_reads: list[PayrollRecordRead] = []
        for r in records:
            emp = r.employee
            snap = r.snapshot or {}
            std_daily = r.standard_hours
            std_monthly = round_money(std_daily * Decimal("26"))
            missed_h = round_money(r.unpaid_leave_hours + r.shortfall_hours)

            record_reads.append(
                PayrollRecordRead(
                    id=r.id,
                    employee_id=r.employee_id,
                    tally_id=emp.tally_id if emp else None,
                    employee_tally_id=emp.tally_id if emp else None,
                    employee_name=emp.name if emp else None,
                    employee_role=emp.role if emp else "WORKER",
                    role=emp.role if emp else "WORKER",
                    standard_hours=std_daily,
                    standard_monthly_hours=std_monthly,
                    scheduled_hours=r.scheduled_hours,
                    worked_hours=r.worked_hours,
                    actual_worked_hours=r.worked_hours,
                    paid_leave_hours=r.paid_leave_hours,
                    unpaid_leave_hours=r.unpaid_leave_hours,
                    shortfall_hours=r.shortfall_hours,
                    missed_hours=missed_h,
                    missed_hours_deduction=r.missed_hours_deduction,
                    ot1_hours=r.ot1_hours,
                    ot2_hours=r.ot2_hours,
                    salary_portion=r.salary_portion,
                    basic_salary=Decimal(str(snap.get("basic_salary", 0))),
                    special_allowance=Decimal(str(snap.get("special_allowance", 0))),
                    fixed_ot_amount=Decimal(str(snap.get("fixed_ot_amount", 0))),
                    bonus=Decimal(str(snap.get("bonus", 0))),
                    telephone_allowance=Decimal(str(snap.get("telephone_allowance", 0))),
                    housing_transport_allowance=Decimal(
                        str(snap.get("housing_transport_allowance", 0))
                    ),
                    ot1_rate=Decimal(str(snap.get("ot1_rate", 0))),
                    ot2_rate=Decimal(str(snap.get("ot2_rate", 0))),
                    ot1_amount=r.ot1_amount,
                    ot2_amount=r.ot2_amount,
                    gross_pay=r.gross_pay,
                    total_deductions=r.missed_hours_deduction,
                    net_pay=r.net_pay,
                    gratuity=r.gratuity,
                    gratuity_provision=r.gratuity,
                    leave_salary=r.leave_salary,
                    leave_salary_provision=r.leave_salary,
                    provisions=r.provisions,
                    company_provisions_total=r.provisions,
                    per_month_provision=r.per_month_provision,
                    total_staff_cost=r.total_staff_cost,
                    hr_oh_amount=r.hr_oh_amount,
                    hr_overhead_amount=r.hr_oh_amount,
                    final_total_staff_cost=r.final_total_staff_cost,
                    snapshot=r.snapshot,
                    created_at=r.created_at,
                )
            )

        await event_bus.publish(
            PayrollRunCreated(
                payroll_run_id=run.id,
                country=run.country,
                is_draft=True,
                actor_user_id=run.created_by_user_id,
            ),
            session=session,
        )

        return PayrollRunDetailRead(
            id=run.id,
            period_start=run.period_start,
            period_end=run.period_end,
            country=run.country,
            status=run.status,
            run_no=run.run_no,
            created_by=run.created_by,
            created_by_user_id=run.created_by_user_id,
            approved_by_user_id=run.approved_by_user_id,
            approved_at=run.approved_at,
            calculation_version=run.calculation_version,
            totals_snapshot=run.totals_snapshot,
            notes=run.notes,
            record_count=len(record_reads),
            created_at=run.created_at,
            updated_at=run.updated_at,
            records=record_reads,
        )

    @staticmethod
    async def list_runs(
        session: AsyncSession,
        country: str | None = None,
        status: str | None = None,
    ) -> list[PayrollRunRead]:
        runs = await PayrollRepository.list_runs(session, country=country, status=status)
        return [
            PayrollRunRead(
                id=r.id,
                period_start=r.period_start,
                period_end=r.period_end,
                country=r.country,
                status=r.status,
                run_no=r.run_no,
                created_by=r.created_by,
                created_by_user_id=r.created_by_user_id,
                approved_by_user_id=r.approved_by_user_id,
                approved_at=r.approved_at,
                calculation_version=r.calculation_version,
                totals_snapshot=r.totals_snapshot,
                notes=r.notes,
                record_count=len(r.records) if r.records else 0,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in runs
        ]

    @staticmethod
    async def get_run_issues(
        session: AsyncSession,
        run_id: UUID,
    ) -> PayrollRunIssuesResponse:
        """Find pending issues that need review before payroll approval."""
        run = await session.get(PayrollRun, run_id)
        if not run:
            raise AppError(code="NOT_FOUND", message="Payroll run not found", status_code=404)

        issues: list[PayrollIssueItem] = []
        unapproved_ot_count = 0
        missing_sal_count = 0
        missing_std_count = 0

        # 1. Unapproved overtime records (status == PENDING_REVIEW with OT minutes)
        att_pairs = await PayrollRepository.get_attendance_calculations_for_period(
            session, run.period_start, run.period_end, run.country
        )
        for rec, calc in att_pairs:
            has_ot = (calc.ot1_minutes and calc.ot1_minutes > 0) or (
                calc.ot2_minutes and calc.ot2_minutes > 0
            )
            if has_ot and rec.review_status == "PENDING_REVIEW":
                unapproved_ot_count += 1
                emp = await session.get(Employee, rec.employee_id)
                issues.append(
                    PayrollIssueItem(
                        issue_type="UNAPPROVED_OVERTIME",
                        employee_id=rec.employee_id,
                        tally_id=emp.tally_id if emp else "",
                        employee_name=emp.name if emp else "",
                        work_date=rec.work_date,
                        details=f"Overtime pending review: {calc.ot1_minutes or 0}m OT1, {calc.ot2_minutes or 0}m OT2",
                    )
                )

        # 2. Employees active during period missing salary structure
        employees = await PayrollRepository.get_active_employees_for_country(session, run.country)
        for emp in employees:
            sal = await PayrollRepository.get_latest_salary_for_employee(
                session, emp.id, run.period_end
            )
            if not sal:
                missing_sal_count += 1
                issues.append(
                    PayrollIssueItem(
                        issue_type="MISSING_SALARY_STRUCTURE",
                        employee_id=emp.id,
                        tally_id=emp.tally_id,
                        employee_name=emp.name,
                        details="No effective salary structure record found for this worker.",
                    )
                )
            elif sal.standard_hours is None or sal.standard_hours <= Decimal("0.0"):
                missing_std_count += 1
                issues.append(
                    PayrollIssueItem(
                        issue_type="MISSING_STANDARD_HOURS",
                        employee_id=emp.id,
                        tally_id=emp.tally_id,
                        employee_name=emp.name,
                        details="Standard hours missing or zero on salary structure.",
                    )
                )

        return PayrollRunIssuesResponse(
            run_id=run.id,
            total_issues=len(issues),
            unapproved_overtime_count=unapproved_ot_count,
            missing_salary_structure_count=missing_sal_count,
            missing_standard_hours_count=missing_std_count,
            issues=issues,
        )

    @staticmethod
    async def approve_run(
        session: AsyncSession,
        run_id: UUID,
        user_id: UUID,
        reason: str | None = None,
    ) -> PayrollRunRead:
        """Approve a DRAFT payroll run: freeze it, snapshot records, and lock month attendance."""
        run = await session.get(PayrollRun, run_id)
        if not run:
            raise AppError(code="NOT_FOUND", message="Payroll run not found", status_code=404)

        if run.status == "APPROVED":
            raise AppError(
                code="ALREADY_APPROVED", message="Payroll run is already APPROVED", status_code=400
            )

        now = datetime.now(UTC)
        run.status = "APPROVED"
        run.approved_by_user_id = user_id
        run.approved_at = now
        run.updated_at = now

        # Lock all attendance records for that period and country
        locked_count = await PayrollRepository.lock_attendance_records(
            session, run.period_start, run.period_end, run.country
        )

        await AuditService.log_action(
            session=session,
            actor_user_id=user_id,
            action="PAYROLL_APPROVED",
            entity_type="payroll_runs",
            entity_id=str(run.id),
            diff={
                "status": "APPROVED",
                "locked_attendance_records_count": locked_count,
                "approved_at": str(now),
            },
            reason=reason
            or f"Approved payroll run #{run.run_no} for period {run.period_start} to {run.period_end}",
        )

        await event_bus.publish(
            PayrollRunApproved(
                payroll_run_id=run.id,
                country=run.country,
                actor_user_id=user_id,
            ),
            session=session,
        )

        return PayrollRunRead(
            id=run.id,
            period_start=run.period_start,
            period_end=run.period_end,
            country=run.country,
            status=run.status,
            run_no=run.run_no,
            created_by=run.created_by,
            created_by_user_id=run.created_by_user_id,
            approved_by_user_id=run.approved_by_user_id,
            approved_at=run.approved_at,
            calculation_version=run.calculation_version,
            totals_snapshot=run.totals_snapshot,
            notes=run.notes,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    @staticmethod
    async def get_worker_approved_slips(
        session: AsyncSession,
        employee_id: UUID,
        period: str | None = None,
    ) -> list[WorkerMobilePayrollSlip]:
        """Fetch worker's own approved monthly payroll slips (employer provisions stripped)."""
        records = await PayrollRepository.get_worker_approved_records(
            session, employee_id, period=period
        )
        slips: list[WorkerMobilePayrollSlip] = []

        for r in records:
            month_str = r.payroll_run.period_start.strftime("%B %Y")
            period_code = r.payroll_run.period_start.strftime("%Y-%m")
            currency = "SAR" if (r.employee and r.employee.country == "SA") else "AED"
            slips.append(
                WorkerMobilePayrollSlip(
                    payroll_record_id=r.id,
                    payroll_run_id=r.payroll_run_id,
                    month_label=month_str,
                    period=period_code,
                    period_start=r.payroll_run.period_start,
                    period_end=r.payroll_run.period_end,
                    status=r.payroll_run.status,
                    employee_tally_id=r.employee.tally_id if r.employee else None,
                    employee_name=r.employee.name if r.employee else None,
                    currency=currency,
                    standard_hours=r.standard_hours,
                    worked_hours=r.worked_hours,
                    paid_leave_hours=r.paid_leave_hours,
                    unpaid_leave_hours=r.unpaid_leave_hours,
                    salary_portion=r.salary_portion,
                    missed_hours_deduction=r.missed_hours_deduction,
                    ot1_hours=r.ot1_hours,
                    ot1_amount=r.ot1_amount,
                    ot2_hours=r.ot2_hours,
                    ot2_amount=r.ot2_amount,
                    gross_pay=r.gross_pay,
                    net_pay=r.net_pay,
                    approved_at=r.payroll_run.approved_at,
                )
            )
        return slips

    # --- Salary Revisions & Job Budget ---

    @staticmethod
    async def create_revision(
        session: AsyncSession,
        payload: SalaryRevisionCreate,
        user_id: UUID | None = None,
    ) -> SalaryRevisionDetailRead:
        existing = await PayrollRepository.get_revision_by_code(session, payload.code)
        if existing:
            raise AppError(
                code="REVISION_CODE_EXISTS",
                message=f"Salary revision with code '{payload.code}' already exists.",
                status_code=409,
            )

        rev = SalaryRevision(
            code=payload.code,
            name=payload.name,
            country=payload.country,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            status="ACTIVE",
            notes=payload.notes,
        )

        for line_in in payload.lines:
            rev.lines.append(
                SalaryRevisionLine(
                    grade_code=line_in.grade_code,
                    grade_group_title=line_in.grade_group_title,
                    basic_salary=line_in.basic_salary,
                    special_allowance=line_in.special_allowance,
                    fixed_ot_amount=line_in.fixed_ot_amount,
                    bonus=line_in.bonus,
                    visa_provision=line_in.visa_provision,
                    air_ticket_provision=line_in.air_ticket_provision,
                    uniform_provision=line_in.uniform_provision,
                    medical_provision=line_in.medical_provision,
                    accommodation_provision=line_in.accommodation_provision,
                    transportation_provision=line_in.transportation_provision,
                )
            )

        await PayrollRepository.create_revision(session, rev)
        await session.flush()

        await AuditService.log_action(
            session=session,
            actor_user_id=user_id,
            action="SALARY_REVISION_CREATED",
            entity_type="salary_revisions",
            entity_id=str(rev.id),
            diff={"code": rev.code, "lines_count": len(rev.lines)},
            reason="Salary revision created",
        )

        return await PayrollService.get_revision_detail(session, rev.code)

    @staticmethod
    async def get_revision_detail(
        session: AsyncSession,
        code: str,
    ) -> SalaryRevisionDetailRead:
        rev = await PayrollRepository.get_revision_by_code(session, code)
        if not rev:
            raise AppError(
                code="NOT_FOUND",
                message=f"Salary revision '{code}' not found",
                status_code=404,
            )

        lines_read: list[SalaryRevisionLineRead] = []
        for line in rev.lines:
            salary_portion = (
                line.basic_salary + line.special_allowance + line.fixed_ot_amount + line.bonus
            )
            provisions_sum = (
                line.visa_provision
                + line.air_ticket_provision
                + line.uniform_provision
                + line.medical_provision
                + line.accommodation_provision
                + (line.transportation_provision or Decimal("0.00"))
            )
            hourly_cost = calculate_revision_planned_hourly_cost(
                revision_salary_portion=salary_portion,
                revision_provisions_sum=provisions_sum,
            )

            lines_read.append(
                SalaryRevisionLineRead(
                    id=line.id,
                    grade_code=line.grade_code,
                    grade_group_title=line.grade_group_title,
                    basic_salary=line.basic_salary,
                    special_allowance=line.special_allowance,
                    fixed_ot_amount=line.fixed_ot_amount,
                    bonus=line.bonus,
                    visa_provision=line.visa_provision,
                    air_ticket_provision=line.air_ticket_provision,
                    uniform_provision=line.uniform_provision,
                    medical_provision=line.medical_provision,
                    accommodation_provision=line.accommodation_provision,
                    transportation_provision=line.transportation_provision,
                    total_provisions=provisions_sum,
                    total_salary_portion=salary_portion,
                    planned_hourly_cost=hourly_cost,
                )
            )

        return SalaryRevisionDetailRead(
            id=rev.id,
            code=rev.code,
            name=rev.name,
            country=rev.country,
            effective_from=rev.effective_from,
            effective_to=rev.effective_to,
            status=rev.status,
            notes=rev.notes,
            line_count=len(lines_read),
            created_at=rev.created_at,
            updated_at=rev.updated_at,
            lines=lines_read,
        )

    @staticmethod
    async def list_revisions(
        session: AsyncSession,
        country: str | None = None,
    ) -> list[SalaryRevisionRead]:
        revs = await PayrollRepository.list_revisions(session, country=country)
        return [
            SalaryRevisionRead(
                id=r.id,
                code=r.code,
                name=r.name,
                country=r.country,
                effective_from=r.effective_from,
                effective_to=r.effective_to,
                status=r.status,
                notes=r.notes,
                line_count=len(r.lines) if r.lines else 0,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in revs
        ]

    @staticmethod
    async def diff_salary_revision_import(
        session: AsyncSession,
        target_revision_code: str,
        base_revision_code: str | None,
        incoming_lines: list[SalaryRevisionLineCreate],
    ) -> SalaryRevisionImportDiffResponse:
        """Produce a side-by-side diff comparing incoming revision lines against a base revision."""
        base_rev = None
        if base_revision_code:
            base_rev = await PayrollRepository.get_revision_by_code(session, base_revision_code)
        if not base_rev:
            # Fall back to latest active revision
            revs = await PayrollRepository.list_revisions(session)
            if revs:
                base_rev = revs[0]

        base_map: dict[str, SalaryRevisionLine] = {}
        if base_rev:
            for rev_line in base_rev.lines:
                base_map[rev_line.grade_code] = rev_line

        diffs: list[SalaryRevisionLineDiff] = []
        new_count = 0
        updated_count = 0
        unchanged_count = 0

        fields_to_compare = [
            ("basic_salary", "Basic Salary"),
            ("special_allowance", "Special Allowance"),
            ("fixed_ot_amount", "Fixed OT Amount"),
            ("bonus", "Bonus"),
            ("visa_provision", "Visa Provision"),
            ("air_ticket_provision", "Air Ticket Provision"),
            ("uniform_provision", "Uniform Provision"),
            ("medical_provision", "Medical Provision"),
            ("accommodation_provision", "Accommodation Provision"),
            ("transportation_provision", "Transportation Provision"),
        ]

        for inc in incoming_lines:
            base_line = base_map.get(inc.grade_code)
            if not base_line:
                new_count += 1
                for f, label in fields_to_compare:
                    diffs.append(
                        SalaryRevisionLineDiff(
                            grade_code=inc.grade_code,
                            field_name=label,
                            old_value=None,
                            new_value=getattr(inc, f),
                            is_changed=True,
                        )
                    )
            else:
                line_changed = False
                for f, label in fields_to_compare:
                    old_v = getattr(base_line, f)
                    new_v = getattr(inc, f)
                    is_c = old_v != new_v
                    if is_c:
                        line_changed = True
                    diffs.append(
                        SalaryRevisionLineDiff(
                            grade_code=inc.grade_code,
                            field_name=label,
                            old_value=old_v,
                            new_value=new_v,
                            is_changed=is_c,
                        )
                    )
                if line_changed:
                    updated_count += 1
                else:
                    unchanged_count += 1

        return SalaryRevisionImportDiffResponse(
            target_revision_code=target_revision_code,
            base_revision_code=base_rev.code if base_rev else None,
            new_grades_count=new_count,
            updated_grades_count=updated_count,
            unchanged_grades_count=unchanged_count,
            diffs=diffs,
            preview_lines=incoming_lines,
        )

    @staticmethod
    async def export_salary_revision_template(
        session: AsyncSession,
        revision_code: str | None = None,
    ) -> bytes:
        """Export salary revision as a professionally formatted Excel (.xlsx) workbook.

        If revision_code is specified, pre-populates existing grade lines so user can edit.
        """
        rev = None
        if revision_code and revision_code.upper() != "ALL":
            rev = await PayrollRepository.get_revision_by_code(session, revision_code)
        if not rev:
            revs = await PayrollRepository.list_revisions(session)
            if revs:
                rev = revs[0]

        wb = openpyxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws.title = "Salary Revision Template"

        headers = [
            ("grade_code", "Grade Code"),
            ("grade_group_title", "Grade Group Title"),
            ("basic_salary", "Basic Salary"),
            ("special_allowance", "Special Allowance"),
            ("fixed_ot_amount", "Fixed OT Amount"),
            ("bonus", "Bonus"),
            ("visa_provision", "Visa Provision"),
            ("air_ticket_provision", "Air Ticket Provision"),
            ("uniform_provision", "Uniform Provision"),
            ("medical_provision", "Medical Provision"),
            ("accommodation_provision", "Accommodation Provision"),
            ("transportation_provision", "Transportation Provision"),
        ]

        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        center_align = Alignment(horizontal="center", vertical="center")
        left_align = Alignment(horizontal="left", vertical="center")
        right_align = Alignment(horizontal="right", vertical="center")

        thin_border = Border(
            left=Side(style="thin", color="E2E8F0"),
            right=Side(style="thin", color="E2E8F0"),
            top=Side(style="thin", color="E2E8F0"),
            bottom=Side(style="thin", color="E2E8F0"),
        )

        for col_idx, (_, header_title) in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header_title)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align

        lines = rev.lines if rev else []
        row_idx = 2

        if lines:
            for line in lines:
                row_data = [
                    line.grade_code,
                    line.grade_group_title or "",
                    float(line.basic_salary),
                    float(line.special_allowance),
                    float(line.fixed_ot_amount),
                    float(line.bonus),
                    float(line.visa_provision),
                    float(line.air_ticket_provision),
                    float(line.uniform_provision),
                    float(line.medical_provision),
                    float(line.accommodation_provision),
                    float(line.transportation_provision or 0.0),
                ]
                for col_idx, val in enumerate(row_data, start=1):
                    cell = ws.cell(row=row_idx, column=col_idx, value=val)
                    cell.border = thin_border
                    if col_idx in (1, 2):
                        cell.alignment = left_align
                    else:
                        cell.alignment = right_align
                        cell.number_format = "#,##0.00"
                row_idx += 1
        else:
            sample_data = [
                (
                    "GE",
                    "General Employees / Helpers",
                    1200.0,
                    150.0,
                    100.0,
                    0.0,
                    100.0,
                    75.0,
                    25.0,
                    50.0,
                    300.0,
                    0.0,
                ),
                (
                    "S1",
                    "Skilled Technicians Level 1",
                    1800.0,
                    250.0,
                    150.0,
                    50.0,
                    100.0,
                    75.0,
                    25.0,
                    50.0,
                    350.0,
                    0.0,
                ),
                (
                    "SUP",
                    "Site Supervisors",
                    2800.0,
                    400.0,
                    200.0,
                    100.0,
                    120.0,
                    100.0,
                    30.0,
                    75.0,
                    500.0,
                    0.0,
                ),
            ]
            for s in sample_data:
                for col_idx, val in enumerate(s, start=1):
                    cell = ws.cell(row=row_idx, column=col_idx, value=val)
                    cell.border = thin_border
                    if col_idx in (1, 2):
                        cell.alignment = left_align
                    else:
                        cell.alignment = right_align
                        cell.number_format = "#,##0.00"
                row_idx += 1

        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(int(col[0].column or 1))
            ws.column_dimensions[col_letter].width = max(max_len + 4, 15)

        stream = io.BytesIO()
        wb.save(stream)
        stream.seek(0)
        return stream.getvalue()

    @staticmethod
    def parse_salary_revision_file(
        file_content: bytes,
        filename: str,
    ) -> list[SalaryRevisionLineCreate]:
        """Parse an Excel (.xlsx/.xls) or CSV file into SalaryRevisionLineCreate objects."""
        lower_name = filename.lower()
        rows_data: list[dict[str, str | Decimal]] = []

        if lower_name.endswith((".xlsx", ".xls")):
            wb = openpyxl.load_workbook(io.BytesIO(file_content), data_only=True)

            # Smart sheet detection: look for known revision line sheet names first
            ws = None
            preferred_line_sheets = [
                "Salary_Revision_Lines",
                "salary_revision_lines",
                "Revision_Lines",
                "revision_lines",
                "Salary Revision Template",
            ]
            for s_name in preferred_line_sheets:
                if s_name in wb.sheetnames:
                    ws = wb[s_name]
                    break

            # If not found by name, scan sheets for one with grade and basic/salary headers
            if ws is None:
                for s_name in wb.sheetnames:
                    candidate = wb[s_name]
                    for r in list(candidate.iter_rows(max_row=10, values_only=True)):
                        str_cells = [str(c).strip().lower() for c in r if c is not None]
                        if (
                            len(str_cells) >= 3
                            and any("grade" in c for c in str_cells)
                            and any("basic" in c or "salary" in c for c in str_cells)
                        ):
                            ws = candidate
                            break
                    if ws is not None:
                        break

            if ws is None:
                ws = wb.active

            assert ws is not None
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                raise AppError(code="INVALID_FILE", message="The uploaded spreadsheet is empty.")

            # Find real header row (must have >= 3 non-empty cells and match grade + basic)
            header_row_idx = 0
            headers: list[str] = []
            for idx, r in enumerate(rows):
                str_cells = [
                    str(c).strip().lower().replace(" ", "_").replace("-", "_")
                    for c in r
                    if c is not None
                ]
                if (
                    len(str_cells) >= 3
                    and any("grade" in c for c in str_cells)
                    and any("basic" in c or "salary" in c for c in str_cells)
                ):
                    header_row_idx = idx
                    headers = [
                        str(c).strip().lower().replace(" ", "_").replace("-", "_")
                        if c is not None
                        else ""
                        for c in r
                    ]
                    break

            if not headers:
                headers = [
                    str(c).strip().lower().replace(" ", "_").replace("-", "_")
                    if c is not None
                    else ""
                    for c in rows[0]
                ]
                header_row_idx = 0

            for r in rows[header_row_idx + 1 :]:
                if not r or all(c is None or str(c).strip() == "" for c in r):
                    continue
                row_dict: dict[str, str | Decimal] = {}
                for col_name, val in zip(headers, r, strict=False):
                    if col_name and val is not None:
                        row_dict[col_name] = str(val).strip()
                if row_dict:
                    rows_data.append(row_dict)
        else:
            try:
                decoded = file_content.decode("utf-8-sig")
            except UnicodeDecodeError:
                decoded = file_content.decode("latin-1")

            reader = csv.DictReader(io.StringIO(decoded))
            for r in reader:
                cleaned: dict[str, str | Decimal] = {
                    k.strip().lower().replace(" ", "_").replace("-", "_"): v.strip()
                    for k, v in r.items()
                    if k
                }
                if cleaned:
                    rows_data.append(cleaned)

        lines: list[SalaryRevisionLineCreate] = []

        def to_dec(val: object) -> Decimal:
            if val is None or str(val).strip() == "":
                return Decimal("0.00")
            s = str(val).replace(",", "").replace("$", "").replace("AED", "").strip()
            try:
                return round_money(Decimal(s))
            except Exception:
                return Decimal("0.00")

        def find_field(d: Mapping[str, object], *possible_keys: str) -> object:
            for k in possible_keys:
                if k in d:
                    return d[k]
                norm_k = k.lower().replace(" ", "_")
                for dk, dv in d.items():
                    if dk == norm_k or norm_k in dk:
                        return dv
            return None

        for d in rows_data:
            grade_code_val = find_field(d, "grade_code", "grade", "code")
            if not grade_code_val:
                continue
            grade_code = str(grade_code_val).strip()
            title = find_field(d, "grade_group_title", "title", "group_title", "description")

            lines.append(
                SalaryRevisionLineCreate(
                    grade_code=grade_code,
                    grade_group_title=str(title).strip() if title else None,
                    basic_salary=to_dec(find_field(d, "basic_salary", "basic")),
                    special_allowance=to_dec(find_field(d, "special_allowance", "special")),
                    fixed_ot_amount=to_dec(
                        find_field(d, "fixed_ot_amount", "fixed_ot", "ot_amount")
                    ),
                    bonus=to_dec(find_field(d, "bonus")),
                    visa_provision=to_dec(find_field(d, "visa_provision", "visa")),
                    air_ticket_provision=to_dec(
                        find_field(d, "air_ticket_provision", "air_ticket", "ticket")
                    ),
                    uniform_provision=to_dec(find_field(d, "uniform_provision", "uniform")),
                    medical_provision=to_dec(find_field(d, "medical_provision", "medical")),
                    accommodation_provision=to_dec(
                        find_field(d, "accommodation_provision", "accommodation")
                    ),
                    transportation_provision=to_dec(
                        find_field(d, "transportation_provision", "transportation")
                    ),
                )
            )

        if not lines:
            raise AppError(
                code="INVALID_DATA",
                message="No valid grade lines found in file. Please ensure 'Grade Code' column is present.",
            )

        return lines

    @staticmethod
    async def preview_salary_revision_file(
        session: AsyncSession,
        file_content: bytes,
        filename: str,
        target_revision_code: str,
        base_revision_code: str | None = None,
    ) -> SalaryRevisionImportDiffResponse:
        """Parse uploaded Excel/CSV file and calculate side-by-side diff against base revision."""
        lines = PayrollService.parse_salary_revision_file(file_content, filename)
        return await PayrollService.diff_salary_revision_import(
            session=session,
            target_revision_code=target_revision_code,
            base_revision_code=base_revision_code,
            incoming_lines=lines,
        )

    @staticmethod
    async def get_budget_vs_actual(
        session: AsyncSession,
        country: str | None = None,
        as_of_date: date | None = None,
    ) -> list[WorksiteBudgetVsActualItem]:
        """Calculate dynamic contract budget from assigned revision lines and items vs actual allocated cost."""
        target_date = as_of_date or datetime.now(UTC).date()
        worksites = await PayrollRepository.get_worksites_and_items(session, country=country)

        items: list[WorksiteBudgetVsActualItem] = []

        for ws in worksites:
            # 1. Resolve assigned or latest active revision
            rev = await PayrollRepository.get_active_revision_for_worksite(
                session, ws.country, ws.salary_revision_code
            )

            # Map grade_code to planned hourly cost from revision
            grade_hourly_rates: dict[str, Decimal] = {}
            if rev:
                for line in rev.lines:
                    portion = (
                        line.basic_salary
                        + line.special_allowance
                        + line.fixed_ot_amount
                        + line.bonus
                    )
                    prov = (
                        line.visa_provision
                        + line.air_ticket_provision
                        + line.uniform_provision
                        + line.medical_provision
                        + line.accommodation_provision
                        + (line.transportation_provision or Decimal("0.00"))
                    )
                    grade_hourly_rates[line.grade_code] = calculate_revision_planned_hourly_cost(
                        portion, prov
                    )

            # 2. Compute annual planned man-hours and labor budget from job items
            annual_man_hours = Decimal("0.0")
            annual_labor_budget = Decimal("0.00")
            budget_only_annual_cost = Decimal("0.00")

            # Load budget-only staff types for this country
            raw_budget_types = await SettingsService.get_setting(
                session, "budget_only_staff_types", country=ws.country, default=[]
            )
            budget_only_types: set[str] = set()
            if isinstance(raw_budget_types, list):
                budget_only_types = {str(x).strip().lower() for x in raw_budget_types}

            for item in ws.items:
                if not item.is_active:
                    continue
                # Expected annual occurrences
                unit = item.frequency_unit
                freq_count = Decimal(str(item.occurrences_per_period or 1))
                if unit == "WEEK":
                    annual_occurrences = freq_count * Decimal("52")
                elif unit == "MONTH":
                    annual_occurrences = freq_count * Decimal("12")
                elif unit == "QUARTER":
                    annual_occurrences = freq_count * Decimal("4")
                else:  # YEAR
                    annual_occurrences = freq_count

                staff_cnt = Decimal(str(item.required_staff_count or 1))
                hrs_per_occ = Decimal(str(item.hours_per_occurrence_per_staff or 8.0))
                item_annual_hours = annual_occurrences * staff_cnt * hrs_per_occ
                annual_man_hours += item_annual_hours

                # Lookup grade rate
                grade = item.planned_grade_code or ""
                # Strip year suffix if present (e.g. "GE-2024" -> "GE")
                base_grade = grade.split("-")[0] if "-" in grade else grade
                rate = grade_hourly_rates.get(
                    grade,
                    grade_hourly_rates.get(base_grade, Decimal("10.00")),
                )
                item_annual_cost = round_money(item_annual_hours * rate)
                annual_labor_budget += item_annual_cost

                # If staff grade is budget-only, track its planned cost so actual cost
                # can be credited equally (since no field attendance is tracked for it)
                if (item.staff_grade_description or "").strip().lower() in budget_only_types:
                    budget_only_annual_cost += item_annual_cost

            # Manual override wins if set on the worksite
            if ws.budget_amount and ws.budget_amount > Decimal("0.00"):
                contract_annual_budget = ws.budget_amount
            else:
                contract_annual_budget = annual_labor_budget

            # 3. Calculate pro-rated budget
            start = ws.start_date or date(target_date.year, 1, 1)
            elapsed_days = (target_date - start).days
            if elapsed_days < 0:
                elapsed_days = 0
            fraction = min(Decimal("1.0"), Decimal(str(elapsed_days)) / Decimal("365.0"))
            prorated_budget = round_money(contract_annual_budget * fraction)
            budget_only_prorated_cost = round_money(budget_only_annual_cost * fraction)

            # 4. Compute cumulative actual cost allocated from job_cost_allocations
            from sqlalchemy import func, select

            act_stmt = (
                select(func.sum(JobCostAllocation.allocated_amount))
                .join(PayrollRecord, JobCostAllocation.payroll_record_id == PayrollRecord.id)
                .join(PayrollRun, PayrollRecord.payroll_run_id == PayrollRun.id)
                .where(
                    JobCostAllocation.worksite_id == ws.id,
                    PayrollRun.status == "APPROVED",
                )
            )
            act_res = await session.execute(act_stmt)
            raw_field_actual = Decimal(str(act_res.scalar() or "0.00"))
            # For budget-only staff positions, actual cost equals planned cost
            # so overall job costing preserves pure operational variance without false skew
            actual_cost = raw_field_actual + budget_only_prorated_cost

            variance = actual_cost - prorated_budget
            variance_pct = (
                round_money((variance / prorated_budget) * Decimal("100.0"))
                if prorated_budget > Decimal("0.00")
                else Decimal("0.0")
            )
            is_over = variance > Decimal("0.00")
            is_under = variance < Decimal("0.00")

            items.append(
                WorksiteBudgetVsActualItem(
                    worksite_id=ws.id,
                    job_number=ws.job_number,
                    job_name=ws.job_name,
                    country=ws.country,
                    salary_revision_code=ws.salary_revision_code or (rev.code if rev else None),
                    assigned_revision_code=ws.salary_revision_code or (rev.code if rev else None),
                    annual_planned_man_hours=annual_man_hours,
                    annual_labor_budget=contract_annual_budget,
                    prorated_budget=prorated_budget,
                    pro_rated_budget=prorated_budget,
                    actual_cost_allocated=actual_cost,
                    actual_allocated_cost=actual_cost,
                    variance=variance,
                    variance_amount=variance,
                    variance_percent=variance_pct,
                    is_over_budget=is_over,
                    is_under_budget=is_under,
                    manual_budget_override=ws.budget_amount,
                    is_custom_budget_override=bool(
                        ws.budget_amount and ws.budget_amount > Decimal("0.00")
                    ),
                )
            )

        return items

    @staticmethod
    async def check_auto_draft_runs(
        session: AsyncSession,
        as_of_date: date | None = None,
    ) -> list[PayrollRunRead]:
        """Check for completed previous calendar months past delay days and auto-generate draft."""
        today = as_of_date or datetime.now(UTC).date()
        delay_days = await SettingsService.get_setting(
            session=session,
            key="payroll_auto_run_delay_days",
            as_of=today,
            default=5,
        )
        delay = int(delay_days or 5)

        # Previous month:
        if today.month == 1:
            prev_year = today.year - 1
            prev_month = 12
        else:
            prev_year = today.year
            prev_month = today.month - 1

        import calendar

        _, last_day = calendar.monthrange(prev_year, prev_month)
        prev_start = date(prev_year, prev_month, 1)
        prev_end = date(prev_year, prev_month, last_day)

        # Days elapsed since month end
        days_since_close = (today - prev_end).days
        generated_runs: list[PayrollRunRead] = []

        if days_since_close >= delay:
            for country in ("AE", "SA"):
                existing = await PayrollRepository.get_latest_run_for_period(
                    session, prev_start, prev_end, country
                )
                if not existing:
                    # Generate automatic draft
                    detail = await PayrollService.generate_draft_run(
                        session=session,
                        payload=PayrollRunCreate(
                            period_start=prev_start,
                            period_end=prev_end,
                            country=country,
                            notes=f"Auto-generated draft {delay} days after month-end",
                        ),
                        user_id=None,
                        actor_role="SYSTEM",
                    )
                    generated_runs.append(
                        PayrollRunRead(
                            id=detail.id,
                            period_start=detail.period_start,
                            period_end=detail.period_end,
                            country=detail.country,
                            status=detail.status,
                            run_no=detail.run_no,
                            created_by=detail.created_by,
                            created_by_user_id=detail.created_by_user_id,
                            approved_by_user_id=detail.approved_by_user_id,
                            approved_at=detail.approved_at,
                            calculation_version=detail.calculation_version,
                            totals_snapshot=detail.totals_snapshot,
                            notes=detail.notes,
                            record_count=detail.record_count,
                            created_at=detail.created_at,
                            updated_at=detail.updated_at,
                        )
                    )
        return generated_runs
