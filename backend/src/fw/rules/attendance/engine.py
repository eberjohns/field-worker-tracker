import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, time
from uuid import UUID

from fw.rules.attendance.gaps import ConstructedGap, calculate_unaccounted_time_minutes
from fw.rules.attendance.visits import ConstructedVisit
from fw.rules.time_rules import ResolvedTimeSchedule


@dataclass(frozen=True)
class ScheduledAssignment:
    scheduled_work_id: UUID
    worksite_id: UUID
    assigned_hours: float
    is_active: bool = True


@dataclass(frozen=True)
class DailyCalculationInputs:
    employee_id: UUID
    tally_id: str
    work_date: date
    is_driver: bool
    has_accommodation: bool
    standard_hours: float  # e.g. 8.0, 10.0, 12.0
    schedule: ResolvedTimeSchedule
    assignments: list[ScheduledAssignment]
    visits: list[ConstructedVisit]
    gaps: list[ConstructedGap]
    is_public_holiday: bool
    is_weekly_off: bool
    is_ot2_weekday: bool  # e.g. Sunday
    has_approved_leave: bool
    first_site_break_override: int | None = None
    grace_period_minutes: int = 10
    gap_flag_minutes: int = 15
    max_transit_minutes: int = 90
    extra_flags: list[str] = field(default_factory=list)


@dataclass
class DailyCalculationResult:
    # Planned values
    planned_accommodation_departure: time | None
    planned_first_site_start: time | None
    planned_break_minutes: int
    planned_last_site_end: time | None
    planned_accommodation_return: time | None
    planned_total_minutes: int
    planned_worked_minutes: int
    standard_hours_minutes: int

    # Actual values
    accommodation_departure_at: datetime | None
    first_site_entry_at: datetime | None
    break_minutes_used: int
    break_source: str
    last_site_exit_at: datetime | None
    accommodation_return_at: datetime | None

    # Durations & variations
    elapsed_site_minutes: int
    shift_span_minutes: int
    unaccounted_minutes: int
    worked_minutes: int
    required_minutes: int
    variation_minutes: int  # signed: worked - required
    shortfall_minutes: int
    grace_minutes: int
    grace_applied: bool
    satisfied: bool

    # Movement breakdown
    productive_minutes: int
    transit_minutes: int
    offsite_minutes: int
    idle_minutes: int

    # Overtime
    ot1_minutes: int
    ot2_minutes: int
    ot_threshold_minutes: int
    day_type: str  # NORMAL | WEEKLY_OFF | OT2_DAY

    # Counts & status
    assigned_count: int
    completed_count: int
    business_status: str  # PRESENT | PARTIAL | ABSENT
    review_status: str  # AUTO | PENDING_REVIEW
    flags: list[str]
    review_reasons: list[str]

    # Deterministic fingerprint
    input_hash: str


