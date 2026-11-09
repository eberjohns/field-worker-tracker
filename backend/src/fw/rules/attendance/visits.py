from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID


class VisitFlag(StrEnum):
    DUPLICATE_ENTRY = "DUPLICATE_ENTRY"
    LEFT_WITHOUT_EXIT = "LEFT_WITHOUT_EXIT"
    EXIT_INSIDE_POLYGON = "EXIT_INSIDE_POLYGON"
    ORPHAN_EXIT = "ORPHAN_EXIT"
    MISSING_EXIT = "MISSING_EXIT"
    INFERRED_EXIT = "INFERRED_EXIT"
    UNASSIGNED_SITE_VISIT = "UNASSIGNED_SITE_VISIT"


@dataclass(frozen=True)
class EventForVisit:
    event_id: UUID
    event_type: str  # ENTRY, EXIT, PING
    event_timestamp_utc: datetime
    sequence_number: int | None
    server_received_at: datetime
    server_verdict: str  # INSIDE, BORDERLINE, OUTSIDE, NO_POLYGON
    server_site_id: UUID | None
    server_accommodation_id: UUID | None
    flags: list[str] = field(default_factory=list)


@dataclass
class ConstructedVisit:
    work_date: date
    place_type: str  # SITE | ACCOMMODATION
    worksite_id: UUID | None
    accommodation_id: UUID | None
    entry_event_id: UUID
    exit_event_id: UUID | None
    entry_at: datetime
    exit_at: datetime | None
    exit_inferred: bool
    last_inside_at: datetime
    counts_as_completed: bool
    duration_minutes: int
    flags: list[str] = field(default_factory=list)


