from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ServerVerdict(StrEnum):
    INSIDE = "INSIDE"
    BORDERLINE = "BORDERLINE"
    OUTSIDE = "OUTSIDE"
    NO_POLYGON = "NO_POLYGON"


class EventFlag(StrEnum):
    LOW_ACCURACY = "LOW_ACCURACY"
    MOCK_LOCATION = "MOCK_LOCATION"
    UNKNOWN_SITE = "UNKNOWN_SITE"
    ENTRY_OUTSIDE_POLYGON = "ENTRY_OUTSIDE_POLYGON"
    EXIT_INSIDE_POLYGON = "EXIT_INSIDE_POLYGON"
    CLOCK_SKEW = "CLOCK_SKEW"
    BORDERLINE_LOCATION = "BORDERLINE_LOCATION"


@dataclass(frozen=True)
class EventVerdictInput:
    event_id: UUID
    event_type: str  # ENTRY, EXIT, PING, LOCATION_DISABLED, LOCATION_ENABLED
    event_timestamp_utc: datetime
    device_clock_utc: datetime | None
    server_received_at: datetime
    latitude: float | None
    longitude: float | None
    accuracy_meters: float | None
    is_mock_location: bool | None
    is_inside_polygon: bool
    distance_to_polygon_m: float | None
    matched_site_id: UUID | None
    matched_accommodation_id: UUID | None
    has_assigned_polygon: bool


@dataclass(frozen=True)
class EventVerdictResult:
    verdict: ServerVerdict
    flags: list[str]
    device_clock_skew_s: int | None
    distance_to_polygon_m: float | None
    server_site_id: UUID | None
    server_accommodation_id: UUID | None


def evaluate_event_verdict(
    item: EventVerdictInput,
    max_location_accuracy_m: float = 100.0,
    clock_skew_tolerance_s: int = 120,
) -> EventVerdictResult:
    """Evaluate server verdict and data quality flags for a mobile event."""
    flags: list[str] = []

    # 1. Clock skew check [DEC-14]
    clock_skew_s: int | None = None
    if item.device_clock_utc is not None:
        skew_diff = item.server_received_at - item.device_clock_utc
        clock_skew_s = int(skew_diff.total_seconds())
        if abs(clock_skew_s) > clock_skew_tolerance_s:
            flags.append(EventFlag.CLOCK_SKEW.value)

    # 2. Mock location check
    if item.is_mock_location:
        flags.append(EventFlag.MOCK_LOCATION.value)

    # 3. Accuracy check
    acc = item.accuracy_meters or 0.0
    if acc > max_location_accuracy_m:
        flags.append(EventFlag.LOW_ACCURACY.value)

    # 4. Spatial verdict determination
    if item.latitude is None or item.longitude is None:
        verdict = ServerVerdict.NO_POLYGON
    elif item.is_inside_polygon:
        verdict = ServerVerdict.INSIDE
    elif item.distance_to_polygon_m is not None:
        # BORDERLINE: outside polygon but within accuracy radius
        if item.distance_to_polygon_m <= acc:
            verdict = ServerVerdict.BORDERLINE
            flags.append(EventFlag.BORDERLINE_LOCATION.value)
        else:
            verdict = ServerVerdict.OUTSIDE
    else:
        verdict = ServerVerdict.OUTSIDE

    # 5. Type-specific semantic checks
    ev_type = item.event_type.upper()
    if ev_type == "ENTRY":
        if verdict not in (ServerVerdict.INSIDE, ServerVerdict.BORDERLINE):
            flags.append(EventFlag.ENTRY_OUTSIDE_POLYGON.value)
    elif ev_type == "EXIT":
        if verdict == ServerVerdict.INSIDE:
            flags.append(EventFlag.EXIT_INSIDE_POLYGON.value)

    if not item.has_assigned_polygon and (item.matched_site_id or item.matched_accommodation_id):
        flags.append(EventFlag.UNKNOWN_SITE.value)

    return EventVerdictResult(
        verdict=verdict,
        flags=flags,
        device_clock_skew_s=clock_skew_s,
        distance_to_polygon_m=item.distance_to_polygon_m,
        server_site_id=item.matched_site_id,
        server_accommodation_id=item.matched_accommodation_id,
    )
