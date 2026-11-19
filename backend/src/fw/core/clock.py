from datetime import UTC, date, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo


class Clock(Protocol):
    """Clock protocol for UTC instants."""

    def now(self) -> datetime:
        """Return the current instant as timezone-aware UTC datetime."""
        ...


class SystemClock:
    """Production clock returning real-world UTC time."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock:
    """Deterministic frozen clock for testing."""

    def __init__(self, fixed_time: datetime | None = None) -> None:
        if fixed_time is None:
            self._time = datetime(2026, 11, 2, 8, 0, 0, tzinfo=UTC)
        else:
            if fixed_time.tzinfo is None:
                self._time = fixed_time.replace(tzinfo=UTC)
            else:
                self._time = fixed_time.astimezone(UTC)

    def now(self) -> datetime:
        return self._time

    def set(self, new_time: datetime) -> None:
        if new_time.tzinfo is None:
            self._time = new_time.replace(tzinfo=UTC)
        else:
            self._time = new_time.astimezone(UTC)

    def advance(self, minutes: int = 0, seconds: int = 0, hours: int = 0) -> None:
        self._time += timedelta(minutes=minutes, seconds=seconds, hours=hours)


_COUNTRY_TIMEZONES: dict[str, str] = {
    "AE": "Asia/Dubai",
    "SA": "Asia/Riyadh",
}

_default_clock: Clock = SystemClock()


def set_system_clock(clock: Clock) -> None:
    """Set the system clock (useful in unit testing)."""
    global _default_clock
    _default_clock = clock


def get_system_clock() -> Clock:
    """Get the current system clock."""
    return _default_clock


def get_country_timezone(country: str | None = None) -> ZoneInfo:
    """Return timezone for given country, defaulting to Asia/Dubai."""
    tz_name = _COUNTRY_TIMEZONES.get((country or "").upper(), "Asia/Dubai")
    return ZoneInfo(tz_name)


def site_now(country: str | None = None) -> datetime:
    """Return current localized datetime in site's timezone."""
    tz = get_country_timezone(country)
    return _default_clock.now().astimezone(tz)


def site_today(country: str | None = None) -> date:
    """Return current calendar date in site's timezone."""
    return site_now(country).date()
