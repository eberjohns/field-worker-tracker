"""Unit tests for pure scheduling rules (Phase 05)."""

import io
from datetime import date
from decimal import Decimal

import openpyxl

from fw.rules.scheduling import (
    CandidateWorker,
    DayMarker,
    EmployeeValidationContext,
    ExcelRosterDayCell,
    ExcelRosterWorkerRow,
    ExistingAssignmentContext,
    JobItemValidationContext,
    TargetJobItem,
    ValidationCode,
    WorkerDayContext,
    build_roster_excel_bytes,
    calculate_allocation_summary,
    compute_effective_standard_hours,
    evaluate_worker_day_marker,
    extract_grade_group,
    generate_assignment_dates,
    rank_candidates_for_job,
    validate_assignment,
)


def test_extract_grade_group():
    assert extract_grade_group("G1C") == "G1"
    assert extract_grade_group("G2B") == "G2"
    assert extract_grade_group("g3") == "G3"
    assert extract_grade_group("G5A-2026") == "G5"
    assert extract_grade_group(None) is None


def test_generate_assignment_dates():
    # Mon Nov 2 to Sun Nov 8, 2026
    start = date(2026, 11, 2)
    end = date(2026, 11, 8)
    holidays = {date(2026, 11, 3)}  # Tuesday is a holiday

    slots = list(
        generate_assignment_dates(
            start_date=start,
            end_date=end,
            weekday_pattern=["MON", "TUE", "WED", "THU", "FRI", "SAT"],
            public_holidays=holidays,
            skip_public_holidays=True,
        )
    )

    assert len(slots) == 7
    # Mon is working
    assert slots[0].work_date == date(2026, 11, 2)
    assert slots[0].is_working_day is True
    # Tue is holiday and skipped
    assert slots[1].work_date == date(2026, 11, 3)
    assert slots[1].is_public_holiday is True
    assert slots[1].is_working_day is False
    # Sun is not in weekday pattern
    assert slots[6].work_date == date(2026, 11, 8)
    assert slots[6].is_working_day is False


def test_generate_assignment_dates_skips_worker_weekly_off_day():
    """Verify that a worker's weekly off day is not scheduled for work."""
    start = date(2026, 11, 2)  # Monday
    end = date(2026, 11, 8)    # Sunday

    slots = list(
        generate_assignment_dates(
            start_date=start,
            end_date=end,
            weekday_pattern=["MON", "TUE", "WED", "THU", "FRI", "SAT"],
            public_holidays=set(),
            skip_public_holidays=True,
            weekly_off_day="FRIDAY",
        )
    )

    # Friday is Nov 6
    fri_slot = slots[4]
    assert fri_slot.work_date == date(2026, 11, 6)
    assert fri_slot.weekday == "FRI"
    assert fri_slot.is_weekly_off is True
    assert fri_slot.is_working_day is False

    # Thursday is working
    thu_slot = slots[3]
    assert thu_slot.is_weekly_off is False
    assert thu_slot.is_working_day is True


def test_evaluate_worker_day_marker():
    # 1. Active assignments -> None (cells show chips)
    ctx1 = WorkerDayContext(
        employee_id="emp1",
        work_date=date(2026, 11, 2),
        weekly_off_day="SUNDAY",
        has_active_assignments=True,
        is_public_holiday=False,
    )
    assert evaluate_worker_day_marker(ctx1) is None

    # 2. Public holiday -> SKIPPED
    ctx2 = WorkerDayContext(
        employee_id="emp1",
        work_date=date(2026, 11, 3),
        weekly_off_day="SUNDAY",
        has_active_assignments=False,
        is_public_holiday=True,
    )
    assert evaluate_worker_day_marker(ctx2) == DayMarker.SKIPPED

    # 3. Weekly off -> WEEKLY_OFF
    ctx3 = WorkerDayContext(
        employee_id="emp1",
        work_date=date(2026, 11, 8),  # Sunday
        weekly_off_day="SUNDAY",
        has_active_assignments=False,
        is_public_holiday=False,
    )
    assert evaluate_worker_day_marker(ctx3) == DayMarker.WEEKLY_OFF

    # 4. On leave -> ON_LEAVE
    ctx4 = WorkerDayContext(
        employee_id="emp1",
        work_date=date(2026, 11, 4),
        weekly_off_day="SUNDAY",
        has_active_assignments=False,
        is_public_holiday=False,
        is_on_leave=True,
    )
    assert evaluate_worker_day_marker(ctx4) == DayMarker.ON_LEAVE

    # 5. Free available day -> FREE
    ctx5 = WorkerDayContext(
        employee_id="emp1",
        work_date=date(2026, 11, 4),
        weekly_off_day="SUNDAY",
        has_active_assignments=False,
        is_public_holiday=False,
        is_on_leave=False,
    )
    assert evaluate_worker_day_marker(ctx5) == DayMarker.FREE


