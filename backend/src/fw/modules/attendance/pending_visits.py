"""Service layer for pending visits detection and follow-up lifecycle."""

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.errors import AppError
from fw.modules.attendance.models import (
    AttendanceComment,
    AttendanceRecord,
    PendingVisit,
    SiteVisit,
)
from fw.modules.attendance.schemas import (
    PendingVisitListResponse,
    PendingVisitResponse,
)
from fw.modules.identity import User
from fw.modules.jobs import JobItem, Worksite
from fw.modules.notifications import NotificationService
from fw.modules.org import Employee, EmployeeReportingLine, OrgService
from fw.modules.scheduling import LeaveRequest, ScheduledWork
from fw.modules.settings import SettingsService

logger = structlog.get_logger(__name__)


class PendingVisitsService:
    """Detection, lifecycle management, and reminders for pending site visits."""

    @staticmethod
    async def detect_pending_visits(
        session: AsyncSession,
        target_date: date,
        min_visit_minutes: int = 10,
    ) -> int:
        """Detect unvisited scheduled work occurrences at day close and create PendingVisit rows.

        Workers with approved leave on target_date are explicitly exempted.
        If delayed events confirm a visit later, any existing OPEN pending visit is closed.
        """
        # 1. Fetch active scheduled work for target_date
        sched_stmt = select(ScheduledWork).where(
            ScheduledWork.work_date == target_date,
            ScheduledWork.status == "ACTIVE",
        )
        scheduled_items = list((await session.execute(sched_stmt)).scalars().all())
        if not scheduled_items:
            return 0

        # 2. Fetch approved leaves covering target_date
        leave_stmt = select(LeaveRequest.employee_id).where(
            LeaveRequest.status == "APPROVED",
            LeaveRequest.from_date <= target_date,
            LeaveRequest.to_date >= target_date,
        )
        leave_emp_ids = set((await session.execute(leave_stmt)).scalars().all())

        # 3. Fetch completed site visits for target_date
        visits_stmt = select(
            SiteVisit.employee_id,
            SiteVisit.worksite_id,
        ).where(
            SiteVisit.work_date == target_date,
            or_(
                SiteVisit.counts_as_completed.is_(True),
                SiteVisit.duration_minutes >= min_visit_minutes,
            ),
        )
        visit_rows = (await session.execute(visits_stmt)).all()
        visited_pairs = {(v[0], v[1]) for v in visit_rows}

        detected_count = 0
        today_date = datetime.now(UTC).date()

        for sw in scheduled_items:
            # Exempt if worker is on approved leave
            if sw.employee_id in leave_emp_ids:
                continue

            has_visited = (sw.employee_id, sw.worksite_id) in visited_pairs

            # Check if pending visit already exists for this scheduled work
            pv_stmt = select(PendingVisit).where(PendingVisit.scheduled_work_id == sw.id)
            pv = (await session.execute(pv_stmt)).scalar_one_or_none()

            if not has_visited:
                if pv is None:
                    new_pv = PendingVisit(
                        scheduled_work_id=sw.id,
                        occurrence_id=sw.occurrence_id,
                        worksite_id=sw.worksite_id,
                        employee_id=sw.employee_id,
                        due_date=target_date,
                        detected_on=today_date,
                        status="OPEN",
                    )
                    session.add(new_pv)
                    detected_count += 1
            else:
                # If a visit was confirmed (e.g. delayed batch upload), close any OPEN pending visit
                if pv is not None and pv.status == "OPEN":
                    pv.status = "CLOSED"
                    pv.closed_reason = "VISIT_CONFIRMED_LATE"
                    pv.closed_at = datetime.now(UTC)

        await session.flush()
        return detected_count

    @staticmethod
    async def explain_pending_visit(
        session: AsyncSession,
        pending_visit_id: UUID,
        user: User,
        explanation: str,
    ) -> PendingVisit:
        """Record a supervisor explanation comment and move pending visit status to EXPLAINED."""
        pv = await session.get(PendingVisit, pending_visit_id)
        if not pv:
            raise AppError(code="NOT_FOUND", message="Pending visit not found", status_code=404)
        if pv.status == "CLOSED":
            raise AppError(code="INVALID_STATUS", message="Cannot explain a closed pending visit", status_code=400)

        # Ensure an AttendanceRecord exists for employee and work_date
        rec_stmt = select(AttendanceRecord).where(
            AttendanceRecord.employee_id == pv.employee_id,
            AttendanceRecord.work_date == pv.due_date,
        )
        rec = (await session.execute(rec_stmt)).scalar_one_or_none()
        if not rec:
            rec = AttendanceRecord(
                employee_id=pv.employee_id,
                work_date=pv.due_date,
                business_status="ABSENT",
                review_status="PENDING_REVIEW",
            )
            session.add(rec)
            await session.flush()

        comment = AttendanceComment(
            attendance_id=rec.id,
            author_user_id=user.id,
            comment_type="PENDING_VISIT_EXPLANATION",
            comment_text=explanation,
            scheduled_work_id=pv.scheduled_work_id,
        )
        session.add(comment)
        await session.flush()

        pv.status = "EXPLAINED"
        pv.explanation_comment_id = comment.id
        await session.flush()
        return pv

    @staticmethod
    async def reschedule_pending_visit(
        session: AsyncSession,
        pending_visit_id: UUID,
        user: User,
        work_date: date,
        employee_ids: list[UUID],
    ) -> list[ScheduledWork]:
        """Reschedule pending visit to a new work date with source FOLLOW_UP."""
        pv = await session.get(PendingVisit, pending_visit_id)
        if not pv:
            raise AppError(code="NOT_FOUND", message="Pending visit not found", status_code=404)
        if not employee_ids:
            raise AppError(code="VALIDATION_ERROR", message="At least one employee must be selected", status_code=400)

        orig_sw = await session.get(ScheduledWork, pv.scheduled_work_id)
        if not orig_sw:
            raise AppError(code="NOT_FOUND", message="Original scheduled work not found", status_code=404)

        new_items = []
        for emp_id in employee_ids:
            new_sw = ScheduledWork(
                employee_id=emp_id,
                worksite_id=orig_sw.worksite_id,
                job_item_id=orig_sw.job_item_id,
                occurrence_id=orig_sw.occurrence_id,
                work_date=work_date,
                assigned_hours=orig_sw.assigned_hours,
                source="FOLLOW_UP",
                status="ACTIVE",
                original_scheduled_work_id=orig_sw.id,
                created_by_user_id=user.id,
            )
            session.add(new_sw)
            new_items.append(new_sw)

        await session.flush()

        pv.status = "RESCHEDULED"
        if new_items:
            pv.rescheduled_to_scheduled_work_id = new_items[0].id
        await session.flush()

        # If a pending visit alert was open, resolve it
        await NotificationService.resolve_alerts_for_ref(
            session=session,
            ref_type="PENDING_VISIT",
            ref_id=pv.id,
            resolved_by_user_id=user.id,
        )

        return new_items

    @staticmethod
    async def close_pending_visit(
        session: AsyncSession,
        pending_visit_id: UUID,
        user: User,
        reason: str,
    ) -> PendingVisit:
        """Close a pending visit with an engineer reason."""
        pv = await session.get(PendingVisit, pending_visit_id)
        if not pv:
            raise AppError(code="NOT_FOUND", message="Pending visit not found", status_code=404)
        if not reason or not reason.strip():
            raise AppError(code="VALIDATION_ERROR", message="A reason is required to close a pending visit", status_code=400)

        pv.status = "CLOSED"
        pv.closed_reason = reason.strip()
        pv.closed_by_user_id = user.id
        pv.closed_at = datetime.now(UTC)
        await session.flush()

        # Resolve open alerts for this pending visit
        await NotificationService.resolve_alerts_for_ref(
            session=session,
            ref_type="PENDING_VISIT",
            ref_id=pv.id,
            resolved_by_user_id=user.id,
        )

        return pv

    @staticmethod
    async def check_pending_visit_reminders(
        session: AsyncSession,
    ) -> int:
        """Emit PENDING_VISIT reminder alerts daily while pending visits remain OPEN."""
        pv_stmt = (
            select(PendingVisit, Employee.name, Worksite.job_name)
            .join(Employee, PendingVisit.employee_id == Employee.id)
            .join(Worksite, PendingVisit.worksite_id == Worksite.id)
            .where(PendingVisit.status == "OPEN")
        )
        rows = (await session.execute(pv_stmt)).all()
        reminded_count = 0

        for pv, worker_name, worksite_name in rows:
            # Check if alert already open
            alert_stmt = select(NotificationService).where() if False else None
            # Use NotificationService to check existing open alert
            from fw.modules.notifications.models import Alert
            existing = await session.execute(
                select(Alert.id).where(
                    Alert.alert_type == "PENDING_VISIT",
                    Alert.ref_id == pv.id,
                    Alert.status == "OPEN",
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue

            await NotificationService.create_alert(
                session=session,
                alert_type="PENDING_VISIT",
                title=f"Pending Visit: {worker_name} @ {worksite_name}",
                message=f"Missed visit for {worker_name} at {worksite_name} on {pv.due_date} requires follow-up.",
                ref_type="PENDING_VISIT",
                ref_id=pv.id,
                employee_id=pv.employee_id,
                target_role="SUPERVISOR",
                details={
                    "pending_visit_id": str(pv.id),
                    "worksite_id": str(pv.worksite_id),
                    "due_date": str(pv.due_date),
                },
            )
            reminded_count += 1

        await session.flush()
        return reminded_count

    @staticmethod
    async def get_pending_visits(
        session: AsyncSession,
        user: User,
        status: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        worksite_id: UUID | None = None,
        supervisor_id: UUID | None = None,
        employee_id: UUID | None = None,
    ) -> PendingVisitListResponse:
        """Query pending visits with filtering, scoping, and escalation indicators."""
        today = datetime.now(UTC).date()

        # 1. Resolve escalation days setting
        esc_days_setting = await SettingsService.get_setting(
            session=session,
            key="pending_visit_escalation_days",
            default=3,
        )
        try:
            esc_days = int(esc_days_setting) if esc_days_setting else 3
        except (ValueError, TypeError):
            esc_days = 3

        # 2. Build query
        stmt = (
            select(
                PendingVisit,
                Employee.name,
                Employee.tally_id,
                Worksite.job_name.label("worksite_name"),
                JobItem.name.label("job_item_name"),
                AttendanceComment.comment_text.label("latest_explanation"),
                User.username.label("closed_by_name"),
                ScheduledWork.job_item_id,
            )
            .join(Employee, PendingVisit.employee_id == Employee.id)
            .join(Worksite, PendingVisit.worksite_id == Worksite.id)
            .join(ScheduledWork, PendingVisit.scheduled_work_id == ScheduledWork.id)
            .outerjoin(JobItem, ScheduledWork.job_item_id == JobItem.id)
            .outerjoin(AttendanceComment, PendingVisit.explanation_comment_id == AttendanceComment.id)
            .outerjoin(User, PendingVisit.closed_by_user_id == User.id)
            .order_by(PendingVisit.due_date.desc(), PendingVisit.created_at.desc())
        )

        # Scope restriction
        if user.role != "ADMIN":
            scoped_ids = await OrgService.get_scoped_employee_ids(session, user)
            if scoped_ids:
                stmt = stmt.where(PendingVisit.employee_id.in_(scoped_ids))
            elif user.employee_id:
                stmt = stmt.where(PendingVisit.employee_id == user.employee_id)
            else:
                stmt = stmt.where(PendingVisit.employee_id.in_([]))

        if employee_id:
            stmt = stmt.where(PendingVisit.employee_id == employee_id)
        if worksite_id:
            stmt = stmt.where(PendingVisit.worksite_id == worksite_id)
        if from_date:
            stmt = stmt.where(PendingVisit.due_date >= from_date)
        if to_date:
            stmt = stmt.where(PendingVisit.due_date <= to_date)
        if status:
            stmt = stmt.where(PendingVisit.status == status.upper())

        rows = (await session.execute(stmt)).all()

        # Build supervisor lookup
        emp_ids = [r[0].employee_id for r in rows]
        sup_lookup: dict[UUID, tuple[UUID, str]] = {}
        if emp_ids:
            sup_stmt = (
                select(
                    EmployeeReportingLine.employee_id,
                    EmployeeReportingLine.manager_id,
                    Employee.name,
                )
                .join(Employee, EmployeeReportingLine.manager_id == Employee.id)
                .where(
                    EmployeeReportingLine.employee_id.in_(emp_ids),
                    EmployeeReportingLine.relationship == "SUPERVISOR",
                )
            )
            sup_rows = (await session.execute(sup_stmt)).all()
            for s_emp_id, m_id, m_name in sup_rows:
                sup_lookup[s_emp_id] = (m_id, m_name)

        items: list[PendingVisitResponse] = []
        open_count = 0
        explained_count = 0
        rescheduled_count = 0
        closed_count = 0
        escalated_count = 0

        for pv, emp_name, tally, site_name, ji_name, explanation, closed_by_user_name, ji_id in rows:
            sup_info = sup_lookup.get(pv.employee_id)
            sup_id = sup_info[0] if sup_info else None
            sup_name = sup_info[1] if sup_info else None

            # Filter by supervisor_id if requested
            if supervisor_id and sup_id != supervisor_id:
                continue

            age_days = max(0, (today - pv.due_date).days)
            is_escalated = (pv.status == "OPEN" and age_days >= esc_days)

            # Tallies
            if pv.status == "OPEN":
                open_count += 1
            elif pv.status == "EXPLAINED":
                explained_count += 1
            elif pv.status == "RESCHEDULED":
                rescheduled_count += 1
            elif pv.status == "CLOSED":
                closed_count += 1

            if is_escalated:
                escalated_count += 1

            items.append(
                PendingVisitResponse(
                    id=pv.id,
                    scheduled_work_id=pv.scheduled_work_id,
                    occurrence_id=pv.occurrence_id,
                    worksite_id=pv.worksite_id,
                    worksite_name=site_name,
                    job_item_id=ji_id,
                    job_item_name=ji_name,
                    employee_id=pv.employee_id,
                    employee_name=emp_name,
                    tally_id=tally,
                    supervisor_id=sup_id,
                    supervisor_name=sup_name,
                    due_date=pv.due_date,
                    detected_on=pv.detected_on,
                    age_days=age_days,
                    status=pv.status,
                    is_escalated=is_escalated,
                    explanation_comment_id=pv.explanation_comment_id,
                    latest_explanation=explanation,
                    rescheduled_to_scheduled_work_id=pv.rescheduled_to_scheduled_work_id,
                    closed_by_user_id=pv.closed_by_user_id,
                    closed_by_name=closed_by_user_name,
                    closed_reason=pv.closed_reason,
                    closed_at=pv.closed_at,
                    created_at=pv.created_at,
                )
            )

        return PendingVisitListResponse(
            items=items,
            open_count=open_count,
            explained_count=explained_count,
            rescheduled_count=rescheduled_count,
            closed_count=closed_count,
            escalated_count=escalated_count,
            total_count=len(items),
        )
