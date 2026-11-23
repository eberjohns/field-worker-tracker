"""Job budget and man-hours (DEC-59, ADR-029). Pure rules: no database, no settings lookups.

Planned cost of a job item = planned hours x hourly rate of its grade.

- Monthly cost of a grade is built with the same formulas payroll uses for actual staff cost:
  salary portion (basic + special allowance + fixed OT + bonus + telephone + housing/transport)
  + provisions + gratuity (basic / 365 x 30) + leave salary (basic / 12), then HR overhead on top.
  The plan uses the revision line's own provisions (owner, 23 Nov 2026); payroll uses settings.
- Hourly rate = monthly final cost / standard_ot_divisor_hours.
- Hours are pro-rated by day: an item counts only on days inside the requested period, the item's
  start/end dates and the worksite contract dates. Each day is worth 1 / (length of the contract
  year it falls in), so a full contract year gives exactly the annual figure.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fw.rules.jobs.frequency import calculate_expected_activities_per_year
from fw.rules.payroll.formulas import (
    calculate_final_total_staff_cost,
    calculate_gratuity,
    calculate_hr_overhead,
    calculate_leave_salary,
    calculate_per_month_provision,
    calculate_total_staff_cost,
    round_money,
)
from fw.rules.payroll.salary import calculate_salary_portion

MISSING_GRADE_RATE = "MISSING_GRADE_RATE"
PROVISIONS_DIFFER_FROM_PAYROLL = "PROVISIONS_DIFFER_FROM_PAYROLL"

_HOURS_Q = Decimal("0.001")
_RATE_Q = Decimal("0.0001")


def _d(v: Decimal | int | float | str | None) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


@dataclass(frozen=True)
class GradeLine:
    """The money fields of one salary revision line (per month)."""

    basic_salary: Decimal
    special_allowance: Decimal = Decimal("0")
    fixed_ot_amount: Decimal = Decimal("0")
    bonus: Decimal = Decimal("0")
    telephone_allowance: Decimal = Decimal("0")
    housing_transport_allowance: Decimal = Decimal("0")
    visa_provision: Decimal = Decimal("0")
    air_ticket_provision: Decimal = Decimal("0")
    uniform_provision: Decimal = Decimal("0")
    medical_provision: Decimal = Decimal("0")
    accommodation_provision: Decimal = Decimal("0")
    transportation_provision: Decimal = Decimal("0")

    @property
    def provisions_total(self) -> Decimal:
        return round_money(
            _d(self.visa_provision)
            + _d(self.air_ticket_provision)
            + _d(self.uniform_provision)
            + _d(self.medical_provision)
            + _d(self.accommodation_provision)
            + _d(self.transportation_provision)
        )


@dataclass(frozen=True)
class GradeMonthlyCost:
    salary_portion: Decimal
    provisions: Decimal
    gratuity: Decimal
    leave_salary: Decimal
    total_staff_cost: Decimal
    hr_overhead: Decimal
    final_cost: Decimal


def grade_monthly_cost(line: GradeLine, hr_overhead_rate: Decimal) -> GradeMonthlyCost:
    """Monthly cost of one person of this grade, built exactly like payroll's final_cost
    (no overtime, no shortfall), but with the revision line's own provisions."""
    portion = calculate_salary_portion(
        basic=line.basic_salary,
        special_allowance=line.special_allowance,
        fixed_ot=line.fixed_ot_amount,
        bonus=line.bonus,
        telephone_allowance=line.telephone_allowance,
        housing_transport_allowance=line.housing_transport_allowance,
    )
    gratuity = calculate_gratuity(line.basic_salary)
    leave_salary = calculate_leave_salary(line.basic_salary)
    per_month_prov = calculate_per_month_provision(line.provisions_total, gratuity, leave_salary)
    staff_cost = calculate_total_staff_cost(portion, per_month_prov)
    hr_oh = calculate_hr_overhead(staff_cost, _d(hr_overhead_rate))
    return GradeMonthlyCost(
        salary_portion=portion,
        provisions=line.provisions_total,
        gratuity=gratuity,
        leave_salary=leave_salary,
        total_staff_cost=staff_cost,
        hr_overhead=hr_oh,
        final_cost=calculate_final_total_staff_cost(staff_cost, hr_oh),
    )


def grade_hourly_rate(
    line: GradeLine, hr_overhead_rate: Decimal, divisor_hours: Decimal
) -> Decimal:
    """Hourly rate = monthly final cost / standard_ot_divisor_hours (4 decimals)."""
    div = _d(divisor_hours)
    if div <= 0:
        raise ValueError("standard_ot_divisor_hours must be greater than 0.")
    final = grade_monthly_cost(line, hr_overhead_rate).final_cost
    return (final / div).quantize(_RATE_Q, rounding=ROUND_HALF_UP)


# --- Contract years and periods -----------------------------------------------------------------


def _add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29 Feb -> 28 Feb
        return d.replace(year=d.year + years, day=28)


def contract_year_containing(day: date, contract_start: date | None) -> tuple[date, date]:
    """The contract year (anniversary to anniversary) that contains ``day``.

    Without a contract start date the calendar year is used.
    """
    anchor = contract_start or date(day.year, 1, 1)
    years = day.year - anchor.year
    start = _add_years(anchor, years)
    if start > day:
        start = _add_years(anchor, years - 1)
    nxt = _add_years(start, 1)
    if nxt <= day:  # can happen around 29 Feb
        start, nxt = nxt, _add_years(start, 2)
    return start, nxt - timedelta(days=1)


