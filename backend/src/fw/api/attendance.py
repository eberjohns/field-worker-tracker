from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fw.core.db import get_db
from fw.core.errors import AppError
from fw.modules.attendance.models import (
    AttendanceCalculation,
    AttendanceRecord,
)
from fw.modules.attendance.schemas import (
    AttendanceApprovalResponse,
    AttendanceCalculationSnapshot,
    AttendanceCommentCreateRequest,
    AttendanceCommentResponse,
    AttendanceDecisionRequest,
    AttendanceListResponse,
    AttendanceRecalculateRequest,
    AttendanceRecalculateResponse,
    AttendanceRecordResponse,
    AttendanceTimelineResponse,
)
from fw.modules.attendance.service import AttendanceService
from fw.modules.events.models import MobileEventLog
from fw.modules.events.schemas import MobileEventResponse
from fw.modules.identity import User, get_current_user, require_role
from fw.modules.org import ScopeService
from fw.modules.org.models import Employee

router = APIRouter(tags=["attendance"])


def _to_calc_snapshot(calc: AttendanceCalculation | None) -> AttendanceCalculationSnapshot | None:
    if not calc:
        return None
    return AttendanceCalculationSnapshot(
        id=calc.id,
        version_no=calc.version_no,
        input_hash=calc.input_hash,
        calculated_at=calc.calculated_at,
        engine_version=calc.engine_version,
        reason=calc.reason,
        planned_accommodation_departure=calc.planned_accommodation_departure,
        planned_first_site_start=calc.planned_first_site_start,
        planned_break_minutes=calc.planned_break_minutes,
        planned_last_site_end=calc.planned_last_site_end,
        planned_accommodation_return=calc.planned_accommodation_return,
        planned_total_minutes=calc.planned_total_minutes,
        planned_worked_minutes=calc.planned_worked_minutes,
        standard_hours_minutes=calc.standard_hours_minutes,
        accommodation_departure_at=calc.accommodation_departure_at,
        first_site_entry_at=calc.first_site_entry_at,
        break_minutes_used=calc.break_minutes_used,
        break_source=calc.break_source,
        last_site_exit_at=calc.last_site_exit_at,
        accommodation_return_at=calc.accommodation_return_at,
        elapsed_site_minutes=calc.elapsed_site_minutes,
        shift_span_minutes=calc.shift_span_minutes,
        unaccounted_minutes=calc.unaccounted_minutes,
        worked_minutes=calc.worked_minutes,
        required_minutes=calc.required_minutes,
        variation_minutes=calc.variation_minutes,
        shortfall_minutes=calc.shortfall_minutes,
        grace_minutes=calc.grace_minutes,
        grace_applied=calc.grace_applied,
        satisfied=calc.satisfied,
        productive_minutes=calc.productive_minutes,
        transit_minutes=calc.transit_minutes,
        offsite_minutes=calc.offsite_minutes,
        idle_minutes=calc.idle_minutes,
        ot1_minutes=calc.ot1_minutes,
        ot2_minutes=calc.ot2_minutes,
        ot_threshold_minutes=calc.ot_threshold_minutes,
        day_type=calc.day_type,
        assigned_count=calc.assigned_count,
        completed_count=calc.completed_count,
        business_status=calc.business_status,
        flags=calc.flags or [],
        review_reasons=calc.review_reasons or [],
        visits_snapshot=calc.visits_snapshot or [],
        gaps_snapshot=calc.gaps_snapshot or [],
        inputs_snapshot=calc.inputs_snapshot or {},
        source_event_ids=calc.source_event_ids or [],
    )


