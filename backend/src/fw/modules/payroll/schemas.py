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


# --- Salary Revisions ---


class SalaryRevisionLineCreate(BaseModel):
    grade_code: str
    grade_group_title: str | None = None
    basic_salary: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    special_allowance: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    fixed_ot_amount: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    bonus: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    visa_provision: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    air_ticket_provision: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    uniform_provision: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    medical_provision: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    accommodation_provision: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"))
    transportation_provision: Decimal | None = Field(default=Decimal("0.00"), ge=Decimal("0.00"))


class SalaryRevisionLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    grade_code: str
    grade_group_title: str | None = None
    basic_salary: Decimal
    special_allowance: Decimal
    fixed_ot_amount: Decimal
    bonus: Decimal
    visa_provision: Decimal
    air_ticket_provision: Decimal
    uniform_provision: Decimal
    medical_provision: Decimal
    accommodation_provision: Decimal
    transportation_provision: Decimal | None = None
    total_provisions: Decimal = Decimal("0.00")
    total_salary_portion: Decimal = Decimal("0.00")
    planned_hourly_cost: Decimal = Decimal("0.00")


class SalaryRevisionCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=255)
    country: str = Field(default="AE", max_length=10)
    effective_from: date
    effective_to: date | None = None
    notes: str | None = None
    lines: list[SalaryRevisionLineCreate] = Field(default_factory=list)


class SalaryRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    country: str
    effective_from: date
    effective_to: date | None = None
    status: str
    notes: str | None = None
    line_count: int = 0
    created_at: datetime
    updated_at: datetime


class SalaryRevisionDetailRead(SalaryRevisionRead):
    lines: list[SalaryRevisionLineRead] = Field(default_factory=list)


class SalaryRevisionLineDiff(BaseModel):
    grade_code: str
    field_name: str
    old_value: Decimal | str | None
    new_value: Decimal | str | None
    is_changed: bool


class SalaryRevisionImportDiffResponse(BaseModel):
    target_revision_code: str
    base_revision_code: str | None = None
    new_grades_count: int
    updated_grades_count: int
    unchanged_grades_count: int
    diffs: list[SalaryRevisionLineDiff] = Field(default_factory=list)
    preview_lines: list[SalaryRevisionLineCreate] = Field(default_factory=list)


# --- Payroll Runs & Records ---


class PayrollRunCreate(BaseModel):
    period_start: date
    period_end: date
    country: str = "AE"
    notes: str | None = None


class PayrollRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    tally_id: str | None = None
    employee_name: str | None = None
    standard_hours: Decimal
    scheduled_hours: Decimal
    worked_hours: Decimal
    paid_leave_hours: Decimal
    unpaid_leave_hours: Decimal
    shortfall_hours: Decimal
    missed_hours_deduction: Decimal
    ot1_hours: Decimal
    ot2_hours: Decimal
    salary_portion: Decimal
    ot1_amount: Decimal
    ot2_amount: Decimal
    gross_pay: Decimal
    net_pay: Decimal
    gratuity: Decimal
    leave_salary: Decimal
    provisions: Decimal
    per_month_provision: Decimal
    total_staff_cost: Decimal
    hr_oh_amount: Decimal
    final_total_staff_cost: Decimal
    snapshot: dict = Field(default_factory=dict)
    created_at: datetime


class PayrollTotalsSnapshot(BaseModel):
    worker_count: int = 0
    scheduled_hours_total: Decimal = Decimal("0.00")
    worked_hours_total: Decimal = Decimal("0.00")
    ot1_hours_total: Decimal = Decimal("0.00")
    ot2_hours_total: Decimal = Decimal("0.00")
    ot1_amount_total: Decimal = Decimal("0.00")
    ot2_amount_total: Decimal = Decimal("0.00")
    gross_pay_total: Decimal = Decimal("0.00")
    net_pay_total: Decimal = Decimal("0.00")
    provisions_total: Decimal = Decimal("0.00")
    total_staff_cost_total: Decimal = Decimal("0.00")
    final_total_staff_cost_total: Decimal = Decimal("0.00")


class PayrollRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    period_start: date
    period_end: date
    country: str
    status: str
    run_no: int
    created_by: str
    created_by_user_id: UUID | None = None
    approved_by_user_id: UUID | None = None
    approved_at: datetime | None = None
    calculation_version: str
    totals_snapshot: PayrollTotalsSnapshot | dict | None = None
    notes: str | None = None
    record_count: int = 0
    created_at: datetime
    updated_at: datetime


class PayrollRunDetailRead(PayrollRunRead):
    records: list[PayrollRecordRead] = Field(default_factory=list)


class PayrollIssueItem(BaseModel):
    issue_type: str  # UNAPPROVED_OVERTIME, MISSING_SALARY_STRUCTURE, MISSING_STANDARD_HOURS
    employee_id: UUID
    tally_id: str
    employee_name: str
    details: str
    work_date: date | None = None


class PayrollRunIssuesResponse(BaseModel):
    run_id: UUID
    total_issues: int
    unapproved_overtime_count: int
    missing_salary_structure_count: int
    missing_standard_hours_count: int
    issues: list[PayrollIssueItem] = Field(default_factory=list)


class WorkerMobilePayrollSlip(BaseModel):
    payroll_record_id: UUID
    payroll_run_id: UUID
    month_label: str  # e.g. "October 2026"
    period_start: date
    period_end: date
    status: str
    standard_hours: Decimal
    worked_hours: Decimal
    paid_leave_hours: Decimal
    unpaid_leave_hours: Decimal
    salary_portion: Decimal
    missed_hours_deduction: Decimal
    ot1_hours: Decimal
    ot1_amount: Decimal
    ot2_hours: Decimal
    ot2_amount: Decimal
    gross_pay: Decimal
    net_pay: Decimal
    approved_at: datetime | None = None


class WorksiteBudgetVsActualItem(BaseModel):
    worksite_id: UUID
    job_number: str
    job_name: str
    country: str
    salary_revision_code: str | None = None
    annual_planned_man_hours: Decimal
    annual_labor_budget: Decimal
    prorated_budget: Decimal
    actual_cost_allocated: Decimal
    variance: Decimal  # actual - prorated_budget
    is_over_budget: bool
    manual_budget_override: Decimal | None = None