def test_validation_permanent_exclusivity():
    emp = EmployeeValidationContext(
        employee_id="emp1",
        is_active=True,
        grade_code="G1C",
        staff_grade_description="Gardener",
        standard_hours=Decimal("8.0"),
    )
    perm_job = JobItemValidationContext(
        job_item_id="item-perm",
        worksite_id="site-1",
        is_active=True,
        worksite_is_active=True,
        deployment_type="PERMANENT",
        planned_grade_code="G1C",
        staff_grade_description="Gardener",
        has_boundary=True,
        start_date=date(2026, 1, 1),
    )
    remote_job = JobItemValidationContext(
        job_item_id="item-remote",
        worksite_id="site-2",
        is_active=True,
        worksite_is_active=True,
        deployment_type="REMOTE",
        planned_grade_code="G1C",
        staff_grade_description="Gardener",
        has_boundary=True,
        start_date=date(2026, 1, 1),
    )

    target_date = date(2026, 11, 4)
    today = date(2026, 11, 1)

    # If worker already has a REMOTE assignment
    existing_remote = [
        ExistingAssignmentContext(
            scheduled_work_id="sw1",
            job_item_id="item-remote",
            worksite_id="site-2",
            occurrence_id="occ1",
            deployment_type="REMOTE",
            assigned_hours=Decimal("4.0"),
            sequence=1,
        )
    ]

    # Trying to assign a PERMANENT job when already assigned to REMOTE -> Error PERMANENT_EXCLUSIVE
    report1 = validate_assignment(
        employee=emp,
        job_item=perm_job,
        target_date=target_date,
        assigned_hours=Decimal("8.0"),
        target_sequence=2,
        existing_assignments=existing_remote,
        today=today,
    )
    assert report1.is_valid is False
    assert any(e.code == ValidationCode.PERMANENT_EXCLUSIVE for e in report1.errors)

    # Trying to assign another REMOTE job when already assigned to REMOTE -> Valid!
    report2 = validate_assignment(
        employee=emp,
        job_item=remote_job,
        target_date=target_date,
        assigned_hours=Decimal("4.0"),
        target_sequence=2,
        existing_assignments=existing_remote,
        today=today,
    )
    assert report2.is_valid is True


def test_validation_hours_and_grade_group_warnings():
    emp = EmployeeValidationContext(
        employee_id="emp1",
        is_active=True,
        grade_code="G2B",  # Grade group G2
        staff_grade_description="Irrigation Technician",
        standard_hours=Decimal("8.0"),
    )
    # Job planned for G1 (Mismatch)
    job = JobItemValidationContext(
        job_item_id="item1",
        worksite_id="site1",
        is_active=True,
        worksite_is_active=True,
        deployment_type="REMOTE",
        planned_grade_code="G1C",
        staff_grade_description="Gardener",
        has_boundary=True,
        start_date=date(2026, 1, 1),
    )

    target_date = date(2026, 11, 4)
    today = date(2026, 11, 1)

    # Assigning 9.0h (standard is 8.0h -> 1h planned OT)
    report = validate_assignment(
        employee=emp,
        job_item=job,
        target_date=target_date,
        assigned_hours=Decimal("9.0"),
        target_sequence=1,
        existing_assignments=[],
        today=today,
    )

    # Still valid (warnings do not invalidate)
    assert report.is_valid is True
    # Grade group mismatch warning
    assert any(w.code == ValidationCode.GRADE_GROUP_MISMATCH for w in report.warnings)
    # Over standard hours warning
    assert any(w.code == ValidationCode.OVER_STANDARD_HOURS for w in report.warnings)


