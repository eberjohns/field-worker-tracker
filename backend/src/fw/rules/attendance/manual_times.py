"""Visits from times an Engineer or Admin entered for a day (owner decision 25 Nov 2026).

When a phone records nothing (a dead phone), the reviewer enters the first site entry and the last
site exit, and optionally the accommodation departure and return. The engine then calculates the
day from these visits instead of phone events: the usual break, required hours, shortfall and
overtime rules all apply. The span is split evenly, back to back, across the day's assigned
worksites in order, so each assignment counts as visited.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid5

from fw.rules.attendance.visits import ConstructedVisit

MANUAL_TIMES_FLAG = "MANUAL_TIMES"
NO_ATTENDANCE_EVENTS_FLAG = "NO_ATTENDANCE_EVENTS"
_NAMESPACE = UUID("6f1c2d8e-0b7a-4c55-9a3e-2f6d1e0c7b11")


def manual_event_id(manual_id: UUID, label: str) -> UUID:
    """A stable stand-in event id (manual visits have no phone event; never stored as one)."""
    return uuid5(_NAMESPACE, f"{manual_id}:{label}")


def build_manual_visits(
    *,
    manual_id: UUID,
    work_date: date,
    first_site_entry_at: datetime,
    last_site_exit_at: datetime,
    worksite_ids: list[UUID],
    accommodation_id: UUID | None = None,
    accommodation_departure_at: datetime | None = None,
    accommodation_return_at: datetime | None = None,
) -> list[ConstructedVisit]:
    """Site visits covering the entered span, plus accommodation departure and return visits."""
    if last_site_exit_at <= first_site_entry_at:
        raise ValueError("The last site exit must be after the first site entry.")
    flags = [MANUAL_TIMES_FLAG]
    visits: list[ConstructedVisit] = []

    if accommodation_departure_at is not None:
        visits.append(
            ConstructedVisit(
                work_date=work_date,
                place_type="ACCOMMODATION",
                worksite_id=None,
                accommodation_id=accommodation_id,
                entry_event_id=manual_event_id(manual_id, "acc-departure"),
                exit_event_id=manual_event_id(manual_id, "acc-departure-exit"),
                entry_at=accommodation_departure_at,
                exit_at=accommodation_departure_at,
                exit_inferred=False,
                last_inside_at=accommodation_departure_at,
                counts_as_completed=False,
                duration_minutes=0,
                flags=list(flags),
            )
        )

    sites: list[UUID | None] = list(dict.fromkeys(worksite_ids)) or [None]
    span = last_site_exit_at - first_site_entry_at
    piece = span / len(sites)
    for i, site_id in enumerate(sites):
        entry_at = first_site_entry_at + piece * i
        exit_at = (
            last_site_exit_at if i == len(sites) - 1 else first_site_entry_at + piece * (i + 1)
        )
        visits.append(
            ConstructedVisit(
                work_date=work_date,
                place_type="SITE",
                worksite_id=site_id,
                accommodation_id=None,
                entry_event_id=manual_event_id(manual_id, f"site-{i}-entry"),
                exit_event_id=manual_event_id(manual_id, f"site-{i}-exit"),
                entry_at=entry_at,
                exit_at=exit_at,
                exit_inferred=False,
                last_inside_at=exit_at,
                counts_as_completed=site_id is not None,
                duration_minutes=int((exit_at - entry_at).total_seconds() // 60),
                flags=list(flags),
            )
        )

    if accommodation_return_at is not None:
        visits.append(
            ConstructedVisit(
                work_date=work_date,
                place_type="ACCOMMODATION",
                worksite_id=None,
                accommodation_id=accommodation_id,
                entry_event_id=manual_event_id(manual_id, "acc-return"),
                exit_event_id=None,
                entry_at=accommodation_return_at,
                exit_at=None,
                exit_inferred=False,
                last_inside_at=accommodation_return_at,
                counts_as_completed=False,
                duration_minutes=0,
                flags=list(flags),
            )
        )
    return visits
