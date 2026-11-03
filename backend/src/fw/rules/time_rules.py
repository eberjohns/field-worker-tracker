from dataclasses import dataclass, field
from datetime import date, time
from enum import StrEnum
from typing import Any
from uuid import UUID


class TimeRuleScope(StrEnum):
    COMPANY = "COMPANY"
    TEAM = "TEAM"
    DRIVERS = "DRIVERS"
    EMPLOYEE = "EMPLOYEE"


class TimeRuleAppliesTo(StrEnum):
    ALL = "ALL"
    OUTDOOR_ONLY = "OUTDOOR_ONLY"
    INDOOR_ONLY = "INDOOR_ONLY"


@dataclass(frozen=True)
class TimeRuleDefinition:
    """Domain model of a time rule (BR-ST-01..05, DEC-03, DEC-41, D3)."""

    id: UUID | str
    name: str
    country: str | None
    scope_type: TimeRuleScope | str
    scope_employee_id: UUID | None
    applies_to: TimeRuleAppliesTo | str
    start_date: date
    end_date: date | None = None
    accommodation_start: time | None = None
    first_site_start: time | None = None
    break_minutes: int | None = None
    last_site_end: time | None = None
    accommodation_end: time | None = None
    standard_hours_change_minutes: int | None = None
    notes: str | None = None
    is_active: bool = True


@dataclass(frozen=True)
class WorkerContext:
    """Context of the worker needed to resolve time rules."""

    employee_id: UUID
    country: str
    is_driver: bool = False
    has_accommodation: bool = True
    # list of (manager_id, relationship: 'SUPERVISOR' | 'SUPERINTENDENT' | 'ENGINEER')
    manager_links: list[tuple[UUID, str]] = field(default_factory=list)


@dataclass
class WinningFieldSource:
    rule_id: UUID | str
    rule_name: str
    scope_type: str
    field_name: str
    value: Any


@dataclass
class MatchedRuleExplanation:
    rule_id: UUID | str
    rule_name: str
    scope_type: str
    applies_to: str
    priority_score: float
    is_match: bool
    status: str  # WON, PARTIAL_INHERITED, SHADOWED, OUT_OF_SCOPE, DATE_MISMATCH, etc.
    reasons: list[str] = field(default_factory=list)


@dataclass
class ResolvedTimeSchedule:
    """Effective 5-point planned schedule and explanation."""

    accommodation_start: time | None
    first_site_start: time | None
    break_minutes: int
    last_site_end: time | None
    accommodation_end: time | None
    planned_total_minutes: int
    planned_worked_minutes: int
    standard_hours_change_minutes: int
    has_accommodation: bool
    winning_rule_id: UUID | str | None
    winning_rule_name: str | None
    winning_sources: dict[str, WinningFieldSource] = field(default_factory=dict)
    matched_rules: list[MatchedRuleExplanation] = field(default_factory=list)


def time_to_minutes(t: time | None) -> int | None:
    if t is None:
        return None
    return t.hour * 60 + t.minute


def time_diff_minutes(start: time | None, end: time | None) -> int:
    """Compute difference in minutes between two times on the same day."""
    if start is None or end is None:
        return 0
    start_m = time_to_minutes(start) or 0
    end_m = time_to_minutes(end) or 0
    diff = end_m - start_m
    if diff < 0:
        # Crosses midnight / wraps around 24 hours
        diff += 24 * 60
    return diff


def _calculate_rule_priority(
    rule: TimeRuleDefinition,
    worker: WorkerContext,
) -> float:
    """Calculate priority score for sorting matching rules.

    EMPLOYEE (400) > TEAM (300 + relationship bonus) > DRIVERS (200) > COMPANY (100)
    OUTDOOR_ONLY / INDOOR_ONLY (+20) > ALL (+10)
    """
    scope_str = str(rule.scope_type).upper()
    if scope_str == TimeRuleScope.EMPLOYEE:
        base_score = 400.0
    elif scope_str == TimeRuleScope.TEAM:
        # Check manager relationship bonus
        # SUPERVISOR = +30, SUPERINTENDENT = +20, ENGINEER = +10
        rel_bonus = 10.0
        for m_id, rel in worker.manager_links:
            if rule.scope_employee_id == m_id:
                rel_upper = rel.upper()
                if rel_upper == "SUPERVISOR":
                    rel_bonus = max(rel_bonus, 30.0)
                elif rel_upper == "SUPERINTENDENT":
                    rel_bonus = max(rel_bonus, 20.0)
                elif rel_upper == "ENGINEER":
                    rel_bonus = max(rel_bonus, 10.0)
        base_score = 300.0 + rel_bonus
    elif scope_str == TimeRuleScope.DRIVERS:
        base_score = 200.0
    else:  # COMPANY
        base_score = 100.0

    applies_str = str(rule.applies_to).upper()
    if applies_str in (TimeRuleAppliesTo.OUTDOOR_ONLY, TimeRuleAppliesTo.INDOOR_ONLY):
        applies_score = 20.0
    else:
        applies_score = 10.0

    return base_score + applies_score


