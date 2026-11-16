"""Unified Registry of Reports with typed columns, permissions, and formatters."""

from dataclasses import dataclass, field
from typing import Any

from fw.modules.reports.schemas import ReportColumn, ReportDefinition


@dataclass
class ReportSpec:
    key: str
    name: str
    description: str
    category: str
    allowed_roles: list[str]
    is_cost_report: bool
    columns: list[ReportColumn]
    supported_formats: list[str]
    handler_module: str
    filter_schema: dict[str, Any] = field(default_factory=dict)


# 1. daily-attendance (D3 layout)
DAILY_ATTENDANCE_COLS = [
    ReportColumn(key="worker_id", label="Worker ID", type="string"),
    ReportColumn(key="worker_name", label="Worker Name", type="string"),
    ReportColumn(key="work_date", label="Date", type="date"),
    ReportColumn(key="status", label="Status", type="badge"),
    # Planned 7 cols
    ReportColumn(key="planned_acc_start", label="Pl. Acc Start", type="string"),
    ReportColumn(key="planned_first_site", label="Pl. First Site", type="string"),
    ReportColumn(key="planned_break", label="Pl. Break", type="duration"),
    ReportColumn(key="planned_last_site", label="Pl. Last Site", type="string"),
    ReportColumn(key="planned_acc_end", label="Pl. Acc End", type="string"),
    ReportColumn(key="planned_total_time", label="Pl. Total Time", type="duration"),
    ReportColumn(key="planned_worked_time", label="Pl. Worked Time", type="duration"),
    # Actual 7 cols
    ReportColumn(key="actual_acc_start", label="Act. Acc Start", type="string"),
    ReportColumn(key="actual_first_site", label="Act. First Site", type="string"),
    ReportColumn(key="actual_break", label="Act. Break", type="duration"),
    ReportColumn(key="actual_last_site", label="Act. Last Site", type="string"),
    ReportColumn(key="actual_acc_end", label="Act. Acc End", type="string"),
    ReportColumn(key="actual_total_time", label="Act. Total Time", type="duration"),
    ReportColumn(key="actual_worked_time", label="Act. Worked Time", type="duration"),
    # Variations & review
    ReportColumn(key="var_total_time", label="Var. Total Time", type="duration"),
    ReportColumn(key="var_worked_time", label="Var. Worked Time", type="duration"),
    ReportColumn(key="ot1_hours", label="OT1 Hours", type="number"),
    ReportColumn(key="ot2_hours", label="OT2 Hours", type="number"),
    ReportColumn(key="flags", label="Flags", type="string"),
    ReportColumn(key="comments", label="Comments", type="string"),
    ReportColumn(key="approval", label="Approval", type="badge"),
]

# 2. monthly-attendance
MONTHLY_ATTENDANCE_COLS = [
    ReportColumn(key="worker_id", label="Worker ID", type="string"),
    ReportColumn(key="worker_name", label="Worker Name", type="string"),
    ReportColumn(key="month", label="Month", type="string"),
    ReportColumn(key="days_present", label="Days Present", type="number"),
    ReportColumn(key="days_partial", label="Days Partial", type="number"),
    ReportColumn(key="days_absent", label="Days Absent", type="number"),
    ReportColumn(key="days_shortfall", label="Days Shortfall", type="number"),
    ReportColumn(key="total_worked_hours", label="Total Worked (h)", type="number"),
    ReportColumn(key="cumulative_worked_hours", label="Cumulative Worked (h)", type="number"),
    ReportColumn(key="ot1_total_hours", label="OT1 Total (h)", type="number"),
    ReportColumn(key="ot2_total_hours", label="OT2 Total (h)", type="number"),
    ReportColumn(key="days_pending_review", label="Days Pending Review", type="number"),
]

