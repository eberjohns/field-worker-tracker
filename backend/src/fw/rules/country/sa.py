from datetime import date
from decimal import ROUND_HALF_UP, Decimal

HOURS_DIVISOR = Decimal("208")
OT1_MULTIPLIER = Decimal("1.25")
OT2_MULTIPLIER = Decimal("1.50")
CENTS = Decimal("0.01")


class SaudiCountryPack:
    """Kingdom of Saudi Arabia country rule pack."""

    @property
    def country_code(self) -> str:
        return "SA"

    @property
    def timezone_name(self) -> str:
        return "Asia/Riyadh"

    @property
    def currency(self) -> str:
        return "SAR"

    @property
    def weekend_days(self) -> tuple[int, ...]:
        # Friday (4) and Saturday (5)
        return (4, 5)

    @property
    def ot2_weekdays(self) -> tuple[int, ...]:
        # Friday (4) is weekly off / OT2 day in KSA
        return (4,)

    def get_public_holidays(self, year: int) -> set[date]:
        # Saudi fixed national holidays
        return {
            date(year, 2, 22),  # Founding Day
            date(year, 9, 23),  # National Day
        }

    def calculate_ot1_rate(self, basic_salary: Decimal) -> Decimal:
        rate = (basic_salary / HOURS_DIVISOR) * OT1_MULTIPLIER
        return rate.quantize(CENTS, rounding=ROUND_HALF_UP)

    def calculate_ot2_rate(self, basic_salary: Decimal) -> Decimal:
        rate = (basic_salary / HOURS_DIVISOR) * OT2_MULTIPLIER
        return rate.quantize(CENTS, rounding=ROUND_HALF_UP)
