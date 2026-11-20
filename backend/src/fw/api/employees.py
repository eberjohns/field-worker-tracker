import io
from datetime import UTC, date, datetime
from uuid import UUID

import xlsxwriter
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.clock import site_today
from fw.core.db import get_db
from fw.core.errors import AppError
from fw.core.events import EmployeeProfileChanged, event_bus
from fw.modules.archive.dsar import generate_employee_dsar_excel
from fw.modules.audit import AuditService
from fw.modules.identity import (
    User,
    UserService,
    UserSession,
    get_current_user,
    hash_password,
    require_role,
    verify_password,
)
from fw.modules.org import (
    DeactivateRequest,
    Employee,
    EmployeeAttributeHistoryRead,
    EmployeeBulkUpdateRequest,
    EmployeeCreate,
    EmployeeDeactivationImpactResponse,
    EmployeeDocumentCreate,
    EmployeeDocumentRead,
    EmployeeProfileDetailsUpdate,
    EmployeeRead,
    EmployeeUpdate,
    EntityLifecycleResponse,
    GradeChangeRequest,
    HierarchyTreeNode,
    HierarchyViolationItem,
    OrgService,
    ReactivateRequest,
    RegisteredDeviceRead,
    ReportingLineCreate,
    ReportingLineRead,
    ScopeService,
    TallyIdChangeRequest,
    TallyIdCheckResponse,
)
from fw.modules.payroll import PayrollSalaryService
from fw.modules.scheduling import SchedulingService
from fw.modules.settings import SettingsService
from fw.modules.sync import MobileConsentWithdrawRequest, SyncService

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("", response_model=list[EmployeeRead])
async def list_employees(
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
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[EmployeeRead]:
    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
    if current_user.role == "SUPERVISOR" and current_user.employee_id:
        from fw.modules.jobs import JobItem, WorksiteSupervisor
        from fw.modules.scheduling.models import ScheduledWork, StandingAssignment

        ws_stmt = select(WorksiteSupervisor.worksite_id).where(
            WorksiteSupervisor.supervisor_id == current_user.employee_id,
            WorksiteSupervisor.is_active == True,  # noqa: E712
        )
        ws_ids = list((await session.execute(ws_stmt)).scalars().all())
        if ws_ids:
            extra_ids: set[UUID] = set()
            sa_stmt = (
                select(StandingAssignment.employee_id)
                .join(JobItem, StandingAssignment.job_item_id == JobItem.id)
                .where(JobItem.worksite_id.in_(ws_ids), StandingAssignment.is_active == True)  # noqa: E712
            )
            extra_ids.update((await session.execute(sa_stmt)).scalars().all())
            sw_stmt = select(ScheduledWork.employee_id).where(ScheduledWork.worksite_id.in_(ws_ids))
            extra_ids.update((await session.execute(sw_stmt)).scalars().all())
            if scoped_ids is not None:
                scoped_ids = scoped_ids | extra_ids

    effective_is_active = is_active if current_user.role == "ADMIN" else True
    employees = await OrgService.list_employees(
        session=session,
        scoped_ids=scoped_ids,
        role=role,
        sgd=sgd,
        grade_code=grade_code,
        manager_id=manager_id,
        accommodation_id=accommodation_id,
        has_accommodation=has_accommodation,
        country=country,
        is_active=effective_is_active,
        q=q,
        limit=limit,
        offset=offset,
    )
    return [EmployeeRead.model_validate(e) for e in employees]


@router.get("/export")
async def export_employees_directory(
    role: str | None = None,
    country: str | None = None,
    is_active: bool | None = None,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
):
    """Export filtered employee directory as an Excel spreadsheet."""
    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
    if current_user.role == "SUPERVISOR" and current_user.employee_id:
        from fw.modules.jobs import JobItem, WorksiteSupervisor
        from fw.modules.scheduling.models import ScheduledWork, StandingAssignment

        ws_stmt = select(WorksiteSupervisor.worksite_id).where(
            WorksiteSupervisor.supervisor_id == current_user.employee_id,
            WorksiteSupervisor.is_active == True,  # noqa: E712
        )
        ws_ids = list((await session.execute(ws_stmt)).scalars().all())
        if ws_ids:
            extra_ids: set[UUID] = set()
            sa_stmt = (
                select(StandingAssignment.employee_id)
                .join(JobItem, StandingAssignment.job_item_id == JobItem.id)
                .where(JobItem.worksite_id.in_(ws_ids), StandingAssignment.is_active == True)  # noqa: E712
            )
            extra_ids.update((await session.execute(sa_stmt)).scalars().all())
            sw_stmt = select(ScheduledWork.employee_id).where(ScheduledWork.worksite_id.in_(ws_ids))
            extra_ids.update((await session.execute(sw_stmt)).scalars().all())
            if scoped_ids is not None:
                scoped_ids = scoped_ids | extra_ids

    effective_is_active = is_active if current_user.role == "ADMIN" else True
    employees = await OrgService.list_employees(
        session=session,
        scoped_ids=scoped_ids,
        role=role,
        country=country,
        is_active=effective_is_active,
        limit=5000,
        offset=0,
    )

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    sheet = workbook.add_worksheet("Employees")
    hdr = workbook.add_format(
        {"bold": True, "bg_color": "#1E293B", "font_color": "#FFFFFF", "border": 1}
    )
    cell = workbook.add_format({"border": 1})
    headers = [
        "Tally ID",
        "Name",
        "Role",
        "Country",
        "Staff Grade Description",
        "Weekly Off",
        "Phone",
        "Email",
        "Consent Status",
        "Status",
    ]
    for i, h in enumerate(headers):
        sheet.write(0, i, h, hdr)
        sheet.set_column(i, i, max(len(h) + 4, 15))

    for row_idx, e in enumerate(employees, start=1):
        sheet.write(row_idx, 0, e.tally_id, cell)
        sheet.write(row_idx, 1, e.name, cell)
        sheet.write(row_idx, 2, e.role, cell)
        sheet.write(row_idx, 3, e.country, cell)
        sheet.write(row_idx, 4, e.staff_grade_description or "", cell)
        sheet.write(row_idx, 5, e.weekly_off_day or "Sunday", cell)
        sheet.write(row_idx, 6, e.phone or "", cell)
        sheet.write(row_idx, 7, e.email or "", cell)
        sheet.write(row_idx, 8, e.consent_status, cell)
        sheet.write(row_idx, 9, "ACTIVE" if e.is_active else "INACTIVE", cell)

    workbook.close()
    filename = f"Employees_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        io.BytesIO(output.getvalue()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{employee_id}/export-dsar")