# 3. employee-movement
EMPLOYEE_MOVEMENT_COLS = [
    ReportColumn(key="worker_id", label="Worker ID", type="string"),
    ReportColumn(key="worker_name", label="Worker Name", type="string"),
    ReportColumn(key="work_date", label="Date", type="date"),
    ReportColumn(key="seq", label="#", type="number"),
    ReportColumn(key="segment_type", label="Segment Type", type="string"),
    ReportColumn(key="location_name", label="Place", type="string"),
    ReportColumn(key="start_time", label="Start Time", type="string"),
    ReportColumn(key="end_time", label="End Time", type="string"),
    ReportColumn(key="duration_minutes", label="Duration (min)", type="number"),
    ReportColumn(key="observation_type", label="Tag", type="badge"),  # OBSERVED / INFERRED
    ReportColumn(key="unaccounted_minutes", label="Unaccounted (min)", type="number"),
]

# 4. site-visits
SITE_VISITS_COLS = [
    ReportColumn(key="worker_id", label="Worker ID", type="string"),
    ReportColumn(key="worker_name", label="Worker Name", type="string"),
    ReportColumn(key="work_date", label="Date", type="date"),
    ReportColumn(key="worksite_code", label="Worksite Code", type="string"),
    ReportColumn(key="worksite_name", label="Worksite Name", type="string"),
    ReportColumn(key="job_item_name", label="Job Item", type="string"),
    ReportColumn(key="scheduled_hours", label="Scheduled (h)", type="number"),
    ReportColumn(key="entry_time", label="Entry Time", type="string"),
    ReportColumn(key="exit_time", label="Exit Time", type="string"),
    ReportColumn(key="time_spent_minutes", label="Time Spent (min)", type="number"),
    ReportColumn(key="exit_tag", label="Exit Tag", type="badge"),
    ReportColumn(key="counted_as_completed", label="Completed", type="badge"),
    ReportColumn(key="flags", label="Flags", type="string"),
]

# 5. employee-utilization (DEC-28)
EMPLOYEE_UTILIZATION_COLS = [
    ReportColumn(key="worker_id", label="Worker ID", type="string"),
    ReportColumn(key="worker_name", label="Worker Name", type="string"),
    ReportColumn(key="work_date", label="Date", type="date"),
    ReportColumn(key="shift_span_minutes", label="Shift Span (min)", type="duration"),
    ReportColumn(key="productive_minutes", label="Productive (min)", type="duration"),
    ReportColumn(key="travel_minutes", label="Travel (min)", type="duration"),
    ReportColumn(key="idle_minutes", label="Idle (min)", type="duration"),
    ReportColumn(key="break_minutes", label="Break (min)", type="duration"),
    ReportColumn(key="utilization_pct", label="Utilization %", type="number"),
    ReportColumn(key="scheduled_minutes", label="Scheduled (min)", type="duration"),
    ReportColumn(key="worked_minutes", label="Worked (min)", type="duration"),
    ReportColumn(key="scheduled_vs_worked_pct", label="Sched vs Worked %", type="number"),
    ReportColumn(key="tag", label="Tag", type="badge"),  # INFERRED
]

# 6. transportation-time
TRANSPORTATION_TIME_COLS = [
    ReportColumn(key="worker_id", label="Worker ID", type="string"),
    ReportColumn(key="worker_name", label="Worker Name", type="string"),
    ReportColumn(key="work_date", label="Date", type="date"),
    ReportColumn(key="commute_out_minutes", label="Commute Out (min)", type="duration"),
    ReportColumn(key="inter_site_minutes", label="Inter-Site (min)", type="duration"),
    ReportColumn(key="commute_back_minutes", label="Commute Back (min)", type="duration"),
    ReportColumn(key="total_transit_minutes", label="Total Transit (min)", type="duration"),
    ReportColumn(key="is_driver_day", label="Driver Day", type="badge"),
    ReportColumn(key="tag", label="Tag", type="badge"),  # INFERRED
]

