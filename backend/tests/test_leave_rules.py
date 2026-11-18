"""Unit tests for pure leave business rules (Doc 04 Section 9, D2, BR-SC-05, DEC-46)."""

import uuid
from datetime import date

from fw.rules.scheduling.leave import (
    LeaveRecord,
    LeaveStatus,
    LeaveType,
    calculate_leave_taken,
    check_overlapping_leaves,
    validate_leave_dates,
)


def test_validate_leave_dates_bounds():
    today = date(2026, 11, 10)
    # End date before start date
    ok, err = validate_leave_dates(date(2026, 11, 20), date(2026, 11, 15), today, is_admin=False)
    assert not ok
    assert "cannot be before start date" in (err or "")


def test_validate_leave_dates_notice_non_admin():
    today = date(2026, 11, 10)
    # Notice < 3 days (e.g. starting in 2 days)
    ok, err = validate_leave_dates(date(2026, 11, 12), date(2026, 11, 15), today, is_admin=False)
    assert not ok
    assert "requires at least 3 days notice" in (err or "")

    # Notice == 3 days
    ok, err = validate_leave_dates(date(2026, 11, 13), date(2026, 11, 15), today, is_admin=False)
    assert ok
    assert err is None


def test_validate_leave_dates_admin_past_allowed():
    today = date(2026, 11, 10)
    # Admin recording short-notice or past leave without bypass is rejected
    ok, err = validate_leave_dates(
        date(2026, 11, 1), date(2026, 11, 5), today, is_admin=True, bypass_notice=False
    )
    assert not ok
    assert err is not None and "at least 3 days notice" in err

    # Admin recording with explicit bypass confirmed is allowed
    ok_bypass, err_bypass = validate_leave_dates(
        date(2026, 11, 1), date(2026, 11, 5), today, is_admin=True, bypass_notice=True
    )
    assert ok_bypass
    assert err_bypass is None


def test_validate_leave_dates_urgent_types_exempt_from_notice():
    today = date(2026, 11, 10)
    # Same-day EMERGENCY and SICK allowed for non-admin without bypass
    for urgent_type in ("EMERGENCY", "SICK"):
        ok, err = validate_leave_dates(
            date(2026, 11, 10),
            date(2026, 11, 11),
            today,
            is_admin=False,
            leave_type=urgent_type,
        )
        assert ok is True
        assert err is None

        # End date before start date still rejected even for urgent types
        ok_bad, err_bad = validate_leave_dates(
            date(2026, 11, 12),
            date(2026, 11, 10),
            today,
            is_admin=False,
            leave_type=urgent_type,
        )
        assert ok_bad is False
        assert err_bad is not None and "before start date" in err_bad

    # Non-urgent types still enforce 3-day notice
    for regular_type in ("ANNUAL", "UNPAID", "OTHER"):
        ok, err = validate_leave_dates(
            date(2026, 11, 11),
            date(2026, 11, 12),
            today,
            is_admin=False,
            leave_type=regular_type,
        )
        assert ok is False
        assert err is not None and "at least 3 days notice" in err


def test_check_overlapping_leaves():
    emp_id = uuid.uuid4()
    other_emp_id = uuid.uuid4()

    existing = [
        LeaveRecord(
            id=uuid.uuid4(),
            employee_id=emp_id,
            leave_type=LeaveType.ANNUAL,
            from_date=date(2026, 11, 15),
            to_date=date(2026, 11, 20),
            status=LeaveStatus.APPROVED,
        ),
        LeaveRecord(
            id=uuid.uuid4(),
            employee_id=emp_id,
            leave_type=LeaveType.SICK,
            from_date=date(2026, 10, 1),
            to_date=date(2026, 10, 5),
            status=LeaveStatus.CANCELLED,
        ),
        LeaveRecord(
            id=uuid.uuid4(),
            employee_id=other_emp_id,
            leave_type=LeaveType.ANNUAL,
            from_date=date(2026, 11, 15),
            to_date=date(2026, 11, 20),
            status=LeaveStatus.APPROVED,
        ),
    ]

    # Overlaps with approved leave of same employee
    ok, err = check_overlapping_leaves(emp_id, date(2026, 11, 18), date(2026, 11, 25), existing)
    assert not ok
    assert "overlaps with existing APPROVED leave" in (err or "")

    # Overlaps with cancelled leave -> allowed!
    ok, err = check_overlapping_leaves(emp_id, date(2026, 10, 2), date(2026, 10, 4), existing)
    assert ok

    # Completely different dates -> allowed!
    ok, err = check_overlapping_leaves(emp_id, date(2026, 11, 21), date(2026, 11, 25), existing)
    assert ok


def test_calculate_leave_taken_working_vs_calendar():
    emp_id = uuid.uuid4()
    # 2026-11-16 (Monday) to 2026-11-22 (Sunday) = 7 calendar days
    # Sunday is weekly-off day -> 6 working days
    # Suppose 2026-11-18 (Wednesday) is a public holiday -> 5 working days
    approved = [
        LeaveRecord(
            id=uuid.uuid4(),
            employee_id=emp_id,
            leave_type="ANNUAL",
            from_date=date(2026, 11, 16),
            to_date=date(2026, 11, 22),
            status=LeaveStatus.APPROVED,
        ),
        LeaveRecord(
            id=uuid.uuid4(),
            employee_id=emp_id,
            leave_type="SICK",
            from_date=date(2026, 12, 1),
            to_date=date(2026, 12, 2),
            status=LeaveStatus.APPROVED,
        ),
    ]

    holidays = {date(2026, 11, 18)}
    summary = calculate_leave_taken(
        approved_leaves=approved,
        year=2026,
        weekly_off_day="SUNDAY",
        public_holidays=holidays,
    )

    annual = summary["ANNUAL"]
    assert annual["calendar_days"] == 7
    assert annual["working_days"] == 5  # 7 - 1 off (Sun) - 1 holiday (Wed)

    sick = summary["SICK"]
    assert sick["calendar_days"] == 2
    assert sick["working_days"] == 2
