"""Pydantic schemas for employee salary structures and history."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EmployeeSalaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    tally_id: str | None = None
    employee_name: str | None = None
    effective_from: date
    standard_hours: Decimal
    basic_salary: Decimal
    special_allowance: Decimal
    fixed_ot_amount: Decimal
    bonus: Decimal
    telephone_allowance: Decimal
    housing_transport_allowance: Decimal
    salary_portion: Decimal
    difference: Decimal = Decimal("0.00")
    created_at: datetime


class EmployeeSalaryCreate(BaseModel):
    effective_from: date | None = None
    standard_hours: Decimal = Field(default=Decimal("8.0"), ge=Decimal("1.0"), le=Decimal("24.0"))
    basic_salary: Decimal = Field(..., ge=Decimal("0.00"))
    special_allowance: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    fixed_ot_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    bonus: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    telephone_allowance: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    housing_transport_allowance: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))


class EmployeeSalaryHistoryResponse(BaseModel):
    employee_id: UUID
    tally_id: str
    employee_name: str
    current_salary: EmployeeSalaryRead | None = None
    last_change_date: date | None = None
    last_change_difference: Decimal | None = None
    history: list[EmployeeSalaryRead] = Field(default_factory=list)


class SalaryStructureListItem(BaseModel):
    employee_id: UUID
    tally_id: str
    name: str
    role: str
    country: str
    standard_hours: Decimal
    salary_portion: Decimal
    basic_salary: Decimal
    effective_from: date
    last_change_date: date | None = None
    difference: Decimal = Decimal("0.00")
