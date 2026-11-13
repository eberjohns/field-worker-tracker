from collections import defaultdict
from datetime import date, time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.errors import ProblemDetailsException
from fw.core.events import TransportRunChanged, event_bus
from fw.modules.audit import AuditService
from fw.modules.jobs import Worksite
from fw.modules.org import Accommodation, Employee
from fw.modules.scheduling import LeaveRequest, ScheduledWork
from fw.modules.transport.models import (
    TransportRun,
    TransportRunPassenger,
    TransportRunStop,
    Vehicle,
)
from fw.modules.transport.repository import TransportRepository
from fw.modules.transport.schemas import (
    CopyRunsRequest,
    CopyRunsResponse,
    DriverRead,
    OmittedPassenger,
    PassengerCreate,
    PassengerRead,
    PublishRunResponse,
    StopCreate,
    StopRead,
    SuggestRunsRequest,
    SuggestRunsResponse,
    TransportRunCreate,
    TransportRunRead,
    TransportRunUpdate,
    UnassignedWorkerRead,
    VehicleCreate,
    VehicleRead,
    VehicleUpdate,
)


class TransportService:
    def __init__(self, repo: TransportRepository | None = None) -> None:
        self.repo = repo or TransportRepository()

    # -------------------------------------------------------------------------
    # Vehicles
    # -------------------------------------------------------------------------
    async def list_vehicles(
        self, session: AsyncSession, active_only: bool = True
    ) -> list[VehicleRead]:
        vehicles = await self.repo.list_vehicles(session, active_only=active_only)
        return [VehicleRead.model_validate(v) for v in vehicles]

    async def get_vehicle(self, session: AsyncSession, vehicle_id: UUID) -> VehicleRead:
        v = await self.repo.get_vehicle(session, vehicle_id)
        if not v:
            raise ProblemDetailsException(
                status_code=404,
                title="Vehicle Not Found",
                detail=f"Vehicle {vehicle_id} not found.",
                code="NOT_FOUND",
            )
        return VehicleRead.model_validate(v)

    async def create_vehicle(
        self, session: AsyncSession, data: VehicleCreate, actor_user_id: UUID | None = None
    ) -> VehicleRead:
        vehicle = Vehicle(
            label=data.label,
            type=data.type,
            notes=data.notes,
        )
        saved = await self.repo.create_vehicle(session, vehicle)
        await AuditService.log_action(
            session=session,
            action="CREATE_VEHICLE",
            entity_type="vehicle",
            entity_id=str(saved.id),
            diff={"label": saved.label, "type": saved.type},
            actor_user_id=actor_user_id,
        )
        return VehicleRead.model_validate(saved)

    async def update_vehicle(
        self,
        session: AsyncSession,
        vehicle_id: UUID,
        data: VehicleUpdate,
        actor_user_id: UUID | None = None,
    ) -> VehicleRead:
        vehicle = await self.repo.get_vehicle(session, vehicle_id)
        if not vehicle:
            raise ProblemDetailsException(
                status_code=404,
                title="Vehicle Not Found",
                detail=f"Vehicle {vehicle_id} not found.",
                code="NOT_FOUND",
            )

        diff = {}
        if data.label is not None and data.label != vehicle.label:
            diff["label"] = data.label
            vehicle.label = data.label
        if data.type is not None and data.type != vehicle.type:
            diff["type"] = data.type
            vehicle.type = data.type
        if data.notes is not None and data.notes != vehicle.notes:
            diff["notes"] = data.notes
            vehicle.notes = data.notes
        if data.is_active is not None and data.is_active != vehicle.is_active:
            diff["is_active"] = data.is_active
            vehicle.is_active = data.is_active

        if diff:
            vehicle.version += 1
            await session.flush()
            await AuditService.log_action(
                session=session,
                action="UPDATE_VEHICLE",
                entity_type="vehicle",
                entity_id=str(vehicle.id),
                diff=diff,
                actor_user_id=actor_user_id,
            )
        return VehicleRead.model_validate(vehicle)

    # -------------------------------------------------------------------------
    # Drivers
    # -------------------------------------------------------------------------
    async def list_drivers(
        self, session: AsyncSession, week_start: date | None = None
    ) -> list[DriverRead]:
        raw_drivers = await self.repo.list_drivers(session, week_start=week_start)
        return [DriverRead.model_validate(d) for d in raw_drivers]

    # -------------------------------------------------------------------------
    # Helper to construct TransportRunRead
    # -------------------------------------------------------------------------
    async def _build_run_read(self, session: AsyncSession, run: TransportRun) -> TransportRunRead:
        driver = await session.get(Employee, run.driver_id)
        driver_name = driver.name if driver else "Unknown Driver"
        driver_phone = driver.phone if driver else None
        driver_tally = driver.tally_id if driver else None

        vehicle_label = run.vehicle.label if run.vehicle else None

        stops_read: list[StopRead] = []
        total_passengers = 0

        for stop in sorted(run.stops, key=lambda s: s.sequence):
            worksite_name = None
            worksite_address = None
            if stop.worksite_id:
                ws = await session.get(Worksite, stop.worksite_id)
                if ws:
                    worksite_name = f"{ws.job_number} - {ws.job_name}"
                    worksite_address = None

            acc_name = None
            if stop.accommodation_id:
                acc = await session.get(Accommodation, stop.accommodation_id)
                if acc:
                    acc_name = acc.name

            passengers_read: list[PassengerRead] = []
            for p in stop.passengers:
                emp = await session.get(Employee, p.employee_id)
                if emp:
                    passengers_read.append(
                        PassengerRead(
                            id=p.id,
                            employee_id=emp.id,
                            tally_id=emp.tally_id,
                            name=emp.name,
                            phone=emp.phone,
                            worksite_id=stop.worksite_id,
                            worksite_name=worksite_name,
                        )
                    )
            total_passengers += len(passengers_read)

            stops_read.append(
                StopRead(
                    id=stop.id,
                    sequence=stop.sequence,
                    stop_type=stop.stop_type,
                    worksite_id=stop.worksite_id,
                    worksite_name=worksite_name,
                    worksite_address=worksite_address,
                    accommodation_id=stop.accommodation_id,
                    accommodation_name=acc_name,
                    planned_time=str(stop.planned_time) if stop.planned_time else None,
                    passengers=passengers_read,
                )
            )

        return TransportRunRead(
            id=run.id,
            run_date=run.run_date,
            direction=run.direction,
            driver_id=run.driver_id,
            driver_name=driver_name,
            driver_phone=driver_phone,
            driver_tally_id=driver_tally,
            vehicle_id=run.vehicle_id,
            vehicle_label=vehicle_label,
            status=run.status,
            needs_update=run.needs_update,
            version=run.version,
            stops=stops_read,
            total_passengers=total_passengers,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    # -------------------------------------------------------------------------
    # Transport Runs
    # -------------------------------------------------------------------------
    async def get_run(self, session: AsyncSession, run_id: UUID) -> TransportRunRead:
        run = await self.repo.get_run(session, run_id)
        if not run:
            raise ProblemDetailsException(
                status_code=404,
                title="Transport Run Not Found",
                detail=f"Run {run_id} not found.",
                code="NOT_FOUND",
            )
        return await self._build_run_read(session, run)

    async def list_runs(
        self,
        session: AsyncSession,
        run_date: date,
        direction: str | None = None,
    ) -> list[TransportRunRead]:
        runs = await self.repo.list_runs(session, run_date=run_date, direction=direction)
        result: list[TransportRunRead] = []
        for r in runs:
            result.append(await self._build_run_read(session, r))
        return result

    async def create_run(
        self,
        session: AsyncSession,
        data: TransportRunCreate,
        actor_user_id: UUID | None = None,
    ) -> TransportRunRead:
        # 1. Validate driver is active employee with is_driver=True
        driver = await session.get(Employee, data.driver_id)
        if not driver or not driver.is_active:
            raise ProblemDetailsException(
                status_code=400,
                title="Invalid Driver",
                detail="Selected driver does not exist or is inactive.",
                code="INVALID_DRIVER",
            )
        if not driver.is_driver:
            raise ProblemDetailsException(
                status_code=400,
                title="Invalid Driver",
                detail=f"Employee {driver.name} is not designated as a driver.",
                code="NOT_A_DRIVER",
            )

        # 2. Check driver overlap on date & direction
        if await self.repo.check_driver_conflict(
            session, data.driver_id, data.run_date, data.direction
        ):
            raise ProblemDetailsException(
                status_code=409,
                title="Driver Conflict",
                detail=f"Driver {driver.name} already has a {data.direction} run on {data.run_date}.",
                code="DRIVER_ALREADY_ASSIGNED",
            )

        # 3. Validate passengers: check for conflicts across existing runs
        seen_run_passengers: set[UUID] = set()
        for s in data.stops:
            for p in s.passengers:
                if p.employee_id in seen_run_passengers:
                    raise ProblemDetailsException(
                        status_code=409,
                        title="Duplicate Passenger in Run",
                        detail=f"Employee {p.employee_id} appears multiple times in this run.",
                        code="DUPLICATE_PASSENGER",
                    )
                seen_run_passengers.add(p.employee_id)

                conflict = await self.repo.check_worker_conflict(
                    session, p.employee_id, data.run_date, data.direction
                )
                if conflict:
                    p_emp = await session.get(Employee, p.employee_id)
                    p_name = p_emp.name if p_emp else str(p.employee_id)
                    raise ProblemDetailsException(
                        status_code=409,
                        title="Worker Run Conflict",
                        detail=f"Worker {p_name} is already assigned to a {data.direction} run on {data.run_date}.",
                        code="WORKER_RUN_CONFLICT",
                    )

        # 4. Create Run
        run = TransportRun(
            run_date=data.run_date,
            direction=data.direction,
            driver_id=data.driver_id,
            vehicle_id=data.vehicle_id,
            status="DRAFT",
            needs_update=False,
            created_by_user_id=actor_user_id,
        )
        session.add(run)
        await session.flush()

        # 5. Create stops and passengers
        for stop_dto in data.stops:
            stop = TransportRunStop(
                run_id=run.id,
                sequence=stop_dto.sequence,
                stop_type=stop_dto.stop_type,
                worksite_id=stop_dto.worksite_id,
                accommodation_id=stop_dto.accommodation_id,
                planned_time=stop_dto.planned_time
                if isinstance(stop_dto.planned_time, time)
                else None,
            )
            session.add(stop)
            await session.flush()

            for p_dto in stop_dto.passengers:
                passenger = TransportRunPassenger(
                    run_id=run.id,
                    stop_id=stop.id,
                    employee_id=p_dto.employee_id,
                )
                session.add(passenger)

        await session.flush()
        await AuditService.log_action(
            session=session,
            action="CREATE_TRANSPORT_RUN",
            entity_type="transport_run",
            entity_id=str(run.id),
            diff={
                "run_date": str(run.run_date),
                "direction": run.direction,
                "driver_id": str(run.driver_id),
                "passengers_count": len(seen_run_passengers),
            },
            actor_user_id=actor_user_id,
        )

        # Reload with relationships
        loaded = await self.repo.get_run(session, run.id)
        assert loaded is not None
        return await self._build_run_read(session, loaded)

    async def update_run(
        self,
        session: AsyncSession,
        run_id: UUID,
        data: TransportRunUpdate,
        actor_user_id: UUID | None = None,
    ) -> TransportRunRead:
        run = await self.repo.get_run(session, run_id)
        if not run:
            raise ProblemDetailsException(
                status_code=404,
                title="Transport Run Not Found",
                detail=f"Run {run_id} not found.",
                code="NOT_FOUND",
            )

        diff = {}
        was_published = run.status == "PUBLISHED"

        # Check driver change
        if data.driver_id is not None and data.driver_id != run.driver_id:
            driver = await session.get(Employee, data.driver_id)
            if not driver or not driver.is_active or not driver.is_driver:
                raise ProblemDetailsException(
                    status_code=400,
                    title="Invalid Driver",
                    detail="Selected driver is invalid or not designated as a driver.",
                    code="INVALID_DRIVER",
                )
            if await self.repo.check_driver_conflict(
                session, data.driver_id, run.run_date, run.direction, exclude_run_id=run.id
            ):
                raise ProblemDetailsException(
                    status_code=409,
                    title="Driver Conflict",
                    detail=f"Driver {driver.name} already has a {run.direction} run on {run.run_date}.",
                    code="DRIVER_ALREADY_ASSIGNED",
                )
            diff["driver_id"] = str(data.driver_id)
            run.driver_id = data.driver_id

        if data.vehicle_id is not None and data.vehicle_id != run.vehicle_id:
            diff["vehicle_id"] = str(data.vehicle_id)
            run.vehicle_id = data.vehicle_id

        if data.status is not None and data.status != run.status:
            diff["status"] = data.status
            run.status = data.status

        if data.needs_update is not None:
            diff["needs_update"] = data.needs_update
            run.needs_update = data.needs_update

        # Update stops if provided
        affected_passenger_ids: list[UUID] = [p.employee_id for p in run.passengers]
        if data.stops is not None:
            # Validate passenger uniqueness and conflicts
            seen_run_passengers: set[UUID] = set()
            for s in data.stops:
                for p in s.passengers:
                    if p.employee_id in seen_run_passengers:
                        raise ProblemDetailsException(
                            status_code=409,
                            title="Duplicate Passenger in Run",
                            detail=f"Employee {p.employee_id} appears multiple times in this run.",
                            code="DUPLICATE_PASSENGER",
                        )
                    seen_run_passengers.add(p.employee_id)

                    conflict = await self.repo.check_worker_conflict(
                        session, p.employee_id, run.run_date, run.direction, exclude_run_id=run.id
                    )
                    if conflict:
                        p_emp = await session.get(Employee, p.employee_id)
                        p_name = p_emp.name if p_emp else str(p.employee_id)
                        raise ProblemDetailsException(
                            status_code=409,
                            title="Worker Run Conflict",
                            detail=f"Worker {p_name} is already assigned to a {run.direction} run on {run.run_date}.",
                            code="WORKER_RUN_CONFLICT",
                        )

            # Reconstruct stops & passengers
            run.stops.clear()
            run.passengers.clear()
            await session.flush()

            for stop_dto in data.stops:
                stop = TransportRunStop(
                    run_id=run.id,
                    sequence=stop_dto.sequence,
                    stop_type=stop_dto.stop_type,
                    worksite_id=stop_dto.worksite_id,
                    accommodation_id=stop_dto.accommodation_id,
                    planned_time=stop_dto.planned_time
                    if isinstance(stop_dto.planned_time, time)
                    else None,
                )
                session.add(stop)
                await session.flush()

                for p_dto in stop_dto.passengers:
                    passenger = TransportRunPassenger(
                        run_id=run.id,
                        stop_id=stop.id,
                        employee_id=p_dto.employee_id,
                    )
                    session.add(passenger)
            diff["stops_updated"] = True
            affected_passenger_ids = list(seen_run_passengers)

        # Clear needs_update when updated/reviewed
        run.needs_update = False
        run.version += 1
        await session.flush()

        await AuditService.log_action(
            session=session,
            action="UPDATE_TRANSPORT_RUN",
            entity_type="transport_run",
            entity_id=str(run.id),
            diff=diff,
            actor_user_id=actor_user_id,
        )

        # If run is published, emit sync event so mobile receives changes immediately
        if was_published or run.status == "PUBLISHED":
            await event_bus.publish(
                TransportRunChanged(
                    run_id=run.id,
                    run_date=run.run_date,
                    driver_id=run.driver_id,
                    affected_employee_ids=affected_passenger_ids,
                    op="UPSERT",
                ),
                session=session,
            )

        loaded = await self.repo.get_run(session, run.id)
        assert loaded is not None
        return await self._build_run_read(session, loaded)

    async def publish_run(
        self,
        session: AsyncSession,
        run_id: UUID,
        actor_user_id: UUID | None = None,
    ) -> PublishRunResponse:
        run = await self.repo.get_run(session, run_id)
        if not run:
            raise ProblemDetailsException(
                status_code=404,
                title="Transport Run Not Found",
                detail=f"Run {run_id} not found.",
                code="NOT_FOUND",
            )

        run.status = "PUBLISHED"
        run.needs_update = False
        run.version += 1
        await session.flush()

        passenger_ids = [p.employee_id for p in run.passengers]
        await event_bus.publish(
            TransportRunChanged(
                run_id=run.id,
                run_date=run.run_date,
                driver_id=run.driver_id,
                affected_employee_ids=passenger_ids,
                op="UPSERT",
            ),
            session=session,
        )

        await AuditService.log_action(
            session=session,
            action="PUBLISH_TRANSPORT_RUN",
            entity_type="transport_run",
            entity_id=str(run.id),
            diff={"status": "PUBLISHED", "version": run.version},
            actor_user_id=actor_user_id,
        )

        return PublishRunResponse(
            id=run.id,
            status="PUBLISHED",
            version=run.version,
            synced_recipients_count=len(passenger_ids) + 1,
        )

    async def delete_run(
        self,
        session: AsyncSession,
        run_id: UUID,
        actor_user_id: UUID | None = None,
    ) -> None:
        run = await self.repo.get_run(session, run_id)
        if not run:
            raise ProblemDetailsException(
                status_code=404,
                title="Transport Run Not Found",
                detail=f"Run {run_id} not found.",
                code="NOT_FOUND",
            )

        was_published = run.status == "PUBLISHED"
        passenger_ids = [p.employee_id for p in run.passengers]
        driver_id = run.driver_id
        run_date = run.run_date

        run.is_active = False
        run.version += 1
        await session.flush()

        if was_published:
            await event_bus.publish(
                TransportRunChanged(
                    run_id=run.id,
                    run_date=run_date,
                    driver_id=driver_id,
                    affected_employee_ids=passenger_ids,
                    op="DELETE",
                ),
                session=session,
            )

        await AuditService.log_action(
            session=session,
            action="DELETE_TRANSPORT_RUN",
            entity_type="transport_run",
            entity_id=str(run.id),
            diff={"is_active": False},
            actor_user_id=actor_user_id,
        )

    # -------------------------------------------------------------------------
    # Suggest Runs from Schedule
    # -------------------------------------------------------------------------
    async def suggest_runs(
        self,
        session: AsyncSession,
        request: SuggestRunsRequest,
        actor_user_id: UUID | None = None,
    ) -> SuggestRunsResponse:
        """Group unassigned scheduled workers by accommodation and worksite and propose draft runs."""
        unassigned = await self.repo.list_unassigned_workers(
            session, run_date=request.run_date, direction=request.direction
        )
        if not unassigned:
            return SuggestRunsResponse(suggested_runs=[], unassigned_workers=[])

        # Find available drivers for this day/direction
        drivers = await self.repo.list_drivers(session)
        available_drivers: list[dict] = []
        for d in drivers:
            has_conflict = await self.repo.check_driver_conflict(
                session, d["employee_id"], request.run_date, request.direction
            )
            if not has_conflict:
                available_drivers.append(d)

        # Cluster unassigned workers by (accommodation_id, worksite_id)
        clusters: dict[tuple[UUID | None, UUID | None], list[dict]] = defaultdict(list)
        for w in unassigned:
            key = (w["accommodation_id"], w["worksite_id"])
            clusters[key].append(w)

        created_runs: list[TransportRunRead] = []
        driver_idx = 0

        for (acc_id, ws_id), workers in clusters.items():
            if not ws_id:
                continue

            # Pick an available driver if one exists
            driver_info = None
            if driver_idx < len(available_drivers):
                driver_info = available_drivers[driver_idx]
                driver_idx += 1

            if not driver_info:
                # No driver available for this cluster; workers stay unassigned
                continue

            # Propose Stops
            # Morning: Stop 1 = Accommodation, Stop 2 = Worksite
            # Evening: Stop 1 = Worksite, Stop 2 = Accommodation
            stops: list[StopCreate] = []
            if request.direction == "MORNING":
                if acc_id:
                    stops.append(
                        StopCreate(
                            sequence=1,
                            stop_type="ACCOMMODATION",
                            accommodation_id=acc_id,
                            passengers=[],
                        )
                    )
                stops.append(
                    StopCreate(
                        sequence=len(stops) + 1,
                        stop_type="SITE",
                        worksite_id=ws_id,
                        passengers=[PassengerCreate(employee_id=w["employee_id"]) for w in workers],
                    )
                )
            else:
                stops.append(
                    StopCreate(
                        sequence=1,
                        stop_type="SITE",
                        worksite_id=ws_id,
                        passengers=[],
                    )
                )
                if acc_id:
                    stops.append(
                        StopCreate(
                            sequence=2,
                            stop_type="ACCOMMODATION",
                            accommodation_id=acc_id,
                            passengers=[
                                PassengerCreate(employee_id=w["employee_id"]) for w in workers
                            ],
                        )
                    )

            run_dto = TransportRunCreate(
                run_date=request.run_date,
                direction=request.direction,
                driver_id=driver_info["employee_id"],
                vehicle_id=None,
                stops=stops,
            )
            created_run = await self.create_run(session, run_dto, actor_user_id=actor_user_id)
            created_runs.append(created_run)

        # Fetch remaining unassigned
        remaining_unassigned = await self.repo.list_unassigned_workers(
            session, run_date=request.run_date, direction=request.direction
        )
        return SuggestRunsResponse(
            suggested_runs=created_runs,
            unassigned_workers=[
                UnassignedWorkerRead.model_validate(w) for w in remaining_unassigned
            ],
        )

    # -------------------------------------------------------------------------
    # Copy Runs Forward
    # -------------------------------------------------------------------------
    async def copy_runs(
        self,
        session: AsyncSession,
        request: CopyRunsRequest,
        actor_user_id: UUID | None = None,
    ) -> CopyRunsResponse:
        """Copy runs from source date to target date, filtering out workers not scheduled."""
        source_runs = await self.repo.list_runs(
            session, run_date=request.source_date, direction=request.direction
        )
        if not source_runs:
            return CopyRunsResponse(created_runs=[], omitted_passengers=[])

        # Get all workers actively scheduled on the target date
        target_sched_q = select(ScheduledWork.employee_id).where(
            ScheduledWork.work_date == request.target_date,
            ScheduledWork.status == "ACTIVE",
        )
        target_sched_res = await session.execute(target_sched_q)
        scheduled_employee_ids = set(target_sched_res.scalars().all())

        # Check leaves on target date
        leave_q = select(LeaveRequest.employee_id).where(
            LeaveRequest.from_date <= request.target_date,
            LeaveRequest.to_date >= request.target_date,
            LeaveRequest.status == "APPROVED",
        )
        leave_res = await session.execute(leave_q)
        on_leave_ids = set(leave_res.scalars().all())

        created_runs: list[TransportRunRead] = []
        omitted_passengers: list[OmittedPassenger] = []

        for src_run in source_runs:
            # Check if driver has a conflict on target date
            driver_conflict = await self.repo.check_driver_conflict(
                session, src_run.driver_id, request.target_date, src_run.direction
            )
            if driver_conflict:
                driver_emp = await session.get(Employee, src_run.driver_id)
                d_name = driver_emp.name if driver_emp else str(src_run.driver_id)
                omitted_passengers.append(
                    OmittedPassenger(
                        employee_id=src_run.driver_id,
                        tally_id=driver_emp.tally_id if driver_emp else "",
                        name=d_name,
                        reason=f"Driver already has a {src_run.direction} run on target date",
                    )
                )
                continue

            # Build stops with valid passengers
            new_stops: list[StopCreate] = []
            for src_stop in sorted(src_run.stops, key=lambda s: s.sequence):
                valid_passengers: list[PassengerCreate] = []
                for p in src_stop.passengers:
                    emp = await session.get(Employee, p.employee_id)
                    p_name = emp.name if emp else str(p.employee_id)
                    p_tally = emp.tally_id if emp else ""

                    if p.employee_id in on_leave_ids:
                        omitted_passengers.append(
                            OmittedPassenger(
                                employee_id=p.employee_id,
                                tally_id=p_tally,
                                name=p_name,
                                reason="On approved leave",
                            )
                        )
                    elif p.employee_id not in scheduled_employee_ids:
                        omitted_passengers.append(
                            OmittedPassenger(
                                employee_id=p.employee_id,
                                tally_id=p_tally,
                                name=p_name,
                                reason="Not scheduled on target date",
                            )
                        )
                    else:
                        valid_passengers.append(PassengerCreate(employee_id=p.employee_id))

                new_stops.append(
                    StopCreate(
                        sequence=src_stop.sequence,
                        stop_type=src_stop.stop_type,
                        worksite_id=src_stop.worksite_id,
                        accommodation_id=src_stop.accommodation_id,
                        planned_time=src_stop.planned_time,
                        passengers=valid_passengers,
                    )
                )

            run_dto = TransportRunCreate(
                run_date=request.target_date,
                direction=src_run.direction,
                driver_id=src_run.driver_id,
                vehicle_id=src_run.vehicle_id,
                stops=new_stops,
            )
            created = await self.create_run(session, run_dto, actor_user_id=actor_user_id)
            created_runs.append(created)

        return CopyRunsResponse(
            created_runs=created_runs,
            omitted_passengers=omitted_passengers,
        )

    # -------------------------------------------------------------------------
    # Unassigned Workers
    # -------------------------------------------------------------------------
    async def list_unassigned_workers(
        self,
        session: AsyncSession,
        run_date: date,
        direction: str = "MORNING",
    ) -> list[UnassignedWorkerRead]:
        unassigned = await self.repo.list_unassigned_workers(
            session, run_date=run_date, direction=direction
        )
        return [UnassignedWorkerRead.model_validate(w) for w in unassigned]
