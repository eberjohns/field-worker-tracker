"""Handler for Employee Utilization Report (DEC-28)."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.progress import yield_every
from fw.modules.reports.handlers._attendance_days import load_attendance_days
from fw.modules.reports.schemas import ReportFilterParams
from fw.modules.scheduling import AccessScope


async def fetch_employee_utilization(
    session: AsyncSession,
    filters: ReportFilterParams,
    scope: AccessScope | None,
) -> list[dict[str, Any]]:
    """Query productive vs travel vs idle time breakdown per worker (DEC-28)."""
    days = await load_attendance_days(
        session,
        filters,
        scope,
        record_fields=("work_date",),
        calc_fields=(
            "shift_span_minutes",
            "productive_minutes",
            "transit_minutes",
            "idle_minutes",
            "break_minutes_used",
            "standard_hours_minutes",
            "worked_minutes",
        ),
        employee_fields=("tally_id", "name"),
    )

    rows: list[dict[str, Any]] = []
    for day_no, day in enumerate(days):
        await yield_every(day_no)
        r, calc, emp = day.rec, day.calc, day.emp
        if not calc:
            continue

        shift_span = calc.shift_span_minutes
        productive = calc.productive_minutes
        travel = calc.transit_minutes
        idle = calc.idle_minutes
        break_used = calc.break_minutes_used

        util_pct = round((productive / shift_span * 100.0), 1) if shift_span > 0 else 0.0
        scheduled_min = calc.standard_hours_minutes
        worked_min = calc.worked_minutes
        sched_vs_worked_pct = (
            round((worked_min / scheduled_min * 100.0), 1) if scheduled_min > 0 else 0.0
        )

        rows.append(
            {
                "worker_id": emp.tally_id if emp else "",
                "worker_name": emp.name if emp else "",
                "work_date": r.work_date,
                "shift_span_minutes": shift_span,
                "productive_minutes": productive,
                "travel_minutes": travel,
                "idle_minutes": idle,
                "break_minutes": break_used,
                "utilization_pct": util_pct,
                "scheduled_minutes": scheduled_min,
                "worked_minutes": worked_min,
                "scheduled_vs_worked_pct": sched_vs_worked_pct,
                "tag": "INFERRED",
            }
        )

    return rows
