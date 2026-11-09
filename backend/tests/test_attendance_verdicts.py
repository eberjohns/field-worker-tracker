from datetime import UTC, datetime
from uuid import uuid4

from fw.rules.attendance import (
    EventFlag,
    EventVerdictInput,
    ServerVerdict,
    evaluate_event_verdict,
)


def test_evaluate_inside_verdict():
    ev_id = uuid4()
    site_id = uuid4()
    now = datetime(2026, 11, 3, 6, 0, tzinfo=UTC)

    res = evaluate_event_verdict(
        EventVerdictInput(
            event_id=ev_id,
            event_type="ENTRY",
            event_timestamp_utc=now,
            device_clock_utc=now,
            server_received_at=now,
            latitude=25.1,
            longitude=55.2,
            accuracy_meters=15.0,
            is_mock_location=False,
            is_inside_polygon=True,
            distance_to_polygon_m=0.0,
            matched_site_id=site_id,
            matched_accommodation_id=None,
            has_assigned_polygon=True,
        )
    )

    assert res.verdict == ServerVerdict.INSIDE
    assert res.flags == []
    assert res.server_site_id == site_id


def test_evaluate_borderline_verdict():
    ev_id = uuid4()
    site_id = uuid4()
    now = datetime(2026, 11, 3, 6, 0, tzinfo=UTC)

    # Outside polygon, distance 20m, but accuracy is 30m -> BORDERLINE
    res = evaluate_event_verdict(
        EventVerdictInput(
            event_id=ev_id,
            event_type="PING",
            event_timestamp_utc=now,
            device_clock_utc=now,
            server_received_at=now,
            latitude=25.1,
            longitude=55.2,
            accuracy_meters=30.0,
            is_mock_location=False,
            is_inside_polygon=False,
            distance_to_polygon_m=20.0,
            matched_site_id=site_id,
            matched_accommodation_id=None,
            has_assigned_polygon=True,
        )
    )

    assert res.verdict == ServerVerdict.BORDERLINE
    assert EventFlag.BORDERLINE_LOCATION.value in res.flags


def test_evaluate_outside_verdict():
    ev_id = uuid4()
    site_id = uuid4()
    now = datetime(2026, 11, 3, 6, 0, tzinfo=UTC)

    # Outside polygon, distance 50m, accuracy is 10m -> OUTSIDE
    res = evaluate_event_verdict(
        EventVerdictInput(
            event_id=ev_id,
            event_type="PING",
            event_timestamp_utc=now,
            device_clock_utc=now,
            server_received_at=now,
            latitude=25.1,
            longitude=55.2,
            accuracy_meters=10.0,
            is_mock_location=False,
            is_inside_polygon=False,
            distance_to_polygon_m=50.0,
            matched_site_id=site_id,
            matched_accommodation_id=None,
            has_assigned_polygon=True,
        )
    )

    assert res.verdict == ServerVerdict.OUTSIDE


def test_clock_skew_and_low_accuracy_flags():
    ev_id = uuid4()
    device_now = datetime(2026, 11, 3, 6, 0, tzinfo=UTC)
    server_now = datetime(2026, 11, 3, 6, 5, tzinfo=UTC)  # 300s skew > 120s

    res = evaluate_event_verdict(
        EventVerdictInput(
            event_id=ev_id,
            event_type="ENTRY",
            event_timestamp_utc=device_now,
            device_clock_utc=device_now,
            server_received_at=server_now,
            latitude=25.1,
            longitude=55.2,
            accuracy_meters=150.0,  # > 100m -> LOW_ACCURACY
            is_mock_location=True,  # MOCK_LOCATION
            is_inside_polygon=True,
            distance_to_polygon_m=0.0,
            matched_site_id=uuid4(),
            matched_accommodation_id=None,
            has_assigned_polygon=True,
        )
    )

    assert res.device_clock_skew_s == 300
    assert EventFlag.CLOCK_SKEW.value in res.flags
    assert EventFlag.LOW_ACCURACY.value in res.flags
    assert EventFlag.MOCK_LOCATION.value in res.flags