def compute_daily_attendance(inputs: DailyCalculationInputs) -> DailyCalculationResult:
    """Compute the daily attendance calculation snapshot according to FWT business rules."""
    flags: list[str] = list(inputs.extra_flags)

    # 1. Planned values from time schedule & standard hours
    sched = inputs.schedule
    std_adj = sched.standard_hours_change_minutes
    standard_hours_minutes = max(0, int(inputs.standard_hours * 60) + std_adj)

    # Required minutes over ACTIVE assignments
    active_assignments = [a for a in inputs.assignments if a.is_active]
    required_minutes = int(sum(a.assigned_hours * 60 for a in active_assignments))
    assigned_count = len(active_assignments)

    # 2. Visits classification (Site visits vs Accommodation visits)
    site_visits = [v for v in inputs.visits if v.place_type == "SITE"]
    acc_visits = [v for v in inputs.visits if v.place_type == "ACCOMMODATION"]

    for v in inputs.visits:
        for f in v.flags:
            if f not in flags:
                flags.append(f)

    # Effective break resolution: first site visited override vs time rule break
    if inputs.first_site_break_override is not None:
        break_minutes_used = inputs.first_site_break_override
        break_source = "JOB_ITEM_OVERRIDE"
    else:
        break_minutes_used = sched.break_minutes
        break_source = "TIME_RULE"

    # Actual timing points
    first_site_entry_at: datetime | None = None
    last_site_exit_at: datetime | None = None
    if site_visits:
        first_site_entry_at = min(v.entry_at for v in site_visits)
        # For exits: use exit_at if present, else last_inside_at
        exits = [v.exit_at or v.last_inside_at for v in site_visits]
        last_site_exit_at = max(exits)

    accommodation_departure_at: datetime | None = None
    accommodation_return_at: datetime | None = None
    if acc_visits:
        # Departure is an EXIT from accommodation
        departures = [v.exit_at for v in acc_visits if v.exit_at is not None]
        if departures:
            accommodation_departure_at = min(departures)
        # Return is an ENTRY to accommodation
        returns = [v.entry_at for v in acc_visits]
        if returns:
            accommodation_return_at = max(returns)

    # Actual worked minutes computation
    elapsed_site_minutes = 0
    if first_site_entry_at and last_site_exit_at and last_site_exit_at > first_site_entry_at:
        elapsed_site_minutes = int((last_site_exit_at - first_site_entry_at).total_seconds() // 60)

    shift_span_minutes = 0
    if inputs.has_accommodation and accommodation_departure_at and accommodation_return_at:
        shift_span_minutes = max(
            0,
            int((accommodation_return_at - accommodation_departure_at).total_seconds() // 60),
        )
    else:
        shift_span_minutes = elapsed_site_minutes

    if inputs.is_driver:
        # Driver formula: (acc_return - acc_departure) - break
        if accommodation_departure_at and accommodation_return_at:
            worked_minutes = max(0, shift_span_minutes - break_minutes_used)
        else:
            if "NO_ACCOMMODATION_EVENTS" not in flags:
                flags.append("NO_ACCOMMODATION_EVENTS")
            worked_minutes = max(0, elapsed_site_minutes - break_minutes_used)
    else:
        # Regular worker / supervisor / engineer: (last_site_exit - first_site_entry) - break
        worked_minutes = max(0, elapsed_site_minutes - break_minutes_used)

    # 3. Unaccounted time & Tracking gap flag
    shift_start = accommodation_departure_at or first_site_entry_at
    shift_end = accommodation_return_at or last_site_exit_at
    unaccounted_minutes = calculate_unaccounted_time_minutes(
        inputs.gaps,
        shift_start,
        shift_end,
        break_minutes_used,
    )
    if unaccounted_minutes > inputs.gap_flag_minutes:
        if "TRACKING_GAP" not in flags:
            flags.append("TRACKING_GAP")

    # 4. Variation & Grace
    variation_minutes = worked_minutes - required_minutes  # signed
    shortfall_minutes = max(0, -variation_minutes)
    grace_applied = 0 < shortfall_minutes <= inputs.grace_period_minutes
    satisfied = (shortfall_minutes == 0) or grace_applied

    if shortfall_minutes > inputs.grace_period_minutes:
        if "SHORTFALL_BEYOND_GRACE" not in flags:
            flags.append("SHORTFALL_BEYOND_GRACE")

    # 5. Counts & Business status [DEC-17]
    assigned_worksite_ids = {a.worksite_id for a in active_assignments}
    completed_site_ids = {
        v.worksite_id for v in site_visits if v.worksite_id is not None and v.counts_as_completed
    }
    completed_count = len(assigned_worksite_ids.intersection(completed_site_ids))

    if assigned_count > 0:
        if completed_count == assigned_count:
            business_status = "PRESENT"
        elif completed_count > 0:
            business_status = "PARTIAL"
        else:
            business_status = "ABSENT" if not inputs.has_approved_leave else "ON_LEAVE"
    else:
        # No scheduled assignments
        if worked_minutes > 0:
            business_status = "PRESENT"
            if "UNSCHEDULED_WORK" not in flags:
                flags.append("UNSCHEDULED_WORK")
        else:
            business_status = (
                "REST" if (inputs.is_weekly_off or inputs.is_public_holiday) else "FREE"
            )

    # 6. Overtime Calculation [DEC-01]
    is_ot2_day = inputs.is_public_holiday or inputs.is_ot2_weekday
    if is_ot2_day:
        day_type = "OT2_DAY"
        ot2_minutes = worked_minutes
        ot1_minutes = 0
    elif inputs.is_weekly_off or assigned_count == 0:
        day_type = "WEEKLY_OFF"
        ot1_minutes = worked_minutes
        ot2_minutes = 0
    else:
        day_type = "NORMAL"
        ot1_minutes = max(0, worked_minutes - standard_hours_minutes)
        ot2_minutes = 0

    # 7. Movement segments breakdown [DEC-28]
    if inputs.is_driver:
        productive_minutes = worked_minutes
        transit_minutes = 0
        offsite_minutes = 0
        idle_minutes = max(0, shift_span_minutes - worked_minutes - break_minutes_used)
    else:
        counted_site_mins = sum(v.duration_minutes for v in site_visits if v.counts_as_completed)
        productive_minutes = max(0, counted_site_mins - break_minutes_used)

        # Calculate transit between consecutive polygon visits
        all_sorted_visits = sorted(inputs.visits, key=lambda v: v.entry_at)
        raw_transit_secs = 0.0
        raw_offsite_secs = 0.0
        for i in range(len(all_sorted_visits) - 1):
            prev_v = all_sorted_visits[i]
            next_v = all_sorted_visits[i + 1]
            prev_exit = prev_v.exit_at or prev_v.last_inside_at
            next_entry = next_v.entry_at
            if next_entry > prev_exit:
                interval_min = (next_entry - prev_exit).total_seconds() / 60.0
                if interval_min <= inputs.max_transit_minutes:
                    raw_transit_secs += (next_entry - prev_exit).total_seconds()
                else:
                    raw_offsite_secs += (next_entry - prev_exit).total_seconds()

        transit_minutes = int(raw_transit_secs // 60)
        offsite_minutes = int(raw_offsite_secs // 60)
        idle_minutes = max(
            0,
            shift_span_minutes - productive_minutes - transit_minutes - break_minutes_used,
        )

    # 8. Review routing & review reasons [DEC-43]
    review_reasons: list[str] = []
    # Reason mapping
    if any(f in flags for f in ("MISSING_EXIT", "INFERRED_EXIT", "LEFT_WITHOUT_EXIT")):
        review_reasons.append("Estimated exit")
    if "TRACKING_GAP" in flags:
        review_reasons.append("Tracking off")
    if "SHORTFALL_BEYOND_GRACE" in flags:
        review_reasons.append("Short hours")
    if "UNASSIGNED_SITE_VISIT" in flags:
        review_reasons.append("Other site")
    if "UNSCHEDULED_WORK" in flags:
        review_reasons.append("Unscheduled work")
    if "CLOCK_SKEW" in flags:
        review_reasons.append("Device clock")
    if "MOCK_LOCATION" in flags:
        review_reasons.append("Mock location")
    if any(f in flags for f in ("BORDERLINE_LOCATION", "LOW_ACCURACY")):
        review_reasons.append("Weak location")
    if "NO_ACCOMMODATION_EVENTS" in flags:
        review_reasons.append("No accommodation data")
    if "CROSSES_MIDNIGHT" in flags:
        review_reasons.append("Midnight crossing")
    if ot1_minutes > 0 or ot2_minutes > 0:
        review_reasons.append("Overtime")

    has_variation_beyond_grace = shortfall_minutes > inputs.grace_period_minutes
    has_overtime = (ot1_minutes > 0) or (ot2_minutes > 0)
    has_review_flags = len(flags) > 0

    if has_variation_beyond_grace or has_overtime or has_review_flags:
        review_status = "PENDING_REVIEW"
    else:
        review_status = "AUTO"

    # 9. Deterministic Input Hash
    hash_payload = {
        "employee_id": str(inputs.employee_id),
        "work_date": str(inputs.work_date),
        "standard_hours": inputs.standard_hours,
        "assignments": [
            {"id": str(a.scheduled_work_id), "site": str(a.worksite_id), "h": a.assigned_hours}
            for a in sorted(active_assignments, key=lambda x: x.scheduled_work_id)
        ],
        "visits": [
            {
                "entry": v.entry_at.isoformat(),
                "exit": v.exit_at.isoformat() if v.exit_at else None,
                "place": str(v.worksite_id or v.accommodation_id),
                "inferred": v.exit_inferred,
            }
            for v in sorted(inputs.visits, key=lambda x: x.entry_at)
        ],
        "gaps": [
            {
                "start": g.started_at.isoformat(),
                "end": g.ended_at.isoformat() if g.ended_at else None,
            }
            for g in sorted(inputs.gaps, key=lambda x: x.started_at)
        ],
        "schedule": {
            "break": sched.break_minutes,
            "acc_st": sched.accommodation_start.strftime("%H:%M")
            if sched.accommodation_start
            else None,
            "site_st": sched.first_site_start.strftime("%H:%M") if sched.first_site_start else None,
            "site_end": sched.last_site_end.strftime("%H:%M") if sched.last_site_end else None,
            "acc_end": sched.accommodation_end.strftime("%H:%M")
            if sched.accommodation_end
            else None,
        },
        "break_used": break_minutes_used,
        "is_holiday": inputs.is_public_holiday,
        "is_off": inputs.is_weekly_off,
        "is_ot2_weekday": inputs.is_ot2_weekday,
    }
    input_hash = hashlib.sha256(
        json.dumps(hash_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()

    return DailyCalculationResult(
        planned_accommodation_departure=sched.accommodation_start,
        planned_first_site_start=sched.first_site_start,
        planned_break_minutes=sched.break_minutes,
        planned_last_site_end=sched.last_site_end,
        planned_accommodation_return=sched.accommodation_end,
        planned_total_minutes=sched.planned_total_minutes,
        planned_worked_minutes=sched.planned_worked_minutes,
        standard_hours_minutes=standard_hours_minutes,
        accommodation_departure_at=accommodation_departure_at,
        first_site_entry_at=first_site_entry_at,
        break_minutes_used=break_minutes_used,
        break_source=break_source,
        last_site_exit_at=last_site_exit_at,
        accommodation_return_at=accommodation_return_at,
        elapsed_site_minutes=elapsed_site_minutes,
        shift_span_minutes=shift_span_minutes,
        unaccounted_minutes=unaccounted_minutes,
        worked_minutes=worked_minutes,
        required_minutes=required_minutes,
        variation_minutes=variation_minutes,
        shortfall_minutes=shortfall_minutes,
        grace_minutes=inputs.grace_period_minutes,
        grace_applied=grace_applied,
        satisfied=satisfied,
        productive_minutes=productive_minutes,
        transit_minutes=transit_minutes,
        offsite_minutes=offsite_minutes,
        idle_minutes=idle_minutes,
        ot1_minutes=ot1_minutes,
        ot2_minutes=ot2_minutes,
        ot_threshold_minutes=required_minutes,
        day_type=day_type,
        assigned_count=assigned_count,
        completed_count=completed_count,
        business_status=business_status,
        review_status=review_status,
        flags=flags,
        review_reasons=review_reasons,
        input_hash=input_hash,
    )