# 7. late-early-departure
LATE_EARLY_DEPARTURE_COLS = [
    ReportColumn(key="worker_id", label="Worker ID", type="string"),
    ReportColumn(key="worker_name", label="Worker Name", type="string"),
    ReportColumn(key="work_date", label="Date", type="date"),
    ReportColumn(key="late_arrival_minutes", label="Late Arrival (min)", type="duration"),
    ReportColumn(key="late_dep_acc_minutes", label="Late Dep. Acc (min)", type="duration"),
    ReportColumn(key="early_dep_minutes", label="Early Exit (min)", type="duration"),
    ReportColumn(key="shortfall_minutes", label="Shortfall (min)", type="duration"),
    ReportColumn(key="grace_applied", label="Grace Applied", type="badge"),
    ReportColumn(key="comments", label="Comments", type="string"),
    ReportColumn(key="review_state", label="Review State", type="badge"),
]

# 8. project-attendance-summary
PROJECT_ATTENDANCE_SUMMARY_COLS = [
    ReportColumn(key="worksite_code", label="Worksite Code", type="string"),
    ReportColumn(key="worksite_name", label="Worksite Name", type="string"),
    ReportColumn(key="group_name", label="Group", type="string"),
    ReportColumn(key="zone_name", label="Zone", type="string"),
    ReportColumn(key="scheduled_worker_days", label="Sched. Worker-Days", type="number"),
    ReportColumn(key="scheduled_man_hours", label="Sched. Man-Hours", type="number"),
    ReportColumn(key="deployed_workers", label="Deployed Workers", type="number"),
    ReportColumn(key="deployed_worker_days", label="Deployed Worker-Days", type="number"),
    ReportColumn(key="actual_man_hours", label="Actual Man-Hours", type="number"),
    ReportColumn(key="present_count", label="Present", type="number"),
    ReportColumn(key="partial_count", label="Partial", type="number"),
    ReportColumn(key="absent_count", label="Absent", type="number"),
    ReportColumn(key="understaffed_days", label="Understaffed Days", type="number"),
]

# 9. pending-visits (DEC-32)
PENDING_VISITS_COLS = [
    ReportColumn(key="worksite_code", label="Worksite Code", type="string"),
    ReportColumn(key="worksite_name", label="Worksite Name", type="string"),
    ReportColumn(key="job_item_name", label="Job Item", type="string"),
    ReportColumn(key="assigned_workers", label="Assigned Workers", type="string"),
    ReportColumn(key="supervisor_name", label="Supervisor", type="string"),
    ReportColumn(key="due_date", label="Due Date", type="date"),
    ReportColumn(key="age_days", label="Age (Days)", type="number"),
    ReportColumn(key="status", label="Status", type="badge"),
    ReportColumn(key="latest_explanation", label="Explanation", type="string"),
    ReportColumn(key="is_escalated", label="Escalated", type="badge"),
]

# 10. staffing-gaps
STAFFING_GAPS_COLS = [
    ReportColumn(key="target_date", label="Date", type="date"),
    ReportColumn(key="worksite_name", label="Worksite", type="string"),
    ReportColumn(key="job_item_name", label="Job Item", type="string"),
    ReportColumn(key="gap_reason", label="Reason", type="string"),
    ReportColumn(key="staff_type", label="Staff Type", type="string"),
    ReportColumn(key="required_hours", label="Required (h)", type="number"),
    ReportColumn(key="allocated_hours", label="Allocated (h)", type="number"),
    ReportColumn(key="gap_hours", label="Gap (h)", type="number"),
    ReportColumn(key="status", label="Status", type="badge"),
]

# 11. document-expiry
DOCUMENT_EXPIRY_COLS = [
    ReportColumn(key="worker_id", label="Worker ID", type="string"),
    ReportColumn(key="worker_name", label="Worker Name", type="string"),
    ReportColumn(key="document_type", label="Document Type", type="string"),
    ReportColumn(key="document_number", label="Document Number", type="string"),
    ReportColumn(key="expiry_date", label="Expiry Date", type="date"),
    ReportColumn(key="days_remaining", label="Days Remaining", type="number"),
    ReportColumn(key="status", label="Status", type="badge"),
    ReportColumn(key="supervisor_name", label="Supervisor", type="string"),
]

