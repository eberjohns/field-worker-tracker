from datetime import UTC, date, datetime, time
from decimal import Decimal
from uuid import uuid4

from fw.rules.attendance import (
    ConstructedGap,
    ConstructedVisit,
    DailyCalculationInputs,
    EventForVisit,
    ScheduledAssignment,
    build_visits_for_day,
    compute_daily_attendance,
)
from fw.rules.time_rules import ResolvedTimeSchedule


def make_dummy_schedule(
    acc_start: time = time(5, 0),
    first_site: time = time(6, 0),
    break_m: int = 30,
    last_site: time = time(15, 30),
    acc_end: time = time(17, 0),
    planned_total: int = 720,
    planned_worked: int = 540,
    std_change_m: int = 0,
) -> ResolvedTimeSchedule:
    return ResolvedTimeSchedule(
        accommodation_start=acc_start,
        first_site_start=first_site,
        break_minutes=break_m,
        last_site_end=last_site,
        accommodation_end=acc_end,
        planned_total_minutes=planned_total,
        planned_worked_minutes=planned_worked,
        standard_hours_change_minutes=std_change_m,
        has_accommodation=True,
        winning_rule_id=None,
        winning_rule_name="Default Company Rule",
    )


def test_scenario_a_regular_day():
    """A - regular day:

    Assigned 3 + 2 + 3 = 8 h (480 min). Standard hours 8 (480 min).
    First entry 06:20, last exit 15:20, break 30.
    Elapsed 540, worked 510, variation vs required +30.
    Not an OT2 day, so OT1 = 510 - 480 = 30 min.
    Row goes to review because of overtime.
    """
    emp_id = uuid4()
    site1 = uuid4()
    work_date = date(2026, 11, 3)

    visits = [
        ConstructedVisit(
            work_date=work_date,
            place_type="SITE",
            worksite_id=site1,
            accommodation_id=None,
            entry_event_id=uuid4(),
            exit_event_id=uuid4(),
            entry_at=datetime(2026, 11, 3, 6, 20, tzinfo=UTC),
            exit_at=datetime(2026, 11, 3, 15, 20, tzinfo=UTC),
            exit_inferred=False,
            last_inside_at=datetime(2026, 11, 3, 15, 20, tzinfo=UTC),
            counts_as_completed=True,
            duration_minutes=540,
        )
    ]

    assignments = [
        ScheduledAssignment(scheduled_work_id=uuid4(), worksite_id=site1, assigned_hours=3.0),
        ScheduledAssignment(scheduled_work_id=uuid4(), worksite_id=site1, assigned_hours=2.0),
        ScheduledAssignment(scheduled_work_id=uuid4(), worksite_id=site1, assigned_hours=3.0),
    ]

    calc = compute_daily_attendance(
        DailyCalculationInputs(
            employee_id=emp_id,
            tally_id="1017",
            work_date=work_date,
            is_driver=False,
            has_accommodation=True,
            standard_hours=8.0,
            schedule=make_dummy_schedule(),
            assignments=assignments,
            visits=visits,
            gaps=[],
            is_public_holiday=False,
            is_weekly_off=False,
            is_ot2_weekday=False,
            has_approved_leave=False,
        )
    )

    assert calc.elapsed_site_minutes == 540
    assert calc.worked_minutes == 510
    assert calc.required_minutes == 480
    assert calc.variation_minutes == 30
    assert calc.ot1_minutes == 30
    assert calc.ot2_minutes == 0
    assert calc.review_status == "PENDING_REVIEW"
    assert "Overtime" in calc.review_reasons


