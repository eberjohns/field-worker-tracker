"""Schemas for planned vs actual (DEC-59). Money fields are Admin only: null for other roles."""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from fw.modules.jobs import BudgetWarning, JobItemCreate


class PlannedActualFigures(BaseModel):
    planned_hours: Decimal = Decimal("0")
    actual_hours: Decimal = Decimal("0")
    hours_diff: Decimal = Decimal("0")
    hours_diff_pct: Decimal | None = None
    planned_cost: Decimal | None = None
    actual_cost: Decimal | None = None
    cost_diff: Decimal | None = None
    cost_diff_pct: Decimal | None = None


class PlannedActualMonth(PlannedActualFigures):
    month_from: date
    month_to: date


class PlannedActualItem(PlannedActualFigures):
    job_item_id: UUID
    sub_item_code: str
    staff_grade_description: str
    grade_code: str
    is_budget_only: bool = False
    is_active: bool = True
    excluded_from_totals: bool = False  # MISSING_GRADE_RATE
    hourly_rate: Decimal | None = None
    months: list[PlannedActualMonth] = Field(default_factory=list)


class WorksiteBudgetVsActualItem(PlannedActualFigures):
    """One worksite: planned vs actual for a period, per item and per month.

    The fields after ``months`` keep the shape the Payroll Budget tab and the Job Costing report
    already read; ``prorated_budget`` is now the planned cost for the period (no days / 365 cap).
    """

    worksite_id: UUID
    job_number: str
    job_name: str
    country: str
    period_from: date
    period_to: date
    revision_code: str | None = None
    unplanned_hours: Decimal = Decimal("0")  # approved hours with no scheduled job item
    unallocated_actual_cost: Decimal | None = None  # allocation in months with no hours to split by
    items: list[PlannedActualItem] = Field(default_factory=list)
    months: list[PlannedActualMonth] = Field(default_factory=list)
    warnings: list[BudgetWarning] = Field(default_factory=list)
    missing_rate_hours: Decimal = Decimal("0")
    # --- kept for existing callers ---
    salary_revision_code: str | None = None
    assigned_revision_code: str | None = None
    annual_planned_man_hours: Decimal = Decimal("0")
    annual_labor_budget: Decimal | None = None
    prorated_budget: Decimal | None = None
    pro_rated_budget: Decimal | None = None
    actual_cost_allocated: Decimal | None = None
    actual_allocated_cost: Decimal | None = None
    variance: Decimal | None = None
    variance_amount: Decimal | None = None
    variance_percent: Decimal | None = None
    is_over_budget: bool | None = None
    is_under_budget: bool | None = None
    manual_budget_override: Decimal | None = None
    is_custom_budget_override: bool = False


class NewWorksiteBudgetPreview(BaseModel):
    """Budget preview for a job item of a worksite that is not saved yet (Add Worksite form)."""

    country: str = Field(..., pattern="^(AE|SA)$")
    salary_revision_code: str | None = None
    contract_start: date | None = None
    contract_end: date | None = None
    item: JobItemCreate
