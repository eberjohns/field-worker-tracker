"""Handler for Monthly Attendance Report."""

from collections import defaultdict
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.progress import yield_every
from fw.modules.reports.handlers._attendance_days import load_attendance_days
from fw.modules.reports.schemas import ReportFilterParams
from fw.modules.scheduling import AccessScope


async def fetch_monthly_attendance(
    session: AsyncSession,
    filters: ReportFilterParams,
    scope: AccessScope | None,
) -> list[dict[str, Any]]:
    """Aggregate attendance per worker across the requested month or date range."""
    target_from = filters.date_from
    target_to = filters.date_to
    if filters.year and filters.month and not target_from:
        import calendar

        _, last_day = calendar.monthrange(filters.year, filters.month)
        target_from = date(filters.year, filters.month, 1)
        target_to = date(filters.year, filters.month, last_day)

    days = await load_attendance_days(
        session,
        filters,
        scope,
        record_fields=("employee_id", "work_date", "business_status", "review_status"),
        calc_fields=(
            "shortfall_minutes",
            "grace_applied",
            "worked_minutes",
            "ot1_minutes",
            "ot2_minutes",
        ),
        date_from=target_from,
        date_to=target_to,
        newest_first=False,
    )
    emp_map = {d.rec.employee_id: d.emp for d in days}

    # Group by (employee_id, YYYY-MM)
    grouped: dict[tuple[UUID, str], list[Any]] = defaultdict(list)
    for day_no, day in enumerate(days):
        await yield_every(day_no)
        rec = day.rec
        rec.current_calculation = day.calc
        month_str = rec.work_date.strftime("%Y-%m")
        grouped[(rec.employee_id, month_str)].append(rec)

    rows: list[dict[str, Any]] = []
    for (emp_id, month_str), recs in grouped.items():
        emp = emp_map.get(emp_id)
        days_pres = sum(1 for r in recs if r.business_status == "PRESENT")
        days_part = sum(1 for r in recs if r.business_status == "PARTIAL")
        days_abs = sum(1 for r in recs if r.business_status == "ABSENT")
        days_shortfall = 0
        total_worked_min = 0
        ot1_min = 0
        ot2_min = 0
        pending_review = sum(1 for r in recs if r.review_status == "PENDING_REVIEW")

        for r in recs:
            calc = r.current_calculation
            if calc:
                if calc.shortfall_minutes > 0 and not calc.grace_applied:
                    days_shortfall += 1
                total_worked_min += calc.worked_minutes
                ot1_min += calc.ot1_minutes
                ot2_min += calc.ot2_minutes

        total_worked_hrs = round(total_worked_min / 60.0, 2)
        ot1_hrs = round(ot1_min / 60.0, 2)
        ot2_hrs = round(ot2_min / 60.0, 2)

        rows.append(
            {
                "worker_id": emp.tally_id if emp else "",
                "worker_name": emp.name if emp else "",
                "month": month_str,
                "days_present": days_pres,
                "days_partial": days_part,
                "days_absent": days_abs,
                "days_shortfall": days_shortfall,
                "total_worked_hours": total_worked_hrs,
                "cumulative_worked_hours": total_worked_hrs,
                "ot1_total_hours": ot1_hrs,
                "ot2_total_hours": ot2_hrs,
                "days_pending_review": pending_review,
            }
        )

    rows.sort(key=lambda r: (r["worker_name"], r["month"]))
    return rows
