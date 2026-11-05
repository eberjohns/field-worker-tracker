"""Pure business logic for assignment validation and warnings (Doc 04 Section 7)."""

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum

from fw.rules.scheduling.assignment import INT_TO_WEEKDAY
from fw.rules.scheduling.markers import normalize_day_name

GRADE_GROUP_PATTERN = re.compile(r"^(G\d+)", re.IGNORECASE)


def extract_grade_group(grade_code: str | None) -> str | None:
    """Extract grade group prefix (e.g. 'G1C' -> 'G1', 'G2' -> 'G2')."""
    if not grade_code:
        return None
    cleaned = grade_code.strip().upper()
    match = GRADE_GROUP_PATTERN.match(cleaned)
    if match:
        return match.group(1).upper()
    return cleaned


class IssueSeverity(StrEnum):
    """Validation issue severity."""

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class ValidationCode(StrEnum):
    """Standard error and warning codes from Doc 04 Section 7."""

    DUPLICATE_ASSIGNMENT = "DUPLICATE_ASSIGNMENT"
    EMPLOYEE_INACTIVE = "EMPLOYEE_INACTIVE"
    JOB_INACTIVE = "JOB_INACTIVE"
    OUTSIDE_JOB_DATES = "OUTSIDE_JOB_DATES"
    BUDGET_ONLY_NOT_SCHEDULABLE = "BUDGET_ONLY_NOT_SCHEDULABLE"
    ON_APPROVED_LEAVE = "ON_APPROVED_LEAVE"
    PERMANENT_EXCLUSIVE = "PERMANENT_EXCLUSIVE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    SEQUENCE_CONFLICT = "SEQUENCE_CONFLICT"
    PAST_DATE = "PAST_DATE"

    WEEKLY_OFF = "WEEKLY_OFF"
    OVER_STANDARD_HOURS = "OVER_STANDARD_HOURS"
    UNDER_STANDARD_HOURS = "UNDER_STANDARD_HOURS"
    GRADE_GROUP_MISMATCH = "GRADE_GROUP_MISMATCH"
    PUBLIC_HOLIDAY = "PUBLIC_HOLIDAY"
    NO_BOUNDARY = "NO_BOUNDARY"


@dataclass(frozen=True)
class ValidationIssue:
    """A validation issue with severity, stable code, and descriptive message."""

    code: ValidationCode
    severity: IssueSeverity
    message: str


@dataclass
class ValidationReport:
    """Result of running assignment validation."""

    is_valid: bool = True
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.WARNING]

    @property
    def infos(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.INFO]


@dataclass(frozen=True)
class EmployeeValidationContext:
    """Employee data relevant to assignment validation."""

    employee_id: str
    is_active: bool
    join_date: date | None = None
    employment_end_date: date | None = None
    weekly_off_day: str | None = None
    grade_code: str | None = None
    staff_grade_description: str | None = None
    standard_hours: Decimal = Decimal("8.0")


@dataclass(frozen=True)
class JobItemValidationContext:
    """Job item and worksite data relevant to assignment validation."""

    job_item_id: str
    worksite_id: str
    is_active: bool
    worksite_is_active: bool
    deployment_type: str  # PERMANENT or REMOTE
    planned_grade_code: str
    staff_grade_description: str
    has_boundary: bool
    start_date: date
    end_date: date | None = None
    is_budget_only: bool = False


@dataclass(frozen=True)
class ExistingAssignmentContext:
    """Existing scheduled work for the employee on the target date."""

    scheduled_work_id: str
    job_item_id: str
    worksite_id: str
    occurrence_id: str | None
    deployment_type: str  # PERMANENT or REMOTE
    assigned_hours: Decimal
    sequence: int