def build_visits_for_day(
    events: list[EventForVisit],
    work_date: date,
    assigned_worksite_ids: set[UUID],
    min_visit_minutes: int = 10,
    day_close_timestamp: datetime | None = None,
) -> list[ConstructedVisit]:
    """Process a worker's day events in time order to construct site and accommodation visits."""
    # Filter out events that cannot confirm visits (e.g. LOW_ACCURACY on entry/exit)
    # Note: Sort by timestamp, then sequence_number, then server_received_at
    sorted_events = sorted(
        events,
        key=lambda e: (
            e.event_timestamp_utc,
            e.sequence_number or 0,
            e.server_received_at,
        ),
    )

    open_visits: dict[tuple[str, UUID], ConstructedVisit] = {}
    completed_visits: list[ConstructedVisit] = []

    for ev in sorted_events:
        ev_type = ev.event_type.upper()
        if ev_type not in ("ENTRY", "EXIT", "PING"):
            continue

        is_low_accuracy = "LOW_ACCURACY" in ev.flags
        verdict = ev.server_verdict.upper() if ev.server_verdict else "OUTSIDE"

        place_type = "ACCOMMODATION" if ev.server_accommodation_id else "SITE"
        place_id = ev.server_accommodation_id or ev.server_site_id
        if not place_id:
            continue

        visit_key = (place_type, place_id)
        current_visit = open_visits.get(visit_key)

        if ev_type == "ENTRY":
            # LOW_ACCURACY cannot confirm an ENTRY
            if is_low_accuracy:
                continue

            if verdict in ("INSIDE", "BORDERLINE"):
                if current_visit is not None:
                    # Duplicate entry while visit is open
                    if VisitFlag.DUPLICATE_ENTRY.value not in current_visit.flags:
                        current_visit.flags.append(VisitFlag.DUPLICATE_ENTRY.value)
                else:
                    # Open new visit
                    flags: list[str] = []
                    if place_type == "SITE" and place_id not in assigned_worksite_ids:
                        flags.append(VisitFlag.UNASSIGNED_SITE_VISIT.value)

                    open_visits[visit_key] = ConstructedVisit(
                        work_date=work_date,
                        place_type=place_type,
                        worksite_id=place_id if place_type == "SITE" else None,
                        accommodation_id=place_id if place_type == "ACCOMMODATION" else None,
                        entry_event_id=ev.event_id,
                        exit_event_id=None,
                        entry_at=ev.event_timestamp_utc,
                        exit_at=None,
                        exit_inferred=False,
                        last_inside_at=ev.event_timestamp_utc,
                        counts_as_completed=False,
                        duration_minutes=0,
                        flags=flags,
                    )

        elif ev_type == "PING":
            if current_visit is not None:
                if verdict in ("INSIDE", "BORDERLINE") and not is_low_accuracy:
                    current_visit.last_inside_at = ev.event_timestamp_utc
                elif verdict == "OUTSIDE":
                    # PING outside while open -> left without exit, close as INFERRED at last_inside_at
                    current_visit.exit_at = current_visit.last_inside_at
                    current_visit.exit_inferred = True
                    current_visit.flags.append(VisitFlag.LEFT_WITHOUT_EXIT.value)
                    current_visit.flags.append(VisitFlag.INFERRED_EXIT.value)
                    current_visit.duration_minutes = max(
                        0,
                        int((current_visit.exit_at - current_visit.entry_at).total_seconds() // 60),
                    )
                    current_visit.counts_as_completed = (
                        current_visit.duration_minutes >= min_visit_minutes
                    )
                    completed_visits.append(current_visit)
                    del open_visits[visit_key]

        elif ev_type == "EXIT":
            if current_visit is not None:
                if verdict == "INSIDE":
                    # EXIT verdict INSIDE -> do not close, flag EXIT_INSIDE_POLYGON
                    if VisitFlag.EXIT_INSIDE_POLYGON.value not in current_visit.flags:
                        current_visit.flags.append(VisitFlag.EXIT_INSIDE_POLYGON.value)
                else:
                    # Valid exit outside or borderline
                    current_visit.exit_event_id = ev.event_id
                    current_visit.exit_at = ev.event_timestamp_utc
                    current_visit.exit_inferred = False
                    current_visit.duration_minutes = max(
                        0,
                        int((current_visit.exit_at - current_visit.entry_at).total_seconds() // 60),
                    )
                    current_visit.counts_as_completed = (
                        current_visit.duration_minutes >= min_visit_minutes
                    )
                    completed_visits.append(current_visit)
                    del open_visits[visit_key]
            else:
                # Orphan exit
                if place_type == "ACCOMMODATION":
                    # Morning departure from camp
                    completed_visits.append(
                        ConstructedVisit(
                            work_date=work_date,
                            place_type=place_type,
                            worksite_id=None,
                            accommodation_id=place_id,
                            entry_event_id=ev.event_id,
                            exit_event_id=ev.event_id,
                            entry_at=ev.event_timestamp_utc,
                            exit_at=ev.event_timestamp_utc,
                            exit_inferred=False,
                            last_inside_at=ev.event_timestamp_utc,
                            counts_as_completed=True,
                            duration_minutes=0,
                            flags=[],
                        )
                    )

    # End of day check for any remaining open visits [DEC-05]
    for _v_key, visit in list(open_visits.items()):
        visit.exit_at = visit.last_inside_at
        if visit.place_type == "SITE":
            visit.exit_inferred = True
            visit.flags.append(VisitFlag.MISSING_EXIT.value)
            visit.flags.append(VisitFlag.INFERRED_EXIT.value)
            visit.duration_minutes = max(
                0,
                int((visit.exit_at - visit.entry_at).total_seconds() // 60),
            )
            visit.counts_as_completed = visit.duration_minutes >= min_visit_minutes
        else:
            # Evening return to camp: stays inside accommodation for rest
            visit.exit_at = None
            visit.exit_inferred = False
            visit.duration_minutes = 0
            visit.counts_as_completed = True
        completed_visits.append(visit)

    # Sort final visits by entry time
    completed_visits.sort(key=lambda v: v.entry_at)
    return completed_visits
