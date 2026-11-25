"""Handler for Late Arrival / Early Departure Report."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.clock import get_country_timezone
from fw.core.progress import yield_every
from fw.modules.reports.handlers._attendance_days import load_attendance_days
from fw.modules.reports.schemas import ReportFilterParams
from fw.modules.scheduling import AccessScope


def _site_minutes(at: datetime, tz: ZoneInfo) -> int:
    """Minutes after midnight in site time. Timestamps are stored in UTC and the planned times
    are site wall-clock times, so the actual time is converted before they are compared."""
    local = at.astimezone(tz) if at.tzinfo is not None else at
    return local.hour * 60 + local.minute


async def fetch_late_early_departure(
    session: AsyncSession,
    filters: ReportFilterParams,
    scope: AccessScope | None,
) -> list[dict[str, Any]]:
    """Query rows where arrival, departure, or shortfall deviated beyond scheduled times."""
    days = await load_attendance_days(
        session,
        filters,
        scope,
        record_fields=("work_date", "review_status"),
        calc_fields=(
            "planned_first_site_start",
            "first_site_entry_at",
            "planned_accommodation_departure",
            "accommodation_departure_at",
            "planned_last_site_end",
            "last_site_exit_at",
            "shortfall_minutes",
            "grace_applied",
        ),
        employee_fields=("tally_id", "name", "country"),
        latest_comment=True,
    )

    rows: list[dict[str, Any]] = []
    for day_no, day in enumerate(days):
        await yield_every(day_no)
        r, calc, emp = day.rec, day.calc, day.emp
        if not calc:
            continue

        tz = get_country_timezone(emp.country if emp else None)

        late_arr = 0
        if calc.planned_first_site_start and calc.first_site_entry_at:
            act_min = _site_minutes(calc.first_site_entry_at, tz)
            pl_min = calc.planned_first_site_start.hour * 60 + calc.planned_first_site_start.minute
            late_arr = max(0, act_min - pl_min)

        late_dep_acc = 0
        if calc.planned_accommodation_departure and calc.accommodation_departure_at:
            act_min = _site_minutes(calc.accommodation_departure_at, tz)
            pl_min = (
                calc.planned_accommodation_departure.hour * 60
                + calc.planned_accommodation_departure.minute
            )
            late_dep_acc = max(0, act_min - pl_min)

        early_dep = 0
        if calc.planned_last_site_end and calc.last_site_exit_at:
            act_min = _site_minutes(calc.last_site_exit_at, tz)
            pl_min = calc.planned_last_site_end.hour * 60 + calc.planned_last_site_end.minute
            early_dep = max(0, pl_min - act_min)

        shortfall = calc.shortfall_minutes

        if late_arr == 0 and late_dep_acc == 0 and early_dep == 0 and shortfall == 0:
            continue

        latest_comment = day.latest_comment

        rows.append(
            {
                "worker_id": emp.tally_id if emp else "",
                "worker_name": emp.name if emp else "",
                "work_date": r.work_date,
                "late_arrival_minutes": late_arr,
                "late_dep_acc_minutes": late_dep_acc,
                "early_dep_minutes": early_dep,
                "shortfall_minutes": shortfall,
                "grace_applied": "YES" if calc.grace_applied else "NO",
                "comments": latest_comment,
                "review_state": r.review_status,
            }
        )

    return rows