def resolve_time_schedule(
    rules: list[TimeRuleDefinition],
    worker: WorkerContext,
    target_date: date,
    is_outdoor: bool | None = None,
) -> ResolvedTimeSchedule:
    """Resolve effective planned schedule for a worker on a given date.

    Implements:
    - Precedence: EMPLOYEE > TEAM > DRIVERS > COMPANY
    - Specificity: OUTDOOR_ONLY / INDOOR_ONLY > ALL
    - Date filtering: start_date <= target_date <= end_date
    - Field inheritance: blanks inherit from lower-priority rules
    - Explainability: tracks matched candidates and field sources
    """
    evaluations: list[tuple[TimeRuleDefinition, float, bool, str, list[str]]] = []

    manager_ids = {m_id for m_id, _ in worker.manager_links}

    for rule in rules:
        reasons: list[str] = []
        is_match = True

        if not rule.is_active:
            is_match = False
            reasons.append("Rule is inactive")

        # Date check
        if rule.start_date > target_date:
            is_match = False
            reasons.append(f"Starts after target date ({rule.start_date} > {target_date})")
        elif rule.end_date is not None and rule.end_date < target_date:
            is_match = False
            reasons.append(f"Expired before target date ({rule.end_date} < {target_date})")

        # Country check
        if rule.country is not None and rule.country.upper() != worker.country.upper():
            is_match = False
            reasons.append(f"Country mismatch ({rule.country} != {worker.country})")

        # Scope check
        scope_str = str(rule.scope_type).upper()
        if scope_str == TimeRuleScope.EMPLOYEE:
            if rule.scope_employee_id != worker.employee_id:
                is_match = False
                reasons.append("Applies to a different employee")
        elif scope_str == TimeRuleScope.TEAM:
            if rule.scope_employee_id not in manager_ids:
                is_match = False
                reasons.append("Manager is not in employee's reporting chain")
        elif scope_str == TimeRuleScope.DRIVERS:
            if not worker.is_driver:
                is_match = False
                reasons.append("Worker is not a driver")
        elif scope_str == TimeRuleScope.COMPANY:
            pass  # always in scope
        else:
            is_match = False
            reasons.append(f"Unknown scope type {rule.scope_type}")

        # Applies to / environment check
        applies_str = str(rule.applies_to).upper()
        if applies_str == TimeRuleAppliesTo.OUTDOOR_ONLY:
            if is_outdoor is False:
                is_match = False
                reasons.append("Rule is OUTDOOR_ONLY but job is indoor")
        elif applies_str == TimeRuleAppliesTo.INDOOR_ONLY:
            if is_outdoor is True:
                is_match = False
                reasons.append("Rule is INDOOR_ONLY but job is outdoor")

        score = _calculate_rule_priority(rule, worker)
        status = "MATCH" if is_match else "EXCLUDED"
        evaluations.append((rule, score, is_match, status, reasons))

    # Sort matching candidates:
    # 1. priority score descending
    # 2. start_date descending (more recent season wins)
    # 3. str(rule.id) for stable tie-breaker
    matching = [e for e in evaluations if e[2]]
    matching.sort(
        key=lambda item: (
            item[1],  # priority score
            item[0].start_date.toordinal(),  # later start date
            str(item[0].id),
        ),
        reverse=True,
    )

    # Track winning fields
    acc_start: time | None = None
    first_site: time | None = None
    break_min: int | None = None
    last_site: time | None = None
    acc_end: time | None = None
    std_change_min: int | None = None

    winning_sources: dict[str, WinningFieldSource] = {}
    primary_winner_id: UUID | str | None = None
    primary_winner_name: str | None = None

    rule_usage_count: dict[UUID | str, int] = {}

    if matching:
        primary_rule = matching[0][0]
        primary_winner_id = primary_rule.id
        primary_winner_name = primary_rule.name

    for rule, _score, _is_match, _st, _reasons in matching:
        rule_id = rule.id
        rule_name = rule.name
        scope_str = str(rule.scope_type).upper()

        if acc_start is None and rule.accommodation_start is not None:
            acc_start = rule.accommodation_start
            winning_sources["accommodation_start"] = WinningFieldSource(
                rule_id=rule_id,
                rule_name=rule_name,
                scope_type=scope_str,
                field_name="accommodation_start",
                value=acc_start.strftime("%H:%M"),
            )
            rule_usage_count[rule_id] = rule_usage_count.get(rule_id, 0) + 1

        if first_site is None and rule.first_site_start is not None:
            first_site = rule.first_site_start
            winning_sources["first_site_start"] = WinningFieldSource(
                rule_id=rule_id,
                rule_name=rule_name,
                scope_type=scope_str,
                field_name="first_site_start",
                value=first_site.strftime("%H:%M"),
            )
            rule_usage_count[rule_id] = rule_usage_count.get(rule_id, 0) + 1

        if break_min is None and rule.break_minutes is not None:
            break_min = rule.break_minutes
            winning_sources["break_minutes"] = WinningFieldSource(
                rule_id=rule_id,
                rule_name=rule_name,
                scope_type=scope_str,
                field_name="break_minutes",
                value=break_min,
            )
            rule_usage_count[rule_id] = rule_usage_count.get(rule_id, 0) + 1

        if last_site is None and rule.last_site_end is not None:
            last_site = rule.last_site_end
            winning_sources["last_site_end"] = WinningFieldSource(
                rule_id=rule_id,
                rule_name=rule_name,
                scope_type=scope_str,
                field_name="last_site_end",
                value=last_site.strftime("%H:%M"),
            )
            rule_usage_count[rule_id] = rule_usage_count.get(rule_id, 0) + 1

        if acc_end is None and rule.accommodation_end is not None:
            acc_end = rule.accommodation_end
            winning_sources["accommodation_end"] = WinningFieldSource(
                rule_id=rule_id,
                rule_name=rule_name,
                scope_type=scope_str,
                field_name="accommodation_end",
                value=acc_end.strftime("%H:%M"),
            )
            rule_usage_count[rule_id] = rule_usage_count.get(rule_id, 0) + 1

        if std_change_min is None and rule.standard_hours_change_minutes is not None:
            std_change_min = rule.standard_hours_change_minutes
            winning_sources["standard_hours_change_minutes"] = WinningFieldSource(
                rule_id=rule_id,
                rule_name=rule_name,
                scope_type=scope_str,
                field_name="standard_hours_change_minutes",
                value=std_change_min,
            )
            rule_usage_count[rule_id] = rule_usage_count.get(rule_id, 0) + 1

    # Defaults if completely unassigned
    resolved_break = break_min if break_min is not None else 0
    resolved_std_change = std_change_min if std_change_min is not None else 0

    # Planned time calculations
    # Client example: 05:00 / 06:00 / 0:30 / 15:30 / 17:00 => 12:00 total, 09:00 worked
    # If no accommodation, total time = last_site - first_site (BR-AT-16)
    if worker.has_accommodation:
        planned_total = time_diff_minutes(acc_start, acc_end)
    else:
        planned_total = time_diff_minutes(first_site, last_site)

    elapsed_site = time_diff_minutes(first_site, last_site)
    planned_worked = max(0, elapsed_site - resolved_break)

    # Build MatchedRuleExplanation list
    matched_explanations: list[MatchedRuleExplanation] = []
    for rule, score, is_match, _status, reasons in evaluations:
        if is_match:
            usage = rule_usage_count.get(rule.id, 0)
            if rule.id == primary_winner_id:
                final_status = "WON"
            elif usage > 0:
                final_status = "PARTIAL_INHERITED"
            else:
                final_status = "SHADOWED"
        else:
            final_status = "EXCLUDED"

        matched_explanations.append(
            MatchedRuleExplanation(
                rule_id=rule.id,
                rule_name=rule.name,
                scope_type=str(rule.scope_type),
                applies_to=str(rule.applies_to),
                priority_score=score,
                is_match=is_match,
                status=final_status,
                reasons=reasons,
            )
        )

    return ResolvedTimeSchedule(
        accommodation_start=acc_start,
        first_site_start=first_site,
        break_minutes=resolved_break,
        last_site_end=last_site,
        accommodation_end=acc_end,
        planned_total_minutes=planned_total,
        planned_worked_minutes=planned_worked,
        standard_hours_change_minutes=resolved_std_change,
        has_accommodation=worker.has_accommodation,
        winning_rule_id=primary_winner_id,
        winning_rule_name=primary_winner_name,
        winning_sources=winning_sources,
        matched_rules=matched_explanations,
    )
