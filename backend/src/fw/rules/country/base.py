from datetime import date
from decimal import Decimal
from typing import Protocol


class CountryRulePack(Protocol):
    """Protocol governing all country-specific business rules."""

    @property
    def country_code(self) -> str: ...

    @property
    def timezone_name(self) -> str: ...

    @property
    def currency(self) -> str: ...

    @property
    def weekend_days(self) -> tuple[int, ...]:
        """0 = Monday, 6 = Sunday."""
        ...

    @property
    def ot2_weekdays(self) -> tuple[int, ...]:
        """Weekdays designated as OT2 by default (e.g. Sunday in UAE)."""
        ...

    def get_public_holidays(self, year: int) -> set[date]: ...

    def calculate_ot1_rate(self, basic_salary: Decimal) -> Decimal:
        """OT1 = basic / 208 * 1.25 per DEC-01."""
        ...

    def calculate_ot2_rate(self, basic_salary: Decimal) -> Decimal:
        """OT2 = basic / 208 * 1.50 per DEC-01."""
        ...
