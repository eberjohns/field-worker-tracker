from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from math import atan2, cos, radians, sin, sqrt
from uuid import UUID


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on the Earth in meters."""
    r = 6371000.0  # Earth radius in meters
    phi1, phi2 = radians(lat1), radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)

    a = sin(delta_phi / 2.0) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2.0) ** 2
    c = 2.0 * atan2(sqrt(a), sqrt(1.0 - a))
    return r * c


@dataclass(frozen=True)
class EventForGap:
    event_id: UUID
    event_type: str  # LOCATION_DISABLED, LOCATION_ENABLED
    event_timestamp_utc: datetime
    location_captured_at_utc: datetime | None
    latitude: Decimal | None
    longitude: Decimal | None
    server_site_id: UUID | None


@dataclass
class ConstructedGap:
    work_date: date
    disabled_event_id: UUID
    enabled_event_id: UUID | None
    started_at: datetime
    ended_at: datetime | None
    duration_minutes: int
    disabled_latitude: Decimal | None
    disabled_longitude: Decimal | None
    disabled_location_captured_at: datetime | None
    resumed_latitude: Decimal | None
    resumed_longitude: Decimal | None
    distance_between_m: float | None
    start_inside_site_id: UUID | None
    end_inside_site_id: UUID | None
    is_inferred: bool


def build_gaps_for_day(
    events: list[EventForGap],
    work_date: date,
    day_end_timestamp: datetime | None = None,
) -> list[ConstructedGap]:
    """Process location state change events to build tracking gaps."""
    sorted_events = sorted(events, key=lambda e: e.event_timestamp_utc)
    gaps: list[ConstructedGap] = []
    open_gap: ConstructedGap | None = None

    for ev in sorted_events:
        ev_type = ev.event_type.upper()
        if ev_type == "LOCATION_DISABLED":
            if open_gap is None:
                open_gap = ConstructedGap(
                    work_date=work_date,
                    disabled_event_id=ev.event_id,
                    enabled_event_id=None,
                    started_at=ev.event_timestamp_utc,
                    ended_at=None,
                    duration_minutes=0,
                    disabled_latitude=ev.latitude,
                    disabled_longitude=ev.longitude,
                    disabled_location_captured_at=ev.location_captured_at_utc,
                    resumed_latitude=None,
                    resumed_longitude=None,
                    distance_between_m=None,
                    start_inside_site_id=ev.server_site_id,
                    end_inside_site_id=None,
                    is_inferred=False,
                )
        elif ev_type == "LOCATION_ENABLED":
            if open_gap is not None:
                open_gap.enabled_event_id = ev.event_id
                open_gap.ended_at = ev.event_timestamp_utc
                open_gap.resumed_latitude = ev.latitude
                open_gap.resumed_longitude = ev.longitude
                open_gap.end_inside_site_id = ev.server_site_id
                open_gap.duration_minutes = max(
                    0,
                    int((open_gap.ended_at - open_gap.started_at).total_seconds() // 60),
                )
                if (
                    open_gap.disabled_latitude is not None
                    and open_gap.disabled_longitude is not None
                    and ev.latitude is not None
                    and ev.longitude is not None
                ):
                    open_gap.distance_between_m = haversine_distance_m(
                        float(open_gap.disabled_latitude),
                        float(open_gap.disabled_longitude),
                        float(ev.latitude),
                        float(ev.longitude),
                    )
                gaps.append(open_gap)
                open_gap = None

    # If gap is still open at end of day, close as inferred [DEC-04]
    if open_gap is not None:
        end_time = day_end_timestamp or open_gap.started_at
        open_gap.ended_at = end_time
        open_gap.is_inferred = True
        open_gap.duration_minutes = max(
            0,
            int((open_gap.ended_at - open_gap.started_at).total_seconds() // 60),
        )
        gaps.append(open_gap)

    return gaps


def calculate_unaccounted_time_minutes(
    gaps: list[ConstructedGap],
    shift_start_at: datetime | None,
    shift_end_at: datetime | None,
    break_minutes_used: int,
) -> int:
    """Compute unaccounted minutes: total tracking-off minutes inside shift span minus break used."""
    if not gaps or shift_start_at is None or shift_end_at is None or shift_start_at >= shift_end_at:
        return 0

    total_off_in_shift_sec = 0.0
    for g in gaps:
        g_start = g.started_at
        g_end = g.ended_at or shift_end_at
        # Overlap with shift interval [shift_start_at, shift_end_at]
        overlap_start = max(shift_start_at, g_start)
        overlap_end = min(shift_end_at, g_end)
        if overlap_end > overlap_start:
            total_off_in_shift_sec += (overlap_end - overlap_start).total_seconds()

    total_off_minutes = int(total_off_in_shift_sec // 60)
    return max(0, total_off_minutes - break_minutes_used)
