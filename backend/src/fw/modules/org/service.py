from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.errors import AppError
from fw.core.events import EmployeeProfileChanged, event_bus
from fw.modules.audit import AuditLog, AuditService
from fw.modules.identity import User, hash_password
from fw.modules.org.models import (
    Accommodation,
    Employee,
    EmployeeDocument,
    EmployeeGradeHistory,
    EmployeeReportingLine,
    Group,
    RegisteredDevice,
    Zone,
)
from fw.modules.org.schemas import (
    AccommodationCreate,
    AccommodationUpdate,
    EmployeeBulkUpdateRequest,
    EmployeeCreate,
    EmployeeDocumentCreate,
    EmployeeUpdate,
    ExpiringDocumentItem,
    ExpiringDocumentsResponse,
    GradeChangeRequest,
    GroupCreate,
    GroupUpdate,
    HierarchyTreeNode,
    HierarchyViolationItem,
    ReportingLineCreate,
    ReportingLineRead,
    TallyIdChangeRequest,
    TallyIdCheckResponse,
    TallyIdPreviousUse,
    ZoneCreate,
    ZoneUpdate,
)
from fw.modules.settings import SettingsService
from fw.rules.hierarchy import (
    HierarchyRuleViolation,
    compute_transitive_scope,
    validate_reporting_link,
)


class ScopeService:
    @staticmethod
    async def get_scoped_employee_ids(
        session: AsyncSession,
        user: User,
    ) -> set[UUID] | None:
        """Resolve employee IDs in user's reporting scope.

        Returns None if user is ADMIN (unrestricted access).
        Returns {user.employee_id} if user is WORKER.
        For other roles, computes transitive descendant closure from reporting lines.
        """
        if user.role == "ADMIN":
            return None

        if user.employee_id is None:
            return set()

        if user.role == "WORKER":
            return {user.employee_id}

        # For ENGINEER, SUPERINTENDENT, SUPERVISOR:
        # Load all reporting lines to compute transitive descendant scope
        query = select(EmployeeReportingLine.employee_id, EmployeeReportingLine.manager_id).where(
            EmployeeReportingLine.is_active == True  # noqa: E712
        )
        result = await session.execute(query)
        links = [(str(row.employee_id), str(row.manager_id)) for row in result.all()]

        scoped_str_ids = compute_transitive_scope(str(user.employee_id), links)
        return {UUID(eid) for eid in scoped_str_ids}


