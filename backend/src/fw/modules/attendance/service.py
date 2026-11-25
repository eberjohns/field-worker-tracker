from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fw.core.clock import get_country_timezone
from fw.modules.attendance.models import (
    AttendanceApproval,
    AttendanceCalculation,
    AttendanceComment,
    AttendanceManualTime,
    AttendanceRecord,
    SiteVisit,
    TrackingGap,
)
from fw.modules.attendance.schemas import (
    AttendanceCommentCreateRequest,
    AttendanceDecisionRequest,
    AttendanceTimelineItem,
    AttendanceTimelineResponse,
)
from fw.modules.events import MobileEventLog
from fw.modules.identity.models import User
from fw.modules.jobs.models import Worksite
from fw.modules.org.models import Accommodation, Employee, EmployeeReportingLine
from fw.modules.scheduling.models import LeaveRequest, ScheduledWork
from fw.modules.settings import SettingsService
from fw.modules.settings.models import PublicHoliday, TimeRule
from fw.rules.attendance import (
    MANUAL_TIMES_FLAG,
    NO_ATTENDANCE_EVENTS_FLAG,
    DailyCalculationInputs,
    EventForGap,
    EventForVisit,
    ScheduledAssignment,
    build_gaps_for_day,
    build_manual_visits,
    build_visits_for_day,
    compute_daily_attendance,
)
from fw.rules.time_rules import (
    TimeRuleDefinition,
    WorkerContext,
    resolve_time_schedule,
    time_diff_minutes,
)

logger = structlog.get_logger(__name__)


