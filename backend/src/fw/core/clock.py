from datetime import UTC, datetime, timedelta
from typing import Protocol


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
