from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.errors import AppError
from fw.core.events import EmployeeProfileChanged, event_bus
from fw.modules.audit import AuditService
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
    GradeChangeRequest,
    GroupCreate,
    GroupUpdate,
    HierarchyTreeNode,
    ReportingLineCreate,
    ReportingLineRead,
    ZoneCreate,
    ZoneUpdate,
)
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

        if user.role == "WORKER":
            return {user.employee_id}

        # For ENGINEER, SUPERINTENDENT, SUPERVISOR:
        # Load all reporting lines to compute transitive descendant scope
        query = select(EmployeeReportingLine.employee_id, EmployeeReportingLine.manager_id)
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
                EmployeeReportingLine.manager_id == manager_id
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
    async def create_employee(
        session: AsyncSession,
        data: EmployeeCreate,
        default_password: str,
        actor_user_id: UUID,
        actor_role: str,
    ) -> Employee:
        # Check uniqueness of tally_id
        existing = await session.execute(select(Employee).where(Employee.tally_id == data.tally_id))
        if existing.scalar_one_or_none():
            raise AppError(
                code="DUPLICATE_TALLY_ID",
                message=f"Employee with ID '{data.tally_id}' already exists.",
                status_code=409,
            )

        employee = Employee(
            tally_id=data.tally_id,
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

        diff: dict[str, Any] = {}
        # Apply fields
        for field, value in data.model_dump(exclude_unset=True, exclude={"version"}).items():
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
        """List all direct and upstream reporting lines for an employee (full management chain)."""
        all_lines_query = select(EmployeeReportingLine)
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
        # Load all existing reporting lines for cycle and constraint validation
        query = select(
            EmployeeReportingLine.employee_id,
            EmployeeReportingLine.manager_id,
            EmployeeReportingLine.relationship,
        )
        result = await session.execute(query)
        existing_links = [
            (str(r.employee_id), str(r.manager_id), r.relationship) for r in result.all()
        ]

        try:
            validate_reporting_link(
                existing_links=existing_links,
                employee_id=str(employee_id),
                manager_id=str(data.manager_id),
                relationship=data.relationship,
            )
        except HierarchyRuleViolation as e:
            raise AppError(code=e.code, message=e.message, status_code=422) from e

        link = EmployeeReportingLine(
            employee_id=employee_id,
            manager_id=data.manager_id,
            relationship=data.relationship,
            notes=data.notes,
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
        )

    @staticmethod
    async def remove_reporting_line(
        session: AsyncSession,
        reporting_line_id: UUID,
        actor_user_id: UUID,
        actor_role: str,
    ) -> None:
        query = select(EmployeeReportingLine).where(EmployeeReportingLine.id == reporting_line_id)
        result = await session.execute(query)
        link = result.scalar_one_or_none()
        if not link:
            raise AppError(code="NOT_FOUND", message="Reporting line not found.", status_code=404)

        emp_id = link.employee_id
        await session.delete(link)
        await session.flush()

        await AuditService.log_action(
            session=session,
            action="REMOVE_REPORTING_LINE",
            entity_type="employee_reporting_line",
            entity_id=str(reporting_line_id),
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

        # Load reporting lines
        lines_query = select(EmployeeReportingLine)
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
    async def list_accommodations(session: AsyncSession) -> list[tuple[Accommodation, str | None]]:
        result = await session.execute(
            select(
                Accommodation,
                func.ST_AsGeoJSON(Accommodation.boundary).label("geojson_str"),
            ).order_by(Accommodation.name.asc())
        )
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
