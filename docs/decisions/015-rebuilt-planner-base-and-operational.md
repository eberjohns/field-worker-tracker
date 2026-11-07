# 015 - Rebuilt Planner Architecture: Base Planner and Operational Planner

Status: Accepted  
Date: 2026-11-07  

## Context
Phase 05 established operations planning and scheduling. In real-world field workforce management, users require a clean conceptual and operational separation between:
1. **Long-Term Recurring Master Blueprint**: Setting up contractual commitments and recurring weekly/monthly/quarterly staff allocations by worksite without date-specific operational noise.
2. **Live Daily Operations**: Managing daily reality (leave gaps, sickness covers, client-requested shift cancellations, compensatory overtime, and weather delays) on concrete calendar dates.
3. **Explicit Day Storage**: Convenience actions (like "Apply across active days") must never overwrite or clear individually customized days (e.g. Sunday or Friday) or wipe multi-week periodic cadence assignments.
4. **Base Worker Operational Cancellations**: Planners need the ability to operationally cancel a recurring base worker for a specific date without assigning a cover, documenting a mandatory reason, and decrementing the active visit quota if the entire visit is cancelled.
5. **Supervisor Crew Filtering & Heatmap Ergonomics**: Coordinators need persistent table headers, supervisor crew grouping toggles, and hours heatmap shading (under-target, met, overtime) without system administrators cluttering the worker roster.

## Options considered
- **Unified Single Planner vs Dedicated Dual-Workspace Separation**:
  - *Option A (Single unified page)*: Mix recurring blueprint rules and live overrides into a single view with multiple modal modes.
  - *Option B (Dedicated Dual Workspaces)*: Architecturally separate into **Base Planner (`/base-planner`)** for the recurring blueprint master and **Operational Planner (`/operational-planner`)** for live daily execution.
- **Base Worker Removal Persistence**:
  - *Option A (Direct deletion of base template)*: Deleting the recurring template entry would mutate all future weeks.
  - *Option B (Audit Cancellation in `scheduled_work`)*: Save an operational override record with `status = "CANCELLED"`, `source = "OVERRIDE"`, and mandatory `override_reason`. Restoring simply deletes this single cancellation row.
- **Cadence & Day-by-Day Storage**:
  - *Option A (Packed bitmask / binary array)*: Compact but error-prone when individual days or multi-week cadences are edited.
  - *Option B (Explicit Day-by-Day Rows)*: Store explicit weekday masks (`MON`..`SUN`, `W1_MON`..`W4_SUN`, `M1_W1_MON`..`M3_W4_SUN`). Each day is independently assignable and never drops other days.

## Decision
- Adopt **Option B (Dedicated Dual Workspaces)**:
  - **Base Planner (`/base-planner`)**: 7-weekday matrix grid (`MON` to `SUN`) by Worksite line item. High-density, recurring master schedule. Enforces contract quota (no excess allowed in blueprint). Mon–Sat auto-fill reliably skips the worker's rest day.
  - **Operational Planner (`/operational-planner`)**: Live daily operations calendar with 7-weekday calendar date grid. Renders base blueprint shifts as low-opacity muted chips (45%), surfaces approved leave gaps as `TO_BE_COVERED` alert slots (amber dashed), and supports operational covers (`OVERRIDE`), compensatory shifts (`DIRECT`), and base shift removals (`REMOVED`).
- Adopt **Option B (Audit Cancellation in `scheduled_work`)**:
  - Base shift removals create an immutable audit record with `status = "CANCELLED"`, `source = "OVERRIDE"`, and mandatory `override_reason`.
  - Grid cell renders cancelled base shifts in bold red (`bg-rose-50 border-rose-300 text-rose-800 line-through`) with `REMOVED` badge and note tooltip.
  - Decrements quota if all staff for that visit are cancelled.
  - Restoring deletes the cancellation record via `DELETE /api/v1/operational-planner/shifts/{id}`, instantly restoring the blueprint.
- Adopt **Option B (Explicit Day-by-Day Rows)**:
  - Base roster templates store explicit `weekday_mask` entries. Multi-week periodic cadences (`W1_MON`..`W4_SUN`, `M1_W1_MON`..`M3_W4_SUN`) are explicitly mapped.
- **Full Period Quota Aggregation**:
  - Monthly (`frequency_unit == "MONTH"`) items aggregate across the entire calendar month.
  - Quarterly (`frequency_unit == "QUARTER"`) items aggregate across the entire 3-month quarter.
- **Roster Usability & Navigation**:
  - Persistent sticky header (`sticky top-0 z-10 bg-slate-100 shadow-sm border-b`) on the Worker Roster table.
  - Real-time worker search, worksite filter dropdown, and supervisor crew grouping toggle.
  - Hours heatmap shading on weekly totals (amber < target, emerald == target, purple > target + OT) and daily cells (sky < 8h, indigo 8h, purple > 8h, slate weekly off, red removed).
  - Admins excluded (`role != 'ADMIN'`).
  - Entity pinning for worksites and workers (`localStorage`).
  - Silent refresh with vertical scroll retention on week navigation.

## Why
- Separating blueprint planning from daily operations mirrors field workforce management reality, preventing accidental corruption of recurring master contracts.
- Storing explicit daily rows prevents overwrite regressions when individual days are edited.
- Explicit cancellation audit trail ensures contract compliance, payroll accuracy, and reversible schedule adjustments.

## Consequences
- Alembic migration `0007_base_op_planner.py` added `base_roster_templates`, `base_roster_entries`, and extended `scheduled_work`.
- Pure domain rules in `backend/src/fw/rules/scheduling/` (`blueprint.py`, `operational.py`, `quotas.py`).
- Frontend routes `/base-planner` and `/operational-planner` provide full planning and operational execution workspaces.