def test_validation_past_date():
    emp = EmployeeValidationContext(employee_id="emp1", is_active=True)
    job = JobItemValidationContext(
        job_item_id="item1",
        worksite_id="site1",
        is_active=True,
        worksite_is_active=True,
        deployment_type="REMOTE",
        planned_grade_code="G1C",
        staff_grade_description="Gardener",
        has_boundary=True,
        start_date=date(2026, 1, 1),
    )

    target_date = date(2026, 10, 1)  # past
    today = date(2026, 11, 1)

    # Non-admin -> past date is rejected
    report_user = validate_assignment(
        employee=emp,
        job_item=job,
        target_date=target_date,
        assigned_hours=Decimal("4.0"),
        target_sequence=1,
        existing_assignments=[],
        today=today,
        is_admin=False,
    )
    assert report_user.is_valid is False
    assert any(e.code == ValidationCode.PAST_DATE for e in report_user.errors)

    # Admin -> permitted
    report_admin = validate_assignment(
        employee=emp,
        job_item=job,
        target_date=target_date,
        assigned_hours=Decimal("4.0"),
        target_sequence=1,
        existing_assignments=[],
        today=today,
        is_admin=True,
    )
    assert not any(e.code == ValidationCode.PAST_DATE for e in report_admin.errors)


def test_suggestions_ranking():
    job = TargetJobItem(
        job_item_id="item1",
        worksite_id="site1",
        planned_grade_code="G1C",
        staff_grade_description="Hand Watering",
        deployment_type="PERMANENT",
        required_hours=Decimal("9.0"),
    )
    target_date = date(2026, 11, 4)

    # Candidate 1: Exact staff type match, same supervisor, worked at site recently
    c1 = CandidateWorker(
        employee_id="c1",
        name="Worker One",
        tally_id="T001",
        is_active=True,
        join_date=date(2025, 1, 1),
        employment_end_date=None,
        grade_code="G1B",
        staff_grade_description="Hand Watering",
        weekly_off_day="SUNDAY",
        standard_hours=Decimal("8.0"),
        is_on_leave=False,
        is_budget_only=False,
        worked_at_site_recently=True,
        shares_supervisor=True,
        weekly_allocated_hours=Decimal("18.0"),
        today_allocated_hours=Decimal("0.0"),
    )

    # Candidate 2: Same grade group (G1), different staff type
    c2 = CandidateWorker(
        employee_id="c2",
        name="Worker Two",
        tally_id="T002",
        is_active=True,
        join_date=date(2025, 1, 1),
        employment_end_date=None,
        grade_code="G1C",
        staff_grade_description="Gardener Helper",
        weekly_off_day="SUNDAY",
        standard_hours=Decimal("8.0"),
        is_on_leave=False,
        is_budget_only=False,
        worked_at_site_recently=False,
        shares_supervisor=False,
        weekly_allocated_hours=Decimal("10.0"),
        today_allocated_hours=Decimal("0.0"),
    )

    # Candidate 3: Ineligible grade group (G3)
    c3 = CandidateWorker(
        employee_id="c3",
        name="Worker Three",
        tally_id="T003",
        is_active=True,
        join_date=date(2025, 1, 1),
        employment_end_date=None,
        grade_code="G3A",
        staff_grade_description="Foreman",
        weekly_off_day="SUNDAY",
        standard_hours=Decimal("8.0"),
        is_on_leave=False,
        is_budget_only=False,
        worked_at_site_recently=True,
        shares_supervisor=True,
        weekly_allocated_hours=Decimal("0.0"),
        today_allocated_hours=Decimal("0.0"),
    )

    ranked = rank_candidates_for_job([c1, c2, c3], job, target_date)

    # c3 is excluded from eligible suggestions
    assert len(ranked) == 2
    # c1 is ranked first due to exact staff type match
    assert ranked[0].worker.employee_id == "c1"
    assert ranked[0].exact_staff_type_match is True
    # c2 is second
    assert ranked[1].worker.employee_id == "c2"
    assert ranked[1].exact_staff_type_match is False


