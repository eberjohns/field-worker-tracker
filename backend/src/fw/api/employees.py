import io
from datetime import UTC, datetime
from uuid import UUID

import xlsxwriter
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.core.errors import AppError
from fw.modules.archive.dsar import generate_employee_dsar_excel
from fw.modules.identity import User, get_current_user, require_role
from fw.modules.org import (
    Employee,
    EmployeeBulkUpdateRequest,
    EmployeeCreate,
    EmployeeDocumentCreate,
    EmployeeDocumentRead,
    EmployeeRead,
    EmployeeUpdate,
    GradeChangeRequest,
    HierarchyTreeNode,
    OrgService,
    RegisteredDeviceRead,
    ReportingLineCreate,
    ReportingLineRead,
    ScopeService,
)
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
        is_active=is_active,
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
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Export filtered employee directory as an Excel spreadsheet."""
    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
    employees = await OrgService.list_employees(
        session=session,
        scoped_ids=scoped_ids,
        role=role,
        country=country,
        is_active=is_active,
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
    return {"updated_count": updated_count}


@router.get("/{employee_id}", response_model=EmployeeRead)
async def get_employee(
    employee_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> EmployeeRead:
    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
    employee = await OrgService.get_employee(session, employee_id, scoped_ids)
    return EmployeeRead.model_validate(employee)


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
    return await OrgService.add_reporting_line(
        session=session,
        employee_id=employee_id,
        data=request,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )


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