def test_scenario_b_grace_period():
    """B - grace:

    Required 480, worked 475: shortfall 5 <= 10 -> grace_applied=true, satisfied; variation stays -5.
    """
    emp_id = uuid4()
    site1 = uuid4()
    work_date = date(2026, 11, 3)

    visits = [
        ConstructedVisit(
            work_date=work_date,
            place_type="SITE",
            worksite_id=site1,
            accommodation_id=None,
            entry_event_id=uuid4(),
            exit_event_id=uuid4(),
            entry_at=datetime(2026, 11, 3, 6, 0, tzinfo=UTC),
            exit_at=datetime(2026, 11, 3, 14, 25, tzinfo=UTC),  # 8h 25m = 505m - 30m break = 475m
            exit_inferred=False,
            last_inside_at=datetime(2026, 11, 3, 14, 25, tzinfo=UTC),
            counts_as_completed=True,
            duration_minutes=505,
        )
    ]

    assignments = [
        ScheduledAssignment(scheduled_work_id=uuid4(), worksite_id=site1, assigned_hours=8.0),
    ]

    calc = compute_daily_attendance(
        DailyCalculationInputs(
            employee_id=emp_id,
            tally_id="1017",
            work_date=work_date,
            is_driver=False,
            has_accommodation=True,
            standard_hours=8.0,
            schedule=make_dummy_schedule(),
            assignments=assignments,
            visits=visits,
            gaps=[],
            is_public_holiday=False,
            is_weekly_off=False,
            is_ot2_weekday=False,
            has_approved_leave=False,
            grace_period_minutes=10,
        )
    )

    assert calc.worked_minutes == 475
    assert calc.required_minutes == 480
    assert calc.variation_minutes == -5
    assert calc.shortfall_minutes == 5
    assert calc.grace_applied is True
    assert calc.satisfied is True
    assert "SHORTFALL_BEYOND_GRACE" not in calc.flags
    assert calc.review_status == "AUTO"


def test_scenario_c_missing_exit():
    """C - missing exit:

    ENTRY 06:30, last inside PING 14:55, no EXIT.
    Visit closed 14:55 INFERRED, flag MISSING_EXIT -> PENDING_REVIEW.
    """
    site1 = uuid4()
    work_date = date(2026, 11, 3)

    events = [
        EventForVisit(
            event_id=uuid4(),
            event_type="ENTRY",
            event_timestamp_utc=datetime(2026, 11, 3, 6, 30, tzinfo=UTC),
            sequence_number=1,
            server_received_at=datetime(2026, 11, 3, 6, 30, tzinfo=UTC),
            server_verdict="INSIDE",
            server_site_id=site1,
            server_accommodation_id=None,
        ),
        EventForVisit(
            event_id=uuid4(),
            event_type="PING",
            event_timestamp_utc=datetime(2026, 11, 3, 14, 55, tzinfo=UTC),
            sequence_number=2,
            server_received_at=datetime(2026, 11, 3, 14, 55, tzinfo=UTC),
            server_verdict="INSIDE",
            server_site_id=site1,
            server_accommodation_id=None,
        ),
    ]

    visits = build_visits_for_day(events, work_date, assigned_worksite_ids={site1})
    assert len(visits) == 1
    v = visits[0]
    assert v.exit_inferred is True
    assert v.exit_at == datetime(2026, 11, 3, 14, 55, tzinfo=UTC)
    assert "MISSING_EXIT" in v.flags

    calc = compute_daily_attendance(
        DailyCalculationInputs(
            employee_id=uuid4(),
            tally_id="1017",
            work_date=work_date,
            is_driver=False,
            has_accommodation=True,
            standard_hours=8.0,
            schedule=make_dummy_schedule(),
            assignments=[
                ScheduledAssignment(
                    scheduled_work_id=uuid4(), worksite_id=site1, assigned_hours=8.0
                )
            ],
            visits=visits,
            gaps=[],
            is_public_holiday=False,
            is_weekly_off=False,
            is_ot2_weekday=False,
            has_approved_leave=False,
        )
    )

    assert "MISSING_EXIT" in calc.flags
    assert calc.review_status == "PENDING_REVIEW"
    assert "Estimated exit" in calc.review_reasons


