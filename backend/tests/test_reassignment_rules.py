"""Unit tests for pure reassignment business rules (Doc 04 Section 9, D2, BR-SC-04, DEC-43)."""

from datetime import date
from decimal import Decimal

from fw.rules.scheduling.reassignment import (
    ReassignmentStatus,
    check_late_approval,
    is_reassignment_expired,
    preview_reassignment_hours,
    validate_reassignment_notice,
)


def test_validate_reassignment_notice():
    today = date(2026, 11, 10)

    # 2 days ahead -> refused (< 3 days)
    ok, err = validate_reassignment_notice(date(2026, 11, 12), today, min_notice_days=3)
    assert not ok
    assert "requires at least 3 days notice" in (err or "")

    # 1 day ahead -> refused
    ok, err = validate_reassignment_notice(date(2026, 11, 11), today, min_notice_days=3)
    assert not ok

    # Same day -> refused
    ok, err = validate_reassignment_notice(date(2026, 11, 10), today, min_notice_days=3)
    assert not ok

    # Exactly 3 days ahead -> accepted
    ok, err = validate_reassignment_notice(date(2026, 11, 13), today, min_notice_days=3)
    assert ok
    assert err is None

    # 5 days ahead -> accepted
    ok, err = validate_reassignment_notice(date(2026, 11, 15), today, min_notice_days=3)
    assert ok


def test_check_late_approval():
    start_date = date(2026, 11, 15)

    # Decided on 2026-11-10 -> 5 days remaining -> NOT late
    assert not check_late_approval(start_date, date(2026, 11, 10), min_notice_days=3)

    # Decided on 2026-11-12 -> 3 days remaining -> NOT late
    assert not check_late_approval(start_date, date(2026, 11, 12), min_notice_days=3)

    # Decided on 2026-11-13 -> 2 days remaining -> LATE_APPROVAL!
    assert check_late_approval(start_date, date(2026, 11, 13), min_notice_days=3)

    # Decided on start_date itself -> LATE_APPROVAL!
    assert check_late_approval(start_date, start_date, min_notice_days=3)


def test_is_reassignment_expired():
    start_date = date(2026, 11, 15)

    # Current date before start -> not expired
    assert not is_reassignment_expired(start_date, date(2026, 11, 14), ReassignmentStatus.PENDING)

    # Current date after start -> expired!
    assert is_reassignment_expired(start_date, date(2026, 11, 16), ReassignmentStatus.PENDING)

    # If already approved, not expired
    assert not is_reassignment_expired(start_date, date(2026, 11, 16), ReassignmentStatus.APPROVED)


def test_preview_reassignment_hours():
    # Normal case: standard 8h, currently 0h, delta +8h -> resulting 8h, clean
    p = preview_reassignment_hours(
        employee_id="w1",
        work_date=date(2026, 11, 15),
        standard_hours=Decimal("8.0"),
        current_hours=Decimal("0.0"),
        proposed_delta=Decimal("8.0"),
        worker_grade_group="G2",
        job_item_grade_group="G2",
    )
    assert p.resulting_hours == Decimal("8.0")
    assert p.free_hours == Decimal("0.0")
    assert p.planned_overtime_hours == Decimal("0.0")
    assert len(p.warnings) == 0

    # Overtime case: currently 8h, delta +4h -> resulting 12h -> planned OT 4h
    p_ot = preview_reassignment_hours(
        employee_id="w1",
        work_date=date(2026, 11, 15),
        standard_hours=Decimal("8.0"),
        current_hours=Decimal("8.0"),
        proposed_delta=Decimal("4.0"),
        worker_grade_group="G2",
        job_item_grade_group="G2",
    )
    assert p_ot.resulting_hours == Decimal("12.0")
    assert p_ot.planned_overtime_hours == Decimal("4.0")
    assert "OVER_STANDARD_HOURS" in p_ot.warnings

    # Warnings for grade mismatch and leave
    p_warn = preview_reassignment_hours(
        employee_id="w1",
        work_date=date(2026, 11, 15),
        standard_hours=Decimal("8.0"),
        current_hours=Decimal("0.0"),
        proposed_delta=Decimal("8.0"),
        worker_grade_group="G1",
        job_item_grade_group="G2",
        is_on_approved_leave=True,
    )
    assert "GRADE_GROUP_MISMATCH" in p_warn.warnings
    assert "ON_APPROVED_LEAVE" in p_warn.warnings
