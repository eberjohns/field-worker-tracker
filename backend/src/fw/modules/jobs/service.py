"""Business logic and database service for Worksites, Job Items, and Occurrences."""

import json
import re
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from geoalchemy2.functions import (
    ST_X,
    ST_Y,
    ST_Area,
    ST_GeomFromGeoJSON,
    ST_IsValid,
    ST_PointOnSurface,
    ST_SetSRID,
)
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from fw.core.errors import AppError
from fw.core.events import AccommodationBoundaryChanged, WorksiteBoundaryChanged, event_bus
from fw.modules.audit import AuditService
from fw.modules.jobs.models import JobItem, JobOccurrence, Worksite
from fw.modules.jobs.schemas import (
    BoundaryExportItem,
    BoundaryImportError,
    BoundaryImportItem,
    BoundaryImportResponse,
    BoundaryQueueItemResponse,
    BoundaryQueueResponse,
    JobItemCreate,
    JobItemResponse,
    JobItemUpdate,
    JobItemValidationResponse,
    JobOccurrenceResponse,
    JobOccurrenceUpdate,
    WorksiteCreate,
    WorksiteDetailResponse,
    WorksiteResponse,
    WorksiteUpdate,
)
from fw.modules.org import Accommodation, Employee, Group, Zone
from fw.modules.settings import SettingsService
from fw.rules.jobs import (
    calculate_days_per_occurrence,
    calculate_expected_activities_per_year,
    calculate_expected_annual_hours,
    generate_occurrence_slots,
    is_job_outdoor,
    split_job_unit_days,
    validate_job_number,
)

logger = structlog.get_logger(__name__)