def test_scenario_d_tracking_gap():
    """D - tracking gap:

    DISABLED 10:05 (captured 10:03), ENABLED 11:40. Gap 95 min; break used 30
    -> unaccounted 65 min > 15 -> flag TRACKING_GAP; PENDING_REVIEW; worked time unchanged.
    """
    site1 = uuid4()
    work_date = date(2026, 11, 3)

    visits = [
        ConstructedVisit(
            work_date=work_date,
            place_type="SITE",
            worksite_id=site1,
            accommodation_id=None,
            entry_event_id=uuid4(),
            exit_event_id=uuid4(),
            entry_at=datetime(2026, 11, 3, 6, 0, tzinfo=UTC),
            exit_at=datetime(2026, 11, 3, 14, 30, tzinfo=UTC),  # 8.5 h elapsed
            exit_inferred=False,
            last_inside_at=datetime(2026, 11, 3, 14, 30, tzinfo=UTC),
            counts_as_completed=True,
            duration_minutes=510,
        )
    ]

    gaps = [
        ConstructedGap(
            work_date=work_date,
            disabled_event_id=uuid4(),
            enabled_event_id=uuid4(),
            started_at=datetime(2026, 11, 3, 10, 5, tzinfo=UTC),
            ended_at=datetime(2026, 11, 3, 11, 40, tzinfo=UTC),
            duration_minutes=95,
            disabled_latitude=Decimal("25.1"),
            disabled_longitude=Decimal("55.2"),
            disabled_location_captured_at=datetime(2026, 11, 3, 10, 3, tzinfo=UTC),
            resumed_latitude=Decimal("25.1"),
            resumed_longitude=Decimal("55.2"),
            distance_between_m=0.0,
            start_inside_site_id=site1,
            end_inside_site_id=site1,
            is_inferred=False,
        )
    ]

    calc = compute_daily_attendance(
        DailyCalculationInputs(
            employee_id=uuid4(),
            tally_id="1017",
            work_date=work_date,
            is_driver=False,
            has_accommodation=True,
            standard_hours=8.0,
            schedule=make_dummy_schedule(),
            assignments=[
                ScheduledAssignment(
                    scheduled_work_id=uuid4(), worksite_id=site1, assigned_hours=8.0
                )
            ],
            visits=visits,
            gaps=gaps,
            is_public_holiday=False,
            is_weekly_off=False,
            is_ot2_weekday=False,
            has_approved_leave=False,
            gap_flag_minutes=15,
        )
    )

    # 510 elapsed - 30 break = 480 worked. Worked time NOT deducted [DEC-04]
    assert calc.worked_minutes == 480
    assert calc.unaccounted_minutes == 65
    assert "TRACKING_GAP" in calc.flags
    assert calc.review_status == "PENDING_REVIEW"
    assert "Tracking off" in calc.review_reasons


def test_scenario_e_driver():
    """E - driver:

    Departure 05:30, return 16:10, break 30 -> worked 610 min.
    """
    work_date = date(2026, 11, 3)
    acc_id = uuid4()

    visits = [
        # Departure from camp
        ConstructedVisit(
            work_date=work_date,
            place_type="ACCOMMODATION",
            worksite_id=None,
            accommodation_id=acc_id,
            entry_event_id=uuid4(),
            exit_event_id=uuid4(),
            entry_at=datetime(2026, 11, 3, 5, 0, tzinfo=UTC),
            exit_at=datetime(2026, 11, 3, 5, 30, tzinfo=UTC),  # Departure 05:30
            exit_inferred=False,
            last_inside_at=datetime(2026, 11, 3, 5, 30, tzinfo=UTC),
            counts_as_completed=True,
            duration_minutes=30,
        ),
        # Return to camp
        ConstructedVisit(
            work_date=work_date,
            place_type="ACCOMMODATION",
            worksite_id=None,
            accommodation_id=acc_id,
            entry_event_id=uuid4(),
            exit_event_id=None,
            entry_at=datetime(2026, 11, 3, 16, 10, tzinfo=UTC),  # Return 16:10
            exit_at=None,
            exit_inferred=False,
            last_inside_at=datetime(2026, 11, 3, 16, 10, tzinfo=UTC),
            counts_as_completed=True,
            duration_minutes=0,
        ),
    ]

    calc = compute_daily_attendance(
        DailyCalculationInputs(
            employee_id=uuid4(),
            tally_id="DRV01",
            work_date=work_date,
            is_driver=True,
            has_accommodation=True,
            standard_hours=8.0,
            schedule=make_dummy_schedule(),
            assignments=[],
            visits=visits,
            gaps=[],
            is_public_holiday=False,
            is_weekly_off=False,
            is_ot2_weekday=False,
            has_approved_leave=False,
        )
    )

    # 16:10 - 05:30 = 10 hours 40 minutes = 640 minutes - 30 min break = 610 minutes
    assert calc.worked_minutes == 610
    assert calc.shift_span_minutes == 640