def _overlap(
    a_from: date, a_to: date, b_from: date | None, b_to: date | None
) -> tuple[date, date] | None:
    lo = max(a_from, b_from) if b_from else a_from
    hi = min(a_to, b_to) if b_to else a_to
    return (lo, hi) if lo <= hi else None


def active_window(
    period_from: date,
    period_to: date,
    item_start: date | None,
    item_end: date | None,
    contract_start: date | None,
    contract_end: date | None,
) -> tuple[date, date] | None:
    """Days of the period on which the item runs (item dates and contract dates)."""
    win = _overlap(period_from, period_to, item_start, item_end)
    if win is None:
        return None
    return _overlap(win[0], win[1], contract_start, contract_end)


def year_fraction(window_from: date, window_to: date, contract_start: date | None) -> Decimal:
    """Sum over the days in the window of 1 / (length of their contract year)."""
    total = Decimal("0")
    cur = window_from
    while cur <= window_to:
        y_from, y_to = contract_year_containing(cur, contract_start)
        seg_to = min(window_to, y_to)
        days = (seg_to - cur).days + 1
        year_len = (y_to - y_from).days + 1
        total += Decimal(days) / Decimal(year_len)
        cur = seg_to + timedelta(days=1)
    return total


# --- Job items ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ItemSchedule:
    frequency_unit: str
    occurrences_per_period: Decimal
    period_interval: int
    required_staff_count: int
    hours_per_occurrence_per_staff: Decimal
    start_date: date | None
    end_date: date | None


@dataclass
class ItemPlan:
    activities_per_year: Decimal
    full_year_hours: Decimal
    period_from: date
    period_to: date
    active_days: int
    hours: Decimal
    hourly_rate: Decimal | None
    cost: Decimal | None
    warnings: list[str] = field(default_factory=list)


def full_year_hours(item: ItemSchedule) -> tuple[Decimal, Decimal]:
    """(activities per year, man-hours per full year), honouring period_interval."""
    activities = calculate_expected_activities_per_year(
        item.frequency_unit, item.occurrences_per_period, item.period_interval or 1
    )
    hours = (
        activities * Decimal(item.required_staff_count) * _d(item.hours_per_occurrence_per_staff)
    )
    return activities, hours.quantize(_HOURS_Q, rounding=ROUND_HALF_UP)


def plan_item(
    item: ItemSchedule,
    hourly_rate: Decimal | None,
    period_from: date,
    period_to: date,
    contract_start: date | None,
    contract_end: date | None,
) -> ItemPlan:
    """Planned hours and cost of one job item for a period.

    ``hourly_rate`` None means the grade has no line in the revision: hours are still returned,
    cost is None and the MISSING_GRADE_RATE warning is set (the caller leaves the item out of
    money totals).
    """
    activities, annual = full_year_hours(item)
    win = active_window(
        period_from, period_to, item.start_date, item.end_date, contract_start, contract_end
    )
    if win is None:
        hours = Decimal("0.000")
        days = 0
    else:
        frac = year_fraction(win[0], win[1], contract_start)
        hours = (annual * frac).quantize(_HOURS_Q, rounding=ROUND_HALF_UP)
        days = (win[1] - win[0]).days + 1
    warnings: list[str] = []
    cost: Decimal | None = None
    if hourly_rate is None:
        warnings.append(MISSING_GRADE_RATE)
    else:
        cost = round_money(hours * hourly_rate)
    return ItemPlan(
        activities_per_year=activities,
        full_year_hours=annual,
        period_from=period_from,
        period_to=period_to,
        active_days=days,
        hours=hours,
        hourly_rate=hourly_rate,
        cost=cost,
        warnings=warnings,
    )


def month_ranges(period_from: date, period_to: date) -> list[tuple[date, date]]:
    """Calendar-month slices of a period (first and last slice may be partial)."""
    out: list[tuple[date, date]] = []
    cur = period_from
    while cur <= period_to:
        nxt = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
        end = min(period_to, nxt - timedelta(days=1))
        out.append((cur, end))
        cur = end + timedelta(days=1)
    return out


def split_by_weights(amount: Decimal, weights: dict[object, Decimal]) -> dict[object, Decimal]:
    """Split money in proportion to weights; the rounding remainder goes to the largest weight."""
    total_w = sum(weights.values(), Decimal("0"))
    if total_w <= 0 or not weights:
        return {}
    shares = {k: round_money(amount * w / total_w) for k, w in weights.items()}
    diff = round_money(amount) - sum(shares.values(), Decimal("0"))
    if diff:
        biggest = max(weights, key=lambda k: weights[k])
        shares[biggest] = round_money(shares[biggest] + diff)
    return shares


def variance(planned: Decimal, actual: Decimal) -> tuple[Decimal, Decimal | None]:
    """(actual - planned, percent of planned or None when nothing was planned)."""
    diff = actual - planned
    pct = round_money(diff / planned * Decimal("100")) if planned > 0 else None
    return diff, pct