# 12. weekly-roster
WEEKLY_ROSTER_COLS = [
    ReportColumn(key="worker_id", label="Worker ID", type="string"),
    ReportColumn(key="worker_name", label="Worker Name", type="string"),
    ReportColumn(key="grade", label="Grade", type="string"),
    ReportColumn(key="supervisor_name", label="Supervisor", type="string"),
    ReportColumn(key="engineer_name", label="Engineer", type="string"),
    ReportColumn(key="mon_sites", label="Mon", type="string"),
    ReportColumn(key="tue_sites", label="Tue", type="string"),
    ReportColumn(key="wed_sites", label="Wed", type="string"),
    ReportColumn(key="thu_sites", label="Thu", type="string"),
    ReportColumn(key="fri_sites", label="Fri", type="string"),
    ReportColumn(key="sat_sites", label="Sat", type="string"),
    ReportColumn(key="sun_sites", label="Sun", type="string"),
    ReportColumn(key="total_planned_hours", label="Total Planned (h)", type="number"),
    ReportColumn(key="standard_hours", label="Standard (h)", type="number"),
]

# 13. payroll (DEC-01, DEC-06, DEC-07, DEC-30) - Admin Only
PAYROLL_COLS = [
    ReportColumn(key="worker_id", label="Worker ID", type="string"),
    ReportColumn(key="worker_name", label="Worker Name", type="string"),
    ReportColumn(key="grade", label="Grade", type="string"),
    ReportColumn(key="supervisor_name", label="Supervisor", type="string"),
    ReportColumn(key="group_name", label="Group", type="string"),
    ReportColumn(key="zone_name", label="Zone", type="string"),
    ReportColumn(key="standard_hours", label="Std Hours", type="number"),
    ReportColumn(key="basic_salary", label="Basic Salary", type="money"),
    ReportColumn(key="special_allowance", label="Special Allow.", type="money"),
    ReportColumn(key="fixed_ot_amount", label="FOT", type="money"),
    ReportColumn(key="bonus_amount", label="Bonus", type="money"),
    ReportColumn(key="telephone_allowance", label="Telephone Allow.", type="money"),
    ReportColumn(key="housing_allowance", label="Housing/Trans. Allow.", type="money"),
    ReportColumn(key="ot1_hours", label="OT1 Hours", type="number"),
    ReportColumn(key="ot1_amount", label="OT1 Amount", type="money"),
    ReportColumn(key="ot2_hours", label="OT2 Hours", type="number"),
    ReportColumn(key="ot2_amount", label="OT2 Amount", type="money"),
    ReportColumn(key="missed_hours_deduction", label="Deductions", type="money"),
    ReportColumn(key="gross_pay", label="Gross Pay", type="money"),
    ReportColumn(key="net_pay", label="Net Pay", type="money"),
    ReportColumn(key="last_salary_change_date", label="Last Change Date", type="date"),
    ReportColumn(key="salary_delta", label="Last Change Delta", type="money"),
]

# 14. provisions-staff-cost (DEC-39) - Admin Only
PROVISIONS_STAFF_COST_COLS = [
    ReportColumn(key="worker_id", label="Worker ID", type="string"),
    ReportColumn(key="worker_name", label="Worker Name", type="string"),
    ReportColumn(key="salary_portion", label="Salary Portion", type="money"),
    ReportColumn(key="ot_amounts", label="OT Amounts", type="money"),
    ReportColumn(key="gratuity_provision", label="Gratuity", type="money"),
    ReportColumn(key="leave_salary_provision", label="Leave Salary", type="money"),
    ReportColumn(key="visa_provision", label="Visa", type="money"),
    ReportColumn(key="air_ticket_provision", label="Air Ticket", type="money"),
    ReportColumn(key="uniform_provision", label="Uniform", type="money"),
    ReportColumn(key="accommodation_provision", label="Accommodation", type="money"),
    ReportColumn(key="medical_provision", label="Medical", type="money"),
    ReportColumn(key="per_month_provision", label="Per-Month Provision", type="money"),
    ReportColumn(key="total_staff_cost", label="Total Staff Cost", type="money"),
    ReportColumn(key="hr_oh_amount", label="HR OH (5%)", type="money"),
    ReportColumn(key="final_total_staff_cost", label="Final Total Staff Cost", type="money"),
]

