# 018 - Attendance Engine, PostGIS Enrichment, and Append-Only Immutability

Status: Accepted  
Date: 2026-11-09  

## Context
Phase 08 implements event ingestion enrichment and the attendance calculation engine. The system must process raw location events from mobile devices, evaluate spatial containment against polygons (worksites and worker accommodations), construct site visits and tracking gaps, compute daily attendance against 5-point planned schedules, classify overtime per DEC-01, route anomalies to review, and maintain append-only immutability for auditability.

Key requirements and client decisions:
1. **Append-Only Immutability** (Golden Rule #4, DEC-14): Raw mobile event records must never be deleted or updated in their device-reported fields (`event_timestamp_utc`, coordinates, mock location, accuracy).
2. **PostGIS Spatial Enrichment**: Point-in-polygon containment (`ST_Covers`) and distance (`ST_Distance`) evaluate spatial verdicts (`INSIDE`, `BORDERLINE`, `OUTSIDE`, `NO_POLYGON`).
3. **Pure Business Rules Engine** (Golden Rule #2): Attendance logic resides in `fw.rules.attendance` with zero ORM or HTTP dependencies.
4. **5-Point Planned Schedules & Time Rules** (DEC-03, DEC-41, ADR-012): Planned times and breaks resolve hierarchically; job-item break overrides take precedence.
5. **Overtime Classification** (DEC-01): Public holidays and Sunday (OT2 day) work is classified as OT2 (1.5x). Hours beyond standard hours on normal days are OT1 (1.25x). Weekly-off and unassigned days are 100% OT1.
6. **Supervisor & Engineer Approvals** (DEC-43): Clean rows are automatically approved. Rows with variations, shortfall, overtime, or anomaly flags require review. Supervisors submit explanation comments; Engineers approve or reject with audit trail.

## Options considered
- **Application-only immutability vs Database Trigger**: Relying on SQLAlchemy event listeners or repository methods leaves direct database queries vulnerable. A PostgreSQL `BEFORE UPDATE OR DELETE` trigger guarantees database-level immutability across all connections with transaction-local bypass (`fwt.bypass_immutability`) for admin bootstrap wipes.
- **Async Event Ingestion vs Synchronous Ingestion**: Celery/Procrastinate background queue versus synchronous processing. In Phase 08, events are synchronously enriched and attendance calculated via domain event bus within the request session, ensuring instant UI reflection and deterministic test assertions without polling.
- **In-place updates vs Calculation Versioning**: Mutating attendance records destroys history. Storing immutable calculation snapshots (`attendance_calculations`) with SHA-256 `input_hash` and linking `current_calculation_id` enables full version comparison across recalculations.

## Decision
1. **Append-Only Trigger**: Created `trg_mobile_event_logs_append_only` in PostgreSQL to prevent deletions and updates to client-reported columns. Added session setting `fwt.bypass_immutability` for reset endpoints.
2. **Decoupled Architecture**: `fw.modules.events` ingests raw events and fires `EventsIngested` domain event. `fw.modules.attendance` listens synchronously, triggers spatial enrichment with assigned sites, and runs `AttendanceService.recalculate_day`.
3. **Pure Attendance Engine**: Implemented `verdicts.py`, `visits.py`, `gaps.py`, and `engine.py` in `fw.rules.attendance`.
4. **Versioned Calculations**: Each recalculation hashes inputs (`input_hash`). If inputs have changed, a new versioned `attendance_calculations` snapshot is inserted and `current_calculation_id` is updated.
5. **Review & Approval Workflow**: Supervisors provide comments; Engineers record decisions (`APPROVED` or `REJECTED`). Decisions snapshot the calculation version.

## Why
- Guarantees regulatory compliance and labor audit defensibility.
- Maintains strict modular monolith layers (`fw.rules` pure, `attendance` -> `events` / `scheduling`).
- Provides deterministic calculations and instant feedback for supervisors and engineers.

## Consequences
- Raw events cannot be deleted in production; test fixtures and admin resets must set `fwt.bypass_immutability = 'on'`.
- Module layering contract is strictly kept: `events` publishes domain events without importing `attendance`.
- Related docs updated: `docs/05-attendance-engine.md`, `docs/07-data-model.md`, `docs/08-api-spec.md`.
