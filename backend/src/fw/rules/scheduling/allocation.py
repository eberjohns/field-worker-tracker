"""Pure business logic for worker capacity and allocation calculations."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class EffectiveStandardHours:
    """Worker standard hours with effective time rule adjustments applied."""

    base_standard_hours: Decimal
    adjustment_minutes: int  # e.g. -120 for Ramadan
    effective_daily_standard_hours: Decimal
    effective_weekly_standard_hours: Decimal
    effective_monthly_standard_hours: Decimal


def compute_effective_standard_hours(
    base_standard_hours: Decimal | None,
    adjustment_minutes: int | None = 0,
    working_days_per_week: int = 6,
    working_days_per_month: int = 26,
) -> EffectiveStandardHours:
    """Calculate effective standard hours for day/week/month."""
    base = base_standard_hours if base_standard_hours is not None else Decimal("8.0")
    adj_min = adjustment_minutes or 0
    adj_hours = Decimal(adj_min) / Decimal("60")
    daily_effective = max(Decimal("0.0"), base + adj_hours)
    weekly_effective = daily_effective * Decimal(working_days_per_week)
    monthly_effective = daily_effective * Decimal(working_days_per_month)

    return EffectiveStandardHours(
        base_standard_hours=base,
        adjustment_minutes=adj_min,
        effective_daily_standard_hours=daily_effective,
        effective_weekly_standard_hours=weekly_effective,
        effective_monthly_standard_hours=monthly_effective,
    )


@dataclass(frozen=True)
class WorkerAllocationSummary:
    """Summary of allocated hours vs standard hours across time buckets."""

    today_allocated: Decimal
    today_standard: Decimal
    today_diff: Decimal
    today_is_over: bool
    today_is_under: bool

    week_allocated: Decimal
    week_standard: Decimal
    week_diff: Decimal
    week_is_over: bool
    week_is_under: bool

    month_allocated: Decimal
    month_standard: Decimal
    month_diff: Decimal
    month_is_over: bool
    month_is_under: bool


def calculate_allocation_summary(
    today_allocated: Decimal,
    week_allocated: Decimal,
    month_allocated: Decimal,
    effective_hours: EffectiveStandardHours,
) -> WorkerAllocationSummary:
    """Build allocation summary with over/under flags."""
    today_diff = today_allocated - effective_hours.effective_daily_standard_hours
    week_diff = week_allocated - effective_hours.effective_weekly_standard_hours
    month_diff = month_allocated - effective_hours.effective_monthly_standard_hours

    return WorkerAllocationSummary(
        today_allocated=today_allocated,
        today_standard=effective_hours.effective_daily_standard_hours,
        today_diff=today_diff,
        today_is_over=today_diff > Decimal("0"),
        today_is_under=today_diff < Decimal("0"),
        week_allocated=week_allocated,
        week_standard=effective_hours.effective_weekly_standard_hours,
        week_diff=week_diff,
        week_is_over=week_diff > Decimal("0"),
        week_is_under=week_diff < Decimal("0"),
        month_allocated=month_allocated,
        month_standard=effective_hours.effective_monthly_standard_hours,
        month_diff=month_diff,
        month_is_over=month_diff > Decimal("0"),
        month_is_under=month_diff < Decimal("0"),
    )

