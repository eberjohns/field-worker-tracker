"""Pure domain rules for period-wide quotas, pacing windows, and excess visit calculation.

Rules:
1. Quota is evaluated strictly at the period level (Week, Month, Quarter).
2. For periodic visits (e.g. 2 visits/month), the period is divided into equal windows
   for visual pacing guidance only.
3. Fulfillment is stable (Zero Swapping):
   Visits are ordered deterministically by (created_at ASC, work_date ASC, id ASC).
   The first K visits fulfill the required quota; any visits beyond K are marked EXCESS.
   Editing or assigning another slot never swaps existing required visits to excess.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID

from fw.rules.scheduling.assignment import INT_TO_WEEKDAY


@dataclass(frozen=True)
class PacingWindow:
    """A pacing window within a period providing visual recommendation guidance."""

    window_index: int  # 1-based index (1..K)
    start_date: date
    end_date: date
    recommended_date: date
    assigned_visit_count: int


@dataclass(frozen=True)
class VisitRecord:
    """A scheduled or candidate visit in a period."""

    id: UUID
    work_date: date
    created_at: datetime
    is_base_blueprint: bool = False


@dataclass(frozen=True)
class EvaluatedVisit:
    """An evaluated visit with stable status determination."""

    id: UUID
    work_date: date
    is_required: bool
    is_excess: bool
    status_label: str  # "REQUIRED_MET" | "EXCESS"


@dataclass(frozen=True)
class PeriodQuotaResult:
    """Evaluation summary of quota fulfillment for a period."""

    period_name: str
    target_count: int
    assigned_count: int
    is_quota_satisfied: bool
    remaining_required: int
    excess_count: int
    evaluated_visits: list[EvaluatedVisit]
    windows: list[PacingWindow]


def calculate_pacing_windows(
    period_start: date,
    period_end: date,
    occurrences: int,
    scheduled_weekdays: list[str] | None = None,
    public_holidays: set[date] | None = None,
) -> list[PacingWindow]:
    """Divide a period into K equal sub-windows and compute the recommended target date for each.

    Args:
        period_start: First calendar date of the period.
        period_end: Last calendar date of the period (inclusive).
        occurrences: Number of target visits K in the period.
        scheduled_weekdays: Preferred days of week (e.g. ["MON", "WED"]). Optional.
        public_holidays: Set of public holiday dates to avoid in recommendation.

    Returns:
        List of K PacingWindow objects with non-overlapping date spans.
    """
    if occurrences <= 0:
        return []

    holidays = public_holidays or set()
    total_days = (period_end - period_start).days + 1
    if total_days < occurrences:
        occurrences = total_days

    window_size = total_days / occurrences
    windows: list[PacingWindow] = []

    preferred_dows = {w.upper() for w in scheduled_weekdays} if scheduled_weekdays else set()

    for i in range(occurrences):
        w_start_offset = int(round(i * window_size))
        w_end_offset = int(round((i + 1) * window_size)) - 1
        if i == occurrences - 1:
            w_end_offset = total_days - 1

        w_start = period_start + timedelta(days=w_start_offset)
        w_end = period_start + timedelta(days=w_end_offset)

        # Determine recommended date in this window
        # 1. Look for preferred weekday that is not a holiday
        recommended: date | None = None
        curr = w_start
        candidates_non_holiday: list[date] = []
        candidates_matching_dow: list[date] = []

        while curr <= w_end:
            dow = INT_TO_WEEKDAY[curr.weekday()]
            if curr not in holidays:
                candidates_non_holiday.append(curr)
                if dow in preferred_dows:
                    candidates_matching_dow.append(curr)
            curr += timedelta(days=1)

        if candidates_matching_dow:
            recommended = candidates_matching_dow[0]
        elif candidates_non_holiday:
            recommended = candidates_non_holiday[0]
        else:
            # Fallback to start of window if all are holidays
            recommended = w_start

        windows.append(
            PacingWindow(
                window_index=i + 1,
                start_date=w_start,
                end_date=w_end,
                recommended_date=recommended,
                assigned_visit_count=0,
            )
        )

    return windows


def evaluate_period_quota(
    target_count: int,
    visits: list[VisitRecord],
    period_start: date,
    period_end: date,
    period_name: str = "Week",
    windows: list[PacingWindow] | None = None,
) -> PeriodQuotaResult:
    """Evaluate period quota with deterministic, stable status (Zero Swapping).

    Visits are sorted deterministically:
      1. created_at ASC (earlier created assignments stay required)
      2. work_date ASC
      3. id ASC
    First target_count visits are REQUIRED_MET; any remaining are EXCESS.
    """
    # Filter visits to those strictly within this period
    period_visits = [v for v in visits if period_start <= v.work_date <= period_end]

    # Deterministic sort
    sorted_visits = sorted(
        period_visits,
        key=lambda v: (v.created_at, v.work_date, str(v.id)),
    )

    evaluated: list[EvaluatedVisit] = []
    for idx, v in enumerate(sorted_visits):
        if idx < target_count:
            evaluated.append(
                EvaluatedVisit(
                    id=v.id,
                    work_date=v.work_date,
                    is_required=True,
                    is_excess=False,
                    status_label="REQUIRED_MET",
                )
            )
        else:
            evaluated.append(
                EvaluatedVisit(
                    id=v.id,
                    work_date=v.work_date,
                    is_required=False,
                    is_excess=True,
                    status_label="EXCESS",
                )
            )

    assigned_count = len(sorted_visits)
    remaining_required = max(0, target_count - assigned_count)
    excess_count = max(0, assigned_count - target_count)
    is_satisfied = assigned_count >= target_count

    # Update assigned count in windows if provided
    updated_windows: list[PacingWindow] = []
    if windows:
        for w in windows:
            count = sum(1 for v in period_visits if w.start_date <= v.work_date <= w.end_date)
            updated_windows.append(
                PacingWindow(
                    window_index=w.window_index,
                    start_date=w.start_date,
                    end_date=w.end_date,
                    recommended_date=w.recommended_date,
                    assigned_visit_count=count,
                )
            )

    return PeriodQuotaResult(
        period_name=period_name,
        target_count=target_count,
        assigned_count=assigned_count,
        is_quota_satisfied=is_satisfied,
        remaining_required=remaining_required,
        excess_count=excess_count,
        evaluated_visits=evaluated,
        windows=updated_windows,
    )
