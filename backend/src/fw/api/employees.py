from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.core.errors import AppError
from fw.modules.identity import User, get_current_user, require_role
from fw.modules.org import (
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

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("", response_model=list[EmployeeRead])
async def list_employees(
    role: str | None = None,
    sgd: str | None = None,
    grade_code: str | None = None,
    manager_id: UUID | None = None,
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
        country=country,
        is_active=is_active,
        q=q,
        limit=limit,
        offset=offset,
    )
    return [EmployeeRead.model_validate(e) for e in employees]


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
        disallowed_fields = {"name", "phone", "email", "role", "grade_code", "staff_grade_description", "country", "join_date", "employment_end_date", "is_active", "is_driver"}
        attempted_fields = set(request.model_dump(exclude_unset=True, exclude={"version"}).keys())
        if attempted_fields.intersection(disallowed_fields):
            raise AppError(
                code="FORBIDDEN",
                message="Engineers may only update weekly_off_day, accommodation_id, or break_override_minutes.",
                status_code=403,
            )
    else:
        raise AppError(code="FORBIDDEN", message="You are not authorized to update employees.", status_code=403)

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
    return [ReportingLineRead.model_validate(line) for line in lines]


@router.post("/{employee_id}/reporting-lines", response_model=ReportingLineRead, status_code=201)
async def add_reporting_line(
    employee_id: UUID,
    request: ReportingLineCreate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> ReportingLineRead:
    line = await OrgService.add_reporting_line(
        session=session,
        employee_id=employee_id,
        data=request,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    return ReportingLineRead.model_validate(line)


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
