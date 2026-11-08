# 016 - Leave Management, Temporary Reassignments, and Approvals Inbox

Status: Accepted  
Date: 2026-11-08  

## Context
Phase 06 establishes leave recording, temporary workforce reassignments, and the approvals inbox.
Key architectural requirements from client specifications and the decision register (DEC-43, DEC-46):
1. **Notice Period**: Temporary reassignments must be submitted at least 3 days in advance (calendar days ahead of `date_from`). Requests under 3 days must be refused across all roles (including Admin).
2. **Dual-Workspace Operational Integrity**: The master recurring blueprint in `base_roster_templates` must remain immutable. Approved operational changes (replacements, moves, additions, cancellations) must materialize into `scheduled_work` as single-day override exceptions (`origin = 'EXCEPTION'`, `source = 'OVERRIDE'`) while preserving original records with `status = 'REASSIGNED'` or `'CANCELLED'`.
3. **Leave Gaps and Cover Alerts**: Approved leaves automatically surface `TO_BE_COVERED` slots on operational coverage grids and generate `COVER_NEEDED` alerts for supervisors and engineers. Approving a cover reassignment automatically resolves the alert.
4. **Late Approvals**: If an approval is executed $< 3$ days before `date_from`, the operation is permitted but tagged `LATE_APPROVAL` for audit transparency.
5. **Leave Taken Accounting**: Per DEC-46, leave is accounted as working days taken (excluding weekly rest days and public holidays) alongside calendar days, with no accrual balances tracked in this system.
6. **Unified Approvals Inbox**: Dedicated inbox (`/approvals`) scoped to Engineer reporting lines (Admin sees all), with mandatory rejection reasons and counts.

## Options considered
- **Event-Driven Decoupling vs Direct Cross-Module Invocations**:
  - *Option A (Direct Service Calls)*: `SchedulingService` calls `NotificationService` directly. Violates modular monolith layers contract since `scheduling` (Layer 94) cannot import `notifications` (Layer 93).
  - *Option B (Domain Events via Core Event Bus)*: `SchedulingService` publishes `LeaveApprovedEvent`, `LeaveCancelledEvent`, and `ReassignmentApprovedEvent` on `core.event_bus`. `NotificationService` registers synchronous event handlers, maintaining strict acyclic layer boundaries.
- **Leave Taken Calculation**:
  - *Option A (Calendar days only)*: Miscounts rest days and public holidays as work absence.
  - *Option B (Working Days with Calendar Days Display)*: Exclude worker's configured weekly off day (`weekly_off_day`) and country public holidays (`public_holidays`), showing `working_days` alongside total `calendar_days`.
- **Standalone Leave Import**:
  - *Option A (Fold into general Phase 03 import)*: Complicates monthly imports.
  - *Option B (Standalone Excel Import)*: Admin-only endpoint `POST /api/v1/leave-requests/import` with downloadable template `GET /api/v1/leave-requests/template`.

## Decision
- Adopt **Option B (Domain Events via Core Event Bus)**:
  - Modules publish typed domain events (`LeaveApprovedEvent`, `LeaveCancelledEvent`, `ReassignmentApprovedEvent`). The notifications module listens synchronously to create/resolve alerts without violating import layers.
- Adopt **Strict 3-Day Notice Enforcement**:
  - Non-negotiable notice validation rule in `backend/src/fw/rules/scheduling/reassignment.py`. Requests with `date_from - today < 3` return HTTP 400.
- Adopt **Audited Operational Materialization**:
  - Reassignment approvals generate `ScheduledWork` rows with `source = 'OVERRIDE'`, sequence derived from active daily count, and `reassignment_request_id` set. Originals transition to `REASSIGNED` or `CANCELLED`.
- Adopt **Working Days Leave Accounting**:
  - Leave summary computes working days excluding `weekly_off_day` and public holidays. Calendar days are provided alongside.
- Adopt **Standalone Leave Import & Approvals Views**:
  - Standalone leave Excel import (`/api/v1/leave-requests/import` & `/template`).
  - Frontend routes `/approvals` (tabs: Leave, Reassignments, Attendance placeholder) and `/leave` (summary, history, record modal, import modal).

## Why
- Preserves clean modular monolith architecture and satisfies import-linter contracts.
- Guarantees complete audit traceability between leave requests, cover reassignments, and operational roster rows.
- Eliminates scheduling collisions and prevents unauthorized short-notice staff reallocations.

## Consequences
- Alembic migration `0008_leave_reassignment_approvals.py` adds `leave_requests`, `reassignment_requests`, `alerts`, and extends `scheduled_work`.
- Domain events exported from `fw.modules.scheduling`.
- New UI routes `/approvals` and `/leave` integrated into `Shell.tsx` navigation with dynamic badge indicators.