def test_suggestions_ranking_prioritizes_role_over_same_crew():
    """Verify that an exact staff grade description match outranks same-crew non-matching roles."""
    job = TargetJobItem(
        job_item_id="item_gh",
        worksite_id="site1",
        planned_grade_code="G1C",
        staff_grade_description="Gardener Helper",
        deployment_type="PERMANENT",
        required_hours=Decimal("8.0"),
    )
    target_date = date(2026, 11, 4)

    # Worker In Same Crew but wrong role (Team Leader)
    crew_tl = CandidateWorker(
        employee_id="tl",
        name="Team Leader in Crew",
        tally_id="TL01",
        is_active=True,
        join_date=date(2025, 1, 1),
        employment_end_date=None,
        grade_code="G1C",
        staff_grade_description="Team Leader",
        weekly_off_day="SUNDAY",
        standard_hours=Decimal("8.0"),
        is_on_leave=False,
        is_budget_only=False,
        worked_at_site_recently=True,
        shares_supervisor=True,  # same crew!
        weekly_allocated_hours=Decimal("0.0"),
        today_allocated_hours=Decimal("0.0"),
    )

    # Worker in Different Crew but EXACT ROLE match (Gardener Helper)
    diff_crew_gh = CandidateWorker(
        employee_id="gh",
        name="Gardener Helper in Other Crew",
        tally_id="GH01",
        is_active=True,
        join_date=date(2025, 1, 1),
        employment_end_date=None,
        grade_code="G1C",
        staff_grade_description="Gardener Helper",  # exact match!
        weekly_off_day="SUNDAY",
        standard_hours=Decimal("8.0"),
        is_on_leave=False,
        is_budget_only=False,
        worked_at_site_recently=False,
        shares_supervisor=False,
        weekly_allocated_hours=Decimal("0.0"),
        today_allocated_hours=Decimal("0.0"),
    )

    ranked = rank_candidates_for_job([crew_tl, diff_crew_gh], job, target_date)
    assert len(ranked) == 2
    # Exact role match MUST be ranked #1
    assert ranked[0].worker.employee_id == "gh"
    assert ranked[0].exact_staff_type_match is True
    # Same crew wrong role is ranked #2
    assert ranked[1].worker.employee_id == "tl"
    assert ranked[1].exact_staff_type_match is False


def test_rank_candidates_with_blocked_worker():
    """Verify that blocked workers (e.g. PERMANENT conflicts) receive penalty and is_blocked flag."""
    target_date = date(2026, 11, 4)
    job = TargetJobItem(
        job_item_id="job_item_1",
        worksite_id="site_1",
        planned_grade_code="G1C",
        staff_grade_description="Gardener Helper",
        deployment_type="PERMANENT",
        required_hours=Decimal("8.0"),
    )

    # Worker A is available and matches
    w_avail = CandidateWorker(
        employee_id="w_avail",
        name="Available Worker",
        tally_id="W001",
        is_active=True,
        join_date=date(2025, 1, 1),
        employment_end_date=None,
        grade_code="G1C",
        staff_grade_description="Gardener Helper",
        weekly_off_day="SUNDAY",
        standard_hours=Decimal("8.0"),
        is_on_leave=False,
        is_budget_only=False,
        worked_at_site_recently=False,
        shares_supervisor=False,
        weekly_allocated_hours=Decimal("0.0"),
        today_allocated_hours=Decimal("0.0"),
        is_blocked=False,
        blocked_reason=None,
    )

    # Worker B matches SGD but is blocked by PERMANENT assignment
    w_blocked = CandidateWorker(
        employee_id="w_blocked",
        name="Blocked Worker",
        tally_id="W002",
        is_active=True,
        join_date=date(2025, 1, 1),
        employment_end_date=None,
        grade_code="G1C",
        staff_grade_description="Gardener Helper",
        weekly_off_day="SUNDAY",
        standard_hours=Decimal("8.0"),
        is_on_leave=False,
        is_budget_only=False,
        worked_at_site_recently=True,
        shares_supervisor=True,
        weekly_allocated_hours=Decimal("8.0"),
        today_allocated_hours=Decimal("8.0"),
        is_blocked=True,
        blocked_reason="Already assigned to PERMANENT job 12A10604",
    )

    ranked = rank_candidates_for_job([w_blocked, w_avail], job, target_date)
    assert len(ranked) == 2

    # Unblocked worker must rank #1
    assert ranked[0].worker.employee_id == "w_avail"
    assert ranked[0].is_blocked is False
    assert ranked[0].is_eligible is True

    # Blocked worker must rank #2, flagged is_blocked and not eligible
    assert ranked[1].worker.employee_id == "w_blocked"
    assert ranked[1].is_blocked is True
    assert ranked[1].blocked_reason == "Already assigned to PERMANENT job 12A10604"
    assert ranked[1].is_eligible is False
    assert any("Blocked:" in w for w in ranked[1].warnings)