def test_scenario_f_sunday_or_public_holiday():
    """F - Sunday or public holiday:

    A worker works 8 h -> ot2 = 480, ot1 = 0.
    """
    site1 = uuid4()
    work_date = date(2026, 11, 8)  # Sunday

    visits = [
        ConstructedVisit(
            work_date=work_date,
            place_type="SITE",
            worksite_id=site1,
            accommodation_id=None,
            entry_event_id=uuid4(),
            exit_event_id=uuid4(),
            entry_at=datetime(2026, 11, 8, 6, 0, tzinfo=UTC),
            exit_at=datetime(2026, 11, 8, 14, 30, tzinfo=UTC),
            exit_inferred=False,
            last_inside_at=datetime(2026, 11, 8, 14, 30, tzinfo=UTC),
            counts_as_completed=True,
            duration_minutes=510,
        )
    ]

    calc = compute_daily_attendance(
        DailyCalculationInputs(
            employee_id=uuid4(),
            tally_id="1017",
            work_date=work_date,
            is_driver=False,
            has_accommodation=True,
            standard_hours=8.0,
            schedule=make_dummy_schedule(),
            assignments=[
                ScheduledAssignment(
                    scheduled_work_id=uuid4(), worksite_id=site1, assigned_hours=8.0
                )
            ],
            visits=visits,
            gaps=[],
            is_public_holiday=False,
            is_weekly_off=False,
            is_ot2_weekday=True,  # Sunday is OT2 day
            has_approved_leave=False,
        )
    )

    assert calc.worked_minutes == 480
    assert calc.ot2_minutes == 480
    assert calc.ot1_minutes == 0
    assert calc.day_type == "OT2_DAY"


def test_scenario_g_weekly_off_or_no_assignment():
    """G - weekly off day or day with no assignment:

    A worker works 8 h on their weekly off day (not Sunday/holiday)
    -> ot1 = 480 (all hours OT1), flag UNSCHEDULED_WORK if no assignment.
    """
    site1 = uuid4()
    work_date = date(2026, 11, 6)  # Friday

    visits = [
        ConstructedVisit(
            work_date=work_date,
            place_type="SITE",
            worksite_id=site1,
            accommodation_id=None,
            entry_event_id=uuid4(),
            exit_event_id=uuid4(),
            entry_at=datetime(2026, 11, 6, 6, 0, tzinfo=UTC),
            exit_at=datetime(2026, 11, 6, 14, 30, tzinfo=UTC),
            exit_inferred=False,
            last_inside_at=datetime(2026, 11, 6, 14, 30, tzinfo=UTC),
            counts_as_completed=True,
            duration_minutes=510,
        )
    ]

    calc = compute_daily_attendance(
        DailyCalculationInputs(
            employee_id=uuid4(),
            tally_id="1017",
            work_date=work_date,
            is_driver=False,
            has_accommodation=True,
            standard_hours=8.0,
            schedule=make_dummy_schedule(),
            assignments=[],  # No assignment!
            visits=visits,
            gaps=[],
            is_public_holiday=False,
            is_weekly_off=True,
            is_ot2_weekday=False,
            has_approved_leave=False,
        )
    )

    assert calc.worked_minutes == 480
    assert calc.ot1_minutes == 480
    assert calc.ot2_minutes == 0
    assert "UNSCHEDULED_WORK" in calc.flags
    assert "Unscheduled work" in calc.review_reasons


