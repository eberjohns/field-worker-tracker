# 014 - Planner: Standing Assignments, Scheduled Work, and Roster Markers

Status: Accepted  
Date: 2026-11-05  

## Context
Phase 05 establishes the operations planning and weekly roster system for the Field Worker Tracker.
Per client requirements and decisions DEC-36, DEC-42, and DEC-52:
1. Operations coordinators and engineers plan long-term work using standing assignments (e.g. permanent teams on repeating weekday schedules).
2. Daily schedules need to be materialized so occurrences have concrete assigned workers, visit sequences, and audit history.
3. Roster views must display day markers: `SKIPPED` (for holidays when work does not occur on public holidays), `WEEKLY_OFF`, `ON_LEAVE`, `TO_BE_COVERED` (under-staffed job slots), and `FREE` (worker with zero assigned hours).
4. Schedulers need real-time validation warnings (PERMANENT job exclusivity, standard hours over/under-allocation, grade-group mismatch, past date scheduling restrictions).
5. Candidate workers must be recommended according to DEC-52 (same grade-group first-class eligibility, exact staff type first `*`, site familiarity, team affinity, and available capacity).

## Options considered
- **Materialization vs Virtual Generation**:
  - *Option A (On-the-fly virtual calculation)*: Compute scheduled work dynamically upon every query from standing assignments without persisting daily rows.
  - *Option B (13-month rolling horizon materialization)*: Materialize concrete `scheduled_work` records linked to job occurrences up to 13 months ahead (matching retention policy DEC-38).
- **Ending or Changing Standing Assignments**:
  - *Option A (Hard delete future records)*: Delete future `scheduled_work` rows when an assignment ends or is modified.
  - *Option B (Audit cancellation)*: Deactivate or set future unstarted rows to `CANCELLED` (or soft-delete them) so the historical plan remains verifiable.
- **Occurrence Linkage**:
  - *Option A (Loose linkage)*: Link `scheduled_work` only to `job_items`.
  - *Option B (Strict occurrence linkage)*: Link `scheduled_work` to both `job_items` and `job_occurrences` for the specific calendar date, allowing visit sequence tracking and mobile sync.
- **Standard Hours and Ramadan Adjustment**:
  - *Option A (Hardcoded 8 hours)*: Assume 8 hours for all workers and dates.
  - *Option B (Dynamic salary + time rules resolution)*: Resolve base standard hours from `employee_salary` (or default 8 h) and apply effective time rules (e.g. Ramadan -2 h reduction for Muslim workers).

## Decision
- Adopt **Option B (13-month rolling horizon materialization)**: Standing assignments generate concrete `scheduled_work` rows linked directly to `job_occurrences` for each active weekday pattern.
- Adopt **Option B (Audit cancellation)**: When a standing assignment is ended with an `end_date`, any future unstarted scheduled work beyond that date is cancelled/removed with audit logging, while completed and past records remain immutable.
- Adopt **Option B (Strict occurrence linkage)**: Scheduled work rows link to both `job_items` and `job_occurrences`. Visits are assigned an explicit `sequence` (1, 2, 3...) per worker per day.
- Adopt **Option B (Dynamic salary + time rules resolution)**: `fw.rules.scheduling.allocation` resolves standard hours per worker from salary structure and applies the Ramadan -120 min adjustment when effective.
- **Pure Domain Rules**: `fw.rules.scheduling` contains zero database and zero HTTP imports. It handles candidate ranking (DEC-52), day markers (`SKIPPED`, `WEEKLY_OFF`, `ON_LEAVE`, `TO_BE_COVERED`, `FREE`), assignment validation (PERMANENT blocking, standard hours limits), and Excel sheet rendering.
- **Sequence Reordering**: Visit sequence updates use a temporary positive offset (`1000 + idx`) in step 1 to prevent unique index collisions before applying the final sequential order `(1, 2, ...)`.
- **Role Permissions for Past Dates**: Scheduling in the past is rejected for regular users (`PAST_DATE` error) but permitted for Admin users with audit logging, evaluated in country local time.

## Why
- Materializing scheduled work ensures daily operations (check-ins, GPS tracking, mobile sync, and exceptions) have persistent target records with clear visit sequences.
- Keeping business rules in pure Python allows comprehensive testing without database dependencies and guarantees fast evaluation (< 2 s for 300 workers).
- Strict occurrence linkage enables 1:1 reconciliation between planned work, assigned staff, and actual field attendance.

## Consequences
- Alembic migration `0006_planner_and_scheduling.py` introduces `standing_assignments` and `scheduled_work` tables with partial unique indexes.
- FastAPI router `fw.api.scheduling` exposes `/roster`, `/schedule/coverage`, `/workers/{id}/allocation`, `/standing-assignments`, and `/scheduled-work` endpoints (including Excel streaming).
- React dashboard at `/planner` provides Weekly Roster, Job Coverage, and Year Plan views with capacity side panel, candidate recommendations, and visit sequence reordering.