# 15. job-costing (DEC-29) - Admin Only
JOB_COSTING_COLS = [
    ReportColumn(key="worksite_code", label="Worksite Code", type="string"),
    ReportColumn(key="worksite_name", label="Worksite Name", type="string"),
    ReportColumn(key="contract_start_date", label="Contract Start", type="date"),
    ReportColumn(key="contract_end_date", label="Contract End", type="date"),
    ReportColumn(key="contract_budget", label="Contract Budget", type="money"),
    ReportColumn(key="actual_labour_cost", label="Actual Labour Cost", type="money"),
    ReportColumn(key="prorated_budget", label="Pro-rated Budget", type="money"),
    ReportColumn(key="variance_amount", label="Variance", type="money"),
    ReportColumn(key="variance_pct", label="Variance %", type="number"),
]


REPORTS_REGISTRY: dict[str, ReportSpec] = {
    "daily-attendance": ReportSpec(
        key="daily-attendance",
        name="Daily Attendance Report",
        description="Daily 5-point schedule comparison, variations, comments, and approvals.",
        category="Operational",
        allowed_roles=["ADMIN", "ENGINEER", "SUPERINTENDENT", "SUPERVISOR"],
        is_cost_report=False,
        columns=DAILY_ATTENDANCE_COLS,
        supported_formats=["xlsx", "csv", "pdf"],
        handler_module="fw.modules.reports.handlers.daily_attendance",
        filter_schema={"date_from": True, "date_to": True, "worksite_id": True, "supervisor_id": True, "country": True},
    ),
    "monthly-attendance": ReportSpec(
        key="monthly-attendance",
        name="Monthly Attendance Summary",
        description="Monthly employee attendance totals, shortfall, cumulative worked hours, and OT.",
        category="Operational",
        allowed_roles=["ADMIN", "ENGINEER", "SUPERINTENDENT", "SUPERVISOR"],
        is_cost_report=False,
        columns=MONTHLY_ATTENDANCE_COLS,
        supported_formats=["xlsx", "csv"],
        handler_module="fw.modules.reports.handlers.monthly_attendance",
        filter_schema={"year": True, "month": True, "country": True},
    ),
    "employee-movement": ReportSpec(
        key="employee-movement",
        name="Employee Movement Report",
        description="Chronological daily worker trail from accommodation to sites with gap tracking.",
        category="Operational",
        allowed_roles=["ADMIN", "ENGINEER", "SUPERINTENDENT", "SUPERVISOR"],
        is_cost_report=False,
        columns=EMPLOYEE_MOVEMENT_COLS,
        supported_formats=["xlsx", "csv"],
        handler_module="fw.modules.reports.handlers.employee_movement",
        filter_schema={"date_from": True, "date_to": True, "employee_id": True, "country": True},
    ),
    "site-visits": ReportSpec(
        key="site-visits",
        name="Site Visit Report",
        description="Worker visits at each worksite, arrival/departure, time spent, and completed flags.",
        category="Operational",
        allowed_roles=["ADMIN", "ENGINEER", "SUPERINTENDENT", "SUPERVISOR"],
        is_cost_report=False,
        columns=SITE_VISITS_COLS,
        supported_formats=["xlsx", "csv"],
        handler_module="fw.modules.reports.handlers.site_visits",
        filter_schema={"date_from": True, "date_to": True, "worksite_id": True, "employee_id": True, "country": True},
    ),
    "employee-utilization": ReportSpec(
        key="employee-utilization",
        name="Employee Utilization Report",
        description="Productive vs travel vs idle time breakdown per worker (DEC-28).",
        category="Operational",
        allowed_roles=["ADMIN", "ENGINEER", "SUPERINTENDENT", "SUPERVISOR"],
        is_cost_report=False,
        columns=EMPLOYEE_UTILIZATION_COLS,
        supported_formats=["xlsx", "csv"],
        handler_module="fw.modules.reports.handlers.employee_utilization",
        filter_schema={"year": True, "month": True, "country": True},
    ),
    "transportation-time": ReportSpec(
        key="transportation-time",
        name="Transportation Time Report",
        description="Time spent travelling between accommodation and worksites.",
        category="Operational",
        allowed_roles=["ADMIN", "ENGINEER", "SUPERINTENDENT", "SUPERVISOR"],
        is_cost_report=False,
        columns=TRANSPORTATION_TIME_COLS,
        supported_formats=["xlsx", "csv"],
        handler_module="fw.modules.reports.handlers.transportation_time",
        filter_schema={"date_from": True, "date_to": True, "country": True},
    ),
    "late-early-departure": ReportSpec(
        key="late-early-departure",
        name="Late Arrival / Early Departure Report",
        description="Schedule deviations exceeding grace limits (late arrival, early exit, shortfall).",
        category="Operational",
        allowed_roles=["ADMIN", "ENGINEER", "SUPERINTENDENT", "SUPERVISOR"],
        is_cost_report=False,
        columns=LATE_EARLY_DEPARTURE_COLS,
        supported_formats=["xlsx", "csv"],
        handler_module="fw.modules.reports.handlers.late_early_departure",
        filter_schema={"date_from": True, "date_to": True, "country": True},
    ),
    "project-attendance-summary": ReportSpec(
        key="project-attendance-summary",
        name="Project Attendance Summary",
        description="Planned vs deployed manpower, unique workers, and hours deployed per worksite.",
        category="Operational",
        allowed_roles=["ADMIN", "ENGINEER", "SUPERINTENDENT", "SUPERVISOR"],
        is_cost_report=False,
        columns=PROJECT_ATTENDANCE_SUMMARY_COLS,
        supported_formats=["xlsx", "csv"],
        handler_module="fw.modules.reports.handlers.project_attendance_summary",
        filter_schema={"date_from": True, "date_to": True, "worksite_id": True, "country": True},
    ),
    "pending-visits": ReportSpec(
        key="pending-visits",
        name="Pending Visits List",
        description="Follow-up list of unvisited site assignments with explanation workflow (DEC-32).",
        category="Operational",
        allowed_roles=["ADMIN", "ENGINEER", "SUPERINTENDENT", "SUPERVISOR"],
        is_cost_report=False,
        columns=PENDING_VISITS_COLS,
        supported_formats=["xlsx", "csv"],
        handler_module="fw.modules.reports.handlers.pending_visits",
        filter_schema={"date_from": True, "date_to": True, "worksite_id": True, "country": True},
    ),
    "staffing-gaps": ReportSpec(
        key="staffing-gaps",
        name="Staffing Gaps Report",
        description="Uncovered shifts due to leave, understaffed occurrences, or missing boundaries.",
        category="Operational",
        allowed_roles=["ADMIN", "ENGINEER", "SUPERINTENDENT", "SUPERVISOR"],
        is_cost_report=False,
        columns=STAFFING_GAPS_COLS,
        supported_formats=["xlsx", "csv"],
        handler_module="fw.modules.reports.handlers.staffing_gaps",
        filter_schema={"date_from": True, "date_to": True, "country": True},
    ),
    "document-expiry": ReportSpec(
        key="document-expiry",
        name="Document Expiry Report",
        description="Compliance tracking for expiring and expired identity and labour documents.",
        category="Compliance",
        allowed_roles=["ADMIN", "ENGINEER", "SUPERINTENDENT", "SUPERVISOR"],
        is_cost_report=False,
        columns=DOCUMENT_EXPIRY_COLS,
        supported_formats=["xlsx", "csv"],
        handler_module="fw.modules.reports.handlers.document_expiry",
        filter_schema={"days_ahead": True, "country": True},
    ),
    "weekly-roster": ReportSpec(
        key="weekly-roster",
        name="Weekly Roster Export",
        description="Weekly plan in the client's Mon-Sun grid format with planned sites and hours.",
        category="Operational",
        allowed_roles=["ADMIN", "ENGINEER", "SUPERINTENDENT", "SUPERVISOR"],
        is_cost_report=False,
        columns=WEEKLY_ROSTER_COLS,
        supported_formats=["xlsx", "csv"],
        handler_module="fw.modules.reports.handlers.weekly_roster",
        filter_schema={"date_from": True, "date_to": True, "country": True},
    ),
    "payroll": ReportSpec(
        key="payroll",
        name="Payroll Report",
        description="Official month-end payroll sheet with salary, allowances, overtime, and net pay.",
        category="Salary & Cost",
        allowed_roles=["ADMIN"],  # Cost report strictly Admin only
        is_cost_report=True,
        columns=PAYROLL_COLS,
        supported_formats=["xlsx", "csv", "pdf"],
        handler_module="fw.modules.reports.handlers.payroll",
        filter_schema={"year": True, "month": True, "payroll_run_id": True, "country": True},
    ),
    "provisions-staff-cost": ReportSpec(
        key="provisions-staff-cost",
        name="Provisions and Total Staff Cost",
        description="Employer cost breakdown: gratuity, leave salary, provisions, and 5% HR OH (DEC-39).",
        category="Salary & Cost",
        allowed_roles=["ADMIN"],  # Cost report strictly Admin only
        is_cost_report=True,
        columns=PROVISIONS_STAFF_COST_COLS,
        supported_formats=["xlsx", "csv"],
        handler_module="fw.modules.reports.handlers.provisions_staff_cost",
        filter_schema={"year": True, "month": True, "country": True},
    ),
    "job-costing": ReportSpec(
        key="job-costing",
        name="Job Costing Report",
        description="Contract budget vs actual labor cost allocated by worked minutes (DEC-29).",
        category="Salary & Cost",
        allowed_roles=["ADMIN"],  # Cost report strictly Admin only
        is_cost_report=True,
        columns=JOB_COSTING_COLS,
        supported_formats=["xlsx", "csv"],
        handler_module="fw.modules.reports.handlers.job_costing",
        filter_schema={"year": True, "month": True, "worksite_id": True, "country": True},
    ),
}

