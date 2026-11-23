"""API endpoints for Worksites, Job Items, Boundaries, and Occurrences (Phase 04)."""

import io
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import xlsxwriter
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.clock import site_today
from fw.core.db import get_db
from fw.core.errors import AppError
from fw.modules.audit import AuditService
from fw.modules.budget import BudgetService
from fw.modules.identity import User, get_current_user, require_role, verify_password
from fw.modules.jobs import (
    BoundaryCopyRequest,
    BoundaryCopyToRequest,
    BoundaryImportRequest,
    BoundaryImportResponse,
    BoundaryQueueResponse,
    BoundaryUpdateRequest,
    GenerateOccurrencesRequest,
    JobItem,
    JobItemCreate,
    JobItemDestination,
    JobItemResponse,
    JobItemUpdate,
    JobItemValidationResponse,
    JobOccurrenceResponse,
    JobOccurrenceUpdate,
    JobsService,
    Worksite,
    WorksiteCreate,
    WorksiteDetailResponse,
    WorksiteResponse,
    WorksiteSupervisorAssign,
    WorksiteSupervisorBulkAssign,
    WorksiteSupervisorBulkAssignResult,
    WorksiteSupervisorProposal,
    WorksiteSupervisorRead,
    WorksiteUpdate,
)
from fw.modules.org import DeactivateRequest, EntityLifecycleResponse, ReactivateRequest
from fw.modules.scheduling import (
    AccessScope,
    SchedulingService,
    WorksiteSupervisorProposalService,
)

router = APIRouter(tags=["jobs"])


async def _with_budget(
    session: AsyncSession, detail: WorksiteDetailResponse, user: User
) -> WorksiteDetailResponse:
    """Add planned man-hours (and, for Admin, cost) per item and the worksite totals (DEC-59)."""
    res = await BudgetService.worksite_budget_by_id(
        session, detail.id, is_admin=user.role == "ADMIN"
    )
    if res is None:
        return detail
    per_item, totals = res
    for it in [*detail.items, *detail.job_items]:
        it.budget = per_item.get(it.id)
    detail.budget_totals = totals
    return detail


async def _item_with_budget(
    session: AsyncSession, item: JobItemResponse, user: User
) -> JobItemResponse:
    res = await BudgetService.worksite_budget_by_id(
        session, item.worksite_id, is_admin=user.role == "ADMIN"
    )
    if res is not None:
        item.budget = res[0].get(item.id)
    return item