async def export_employee_dsar(
    employee_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Export complete Subject Access Request (DSAR) multi-sheet Excel file for an employee."""
    if current_user.role != "ADMIN" and current_user.employee_id != employee_id:
        scoped = await ScopeService.get_scoped_employee_ids(session, current_user)
        if scoped and employee_id not in scoped:
            raise AppError(
                code="FORBIDDEN",
                message="Cannot export data for employee outside your scope.",
                status_code=403,
            )

    excel_bytes = await generate_employee_dsar_excel(session, employee_id)
    emp = await session.get(Employee, employee_id)
    tally = emp.tally_id if emp else str(employee_id)[:8]
    filename = f"DSAR_{tally}_{datetime.now(UTC).strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{employee_id}/withdraw-consent")
async def admin_withdraw_consent(
    employee_id: UUID,
    request: MobileConsentWithdrawRequest | None = None,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
):
    """Administrator records worker consent withdrawal."""
    reason = (
        request.reason
        if request and request.reason
        else "Withdrawn by Administrator on behalf of worker"
    )
    await SyncService.withdraw_consent(session=session, employee_id=employee_id, reason=reason)
    return {"status": "CONSENT_WITHDRAWN", "employee_id": str(employee_id)}


@router.post("/{employee_id}/reset-password")
async def reset_employee_password(
    employee_id: UUID,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
):
    """Admin resets an employee's user/device password to company default.
    Auto-provisions the user account if not yet created.
    """
    employee = await session.get(Employee, employee_id)
    if not employee:
        raise AppError(code="NOT_FOUND", message="Employee not found.", status_code=404)

    default_pwd = await SyncService.get_default_password(session)

    # Find linked user
    user_q = select(User).where(
        or_(User.employee_id == employee.id, User.username == employee.tally_id)
    )
    user_res = await session.execute(user_q)
    user = user_res.scalars().first()

    if user:
        await UserService.reset_password_to_default(
            session=session,
            user_id=user.id,
            default_password=default_pwd,
        )
    else:
        user = User(
            username=employee.tally_id,
            credential_hash=hash_password(default_pwd),
            role=employee.role or "WORKER",
            employee_id=employee.id,
            must_change_password=True,
            is_active=True,
        )
        session.add(user)
        await session.flush()

    await AuditService.log_action(
        session=session,
        action="RESET_PASSWORD",
        entity_type="employee",
        entity_id=str(employee.id),
        diff={"tally_id": employee.tally_id, "username": user.username, "reset_to_default": True},
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    await session.commit()
    return {
        "status": "PASSWORD_RESET",
        "employee_id": str(employee.id),
        "username": user.username,
        "message": "Password reset to company default successfully.",
    }


@router.post("", response_model=EmployeeRead, status_code=201)
async def create_employee(
    request: EmployeeCreate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> EmployeeRead:
    default_password = await SettingsService.get_setting(
        session,
        key="default_password",
        default="ChangeMe123!",
    )
    employee = await OrgService.create_employee(
        session=session,
        data=request,
        default_password=str(default_password),
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    return EmployeeRead.model_validate(employee)


@router.get("/hierarchy", response_model=list[HierarchyTreeNode])
async def get_hierarchy(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[HierarchyTreeNode]:
    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
    return await OrgService.get_hierarchy_tree(session=session, scoped_ids=scoped_ids)


@router.post("/bulk-update")
async def bulk_update_employees(
    request: EmployeeBulkUpdateRequest,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
    updated_count = await OrgService.bulk_update(
        session=session,
        request=request,
        scoped_ids=scoped_ids,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    if request.changes.break_override_minutes is not None:
        eff_from = request.effective_from or site_today()
        sup_query = select(Employee).where(
            Employee.id.in_(request.employee_ids),
            Employee.role == "SUPERVISOR",
        )
        supervisors = (await session.execute(sup_query)).scalars().all()
        for sup in supervisors:
            await PayrollSalaryService.propagate_crew_break_to_supervisor_crew(
                session=session,
                supervisor_id=sup.id,
                break_minutes=request.changes.break_override_minutes,
                effective_from=eff_from,
                actor_user_id=current_user.id,
                actor_role=current_user.role,
            )
    return {"updated_count": updated_count}


@router.get("/hierarchy-violations", response_model=list[HierarchyViolationItem])
async def get_hierarchy_violations(
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> list[HierarchyViolationItem]:
    """Admin-only audit endpoint listing reporting lines that violate the fixed crew structure."""
    return await OrgService.get_hierarchy_violations(session=session)


@router.get("/hierarchy-violations/export")
async def export_hierarchy_violations(
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Admin-only export of hierarchy violations to Excel (.xlsx)."""
    violations = await OrgService.get_hierarchy_violations(session=session)
    excel_bytes = OrgService.export_hierarchy_violations_excel(violations)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=hierarchy_violations.xlsx"},
    )