def test_allocation_with_ramadan_adjustment():
    # Base standard 8.0h, Ramadan adjustment -120 min (-2.0h) -> 6.0h daily
    eff = compute_effective_standard_hours(
        base_standard_hours=Decimal("8.0"),
        adjustment_minutes=-120,
    )
    assert eff.effective_daily_standard_hours == Decimal("6.0")
    assert eff.effective_weekly_standard_hours == Decimal("36.0")

    summary = calculate_allocation_summary(
        today_allocated=Decimal("7.0"),
        week_allocated=Decimal("35.0"),
        month_allocated=Decimal("150.0"),
        effective_hours=eff,
    )
    # Today 7.0 vs standard 6.0 -> 1h over (planned OT)
    assert summary.today_is_over is True
    assert summary.today_diff == Decimal("1.0")
    # Week 35.0 vs standard 36.0 -> 1h under
    assert summary.week_is_under is True
    assert summary.week_diff == Decimal("-1.0")


def test_build_roster_excel_bytes():
    start = date(2026, 11, 2)
    daily_cells = [
        ExcelRosterDayCell(
            work_date=start,
            display_text="12A14301 A (9.0h)",
            hours=Decimal("9.0"),
            is_marker=False,
        ),
        ExcelRosterDayCell(
            work_date=date(2026, 11, 3),
            display_text="SKIPPED",
            hours=Decimal("0.0"),
            is_marker=True,
        ),
        ExcelRosterDayCell(
            work_date=date(2026, 11, 4),
            display_text="12A14301 A (9.0h)",
            hours=Decimal("9.0"),
            is_marker=False,
        ),
        ExcelRosterDayCell(
            work_date=date(2026, 11, 5),
            display_text="12A14301 A (9.0h)",
            hours=Decimal("9.0"),
            is_marker=False,
        ),
        ExcelRosterDayCell(
            work_date=date(2026, 11, 6),
            display_text="12A14301 A (9.0h)",
            hours=Decimal("9.0"),
            is_marker=False,
        ),
        ExcelRosterDayCell(
            work_date=date(2026, 11, 7),
            display_text="12A14301 A (9.0h)",
            hours=Decimal("9.0"),
            is_marker=False,
        ),
        ExcelRosterDayCell(
            work_date=date(2026, 11, 8),
            display_text="WEEKLY-OFF",
            hours=Decimal("0.0"),
            is_marker=True,
        ),
    ]

    row = ExcelRosterWorkerRow(
        employee_name="Shanto Miah",
        tally_id="E00123",
        grade_code="G2B",
        staff_grade_description="Gardener",
        standard_hours=Decimal("8.0"),
        daily_cells=daily_cells,
        total_allocated_hours=Decimal("45.0"),
        total_standard_hours=Decimal("48.0"),
        remarks="Deira Bus",
    )

    excel_bytes = build_roster_excel_bytes(week_start=start, worker_rows=[row])
    assert len(excel_bytes) > 0

    # Verify workbook can be read by openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
    ws = wb.active
    assert ws is not None
    assert ws.title == "Weekly Roster"
    assert ws["A1"].value.startswith("Weekly Roster")
    # Check header
    assert ws["A3"].value == "Worker Name"
    # Check worker row
    assert ws["A4"].value == "Shanto Miah"
    assert ws["B4"].value == "E00123"
    assert ws["F4"].value == "12A14301 A (9.0h)"
    assert ws["G4"].value == "SKIPPED"
    assert ws["L4"].value == "WEEKLY-OFF"
    assert ws["M4"].value == "45.0 / 48.0"
    assert ws["N4"].value == "Deira Bus"
