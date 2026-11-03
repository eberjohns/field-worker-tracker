"""Public interface for jobs domain rules (BR-JB-*)."""

from fw.rules.jobs.day_split import (
    DEFAULT_PLANNED_WORKDAY_HOURS,
    calculate_days_per_occurrence,
    split_job_unit_days,
)
from fw.rules.jobs.format import (
    JOB_NUMBER_REGEX,
    InvalidJobNumberError,
    is_job_outdoor,
    validate_job_number,
)
from fw.rules.jobs.frequency import (
    PERIODS_PER_YEAR,
    InvalidFrequencyError,
    calculate_expected_activities_per_year,
    calculate_expected_annual_hours,
)
from fw.rules.jobs.occurrences import (
    OccurrenceSlot,
    generate_occurrence_slots,
    is_budget_only_staff_type,
)

__all__ = [
    "DEFAULT_PLANNED_WORKDAY_HOURS",
    "InvalidFrequencyError",
    "InvalidJobNumberError",
    "JOB_NUMBER_REGEX",
    "OccurrenceSlot",
    "PERIODS_PER_YEAR",
    "calculate_days_per_occurrence",
    "calculate_expected_activities_per_year",
    "calculate_expected_annual_hours",
    "generate_occurrence_slots",
    "is_budget_only_staff_type",
    "is_job_outdoor",
    "split_job_unit_days",
    "validate_job_number",
]

