# Transport Module (`fw.modules.transport`)

The `transport` module manages fleet vehicles, daily morning and evening transport runs, driver manifests, ordered pick-up and drop-off stops, passenger manifests, and integration with the operational schedule and mobile devices.

---

## 1. Responsibilities

- **Fleet Vehicles**: Manage company-owned, leased, or assigned transport vehicles (buses, vans, etc.) and their active status.
- **Drivers & Runs**: Plan daily morning runs (from accommodation to client worksites) and evening runs (from worksites back to accommodation).
- **Stops & Manifests**: Define ordered stops (accommodations or worksites) with sequence, scheduled times, and assigned passengers per stop.
- **Schedule Validation**: Ensure passengers are scheduled to work on the run date, prevent assigning a worker to multiple morning (or evening) runs, and prevent assigning a driver to overlapping runs in the same direction.
- **Suggest Runs**: Automatically propose draft runs by grouping scheduled workers by accommodation and primary worksite.
- **Copy Day / Week**: Copy transport manifests forward to target dates, automatically omitting workers who are unscheduled or on approved leave on the target date, and returning a detailed list of omitted workers with clear reasons.
- **Reassignment / Schedule Sync**: Detect schedule changes or approved reassignments that affect workers on published runs, automatically flagging the affected run with `needs_update = True`.
- **Mobile Sync Manifests**: Publish runs to mobile devices (`TRANSPORT_RUN` sync entity) with strict role-based privacy slicing:
  - **Driver**: Receives all ordered stops and all passenger names.
  - **Passenger**: Receives the driver, vehicle, and only their specific stop with only their name (other stops and passenger names are stripped).
- **Printable Run Sheet**: Provide an operational driver manifest ready for printing (`@media print`) and dispatch operations.

---

## 2. Tables Owned

The module owns four tables created in Alembic migration `0012_transport_and_drivers.py`:

| Table | Purpose |
|---|---|
| `vehicles` | Fleet vehicles (`id`, `label`, `type`, `notes`, `is_active`, `version`). |
| `transport_runs` | Daily transport runs (`id`, `run_date`, `direction`, `driver_id`, `vehicle_id`, `status`, `needs_update`, `notes`, `version`, `created_by_user_id`). Unique constraint on `(run_date, direction, driver_id)`. |
| `transport_run_stops` | Ordered stops on a run (`id`, `run_id`, `stop_type`, `accommodation_id`, `worksite_id`, `sequence`, `planned_time`, `notes`). Unique constraint on `(run_id, sequence)`. |
| `transport_run_passengers` | Worker assignments to stops (`id`, `run_id`, `stop_id`, `employee_id`, `notes`). Unique constraint on `(run_id, employee_id)`. |

---

## 3. Public Interface (`__init__.py`)

External modules only access `fw.modules.transport` through its root export:

- **Router**: `transport_router` mounted under `/api/v1`.
- **Service**: `TransportService` for programmatic run creation, queries, and schedule change flagging.
- **Models**: `Vehicle`, `TransportRun`, `TransportRunStop`, `TransportRunPassenger`.
- **Schemas**: `VehicleCreate`, `VehicleUpdate`, `VehicleRead`, `DriverRead`, `TransportRunCreate`, `TransportRunUpdate`, `TransportRunRead`, `TransportRunListResponse`, `UnassignedWorkersResponse`, `SuggestRunsRequest`, `SuggestRunsResponse`, `CopyRunsRequest`, `CopyRunsResponse`.

---

## 4. Dependencies & Layering

Per `docs/13-architecture.md` and `pyproject.toml` import-linter contracts:
- **Allowed Downward Imports**: `fw.core`, `fw.modules.identity`, `fw.modules.settings`, `fw.modules.audit`, `fw.modules.org`, `fw.modules.jobs`, `fw.modules.scheduling`.
- **Consumers**:
  - `fw.modules.sync` listens for `TransportRunChanged` domain events to generate `TRANSPORT_RUN` change log entries (`UPSERT` and `DELETE`).
  - `fw.modules.sync` builds 30-day snapshot entries for `TRANSPORT_RUN` with privacy slicing.
  - `fw.modules.sync` (via `handle_scheduled_work_changed`) flags runs needing update when assigned workers have their schedule altered.

---

## 5. Why a Separate Module?

Transport operations represent a distinct business domain focused on physical logistics and dispatch. While it reads schedules and accommodations, it does not dictate attendance calculations, payroll rules, or GPS tracking logic. Isolating transport ensures that if a client does not use company transport, or if third-party vehicle tracking systems are utilized, the core field worker tracking, attendance, and payroll modules remain completely decoupled and operational.

