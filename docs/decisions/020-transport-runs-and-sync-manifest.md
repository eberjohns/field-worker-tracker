# 020 - Transport runs, mobile sync manifests, and schedule integration

Status: Accepted  
Date: 2026-11-13  

## Context
Client requirement DEC-44 and design specification D5 describe transport operations for field work: recording vehicles and daily morning and evening transport runs (driver, ordered stops, passengers) synced to drivers and workers. Vehicles carry workers from camps/accommodations to client worksites in the morning, and return them in the evening. Workers must know who is driving them and what vehicle they are traveling in, and drivers must know the full ordered route and passenger roster. In addition, when worker schedules change or temporary reassignments occur, transport manifests must reflect discrepancies.

## Options considered
1. **Implicit transport derived directly from scheduled work**:
   Infer driver runs automatically based purely on worker scheduled worksites and employee accommodation assignments.
   - *Drawback*: Real-world field logistics require explicit fleet vehicle tracking, manual stop ordering, capacity decisions, and flexibility (e.g. one driver serving 3 different worksites, workers swapping vehicles, or workers with different accommodations).
2. **Dedicated transport module with daily run manifests, mobile privacy slicing, and schedule-change flagging (Chosen)**:
   - Dedicated tables: `vehicles`, `transport_runs`, `transport_run_stops`, `transport_run_passengers`.
   - Distinct directions: `MORNING` (Accommodation -> Worksites) and `EVENING` (Worksites -> Accommodation).
   - Validation constraints: A worker is on at most one run per direction per date; a driver cannot be assigned to overlapping runs in the same direction on the same date.
   - Privacy-sliced sync payload: Drivers receive the complete ordered route and all passenger names; passengers receive their driver, vehicle, and only their own designated stop with only their name (other passengers and other stops omitted).
   - Schedule integration: When an approved reassignment or schedule modification changes a scheduled worker who is on a published run, the run is flagged with `needs_update = True`.
   - Operational tools: Run suggestion algorithm grouping unassigned scheduled workers by accommodation and primary worksite; day/week copy tool with automatic omission of unscheduled/on-leave workers and explicit reason reporting; printable driver run sheet (`@media print`).

## Decision
Adopt Option 2:
- Implement `fw.modules.transport` with explicit vehicle and run entities.
- Enforce single-run constraints per worker per direction per date at the database and application levels.
- Emit `TransportRunChanged` domain events upon publishing or cancelling runs, triggering synchronous `sync_changes` delta generation (`UPSERT`/`DELETE`) and 30-day snapshot population with role-aware privacy slicing.
- Integrate `handle_scheduled_work_changed` event listener to set `needs_update = True` on published runs when an assigned worker's schedule changes.
- Provide a dedicated web interface at `/transport` with morning/evening views, unassigned worker tray, run editor, vehicle management, day copy with omission summary, and printable driver run sheets.

## Why
Provides full operational dispatch control while protecting worker privacy on mobile devices. Decoupling transport from attendance and payroll engines ensures that third-party vehicle tracking hardware and core system components operate without circular dependencies or hard coupling.

## Consequences
- Dispatchers can plan, edit, copy, and publish morning and evening runs with high operational confidence.
- Mobile sync change logs provide offline-capable manifests to drivers and passengers.
- If schedule changes occur after publishing, dispatchers see the `needs_update` flag immediately.
- Zero impact on core attendance and payroll if transport is not used for a worksite or worker.

