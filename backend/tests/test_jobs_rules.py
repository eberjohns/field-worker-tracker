"""Unit tests for jobs rules (BR-JB-*, 04-scheduling-engine sections 2-4)."""

from datetime import date
from decimal import Decimal

import pytest

from fw.rules.jobs.day_split import (
    calculate_days_per_occurrence,
    split_job_unit_days,
)
from fw.rules.jobs.format import (
    InvalidJobNumberError,
    is_job_outdoor,
    validate_job_number,
)
from fw.rules.jobs.frequency import (
    calculate_expected_activities_per_year,
    calculate_expected_annual_hours,
)
from fw.rules.jobs.occurrences import (
    generate_occurrence_slots,
    is_budget_only_staff_type,
)


def test_job_number_validation_success():
    assert validate_job_number("12A14301") == "12A14301"
    assert validate_job_number("32B14119") == "32B14119"
    assert validate_job_number("01C00001") == "01C00001"
    assert is_job_outdoor("12A14301") is True
    assert is_job_outdoor("32B14119") is False
    assert is_job_outdoor("01C00001") is False


def test_job_number_validation_rejections():
    # Hyphens or combined numbers (BR-JB-01, DEC-23)
    with pytest.raises(InvalidJobNumberError):
        validate_job_number("12A14301-02")
    with pytest.raises(InvalidJobNumberError):
        validate_job_number("12A14301/02")
    with pytest.raises(InvalidJobNumberError):
        validate_job_number("12A14301, 12B14302")
    # Invalid letter
    with pytest.raises(InvalidJobNumberError):
        validate_job_number("12D14301")
    # Wrong digits count
    with pytest.raises(InvalidJobNumberError):
        validate_job_number("1A14301")
    with pytest.raises(InvalidJobNumberError):
        validate_job_number("12A1430")


def test_frequency_activities_table():
    """Verify frequency table in 04 gives exact expected activities per year."""
    # Daily (6 days a week): WEEK, 6, 1 -> 312/yr
    assert calculate_expected_activities_per_year("WEEK", 6, 1) == Decimal("312.000")
    # One time / week: WEEK, 1, 1 -> 52
    assert calculate_expected_activities_per_year("WEEK", 1, 1) == Decimal("52.000")
    # One time / 2 weeks: WEEK, 1, 2 -> 26
    assert calculate_expected_activities_per_year("WEEK", 1, 2) == Decimal("26.000")
    # Three time / week: WEEK, 3, 1 -> 156
    assert calculate_expected_activities_per_year("WEEK", 3, 1) == Decimal("156.000")
    # Two time / month: MONTH, 2, 1 -> 24
    assert calculate_expected_activities_per_year("MONTH", 2, 1) == Decimal("24.000")
    # Monthly: MONTH, 1, 1 -> 12
    assert calculate_expected_activities_per_year("MONTH", 1, 1) == Decimal("12.000")
    # Quarterly: QUARTER, 1, 1 -> 4
    assert calculate_expected_activities_per_year("QUARTER", 1, 1) == Decimal("4.000")
    # Three time / year: YEAR, 3, 1 -> 3
    assert calculate_expected_activities_per_year("YEAR", 3, 1) == Decimal("3.000")


def test_expected_annual_hours():
    # Example: 312 activities * 3 staff * 9 hours = 8424 man-hours
    activities = calculate_expected_activities_per_year("WEEK", 6, 1)
    annual_hours = calculate_expected_annual_hours(
        activities, required_staff_count=3, hours_per_occurrence_per_staff=9
    )
    assert annual_hours == Decimal("8424.000")


def test_large_hours_split_into_9_hour_days():
    """Verify 42.688 h splits into 4 x 9.0 + 6.688 (5 days)."""
    chunks = split_job_unit_days(Decimal("42.688"), planned_workday_hours=Decimal("9.0"))
    assert len(chunks) == 5
    assert chunks == [
        Decimal("9.0"),
        Decimal("9.0"),
        Decimal("9.0"),
        Decimal("9.0"),
        Decimal("6.688"),
    ]
    assert calculate_days_per_occurrence(Decimal("42.688")) == 5

    # Exactly 18 hours -> [9.0, 9.0]
    assert split_job_unit_days(18) == [Decimal("9.0"), Decimal("9.0")]
    # 4 hours -> [4.0]
    assert split_job_unit_days(4) == [Decimal("4.0")]


def test_budget_only_staff_types_exclusion():
    """Verify budget-only staff types never generate occurrences."""
    budget_types = ["HSE Engineer", "Project Manager", "Irrigation Engineer"]
    assert is_budget_only_staff_type("HSE Engineer", budget_types) is True
    assert is_budget_only_staff_type("Gardener - Hand Watering", budget_types) is False

    slots = generate_occurrence_slots(
        frequency_unit="WEEK",
        occurrences_per_period=6,
        period_interval=1,
        required_staff_count=1,
        hours_per_occurrence_per_staff=9,
        horizon_start=date(2026, 1, 1),
        horizon_end=date(2026, 1, 31),
        item_start_date=date(2026, 1, 1),
        staff_grade_description="Project Manager",
        budget_only_types=budget_types,
    )
    assert len(slots) == 0


def test_occurrence_generation_week_with_weekday_pattern():
    slots = generate_occurrence_slots(
        frequency_unit="WEEK",
        occurrences_per_period=3,
        period_interval=1,
        required_staff_count=2,
        hours_per_occurrence_per_staff=9,
        horizon_start=date(2026, 1, 5),  # 2026-01-05 is Monday
        horizon_end=date(2026, 1, 11),  # Sunday
        item_start_date=date(2026, 1, 1),
        weekday_pattern=["MONDAY", "WEDNESDAY", "FRIDAY"],
        staff_grade_description="Gardener Helper",
        budget_only_types=[],
    )
    assert len(slots) == 3
    assert slots[0].due_date == date(2026, 1, 5)
    assert slots[1].due_date == date(2026, 1, 7)
    assert slots[2].due_date == date(2026, 1, 9)
    assert slots[0].required_staff_count == 2
    assert slots[0].required_hours_per_staff == Decimal("9")