def test_scenario_h_client_attendance_table_example():
    """H - client's attendance table:

    Planned: 05:00 / 06:00 / 0:30 / 15:30 / 17:00 (Total 12:00 = 720 min, Worked 09:00 = 540 min).
    Actual: 05:20 / 06:20 / 0:30 / 15:20 / 16:50 (Total 11:30 = 690 min, Worked 08:30 = 510 min).
    Variation in total time -00:30 (-30 min), in worked time -00:30 (-30 min).
    Row needs supervisor comment and engineer approval (PENDING_REVIEW).
    """
    site1 = uuid4()
    acc_id = uuid4()
    work_date = date(2026, 11, 3)

    schedule = make_dummy_schedule(
        acc_start=time(5, 0),
        first_site=time(6, 0),
        break_m=30,
        last_site=time(15, 30),
        acc_end=time(17, 0),
        planned_total=720,  # 12:00
        planned_worked=540,  # 09:00
    )

    visits = [
        # Accommodation departure 05:20
        ConstructedVisit(
            work_date=work_date,
            place_type="ACCOMMODATION",
            worksite_id=None,
            accommodation_id=acc_id,
            entry_event_id=uuid4(),
            exit_event_id=uuid4(),
            entry_at=datetime(2026, 11, 3, 5, 0, tzinfo=UTC),
            exit_at=datetime(2026, 11, 3, 5, 20, tzinfo=UTC),
            exit_inferred=False,
            last_inside_at=datetime(2026, 11, 3, 5, 20, tzinfo=UTC),
            counts_as_completed=True,
            duration_minutes=20,
        ),
        # First site entry 06:20, last site exit 15:20
        ConstructedVisit(
            work_date=work_date,
            place_type="SITE",
            worksite_id=site1,
            accommodation_id=None,
            entry_event_id=uuid4(),
            exit_event_id=uuid4(),
            entry_at=datetime(2026, 11, 3, 6, 20, tzinfo=UTC),
            exit_at=datetime(2026, 11, 3, 15, 20, tzinfo=UTC),
            exit_inferred=False,
            last_inside_at=datetime(2026, 11, 3, 15, 20, tzinfo=UTC),
            counts_as_completed=True,
            duration_minutes=540,
        ),
        # Accommodation return 16:50
        ConstructedVisit(
            work_date=work_date,
            place_type="ACCOMMODATION",
            worksite_id=None,
            accommodation_id=acc_id,
            entry_event_id=uuid4(),
            exit_event_id=None,
            entry_at=datetime(2026, 11, 3, 16, 50, tzinfo=UTC),
            exit_at=None,
            exit_inferred=False,
            last_inside_at=datetime(2026, 11, 3, 16, 50, tzinfo=UTC),
            counts_as_completed=True,
            duration_minutes=0,
        ),
    ]

    assignments = [
        ScheduledAssignment(scheduled_work_id=uuid4(), worksite_id=site1, assigned_hours=9.0),
    ]

    calc = compute_daily_attendance(
        DailyCalculationInputs(
            employee_id=uuid4(),
            tally_id="1017",
            work_date=work_date,
            is_driver=False,
            has_accommodation=True,
            standard_hours=8.0,
            schedule=schedule,
            assignments=assignments,
            visits=visits,
            gaps=[],
            is_public_holiday=False,
            is_weekly_off=False,
            is_ot2_weekday=False,
            has_approved_leave=False,
            grace_period_minutes=10,
        )
    )

    # Planned
    assert calc.planned_total_minutes == 720  # 12:00
    assert calc.planned_worked_minutes == 540  # 09:00

    # Actual
    # 16:50 - 05:20 = 11:30 = 690 min
    assert calc.shift_span_minutes == 690  # 11:30
    # 15:20 - 06:20 = 09:00 (540 min) - 30 min break = 08:30 (510 min)
    assert calc.worked_minutes == 510  # 08:30

    # Variation in total: 690 - 720 = -30 min (-00:30)
    var_total = calc.shift_span_minutes - calc.planned_total_minutes
    assert var_total == -30

    # Variation in worked: 510 - 540 = -30 min (-00:30)
    assert calc.variation_minutes == -30
    assert calc.shortfall_minutes == 30

    # 30 > grace (10) -> SHORTFALL_BEYOND_GRACE
    assert "SHORTFALL_BEYOND_GRACE" in calc.flags
    assert calc.review_status == "PENDING_REVIEW"
    assert "Short hours" in calc.review_reasons