@router.post("/hierarchy-violations/{line_id}/deactivate")
async def deactivate_hierarchy_violation_line(
    line_id: UUID,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Deactivate a non-conforming reporting line."""
    await OrgService.remove_reporting_line(
        session=session,
        reporting_line_id=line_id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    return {"message": "Reporting line deactivated successfully."}


@router.post("/hierarchy-violations/{line_id}/move-to-supervisor")
async def move_hierarchy_violation_to_supervisor(
    line_id: UUID,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Move a worker's direct supt/eng link to their supervisor, then deactivate the worker link."""
    await OrgService.move_reporting_line_to_supervisor(
        session=session,
        reporting_line_id=line_id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    return {"message": "Reporting line moved to supervisor and direct link deactivated."}


@router.get("/check-tally-id", response_model=TallyIdCheckResponse)
async def check_tally_id(
    tally_id: str = Query(..., min_length=1),
    exclude_employee_id: UUID | None = Query(None),
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> TallyIdCheckResponse:
    """Check whether a Tally ID is available and whether it was previously held by another employee."""
    return await OrgService.check_tally_id(
        session=session,
        tally_id=tally_id,
        exclude_employee_id=exclude_employee_id,
    )


@router.get("/{employee_id}", response_model=EmployeeRead)
async def get_employee(
    employee_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> EmployeeRead:
    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
    employee = await OrgService.get_employee(session, employee_id, scoped_ids)
    if not employee.is_active and current_user.role != "ADMIN":
        raise AppError(code="NOT_FOUND", message="Employee not found.", status_code=404)
    return EmployeeRead.model_validate(employee)


@router.post("/{employee_id}/change-tally-id", response_model=EmployeeRead)
async def change_employee_tally_id(
    employee_id: UUID,
    request: TallyIdChangeRequest,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> EmployeeRead:
    """Admin updates an employee's Tally ID (e.g. temporary probation ID -> permanent ID) and login username."""
    employee = await OrgService.change_tally_id(
        session=session,
        employee_id=employee_id,
        request=request,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    await session.commit()
    return EmployeeRead.model_validate(employee)


@router.get("/{employee_id}/deactivation-impact", response_model=EmployeeDeactivationImpactResponse)
async def get_employee_deactivation_impact(
    employee_id: UUID,
    effective_date: date | None = Query(None),
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> EmployeeDeactivationImpactResponse:
    """Preview scheduling and reporting-line impact before deactivating an employee (Admin only)."""
    employee = await session.get(Employee, employee_id)
    if not employee:
        raise AppError(code="NOT_FOUND", message="Employee not found.", status_code=404)

    eff = effective_date or site_today()
    sched_impact = await SchedulingService(session).get_employee_deactivation_impact(
        employee_id=employee.id,
        effective_date=eff,
    )
    direct_reports = await OrgService.count_active_direct_reports(session, employee.id)

    return EmployeeDeactivationImpactResponse(
        employee_id=employee.id,
        employee_name=employee.name,
        tally_id=employee.tally_id,
        role=employee.role,
        effective_date=eff,
        future_active_shifts=sched_impact["future_active_shifts"],
        base_roster_slots=sched_impact["base_roster_slots"],
        active_standing_assignments=sched_impact["active_standing_assignments"],
        pending_leave_requests=sched_impact["pending_leave_requests"],
        pending_reassignment_requests=sched_impact["pending_reassignment_requests"],
        active_direct_reports=direct_reports,
    )


@router.post("/{employee_id}/deactivate", response_model=EntityLifecycleResponse)
async def deactivate_employee(
    employee_id: UUID,
    payload: DeactivateRequest,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> EntityLifecycleResponse:
    """Admin-only deactivation with DEACTIVATE confirmation + admin password + cascading schedule cleanup."""
    if payload.confirmation_text.strip() != "DEACTIVATE":
        raise AppError(
            code="VALIDATION_ERROR",
            message='You must type "DEACTIVATE" exactly to confirm deactivation.',
            status_code=400,
        )
    if not payload.admin_password or not verify_password(
        payload.admin_password, current_user.credential_hash
    ):
        raise AppError(
            code="INVALID_PASSWORD",
            message="Admin password is incorrect. Deactivation aborted.",
            status_code=403,
        )
    if not payload.reason or not payload.reason.strip():
        raise AppError(
            code="REASON_REQUIRED",
            message="A reason for deactivation is required.",
            status_code=400,
        )

    employee = await session.get(Employee, employee_id)
    if not employee:
        raise AppError(code="NOT_FOUND", message="Employee not found.", status_code=404)
    if (
        employee.role == "ADMIN"
        or employee.tally_id == "ADMIN001"
        or employee.id == current_user.employee_id
    ):
        raise AppError(
            code="FORBIDDEN",
            message="System admin accounts cannot be deactivated.",
            status_code=400,
        )
    if not employee.is_active:
        raise AppError(
            code="INVALID_STATE",
            message="Employee is already deactivated.",
            status_code=400,
        )

    eff = payload.effective_date or site_today()
    now = datetime.now(UTC)

    employee.is_active = False
    if employee.employment_end_date is None or employee.employment_end_date > eff:
        employee.employment_end_date = eff
    employee.version += 1

    # Immediately disable linked User login and revoke all refresh sessions
    user_stmt = select(User).where(
        or_(User.employee_id == employee.id, User.username == employee.tally_id)
    )
    linked_users = list((await session.execute(user_stmt)).scalars().all())
    revoked_sessions = 0
    for u in linked_users:
        u.is_active = False
        sess_stmt = select(UserSession).where(
            UserSession.user_id == u.id,
            UserSession.revoked_at.is_(None),
        )
        active_sessions = list((await session.execute(sess_stmt)).scalars().all())
        for s in active_sessions:
            s.revoked_at = now
            revoked_sessions += 1

    cascade_summary = await SchedulingService(session).cascade_employee_deactivation(
        employee_id=employee.id,
        effective_date=eff,
        actor_user_id=current_user.id,
    )
    cascade_summary["disabled_user_accounts"] = len(linked_users)
    cascade_summary["revoked_sessions"] = revoked_sessions

    await AuditService.log_action(
        session=session,
        action="DEACTIVATE_EMPLOYEE",
        entity_type="employee",
        entity_id=str(employee.id),
        diff={
            "tally_id": employee.tally_id,
            "name": employee.name,
            "role": employee.role,
            "effective_date": eff.isoformat(),
            **cascade_summary,
        },
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        reason=payload.reason.strip(),
    )
    await event_bus.publish(EmployeeProfileChanged(employee_id=employee.id), session=session)
    await session.commit()

    return EntityLifecycleResponse(
        status="DEACTIVATED",
        entity_id=employee.id,
        is_active=False,
        effective_date=eff,
        summary=cascade_summary,
        message=(
            f"Employee {employee.name} ({employee.tally_id}) deactivated effective {eff.isoformat()}. "
            "Login access disabled and future shifts marked as Needs Cover."
        ),
    )


@router.post("/{employee_id}/reactivate", response_model=EntityLifecycleResponse)
async def reactivate_employee(
    employee_id: UUID,
    payload: ReactivateRequest,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> EntityLifecycleResponse:
    """Admin-only clean reactivation (Option A): re-enables account & visibility without restoring old schedules."""
    if payload.confirmation_text.strip() != "REACTIVATE":
        raise AppError(
            code="VALIDATION_ERROR",
            message='You must type "REACTIVATE" exactly to confirm reactivation.',
            status_code=400,
        )
    if not payload.admin_password or not verify_password(
        payload.admin_password, current_user.credential_hash
    ):
        raise AppError(
            code="INVALID_PASSWORD",
            message="Admin password is incorrect. Reactivation aborted.",
            status_code=403,
        )
    if not payload.reason or not payload.reason.strip():
        raise AppError(
            code="REASON_REQUIRED",
            message="A reason for reactivation is required.",
            status_code=400,
        )

    employee = await session.get(Employee, employee_id)
    if not employee:
        raise AppError(code="NOT_FOUND", message="Employee not found.", status_code=404)
    if employee.is_active:
        raise AppError(
            code="INVALID_STATE",
            message="Employee is already active.",
            status_code=400,
        )

    employee.is_active = True
    employee.employment_end_date = None
    employee.version += 1

    user_stmt = select(User).where(
        or_(User.employee_id == employee.id, User.username == employee.tally_id)
    )
    linked_users = list((await session.execute(user_stmt)).scalars().all())
    for u in linked_users:
        u.is_active = True

    await AuditService.log_action(
        session=session,
        action="REACTIVATE_EMPLOYEE",
        entity_type="employee",
        entity_id=str(employee.id),
        diff={
            "tally_id": employee.tally_id,
            "name": employee.name,
            "re_enabled_user_accounts": len(linked_users),
            "schedules_restored": False,
        },
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        reason=payload.reason.strip(),
    )
    await event_bus.publish(EmployeeProfileChanged(employee_id=employee.id), session=session)
    await session.commit()

    return EntityLifecycleResponse(
        status="REACTIVATED",
        entity_id=employee.id,
        is_active=True,
        summary={"re_enabled_user_accounts": len(linked_users), "schedules_restored": False},
        message=(
            f"Employee {employee.name} ({employee.tally_id}) reactivated cleanly. "
            "No previous schedules were restored; assign shifts manually as needed."
        ),
    )


@router.patch("/{employee_id}", response_model=EmployeeRead)
async def update_employee(
    employee_id: UUID,
    request: EmployeeUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> EmployeeRead:
    # Role permissions:
    # Admin: all fields.
    # Engineer: weekly_off_day, accommodation_id, break_override_minutes in scope.
    if current_user.role == "ADMIN":
        scoped_ids = None
    elif current_user.role == "ENGINEER":
        scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
        # Verify engineer is only updating allowed fields
        disallowed_fields = {
            "name",
            "phone",
            "email",
            "role",
            "grade_code",
            "staff_grade_description",
            "country",
            "join_date",
            "employment_end_date",
            "is_active",
            "is_driver",
        }
        attempted_fields = set(request.model_dump(exclude_unset=True, exclude={"version"}).keys())
        if attempted_fields.intersection(disallowed_fields):
            raise AppError(
                code="FORBIDDEN",
                message="Engineers may only update weekly_off_day, accommodation_id, or break_override_minutes.",
                status_code=403,
            )
    else:
        raise AppError(
            code="FORBIDDEN", message="You are not authorized to update employees.", status_code=403
        )

    employee = await OrgService.update_employee(
        session=session,
        employee_id=employee_id,
        data=request,
        scoped_ids=scoped_ids,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    if request.break_override_minutes is not None and employee.role == "SUPERVISOR":
        eff_from = request.effective_from or site_today()
        await PayrollSalaryService.propagate_crew_break_to_supervisor_crew(
            session=session,
            supervisor_id=employee.id,
            break_minutes=request.break_override_minutes,
            effective_from=eff_from,
            actor_user_id=current_user.id,
            actor_role=current_user.role,
        )
    return EmployeeRead.model_validate(employee)


@router.post("/{employee_id}/grade-change", response_model=EmployeeRead)
async def change_employee_grade(
    employee_id: UUID,
    request: GradeChangeRequest,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> EmployeeRead:
    employee = await OrgService.change_grade(
        session=session,
        employee_id=employee_id,
        request=request,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    return EmployeeRead.model_validate(employee)


@router.patch("/{employee_id}/profile-details", response_model=EmployeeRead)
async def update_employee_profile_details(
    employee_id: UUID,
    request: EmployeeProfileDetailsUpdate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> EmployeeRead:
    """Update employee trade designation, grade code, or driver status with immutable audit history."""
    employee = await OrgService.update_profile_details(
        session=session,
        employee_id=employee_id,
        request=request,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    return EmployeeRead.model_validate(employee)


@router.get(
    "/{employee_id}/attribute-history",
    response_model=list[EmployeeAttributeHistoryRead],
)
async def list_employee_attribute_history(
    employee_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[EmployeeAttributeHistoryRead]:
    """List immutable attribute history records (grade, designation, driver) for an employee."""
    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
    if scoped_ids is not None and employee_id not in scoped_ids:
        raise AppError(code="OUT_OF_SCOPE", message="Employee is out of scope.", status_code=403)
    return await OrgService.list_attribute_history(session, employee_id)


@router.get("/{employee_id}/reporting-lines", response_model=list[ReportingLineRead])
async def list_reporting_lines(
    employee_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[ReportingLineRead]:
    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
    if scoped_ids is not None and employee_id not in scoped_ids:
        raise AppError(code="OUT_OF_SCOPE", message="Employee is out of scope.", status_code=403)
    lines = await OrgService.list_reporting_lines(session, employee_id)
    return lines


@router.post("/{employee_id}/reporting-lines", response_model=ReportingLineRead, status_code=201)
async def add_reporting_line(
    employee_id: UUID,
    request: ReportingLineCreate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> ReportingLineRead:
    res = await OrgService.add_reporting_line(
        session=session,
        employee_id=employee_id,
        data=request,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    if request.relationship == "SUPERVISOR":
        mgr = await session.get(Employee, request.manager_id)
        if mgr and mgr.break_override_minutes and mgr.break_override_minutes > 0:
            await PayrollSalaryService.propagate_crew_break_to_worker(
                session=session,
                worker_id=employee_id,
                break_minutes=mgr.break_override_minutes,
                effective_from=site_today(),
                actor_user_id=current_user.id,
                actor_role=current_user.role,
            )
    return res


@router.delete("/{employee_id}/reporting-lines/{line_id}")
async def remove_reporting_line(
    employee_id: UUID,
    line_id: UUID,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await OrgService.remove_reporting_line(
        session=session,
        reporting_line_id=line_id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    return {"message": "Reporting line removed."}


@router.get("/{employee_id}/documents", response_model=list[EmployeeDocumentRead])
async def list_employee_documents(
    employee_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[EmployeeDocumentRead]:
    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
    if scoped_ids is not None and employee_id not in scoped_ids:
        raise AppError(code="OUT_OF_SCOPE", message="Employee is out of scope.", status_code=403)
    docs = await OrgService.list_documents(session, employee_id)
    return [EmployeeDocumentRead.model_validate(d) for d in docs]


@router.post("/{employee_id}/documents", response_model=EmployeeDocumentRead)
async def add_or_update_employee_document(
    employee_id: UUID,
    request: EmployeeDocumentCreate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> EmployeeDocumentRead:
    doc = await OrgService.add_or_update_document(
        session=session,
        employee_id=employee_id,
        data=request,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    return EmployeeDocumentRead.model_validate(doc)


@router.get("/{employee_id}/devices", response_model=list[RegisteredDeviceRead])
async def list_employee_devices(
    employee_id: UUID,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> list[RegisteredDeviceRead]:
    devices = await OrgService.list_devices(session, employee_id)
    return [RegisteredDeviceRead.model_validate(d) for d in devices]
