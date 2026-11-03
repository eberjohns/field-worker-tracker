from datetime import date
from decimal import ROUND_HALF_UP, Decimal

HOURS_DIVISOR = Decimal("208")
OT1_MULTIPLIER = Decimal("1.25")
OT2_MULTIPLIER = Decimal("1.50")
CENTS = Decimal("0.01")


class UAECountryPack:
    """United Arab Emirates country rule pack."""

    @property
    def country_code(self) -> str:
        return "AE"

    @property
    def timezone_name(self) -> str:
        return "Asia/Dubai"

    @property
    def currency(self) -> str:
        return "AED"

    @property
    def weekend_days(self) -> tuple[int, ...]:
        # Saturday (5) and Sunday (6)
        return (5, 6)

    @property
    def ot2_weekdays(self) -> tuple[int, ...]:
        # Sunday (6) is default OT2 weekday per DEC-01
        return (6,)

    def get_public_holidays(self, year: int) -> set[date]:
        # Standard fixed UAE statutory holidays (lunar Islamic holidays injected via database/settings)
        return {
            date(year, 1, 1),  # New Year's Day
            date(year, 12, 1),  # Commemoration Day
            date(year, 12, 2),  # National Day
            date(year, 12, 3),  # National Day holiday
        }

    def calculate_ot1_rate(self, basic_salary: Decimal) -> Decimal:
        rate = (basic_salary / HOURS_DIVISOR) * OT1_MULTIPLIER
        return rate.quantize(CENTS, rounding=ROUND_HALF_UP)

    def calculate_ot2_rate(self, basic_salary: Decimal) -> Decimal:
        rate = (basic_salary / HOURS_DIVISOR) * OT2_MULTIPLIER
        return rate.quantize(CENTS, rounding=ROUND_HALF_UP)
