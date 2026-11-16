"""Pure payroll and salary business rules."""

from fw.rules.payroll.formulas import (
    DEFAULT_HR_OH_RATE,
    DEFAULT_OT1_MULTIPLIER,
    DEFAULT_OT2_MULTIPLIER,
    DEFAULT_OT_DIVISOR,
    calculate_final_total_staff_cost,
    calculate_gratuity,
    calculate_gross_pay,
    calculate_hourly_ot_rate,
    calculate_hr_overhead,
    calculate_leave_salary,
    calculate_missed_hours_deduction,
    calculate_per_month_provision,
    calculate_provisions,
    calculate_revision_planned_hourly_cost,
    calculate_total_staff_cost,
)
from fw.rules.payroll.salary import (
    calculate_salary_difference,
    calculate_salary_portion,
    compute_next_payroll_month_start,
    round_money,
)

__all__ = [
    "DEFAULT_HR_OH_RATE",
    "DEFAULT_OT1_MULTIPLIER",
    "DEFAULT_OT2_MULTIPLIER",
    "DEFAULT_OT_DIVISOR",
    "calculate_final_total_staff_cost",
    "calculate_gratuity",
    "calculate_gross_pay",
    "calculate_hourly_ot_rate",
    "calculate_hr_overhead",
    "calculate_leave_salary",
    "calculate_missed_hours_deduction",
    "calculate_per_month_provision",
    "calculate_provisions",
    "calculate_revision_planned_hourly_cost",
    "calculate_salary_difference",
    "calculate_salary_portion",
    "calculate_total_staff_cost",
    "compute_next_payroll_month_start",
    "round_money",
]
