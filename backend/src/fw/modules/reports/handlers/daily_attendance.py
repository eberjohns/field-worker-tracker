"""Handler for Daily Attendance Report."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.progress import yield_every
from fw.modules.reports.handlers._attendance_days import load_attendance_days
from fw.modules.reports.schemas import ReportFilterParams
from fw.modules.scheduling import AccessScope


async def fetch_daily_attendance(
    session: AsyncSession,
    filters: ReportFilterParams,
    scope: AccessScope | None,
) -> list[dict[str, Any]]:
    """Query daily attendance data comparing 5-point planned schedule against actuals."""
    days = await load_attendance_days(
        session,
        filters,
        scope,
        record_fields=("work_date", "business_status", "review_status"),
        calc_fields=(
            "planned_accommodation_departure",
            "planned_first_site_start",
            "planned_break_minutes",
            "planned_last_site_end",
            "planned_accommodation_return",
            "planned_total_minutes",
            "planned_worked_minutes",
            "accommodation_departure_at",
            "first_site_entry_at",
            "break_minutes_used",
            "last_site_exit_at",
            "accommodation_return_at",
            "shift_span_minutes",
            "worked_minutes",
            "ot1_minutes",
            "ot2_minutes",
            "flags",
        ),
        employee_fields=("tally_id", "name", "accommodation_id"),
        latest_comment=True,
        filter_sgd=True,
    )

    rows: list[dict[str, Any]] = []
    for day_no, day in enumerate(days):
        await yield_every(day_no)
        rec, calc, emp = day.rec, day.calc, day.emp

        has_acc = bool(emp and emp.accommodation_id is not None)

        # Planned 7 cols
        pl_acc_st = (
            calc.planned_accommodation_departure.strftime("%H:%M")
            if calc and calc.planned_accommodation_departure
            else ("-" if has_acc else "n/a")
        )
        pl_first = (
            calc.planned_first_site_start.strftime("%H:%M")
            if calc and calc.planned_first_site_start
            else "-"
        )
        pl_break = calc.planned_break_minutes if calc else 0
        pl_last = (
            calc.planned_last_site_end.strftime("%H:%M")
            if calc and calc.planned_last_site_end
            else "-"
        )
        pl_acc_end = (
            calc.planned_accommodation_return.strftime("%H:%M")
            if calc and calc.planned_accommodation_return
            else ("-" if has_acc else "n/a")
        )
        pl_total = calc.planned_total_minutes if calc else 0
        pl_worked = calc.planned_worked_minutes if calc else 0

        # Actual 7 cols
        act_acc_st = (
            calc.accommodation_departure_at.strftime("%H:%M")
            if calc and calc.accommodation_departure_at
            else ("-" if has_acc else "n/a")
        )
        act_first = (
            calc.first_site_entry_at.strftime("%H:%M") if calc and calc.first_site_entry_at else "-"
        )
        act_break = calc.break_minutes_used if calc else 0
        act_last = (
            calc.last_site_exit_at.strftime("%H:%M") if calc and calc.last_site_exit_at else "-"
        )
        act_acc_end = (
            calc.accommodation_return_at.strftime("%H:%M")
            if calc and calc.accommodation_return_at
            else ("-" if has_acc else "n/a")
        )
        act_total = calc.shift_span_minutes if calc else 0
        act_worked = calc.worked_minutes if calc else 0

        # Variations
        var_total = act_total - pl_total if calc else 0
        var_worked = act_worked - pl_worked if calc else 0

        # Overtime
        ot1_hrs = round(calc.ot1_minutes / 60.0, 2) if calc else 0.0
        ot2_hrs = round(calc.ot2_minutes / 60.0, 2) if calc else 0.0

        # Comments & Approval
        latest_comment = day.latest_comment
        approval_str = rec.review_status
        flags_str = ", ".join(calc.flags) if calc and calc.flags else ""

        rows.append(
            {
                "worker_id": emp.tally_id if emp else "",
                "worker_name": emp.name if emp else "",
                "work_date": rec.work_date,
                "status": rec.business_status,
                "planned_acc_start": pl_acc_st,
                "planned_first_site": pl_first,
                "planned_break": pl_break,
                "planned_last_site": pl_last,
                "planned_acc_end": pl_acc_end,
                "planned_total_time": pl_total,
                "planned_worked_time": pl_worked,
                "actual_acc_start": act_acc_st,
                "actual_first_site": act_first,
                "actual_break": act_break,
                "actual_last_site": act_last,
                "actual_acc_end": act_acc_end,
                "actual_total_time": act_total,
                "actual_worked_time": act_worked,
                "var_total_time": var_total,
                "var_worked_time": var_worked,
                "ot1_hours": ot1_hrs,
                "ot2_hours": ot2_hrs,
                "flags": flags_str,
                "comments": latest_comment,
                "approval": approval_str,
            }
        )

    return rows
