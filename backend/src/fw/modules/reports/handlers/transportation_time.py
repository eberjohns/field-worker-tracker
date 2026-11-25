"""Handler for Transportation Time Report."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.progress import yield_every
from fw.modules.reports.handlers._attendance_days import load_attendance_days
from fw.modules.reports.schemas import ReportFilterParams
from fw.modules.scheduling import AccessScope


async def fetch_transportation_time(
    session: AsyncSession,
    filters: ReportFilterParams,
    scope: AccessScope | None,
) -> list[dict[str, Any]]:
    """Query commute out, inter-site, commute back, and total transit per worker/day."""
    days = await load_attendance_days(
        session,
        filters,
        scope,
        record_fields=("work_date",),
        calc_fields=(
            "transit_minutes",
            "accommodation_departure_at",
            "first_site_entry_at",
            "last_site_exit_at",
            "accommodation_return_at",
        ),
        employee_fields=("tally_id", "name", "role"),
    )

    rows: list[dict[str, Any]] = []
    for day_no, day in enumerate(days):
        await yield_every(day_no)
        r, calc, emp = day.rec, day.calc, day.emp
        if not calc:
            continue

        total_transit = calc.transit_minutes
        commute_out = 0
        if calc.accommodation_departure_at and calc.first_site_entry_at:
            commute_out = max(
                0,
                int(
                    (calc.first_site_entry_at - calc.accommodation_departure_at).total_seconds()
                    / 60
                ),
            )

        commute_back = 0
        if calc.last_site_exit_at and calc.accommodation_return_at:
            commute_back = max(
                0, int((calc.accommodation_return_at - calc.last_site_exit_at).total_seconds() / 60)
            )

        inter_site = max(0, total_transit - commute_out - commute_back)
        is_driver = bool(emp and emp.role == "DRIVER")

        rows.append(
            {
                "worker_id": emp.tally_id if emp else "",
                "worker_name": emp.name if emp else "",
                "work_date": r.work_date,
                "commute_out_minutes": commute_out,
                "inter_site_minutes": inter_site,
                "commute_back_minutes": commute_back,
                "total_transit_minutes": total_transit,
                "is_driver_day": "YES" if is_driver else "NO",
                "tag": "INFERRED",
            }
        )

    return rows
