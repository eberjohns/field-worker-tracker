from datetime import UTC, datetime

from fw.core.clock import FrozenClock, SystemClock


def test_system_clock():
    clock = SystemClock()
    t1 = clock.now()
    assert t1.tzinfo is not None
    assert t1.tzinfo == UTC


def test_frozen_clock_advance():
    start = datetime(2026, 11, 2, 9, 0, 0, tzinfo=UTC)
    clock = FrozenClock(start)
    assert clock.now() == start

    clock.advance(minutes=15)
    assert clock.now() == datetime(2026, 11, 2, 9, 15, 0, tzinfo=UTC)

    clock.advance(hours=1)
    assert clock.now() == datetime(2026, 11, 2, 10, 15, 0, tzinfo=UTC)
