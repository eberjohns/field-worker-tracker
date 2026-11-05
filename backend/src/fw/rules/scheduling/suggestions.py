"""Pure business logic for candidate recommendations (DEC-52, Doc 04 Section 8)."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fw.rules.scheduling.validation import extract_grade_group


@dataclass(frozen=True)
class CandidateWorker:
    """Worker candidate profile for ranking."""

    employee_id: str
    name: str
    tally_id: str
    is_active: bool
    join_date: date | None
    employment_end_date: date | None
    grade_code: str | None
    staff_grade_description: str | None
    weekly_off_day: str | None
    standard_hours: Decimal
    is_on_leave: bool
    is_budget_only: bool
    worked_at_site_recently: bool  # within last 14 days
    shares_supervisor: bool  # reports to the same supervisor
    weekly_allocated_hours: Decimal
    today_allocated_hours: Decimal
    is_scope_accessible: bool = True


@dataclass(frozen=True)
class TargetJobItem:
    """Target job item being staffed."""

    job_item_id: str
    worksite_id: str
    planned_grade_code: str
    staff_grade_description: str
    deployment_type: str
    required_hours: Decimal


@dataclass(frozen=True)
class ScoredCandidate:
    """Evaluated worker candidate with recommendation score and flags."""

    worker: CandidateWorker
    is_eligible: bool
    exact_staff_type_match: bool
    grade_group_match: bool
    ranking_score: float  # higher is better
    reasons: list[str]
    warnings: list[str]


def rank_candidates_for_job(
    candidates: list[CandidateWorker],
    job: TargetJobItem,
    target_date: date,
) -> list[ScoredCandidate]:
    """Rank worker candidates for a job assignment on target_date.

    Only eligible workers are returned in the recommendation list:
    - Active and employed on target_date
    - Accessible in user's scope
    - Not on approved leave
    - Not budget-only
    - Grade group matches the job item planned grade group

    Sorting order:
    1. Exact staff type match first
    2. Worked at this worksite in last 14 days
    3. Shares same supervisor
    4. Most free hours in the target week
    """
    job_group = extract_grade_group(job.planned_grade_code)
    job_sgd = (job.staff_grade_description or "").strip().lower()

    scored_list: list[ScoredCandidate] = []

    for w in candidates:
        # Base hard filters
        if not w.is_scope_accessible or not w.is_active or w.is_on_leave or w.is_budget_only:
            continue

        if w.join_date and target_date < w.join_date:
            continue
        if w.employment_end_date and target_date > w.employment_end_date:
            continue

        worker_group = extract_grade_group(w.grade_code)
        worker_sgd = (w.staff_grade_description or "").strip().lower()

        grade_group_match = bool(worker_group and job_group and worker_group == job_group)
        exact_staff_type = bool(worker_sgd and job_sgd and worker_sgd == job_sgd)

        # Eligible candidates must match the grade group
        if not grade_group_match:
            continue

        reasons: list[str] = []
        warnings: list[str] = []

        if exact_staff_type:
            reasons.append("Exact staff type match")
        elif grade_group_match:
            reasons.append(f"Same grade group ({worker_group})")

        if w.worked_at_site_recently:
            reasons.append("Worked at this site in the last 14 days")

        if w.shares_supervisor:
            reasons.append("Same supervisor as team")

        # Capacity calculations
        free_weekly_hours = max(
            Decimal("0"), (w.standard_hours * Decimal("6")) - w.weekly_allocated_hours
        )
        reasons.append(f"{free_weekly_hours}h free capacity this week")

        # Warnings preview
        if w.today_allocated_hours + job.required_hours > w.standard_hours:
            warnings.append("Will exceed standard hours today (planned overtime)")

        # Composite score
        # Exact staff type match is heavily weighted
        score = 0.0
        if exact_staff_type:
            score += 1000.0
        if w.worked_at_site_recently:
            score += 100.0
        if w.shares_supervisor:
            score += 50.0
        score += float(free_weekly_hours)

        scored_list.append(
            ScoredCandidate(
                worker=w,
                is_eligible=True,
                exact_staff_type_match=exact_staff_type,
                grade_group_match=grade_group_match,
                ranking_score=score,
                reasons=reasons,
                warnings=warnings,
            )
        )

    # Sort descending by ranking_score
    scored_list.sort(key=lambda sc: sc.ranking_score, reverse=True)
    return scored_list