def _to_record_response(
    rec: AttendanceRecord,
    employee: Employee | None,
    supervisor_name: str | None = None,
) -> AttendanceRecordResponse:
    calc_snap = _to_calc_snapshot(rec.current_calculation)
    comments = [
        AttendanceCommentResponse(
            id=c.id,
            attendance_id=c.attendance_id,
            author_user_id=c.author_user_id,
            author_name="User",
            comment_type=c.comment_type,
            comment_text=c.comment_text,
            scheduled_work_id=c.scheduled_work_id,
            created_at=c.created_at,
        )
        for c in (rec.comments or [])
    ]
    approvals = [
        AttendanceApprovalResponse(
            id=a.id,
            attendance_id=a.attendance_id,
            reviewer_user_id=a.reviewer_user_id,
            reviewer_name="Reviewer",
            decision=a.decision,
            comment=a.comment,
            calculation_id=a.calculation_id,
            created_at=a.created_at,
        )
        for a in (rec.approvals or [])
    ]
    return AttendanceRecordResponse(
        id=rec.id,
        employee_id=rec.employee_id,
        employee_name=employee.name if employee else "Unknown",
        tally_id=employee.tally_id if employee else "",
        supervisor_name=supervisor_name,
        work_date=rec.work_date,
        business_status=rec.business_status,
        review_status=rec.review_status,
        locked=rec.locked,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
        current_calculation=calc_snap,
        comments=comments,
        approvals=approvals,
    )


@router.get("/attendance", response_model=AttendanceListResponse)
async def list_attendance(
    from_date: date | None = None,
    to_date: date | None = None,
    employee_id: UUID | None = None,
    supervisor_id: UUID | None = None,
    review_status: str | None = None,
    business_status: str | None = None,
    flag: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AttendanceListResponse:
    """List attendance records with filtering and scope restrictions."""
    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)

    q = (
        select(AttendanceRecord, Employee)
        .join(Employee, Employee.id == AttendanceRecord.employee_id)
        .outerjoin(
            AttendanceCalculation,
            AttendanceCalculation.id == AttendanceRecord.current_calculation_id,
        )
        .options(
            selectinload(AttendanceRecord.current_calculation),
            selectinload(AttendanceRecord.comments),
            selectinload(AttendanceRecord.approvals),
        )
    )

    if scoped_ids is not None:
        q = q.where(AttendanceRecord.employee_id.in_(scoped_ids))

    if employee_id:
        q = q.where(AttendanceRecord.employee_id == employee_id)
    if from_date:
        q = q.where(AttendanceRecord.work_date >= from_date)
    if to_date:
        q = q.where(AttendanceRecord.work_date <= to_date)
    if review_status:
        q = q.where(AttendanceRecord.review_status == review_status.upper())
    if business_status:
        q = q.where(AttendanceRecord.business_status == business_status.upper())
    if flag:
        q = q.where(AttendanceCalculation.flags.any(flag.upper()))

    # Total count
    count_q = select(func.count()).select_from(q.subquery())
    count_res = await session.execute(count_q)
    total = count_res.scalar_one()

    # Pagination & sort by work_date desc, employee_name asc
    q = (
        q.order_by(desc(AttendanceRecord.work_date), Employee.name.asc())
        .offset(offset)
        .limit(limit)
    )
    res = await session.execute(q)
    rows = res.all()

    items = [_to_record_response(rec, emp) for rec, emp in rows]
    return AttendanceListResponse(items=items, total=total)