class AttendanceService:
    """Orchestration service for daily attendance calculation, timeline, comments, and approvals."""

    @staticmethod
    async def recalculate_day(
        session: AsyncSession,
        employee_id: UUID,
        work_date: date,
        reason: str = "NEW_EVENTS",
    ) -> AttendanceRecord | None:
        """Recompute attendance for an employee on a work date."""
        # 1. Fetch employee
        emp_q = select(Employee).where(Employee.id == employee_id)
        emp_res = await session.execute(emp_q)
        employee = emp_res.scalar_one_or_none()
        if not employee:
            return None

        country = (employee.country or "AE").upper()
        tz = get_country_timezone(country)

        # 2. Check if payroll is approved for this date (locked)
        from sqlalchemy import text

        locked = await AttendanceService.is_payroll_locked(session, employee_id, work_date)
        if locked:
            reason = "POST_FINALIZATION"

        # 3. Load employee standard hours and break minutes from salary structure (or fallback)
        standard_hours = 8.0
        salary_break_minutes: int | None = None
        has_salary_structure = False

        sal_res = await session.execute(
            text(
                """
                SELECT standard_hours, break_minutes FROM employee_salary
                WHERE employee_id = :emp_id AND effective_from <= :w_date
                ORDER BY effective_from DESC LIMIT 1
                """
            ),
            {"emp_id": employee_id, "w_date": work_date},
        )
        sal_row = sal_res.first()
        if sal_row is not None:
            has_salary_structure = True
            if sal_row[0] is not None:
                standard_hours = float(sal_row[0])
            if sal_row[1] is not None:
                salary_break_minutes = int(sal_row[1])

        # 4. Resolve time rules for this worker & date
        tr_q = select(TimeRule).where(
            TimeRule.is_active.is_(True),
            TimeRule.start_date <= work_date,
        )
        tr_res = await session.execute(tr_q)
        db_rules = tr_res.scalars().all()
        rule_defs = [
            TimeRuleDefinition(
                id=r.id,
                name=r.name,
                country=r.country,
                scope_type=r.scope_type,
                scope_employee_id=r.scope_employee_id,
                applies_to=r.applies_to,
                start_date=r.start_date,
                end_date=r.end_date,
                accommodation_start=r.accommodation_start,
                first_site_start=r.first_site_start,
                break_minutes=r.break_minutes,
                last_site_end=r.last_site_end,
                accommodation_end=r.accommodation_end,
                standard_hours_change_minutes=r.standard_hours_change_minutes,
                is_active=r.is_active,
            )
            for r in db_rules
        ]

        # Load reporting lines for team resolution
        lines_q = select(
            EmployeeReportingLine.manager_id, EmployeeReportingLine.relationship
        ).where(
            EmployeeReportingLine.employee_id == employee_id,
            EmployeeReportingLine.is_active == True,  # noqa: E712
        )
        lines_res = await session.execute(lines_q)
        mgr_links = [(row[0], row[1]) for row in lines_res.all()]

        worker_ctx = WorkerContext(
            employee_id=employee_id,
            country=country,
            is_driver=employee.is_driver or False,
            has_accommodation=employee.accommodation_id is not None,
            manager_links=mgr_links,
        )
        resolved_schedule = resolve_time_schedule(rule_defs, worker_ctx, work_date)

        # Fallback to company settings / defaults if time rules did not specify 5-point schedule
        if resolved_schedule.first_site_start is None or resolved_schedule.last_site_end is None:
            raw_acc_start = (
                await SettingsService.get_setting(
                    session, "default_accommodation_start", country=country
                )
                or "05:00"
            )
            raw_first_start = (
                await SettingsService.get_setting(
                    session, "default_first_site_start", country=country
                )
                or "06:00"
            )
            raw_break_min = (
                await SettingsService.get_setting(session, "default_break_minutes", country=country)
                or 30
            )
            raw_last_end = (
                await SettingsService.get_setting(session, "default_last_site_end", country=country)
                or "15:30"
            )
            raw_acc_end = (
                await SettingsService.get_setting(
                    session, "default_accommodation_end", country=country
                )
                or "17:00"
            )

            def _parse_time(v: Any, default_t: time) -> time:
                if isinstance(v, time):
                    return v
                if isinstance(v, str):
                    try:
                        parts = v.strip().split(":")
                        return time(int(parts[0]), int(parts[1]))
                    except Exception:
                        pass
                return default_t

            if resolved_schedule.first_site_start is None:
                resolved_schedule.first_site_start = _parse_time(raw_first_start, time(6, 0))
            if resolved_schedule.last_site_end is None:
                resolved_schedule.last_site_end = _parse_time(raw_last_end, time(15, 30))
            if not resolved_schedule.break_minutes:
                try:
                    resolved_schedule.break_minutes = int(raw_break_min)
                except Exception:
                    resolved_schedule.break_minutes = 30

            if worker_ctx.has_accommodation:
                if resolved_schedule.accommodation_start is None:
                    resolved_schedule.accommodation_start = _parse_time(raw_acc_start, time(5, 0))
                if resolved_schedule.accommodation_end is None:
                    resolved_schedule.accommodation_end = _parse_time(raw_acc_end, time(17, 0))

            # Recalculate planned total and worked minutes
            if (
                worker_ctx.has_accommodation
                and resolved_schedule.accommodation_start
                and resolved_schedule.accommodation_end
            ):
                resolved_schedule.planned_total_minutes = time_diff_minutes(
                    resolved_schedule.accommodation_start, resolved_schedule.accommodation_end
                )
            else:
                resolved_schedule.planned_total_minutes = time_diff_minutes(
                    resolved_schedule.first_site_start, resolved_schedule.last_site_end
                )

            elapsed_site = time_diff_minutes(
                resolved_schedule.first_site_start, resolved_schedule.last_site_end
            )
            resolved_schedule.planned_worked_minutes = max(
                0, elapsed_site - (resolved_schedule.break_minutes or 0)
            )

            if not resolved_schedule.winning_rule_name:
                resolved_schedule.winning_rule_name = "Company Default Settings"

        # 5. Load scheduled work for today
        sw_q = select(ScheduledWork).where(
            ScheduledWork.employee_id == employee_id,
            ScheduledWork.work_date == work_date,
            ScheduledWork.status == "ACTIVE",
        )
        sw_res = await session.execute(sw_q)
        scheduled_works = sw_res.scalars().all()
        assignments = [
            ScheduledAssignment(
                scheduled_work_id=s.id,
                worksite_id=s.worksite_id,
                assigned_hours=float(s.assigned_hours),
                is_active=True,
            )
            for s in scheduled_works
        ]

        # 6. Check holidays, weekly off, and leave
        hol_q = select(PublicHoliday).where(
            PublicHoliday.holiday_date == work_date,
            PublicHoliday.country == country,
        )
        hol_res = await session.execute(hol_q)
        is_holiday = hol_res.scalar_one_or_none() is not None

        weekday_name = work_date.strftime("%A").upper()
        if employee.weekly_off_day and employee.weekly_off_day.strip():
            worker_off = employee.weekly_off_day.strip().upper()
            is_weekly_off = weekday_name == worker_off
            has_weekly_off = True
        else:
            is_weekly_off = False
            has_weekly_off = False

        leave_q = select(LeaveRequest.id).where(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.from_date <= work_date,
            LeaveRequest.to_date >= work_date,
            LeaveRequest.status == "APPROVED",
        )
        leave_res = await session.execute(leave_q)
        has_approved_leave = leave_res.scalar_one_or_none() is not None

        # 7. Query events for this work_date (in site's timezone)
        # Convert work_date start/end to UTC bounds
        day_start_local = datetime.combine(work_date, time.min, tzinfo=tz)
        day_end_local = datetime.combine(work_date, time.max, tzinfo=tz)
        start_utc = day_start_local.astimezone(UTC)
        end_utc = day_end_local.astimezone(UTC)

        events_q = (
            select(MobileEventLog)
            .where(
                MobileEventLog.employee_id == employee_id,
                MobileEventLog.event_timestamp_utc >= start_utc - timedelta(hours=2),
                MobileEventLog.event_timestamp_utc <= end_utc + timedelta(hours=2),
            )
            .order_by(MobileEventLog.event_timestamp_utc.asc())
        )
        events_res = await session.execute(events_q)
        raw_events = events_res.scalars().all()

        # Filter strictly to events whose local date matches work_date
        day_events: list[MobileEventLog] = []
        for ev in raw_events:
            ev_local_date = ev.event_timestamp_utc.astimezone(tz).date()
            if ev_local_date == work_date:
                day_events.append(ev)

        # If no events and no scheduled work, no record needed unless record already exists
        rec_q = (
            select(AttendanceRecord)
            .where(
                AttendanceRecord.employee_id == employee_id,
                AttendanceRecord.work_date == work_date,
            )
            .options(
                selectinload(AttendanceRecord.current_calculation),
                selectinload(AttendanceRecord.calculations),
                selectinload(AttendanceRecord.comments),
                selectinload(AttendanceRecord.approvals),
            )
        )
        rec_res = await session.execute(rec_q)
        record = rec_res.scalar_one_or_none()

        # Times an Engineer or Admin entered for the day replace the phone events (dead phone).
        manual = (
            await session.execute(
                select(AttendanceManualTime).where(
                    AttendanceManualTime.employee_id == employee_id,
                    AttendanceManualTime.work_date == work_date,
                    AttendanceManualTime.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()

        if not day_events and not assignments and record is None and manual is None:
            return None

        # 8. Build visits & tracking gaps
        assigned_site_ids = {a.worksite_id for a in assignments}
        events_for_visit = [
            EventForVisit(
                event_id=ev.event_id,
                event_type=ev.event_type,
                event_timestamp_utc=ev.event_timestamp_utc,
                sequence_number=ev.sequence_number,
                server_received_at=ev.server_received_at,
                server_verdict=ev.server_verdict or "OUTSIDE",
                server_site_id=ev.server_site_id,
                server_accommodation_id=ev.server_accommodation_id,
                flags=ev.flags or [],
            )
            for ev in day_events
        ]
        constructed_visits = build_visits_for_day(events_for_visit, work_date, assigned_site_ids)

        events_for_gap = [
            EventForGap(
                event_id=ev.event_id,
                event_type=ev.event_type,
                event_timestamp_utc=ev.event_timestamp_utc,
                location_captured_at_utc=ev.location_captured_at_utc,
                latitude=ev.latitude,
                longitude=ev.longitude,
                server_site_id=ev.server_site_id,
            )
            for ev in day_events
            if ev.event_type in ("LOCATION_DISABLED", "LOCATION_ENABLED")
        ]
        constructed_gaps = build_gaps_for_day(events_for_gap, work_date)
        if manual is not None:
            ordered_sites = [
                s.worksite_id for s in sorted(scheduled_works, key=lambda x: (x.sequence, x.id))
            ]
            constructed_visits = build_manual_visits(
                manual_id=manual.id,
                work_date=work_date,
                first_site_entry_at=manual.first_site_entry_at,
                last_site_exit_at=manual.last_site_exit_at,
                worksite_ids=ordered_sites,
                accommodation_id=employee.accommodation_id,
                accommodation_departure_at=manual.accommodation_departure_at,
                accommodation_return_at=manual.accommodation_return_at,
            )
            constructed_gaps = []

        # 9. Effective break minutes resolution: Salary Structure > Resolved Time Rule > Company Default
        effective_break_minutes: int
        effective_break_source: str

        if salary_break_minutes is not None and salary_break_minutes > 0:
            effective_break_minutes = salary_break_minutes
            effective_break_source = "SALARY_STRUCTURE"
        elif (
            resolved_schedule.winning_sources.get("break_minutes") is not None
            and resolved_schedule.break_minutes > 0
        ):
            effective_break_minutes = resolved_schedule.break_minutes
            effective_break_source = "TIME_RULE"
        else:
            default_break_setting = await SettingsService.get_setting(
                session, "default_break_minutes", country=country, as_of=work_date
            )
            try:
                effective_break_minutes = (
                    int(default_break_setting) if default_break_setting is not None else 0
                )
            except Exception:
                effective_break_minutes = 0
            effective_break_source = "COMPANY_DEFAULT"

        resolved_schedule.break_minutes = effective_break_minutes

        extra_flags: list[str] = []
        if not has_salary_structure:
            extra_flags.append("NO_SALARY_STRUCTURE")
        if not has_weekly_off:
            extra_flags.append("NO_WEEKLY_OFF_DAY")
        if manual is not None:
            extra_flags.append(MANUAL_TIMES_FLAG)
        elif assignments and not day_events and not has_approved_leave:
            extra_flags.append(NO_ATTENDANCE_EVENTS_FLAG)

        # 10. Run pure engine calculation
        calc_inputs = DailyCalculationInputs(
            employee_id=employee_id,
            tally_id=employee.tally_id,
            work_date=work_date,
            is_driver=employee.is_driver or False,
            has_accommodation=employee.accommodation_id is not None,
            standard_hours=standard_hours,
            schedule=resolved_schedule,
            assignments=assignments,
            visits=constructed_visits,
            gaps=constructed_gaps,
            is_public_holiday=is_holiday,
            is_weekly_off=is_weekly_off,
            is_ot2_weekday=False,
            has_approved_leave=has_approved_leave,
            first_site_break_override=None,
            break_source=effective_break_source,
            extra_flags=extra_flags,
        )
        calc_result = compute_daily_attendance(calc_inputs)

        # 11. Find or create AttendanceRecord
        if record is None:
            record = AttendanceRecord(
                employee_id=employee_id,
                work_date=work_date,
                business_status=calc_result.business_status,
                review_status=calc_result.review_status,
                locked=locked,
            )
            session.add(record)
            await session.flush()

        # 12. Versioning & Idempotency check via input_hash
        cur_calc = record.current_calculation
        if cur_calc is not None and cur_calc.input_hash == calc_result.input_hash:
            # Inputs unchanged; do not create duplicate version
            return record

        # Determine new version number
        max_ver_q = select(func.coalesce(func.max(AttendanceCalculation.version_no), 0)).where(
            AttendanceCalculation.attendance_record_id == record.id
        )
        max_ver_res = await session.execute(max_ver_q)
        next_ver = int(max_ver_res.scalar_one()) + 1

        # Check if previous calculation was APPROVED and now needs reset to PENDING_REVIEW
        new_review_status = calc_result.review_status
        if record.review_status == "APPROVED" and cur_calc is not None:
            if (
                cur_calc.worked_minutes != calc_result.worked_minutes
                or cur_calc.ot1_minutes != calc_result.ot1_minutes
                or cur_calc.ot2_minutes != calc_result.ot2_minutes
                or cur_calc.business_status != calc_result.business_status
            ):
                new_review_status = "PENDING_REVIEW"
        elif record.review_status == "REJECTED":
            # Recalculation creates fresh review
            new_review_status = "PENDING_REVIEW"

        # Build snapshot payloads
        visits_snap = [
            {
                "place_type": v.place_type,
                "worksite_id": str(v.worksite_id) if v.worksite_id else None,
                "accommodation_id": str(v.accommodation_id) if v.accommodation_id else None,
                "entry_at": v.entry_at.isoformat(),
                "exit_at": v.exit_at.isoformat() if v.exit_at else None,
                "exit_inferred": v.exit_inferred,
                "duration_minutes": v.duration_minutes,
                "counts_as_completed": v.counts_as_completed,
                "flags": v.flags,
            }
            for v in constructed_visits
        ]
        gaps_snap = [
            {
                "started_at": g.started_at.isoformat(),
                "ended_at": g.ended_at.isoformat() if g.ended_at else None,
                "duration_minutes": g.duration_minutes,
                "distance_between_m": g.distance_between_m,
                "is_inferred": g.is_inferred,
            }
            for g in constructed_gaps
        ]
        inputs_snap = {
            "manual_times_id": str(manual.id) if manual is not None else None,
            "standard_hours": standard_hours,
            "required_minutes": calc_result.required_minutes,
            "assigned_count": calc_result.assigned_count,
            "is_driver": employee.is_driver or False,
            "has_accommodation": employee.accommodation_id is not None,
            "break_minutes_used": calc_result.break_minutes_used,
            "break_source": calc_result.break_source,
        }
        source_event_ids = [ev.event_id for ev in day_events]

        calc_entry = AttendanceCalculation(
            attendance_record_id=record.id,
            version_no=next_ver,
            input_hash=calc_result.input_hash,
            calculated_at=datetime.now(UTC),
            engine_version="1.0.0",
            reason=reason,
            planned_accommodation_departure=calc_result.planned_accommodation_departure,
            planned_first_site_start=calc_result.planned_first_site_start,
            planned_break_minutes=calc_result.planned_break_minutes,
            planned_last_site_end=calc_result.planned_last_site_end,
            planned_accommodation_return=calc_result.planned_accommodation_return,
            planned_total_minutes=calc_result.planned_total_minutes,
            planned_worked_minutes=calc_result.planned_worked_minutes,
            standard_hours_minutes=calc_result.standard_hours_minutes,
            accommodation_departure_at=calc_result.accommodation_departure_at,
            first_site_entry_at=calc_result.first_site_entry_at,
            break_minutes_used=calc_result.break_minutes_used,
            break_source=calc_result.break_source,
            last_site_exit_at=calc_result.last_site_exit_at,
            accommodation_return_at=calc_result.accommodation_return_at,
            elapsed_site_minutes=calc_result.elapsed_site_minutes,
            shift_span_minutes=calc_result.shift_span_minutes,
            unaccounted_minutes=calc_result.unaccounted_minutes,
            worked_minutes=calc_result.worked_minutes,
            required_minutes=calc_result.required_minutes,
            variation_minutes=calc_result.variation_minutes,
            shortfall_minutes=calc_result.shortfall_minutes,
            grace_minutes=calc_result.grace_minutes,
            grace_applied=calc_result.grace_applied,
            satisfied=calc_result.satisfied,
            productive_minutes=calc_result.productive_minutes,
            transit_minutes=calc_result.transit_minutes,
            offsite_minutes=calc_result.offsite_minutes,
            idle_minutes=calc_result.idle_minutes,
            ot1_minutes=calc_result.ot1_minutes,
            ot2_minutes=calc_result.ot2_minutes,
            ot_threshold_minutes=calc_result.ot_threshold_minutes,
            day_type=calc_result.day_type,
            assigned_count=calc_result.assigned_count,
            completed_count=calc_result.completed_count,
            business_status=calc_result.business_status,
            flags=calc_result.flags,
            review_reasons=calc_result.review_reasons,
            visits_snapshot=visits_snap,
            gaps_snapshot=gaps_snap,
            inputs_snapshot=inputs_snap,
            source_event_ids=source_event_ids,
        )
        session.add(calc_entry)
        await session.flush()

        # Update record pointers and statuses
        record.current_calculation_id = calc_entry.id
        record.business_status = calc_result.business_status
        record.review_status = new_review_status
        record.locked = locked
        record.updated_at = datetime.now(UTC)

        # Replace persisted derived visits and gaps for this date
        await session.execute(
            delete(SiteVisit).where(
                SiteVisit.employee_id == employee_id,
                SiteVisit.work_date == work_date,
            )
        )
        for v in constructed_visits if manual is None else []:
            session.add(
                SiteVisit(
                    employee_id=employee_id,
                    work_date=work_date,
                    place_type=v.place_type,
                    worksite_id=v.worksite_id,
                    accommodation_id=v.accommodation_id,
                    entry_event_id=v.entry_event_id,
                    exit_event_id=v.exit_event_id,
                    entry_at=v.entry_at,
                    exit_at=v.exit_at,
                    exit_inferred=v.exit_inferred,
                    last_inside_at=v.last_inside_at,
                    counts_as_completed=v.counts_as_completed,
                    duration_minutes=v.duration_minutes,
                    flags=v.flags,
                )
            )

        await session.execute(
            delete(TrackingGap).where(
                TrackingGap.employee_id == employee_id,
                TrackingGap.work_date == work_date,
            )
        )
        for g in constructed_gaps:
            session.add(
                TrackingGap(
                    employee_id=employee_id,
                    work_date=work_date,
                    disabled_event_id=g.disabled_event_id,
                    enabled_event_id=g.enabled_event_id,
                    started_at=g.started_at,
                    ended_at=g.ended_at,
                    duration_minutes=g.duration_minutes,
                    disabled_latitude=g.disabled_latitude,
                    disabled_longitude=g.disabled_longitude,
                    disabled_location_captured_at=g.disabled_location_captured_at,
                    resumed_latitude=g.resumed_latitude,
                    resumed_longitude=g.resumed_longitude,
                    distance_between_m=g.distance_between_m,
                    start_inside_site_id=g.start_inside_site_id,
                    end_inside_site_id=g.end_inside_site_id,
                    is_inferred=g.is_inferred,
                )
            )

        await session.flush()
        return record

    @staticmethod
    async def is_payroll_locked(session: AsyncSession, employee_id: UUID, work_date: date) -> bool:
        """True when an APPROVED payroll run covers this employee-day."""
        from sqlalchemy import text

        chk_table = await session.execute(text("SELECT to_regclass('public.payroll_runs');"))
        if chk_table.scalar() is None:
            return False
        p_res = await session.execute(
            text(
                """
                SELECT pr.id FROM payroll_runs pr
                JOIN payroll_records rec ON rec.payroll_run_id = pr.id
                WHERE rec.employee_id = :emp_id
                  AND pr.period_start <= :w_date
                  AND pr.period_end >= :w_date
                  AND pr.status = 'APPROVED'
                LIMIT 1
                """
            ),
            {"emp_id": employee_id, "w_date": work_date},
        )
        return p_res.first() is not None

    @staticmethod
    async def set_manual_times(
        session: AsyncSession,
        *,
        employee_id: UUID,
        work_date: date,
        first_site_entry: time,
        last_site_exit: time,
        accommodation_departure: time | None,
        accommodation_return: time | None,
        reason: str,
        actor: User,
    ) -> AttendanceRecord:
        """Enter the times for a day the phone did not record (owner decision 25 Nov 2026).

        The previous manual times for the day, if any, are deactivated (kept). The day is then
        recalculated with reason MANUAL_CORRECTION: a new calculation version, flagged
        MANUAL_TIMES and sent to review; the old versions stay. Audited.
        """
        from fw.core.clock import site_today
        from fw.core.errors import AppError
        from fw.modules.audit import AuditService

        employee = await session.get(Employee, employee_id)
        if employee is None:
            raise AppError(code="NOT_FOUND", message="Employee not found", status_code=404)
        text_reason = (reason or "").strip()
        if not text_reason:
            raise AppError(
                code="REASON_REQUIRED",
                message="A reason is required for manual attendance times.",
                status_code=422,
            )
        country = (employee.country or "AE").upper()
        if work_date > site_today(country):
            raise AppError(
                code="FUTURE_DATE",
                message="Times can only be entered for today or a past day.",
                status_code=422,
            )
        if last_site_exit <= first_site_entry:
            raise AppError(
                code="INVALID_TIMES",
                message="The last site exit must be after the first site entry (same day).",
                status_code=422,
            )
        if (accommodation_departure is None) != (accommodation_return is None):
            raise AppError(
                code="INVALID_TIMES",
                message="Enter both the accommodation departure and return, or neither.",
                status_code=422,
            )
        if accommodation_departure is not None and accommodation_return is not None:
            if accommodation_departure > first_site_entry or accommodation_return < last_site_exit:
                raise AppError(
                    code="INVALID_TIMES",
                    message=(
                        "The accommodation departure must be before the first site entry, and "
                        "the return after the last site exit."
                    ),
                    status_code=422,
                )
        if await AttendanceService.is_payroll_locked(session, employee_id, work_date):
            raise AppError(
                code="PAYROLL_LOCKED",
                message="Payroll for this day is approved; its attendance can no longer change.",
                status_code=409,
            )

        tz = get_country_timezone(country)

        def at(t: time | None) -> datetime | None:
            return None if t is None else datetime.combine(work_date, t, tzinfo=tz)

        previous = list(
            (
                await session.execute(
                    select(AttendanceManualTime).where(
                        AttendanceManualTime.employee_id == employee_id,
                        AttendanceManualTime.work_date == work_date,
                        AttendanceManualTime.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        for old in previous:
            old.is_active = False
        await session.flush()

        first_at = at(first_site_entry)
        last_at = at(last_site_exit)
        assert first_at is not None and last_at is not None
        manual = AttendanceManualTime(
            employee_id=employee_id,
            work_date=work_date,
            first_site_entry_at=first_at,
            last_site_exit_at=last_at,
            accommodation_departure_at=at(accommodation_departure),
            accommodation_return_at=at(accommodation_return),
            reason=text_reason,
            created_by_user_id=actor.id,
        )
        session.add(manual)
        await session.flush()

        record = await AttendanceService.recalculate_day(
            session, employee_id, work_date, reason="MANUAL_CORRECTION"
        )
        if record is None:  # pragma: no cover - a manual row always yields a record
            raise AppError(code="NOT_CALCULATED", message="Day not calculated", status_code=500)

        def fmt(t: time | None) -> str | None:
            return t.strftime("%H:%M") if t is not None else None

        await AuditService.log_action(
            session=session,
            action="ATTENDANCE_MANUAL_TIMES",
            entity_type="AttendanceRecord",
            entity_id=str(record.id),
            actor_user_id=actor.id,
            actor_role=actor.role,
            reason=text_reason,
            diff={
                "employee_id": str(employee_id),
                "work_date": work_date.isoformat(),
                "first_site_entry": fmt(first_site_entry),
                "last_site_exit": fmt(last_site_exit),
                "accommodation_departure": fmt(accommodation_departure),
                "accommodation_return": fmt(accommodation_return),
                "replaced_manual_times_ids": [str(o.id) for o in previous],
                "calculation_id": str(record.current_calculation_id),
            },
        )
        return record

    @staticmethod
    async def add_comment(
        session: AsyncSession,
        attendance_id: UUID,
        author_user_id: UUID,
        request: AttendanceCommentCreateRequest,
    ) -> AttendanceComment:
        """Add an operational or explanation comment on an attendance record."""
        rec_q = select(AttendanceRecord).where(AttendanceRecord.id == attendance_id)
        rec_res = await session.execute(rec_q)
        record = rec_res.scalar_one_or_none()
        if not record:
            raise ValueError(f"Attendance record {attendance_id} not found")

        comment = AttendanceComment(
            attendance_id=attendance_id,
            author_user_id=author_user_id,
            comment_type=request.comment_type,
            comment_text=request.comment_text,
            scheduled_work_id=request.scheduled_work_id,
            created_at=datetime.now(UTC),
        )
        session.add(comment)

        # Supervisor adding comment on a REJECTED row routes it back to PENDING_REVIEW (DEC-43)
        if record.review_status == "REJECTED":
            record.review_status = "PENDING_REVIEW"
            record.updated_at = datetime.now(UTC)

        await session.flush()
        return comment

    @staticmethod
    async def record_decision(
        session: AsyncSession,
        attendance_id: UUID,
        reviewer_user_id: UUID,
        request: AttendanceDecisionRequest,
    ) -> AttendanceApproval:
        """Engineer or Admin approval or rejection decision."""
        rec_q = (
            select(AttendanceRecord)
            .where(AttendanceRecord.id == attendance_id)
            .options(selectinload(AttendanceRecord.current_calculation))
        )
        rec_res = await session.execute(rec_q)
        record = rec_res.scalar_one_or_none()
        if not record or not record.current_calculation_id:
            raise ValueError(f"Attendance record {attendance_id} has no calculation to approve")

        decision = request.decision.upper()
        if decision not in ("APPROVED", "REJECTED"):
            raise ValueError("Decision must be APPROVED or REJECTED")

        if decision == "REJECTED" and not request.comment:
            raise ValueError("Comment is required when rejecting attendance")

        approval = AttendanceApproval(
            attendance_id=attendance_id,
            reviewer_user_id=reviewer_user_id,
            decision=decision,
            comment=request.comment,
            calculation_id=record.current_calculation_id,
            created_at=datetime.now(UTC),
        )
        session.add(approval)

        record.review_status = decision
        record.updated_at = datetime.now(UTC)

        await session.flush()
        return approval

    @staticmethod
    async def get_timeline(
        session: AsyncSession,
        attendance_id: UUID,
    ) -> AttendanceTimelineResponse:
        """Construct the derived timeline of observed vs inferred items for an attendance day."""
        rec_q = (
            select(AttendanceRecord)
            .where(AttendanceRecord.id == attendance_id)
            .options(
                selectinload(AttendanceRecord.current_calculation),
            )
        )
        rec_res = await session.execute(rec_q)
        record = rec_res.scalar_one_or_none()
        if not record:
            raise ValueError(f"Attendance record {attendance_id} not found")

        emp_q = select(Employee.name).where(Employee.id == record.employee_id)
        emp_res = await session.execute(emp_q)
        emp_name = emp_res.scalar_one_or_none() or "Unknown"

        # Load visits and gaps
        v_q = (
            select(SiteVisit)
            .where(
                SiteVisit.employee_id == record.employee_id,
                SiteVisit.work_date == record.work_date,
            )
            .order_by(SiteVisit.entry_at.asc())
        )
        v_res = await session.execute(v_q)
        visits = list(v_res.scalars().all())

        g_q = (
            select(TrackingGap)
            .where(
                TrackingGap.employee_id == record.employee_id,
                TrackingGap.work_date == record.work_date,
            )
            .order_by(TrackingGap.started_at.asc())
        )
        g_res = await session.execute(g_q)
        gaps = list(g_res.scalars().all())

        # Resolve worksite and accommodation names
        worksite_ids = [v.worksite_id for v in visits if v.worksite_id]
        worksite_map: dict[UUID, str] = {}
        if worksite_ids:
            ws_res = await session.execute(
                select(Worksite.id, Worksite.job_name, Worksite.job_number).where(
                    Worksite.id.in_(worksite_ids)
                )
            )
            for w_id, w_name, w_code in ws_res.all():
                worksite_map[w_id] = (
                    f"{w_name} ({w_code})"
                    if w_name and w_code
                    else (w_name or w_code or "Worksite")
                )

        accom_ids = [v.accommodation_id for v in visits if v.accommodation_id]
        accom_map: dict[UUID, str] = {}
        if accom_ids:
            ac_res = await session.execute(
                select(Accommodation.id, Accommodation.name).where(Accommodation.id.in_(accom_ids))
            )
            for a_id, a_name in ac_res.all():
                accom_map[a_id] = a_name or "Worker Accommodation"

        # Resolve coordinates for entry events
        event_ids = [v.entry_event_id for v in visits if v.entry_event_id]
        event_coords: dict[UUID, tuple[float | None, float | None]] = {}
        if event_ids:
            ev_res = await session.execute(
                select(
                    MobileEventLog.event_id, MobileEventLog.latitude, MobileEventLog.longitude
                ).where(MobileEventLog.event_id.in_(event_ids))
            )
            for e_id, lat, lng in ev_res.all():
                event_coords[e_id] = (
                    float(lat) if lat is not None else None,
                    float(lng) if lng is not None else None,
                )

        timeline_items: list[AttendanceTimelineItem] = []

        # Visits as timeline items
        for v in visits:
            if v.place_type == "SITE":
                label = "Worksite Visit"
                place = (
                    worksite_map.get(v.worksite_id) if v.worksite_id else None
                ) or "Assigned Worksite"
            else:
                label = "Accommodation Stay"
                place = (
                    accom_map.get(v.accommodation_id) if v.accommodation_id else None
                ) or "Worker Accommodation"

            lat, lng = event_coords.get(v.entry_event_id, (None, None))
            timeline_items.append(
                AttendanceTimelineItem(
                    item_id=str(v.id),
                    item_type=f"{v.place_type}_VISIT",
                    label=label,
                    place_name=place,
                    started_at=v.entry_at,
                    ended_at=v.exit_at or v.last_inside_at,
                    duration_minutes=v.duration_minutes,
                    is_inferred=v.exit_inferred,
                    flags=v.flags or [],
                    details={
                        "counts_as_completed": v.counts_as_completed,
                        "entry_event_id": str(v.entry_event_id),
                        "exit_event_id": str(v.exit_event_id) if v.exit_event_id else None,
                        "latitude": lat,
                        "longitude": lng,
                    },
                )
            )

        # Gaps as timeline items
        for g in gaps:
            timeline_items.append(
                AttendanceTimelineItem(
                    item_id=str(g.id),
                    item_type="TRACKING_GAP",
                    label="Tracking Interruption (Location Disabled)",
                    place_name="Offsite / Commute",
                    started_at=g.started_at,
                    ended_at=g.ended_at,
                    duration_minutes=g.duration_minutes,
                    is_inferred=g.is_inferred,
                    flags=["TRACKING_GAP"],
                    details={
                        "distance_between_m": g.distance_between_m,
                    },
                )
            )

        # Fallback to raw events if no visits or gaps yet
        if not timeline_items:
            start_utc = datetime.combine(record.work_date, time.min, tzinfo=UTC) - timedelta(
                hours=4
            )
            end_utc = datetime.combine(record.work_date, time.max, tzinfo=UTC) + timedelta(hours=4)
            raw_q = (
                select(MobileEventLog)
                .where(
                    MobileEventLog.employee_id == record.employee_id,
                    MobileEventLog.event_timestamp_utc >= start_utc,
                    MobileEventLog.event_timestamp_utc <= end_utc,
                )
                .order_by(MobileEventLog.event_timestamp_utc.asc())
            )
            raw_res = await session.execute(raw_q)
            for ev in raw_res.scalars().all():
                lat = float(ev.latitude) if ev.latitude is not None else None
                lng = float(ev.longitude) if ev.longitude is not None else None
                timeline_items.append(
                    AttendanceTimelineItem(
                        item_id=str(ev.event_id),
                        item_type=f"EVENT_{ev.event_type}",
                        label=f"Location {ev.event_type}",
                        place_name=f"Verdict: {ev.server_verdict or 'RECORDED'}",
                        started_at=ev.event_timestamp_utc,
                        ended_at=None,
                        duration_minutes=0,
                        is_inferred=False,
                        flags=ev.flags or [],
                        details={
                            "latitude": lat,
                            "longitude": lng,
                            "accuracy": ev.accuracy_meters,
                            "verdict": ev.server_verdict,
                        },
                    )
                )

        timeline_items.sort(key=lambda x: x.started_at)

        return AttendanceTimelineResponse(
            attendance_id=record.id,
            employee_id=record.employee_id,
            employee_name=emp_name,
            work_date=record.work_date,
            timeline_items=timeline_items,
        )

    @staticmethod
    def _attendance_review_filter(norm_status: str) -> Any:
        from fw.modules.attendance.models import AttendanceRecord

        if norm_status == "PENDING":
            return AttendanceRecord.review_status == "PENDING_REVIEW"
        if norm_status in ("APPROVED", "REJECTED"):
            return AttendanceRecord.review_status == norm_status
        if norm_status == "DECIDED":
            return AttendanceRecord.review_status.in_(("APPROVED", "REJECTED"))
        return None  # ALL

    @staticmethod
    async def count_attendance_reviews(
        session: AsyncSession,
        current_user: User,
        status: str | None = "PENDING",
        *,
        scope_resolved: bool = False,
        scoped_ids: set[UUID] | None = None,
    ) -> int:
        """Attendance days in the approvals inbox scope for a status (count only).

        Pass ``scope_resolved=True`` with ``scoped_ids`` when the scope is already known.
        """
        from fw.modules.attendance.models import AttendanceRecord
        from fw.modules.org import ScopeService

        if not scope_resolved:
            scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
        q = select(func.count(AttendanceRecord.id))
        clause = AttendanceService._attendance_review_filter((status or "PENDING").upper())
        if clause is not None:
            q = q.where(clause)
        if scoped_ids is not None:
            q = q.where(AttendanceRecord.employee_id.in_(scoped_ids))
        return int((await session.execute(q)).scalar_one() or 0)

    @staticmethod
    async def get_attendance_approvals(
        session: AsyncSession,
        current_user: User,
        status: str | None = "PENDING",
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int, int]:
        """One page of attendance days for the approvals inbox.

        Returns (rows, pending count, total in the selected status). The current calculation
        comes from the join (no second load of the same rows).
        """
        from fw.modules.attendance.models import AttendanceCalculation, AttendanceRecord
        from fw.modules.org import Employee, ScopeService

        norm_status = (status or "PENDING").upper()
        scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
        att_q = (
            select(AttendanceRecord, Employee.name, AttendanceCalculation)
            .join(Employee, Employee.id == AttendanceRecord.employee_id)
            .outerjoin(
                AttendanceCalculation,
                AttendanceCalculation.id == AttendanceRecord.current_calculation_id,
            )
        )
        if scoped_ids is not None:
            att_q = att_q.where(AttendanceRecord.employee_id.in_(scoped_ids))
        clause = AttendanceService._attendance_review_filter(norm_status)
        if clause is not None:
            att_q = att_q.where(clause)

        att_q = att_q.order_by(desc(AttendanceRecord.work_date), AttendanceRecord.id)
        if limit is not None:
            att_q = att_q.offset(offset).limit(limit)
        att_rows_db = (await session.execute(att_q)).all()

        attendance_rows = [
            {
                "id": str(rec.id),
                "employee_id": str(rec.employee_id),
                "employee_name": emp_name,
                "work_date": str(rec.work_date),
                "review_status": rec.review_status,
                "business_status": rec.business_status,
                "review_reasons": calc.review_reasons if calc else [],
                "worked_minutes": calc.worked_minutes if calc else 0,
                "required_minutes": calc.required_minutes if calc else 0,
                "variation_minutes": calc.variation_minutes if calc else 0,
                "ot1_minutes": calc.ot1_minutes if calc else 0,
                "ot2_minutes": calc.ot2_minutes if calc else 0,
            }
            for rec, emp_name, calc in att_rows_db
        ]
        pending_att_count = await AttendanceService.count_attendance_reviews(
            session, current_user, "PENDING", scope_resolved=True, scoped_ids=scoped_ids
        )
        total = (
            pending_att_count
            if norm_status == "PENDING"
            else await AttendanceService.count_attendance_reviews(
                session, current_user, norm_status, scope_resolved=True, scoped_ids=scoped_ids
            )
        )
        return attendance_rows, pending_att_count, total