class OrgService:
    get_scoped_employee_ids = ScopeService.get_scoped_employee_ids

    @staticmethod
    async def list_employees(
        session: AsyncSession,
        scoped_ids: set[UUID] | None = None,
        role: str | None = None,
        sgd: str | None = None,
        grade_code: str | None = None,
        manager_id: UUID | None = None,
        accommodation_id: UUID | None = None,
        has_accommodation: bool | None = None,
        country: str | None = None,
        is_active: bool | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Employee]:
        query = select(Employee).order_by(Employee.name.asc())

        if scoped_ids is not None:
            query = query.where(Employee.id.in_(scoped_ids))

        if role:
            query = query.where(Employee.role == role)
        else:
            query = query.where(Employee.tally_id != "ADMIN001")
        if sgd:
            query = query.where(Employee.staff_grade_description == sgd)
        if grade_code:
            query = query.where(Employee.grade_code == grade_code)
        if country:
            query = query.where(Employee.country == country)
        if accommodation_id is not None:
            query = query.where(Employee.accommodation_id == accommodation_id)
        elif has_accommodation is True:
            query = query.where(Employee.accommodation_id.isnot(None))
        elif has_accommodation is False:
            query = query.where(Employee.accommodation_id.is_(None))
        if is_active is not None:
            query = query.where(Employee.is_active == is_active)
        if q:
            search = f"%{q}%"
            query = query.where(or_(Employee.name.ilike(search), Employee.tally_id.ilike(search)))
        if manager_id:
            subquery = select(EmployeeReportingLine.employee_id).where(
                EmployeeReportingLine.manager_id == manager_id,
                EmployeeReportingLine.is_active == True,  # noqa: E712
            )
            query = query.where(Employee.id.in_(subquery))

        query = query.limit(limit).offset(offset)
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_employee(
        session: AsyncSession,
        employee_id: UUID,
        scoped_ids: set[UUID] | None = None,
    ) -> Employee:
        if scoped_ids is not None and employee_id not in scoped_ids:
            raise AppError(
                code="OUT_OF_SCOPE",
                message="Employee is out of your reporting scope.",
                status_code=403,
            )

        query = select(Employee).where(Employee.id == employee_id)
        result = await session.execute(query)
        employee = result.scalar_one_or_none()
        if not employee:
            raise AppError(code="NOT_FOUND", message="Employee not found.", status_code=404)
        return employee

    @staticmethod
    async def check_tally_id(
        session: AsyncSession,
        tally_id: str,
        exclude_employee_id: UUID | None = None,
    ) -> TallyIdCheckResponse:
        """Check whether a tally_id is available and whether it was ever previously used."""
        clean_id = tally_id.strip()
        emp_stmt = select(Employee).where(Employee.tally_id == clean_id)
        if exclude_employee_id is not None:
            emp_stmt = emp_stmt.where(Employee.id != exclude_employee_id)
        existing_emp = (await session.execute(emp_stmt)).scalar_one_or_none()

        user_stmt = select(User).where(User.username == clean_id)
        if exclude_employee_id is not None:
            user_stmt = user_stmt.where(
                or_(User.employee_id.is_(None), User.employee_id != exclude_employee_id)
            )
        existing_user = (await session.execute(user_stmt)).scalar_one_or_none()

        available = existing_emp is None and existing_user is None

        # Check historical CHANGE_TALLY_ID audit logs for previous usage of this tally_id
        audit_stmt = (
            select(AuditLog)
            .where(AuditLog.action == "CHANGE_TALLY_ID")
            .order_by(AuditLog.created_at.desc())
        )
        audit_rows = (await session.execute(audit_stmt)).scalars().all()
        previous_uses: list[TallyIdPreviousUse] = []
        for log in audit_rows:
            d = log.diff or {}
            if str(d.get("old_tally_id", "")).strip() == clean_id:
                previous_uses.append(
                    TallyIdPreviousUse(
                        employee_id=str(log.entity_id),
                        employee_name=d.get("employee_name"),
                        new_tally_id=d.get("new_tally_id"),
                        changed_at=log.created_at,
                    )
                )

        return TallyIdCheckResponse(
            tally_id=clean_id,
            available=available,
            in_use_by_employee_id=existing_emp.id if existing_emp else None,
            in_use_by_name=existing_emp.name if existing_emp else None,
            previously_used=len(previous_uses) > 0,
            previous_uses=previous_uses,
        )

    @staticmethod
    async def change_tally_id(
        session: AsyncSession,
        employee_id: UUID,
        request: TallyIdChangeRequest,
        actor_user_id: UUID,
        actor_role: str,
    ) -> Employee:
        """Admin changes an employee's tally_id (e.g. temporary -> permanent) and linked login username."""
        new_id = request.new_tally_id.strip()
        if not new_id:
            raise AppError(
                code="VALIDATION_ERROR",
                message="New Tally ID cannot be empty.",
                status_code=400,
            )
        if not request.reason or not request.reason.strip():
            raise AppError(
                code="REASON_REQUIRED",
                message="A reason for changing the Tally ID is required.",
                status_code=400,
            )

        employee = await session.get(Employee, employee_id)
        if not employee:
            raise AppError(code="NOT_FOUND", message="Employee not found.", status_code=404)
        if employee.role == "ADMIN" or employee.tally_id == "ADMIN001":
            raise AppError(
                code="FORBIDDEN",
                message="System admin account Tally ID cannot be changed.",
                status_code=400,
            )
        if employee.tally_id == new_id:
            raise AppError(
                code="VALIDATION_ERROR",
                message="New Tally ID is identical to the current Tally ID.",
                status_code=400,
            )

        check = await OrgService.check_tally_id(session, new_id, exclude_employee_id=employee.id)
        if not check.available:
            raise AppError(
                code="DUPLICATE_TALLY_ID",
                message=f"Tally ID '{new_id}' is already assigned to another account.",
                status_code=409,
            )
        if check.previously_used and not request.confirm_reuse:
            prev = check.previous_uses[0]
            raise AppError(
                code="TALLY_ID_PREVIOUSLY_USED",
                message=(
                    f"Tally ID '{new_id}' was previously assigned to "
                    f"{prev.employee_name or prev.employee_id} (changed to {prev.new_tally_id}). "
                    "Confirm reuse explicitly to proceed."
                ),
                status_code=409,
            )

        old_id = employee.tally_id
        employee.tally_id = new_id
        employee.version += 1

        # Update linked User.username atomically (active JWT sessions remain valid by UUID)
        user_stmt = select(User).where(
            or_(User.employee_id == employee.id, User.username == old_id)
        )
        linked_user = (await session.execute(user_stmt)).scalars().first()
        if linked_user:
            linked_user.username = new_id

        await session.flush()

        await AuditService.log_action(
            session=session,
            action="CHANGE_TALLY_ID",
            entity_type="employee",
            entity_id=str(employee.id),
            diff={
                "old_tally_id": old_id,
                "new_tally_id": new_id,
                "employee_name": employee.name,
                "reused_historical_id": check.previously_used,
            },
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            reason=request.reason.strip(),
        )
        await event_bus.publish(EmployeeProfileChanged(employee_id=employee.id), session=session)
        return employee

    @staticmethod
    async def count_active_direct_reports(session: AsyncSession, manager_id: UUID) -> int:
        """Count distinct active employees who report directly to manager_id."""
        stmt = (
            select(func.count(func.distinct(EmployeeReportingLine.employee_id)))
            .join(Employee, Employee.id == EmployeeReportingLine.employee_id)
            .where(
                EmployeeReportingLine.manager_id == manager_id,
                EmployeeReportingLine.is_active.is_(True),
                Employee.is_active.is_(True),
            )
        )
        return int((await session.execute(stmt)).scalar_one() or 0)

    @staticmethod
    async def create_employee(
        session: AsyncSession,
        data: EmployeeCreate,
        default_password: str,
        actor_user_id: UUID,
        actor_role: str,
    ) -> Employee:
        clean_tally = data.tally_id.strip()
        if data.role.strip().upper() == "ADMIN":
            raise AppError(
                code="ADMIN_ROLE_RESERVED",
                message=(
                    "Cannot create an employee with role ADMIN. "
                    "The system administrator (ADMIN001) is a single standalone account."
                ),
                status_code=400,
            )
        if clean_tally.upper() == "ADMIN001":
            raise AppError(
                code="RESERVED_TALLY_ID",
                message="Tally ID 'ADMIN001' is reserved for the standalone system administrator.",
                status_code=400,
            )
        check = await OrgService.check_tally_id(session, clean_tally)
        if not check.available:
            raise AppError(
                code="DUPLICATE_TALLY_ID",
                message=f"Employee with ID '{clean_tally}' already exists.",
                status_code=409,
            )
        if check.previously_used and not data.confirm_reuse:
            prev = check.previous_uses[0]
            raise AppError(
                code="TALLY_ID_PREVIOUSLY_USED",
                message=(
                    f"Tally ID '{clean_tally}' was previously assigned to "
                    f"{prev.employee_name or prev.employee_id} (changed to {prev.new_tally_id}). "
                    "Confirm reuse explicitly to create an employee with this ID."
                ),
                status_code=409,
            )

        employee = Employee(
            tally_id=clean_tally,
            name=data.name,
            phone=data.phone,
            email=data.email,
            role=data.role,
            grade_code=data.grade_code,
            staff_grade_description=data.staff_grade_description,
            accommodation_id=data.accommodation_id,
            weekly_off_day=data.weekly_off_day,
            is_driver=data.is_driver,
            country=data.country,
            break_override_minutes=data.break_override_minutes,
            join_date=data.join_date,
            employment_end_date=data.employment_end_date,
        )
        session.add(employee)
        await session.flush()

        # Create linked user account with default password (DEC-53)
        user = User(
            employee_id=employee.id,
            username=employee.tally_id,
            credential_hash=hash_password(default_password),
            role=employee.role,
            must_change_password=True,
        )
        session.add(user)
        await session.flush()

        await AuditService.log_action(
            session=session,
            action="CREATE_EMPLOYEE",
            entity_type="employee",
            entity_id=str(employee.id),
            diff={"tally_id": employee.tally_id, "name": employee.name, "role": employee.role},
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
        return employee

    @staticmethod
    async def update_employee(
        session: AsyncSession,
        employee_id: UUID,
        data: EmployeeUpdate,
        scoped_ids: set[UUID] | None,
        actor_user_id: UUID,
        actor_role: str,
    ) -> Employee:
        employee = await OrgService.get_employee(session, employee_id, scoped_ids)

        if employee.version != data.version:
            raise AppError(
                code="VERSION_CONFLICT",
                message="Employee record was modified by another request.",
                status_code=409,
            )

        if data.role is not None and data.role.strip().upper() == "ADMIN":
            raise AppError(
                code="ADMIN_ROLE_RESERVED",
                message=(
                    "Cannot assign role ADMIN to an employee. "
                    "The system administrator (ADMIN001) is a single standalone account."
                ),
                status_code=400,
            )

        diff: dict[str, Any] = {}
        # Apply fields
        for field, value in data.model_dump(
            exclude_unset=True, exclude={"version", "effective_from"}
        ).items():
            old_val = getattr(employee, field)
            if old_val != value:
                diff[field] = {"old": str(old_val), "new": str(value)}
                setattr(employee, field, value)

        employee.version += 1
        await session.flush()

        if diff:
            await AuditService.log_action(
                session=session,
                action="UPDATE_EMPLOYEE",
                entity_type="employee",
                entity_id=str(employee.id),
                diff=diff,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
            )
            await event_bus.publish(
                EmployeeProfileChanged(employee_id=employee.id), session=session
            )
        return employee

    @staticmethod
    async def bulk_update(
        session: AsyncSession,
        request: EmployeeBulkUpdateRequest,
        scoped_ids: set[UUID] | None,
        actor_user_id: UUID,
        actor_role: str,
    ) -> int:
        """Bulk update accommodation, break override, or weekly off day (BR-EM-10)."""
        count = 0
        for emp_id in request.employee_ids:
            if scoped_ids is not None and emp_id not in scoped_ids:
                continue

            query = select(Employee).where(Employee.id == emp_id)
            res = await session.execute(query)
            employee = res.scalar_one_or_none()
            if not employee:
                continue

            diff: dict[str, Any] = {}
            if request.changes.accommodation_id is not None:
                diff["accommodation_id"] = str(request.changes.accommodation_id)
                employee.accommodation_id = request.changes.accommodation_id
            if request.changes.break_override_minutes is not None:
                diff["break_override_minutes"] = request.changes.break_override_minutes
                employee.break_override_minutes = request.changes.break_override_minutes
            if request.changes.weekly_off_day is not None:
                diff["weekly_off_day"] = request.changes.weekly_off_day
                employee.weekly_off_day = request.changes.weekly_off_day

            if diff:
                employee.version += 1
                await session.flush()
                await AuditService.log_action(
                    session=session,
                    action="BULK_UPDATE_EMPLOYEE",
                    entity_type="employee",
                    entity_id=str(employee.id),
                    diff=diff,
                    actor_user_id=actor_user_id,
                    actor_role=actor_role,
                    reason="Bulk update action",
                )
                await event_bus.publish(
                    EmployeeProfileChanged(employee_id=employee.id), session=session
                )
                count += 1
        return count

    @staticmethod
    async def change_grade(
        session: AsyncSession,
        employee_id: UUID,
        request: GradeChangeRequest,
        actor_user_id: UUID,
        actor_role: str,
    ) -> Employee:
        employee = await OrgService.get_employee(session, employee_id)
        old_grade = employee.grade_code

        employee.grade_code = request.new_grade_code
        employee.version += 1
        await session.flush()

        history = EmployeeGradeHistory(
            employee_id=employee.id,
            old_grade_code=old_grade,
            new_grade_code=request.new_grade_code,
            effective_from=request.effective_from,
            changed_by_user_id=actor_user_id,
            reason=request.reason,
        )
        session.add(history)
        await session.flush()

        await AuditService.log_action(
            session=session,
            action="CHANGE_GRADE",
            entity_type="employee",
            entity_id=str(employee.id),
            diff={"old_grade": old_grade, "new_grade": request.new_grade_code},
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            reason=request.reason,
        )
        return employee

    # --- Reporting Lines ---
    @staticmethod
    async def list_reporting_lines(
        session: AsyncSession,
        employee_id: UUID,
    ) -> list[ReportingLineRead]:
        """List all active direct and upstream reporting lines for an employee (full management chain)."""
        all_lines_query = select(EmployeeReportingLine).where(
            EmployeeReportingLine.is_active == True  # noqa: E712
        )
        all_lines = (await session.execute(all_lines_query)).scalars().all()

        emp_query = select(Employee)
        emp_map = {e.id: e for e in (await session.execute(emp_query)).scalars().all()}

        upwards: dict[UUID, list[EmployeeReportingLine]] = {}
        for line_item in all_lines:
            upwards.setdefault(line_item.employee_id, []).append(line_item)

        visited: set[UUID] = set()
        result_lines: list[ReportingLineRead] = []

        def traverse(curr_emp_id: UUID, is_direct: bool, via_name: str | None = None) -> None:
            for line in upwards.get(curr_emp_id, []):
                if line.manager_id in visited or line.manager_id == employee_id:
                    continue
                visited.add(line.manager_id)
                mgr = emp_map.get(line.manager_id)
                result_lines.append(
                    ReportingLineRead(
                        id=line.id,
                        employee_id=employee_id,
                        manager_id=line.manager_id,
                        manager_name=mgr.name if mgr else None,
                        manager_tally_id=mgr.tally_id if mgr else None,
                        relationship=line.relationship,
                        notes=line.notes,
                        created_at=line.created_at,
                        is_active=line.is_active,
                        is_direct=is_direct,
                        via_name=via_name,
                    )
                )
                if mgr:
                    traverse(mgr.id, False, mgr.name)

        traverse(employee_id, is_direct=True, via_name=None)
        return result_lines

    @staticmethod
    async def add_reporting_line(
        session: AsyncSession,
        employee_id: UUID,
        data: ReportingLineCreate,
        actor_user_id: UUID,
        actor_role: str,
    ) -> ReportingLineRead:
        emp = await session.get(Employee, employee_id)
        if not emp:
            raise AppError(
                code="EMPLOYEE_NOT_FOUND", message="Employee not found.", status_code=404
            )
        mgr = await session.get(Employee, data.manager_id)
        if not mgr:
            raise AppError(code="MANAGER_NOT_FOUND", message="Manager not found.", status_code=404)

        if (
            emp.role == "ADMIN"
            or emp.tally_id == "ADMIN001"
            or mgr.role == "ADMIN"
            or mgr.tally_id == "ADMIN001"
        ):
            raise AppError(
                code="ADMIN_NOT_IN_HIERARCHY",
                message="Admin accounts are system superusers and cannot participate in the employee hierarchy.",
                status_code=400,
            )

        # Load active reporting lines for cycle and constraint validation
        query = select(
            EmployeeReportingLine.employee_id,
            EmployeeReportingLine.manager_id,
            EmployeeReportingLine.relationship,
        ).where(EmployeeReportingLine.is_active == True)  # noqa: E712
        result = await session.execute(query)
        existing_links = [
            (str(r.employee_id), str(r.manager_id), r.relationship) for r in result.all()
        ]

        if (str(employee_id), str(data.manager_id), data.relationship) in existing_links:
            raise AppError(
                code="DUPLICATE_REPORTING_LINE",
                message="This reporting line already exists.",
                status_code=409,
            )

        try:
            validate_reporting_link(
                existing_links=existing_links,
                employee_id=str(employee_id),
                manager_id=str(data.manager_id),
                relationship=data.relationship,
                employee_role=emp.role,
                manager_role=mgr.role,
            )
        except HierarchyRuleViolation as e:
            raise AppError(code=e.code, message=e.message, status_code=422) from e

        # Check if an inactive line exists that can be reactivated
        inactive_query = select(EmployeeReportingLine).where(
            EmployeeReportingLine.employee_id == employee_id,
            EmployeeReportingLine.manager_id == data.manager_id,
            EmployeeReportingLine.relationship == data.relationship,
            EmployeeReportingLine.is_active == False,  # noqa: E712
        )
        existing_inactive = (await session.execute(inactive_query)).scalar_one_or_none()

        if existing_inactive:
            link = existing_inactive
            link.is_active = True
            link.deactivated_at = None
            link.deactivated_by = None
            link.notes = data.notes
        else:
            link = EmployeeReportingLine(
                employee_id=employee_id,
                manager_id=data.manager_id,
                relationship=data.relationship,
                notes=data.notes,
                is_active=True,
            )
            session.add(link)

        await session.flush()

        await AuditService.log_action(
            session=session,
            action="ADD_REPORTING_LINE",
            entity_type="employee_reporting_line",
            entity_id=str(link.id),
            diff={
                "employee_id": str(employee_id),
                "manager_id": str(data.manager_id),
                "relationship": data.relationship,
            },
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

        await event_bus.publish(EmployeeProfileChanged(employee_id=employee_id), session=session)

        mgr = await session.get(Employee, data.manager_id)
        return ReportingLineRead(
            id=link.id,
            employee_id=link.employee_id,
            manager_id=link.manager_id,
            manager_name=mgr.name if mgr else None,
            manager_tally_id=mgr.tally_id if mgr else None,
            relationship=link.relationship,
            notes=link.notes,
            created_at=link.created_at,
            is_active=link.is_active,
        )

    @staticmethod
    async def remove_reporting_line(
        session: AsyncSession,
        reporting_line_id: UUID,
        actor_user_id: UUID,
        actor_role: str,
    ) -> None:
        query = select(EmployeeReportingLine).where(
            EmployeeReportingLine.id == reporting_line_id,
            EmployeeReportingLine.is_active == True,  # noqa: E712
        )
        result = await session.execute(query)
        link = result.scalar_one_or_none()
        if not link:
            raise AppError(code="NOT_FOUND", message="Reporting line not found.", status_code=404)

        emp_id = link.employee_id
        link.is_active = False
        link.deactivated_at = datetime.now(UTC)
        link.deactivated_by = actor_user_id
        await session.flush()

        await AuditService.log_action(
            session=session,
            action="DEACTIVATE_REPORTING_LINE",
            entity_type="employee_reporting_line",
            entity_id=str(reporting_line_id),
            diff={
                "is_active": {"old": "True", "new": "False"},
                "employee_id": str(link.employee_id),
                "manager_id": str(link.manager_id),
                "relationship": link.relationship,
            },
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

        await event_bus.publish(EmployeeProfileChanged(employee_id=emp_id), session=session)

    # --- Hierarchy Tree ---
    @staticmethod
    async def get_hierarchy_tree(
        session: AsyncSession,
        scoped_ids: set[UUID] | None = None,
    ) -> list[HierarchyTreeNode]:
        """Build hierarchical employee tree."""
        query = select(Employee).where(Employee.is_active == True)  # noqa: E712
        if scoped_ids is not None:
            query = query.where(Employee.id.in_(scoped_ids))
        employees = {emp.id: emp for emp in (await session.execute(query)).scalars().all()}

        # Load active reporting lines
        lines_query = select(EmployeeReportingLine).where(
            EmployeeReportingLine.is_active == True  # noqa: E712
        )
        all_lines = (await session.execute(lines_query)).scalars().all()

        # Build child map
        manager_to_reports: dict[UUID, list[tuple[UUID, str]]] = defaultdict(list)
        has_manager: set[UUID] = set()

        for line in all_lines:
            if line.employee_id in employees and line.manager_id in employees:
                manager_to_reports[line.manager_id].append((line.employee_id, line.relationship))
                has_manager.add(line.employee_id)

        # Roots are employees in scope who don't report to anyone else in scope
        roots = [emp for emp_id, emp in employees.items() if emp_id not in has_manager]

        def build_node(emp: Employee, rel: str | None = None) -> HierarchyTreeNode:
            subordinates = [
                build_node(employees[sub_id], sub_rel)
                for sub_id, sub_rel in manager_to_reports.get(emp.id, [])
            ]
            return HierarchyTreeNode(
                employee=emp,  # type: ignore[arg-type]
                relationship=rel,
                subordinates=subordinates,
            )

        return [build_node(r) for r in roots]

    # --- Hierarchy Violations Audit (Batch 4) ---
    @staticmethod
    async def get_hierarchy_violations(
        session: AsyncSession,
    ) -> list[HierarchyViolationItem]:
        """Audit active reporting lines and return all that violate the fixed crew structure."""
        lines_query = select(EmployeeReportingLine).where(
            EmployeeReportingLine.is_active == True  # noqa: E712
        )
        lines = (await session.execute(lines_query)).scalars().all()

        emp_query = select(Employee)
        employees = {e.id: e for e in (await session.execute(emp_query)).scalars().all()}

        # Map supervisor per worker and leaders per supervisor
        worker_supervisor: dict[UUID, Employee] = {}
        supervisor_leaders: dict[UUID, set[tuple[UUID, str]]] = defaultdict(set)

        for line in lines:
            if line.relationship == "SUPERVISOR":
                emp = employees.get(line.employee_id)
                mgr = employees.get(line.manager_id)
                if emp and mgr:
                    worker_supervisor[emp.id] = mgr
            elif line.relationship in ("SUPERINTENDENT", "ENGINEER"):
                supervisor_leaders[line.employee_id].add((line.manager_id, line.relationship))

        violations: list[HierarchyViolationItem] = []

        for line in lines:
            emp = employees.get(line.employee_id)
            mgr = employees.get(line.manager_id)
            if not emp or not mgr:
                continue

            violation_code: str | None = None
            violation_msg: str | None = None

            if emp.role == "WORKER" and line.relationship in ("SUPERINTENDENT", "ENGINEER"):
                violation_code = "WORKER_DIRECT_LINK_NOT_ALLOWED"
                violation_msg = (
                    f"Worker {emp.tally_id} ({emp.name}) has direct {line.relationship} link to "
                    f"{mgr.tally_id} ({mgr.name}). Workers inherit leadership through their supervisor."
                )
            elif line.relationship == "SUPERVISOR" and emp.role != "WORKER":
                violation_code = "INVALID_LINK_SUBJECT"
                violation_msg = (
                    f"Supervisor reporting line has subordinate {emp.tally_id} ({emp.name}) with role {emp.role}. "
                    f"Only workers have a supervisor."
                )
            elif line.relationship == "SUPERVISOR" and mgr.role != "SUPERVISOR":
                violation_code = "SUPERVISOR_LINK_ROLE_MISMATCH"
                violation_msg = (
                    f"Supervisor reporting line for {emp.tally_id} ({emp.name}) has manager "
                    f"{mgr.tally_id} ({mgr.name}) with role {mgr.role} instead of SUPERVISOR."
                )
            elif line.relationship in ("SUPERINTENDENT", "ENGINEER") and emp.role != "SUPERVISOR":
                violation_code = "INVALID_LINK_SUBJECT"
                violation_msg = (
                    f"{line.relationship} link has subordinate {emp.tally_id} ({emp.name}) "
                    f"with role {emp.role}. These links must attach only to supervisors."
                )
            elif line.relationship == "SUPERINTENDENT" and mgr.role != "SUPERINTENDENT":
                violation_code = "HIERARCHY_ROLE_MISMATCH"
                violation_msg = (
                    f"Superintendent link has manager {mgr.tally_id} ({mgr.name}) with role {mgr.role}."
                )
            elif line.relationship == "ENGINEER" and mgr.role != "ENGINEER":
                violation_code = "HIERARCHY_ROLE_MISMATCH"
                violation_msg = (
                    f"Engineer link has manager {mgr.tally_id} ({mgr.name}) with role {mgr.role}."
                )

            if violation_code and violation_msg:
                sup_emp = worker_supervisor.get(emp.id)
                sup_already_has = False
                can_move = False
                if sup_emp and line.relationship in ("SUPERINTENDENT", "ENGINEER"):
                    sup_leaders = supervisor_leaders.get(sup_emp.id, set())
                    sup_already_has = (mgr.id, line.relationship) in sup_leaders
                    can_move = emp.role == "WORKER" and not sup_already_has

                violations.append(
                    HierarchyViolationItem(
                        reporting_line_id=line.id,
                        employee_id=emp.id,
                        employee_tally_id=emp.tally_id,
                        employee_name=emp.name,
                        employee_role=emp.role,
                        manager_id=mgr.id,
                        manager_tally_id=mgr.tally_id,
                        manager_name=mgr.name,
                        manager_role=mgr.role,
                        relationship=line.relationship,
                        violation_code=violation_code,
                        violation_message=violation_msg,
                        supervisor_id=sup_emp.id if sup_emp else None,
                        supervisor_tally_id=sup_emp.tally_id if sup_emp else None,
                        supervisor_name=sup_emp.name if sup_emp else None,
                        supervisor_already_has_manager=sup_already_has,
                        can_move_to_supervisor=can_move,
                    )
                )

        return violations

    @staticmethod
    async def move_reporting_line_to_supervisor(
        session: AsyncSession,
        reporting_line_id: UUID,
        actor_user_id: UUID,
        actor_role: str,
    ) -> None:
        """Move a direct worker->supt/eng link to the worker's supervisor, then deactivate the direct link."""
        line = await session.get(EmployeeReportingLine, reporting_line_id)
        if not line or not line.is_active:
            raise AppError(code="NOT_FOUND", message="Active reporting line not found.", status_code=404)

        emp = await session.get(Employee, line.employee_id)
        mgr = await session.get(Employee, line.manager_id)
        if not emp or not mgr:
            raise AppError(code="NOT_FOUND", message="Employee or manager not found.", status_code=404)

        if emp.role != "WORKER" or line.relationship not in ("SUPERINTENDENT", "ENGINEER"):
            raise AppError(
                code="INVALID_MOVE_REQUEST",
                message="Only direct superintendent or engineer links on workers can be moved to a supervisor.",
                status_code=400,
            )

        # Find worker's supervisor
        sup_stmt = select(EmployeeReportingLine).where(
            EmployeeReportingLine.employee_id == emp.id,
            EmployeeReportingLine.relationship == "SUPERVISOR",
            EmployeeReportingLine.is_active == True,  # noqa: E712
        )
        sup_link = (await session.execute(sup_stmt)).scalar_one_or_none()
        if not sup_link:
            raise AppError(
                code="WORKER_HAS_NO_SUPERVISOR",
                message=f"Worker {emp.tally_id} has no active supervisor to move this link to.",
                status_code=400,
            )

        supervisor_id = sup_link.manager_id

        # Check if supervisor already has this link (active or inactive)
        check_stmt = select(EmployeeReportingLine).where(
            EmployeeReportingLine.employee_id == supervisor_id,
            EmployeeReportingLine.manager_id == mgr.id,
            EmployeeReportingLine.relationship == line.relationship,
        )
        existing_sup_link = (await session.execute(check_stmt)).scalar_one_or_none()

        if existing_sup_link:
            if not existing_sup_link.is_active:
                existing_sup_link.is_active = True
                existing_sup_link.deactivated_at = None
                existing_sup_link.deactivated_by = None
        else:
            new_sup_link = EmployeeReportingLine(
                employee_id=supervisor_id,
                manager_id=mgr.id,
                relationship=line.relationship,
                notes=f"Moved from worker {emp.tally_id} ({emp.name})",
                is_active=True,
            )
            session.add(new_sup_link)

        # Deactivate worker's direct link
        line.is_active = False
        line.deactivated_at = datetime.now(UTC)
        line.deactivated_by = actor_user_id
        await session.flush()

        await AuditService.log_action(
            session=session,
            action="MOVE_REPORTING_LINE_TO_SUPERVISOR",
            entity_type="employee_reporting_line",
            entity_id=str(reporting_line_id),
            diff={
                "worker_id": str(emp.id),
                "supervisor_id": str(supervisor_id),
                "manager_id": str(mgr.id),
                "relationship": line.relationship,
            },
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            reason=f"Moved {line.relationship} link from worker {emp.tally_id} to supervisor",
        )

        await event_bus.publish(EmployeeProfileChanged(employee_id=emp.id), session=session)
        await event_bus.publish(EmployeeProfileChanged(employee_id=supervisor_id), session=session)

    @staticmethod
    def export_hierarchy_violations_excel(violations: list[HierarchyViolationItem]) -> bytes:
        import io
        import openpyxl
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws.title = "Hierarchy Violations"

        headers = [
            "Employee Tally ID",
            "Employee Name",
            "Employee Role",
            "Manager Tally ID",
            "Manager Name",
            "Manager Role",
            "Relationship",
            "Violation Code",
            "Violation Message",
            "Worker's Supervisor",
            "Supervisor Already Has Manager",
            "Can Move To Supervisor",
        ]
        ws.append(headers)

        header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for v in violations:
            sup_display = f"{v.supervisor_tally_id} ({v.supervisor_name})" if v.supervisor_tally_id else "None"
            ws.append([
                v.employee_tally_id,
                v.employee_name,
                v.employee_role,
                v.manager_tally_id,
                v.manager_name,
                v.manager_role,
                v.relationship,
                v.violation_code,
                v.violation_message,
                sup_display,
                "Yes" if v.supervisor_already_has_manager else "No",
                "Yes" if v.can_move_to_supervisor else "No",
            ])

        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(int(col[0].column or 1))
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()

    # --- Groups, Zones, Accommodations CRUD ---
    @staticmethod
    async def list_groups(session: AsyncSession) -> list[Group]:
        result = await session.execute(select(Group).order_by(Group.name.asc()))
        return list(result.scalars().all())

    @staticmethod
    async def create_group(
        session: AsyncSession, data: GroupCreate, actor_user_id: UUID, actor_role: str
    ) -> Group:
        group = Group(code=data.code, name=data.name)
        session.add(group)
        await session.flush()
        await AuditService.log_action(
            session=session,
            action="CREATE_GROUP",
            entity_type="group",
            entity_id=str(group.id),
            diff={"code": group.code, "name": group.name},
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
        return group

    @staticmethod
    async def update_group(
        session: AsyncSession,
        group_id: UUID,
        data: GroupUpdate,
        actor_user_id: UUID,
        actor_role: str,
    ) -> Group:
        res = await session.execute(select(Group).where(Group.id == group_id))
        group = res.scalar_one_or_none()
        if not group:
            raise AppError(code="NOT_FOUND", message="Group not found.", status_code=404)
        if group.version != data.version:
            raise AppError(code="VERSION_CONFLICT", message="Conflict.", status_code=409)

        diff: dict[str, Any] = {}
        if data.name is not None and data.name != group.name:
            diff["name"] = data.name
            group.name = data.name
        if data.is_active is not None and data.is_active != group.is_active:
            diff["is_active"] = data.is_active
            group.is_active = data.is_active
        group.version += 1
        await session.flush()

        await AuditService.log_action(
            session=session,
            action="UPDATE_GROUP",
            entity_type="group",
            entity_id=str(group.id),
            diff=diff,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
        return group

    @staticmethod
    async def list_zones(session: AsyncSession) -> list[Zone]:
        result = await session.execute(select(Zone).order_by(Zone.name.asc()))
        return list(result.scalars().all())

    @staticmethod
    async def create_zone(
        session: AsyncSession, data: ZoneCreate, actor_user_id: UUID, actor_role: str
    ) -> Zone:
        zone = Zone(code=data.code, name=data.name)
        session.add(zone)
        await session.flush()
        await AuditService.log_action(
            session=session,
            action="CREATE_ZONE",
            entity_type="zone",
            entity_id=str(zone.id),
            diff={"code": zone.code, "name": zone.name},
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
        return zone

    @staticmethod
    async def update_zone(
        session: AsyncSession,
        zone_id: UUID,
        data: ZoneUpdate,
        actor_user_id: UUID,
        actor_role: str,
    ) -> Zone:
        res = await session.execute(select(Zone).where(Zone.id == zone_id))
        zone = res.scalar_one_or_none()
        if not zone:
            raise AppError(code="NOT_FOUND", message="Zone not found.", status_code=404)
        if zone.version != data.version:
            raise AppError(code="VERSION_CONFLICT", message="Conflict.", status_code=409)

        diff: dict[str, Any] = {}
        if data.name is not None and data.name != zone.name:
            diff["name"] = data.name
            zone.name = data.name
        if data.is_active is not None and data.is_active != zone.is_active:
            diff["is_active"] = data.is_active
            zone.is_active = data.is_active
        zone.version += 1
        await session.flush()

        await AuditService.log_action(
            session=session,
            action="UPDATE_ZONE",
            entity_type="zone",
            entity_id=str(zone.id),
            diff=diff,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
        return zone

    @staticmethod
    async def list_accommodations(
        session: AsyncSession,
        is_active: bool | None = True,
    ) -> list[tuple[Accommodation, str | None]]:
        stmt = select(
            Accommodation,
            func.ST_AsGeoJSON(Accommodation.boundary).label("geojson_str"),
        )
        if is_active is not None:
            stmt = stmt.where(Accommodation.is_active.is_(is_active))
        result = await session.execute(stmt.order_by(Accommodation.name.asc()))
        return list(result.all())

    @staticmethod
    async def create_accommodation(
        session: AsyncSession,
        data: AccommodationCreate,
        actor_user_id: UUID,
        actor_role: str,
    ) -> Accommodation:
        acc = Accommodation(
            accommodation_code=data.accommodation_code,
            name=data.name,
            address=data.address,
            rep_latitude=data.rep_latitude,
            rep_longitude=data.rep_longitude,
        )
        session.add(acc)
        await session.flush()
        await AuditService.log_action(
            session=session,
            action="CREATE_ACCOMMODATION",
            entity_type="accommodation",
            entity_id=str(acc.id),
            diff={"code": acc.accommodation_code, "name": acc.name},
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
        return acc

    @staticmethod
    async def update_accommodation(
        session: AsyncSession,
        acc_id: UUID,
        data: AccommodationUpdate,
        actor_user_id: UUID,
        actor_role: str,
    ) -> Accommodation:
        res = await session.execute(select(Accommodation).where(Accommodation.id == acc_id))
        acc = res.scalar_one_or_none()
        if not acc:
            raise AppError(code="NOT_FOUND", message="Accommodation not found.", status_code=404)
        if acc.version != data.version:
            raise AppError(code="VERSION_CONFLICT", message="Conflict.", status_code=409)

        diff: dict[str, Any] = {}
        for field, value in data.model_dump(exclude_unset=True, exclude={"version"}).items():
            diff[field] = value
            setattr(acc, field, value)
        acc.version += 1
        await session.flush()

        await AuditService.log_action(
            session=session,
            action="UPDATE_ACCOMMODATION",
            entity_type="accommodation",
            entity_id=str(acc.id),
            diff=diff,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
        return acc

    # --- Documents ---
    @staticmethod
    async def list_documents(
        session: AsyncSession,
        employee_id: UUID,
    ) -> list[EmployeeDocument]:
        query = select(EmployeeDocument).where(EmployeeDocument.employee_id == employee_id)
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def add_or_update_document(
        session: AsyncSession,
        employee_id: UUID,
        data: EmployeeDocumentCreate,
        actor_user_id: UUID,
        actor_role: str,
    ) -> EmployeeDocument:
        query = select(EmployeeDocument).where(
            EmployeeDocument.employee_id == employee_id,
            EmployeeDocument.document_type == data.document_type,
        )
        res = await session.execute(query)
        doc = res.scalar_one_or_none()
        if doc:
            doc.expiry_date = data.expiry_date
            if data.start_date:
                doc.start_date = data.start_date
            action = "UPDATE_DOCUMENT"
        else:
            doc = EmployeeDocument(
                employee_id=employee_id,
                document_type=data.document_type,
                expiry_date=data.expiry_date,
                start_date=data.start_date,
            )
            session.add(doc)
            action = "ADD_DOCUMENT"
        await session.flush()

        await AuditService.log_action(
            session=session,
            action=action,
            entity_type="employee_document",
            entity_id=str(doc.id),
            diff={"document_type": data.document_type, "expiry_date": str(data.expiry_date)},
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
        return doc

    # --- Devices ---
    @staticmethod
    async def list_devices(
        session: AsyncSession,
        employee_id: UUID,
    ) -> list[RegisteredDevice]:
        query = select(RegisteredDevice).where(RegisteredDevice.employee_id == employee_id)
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def revoke_device(
        session: AsyncSession,
        device_id: UUID,
        actor_user_id: UUID,
        actor_role: str,
    ) -> RegisteredDevice:
        res = await session.execute(
            select(RegisteredDevice).where(RegisteredDevice.id == device_id)
        )
        device = res.scalar_one_or_none()
        if not device:
            raise AppError(code="NOT_FOUND", message="Device not found.", status_code=404)

        device.is_active = False
        device.revoked_by_user_id = actor_user_id
        await session.flush()

        await AuditService.log_action(
            session=session,
            action="REVOKE_DEVICE",
            entity_type="registered_device",
            entity_id=str(device.id),
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            reason="Admin revoked device binding",
        )
        return device

    @staticmethod
    async def get_expiring_documents(
        session: AsyncSession,
        user: User,
        within_days: int | None = None,
        document_type: str | None = None,
        supervisor_id: UUID | None = None,
    ) -> ExpiringDocumentsResponse:
        """Fetch expiring and expired documents for Admin/scope."""
        today = datetime.now(UTC).date()

        # Resolve lead days setting if within_days not passed
        if within_days is None:
            lead_days_setting = await SettingsService.get_setting(
                session=session,
                key="document_expiry_lead_days",
                default=30,
            )
            try:
                within_days = int(lead_days_setting) if lead_days_setting else 30
            except (ValueError, TypeError):
                within_days = 30

        query = (
            select(
                EmployeeDocument,
                Employee.name,
                Employee.tally_id,
            )
            .join(Employee, EmployeeDocument.employee_id == Employee.id)
            .where(EmployeeDocument.is_active.is_(True), Employee.is_active.is_(True))
            .order_by(EmployeeDocument.expiry_date.asc())
        )

        # Scoping
        if user.role != "ADMIN":
            scoped_ids = await ScopeService.get_scoped_employee_ids(session, user)
            if scoped_ids:
                query = query.where(EmployeeDocument.employee_id.in_(scoped_ids))
            elif user.employee_id:
                query = query.where(EmployeeDocument.employee_id == user.employee_id)
            else:
                query = query.where(EmployeeDocument.employee_id.in_([]))

        if document_type:
            query = query.where(EmployeeDocument.document_type == document_type.upper())

        rows = (await session.execute(query)).all()

        # Build supervisor lookup
        emp_ids = [r[0].employee_id for r in rows]
        sup_lookup: dict[UUID, tuple[UUID, str]] = {}
        if emp_ids:
            sup_stmt = (
                select(
                    EmployeeReportingLine.employee_id,
                    EmployeeReportingLine.manager_id,
                    Employee.name,
                )
                .join(Employee, EmployeeReportingLine.manager_id == Employee.id)
                .where(
                    EmployeeReportingLine.employee_id.in_(emp_ids),
                    EmployeeReportingLine.relationship == "SUPERVISOR",
                    EmployeeReportingLine.is_active == True,  # noqa: E712
                )
            )
            sup_rows = (await session.execute(sup_stmt)).all()
            for s_emp_id, m_id, m_name in sup_rows:
                sup_lookup[s_emp_id] = (m_id, m_name)

        items: list[ExpiringDocumentItem] = []
        expiring_count = 0
        expired_count = 0
        ok_count = 0

        for doc, emp_name, tally in rows:
            sup_info = sup_lookup.get(doc.employee_id)
            sup_id = sup_info[0] if sup_info else None
            sup_name = sup_info[1] if sup_info else None

            if supervisor_id and sup_id != supervisor_id:
                continue

            days_remaining = (doc.expiry_date - today).days
            if days_remaining < 0:
                status = "EXPIRED"
                expired_count += 1
            elif days_remaining <= within_days:
                status = "EXPIRING"
                expiring_count += 1
            else:
                status = "OK"
                ok_count += 1

            items.append(
                ExpiringDocumentItem(
                    document_id=doc.id,
                    employee_id=doc.employee_id,
                    employee_name=emp_name,
                    tally_id=tally,
                    supervisor_id=sup_id,
                    supervisor_name=sup_name,
                    document_type=doc.document_type,
                    expiry_date=doc.expiry_date,
                    days_remaining=days_remaining,
                    status=status,
                    is_active=doc.is_active,
                )
            )

        return ExpiringDocumentsResponse(
            items=items,
            expiring_count=expiring_count,
            expired_count=expired_count,
            ok_count=ok_count,
            total_count=len(items),
        )

    @staticmethod
    async def get_unique_staff_grades(session: AsyncSession) -> list[str]:
        """Fetch all unique staff grade descriptions from active employees in the system."""
        stmt = (
            select(Employee.staff_grade_description)
            .where(
                Employee.staff_grade_description.is_not(None),
                Employee.staff_grade_description != "",
            )
            .distinct()
        )
        emp_grades = set((await session.execute(stmt)).scalars().all())
        return sorted([g.strip() for g in emp_grades if g and g.strip()])
