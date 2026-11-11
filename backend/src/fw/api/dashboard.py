"""Dashboard management summary statistics API endpoint."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.modules.attendance.models import (
    AttendanceCalculation,
    AttendanceRecord,
    PendingVisit,
)
from fw.modules.events import EventsService
from fw.modules.identity import User, get_current_user
from fw.modules.jobs import Worksite
from fw.modules.notifications.models import Alert
from fw.modules.org import EmployeeDocument, OrgService
from fw.modules.scheduling.models import LeaveRequest, ReassignmentRequest, ScheduledWork

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class AttendanceSummaryItem(BaseModel):
    present: int = 0
    partial: int = 0
    absent: int = 0
    not_started: int = 0
    total_scheduled: int = 0


class LiveWorkersSummaryItem(BaseModel):
    active: int = 0
    no_recent_signal: int = 0
    location_disabled: int = 0
    not_scheduled: int = 0
    total: int = 0


class DashboardSummaryResponse(BaseModel):
    today_date: str
    attendance: AttendanceSummaryItem
    live_workers: LiveWorkersSummaryItem
    pending_visits_count: int
    late_arrivals_count: int
    overtime_hours_today: float
    open_alerts_count: int
    expiring_documents_count: int
    pending_approvals_count: int


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DashboardSummaryResponse:
    """Get role-aware overview statistics: today's attendance, live workers, pending visits, late arrivals, OT."""
    now = datetime.now(UTC)
    local_today = now.astimezone(ZoneInfo("Asia/Dubai")).date()

    # Scope resolution
    scoped_ids: set[UUID] | None = None
    if current_user.role != "ADMIN":
        scoped_list = await OrgService.get_scoped_employee_ids(session, current_user)
        scoped_ids = set(scoped_list) if scoped_list else set()

    # 1. Scheduled work today
    sched_q = (
        select(
            ScheduledWork.employee_id,
            ScheduledWork.worksite_id,
            ScheduledWork.assigned_hours,
            Worksite.job_name.label("worksite_name"),
        )
        .outerjoin(Worksite, ScheduledWork.worksite_id == Worksite.id)
        .where(
            ScheduledWork.work_date == local_today,
            ScheduledWork.status == "ACTIVE",
        )
    )
    if scoped_ids is not None:
        sched_q = sched_q.where(ScheduledWork.employee_id.in_(scoped_ids))
    elif current_user.role != "ADMIN" and current_user.employee_id:
        sched_q = sched_q.where(ScheduledWork.employee_id == current_user.employee_id)

    sched_rows = (await session.execute(sched_q)).all()
    scheduled_emp_ids: set[UUID] = set()
    today_assignments_by_emp: dict[UUID, list[dict[str, Any]]] = {}
    for emp_id, site_id, hours, site_name in sched_rows:
        scheduled_emp_ids.add(emp_id)
        if emp_id not in today_assignments_by_emp:
            today_assignments_by_emp[emp_id] = []
        today_assignments_by_emp[emp_id].append(
            {
                "worksite_id": str(site_id),
                "worksite_name": site_name or "Unknown Worksite",
                "assigned_hours": float(hours) if hours is not None else 0.0,
            }
        )

    # 2. Attendance records today
    att_q = select(AttendanceRecord).where(AttendanceRecord.work_date == local_today)
    if scoped_ids is not None:
        att_q = att_q.where(AttendanceRecord.employee_id.in_(scoped_ids))
    elif current_user.role != "ADMIN" and current_user.employee_id:
        att_q = att_q.where(AttendanceRecord.employee_id == current_user.employee_id)

    att_records = list((await session.execute(att_q)).scalars().all())

    present_count = sum(1 for a in att_records if a.business_status == "PRESENT")
    partial_count = sum(1 for a in att_records if a.business_status == "PARTIAL")
    absent_count = sum(1 for a in att_records if a.business_status == "ABSENT")
    recorded_emp_ids = {a.employee_id for a in att_records}
    not_started_count = max(0, len(scheduled_emp_ids - recorded_emp_ids))

    # 3. Live workers
    live_resp = await EventsService.get_live_positions(
        session=session,
        user=current_user,
        scoped_employee_ids=scoped_ids,
        scheduled_employee_ids=scheduled_emp_ids,
        today_assignments_by_emp=today_assignments_by_emp,
        as_of=now,
    )

    # 4. Pending visits
    pv_q = select(func.count(PendingVisit.id)).where(PendingVisit.status == "OPEN")
    if scoped_ids is not None:
        pv_q = pv_q.where(PendingVisit.employee_id.in_(scoped_ids))
    elif current_user.role != "ADMIN" and current_user.employee_id:
        pv_q = pv_q.where(PendingVisit.employee_id == current_user.employee_id)
    pending_visits_count = (await session.execute(pv_q)).scalar() or 0

    # 5. Overtime hours today & Late arrivals
    calc_q = (
        select(AttendanceCalculation)
        .join(AttendanceRecord, AttendanceCalculation.attendance_record_id == AttendanceRecord.id)
        .where(
            AttendanceRecord.work_date == local_today,
            AttendanceRecord.current_calculation_id == AttendanceCalculation.id,
        )
    )
    if scoped_ids is not None:
        calc_q = calc_q.where(AttendanceRecord.employee_id.in_(scoped_ids))
    elif current_user.role != "ADMIN" and current_user.employee_id:
        calc_q = calc_q.where(AttendanceRecord.employee_id == current_user.employee_id)

    calcs = list((await session.execute(calc_q)).scalars().all())
    ot_minutes_total = sum((c.ot1_minutes + c.ot2_minutes) for c in calcs)
    late_arrivals_count = sum(
        1 for c in calcs if any(f in ("SHORTFALL_BEYOND_GRACE", "LATE_ARRIVAL") for f in c.flags)
    )

    # 6. Open alerts
    alert_q = select(func.count(Alert.id)).where(Alert.status == "OPEN")
    if scoped_ids is not None:
        alert_q = alert_q.where(
            (Alert.employee_id.in_(scoped_ids))
            | (Alert.target_user_id == current_user.id)
            | (Alert.target_role == current_user.role)
        )
    elif current_user.role != "ADMIN" and current_user.employee_id:
        alert_q = alert_q.where(
            (Alert.employee_id == current_user.employee_id)
            | (Alert.target_user_id == current_user.id)
            | (Alert.target_role == current_user.role)
        )
    open_alerts_count = (await session.execute(alert_q)).scalar() or 0

    # 7. Expiring documents count
    doc_q = select(func.count(EmployeeDocument.id)).where(
        EmployeeDocument.is_active.is_(True),
        EmployeeDocument.expiry_date <= local_today,
    )
    if scoped_ids is not None:
        doc_q = doc_q.where(EmployeeDocument.employee_id.in_(scoped_ids))
    expiring_docs_count = (await session.execute(doc_q)).scalar() or 0

    # 8. Pending approvals count
    pending_leaves = (
        await session.execute(
            select(func.count(LeaveRequest.id)).where(LeaveRequest.status == "REQUESTED")
        )
    ).scalar() or 0
    pending_reassign = (
        await session.execute(
            select(func.count(ReassignmentRequest.id)).where(
                ReassignmentRequest.status == "REQUESTED"
            )
        )
    ).scalar() or 0
    pending_att_reviews = (
        await session.execute(
            select(func.count(AttendanceRecord.id)).where(
                AttendanceRecord.review_status == "PENDING_REVIEW"
            )
        )
    ).scalar() or 0
    pending_approvals_count = pending_leaves + pending_reassign + pending_att_reviews

    return DashboardSummaryResponse(
        today_date=str(local_today),
        attendance=AttendanceSummaryItem(
            present=present_count,
            partial=partial_count,
            absent=absent_count,
            not_started=not_started_count,
            total_scheduled=len(scheduled_emp_ids),
        ),
        live_workers=LiveWorkersSummaryItem(
            active=live_resp.active_count,
            no_recent_signal=live_resp.offline_count,
            location_disabled=live_resp.disabled_count,
            not_scheduled=live_resp.not_scheduled_count,
            total=live_resp.total_count,
        ),
        pending_visits_count=pending_visits_count,
        late_arrivals_count=late_arrivals_count,
        overtime_hours_today=round(ot_minutes_total / 60.0, 1),
        open_alerts_count=open_alerts_count,
        expiring_documents_count=expiring_docs_count,
        pending_approvals_count=pending_approvals_count,
    )
