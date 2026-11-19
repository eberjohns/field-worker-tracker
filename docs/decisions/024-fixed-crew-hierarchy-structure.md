# 024 - Fixed Crew Hierarchy Structure and Transitive Leadership Inheritance
Status: Accepted  
Date: 2026-11-19  

## Context
In early phases, employee reporting lines permitted arbitrary links across roles. In operational field deployment, the client confirmed (DEC-10, Owner confirmation 19 Nov 2026) that field workforce management follows a strict crew structure:
1. Every field WORKER belongs to a crew led by exactly one SUPERVISOR (manager role must be `SUPERVISOR`).
2. Leadership roles (`SUPERINTENDENT` and `ENGINEER`) attach only to supervisors, not directly to individual workers.
3. Field workers inherit their supervisor's superintendents and engineers transitively for scope (ADR-011), approval routing (leave requests, temporary reassignments, attendance review), live map filtering, and report access.
4. Historical reporting lines must never be permanently deleted from the database (Golden Rule 5).

## Options considered
1. **Unrestricted direct links:** Allow arbitrary links from workers to superintendents and engineers. Rejected: causes duplicated assignments, conflicting approval authorities, and inconsistency with the physical crew operational model.
2. **Fixed crew structure with transitive leadership inheritance:** Workers link strictly to one supervisor. Superintendents and engineers attach only to supervisors. Workers inherit upper management transitively. Reporting lines support soft-deactivation (`is_active = false`) rather than hard deletion.

## Decision
- Enforce pure validation rules in `fw.rules.hierarchy`:
  - `WORKER_DIRECT_LINK_NOT_ALLOWED`: Direct worker links to superintendents or engineers are prohibited.
  - `SUPERVISOR_LINK_ROLE_MISMATCH`: A supervisor reporting line requires the manager to have role `SUPERVISOR`.
  - `INVALID_LINK_SUBJECT`: Superintendent and engineer links attach only to supervisors.
  - `HIERARCHY_ROLE_MISMATCH`: Managers in superintendent/engineer links must match the corresponding role.
- Soft-deactivation on `employee_reporting_lines`: added `is_active` (boolean, default true), `deactivated_at` (timestamptz), and `deactivated_by` (UUID). Replaced uniqueness constraints with partial unique indexes filtering `WHERE is_active = true`.
- Deletion operations (`remove_reporting_line`) now perform soft-deactivation and log `DEACTIVATE_REPORTING_LINE` in the audit log.
- Admin hierarchy audit endpoints: `GET /api/v1/employees/hierarchy-violations` detects existing non-conforming links, with `.xlsx` export and actions to "Move to supervisor" or "Deactivate".
- Transitive scope resolution (`compute_transitive_scope`) and all operational queries (approvals, live map, attendance review, scheduling) filter active links and naturally cover workers through their supervisor.

## Why
Ensures one single source of truth for crew hierarchy, aligns system behavior with client field management practices, guarantees that pending approvals cleanly re-route via the supervisor, and preserves auditability without destroying historical records.

## Consequences
- All database queries touching `employee_reporting_lines` must filter `is_active = True`.
- Web UI on `EmployeeDetail` offers only "Supervisor" for workers, and restricts "Superintendent" / "Engineer" relationships to supervisor records.
- Bulk import previews flag non-conforming reporting lines with actionable row errors.
