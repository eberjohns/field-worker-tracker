"""Day close: a planned day with no attendance becomes ABSENT, pending review (owner, 25 Nov 2026).

Runs once a day for the site day that has just ended. For every employee with ACTIVE scheduled
work that day and no attendance record (the phone sent no events), the day is calculated with
reason DAY_CLOSE. With no visits, the engine marks it ABSENT with the planned hours as shortfall
(missed hours), flags it NO_ATTENDANCE_EVENTS and sends it to review, so it appears in the
attendance review, the dashboard and the approvals count like any flagged day.

Not closed: a day of approved leave, the worker's weekly off, or a day with no scheduled work.
A phone that uploads the day later recalculates it as usual (a new calculation version).
"""

from __future__ import annotations

from datetime import date

import structlog
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.modules.attendance.models import AttendanceRecord
from fw.modules.attendance.service import AttendanceService
from fw.modules.org import Employee
from fw.modules.scheduling import LeaveRequest, ScheduledWork
from fw.rules.scheduling import INT_TO_WEEKDAY, is_same_weekday

logger = structlog.get_logger(__name__)

DAY_CLOSE_REASON = "DAY_CLOSE"


class DayCloseService:
    @staticmethod
    async def close_day(session: AsyncSession, target_date: date, country: str) -> dict[str, int]:
        """Calculate every planned, unrecorded employee-day of ``target_date`` in ``country``."""
        country = (country or "AE").upper()
        has_record = exists().where(
            AttendanceRecord.employee_id == ScheduledWork.employee_id,
            AttendanceRecord.work_date == target_date,
        )
        employees = list(
            (
                await session.execute(
                    select(Employee)
                    .join(ScheduledWork, ScheduledWork.employee_id == Employee.id)
                    .where(
                        ScheduledWork.work_date == target_date,
                        ScheduledWork.status == "ACTIVE",
                        Employee.country == country,
                        ~has_record,
                    )
                    .distinct()
                )
            )
            .scalars()
            .all()
        )
        result = {
            "absent": 0,
            "calculated_other": 0,
            "skipped_leave": 0,
            "skipped_weekly_off": 0,
        }
        if not employees:
            return result

        on_leave = set(
            (
                await session.execute(
                    select(LeaveRequest.employee_id).where(
                        LeaveRequest.employee_id.in_([e.id for e in employees]),
                        LeaveRequest.status == "APPROVED",
                        LeaveRequest.is_active.is_(True),
                        LeaveRequest.from_date <= target_date,
                        LeaveRequest.to_date >= target_date,
                    )
                )
            )
            .scalars()
            .all()
        )
        dow = INT_TO_WEEKDAY[target_date.weekday()]
        for emp in sorted(employees, key=lambda e: e.tally_id or ""):
            if emp.id in on_leave:
                result["skipped_leave"] += 1
                continue
            if is_same_weekday(emp.weekly_off_day, dow):
                result["skipped_weekly_off"] += 1
                continue
            record = await AttendanceService.recalculate_day(
                session, emp.id, target_date, reason=DAY_CLOSE_REASON
            )
            if record is not None and record.business_status == "ABSENT":
                result["absent"] += 1
            else:
                result["calculated_other"] += 1
        await session.flush()
        logger.info("attendance_day_closed", work_date=target_date.isoformat(), **result)
        return result