# The 11 reports auto-generated at month-end
MONTH_END_REPORT_KEYS: list[str] = [
    "payroll",
    "provisions-staff-cost",
    "job-costing",
    "daily-attendance",
    "monthly-attendance",
    "project-attendance-summary",
    "employee-utilization",
    "site-visits",
    "transportation-time",
    "late-early-departure",
    "employee-movement",
]


def get_report_definition(key: str) -> ReportDefinition:
    """Retrieve report definition by key."""
    if key not in REPORTS_REGISTRY:
        raise KeyError(f"Unknown report key: {key}")
    spec = REPORTS_REGISTRY[key]
    return ReportDefinition(
        key=spec.key,
        name=spec.name,
        description=spec.description,
        category=spec.category,
        allowed_roles=spec.allowed_roles,
        is_cost_report=spec.is_cost_report,
        columns=spec.columns,
        supported_formats=spec.supported_formats,
        filter_schema=spec.filter_schema,
    )


def list_reports_for_role(role: str) -> list[ReportDefinition]:
    """Return all report definitions accessible to the given user role."""
    result = []
    norm_role = role.upper()
    for spec in REPORTS_REGISTRY.values():
        if norm_role in [r.upper() for r in spec.allowed_roles]:
            result.append(
                ReportDefinition(
                    key=spec.key,
                    name=spec.name,
                    description=spec.description,
                    category=spec.category,
                    allowed_roles=spec.allowed_roles,
                    is_cost_report=spec.is_cost_report,
                    columns=spec.columns,
                    supported_formats=spec.supported_formats,
                    filter_schema=spec.filter_schema,
                )
            )
    return result


def can_access_report(key: str, role: str) -> bool:
    """Check if the given role is allowed to view this report."""
    if key not in REPORTS_REGISTRY:
        return False
    spec = REPORTS_REGISTRY[key]
    return role.upper() in [r.upper() for r in spec.allowed_roles]