@router.get("/attendance/exceptions", response_model=AttendanceListResponse)
async def list_attendance_exceptions(
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AttendanceListResponse:
    """List attendance records requiring review (exceptions queue)."""
    return await list_attendance(
        from_date=from_date,
        to_date=to_date,
        review_status="PENDING_REVIEW",
        limit=limit,
        offset=offset,
        current_user=current_user,
        session=session,
    )


@router.get("/attendance/{attendance_id}", response_model=AttendanceRecordResponse)
async def get_attendance_detail(
    attendance_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AttendanceRecordResponse:
    """Get complete attendance record details, calculations, comments, and approvals."""
    q = (
        select(AttendanceRecord, Employee)
        .join(Employee, Employee.id == AttendanceRecord.employee_id)
        .where(AttendanceRecord.id == attendance_id)
        .options(
            selectinload(AttendanceRecord.current_calculation),
            selectinload(AttendanceRecord.comments),
            selectinload(AttendanceRecord.approvals),
        )
    )
    res = await session.execute(q)
    row = res.first()
    if not row:
        raise AppError(code="NOT_FOUND", message="Attendance record not found", status_code=404)

    record, employee = row
    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
    if scoped_ids is not None and record.employee_id not in scoped_ids:
        raise AppError(code="OUT_OF_SCOPE", message="Record is out of scope", status_code=403)

    return _to_record_response(record, employee)


@router.get(
    "/attendance/{attendance_id}/calculations", response_model=list[AttendanceCalculationSnapshot]
)
async def list_attendance_calculations(
    attendance_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[AttendanceCalculationSnapshot]:
    """Get all calculation versions of an attendance record."""
    rec_q = select(AttendanceRecord).where(AttendanceRecord.id == attendance_id)
    rec_res = await session.execute(rec_q)
    record = rec_res.scalar_one_or_none()
    if not record:
        raise AppError(code="NOT_FOUND", message="Attendance record not found", status_code=404)

    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
    if scoped_ids is not None and record.employee_id not in scoped_ids:
        raise AppError(code="OUT_OF_SCOPE", message="Record is out of scope", status_code=403)

    calcs_q = (
        select(AttendanceCalculation)
        .where(AttendanceCalculation.attendance_record_id == attendance_id)
        .order_by(desc(AttendanceCalculation.version_no))
    )
    calcs_res = await session.execute(calcs_q)
    calcs = calcs_res.scalars().all()
    return [_to_calc_snapshot(c) for c in calcs if c is not None]


@router.get("/attendance/{attendance_id}/timeline", response_model=AttendanceTimelineResponse)
async def get_attendance_timeline(
    attendance_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> AttendanceTimelineResponse:
    """Get derived timeline with observed and inferred items."""
    rec_q = select(AttendanceRecord).where(AttendanceRecord.id == attendance_id)
    rec_res = await session.execute(rec_q)
    record = rec_res.scalar_one_or_none()
    if not record:
        raise AppError(code="NOT_FOUND", message="Attendance record not found", status_code=404)

    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
    if scoped_ids is not None and record.employee_id not in scoped_ids:
        raise AppError(code="OUT_OF_SCOPE", message="Record is out of scope", status_code=403)

    return await AttendanceService.get_timeline(session, attendance_id)


@router.post("/attendance/{attendance_id}/comments", response_model=AttendanceCommentResponse)
async def add_attendance_comment(
    attendance_id: UUID,
    request: AttendanceCommentCreateRequest,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER", "SUPERINTENDENT", "SUPERVISOR")),
    session: AsyncSession = Depends(get_db),
) -> AttendanceCommentResponse:
    """Add a supervisor or engineer comment on an attendance record."""
    rec_q = select(AttendanceRecord).where(AttendanceRecord.id == attendance_id)
    rec_res = await session.execute(rec_q)
    record = rec_res.scalar_one_or_none()
    if not record:
        raise AppError(code="NOT_FOUND", message="Attendance record not found", status_code=404)

    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
    if scoped_ids is not None and record.employee_id not in scoped_ids:
        raise AppError(code="OUT_OF_SCOPE", message="Record is out of scope", status_code=403)

    comment = await AttendanceService.add_comment(
        session=session,
        attendance_id=attendance_id,
        author_user_id=current_user.id,
        request=request,
    )

    return AttendanceCommentResponse(
        id=comment.id,
        attendance_id=comment.attendance_id,
        author_user_id=comment.author_user_id,
        author_name=current_user.username,
        comment_type=comment.comment_type,
        comment_text=comment.comment_text,
        scheduled_work_id=comment.scheduled_work_id,
        created_at=comment.created_at,
    )


@router.post("/attendance/{attendance_id}/decisions", response_model=AttendanceApprovalResponse)
async def record_attendance_decision(
    attendance_id: UUID,
    request: AttendanceDecisionRequest,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> AttendanceApprovalResponse:
    """Record an Engineer or Admin approval/rejection decision on an attendance record."""
    rec_q = select(AttendanceRecord).where(AttendanceRecord.id == attendance_id)
    rec_res = await session.execute(rec_q)
    record = rec_res.scalar_one_or_none()
    if not record:
        raise AppError(code="NOT_FOUND", message="Attendance record not found", status_code=404)

    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
    if scoped_ids is not None and record.employee_id not in scoped_ids:
        raise AppError(code="OUT_OF_SCOPE", message="Record is out of scope", status_code=403)

    try:
        approval = await AttendanceService.record_decision(
            session=session,
            attendance_id=attendance_id,
            reviewer_user_id=current_user.id,
            request=request,
        )
    except ValueError as e:
        raise AppError(code="VALIDATION_ERROR", message=str(e), status_code=422) from e

    return AttendanceApprovalResponse(
        id=approval.id,
        attendance_id=approval.attendance_id,
        reviewer_user_id=approval.reviewer_user_id,
        reviewer_name=current_user.username,
        decision=approval.decision,
        comment=approval.comment,
        calculation_id=approval.calculation_id,
        created_at=approval.created_at,
    )


@router.post("/attendance/recalculate", response_model=AttendanceRecalculateResponse)
async def recalculate_attendance(
    request: AttendanceRecalculateRequest,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> AttendanceRecalculateResponse:
    """Admin manual trigger to recalculate attendance for an employee or date range."""
    count = 0
    cur_date = request.from_date

    # Determine employees to recompute
    if request.employee_id:
        emp_ids = [request.employee_id]
    else:
        emp_q = select(Employee.id).where(Employee.is_active.is_(True))
        emp_res = await session.execute(emp_q)
        emp_ids = list(emp_res.scalars().all())

    while cur_date <= request.to_date:
        for eid in emp_ids:
            res = await AttendanceService.recalculate_day(
                session=session,
                employee_id=eid,
                work_date=cur_date,
                reason=request.reason,
            )
            if res is not None:
                count += 1
        cur_date += timedelta(days=1)

    return AttendanceRecalculateResponse(
        recalculated_count=count,
        message=f"Recalculated {count} attendance records between {request.from_date} and {request.to_date}.",
    )


@router.get("/events", response_model=list[MobileEventResponse])
async def list_events(
    employee_id: UUID | None = None,
    event_date: date | None = None,
    event_type: str | None = None,
    flag: str | None = None,
    limit: int = Query(100, le=200),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[MobileEventResponse]:
    """Query verified raw event logs in scope (read-only audit)."""
    scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)

    q = select(MobileEventLog).order_by(desc(MobileEventLog.event_timestamp_utc)).limit(limit)

    if scoped_ids is not None:
        q = q.where(MobileEventLog.employee_id.in_(scoped_ids))
    if employee_id:
        q = q.where(MobileEventLog.employee_id == employee_id)
    if event_type:
        q = q.where(MobileEventLog.event_type == event_type.upper())
    if flag:
        q = q.where(MobileEventLog.flags.any(flag.upper()))
    if event_date:
        start_utc = datetime.combine(event_date, time.min, tzinfo=UTC)
        end_utc = datetime.combine(event_date, time.max, tzinfo=UTC)
        q = q.where(
            MobileEventLog.event_timestamp_utc >= start_utc - timedelta(hours=4),
            MobileEventLog.event_timestamp_utc <= end_utc + timedelta(hours=4),
        )

    res = await session.execute(q)
    logs = res.scalars().all()

    return [
        MobileEventResponse(
            event_id=ev.event_id,
            employee_id=ev.employee_id,
            device_id=ev.device_id,
            event_type=ev.event_type,
            event_timestamp_utc=ev.event_timestamp_utc,
            location_captured_at_utc=ev.location_captured_at_utc,
            latitude=ev.latitude,
            longitude=ev.longitude,
            accuracy_meters=ev.accuracy_meters,
            is_mock_location=ev.is_mock_location,
            sequence_number=ev.sequence_number,
            server_received_at=ev.server_received_at,
            processing_status=ev.processing_status,
            server_site_id=ev.server_site_id,
            server_accommodation_id=ev.server_accommodation_id,
            server_verdict=ev.server_verdict,
            distance_to_polygon_m=ev.distance_to_polygon_m,
            flags=ev.flags or [],
        )
        for ev in logs
    ]
