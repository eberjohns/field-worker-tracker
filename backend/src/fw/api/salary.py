"""API endpoints for employee salary structures and history."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.modules.identity import User, get_current_user, require_role
from fw.modules.payroll import (
    EmployeeSalaryCreate,
    EmployeeSalaryHistoryResponse,
    EmployeeSalaryRead,
    EmployeeSalaryUpdate,
    PayrollSalaryService,
    SalaryStructureListItem,
)

router = APIRouter(tags=["salary"])


@router.get("/employees/{employee_id}/salary", response_model=EmployeeSalaryHistoryResponse)
async def get_employee_salary_history(
    employee_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> EmployeeSalaryHistoryResponse:
    """Get salary history, current salary structure, last change date and difference."""
    # Workers can see their own, admins can view all. Other roles are forbidden (DEC-47).
    if current_user.role != "ADMIN" and not (
        current_user.role == "WORKER" and current_user.employee_id == employee_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN",
                "message": "Only administrators can view employee salary structures.",
            },
        )

    history = await PayrollSalaryService.get_salary_history(session, employee_id)
    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Employee {employee_id} not found."},
        )
    return history


@router.post(
    "/employees/{employee_id}/salary",
    response_model=EmployeeSalaryRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_or_update_employee_salary(
    employee_id: UUID,
    data: EmployeeSalaryCreate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> EmployeeSalaryRead:
    """Create or update an effective-dated salary structure for an employee."""
    salary_record = await PayrollSalaryService.create_or_update_salary(
        session=session,
        employee_id=employee_id,
        data=data,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    return salary_record


@router.patch(
    "/employees/{employee_id}/salary/{salary_id}",
    response_model=EmployeeSalaryRead,
)
async def update_future_salary_revision(
    employee_id: UUID,
    salary_id: UUID,
    data: EmployeeSalaryUpdate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> EmployeeSalaryRead:
    """Update a future-dated salary revision (DEC-06). Rejects current/past rows."""
    return await PayrollSalaryService.update_future_salary_revision(
        session=session,
        employee_id=employee_id,
        salary_id=salary_id,
        data=data,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )


@router.delete(
    "/employees/{employee_id}/salary/{salary_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_future_salary_revision(
    employee_id: UUID,
    salary_id: UUID,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a future-dated salary revision (DEC-06). Rejects current/past rows."""
    await PayrollSalaryService.delete_future_salary_revision(
        session=session,
        employee_id=employee_id,
        salary_id=salary_id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )


@router.get("/salary-structures", response_model=list[SalaryStructureListItem])
async def list_salary_structures(
    country: str | None = None,
    as_of: date | None = None,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> list[SalaryStructureListItem]:
    """List active salary structures across all workers."""
    items = await PayrollSalaryService.list_salary_structures(
        session=session,
        country=country,
        as_of=as_of,
    )
    return items