# --- Worksites ---
@router.get("/worksites", response_model=list[WorksiteResponse])
async def list_worksites(
    q: str | None = Query(None, description="Search by job number or name"),
    group_id: UUID | None = None,
    zone_id: UUID | None = None,
    country: str | None = None,
    has_boundary: bool | None = None,
    is_active: bool | None = True,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    unassigned: bool = Query(False, description="Only worksites with no active supervisor"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[WorksiteResponse]:
    """List worksites in the caller's scope (DEC-57).

    Deactivated worksites are visible to Admin only; budget is hidden for non-admins.
    """
    effective_is_active = is_active if current_user.role == "ADMIN" else True
    scope = await AccessScope.resolve(session, current_user)
    worksites = await JobsService.list_worksites(
        session=session,
        scoped_ids=scope.worksite_filter,
        unassigned_only=unassigned,
        q=q,
        group_id=group_id,
        zone_id=zone_id,
        country=country,
        has_boundary=has_boundary,
        is_active=effective_is_active,
        limit=limit,
        offset=offset,
    )
    if current_user.role != "ADMIN":
        for w in worksites:
            w.budget_amount = None
    return worksites


@router.get("/worksites/supervisor-proposals", response_model=list[WorksiteSupervisorProposal])
async def list_worksite_supervisor_proposals(
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> list[WorksiteSupervisorProposal]:
    """Propose supervisors from current crews for each worksite (Admin reviews; DEC-57)."""
    return await WorksiteSupervisorProposalService.propose(session)


@router.post(
    "/worksites/supervisors/bulk-assign", response_model=WorksiteSupervisorBulkAssignResult
)
async def bulk_assign_worksite_supervisors(
    payload: WorksiteSupervisorBulkAssign,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> WorksiteSupervisorBulkAssignResult:
    """Assign the worksite/supervisor pairs Admin confirmed (all or nothing, audited)."""
    return await WorksiteSupervisorProposalService.bulk_assign(
        session=session,
        payload=payload,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )


@router.get("/job-items/destinations", response_model=list[JobItemDestination])
async def list_job_item_destinations(
    current_user: User = Depends(require_role("ADMIN", "ENGINEER", "SUPERINTENDENT", "SUPERVISOR")),
    session: AsyncSession = Depends(get_db),
) -> list[JobItemDestination]:
    """All active job items, for reassignment request destinations (not scoped; no costs)."""
    return await JobsService.list_destinations(session)


@router.get("/worksites/export")
async def export_worksites_excel(
    q: str | None = Query(None),
    country: str | None = None,
    is_active: bool | None = True,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
):
    """Export worksites list with a dedicated Job_Items worksheet (Admin & Engineer only)."""
    effective_is_active = is_active if current_user.role == "ADMIN" else True
    scope = await AccessScope.resolve(session, current_user)
    worksites = await JobsService.list_worksites(
        session=session,
        scoped_ids=scope.worksite_filter,
        q=q,
        country=country,
        is_active=effective_is_active,
        limit=5000,
        offset=0,
    )

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    hdr = workbook.add_format(
        {"bold": True, "bg_color": "#1E293B", "font_color": "#FFFFFF", "border": 1}
    )
    cell = workbook.add_format({"border": 1})

    # Sheet 1: Worksites
    ws_sheet = workbook.add_worksheet("Worksites")
    headers = [
        "Job Number",
        "Worksite Name",
        "Country",
        "Group",
        "Zone",
        "Has Boundary",
        "Rep Latitude",
        "Rep Longitude",
        "Status",
    ]
    is_admin = current_user.role == "ADMIN"
    if is_admin:
        headers.append("Budget Amount")

    for i, h in enumerate(headers):
        ws_sheet.write(0, i, h, hdr)
        ws_sheet.set_column(i, i, max(len(h) + 4, 15))

    for row_idx, w in enumerate(worksites, start=1):
        ws_sheet.write(row_idx, 0, w.job_number, cell)
        ws_sheet.write(row_idx, 1, w.job_name, cell)
        ws_sheet.write(row_idx, 2, w.country, cell)
        ws_sheet.write(row_idx, 3, w.group_name or "", cell)
        ws_sheet.write(row_idx, 4, w.zone_name or "", cell)
        ws_sheet.write(row_idx, 5, "Yes" if w.has_boundary else "No", cell)
        ws_sheet.write(row_idx, 6, str(w.rep_latitude) if w.rep_latitude else "", cell)
        ws_sheet.write(row_idx, 7, str(w.rep_longitude) if w.rep_longitude else "", cell)
        ws_sheet.write(row_idx, 8, "ACTIVE" if w.is_active else "INACTIVE", cell)
        if is_admin:
            ws_sheet.write(
                row_idx, 9, str(w.budget_amount) if w.budget_amount is not None else "", cell
            )

    # Sheet 2: Job_Items
    ji_sheet = workbook.add_worksheet("Job_Items")
    ji_headers = [
        "Job Number",
        "Worksite Name",
        "Sub Item Code",
        "Staff Grade Description",
        "Planned Grade Code",
        "Start Date",
        "End Date",
        "Frequency Unit",
        "Occurrences Per Period",
        "Period Interval",
        "Required Staff",
        "Hours Per Occurrence",
        "Deployment Type",
        "Break Override (min)",
        "Status",
    ]
    for i, h in enumerate(ji_headers):
        ji_sheet.write(0, i, h, hdr)
        ji_sheet.set_column(i, i, max(len(h) + 4, 15))

    ws_map = {w.id: w for w in worksites}
    ws_ids = list(ws_map.keys())
    ji_row_idx = 1
    if ws_ids:
        ji_stmt = (
            select(JobItem)
            .where(JobItem.worksite_id.in_(ws_ids))
            .order_by(JobItem.worksite_id, JobItem.sub_item_code)
        )
        ji_rows = (await session.execute(ji_stmt)).scalars().all()
        for item in ji_rows:
            parent_ws = ws_map.get(item.worksite_id)
            if not parent_ws:
                continue
            ji_sheet.write(ji_row_idx, 0, parent_ws.job_number, cell)
            ji_sheet.write(ji_row_idx, 1, parent_ws.job_name, cell)
            ji_sheet.write(ji_row_idx, 2, item.sub_item_code, cell)
            ji_sheet.write(ji_row_idx, 3, item.staff_grade_description, cell)
            ji_sheet.write(ji_row_idx, 4, item.planned_grade_code, cell)
            ji_sheet.write(ji_row_idx, 5, str(item.start_date) if item.start_date else "", cell)
            ji_sheet.write(ji_row_idx, 6, str(item.end_date) if item.end_date else "", cell)
            ji_sheet.write(ji_row_idx, 7, item.frequency_unit, cell)
            ji_sheet.write(ji_row_idx, 8, float(item.occurrences_per_period), cell)
            ji_sheet.write(ji_row_idx, 9, item.period_interval, cell)
            ji_sheet.write(ji_row_idx, 10, item.required_staff_count, cell)
            ji_sheet.write(ji_row_idx, 11, float(item.hours_per_occurrence_per_staff), cell)
            ji_sheet.write(ji_row_idx, 12, item.deployment_type, cell)
            ji_sheet.write(
                ji_row_idx,
                13,
                item.break_override_minutes if item.break_override_minutes is not None else "",
                cell,
            )
            ji_sheet.write(ji_row_idx, 14, "ACTIVE" if item.is_active else "INACTIVE", cell)
            ji_row_idx += 1

    workbook.close()
    filename = f"Worksites_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        io.BytesIO(output.getvalue()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/worksites", response_model=WorksiteResponse, status_code=status.HTTP_201_CREATED)
async def create_worksite(
    payload: WorksiteCreate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> WorksiteResponse:
    """Create a worksite record (Admin only)."""
    return await JobsService.create_worksite(
        session=session,
        payload=payload,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )


@router.get("/worksites/{worksite_id}", response_model=WorksiteDetailResponse)
async def get_worksite_detail(
    worksite_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorksiteDetailResponse:
    """Get full details of a worksite in the caller's scope (DEC-57)."""
    scope = await AccessScope.resolve(session, current_user)
    if not scope.can_view_worksite(worksite_id):
        raise AppError(code="NOT_FOUND", message="Worksite not found.", status_code=404)
    detail = await JobsService.get_worksite(session=session, worksite_id=worksite_id)
    if current_user.role != "ADMIN":
        if not detail.is_active:
            raise AppError(code="NOT_FOUND", message="Worksite not found.", status_code=404)
        detail.items = [it for it in detail.items if it.is_active]
        detail.budget_amount = None
    return await _with_budget(session, detail, current_user)


@router.get("/worksites/{worksite_id}/supervisors", response_model=list[WorksiteSupervisorRead])
async def list_worksite_supervisors(
    worksite_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[WorksiteSupervisorRead]:
    """List supervisors assigned to a worksite in the caller's scope."""
    scope = await AccessScope.resolve(session, current_user)
    if not scope.can_view_worksite(worksite_id):
        raise AppError(code="NOT_FOUND", message="Worksite not found.", status_code=404)
    return await JobsService.list_worksite_supervisors(session, worksite_id)


@router.post(
    "/worksites/{worksite_id}/supervisors",
    response_model=WorksiteSupervisorRead,
    status_code=status.HTTP_201_CREATED,
)
async def assign_worksite_supervisor(
    worksite_id: UUID,
    payload: WorksiteSupervisorAssign,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> WorksiteSupervisorRead:
    """Assign a supervisor to a worksite (Admin & Engineer only)."""
    return await JobsService.assign_worksite_supervisor(
        session=session,
        worksite_id=worksite_id,
        supervisor_id=payload.supervisor_id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )


@router.delete(
    "/worksites/{worksite_id}/supervisors/{supervisor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_worksite_supervisor(
    worksite_id: UUID,
    supervisor_id: UUID,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Unassign a supervisor from a worksite (Admin & Engineer only)."""
    removed = await JobsService.remove_worksite_supervisor(
        session=session,
        worksite_id=worksite_id,
        supervisor_id=supervisor_id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    if not removed:
        raise AppError(
            "SUPERVISOR_NOT_ASSIGNED", "Supervisor is not assigned to worksite", status_code=404
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/worksites/{worksite_id}/deactivation-impact")
async def get_worksite_deactivation_impact(
    worksite_id: UUID,
    effective_date: date | None = Query(None),
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Preview scheduling impact of deactivating a worksite (Admin only)."""
    ws = await session.get(Worksite, worksite_id)
    if not ws:
        raise AppError(code="NOT_FOUND", message="Worksite not found.", status_code=404)

    eff = effective_date or site_today()
    items = list(
        (
            await session.execute(
                select(JobItem).where(JobItem.worksite_id == ws.id, JobItem.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    item_ids = [it.id for it in items]
    impact = await SchedulingService(session).get_job_items_deactivation_impact(
        job_item_ids=item_ids,
        effective_date=eff,
    )
    return {
        "worksite_id": str(ws.id),
        "job_number": ws.job_number,
        "job_name": ws.job_name,
        "effective_date": eff.isoformat(),
        "active_job_items": len(item_ids),
        **impact,
    }


@router.post("/worksites/{worksite_id}/deactivate", response_model=EntityLifecycleResponse)
async def deactivate_worksite(
    worksite_id: UUID,
    payload: DeactivateRequest,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> EntityLifecycleResponse:
    """Admin-only worksite deactivation with DEACTIVATE confirmation + admin password + worker schedule release."""
    if payload.confirmation_text.strip() != "DEACTIVATE":
        raise AppError(
            code="VALIDATION_ERROR",
            message='You must type "DEACTIVATE" exactly to confirm deactivation.',
            status_code=400,
        )
    if not payload.admin_password or not verify_password(
        payload.admin_password, current_user.credential_hash
    ):
        raise AppError(
            code="INVALID_PASSWORD",
            message="Admin password is incorrect. Deactivation aborted.",
            status_code=403,
        )
    if not payload.reason or not payload.reason.strip():
        raise AppError(
            code="REASON_REQUIRED",
            message="A reason for deactivation is required.",
            status_code=400,
        )

    ws = await session.get(Worksite, worksite_id)
    if not ws:
        raise AppError(code="NOT_FOUND", message="Worksite not found.", status_code=404)
    if not ws.is_active:
        raise AppError(
            code="INVALID_STATE", message="Worksite is already deactivated.", status_code=400
        )

    eff = payload.effective_date or site_today()
    ws.is_active = False
    ws.version += 1

    items = list(
        (
            await session.execute(
                select(JobItem).where(JobItem.worksite_id == ws.id, JobItem.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )
    item_ids: list[UUID] = []
    for it in items:
        it.is_active = False
        it.version += 1
        item_ids.append(it.id)

    cascade_summary, affected_workers = await SchedulingService(
        session
    ).cascade_job_items_deactivation(
        job_item_ids=item_ids,
        effective_date=eff,
        reason_label="WORKSITE_DEACTIVATED",
    )
    cascade_summary["deactivated_job_items"] = len(item_ids)
    cascade_summary["freed_workers"] = len(affected_workers)

    await AuditService.log_action(
        session=session,
        action="DEACTIVATE_WORKSITE",
        entity_type="worksite",
        entity_id=str(ws.id),
        diff={
            "job_number": ws.job_number,
            "job_name": ws.job_name,
            "effective_date": eff.isoformat(),
            **cascade_summary,
        },
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        reason=payload.reason.strip(),
    )
    await session.commit()

    return EntityLifecycleResponse(
        status="DEACTIVATED",
        entity_id=ws.id,
        is_active=False,
        effective_date=eff,
        summary=cascade_summary,
        message=(
            f"Worksite {ws.job_number} deactivated effective {eff.isoformat()}. "
            f"{cascade_summary['cancelled_future_shifts']} future shift(s) cancelled, freeing assigned workers."
        ),
    )


@router.post("/worksites/{worksite_id}/reactivate", response_model=EntityLifecycleResponse)
async def reactivate_worksite(
    worksite_id: UUID,
    payload: ReactivateRequest,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> EntityLifecycleResponse:
    """Admin-only clean reactivation (Option A): sets worksite active without restoring old schedules."""
    if payload.confirmation_text.strip() != "REACTIVATE":
        raise AppError(
            code="VALIDATION_ERROR",
            message='You must type "REACTIVATE" exactly to confirm reactivation.',
            status_code=400,
        )
    if not payload.admin_password or not verify_password(
        payload.admin_password, current_user.credential_hash
    ):
        raise AppError(
            code="INVALID_PASSWORD",
            message="Admin password is incorrect. Reactivation aborted.",
            status_code=403,
        )
    if not payload.reason or not payload.reason.strip():
        raise AppError(
            code="REASON_REQUIRED",
            message="A reason for reactivation is required.",
            status_code=400,
        )

    ws = await session.get(Worksite, worksite_id)
    if not ws:
        raise AppError(code="NOT_FOUND", message="Worksite not found.", status_code=404)
    if ws.is_active:
        raise AppError(code="INVALID_STATE", message="Worksite is already active.", status_code=400)

    ws.is_active = True
    ws.version += 1

    reactivated_items = 0
    if payload.reactivate_items:
        items = list(
            (
                await session.execute(
                    select(JobItem).where(
                        JobItem.worksite_id == ws.id, JobItem.is_active.is_(False)
                    )
                )
            )
            .scalars()
            .all()
        )
        for it in items:
            it.is_active = True
            it.version += 1
            reactivated_items += 1

    await AuditService.log_action(
        session=session,
        action="REACTIVATE_WORKSITE",
        entity_type="worksite",
        entity_id=str(ws.id),
        diff={
            "job_number": ws.job_number,
            "reactivated_job_items": reactivated_items,
            "schedules_restored": False,
        },
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        reason=payload.reason.strip(),
    )
    await session.commit()

    return EntityLifecycleResponse(
        status="REACTIVATED",
        entity_id=ws.id,
        is_active=True,
        summary={"reactivated_job_items": reactivated_items, "schedules_restored": False},
        message=(
            f"Worksite {ws.job_number} reactivated cleanly ({reactivated_items} item(s) restored). "
            "No old schedules were restored."
        ),
    )


@router.patch("/worksites/{worksite_id}", response_model=WorksiteResponse)
async def update_worksite(
    worksite_id: UUID,
    payload: WorksiteUpdate,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> WorksiteResponse:
    """Update worksite metadata with optimistic locking (Admin only)."""
    return await JobsService.update_worksite(
        session=session,
        worksite_id=worksite_id,
        payload=payload,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )


# --- Boundaries & Queue ---
@router.get("/boundary-queue", response_model=BoundaryQueueResponse)
async def get_boundary_queue(
    status: str = Query("UNSET", pattern="^(ALL|UNSET|SET|PENDING)$"),
    entity_type: str | None = Query(None, pattern="^(WORKSITE|ACCOMMODATION)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> BoundaryQueueResponse:
    """Get boundary setup queue with progress and unset entities (D6)."""
    norm_status = "UNSET" if status == "PENDING" else status
    return await JobsService.get_boundary_queue(
        session=session,
        status=norm_status,
        entity_type=entity_type,
        limit=limit,
        offset=offset,
    )


@router.get("/boundaries/export")
async def export_boundaries(
    format: str = Query("csv", pattern="^(csv|json)$"),
    entity_type: str | None = Query(None, pattern="^(WORKSITE|ACCOMMODATION)$"),
    polygon_format: str = Query("WKT", pattern="^(WKT|GeoJSON)$"),
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
):
    """Export all worksite and accommodation boundaries as CSV or JSON."""
    items = await JobsService.export_boundaries(
        session=session,
        entity_type=entity_type,
        polygon_format=polygon_format,
    )
    if format == "json":
        return [item.model_dump() for item in items]

    # Generate CSV
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["entity_type", "code", "name", "has_boundary", "format", "polygon"])
    for it in items:
        writer.writerow(
            [
                it.entity_type,
                it.code,
                it.name,
                str(it.has_boundary).lower(),
                it.format,
                it.polygon or "",
            ]
        )

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=fwt_boundaries_export.csv"},
    )


@router.post("/boundaries/import", response_model=BoundaryImportResponse)
async def import_boundaries(
    payload: BoundaryImportRequest,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> BoundaryImportResponse:
    """Bulk import boundaries with row-level validation and skip reporting."""
    return await JobsService.import_boundaries(
        session=session,
        items=payload.items,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )


@router.put("/worksites/{worksite_id}/boundary", response_model=WorksiteDetailResponse)
async def update_worksite_boundary(
    worksite_id: UUID,
    payload: BoundaryUpdateRequest,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> WorksiteDetailResponse:
    """Set or update worksite polygon boundary."""
    return await JobsService.update_worksite_boundary(
        session=session,
        worksite_id=worksite_id,
        geojson_dict=payload.boundary,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )


@router.post("/worksites/{worksite_id}/copy-boundary", response_model=WorksiteDetailResponse)
async def copy_boundary_from(
    worksite_id: UUID,
    payload: BoundaryCopyRequest,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> WorksiteDetailResponse:
    """Copy boundary polygon from source worksite into this worksite."""
    return await JobsService.copy_boundary(
        session=session,
        target_worksite_id=worksite_id,
        source_worksite_id=payload.source_worksite_id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )


@router.post("/worksites/{worksite_id}/copy-boundary-to", response_model=list[WorksiteResponse])
async def copy_boundary_to_targets(
    worksite_id: UUID,
    payload: BoundaryCopyToRequest,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> list[WorksiteResponse]:
    """Copy this worksite's boundary to one or more target worksites."""
    return await JobsService.copy_boundary_to_multiple(
        session=session,
        source_worksite_id=worksite_id,
        target_worksite_ids=payload.target_worksite_ids,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )


@router.put("/accommodations/{accommodation_id}/boundary", status_code=status.HTTP_204_NO_CONTENT)
async def update_accommodation_boundary(
    accommodation_id: UUID,
    payload: BoundaryUpdateRequest,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Update accommodation camp boundary polygon."""
    await JobsService.update_accommodation_boundary(
        session=session,
        accommodation_id=accommodation_id,
        geojson_dict=payload.boundary,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )


# --- Job Items ---
@router.post(
    "/worksites/{worksite_id}/job-items",
    response_model=JobItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_job_item(
    worksite_id: UUID,
    payload: JobItemCreate,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> JobItemResponse:
    """Create a job item under a worksite. The response includes its planned man-hours."""
    item = await JobsService.create_job_item(
        session=session,
        worksite_id=worksite_id,
        payload=payload,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    return await _item_with_budget(session, item, current_user)


@router.patch("/job-items/{job_item_id}", response_model=JobItemResponse)
async def update_job_item(
    job_item_id: UUID,
    payload: JobItemUpdate,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> JobItemResponse:
    """Update a job item with optimistic locking. The response includes its planned man-hours."""
    item = await JobsService.update_job_item(
        session=session,
        job_item_id=job_item_id,
        payload=payload,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
    return await _item_with_budget(session, item, current_user)


@router.post(
    "/job-items/{job_item_id}/generate-occurrences", response_model=list[JobOccurrenceResponse]
)
async def generate_occurrences(
    job_item_id: UUID,
    payload: GenerateOccurrencesRequest = GenerateOccurrencesRequest(),
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> list[JobOccurrenceResponse]:
    """Trigger occurrence generation for a job item across rolling horizon."""
    return await JobsService.generate_job_occurrences(
        session=session,
        job_item_id=job_item_id,
        from_date=payload.from_date,
        to_date=payload.to_date,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )


@router.get("/job-items/{job_item_id}/deactivation-impact")
async def get_job_item_deactivation_impact(
    job_item_id: UUID,
    effective_date: date | None = Query(None),
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Preview scheduling impact of deactivating a single job item (Admin only)."""
    item = await session.get(JobItem, job_item_id)
    if not item:
        raise AppError(code="NOT_FOUND", message="Job item not found.", status_code=404)

    eff = effective_date or site_today()
    impact = await SchedulingService(session).get_job_items_deactivation_impact(
        job_item_ids=[item.id],
        effective_date=eff,
    )
    return {
        "job_item_id": str(item.id),
        "sub_item_code": item.sub_item_code,
        "staff_grade_description": item.staff_grade_description,
        "effective_date": eff.isoformat(),
        **impact,
    }


@router.post("/job-items/{job_item_id}/deactivate", response_model=EntityLifecycleResponse)
async def deactivate_job_item(
    job_item_id: UUID,
    payload: DeactivateRequest,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> EntityLifecycleResponse:
    """Admin-only job item deactivation with DEACTIVATE confirmation + admin password + schedule release."""
    if payload.confirmation_text.strip() != "DEACTIVATE":
        raise AppError(
            code="VALIDATION_ERROR",
            message='You must type "DEACTIVATE" exactly to confirm deactivation.',
            status_code=400,
        )
    if not payload.admin_password or not verify_password(
        payload.admin_password, current_user.credential_hash
    ):
        raise AppError(
            code="INVALID_PASSWORD",
            message="Admin password is incorrect. Deactivation aborted.",
            status_code=403,
        )
    if not payload.reason or not payload.reason.strip():
        raise AppError(
            code="REASON_REQUIRED",
            message="A reason for deactivation is required.",
            status_code=400,
        )

    item = await session.get(JobItem, job_item_id)
    if not item:
        raise AppError(code="NOT_FOUND", message="Job item not found.", status_code=404)
    if not item.is_active:
        raise AppError(
            code="INVALID_STATE", message="Job item is already deactivated.", status_code=400
        )

    eff = payload.effective_date or site_today()
    item.is_active = False
    item.version += 1

    cascade_summary, affected_workers = await SchedulingService(
        session
    ).cascade_job_items_deactivation(
        job_item_ids=[item.id],
        effective_date=eff,
        reason_label="JOB_ITEM_DEACTIVATED",
    )
    cascade_summary["freed_workers"] = len(affected_workers)

    await AuditService.log_action(
        session=session,
        action="DEACTIVATE_JOB_ITEM",
        entity_type="job_item",
        entity_id=str(item.id),
        diff={
            "sub_item_code": item.sub_item_code,
            "worksite_id": str(item.worksite_id),
            "effective_date": eff.isoformat(),
            **cascade_summary,
        },
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        reason=payload.reason.strip(),
    )
    await session.commit()

    return EntityLifecycleResponse(
        status="DEACTIVATED",
        entity_id=item.id,
        is_active=False,
        effective_date=eff,
        summary=cascade_summary,
        message=(
            f"Job item {item.sub_item_code} deactivated effective {eff.isoformat()}. "
            f"{cascade_summary['cancelled_future_shifts']} future shift(s) cancelled."
        ),
    )


@router.post("/job-items/{job_item_id}/reactivate", response_model=EntityLifecycleResponse)
async def reactivate_job_item(
    job_item_id: UUID,
    payload: ReactivateRequest,
    current_user: User = Depends(require_role("ADMIN")),
    session: AsyncSession = Depends(get_db),
) -> EntityLifecycleResponse:
    """Admin-only clean reactivation (Option A) of a job item (parent worksite must be active)."""
    if payload.confirmation_text.strip() != "REACTIVATE":
        raise AppError(
            code="VALIDATION_ERROR",
            message='You must type "REACTIVATE" exactly to confirm reactivation.',
            status_code=400,
        )
    if not payload.admin_password or not verify_password(
        payload.admin_password, current_user.credential_hash
    ):
        raise AppError(
            code="INVALID_PASSWORD",
            message="Admin password is incorrect. Reactivation aborted.",
            status_code=403,
        )
    if not payload.reason or not payload.reason.strip():
        raise AppError(
            code="REASON_REQUIRED",
            message="A reason for reactivation is required.",
            status_code=400,
        )

    item = await session.get(JobItem, job_item_id)
    if not item:
        raise AppError(code="NOT_FOUND", message="Job item not found.", status_code=404)
    if item.is_active:
        raise AppError(code="INVALID_STATE", message="Job item is already active.", status_code=400)

    parent_ws = await session.get(Worksite, item.worksite_id)
    if not parent_ws or not parent_ws.is_active:
        raise AppError(
            code="PARENT_INACTIVE",
            message="Reactivate the parent worksite before reactivating this job item.",
            status_code=400,
        )

    item.is_active = True
    item.version += 1

    await AuditService.log_action(
        session=session,
        action="REACTIVATE_JOB_ITEM",
        entity_type="job_item",
        entity_id=str(item.id),
        diff={"sub_item_code": item.sub_item_code, "schedules_restored": False},
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        reason=payload.reason.strip(),
    )
    await session.commit()

    return EntityLifecycleResponse(
        status="REACTIVATED",
        entity_id=item.id,
        is_active=True,
        summary={"schedules_restored": False},
        message=f"Job item {item.sub_item_code} reactivated cleanly. No old schedules were restored.",
    )


@router.get("/job-items/{job_item_id}/validation", response_model=JobItemValidationResponse)
async def get_job_item_validation(
    job_item_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> JobItemValidationResponse:
    """Get validation calculations for job item validation panel."""
    return await JobsService.get_job_item_validation(session=session, job_item_id=job_item_id)


# --- Occurrences ---
@router.get("/occurrences", response_model=list[JobOccurrenceResponse])
async def list_occurrences(
    job_item_id: UUID | None = None,
    worksite_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    status: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[JobOccurrenceResponse]:
    """List job occurrences with filtering."""
    return await JobsService.list_occurrences(
        session=session,
        job_item_id=job_item_id,
        worksite_id=worksite_id,
        from_date=from_date,
        to_date=to_date,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.patch("/occurrences/{occurrence_id}", response_model=JobOccurrenceResponse)
async def update_occurrence(
    occurrence_id: UUID,
    payload: JobOccurrenceUpdate,
    current_user: User = Depends(require_role("ADMIN", "ENGINEER")),
    session: AsyncSession = Depends(get_db),
) -> JobOccurrenceResponse:
    """Update occurrence due date or status."""
    return await JobsService.update_occurrence(
        session=session,
        occurrence_id=occurrence_id,
        payload=payload,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
    )
