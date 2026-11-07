"""Unit tests for Rebuilt Planner pure business rules (Blueprint, Quotas, Operational)."""

from datetime import date, datetime, timezone
from uuid import uuid4

from fw.rules.scheduling.blueprint import (
    BlueprintEntry,
    resolve_base_template_slots,
    validate_base_template_entries,
)
from fw.rules.scheduling.operational import (
    OperationalShiftInput,
    resolve_operational_cell,
)
from fw.rules.scheduling.quotas import (
    VisitRecord,
    calculate_pacing_windows,
    evaluate_period_quota,
)


def test_mode_a_uniform_crew_with_rest_day_warning():
    """Mode A assigns the same workers across working days; rest day generates warning."""
    emp1 = uuid4()
    emp2 = uuid4()

    entries = [
        BlueprintEntry(employee_id=emp1, weekday_mask="ALL", assigned_hours=8.0),
        BlueprintEntry(employee_id=emp2, weekday_mask="ALL", assigned_hours=8.0),
    ]

    target_dates = [
        date(2026, 11, 23),  # MON
        date(2026, 11, 27),  # FRI
    ]

    # emp1 has Friday off; emp2 has Sunday off
    worker_offs = {emp1: "FRI", emp2: "SUN"}
    public_holidays = {date(2026, 11, 27)}  # Friday is also a holiday

    slots = resolve_base_template_slots(
        allocation_mode="UNIFORM",
        entries=entries,
        target_dates=target_dates,
        public_holidays=public_holidays,
        worker_weekly_off_days=worker_offs,
    )

    # Total 4 slots (2 days * 2 workers)
    assert len(slots) == 4

    # Monday slots
    mon_slots = [s for s in slots if s.day_of_week == "MON"]
    assert len(mon_slots) == 2
    assert all(s.status == "VALID" for s in mon_slots)

    # Friday slots
    fri_emp1 = next(s for s in slots if s.day_of_week == "FRI" and s.employee_id == emp1)
    fri_emp2 = next(s for s in slots if s.day_of_week == "FRI" and s.employee_id == emp2)

    # emp1 is on rest day and holiday
    assert fri_emp1.is_worker_weekly_off is True
    assert fri_emp1.is_public_holiday is True
    assert fri_emp1.status == "REST_DAY_WARNING"

    # emp2 is on holiday only
    assert fri_emp2.is_worker_weekly_off is False
    assert fri_emp2.is_public_holiday is True
    assert fri_emp2.status == "HOLIDAY_OVERTIME"


def test_mode_b_day_of_week_crew_resolves_friday_rotation():
    """Mode B allows specifying distinct workers on Friday vs Mon-Thu/Sat."""
    worker_regular = uuid4()  # has Friday off
    worker_friday_sub = uuid4()  # has Sunday off

    entries = [
        BlueprintEntry(employee_id=worker_regular, weekday_mask="MON", assigned_hours=8.0),
        BlueprintEntry(employee_id=worker_regular, weekday_mask="TUE", assigned_hours=8.0),
        BlueprintEntry(employee_id=worker_regular, weekday_mask="WED", assigned_hours=8.0),
        BlueprintEntry(employee_id=worker_regular, weekday_mask="THU", assigned_hours=8.0),
        BlueprintEntry(employee_id=worker_friday_sub, weekday_mask="FRI", assigned_hours=8.0),
        BlueprintEntry(employee_id=worker_regular, weekday_mask="SAT", assigned_hours=8.0),
    ]

    target_dates = [
        date(2026, 11, 23),  # MON
        date(2026, 11, 27),  # FRI
        date(2026, 11, 28),  # SAT
    ]

    worker_offs = {worker_regular: "FRI", worker_friday_sub: "SUN"}

    slots = resolve_base_template_slots(
        allocation_mode="DAY_OF_WEEK",
        entries=entries,
        target_dates=target_dates,
        public_holidays=set(),
        worker_weekly_off_days=worker_offs,
    )

    fri_slot = next(s for s in slots if s.day_of_week == "FRI")
    assert fri_slot.employee_id == worker_friday_sub
    assert fri_slot.is_worker_weekly_off is False
    assert fri_slot.status == "VALID"

    mon_slot = next(s for s in slots if s.day_of_week == "MON")
    assert mon_slot.employee_id == worker_regular
    assert mon_slot.is_worker_weekly_off is False