class JobsService:
    @staticmethod
    async def list_worksites(
        session: AsyncSession,
        q: str | None = None,
        group_id: UUID | None = None,
        zone_id: UUID | None = None,
        country: str | None = None,
        has_boundary: bool | None = None,
        is_active: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[WorksiteResponse]:
        """List worksites matching search and filter criteria."""
        query = (
            select(
                Worksite,
                Group.name.label("group_name"),
                Zone.name.label("zone_name"),
            )
            .join(Group, Worksite.group_id == Group.id)
            .join(Zone, Worksite.zone_id == Zone.id)
        )

        if is_active is not None:
            query = query.where(Worksite.is_active == is_active)
        if group_id:
            query = query.where(Worksite.group_id == group_id)
        if zone_id:
            query = query.where(Worksite.zone_id == zone_id)
        if country:
            query = query.where(Worksite.country == country.upper())
        if has_boundary is True:
            query = query.where(Worksite.boundary.is_not(None))
        elif has_boundary is False:
            query = query.where(Worksite.boundary.is_(None))

        if q:
            term = f"%{q.strip()}%"
            query = query.where(
                or_(
                    Worksite.job_number.ilike(term),
                    Worksite.job_name.ilike(term),
                )
            )

        query = query.order_by(Worksite.job_number).offset(offset).limit(limit)
        result = await session.execute(query)
        rows = result.all()

        responses: list[WorksiteResponse] = []
        for ws, g_name, z_name in rows:
            responses.append(
                WorksiteResponse(
                    id=ws.id,
                    job_number=ws.job_number,
                    job_name=ws.job_name,
                    renewal_reference=ws.renewal_reference,
                    group_id=ws.group_id,
                    group_name=g_name,
                    zone_id=ws.zone_id,
                    zone_name=z_name,
                    customer_type=ws.customer_type,
                    is_outdoor=ws.is_outdoor,
                    country=ws.country,
                    contract_group_ref=ws.contract_group_ref,
                    start_date=ws.start_date,
                    end_date=ws.end_date,
                    has_boundary=ws.boundary is not None,
                    rep_latitude=ws.rep_latitude,
                    rep_longitude=ws.rep_longitude,
                    budget_amount=ws.budget_amount,
                    is_active=ws.is_active,
                    version=ws.version,
                    created_at=ws.created_at,
                    updated_at=ws.updated_at,
                )
            )
        return responses

    @staticmethod
    async def get_worksite(
        session: AsyncSession,
        worksite_id: UUID,
    ) -> WorksiteDetailResponse:
        """Fetch worksite detail with items, group/zone names, and GeoJSON boundary."""
        query = (
            select(
                Worksite,
                Group.name.label("group_name"),
                Zone.name.label("zone_name"),
                func.ST_AsGeoJSON(Worksite.boundary).label("geojson_str"),
            )
            .join(Group, Worksite.group_id == Group.id)
            .join(Zone, Worksite.zone_id == Zone.id)
            .where(Worksite.id == worksite_id)
            .options(selectinload(Worksite.items))
        )
        result = await session.execute(query)
        row = result.first()
        if not row:
            raise AppError("WORKSITE_NOT_FOUND", "Worksite not found", status_code=404)

        ws, g_name, z_name, geojson_str = row
        boundary_dict = json.loads(geojson_str) if geojson_str else None

        item_responses: list[JobItemResponse] = []
        for item in ws.items:
            exp_activities = calculate_expected_activities_per_year(
                item.frequency_unit, item.occurrences_per_period, item.period_interval
            )
            exp_hours = calculate_expected_annual_hours(
                exp_activities, item.required_staff_count, item.hours_per_occurrence_per_staff
            )
            days_count = calculate_days_per_occurrence(item.hours_per_occurrence_per_staff)
            day_splits = split_job_unit_days(item.hours_per_occurrence_per_staff)

            item_responses.append(
                JobItemResponse(
                    id=item.id,
                    worksite_id=item.worksite_id,
                    sub_item_code=item.sub_item_code,
                    staff_grade_description=item.staff_grade_description,
                    planned_grade_code=item.planned_grade_code,
                    frequency_unit=item.frequency_unit,
                    occurrences_per_period=item.occurrences_per_period,
                    period_interval=item.period_interval,
                    weekday_pattern=item.weekday_pattern,
                    required_staff_count=item.required_staff_count,
                    hours_per_occurrence_per_staff=item.hours_per_occurrence_per_staff,
                    declared_activities_per_year=item.declared_activities_per_year,
                    declared_total_hours_per_year=item.declared_total_hours_per_year,
                    start_date=item.start_date,
                    end_date=item.end_date,
                    deployment_type=item.deployment_type,
                    break_override_minutes=item.break_override_minutes,
                    is_active=item.is_active,
                    version=item.version,
                    expected_activities_per_year=exp_activities,
                    expected_annual_hours=exp_hours,
                    days_per_occurrence=days_count,
                    job_unit_day_split=day_splits,
                    created_at=item.created_at,
                )
            )

        return WorksiteDetailResponse(
            id=ws.id,
            job_number=ws.job_number,
            job_name=ws.job_name,
            renewal_reference=ws.renewal_reference,
            group_id=ws.group_id,
            group_name=g_name,
            zone_id=ws.zone_id,
            zone_name=z_name,
            customer_type=ws.customer_type,
            is_outdoor=ws.is_outdoor,
            country=ws.country,
            contract_group_ref=ws.contract_group_ref,
            start_date=ws.start_date,
            end_date=ws.end_date,
            has_boundary=ws.boundary is not None,
            rep_latitude=ws.rep_latitude,
            rep_longitude=ws.rep_longitude,
            budget_amount=ws.budget_amount,
            is_active=ws.is_active,
            version=ws.version,
            created_at=ws.created_at,
            updated_at=ws.updated_at,
            boundary_geojson=boundary_dict,
            items=item_responses,
            job_items=item_responses,
        )

    @staticmethod
    async def create_worksite(
        session: AsyncSession,
        payload: WorksiteCreate,
        actor_user_id: UUID | None = None,
        actor_role: str | None = None,
    ) -> WorksiteResponse:
        """Create a new worksite (BR-JB-01)."""
        valid_number = validate_job_number(payload.job_number)

        # Check uniqueness
        exists_stmt = select(Worksite.id).where(Worksite.job_number == valid_number)
        existing = await session.scalar(exists_stmt)
        if existing:
            raise AppError(
                "DUPLICATE_JOB_NUMBER",
                f"Worksite with job number {valid_number} already exists.",
                status_code=409,
            )

        # Verify group & zone exist
        group_exists = await session.scalar(select(Group.id).where(Group.id == payload.group_id))
        if not group_exists:
            raise AppError("GROUP_NOT_FOUND", "Referenced group does not exist.", status_code=400)
        zone_exists = await session.scalar(select(Zone.id).where(Zone.id == payload.zone_id))
        if not zone_exists:
            raise AppError("ZONE_NOT_FOUND", "Referenced zone does not exist.", status_code=400)

        # Inferred or explicit outdoor flag
        outdoor = is_job_outdoor(valid_number)

        ws = Worksite(
            job_number=valid_number,
            job_name=payload.job_name.strip(),
            renewal_reference=payload.renewal_reference.strip()
            if payload.renewal_reference
            else None,
            group_id=payload.group_id,
            zone_id=payload.zone_id,
            customer_type=payload.customer_type,
            is_outdoor=outdoor,
            country=payload.country.upper(),
            contract_group_ref=payload.contract_group_ref,
            start_date=payload.start_date,
            end_date=payload.end_date,
            budget_amount=payload.budget_amount,
        )
        session.add(ws)
        await session.flush()

        await AuditService.log_action(
            session=session,
            action="CREATE_WORKSITE",
            entity_type="worksite",
            entity_id=str(ws.id),
            diff={"job_number": ws.job_number, "job_name": ws.job_name, "country": ws.country},
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

        return await JobsService.get_worksite(session, ws.id)

    @staticmethod
    async def update_worksite(
        session: AsyncSession,
        worksite_id: UUID,
        payload: WorksiteUpdate,
        actor_user_id: UUID | None = None,
        actor_role: str | None = None,
    ) -> WorksiteResponse:
        """Update worksite metadata with optimistic locking."""
        ws = await session.get(Worksite, worksite_id)
        if not ws:
            raise AppError("WORKSITE_NOT_FOUND", "Worksite not found", status_code=404)

        if ws.version != payload.version:
            raise AppError(
                "VERSION_CONFLICT",
                "Worksite has been modified by another transaction.",
                status_code=409,
            )

        diff: dict[str, Any] = {}
        if payload.job_name is not None and payload.job_name.strip() != ws.job_name:
            diff["job_name"] = {"old": ws.job_name, "new": payload.job_name.strip()}
            ws.job_name = payload.job_name.strip()
        if payload.renewal_reference is not None:
            diff["renewal_reference"] = {
                "old": ws.renewal_reference,
                "new": payload.renewal_reference,
            }
            ws.renewal_reference = payload.renewal_reference
        if payload.customer_type is not None:
            diff["customer_type"] = {"old": ws.customer_type, "new": payload.customer_type}
            ws.customer_type = payload.customer_type
        if payload.contract_group_ref is not None:
            diff["contract_group_ref"] = {
                "old": ws.contract_group_ref,
                "new": payload.contract_group_ref,
            }
            ws.contract_group_ref = payload.contract_group_ref
        if payload.budget_amount is not None:
            diff["budget_amount"] = {
                "old": str(ws.budget_amount),
                "new": str(payload.budget_amount),
            }
            ws.budget_amount = payload.budget_amount
        if payload.start_date is not None:
            diff["start_date"] = {"old": str(ws.start_date), "new": str(payload.start_date)}
            ws.start_date = payload.start_date
        if payload.end_date is not None:
            diff["end_date"] = {"old": str(ws.end_date), "new": str(payload.end_date)}
            ws.end_date = payload.end_date
        if payload.is_active is not None and payload.is_active != ws.is_active:
            diff["is_active"] = {"old": ws.is_active, "new": payload.is_active}
            ws.is_active = payload.is_active

        ws.version += 1
        await session.flush()

        await AuditService.log_action(
            session=session,
            action="UPDATE_WORKSITE",
            entity_type="worksite",
            entity_id=str(ws.id),
            diff=diff,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

        return await JobsService.get_worksite(session, ws.id)

    @staticmethod
    def _extract_polygon_geojson(geojson_dict: dict[str, Any]) -> dict[str, Any]:
        """Extract Polygon geometry dict from Feature or raw Geometry."""
        geom_type = geojson_dict.get("type")
        if geom_type == "Feature":
            geometry = geojson_dict.get("geometry")
            if not isinstance(geometry, dict):
                raise AppError("INVALID_GEOJSON", "Feature has no geometry dict.", status_code=422)
            return geometry
        elif geom_type == "Polygon":
            return geojson_dict
        else:
            raise AppError(
                "INVALID_GEOMETRY_TYPE",
                f"Geometry type must be 'Polygon', got '{geom_type}'.",
                status_code=422,
            )

    @staticmethod
    def _parse_polygon_input(raw: Any) -> dict[str, Any]:
        """Parse raw polygon input from GeoJSON dict, GeoJSON string, or WKT string."""
        if isinstance(raw, dict):
            return JobsService._extract_polygon_geojson(raw)
        if isinstance(raw, str):
            s = raw.strip()
            if s.startswith("{"):
                parsed = json.loads(s)
                if isinstance(parsed, dict):
                    return JobsService._extract_polygon_geojson(parsed)
            # Try WKT
            match = re.search(r"POLYGON\s*\(\(\s*(.*?)\s*\)\)", s, re.IGNORECASE | re.DOTALL)
            if match:
                pts_str = match.group(1).split(",")
                ring = []
                for p in pts_str:
                    parts = p.strip().split()
                    if len(parts) >= 2:
                        ring.append([float(parts[0]), float(parts[1])])
                if len(ring) < 3:
                    raise ValueError("WKT polygon requires at least 3 points.")
                if ring[0] != ring[-1]:
                    ring.append(ring[0])
                return {"type": "Polygon", "coordinates": [ring]}
        raise ValueError("Unrecognized polygon format. Expected GeoJSON or WKT POLYGON((...)).")

    @staticmethod
    def _polygon_geojson_to_wkt(geojson_dict: dict[str, Any] | None) -> str | None:
        """Convert a GeoJSON Polygon geometry dict to WKT string."""
        if not geojson_dict:
            return None
        coords = geojson_dict.get("coordinates")
        if not coords or not isinstance(coords, list) or len(coords) == 0:
            return None
        ring = coords[0]
        pts = ", ".join(f"{pt[0]} {pt[1]}" for pt in ring)
        return f"POLYGON(({pts}))"

    @staticmethod
    async def update_worksite_boundary(
        session: AsyncSession,
        worksite_id: UUID,
        geojson_dict: dict[str, Any],
        actor_user_id: UUID | None = None,
        actor_role: str | None = None,
    ) -> WorksiteDetailResponse:
        """Set or update worksite polygon boundary with PostGIS validity checks."""
        ws = await session.get(Worksite, worksite_id)
        if not ws:
            raise AppError("WORKSITE_NOT_FOUND", "Worksite not found", status_code=404)

        polygon_geom = JobsService._extract_polygon_geojson(geojson_dict)
        coords = polygon_geom.get("coordinates")
        if not coords or not isinstance(coords, list) or len(coords) == 0:
            raise AppError(
                "EMPTY_COORDINATES", "Polygon coordinates cannot be empty.", status_code=422
            )

        exterior_ring = coords[0]
        if len(exterior_ring) < 4:
            raise AppError(
                "INVALID_RING",
                "A polygon ring must have at least 4 positions (closed ring).",
                status_code=422,
            )
        if exterior_ring[0] != exterior_ring[-1]:
            raise AppError(
                "OPEN_RING",
                "First and last positions of polygon ring must be identical.",
                status_code=422,
            )

        json_str = json.dumps(polygon_geom)
        geom_expr = ST_SetSRID(ST_GeomFromGeoJSON(json_str), 4326)

        # Validate geometry validity and non-zero area using PostGIS
        val_stmt = select(
            ST_IsValid(geom_expr).label("is_valid"),
            ST_Area(geom_expr).label("area"),
            ST_X(ST_PointOnSurface(geom_expr)).label("rep_x"),
            ST_Y(ST_PointOnSurface(geom_expr)).label("rep_y"),
        )
        val_res = await session.execute(val_stmt)
        val_row = val_res.first()
        if not val_row or not val_row.is_valid:
            raise AppError(
                "INVALID_POLYGON",
                "The boundary polygon is invalid or has self-intersecting lines.",
                status_code=422,
            )
        if val_row.area <= 0:
            raise AppError(
                "ZERO_AREA_POLYGON",
                "The boundary polygon must enclose a positive area.",
                status_code=422,
            )

        ws.boundary = geom_expr
        rep_lng_val = float(val_row.rep_x)
        rep_lat_val = float(val_row.rep_y)
        ws.rep_longitude = Decimal(str(round(val_row.rep_x, 6)))
        ws.rep_latitude = Decimal(str(round(val_row.rep_y, 6)))
        ws.version += 1
        await session.flush()

        logger.info(
            "site_boundary_updated",
            worksite_id=str(ws.id),
            job_number=ws.job_number,
            message="Site boundary updated; SITE_BOUNDARY sync changes will be emitted in Phase 07.",
        )

        await AuditService.log_action(
            session=session,
            action="UPDATE_BOUNDARY",
            entity_type="worksite",
            entity_id=str(ws.id),
            diff={
                "boundary_updated": True,
                "rep_lat": rep_lat_val,
                "rep_lng": rep_lng_val,
            },
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

        await event_bus.publish(WorksiteBoundaryChanged(worksite_id=ws.id), session=session)

        return await JobsService.get_worksite(session, ws.id)

    @staticmethod
    async def copy_boundary(
        session: AsyncSession,
        target_worksite_id: UUID,
        source_worksite_id: UUID,
        actor_user_id: UUID | None = None,
        actor_role: str | None = None,
    ) -> WorksiteDetailResponse:
        """Copy boundary polygon from source worksite to target worksite."""
        source_ws = await session.get(Worksite, source_worksite_id)
        if not source_ws or source_ws.boundary is None:
            raise AppError(
                "SOURCE_BOUNDARY_MISSING",
                "Source worksite has no boundary to copy.",
                status_code=400,
            )

        target_ws = await session.get(Worksite, target_worksite_id)
        if not target_ws:
            raise AppError(
                "TARGET_WORKSITE_NOT_FOUND", "Target worksite not found.", status_code=404
            )

        target_ws.boundary = source_ws.boundary
        target_ws.rep_latitude = source_ws.rep_latitude
        target_ws.rep_longitude = source_ws.rep_longitude
        target_ws.version += 1
        await session.flush()

        await AuditService.log_action(
            session=session,
            action="COPY_BOUNDARY",
            entity_type="worksite",
            entity_id=str(target_ws.id),
            diff={
                "copied_from_source_id": str(source_ws.id),
                "source_job_number": source_ws.job_number,
            },
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

        await event_bus.publish(WorksiteBoundaryChanged(worksite_id=target_ws.id), session=session)

        return await JobsService.get_worksite(session, target_ws.id)

    @staticmethod
    async def copy_boundary_to_multiple(
        session: AsyncSession,
        source_worksite_id: UUID,
        target_worksite_ids: list[UUID],
        actor_user_id: UUID | None = None,
        actor_role: str | None = None,
    ) -> list[WorksiteResponse]:
        """Copy boundary from source worksite to multiple target worksites."""
        source_ws = await session.get(Worksite, source_worksite_id)
        if not source_ws or source_ws.boundary is None:
            raise AppError(
                "SOURCE_BOUNDARY_MISSING",
                "Source worksite has no boundary to copy.",
                status_code=400,
            )

        updated: list[WorksiteResponse] = []
        for tid in target_worksite_ids:
            tws = await session.get(Worksite, tid)
            if tws:
                tws.boundary = source_ws.boundary
                tws.rep_latitude = source_ws.rep_latitude
                tws.rep_longitude = source_ws.rep_longitude
                tws.version += 1
                await session.flush()

                await AuditService.log_action(
                    session=session,
                    action="COPY_BOUNDARY",
                    entity_type="worksite",
                    entity_id=str(tws.id),
                    diff={"copied_from_source_id": str(source_ws.id)},
                    actor_user_id=actor_user_id,
                    actor_role=actor_role,
                )
                await event_bus.publish(
                    WorksiteBoundaryChanged(worksite_id=tws.id), session=session
                )
                res = await JobsService.get_worksite(session, tws.id)
                updated.append(res)

        return updated

    @staticmethod
    async def update_accommodation_boundary(
        session: AsyncSession,
        accommodation_id: UUID,
        geojson_dict: dict[str, Any],
        actor_user_id: UUID | None = None,
        actor_role: str | None = None,
    ) -> None:
        """Update boundary for an accommodation camp."""
        acc = await session.get(Accommodation, accommodation_id)
        if not acc:
            raise AppError("ACCOMMODATION_NOT_FOUND", "Accommodation not found.", status_code=404)

        polygon_geom = JobsService._extract_polygon_geojson(geojson_dict)
        json_str = json.dumps(polygon_geom)
        geom_expr = ST_SetSRID(ST_GeomFromGeoJSON(json_str), 4326)

        val_stmt = select(
            ST_IsValid(geom_expr).label("is_valid"),
            ST_Area(geom_expr).label("area"),
            ST_X(ST_PointOnSurface(geom_expr)).label("rep_x"),
            ST_Y(ST_PointOnSurface(geom_expr)).label("rep_y"),
        )
        val_res = await session.execute(val_stmt)
        val_row = val_res.first()
        if not val_row or not val_row.is_valid or val_row.area <= 0:
            raise AppError("INVALID_POLYGON", "Invalid accommodation polygon.", status_code=422)

        acc.boundary = geom_expr
        acc_lng_val = float(val_row.rep_x)
        acc_lat_val = float(val_row.rep_y)
        acc.rep_longitude = Decimal(str(round(val_row.rep_x, 6)))
        acc.rep_latitude = Decimal(str(round(val_row.rep_y, 6)))
        acc.version += 1
        await session.flush()

        await AuditService.log_action(
            session=session,
            action="UPDATE_ACCOMMODATION_BOUNDARY",
            entity_type="accommodation",
            entity_id=str(acc.id),
            diff={
                "rep_lat": acc_lat_val,
                "rep_lng": acc_lng_val,
            },
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

        await event_bus.publish(
            AccommodationBoundaryChanged(accommodation_id=acc.id), session=session
        )

    @staticmethod
    async def get_boundary_queue(
        session: AsyncSession,
        status: str = "ALL",
        entity_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> BoundaryQueueResponse:
        """Retrieve progress stats and queue items for worksites & accommodations (D6)."""
        # Worksites counts
        ws_total = await session.scalar(select(func.count(Worksite.id))) or 0
        ws_done = (
            await session.scalar(
                select(func.count(Worksite.id)).where(Worksite.boundary.is_not(None))
            )
            or 0
        )
        ws_unset = ws_total - ws_done

        # Accommodations counts
        acc_total = await session.scalar(select(func.count(Accommodation.id))) or 0
        acc_done = (
            await session.scalar(
                select(func.count(Accommodation.id)).where(Accommodation.boundary.is_not(None))
            )
            or 0
        )
        acc_unset = acc_total - acc_done

        total_count = ws_total + acc_total
        done_count = ws_done + acc_done
        unset_count = total_count - done_count

        items: list[BoundaryQueueItemResponse] = []

        # Worksites
        if not entity_type or entity_type == "WORKSITE":
            ws_query = (
                select(
                    Worksite,
                    Zone.name.label("zone_name"),
                    func.ST_AsGeoJSON(Worksite.boundary).label("geojson"),
                )
                .join(Zone, Worksite.zone_id == Zone.id)
                .where(Worksite.is_active.is_(True))
            )
            if status == "UNSET":
                ws_query = ws_query.where(Worksite.boundary.is_(None))
            elif status == "SET":
                ws_query = ws_query.where(Worksite.boundary.is_not(None))

            ws_query = ws_query.order_by(Worksite.job_number).offset(offset).limit(limit)
            ws_rows = (await session.execute(ws_query)).all()
            for ws, z_name, geojson_str in ws_rows:
                items.append(
                    BoundaryQueueItemResponse(
                        id=ws.id,
                        entity_type="WORKSITE",
                        code=ws.job_number,
                        name=ws.job_name,
                        zone_name=z_name,
                        country=ws.country,
                        has_boundary=ws.boundary is not None,
                        rep_latitude=ws.rep_latitude,
                        rep_longitude=ws.rep_longitude,
                        boundary_geojson=json.loads(geojson_str) if geojson_str else None,
                    )
                )

        # Accommodations
        if not entity_type or entity_type == "ACCOMMODATION":
            remaining_limit = limit - len(items) if not entity_type else limit
            if remaining_limit > 0:
                acc_query = select(
                    Accommodation,
                    func.ST_AsGeoJSON(Accommodation.boundary).label("geojson"),
                ).where(Accommodation.is_active.is_(True))

                if status == "UNSET":
                    acc_query = acc_query.where(Accommodation.boundary.is_(None))
                elif status == "SET":
                    acc_query = acc_query.where(Accommodation.boundary.is_not(None))

                acc_query = acc_query.order_by(Accommodation.accommodation_code).limit(
                    remaining_limit
                )
                acc_rows = (await session.execute(acc_query)).all()
                for acc, geojson_str in acc_rows:
                    items.append(
                        BoundaryQueueItemResponse(
                            id=acc.id,
                            entity_type="ACCOMMODATION",
                            code=acc.accommodation_code,
                            name=acc.name,
                            zone_name=acc.address,
                            country="AE",
                            has_boundary=acc.boundary is not None,
                            rep_latitude=acc.rep_latitude,
                            rep_longitude=acc.rep_longitude,
                            boundary_geojson=json.loads(geojson_str) if geojson_str else None,
                        )
                    )

        return BoundaryQueueResponse(
            total_count=total_count,
            done_count=done_count,
            unset_count=unset_count,
            worksites_total_count=ws_total,
            worksites_done_count=ws_done,
            worksites_unset_count=ws_unset,
            accommodations_total_count=acc_total,
            accommodations_done_count=acc_done,
            accommodations_unset_count=acc_unset,
            items=items,
        )

    @staticmethod
    async def export_boundaries(
        session: AsyncSession,
        entity_type: str | None = None,
        polygon_format: str = "WKT",
    ) -> list[BoundaryExportItem]:
        """Export boundaries for worksites and accommodations."""
        items: list[BoundaryExportItem] = []
        norm_type = (entity_type or "").upper() if entity_type else None

        if not norm_type or norm_type == "WORKSITE":
            ws_stmt = (
                select(
                    Worksite.job_number,
                    Worksite.job_name,
                    func.ST_AsGeoJSON(Worksite.boundary).label("geojson"),
                )
                .where(Worksite.is_active.is_(True))
                .order_by(Worksite.job_number)
            )
            ws_rows = (await session.execute(ws_stmt)).all()
            for job_num, job_name, geojson_str in ws_rows:
                geojson_dict = json.loads(geojson_str) if geojson_str else None
                poly_repr = (
                    JobsService._polygon_geojson_to_wkt(geojson_dict)
                    if polygon_format == "WKT"
                    else geojson_str
                )
                items.append(
                    BoundaryExportItem(
                        entity_type="WORKSITE",
                        code=job_num,
                        name=job_name,
                        has_boundary=geojson_dict is not None,
                        format=polygon_format if geojson_dict else "NONE",
                        polygon=poly_repr,
                    )
                )

        if not norm_type or norm_type == "ACCOMMODATION":
            acc_stmt = (
                select(
                    Accommodation.accommodation_code,
                    Accommodation.name,
                    func.ST_AsGeoJSON(Accommodation.boundary).label("geojson"),
                )
                .where(Accommodation.is_active.is_(True))
                .order_by(Accommodation.accommodation_code)
            )
            acc_rows = (await session.execute(acc_stmt)).all()
            for code, name, geojson_str in acc_rows:
                geojson_dict = json.loads(geojson_str) if geojson_str else None
                poly_repr = (
                    JobsService._polygon_geojson_to_wkt(geojson_dict)
                    if polygon_format == "WKT"
                    else geojson_str
                )
                items.append(
                    BoundaryExportItem(
                        entity_type="ACCOMMODATION",
                        code=code,
                        name=name,
                        has_boundary=geojson_dict is not None,
                        format=polygon_format if geojson_dict else "NONE",
                        polygon=poly_repr,
                    )
                )

        return items

    @staticmethod
    async def import_boundaries(
        session: AsyncSession,
        items: list[BoundaryImportItem],
        actor_user_id: UUID | None = None,
        actor_role: str | None = None,
    ) -> BoundaryImportResponse:
        """Bulk import boundaries with graceful row-level error reporting."""
        updated_count = 0
        skipped_count = 0
        errors: list[BoundaryImportError] = []

        for idx, item in enumerate(items, start=1):
            entity_type = (item.entity_type or "").upper().strip()
            code = (item.code or "").strip()

            if not code:
                errors.append(
                    BoundaryImportError(
                        row=idx,
                        code=code,
                        entity_type=entity_type,
                        reason="Missing primary key code.",
                    )
                )
                skipped_count += 1
                continue

            try:
                geojson_dict = JobsService._parse_polygon_input(item.polygon)
            except Exception as e:
                errors.append(
                    BoundaryImportError(
                        row=idx,
                        code=code,
                        entity_type=entity_type,
                        reason=f"Invalid polygon geometry: {str(e)}",
                    )
                )
                skipped_count += 1
                continue

            if entity_type == "WORKSITE":
                ws_stmt = select(Worksite).where(Worksite.job_number == code)
                ws = (await session.execute(ws_stmt)).scalar_one_or_none()
                if not ws:
                    errors.append(
                        BoundaryImportError(
                            row=idx,
                            code=code,
                            entity_type="WORKSITE",
                            reason=f"Worksite job number '{code}' not found in system.",
                        )
                    )
                    skipped_count += 1
                    continue

                try:
                    await JobsService.update_worksite_boundary(
                        session=session,
                        worksite_id=ws.id,
                        geojson_dict=geojson_dict,
                        actor_user_id=actor_user_id,
                        actor_role=actor_role,
                    )
                    updated_count += 1
                except Exception as e:
                    errors.append(
                        BoundaryImportError(
                            row=idx,
                            code=code,
                            entity_type="WORKSITE",
                            reason=f"Validation failed: {str(e)}",
                        )
                    )
                    skipped_count += 1

            elif entity_type == "ACCOMMODATION":
                acc_stmt = select(Accommodation).where(Accommodation.accommodation_code == code)
                acc = (await session.execute(acc_stmt)).scalar_one_or_none()
                if not acc:
                    errors.append(
                        BoundaryImportError(
                            row=idx,
                            code=code,
                            entity_type="ACCOMMODATION",
                            reason=f"Accommodation code '{code}' not found in system.",
                        )
                    )
                    skipped_count += 1
                    continue

                try:
                    await JobsService.update_accommodation_boundary(
                        session=session,
                        accommodation_id=acc.id,
                        geojson_dict=geojson_dict,
                        actor_user_id=actor_user_id,
                        actor_role=actor_role,
                    )
                    updated_count += 1
                except Exception as e:
                    errors.append(
                        BoundaryImportError(
                            row=idx,
                            code=code,
                            entity_type="ACCOMMODATION",
                            reason=f"Validation failed: {str(e)}",
                        )
                    )
                    skipped_count += 1
            else:
                errors.append(
                    BoundaryImportError(
                        row=idx,
                        code=code,
                        entity_type=entity_type,
                        reason=f"Invalid entity_type '{entity_type}'. Must be WORKSITE or ACCOMMODATION.",
                    )
                )
                skipped_count += 1

        return BoundaryImportResponse(
            total_rows=len(items),
            updated_count=updated_count,
            skipped_count=skipped_count,
            errors=errors,
        )

    @staticmethod
    async def create_job_item(
        session: AsyncSession,
        worksite_id: UUID,
        payload: JobItemCreate,
        actor_user_id: UUID | None = None,
        actor_role: str | None = None,
    ) -> JobItemResponse:
        """Create a new job item and trigger automatic occurrence generation."""
        ws = await session.get(Worksite, worksite_id)
        if not ws:
            raise AppError("WORKSITE_NOT_FOUND", "Worksite not found.", status_code=404)

        # Unique constraint per worksite
        sub_code = payload.sub_item_code.strip()
        existing = await session.scalar(
            select(JobItem.id).where(
                JobItem.worksite_id == worksite_id,
                JobItem.sub_item_code == sub_code,
            )
        )
        if existing:
            raise AppError(
                "DUPLICATE_SUB_ITEM",
                f"Job item '{sub_code}' already exists for worksite {ws.job_number}.",
                status_code=409,
            )

        item = JobItem(
            worksite_id=worksite_id,
            sub_item_code=sub_code,
            staff_grade_description=payload.staff_grade_description.strip(),
            planned_grade_code=payload.planned_grade_code.strip(),
            frequency_unit=payload.frequency_unit.strip().upper(),
            occurrences_per_period=payload.occurrences_per_period,
            period_interval=payload.period_interval,
            weekday_pattern=payload.weekday_pattern,
            required_staff_count=payload.required_staff_count,
            hours_per_occurrence_per_staff=payload.hours_per_occurrence_per_staff,
            declared_activities_per_year=payload.declared_activities_per_year,
            declared_total_hours_per_year=payload.declared_total_hours_per_year,
            start_date=payload.start_date,
            end_date=payload.end_date,
            deployment_type=payload.deployment_type.strip().upper(),
            break_override_minutes=payload.break_override_minutes,
        )
        session.add(item)
        await session.flush()

        # Automatic rolling horizon occurrence generation
        await JobsService.generate_job_occurrences(
            session=session,
            job_item_id=item.id,
            from_date=item.start_date,
            to_date=None,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

        await AuditService.log_action(
            session=session,
            action="CREATE_JOB_ITEM",
            entity_type="job_item",
            entity_id=str(item.id),
            diff={"worksite_id": str(worksite_id), "sub_item_code": item.sub_item_code},
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

        exp_act = calculate_expected_activities_per_year(
            item.frequency_unit, item.occurrences_per_period, item.period_interval
        )
        exp_hrs = calculate_expected_annual_hours(
            exp_act, item.required_staff_count, item.hours_per_occurrence_per_staff
        )

        return JobItemResponse(
            id=item.id,
            worksite_id=item.worksite_id,
            sub_item_code=item.sub_item_code,
            staff_grade_description=item.staff_grade_description,
            planned_grade_code=item.planned_grade_code,
            frequency_unit=item.frequency_unit,
            occurrences_per_period=item.occurrences_per_period,
            period_interval=item.period_interval,
            weekday_pattern=item.weekday_pattern,
            required_staff_count=item.required_staff_count,
            hours_per_occurrence_per_staff=item.hours_per_occurrence_per_staff,
            declared_activities_per_year=item.declared_activities_per_year,
            declared_total_hours_per_year=item.declared_total_hours_per_year,
            start_date=item.start_date,
            end_date=item.end_date,
            deployment_type=item.deployment_type,
            break_override_minutes=item.break_override_minutes,
            is_active=item.is_active,
            version=item.version,
            expected_activities_per_year=exp_act,
            expected_annual_hours=exp_hrs,
            days_per_occurrence=calculate_days_per_occurrence(item.hours_per_occurrence_per_staff),
            job_unit_day_split=split_job_unit_days(item.hours_per_occurrence_per_staff),
            created_at=item.created_at,
        )

    @staticmethod
    async def update_job_item(
        session: AsyncSession,
        job_item_id: UUID,
        payload: JobItemUpdate,
        actor_user_id: UUID | None = None,
        actor_role: str | None = None,
    ) -> JobItemResponse:
        """Update job item with optimistic locking and occurrence regeneration."""
        item = await session.get(JobItem, job_item_id)
        if not item:
            raise AppError("JOB_ITEM_NOT_FOUND", "Job item not found.", status_code=404)

        if item.version != payload.version:
            raise AppError(
                "VERSION_CONFLICT", "Job item was modified concurrently.", status_code=409
            )

        diff: dict[str, Any] = {}
        regen_needed = False

        if payload.sub_item_code is not None:
            diff["sub_item_code"] = payload.sub_item_code
            item.sub_item_code = payload.sub_item_code.strip()
        if payload.deployment_type is not None:
            diff["deployment_type"] = payload.deployment_type
            item.deployment_type = payload.deployment_type.strip()
        if payload.staff_grade_description is not None:
            diff["staff_grade_description"] = payload.staff_grade_description
            item.staff_grade_description = payload.staff_grade_description.strip()
            regen_needed = True
        if payload.planned_grade_code is not None:
            diff["planned_grade_code"] = payload.planned_grade_code
            item.planned_grade_code = payload.planned_grade_code.strip()
        if payload.frequency_unit is not None:
            diff["frequency_unit"] = payload.frequency_unit
            item.frequency_unit = payload.frequency_unit.strip().upper()
            regen_needed = True
        if payload.occurrences_per_period is not None:
            diff["occurrences_per_period"] = str(payload.occurrences_per_period)
            item.occurrences_per_period = payload.occurrences_per_period
            regen_needed = True
        if payload.period_interval is not None:
            diff["period_interval"] = payload.period_interval
            item.period_interval = payload.period_interval
            regen_needed = True
        if payload.weekday_pattern is not None:
            diff["weekday_pattern"] = payload.weekday_pattern
            item.weekday_pattern = payload.weekday_pattern
            regen_needed = True
        if payload.required_staff_count is not None:
            diff["required_staff_count"] = payload.required_staff_count
            item.required_staff_count = payload.required_staff_count
            regen_needed = True
        if payload.hours_per_occurrence_per_staff is not None:
            diff["hours_per_occurrence_per_staff"] = str(payload.hours_per_occurrence_per_staff)
            item.hours_per_occurrence_per_staff = payload.hours_per_occurrence_per_staff
            regen_needed = True
        if payload.break_override_minutes is not None:
            diff["break_override_minutes"] = payload.break_override_minutes
            item.break_override_minutes = payload.break_override_minutes
        if payload.is_active is not None:
            diff["is_active"] = payload.is_active
            item.is_active = payload.is_active

        item.version += 1
        await session.flush()

        if regen_needed:
            await JobsService.generate_job_occurrences(
                session=session,
                job_item_id=item.id,
                from_date=datetime.now(UTC).date(),
                to_date=None,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
            )

        await AuditService.log_action(
            session=session,
            action="UPDATE_JOB_ITEM",
            entity_type="job_item",
            entity_id=str(item.id),
            diff=diff,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

        exp_act = calculate_expected_activities_per_year(
            item.frequency_unit, item.occurrences_per_period, item.period_interval
        )
        exp_hrs = calculate_expected_annual_hours(
            exp_act, item.required_staff_count, item.hours_per_occurrence_per_staff
        )

        return JobItemResponse(
            id=item.id,
            worksite_id=item.worksite_id,
            sub_item_code=item.sub_item_code,
            staff_grade_description=item.staff_grade_description,
            planned_grade_code=item.planned_grade_code,
            frequency_unit=item.frequency_unit,
            occurrences_per_period=item.occurrences_per_period,
            period_interval=item.period_interval,
            weekday_pattern=item.weekday_pattern,
            required_staff_count=item.required_staff_count,
            hours_per_occurrence_per_staff=item.hours_per_occurrence_per_staff,
            declared_activities_per_year=item.declared_activities_per_year,
            declared_total_hours_per_year=item.declared_total_hours_per_year,
            start_date=item.start_date,
            end_date=item.end_date,
            deployment_type=item.deployment_type,
            break_override_minutes=item.break_override_minutes,
            is_active=item.is_active,
            version=item.version,
            expected_activities_per_year=exp_act,
            expected_annual_hours=exp_hrs,
            days_per_occurrence=calculate_days_per_occurrence(item.hours_per_occurrence_per_staff),
            job_unit_day_split=split_job_unit_days(item.hours_per_occurrence_per_staff),
            created_at=item.created_at,
        )

    @staticmethod
    async def generate_job_occurrences(
        session: AsyncSession,
        job_item_id: UUID,
        from_date: date | None = None,
        to_date: date | None = None,
        actor_user_id: UUID | None = None,
        actor_role: str | None = None,
    ) -> list[JobOccurrenceResponse]:
        """Generate occurrences across rolling horizon idempotently (BR-JB-07, docs/04 Section 3)."""
        item = await session.get(JobItem, job_item_id)
        if not item:
            raise AppError("JOB_ITEM_NOT_FOUND", "Job item not found.", status_code=404)

        # Budget-only staff types check
        budget_types = await SettingsService.get_setting(
            session=session,
            key="budget_only_staff_types",
            default=None,
        )
        if budget_types is None:
            budget_types = ["HSE Engineer", "Project Manager", "Irrigation Engineer"]
        elif not isinstance(budget_types, list):
            if isinstance(budget_types, str) and budget_types:
                budget_types = [x.strip() for x in budget_types.split(",") if x.strip()]
            else:
                budget_types = []

        # Horizon parameters
        horizon_months = await SettingsService.get_setting(
            session=session,
            key="occurrence_horizon_months",
            default=13,
        )
        if not isinstance(horizon_months, int):
            horizon_months = 13

        today = datetime.now(UTC).date()
        start = from_date or max(today, item.start_date)
        end = to_date or (start + timedelta(days=horizon_months * 31))
        if item.end_date:
            end = min(end, item.end_date)

        slots = generate_occurrence_slots(
            frequency_unit=item.frequency_unit,
            occurrences_per_period=item.occurrences_per_period,
            period_interval=item.period_interval,
            required_staff_count=item.required_staff_count,
            hours_per_occurrence_per_staff=item.hours_per_occurrence_per_staff,
            horizon_start=start,
            horizon_end=end,
            item_start_date=item.start_date,
            item_end_date=item.end_date,
            weekday_pattern=item.weekday_pattern,
            staff_grade_description=item.staff_grade_description,
            budget_only_types=budget_types,
        )

        # Existing occurrences for this item
        existing_stmt = select(JobOccurrence).where(
            JobOccurrence.job_item_id == job_item_id,
        )
        existing_rows = (await session.execute(existing_stmt)).scalars().all()
        existing_map = {(row.window_start, row.slot_index): row for row in existing_rows}

        # Clean up unassigned generated occurrences that are no longer in the generated schedule
        generated_keys = {(slot.window_start, slot.slot_index) for slot in slots}
        if slots:
            min_win = min(s.window_start for s in slots)
            max_win = max(s.window_end for s in slots)
            for row in existing_rows:
                if row.window_start >= min_win and row.window_end <= max_win:
                    if (
                        row.window_start,
                        row.slot_index,
                    ) not in generated_keys and row.status == "GENERATED":
                        await session.delete(row)
                        existing_map.pop((row.window_start, row.slot_index), None)

        results: list[JobOccurrence] = []
        for slot in slots:
            key = (slot.window_start, slot.slot_index)
            if key in existing_map:
                existing = existing_map[key]
                # If assigned or completed: keep, but flag needs_review if hours/staff changed
                if existing.status in ("ASSIGNED", "COMPLETED"):
                    if (
                        existing.required_staff_count != slot.required_staff_count
                        or existing.required_hours_per_staff != slot.required_hours_per_staff
                    ):
                        existing.needs_review = True
                    results.append(existing)
                else:
                    # Update snapshots
                    existing.due_date = slot.due_date
                    existing.required_staff_count = slot.required_staff_count
                    existing.required_hours_per_staff = slot.required_hours_per_staff
                    results.append(existing)
            else:
                occ = JobOccurrence(
                    job_item_id=job_item_id,
                    window_start=slot.window_start,
                    window_end=slot.window_end,
                    slot_index=slot.slot_index,
                    due_date=slot.due_date or slot.suggested_date,
                    status="GENERATED",
                    source="GENERATED",
                    required_staff_count=slot.required_staff_count,
                    required_hours_per_staff=slot.required_hours_per_staff,
                    needs_review=False,
                )
                session.add(occ)
                results.append(occ)

        await session.flush()
        return [
            JobOccurrenceResponse(
                id=r.id,
                job_item_id=r.job_item_id,
                sub_item_code=item.sub_item_code,
                staff_grade_description=item.staff_grade_description,
                planned_grade_code=item.planned_grade_code,
                window_start=r.window_start,
                window_end=r.window_end,
                slot_index=r.slot_index,
                due_date=r.due_date,
                status=r.status,
                source=r.source,
                required_staff_count=r.required_staff_count,
                required_hours_per_staff=r.required_hours_per_staff,
                needs_review=r.needs_review,
                created_at=r.created_at,
            )
            for r in results
        ]

    @staticmethod
    async def get_job_item_validation(
        session: AsyncSession,
        job_item_id: UUID,
    ) -> JobItemValidationResponse:
        """Calculate validation statistics for job item validation panel (BR-JB-06, BR-JB-12)."""
        item = await session.get(JobItem, job_item_id)
        if not item:
            raise AppError("JOB_ITEM_NOT_FOUND", "Job item not found.", status_code=404)

        calc_activities = calculate_expected_activities_per_year(
            item.frequency_unit, item.occurrences_per_period, item.period_interval
        )
        calc_annual_hours = calculate_expected_annual_hours(
            calc_activities, item.required_staff_count, item.hours_per_occurrence_per_staff
        )
        days_per_occ = calculate_days_per_occurrence(item.hours_per_occurrence_per_staff)
        daily_splits = split_job_unit_days(item.hours_per_occurrence_per_staff)

        # Count occurrences in next 12 months
        occ_count = (
            await session.scalar(
                select(func.count(JobOccurrence.id)).where(JobOccurrence.job_item_id == job_item_id)
            )
            or 0
        )

        # Count eligible workers with matching SGD or Grade Group
        # Look up worksite country
        ws = await session.get(Worksite, item.worksite_id)
        ws_country = ws.country if ws else "AE"

        emp_count_stmt = select(func.count(Employee.id)).where(
            Employee.is_active.is_(True),
            Employee.country == ws_country,
            Employee.staff_grade_description.ilike(item.staff_grade_description),
        )
        eligible_count = await session.scalar(emp_count_stmt) or 0

        note: str | None = None
        if (
            item.declared_activities_per_year
            and item.declared_activities_per_year != calc_activities
        ):
            note = (
                f"Declared activities ({item.declared_activities_per_year}) differs from calculated "
                f"({calc_activities}). Calculated value is used by the system."
            )

        return JobItemValidationResponse(
            job_item_id=item.id,
            sub_item_code=item.sub_item_code,
            staff_grade_description=item.staff_grade_description,
            declared_activities_per_year=item.declared_activities_per_year,
            calculated_activities_per_year=calc_activities,
            declared_total_hours_per_year=item.declared_total_hours_per_year,
            calculated_annual_hours=calc_annual_hours,
            expected_occurrences_count=occ_count,
            days_per_occurrence=days_per_occ,
            daily_hours_split=daily_splits,
            eligible_workers_count=eligible_count,
            difference_note=note,
        )

    @staticmethod
    async def list_occurrences(
        session: AsyncSession,
        job_item_id: UUID | None = None,
        worksite_id: UUID | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        status: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[JobOccurrenceResponse]:
        """List occurrences with filtering and joined item descriptors."""
        query = (
            select(JobOccurrence)
            .options(joinedload(JobOccurrence.job_item))
            .join(JobItem, JobOccurrence.job_item_id == JobItem.id)
        )

        if job_item_id:
            query = query.where(JobOccurrence.job_item_id == job_item_id)
        if worksite_id:
            query = query.where(JobItem.worksite_id == worksite_id)
        if from_date:
            query = query.where(JobOccurrence.window_start >= from_date)
        if to_date:
            query = query.where(JobOccurrence.window_end <= to_date)
        if status:
            query = query.where(JobOccurrence.status == status.upper())

        query = (
            query.order_by(JobOccurrence.window_start, JobOccurrence.slot_index)
            .offset(offset)
            .limit(limit)
        )
        rows = (await session.execute(query)).scalars().all()
        return [
            JobOccurrenceResponse(
                id=r.id,
                job_item_id=r.job_item_id,
                sub_item_code=r.job_item.sub_item_code if r.job_item else None,
                staff_grade_description=r.job_item.staff_grade_description if r.job_item else None,
                planned_grade_code=r.job_item.planned_grade_code if r.job_item else None,
                window_start=r.window_start,
                window_end=r.window_end,
                slot_index=r.slot_index,
                due_date=r.due_date,
                status=r.status,
                source=r.source,
                required_staff_count=r.required_staff_count,
                required_hours_per_staff=r.required_hours_per_staff,
                needs_review=r.needs_review,
                created_at=r.created_at,
            )
            for r in rows
        ]

    @staticmethod
    async def update_occurrence(
        session: AsyncSession,
        occurrence_id: UUID,
        payload: JobOccurrenceUpdate,
        actor_user_id: UUID | None = None,
        actor_role: str | None = None,
    ) -> JobOccurrenceResponse:
        """Update occurrence due date or status."""
        occ = await session.get(JobOccurrence, occurrence_id)
        if not occ:
            raise AppError("OCCURRENCE_NOT_FOUND", "Occurrence not found.", status_code=404)

        diff: dict[str, Any] = {}
        if payload.due_date is not None:
            diff["due_date"] = str(payload.due_date)
            occ.due_date = payload.due_date
        if payload.status is not None:
            diff["status"] = payload.status
            occ.status = payload.status.upper()

        await session.flush()
        await AuditService.log_action(
            session=session,
            action="UPDATE_OCCURRENCE",
            entity_type="job_occurrence",
            entity_id=str(occ.id),
            diff=diff,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )

        return JobOccurrenceResponse.model_validate(occ)