def validate_assignment(
    employee: EmployeeValidationContext,
    job_item: JobItemValidationContext,
    target_date: date,
    assigned_hours: Decimal,
    target_sequence: int,
    existing_assignments: list[ExistingAssignmentContext],
    today: date,
    is_admin: bool = False,
    is_public_holiday: bool = False,
    is_on_leave: bool = False,
    target_occurrence_id: str | None = None,
    exclude_scheduled_work_id: str | None = None,
) -> ValidationReport:
    """Run all validation rules from Doc 04 Section 7 against a proposed assignment."""
    report = ValidationReport()

    def add_issue(code: ValidationCode, severity: IssueSeverity, message: str) -> None:
        report.issues.append(ValidationIssue(code=code, severity=severity, message=message))
        if severity == IssueSeverity.ERROR:
            report.is_valid = False

    # 1. Past date check (Admin allowed, non-Admin rejected)
    if target_date < today and not is_admin:
        add_issue(
            ValidationCode.PAST_DATE,
            IssueSeverity.ERROR,
            f"Cannot create or change assignments on past date {target_date.isoformat()}.",
        )

    # 2. Employee active and employment dates
    if not employee.is_active:
        add_issue(
            ValidationCode.EMPLOYEE_INACTIVE,
            IssueSeverity.ERROR,
            f"Employee {employee.employee_id} is inactive.",
        )
    if employee.join_date and target_date < employee.join_date:
        add_issue(
            ValidationCode.EMPLOYEE_INACTIVE,
            IssueSeverity.ERROR,
            f"Date {target_date.isoformat()} is before employee join date {employee.join_date.isoformat()}.",
        )
    if employee.employment_end_date and target_date > employee.employment_end_date:
        add_issue(
            ValidationCode.EMPLOYEE_INACTIVE,
            IssueSeverity.ERROR,
            f"Date {target_date.isoformat()} is after employee end date {employee.employment_end_date.isoformat()}.",
        )

    # 3. Job and worksite active
    if not job_item.is_active or not job_item.worksite_is_active:
        add_issue(
            ValidationCode.JOB_INACTIVE,
            IssueSeverity.ERROR,
            "Job item or parent worksite is inactive.",
        )

    # 4. Outside job item dates
    if target_date < job_item.start_date:
        add_issue(
            ValidationCode.OUTSIDE_JOB_DATES,
            IssueSeverity.ERROR,
            f"Date {target_date.isoformat()} is before job item start date {job_item.start_date.isoformat()}.",
        )
    if job_item.end_date and target_date > job_item.end_date:
        add_issue(
            ValidationCode.OUTSIDE_JOB_DATES,
            IssueSeverity.ERROR,
            f"Date {target_date.isoformat()} is after job item end date {job_item.end_date.isoformat()}.",
        )

    # 5. Budget only staff types
    if job_item.is_budget_only:
        add_issue(
            ValidationCode.BUDGET_ONLY_NOT_SCHEDULABLE,
            IssueSeverity.ERROR,
            f"Staff type '{job_item.staff_grade_description}' is configured as budget-only and cannot be scheduled.",
        )

    # 6. Approved leave
    if is_on_leave:
        add_issue(
            ValidationCode.ON_APPROVED_LEAVE,
            IssueSeverity.ERROR,
            f"Employee {employee.employee_id} is on approved leave on {target_date.isoformat()}.",
        )

    # Filter out assignment being updated
    active_existing = [
        a for a in existing_assignments if a.scheduled_work_id != exclude_scheduled_work_id
    ]

    # 7. Duplicate assignment check
    if target_occurrence_id:
        for a in active_existing:
            if a.occurrence_id == target_occurrence_id:
                add_issue(
                    ValidationCode.DUPLICATE_ASSIGNMENT,
                    IssueSeverity.ERROR,
                    f"Employee is already assigned to occurrence {target_occurrence_id} on {target_date.isoformat()}.",
                )
                break

    # 8. PERMANENT exclusivity (DEC-36)
    is_target_permanent = job_item.deployment_type.upper() == "PERMANENT"
    has_existing_permanent = any(a.deployment_type.upper() == "PERMANENT" for a in active_existing)

    if is_target_permanent and len(active_existing) > 0:
        add_issue(
            ValidationCode.PERMANENT_EXCLUSIVE,
            IssueSeverity.ERROR,
            "A PERMANENT job cannot share a work day with another assignment.",
        )
    elif not is_target_permanent and has_existing_permanent:
        add_issue(
            ValidationCode.PERMANENT_EXCLUSIVE,
            IssueSeverity.ERROR,
            "Worker already has a PERMANENT job assignment on this date.",
        )

    # 9. Sequence conflict
    existing_sequences = {a.sequence for a in active_existing}
    if target_sequence in existing_sequences:
        add_issue(
            ValidationCode.SEQUENCE_CONFLICT,
            IssueSeverity.ERROR,
            f"Sequence number {target_sequence} conflicts with another assignment on this date.",
        )

    # --- WARNINGS & INFOS ---

    # 10. Weekly off warning
    weekday_str = INT_TO_WEEKDAY[target_date.weekday()]
    worker_off = normalize_day_name(employee.weekly_off_day)
    if worker_off and weekday_str == worker_off:
        add_issue(
            ValidationCode.WEEKLY_OFF,
            IssueSeverity.WARNING,
            f"Assigning on worker's weekly off day ({weekday_str}).",
        )

    # 11. Public holiday warning
    if is_public_holiday:
        add_issue(
            ValidationCode.PUBLIC_HOLIDAY,
            IssueSeverity.WARNING,
            f"Assigning on a public holiday ({target_date.isoformat()}).",
        )

    # 12. Grade group mismatch warning (DEC-52)
    emp_group = extract_grade_group(employee.grade_code)
    job_group = extract_grade_group(job_item.planned_grade_code)
    if emp_group and job_group and emp_group != job_group:
        add_issue(
            ValidationCode.GRADE_GROUP_MISMATCH,
            IssueSeverity.WARNING,
            f"Worker grade group ({emp_group}) differs from planned grade group ({job_group}).",
        )

    # 13. Site boundary warning
    if not job_item.has_boundary:
        add_issue(
            ValidationCode.NO_BOUNDARY,
            IssueSeverity.WARNING,
            "The worksite does not have a boundary polygon defined.",
        )

    # 14. Standard hours checks (over = warning, under = info)
    total_day_hours = sum((a.assigned_hours for a in active_existing), Decimal("0")) + assigned_hours
    if total_day_hours > employee.standard_hours:
        diff = total_day_hours - employee.standard_hours
        add_issue(
            ValidationCode.OVER_STANDARD_HOURS,
            IssueSeverity.WARNING,
            f"Allocated {total_day_hours}h exceeds standard {employee.standard_hours}h by {diff}h (planned overtime).",
        )
    elif total_day_hours < employee.standard_hours:
        diff = employee.standard_hours - total_day_hours
        add_issue(
            ValidationCode.UNDER_STANDARD_HOURS,
            IssueSeverity.INFO,
            f"Allocated {total_day_hours}h is below standard {employee.standard_hours}h ({diff}h free).",
        )

    return report