def test_pacing_windows_and_stable_quota_zero_swapping():
    """Verify window pacing and deterministic zero-swapping quota fulfillment."""
    # Semi-monthly: 2 visits across November (30 days)
    p_start = date(2026, 11, 1)
    p_end = date(2026, 11, 30)

    windows = calculate_pacing_windows(
        period_start=p_start,
        period_end=p_end,
        occurrences=2,
        scheduled_weekdays=["WED"],
    )
    assert len(windows) == 2
    assert windows[0].start_date == date(2026, 11, 1)
    assert windows[0].end_date == date(2026, 11, 15)
    assert windows[1].start_date == date(2026, 11, 16)
    assert windows[1].end_date == date(2026, 11, 30)

    # 3 scheduled visits created sequentially
    v1_id = uuid4()
    v2_id = uuid4()
    v3_id = uuid4()

    visits = [
        VisitRecord(id=v1_id, work_date=date(2026, 11, 4), created_at=datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)),
        VisitRecord(id=v2_id, work_date=date(2026, 11, 18), created_at=datetime(2026, 11, 1, 10, 5, tzinfo=timezone.utc)),
        VisitRecord(id=v3_id, work_date=date(2026, 11, 11), created_at=datetime(2026, 11, 1, 11, 0, tzinfo=timezone.utc)),
    ]

    res = evaluate_period_quota(
        target_count=2,
        visits=visits,
        period_start=p_start,
        period_end=p_end,
        windows=windows,
    )

    assert res.target_count == 2
    assert res.assigned_count == 3
    assert res.is_quota_satisfied is True
    assert res.excess_count == 1

    # v1 and v2 were created first -> REQUIRED_MET
    # v3 was created last -> EXCESS (regardless of work_date 11 Nov being earlier than 18 Nov)
    v1_eval = next(v for v in res.evaluated_visits if v.id == v1_id)
    v2_eval = next(v for v in res.evaluated_visits if v.id == v2_id)
    v3_eval = next(v for v in res.evaluated_visits if v.id == v3_id)

    assert v1_eval.is_required is True
    assert v1_eval.is_excess is False
    assert v2_eval.is_required is True
    assert v2_eval.is_excess is False
    assert v3_eval.is_required is False
    assert v3_eval.is_excess is True


def test_operational_cell_precedence_and_overrides():
    """Verify precedence: Operational Override > Approved Leave Gap > Base Blueprint."""
    base_worker1 = uuid4()  # Present base worker
    base_worker2 = uuid4()  # Base worker on leave, with cover
    base_worker3 = uuid4()  # Base worker on leave, NO cover -> TO_BE_COVERED
    cover_worker = uuid4()   # Operational replacement

    from fw.rules.scheduling.blueprint import ResolvedTemplateSlot

    d = date(2026, 11, 25)
    base_slots = [
        ResolvedTemplateSlot(work_date=d, day_of_week="WED", employee_id=base_worker1, assigned_hours=8.0, sequence=1, is_public_holiday=False, is_worker_weekly_off=False, status="VALID"),
        ResolvedTemplateSlot(work_date=d, day_of_week="WED", employee_id=base_worker2, assigned_hours=8.0, sequence=2, is_public_holiday=False, is_worker_weekly_off=False, status="VALID"),
        ResolvedTemplateSlot(work_date=d, day_of_week="WED", employee_id=base_worker3, assigned_hours=8.0, sequence=3, is_public_holiday=False, is_worker_weekly_off=False, status="VALID"),
    ]

    approved_leaves = {base_worker2, base_worker3}

    op_shifts = [
        OperationalShiftInput(
            id=uuid4(),
            work_date=d,
            employee_id=cover_worker,
            source="OVERRIDE",
            original_employee_id=base_worker2,
            override_reason="Sick Leave Cover",
            assigned_hours=8.0,
            sequence=2,
        )
    ]

    cell_workers = resolve_operational_cell(
        work_date=d,
        base_slots=base_slots,
        approved_leave_worker_ids=approved_leaves,
        operational_shifts=op_shifts,
    )

    assert len(cell_workers) == 3

    # Worker 1: Normal base blueprint (muted)
    w1 = next(w for w in cell_workers if w.employee_id == base_worker1)
    assert w1.display_type == "BLUEPRINT"
    assert w1.opacity_class == "muted"

    # Worker 2: Overridden by cover_worker (solid)
    w2 = next(w for w in cell_workers if w.employee_id == cover_worker)
    assert w2.display_type == "OVERRIDE"
    assert w2.opacity_class == "solid"
    assert w2.original_employee_id == base_worker2
    assert w2.reason == "Sick Leave Cover"

    # Worker 3: On leave without cover -> TO_BE_COVERED (dashed)
    w3 = next(w for w in cell_workers if w.employee_id == base_worker3)
    assert w3.display_type == "TO_BE_COVERED"
    assert w3.opacity_class == "warning"
