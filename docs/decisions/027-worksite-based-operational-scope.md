# 027 - Worksite-based operational scope
Status: Accepted (amends the scoping part of ADR-026)
Date: 2026-11-20

## Context
ADR-026 added `worksite_supervisors` but applied it unevenly. Only the worksite list and the Employees list used it, and the Employees list did so through SQL pasted into two routes. Detail pages, attendance, the live map, pending visits, reports and the dashboard still used the crew chain only. Worksite detail had no scope check at all. Nothing created `worksite_supervisors` rows, so every non-admin saw an empty Worksites page and an empty planner.

The client clarified the rule at the meeting of 19 Nov 2026 (item 3), and the owner confirmed the details on 20 Nov 2026:
- Supervisors see their assigned worksites. Superintendents and Engineers see the worksites assigned to supervisors in their scope.
- A supervisor's own crew is visible on Employees, Leave and their own requests. Attendance and live position on another supervisor's site belong to that site's supervisor.
- Workers from another crew on my site are read-only: I can view and comment, and decisions stay with the crew chain (DEC-10).
- Reassignment destinations list every active worksite, because a supervisor moves their own crew onto other supervisors' sites.

## Options considered
1. **Keep per-route filters**: rejected. This is how the inconsistency arose.
2. **Precompute one employee ID set per user**: rejected. Operational views depend on the date (who works on my site *that day*), so one set cannot answer both "this week's roster" and "last month's attendance".
3. **One scope object with a purpose and a date**: chosen.

## Decision
- A pure rule in `fw/rules/scope.py` (`employee_access(role, purpose, in_crew, on_my_sites)`) returns FULL, READ_ONLY or hidden for the three purposes DIRECTORY, REQUESTS and OPERATIONS.
- `fw.modules.scheduling.AccessScope` resolves a user once (crew IDs and worksite IDs). It gives every route the same filters:
  - `worksite_filter` and `can_view_worksite` for worksites;
  - `directory_ids` and `request_ids` for Employees, Leave and Reassignments;
  - the **site-day rule** (`operations_clause`, `operations_access`, `operations_ids_on`, `site_days`) for anything with a work date: an employee-day is on my sites when there is ACTIVE or COMPLETED scheduled work on one of my worksites that day;
  - `worksite_row_clause` for rows that belong to one worksite (pending visits);
  - `can_decide` (crew chain) for edits and approvals.
- "On my worksite" for the directory means an active standing assignment today, or scheduled work within ± `scope_site_worker_window_days` (company setting, default 31).
- Responses carry `read_only: true` when the caller sees the employee only through a worksite. The web hides edit and approve controls on those rows, and the server refuses the decision (`READ_ONLY_SCOPE`, 403).
- Ways to create assignments:
  - the `Worksite_Supervisors` import sheet;
  - the per-worksite assign action;
  - the Admin action "Assign supervisors from current crews", where the server proposes, Admin reviews and nothing is assigned silently.

  Admin sees an "Unassigned worksites" count and filter.
- An assignment ends automatically when its supervisor is deactivated or stops being a SUPERVISOR (audited `REMOVE_WORKSITE_SUPERVISOR`, `automatic: true`).

## Why
- One rule in one place, tested as a pure function, keeps lists, detail pages, exports and reports in agreement.
- The site-day rule follows the client's wording: the site's supervisor owns that day.
- Read-only visibility lets supervisors see who works on their site without breaking DEC-10 approval routing.

## Consequences
- A worksite with no supervisor is visible only to Admin until someone assigns one, which is why the dashboard warning exists.
- Report rules per handler (also in `docs/12-reports.md` section 1):
  - site-day: Daily Attendance, Monthly Attendance, Late/Early Departure, Employee Utilization, Transportation Time, Site Visits, Employee Movement, Project Attendance Summary (also limited to my worksites), Weekly Roster (per cell);
  - worksite rows: Pending Visits;
  - Staffing Gaps: crew, or scheduled on my worksites during the leave;
  - crew: Document Expiry;
  - Admin only: Payroll, Provisions & Staff Cost, Job Costing.
- There is no mobile contract change.
- Related: ADR-011 (transitive scope), ADR-024 (crew hierarchy), ADR-026, DEC-10, DEC-57.
