"""Service for employee salary structures and history."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.modules.audit import AuditService
from fw.modules.org import Employee
from fw.modules.payroll.models import EmployeeSalary
from fw.modules.payroll.schemas import (
    EmployeeSalaryCreate,
    EmployeeSalaryHistoryResponse,
    EmployeeSalaryRead,
    SalaryStructureListItem,
)
from fw.rules.payroll import (
    calculate_salary_difference,
    calculate_salary_portion,
    compute_next_payroll_month_start,
)


class PayrollSalaryService:
    @staticmethod
    async def get_salary_history(
        session: AsyncSession,
        employee_id: UUID,
    ) -> EmployeeSalaryHistoryResponse | None:
        """Fetch full salary structure history and change difference for an employee."""
        emp_stmt = select(Employee).where(Employee.id == employee_id)
        emp_res = await session.execute(emp_stmt)
        emp = emp_res.scalar_one_or_none()
        if not emp:
            return None

        stmt = (
            select(EmployeeSalary)
            .where(EmployeeSalary.employee_id == employee_id)
            .order_by(EmployeeSalary.effective_from.asc(), EmployeeSalary.created_at.asc())
        )
        res = await session.execute(stmt)
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
            item = EmployeeSalaryRead(
                id=r.id,
                employee_id=r.employee_id,
                tally_id=emp.tally_id,
                employee_name=emp.name,
                effective_from=r.effective_from,
                standard_hours=r.standard_hours,
                basic_salary=r.basic_salary,
                special_allowance=r.special_allowance,
                fixed_ot_amount=r.fixed_ot_amount,
                bonus=r.bonus,
                telephone_allowance=r.telephone_allowance,
                housing_transport_allowance=r.housing_transport_allowance,
                salary_portion=portion,
                difference=diff,
                created_at=r.created_at,
            )
            history_items.append(item)
            prev_portion = portion

        # In reverse chronological order for history display
        history_items.reverse()

        current = history_items[0] if history_items else None
        last_change_date = current.effective_from if current else None
        last_change_diff = current.difference if current else None

        return EmployeeSalaryHistoryResponse(
            employee_id=emp.id,
            tally_id=emp.tally_id,
            employee_name=emp.name,
            current_salary=current,
            last_change_date=last_change_date,
            last_change_difference=last_change_diff,
            history=history_items,
        )

    @staticmethod
    async def list_salary_structures(
        session: AsyncSession,
        country: str | None = None,
        as_of: date | None = None,
    ) -> list[SalaryStructureListItem]:
        """List active salary structures across all workers."""
        _query_date = as_of or date.today()
        stmt = (
            select(Employee).where(Employee.is_active.is_(True)).order_by(Employee.tally_id.asc())
        )
        if country:
            stmt = stmt.where(Employee.country == country)

        emp_res = await session.execute(stmt)
        employees = list(emp_res.scalars().all())

        items: list[SalaryStructureListItem] = []
        for emp in employees:
            history_resp = await PayrollSalaryService.get_salary_history(session, emp.id)
            if history_resp and history_resp.current_salary:
                curr = history_resp.current_salary
                items.append(
                    SalaryStructureListItem(
                        employee_id=emp.id,
                        tally_id=emp.tally_id,
                        name=emp.name,
                        role=emp.role,
                        country=emp.country,
                        standard_hours=curr.standard_hours,
                        salary_portion=curr.salary_portion,
                        basic_salary=curr.basic_salary,
                        effective_from=curr.effective_from,
                        last_change_date=history_resp.last_change_date,
                        difference=curr.difference,
                    )
                )

        return items

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
            if batch_id:
                existing.import_batch_id = batch_id
            target = existing
            action = "UPDATE"
        else:
            target = EmployeeSalary(
                employee_id=employee_id,
                effective_from=effective_from,
                standard_hours=data.standard_hours,
                basic_salary=data.basic_salary,
                special_allowance=data.special_allowance,
                fixed_ot_amount=data.fixed_ot_amount,
                bonus=data.bonus,
                telephone_allowance=data.telephone_allowance,
                housing_transport_allowance=data.housing_transport_allowance,
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
