# Decision Register (final, v1)

All client questions are answered. **CONFIRMED** = the client decided; **PROPOSED** = our default, built behind a setting and easy to change; **HUMAN** = needs a person outside development (see `../legal/01-human-actions.md`). Answer history: `../reference/client-answers-round-1.md`, `../reference/client-answers-round-2.md`.

| ID | Topic | Final decision | Docs | Status |
|---|---|---|---|---|
| DEC-01 | Overtime | OT rate = basic / 208 x 1.25 (OT1) or x 1.5 (OT2). OT2 = all hours worked on public holidays and worker's own weekly off day, nothing else. OT1 = hours beyond standard hours on normal working days, and all hours on an unassigned non-off day. Sunday hardcoding removed; missing weekly off flags NO_WEEKLY_OFF_DAY. Fixed OT paid as given. OT is reviewed and approved before payment (Owner confirmation 19 Nov 2026) | 03, 05, 06, ADR-018, ADR-020, ADR-025 | CONFIRMED |
| DEC-03 | Break and planned times | Break hierarchy (lowest to highest): company default (`default_break_minutes`) -> seasonal/effective time rule -> crew break stored in `employee_salary.break_minutes`. Crew break set on supervisor propagates to linked workers' salary structure. Attendance resolves salary break (>0) -> time rule -> company default. Job-item break override is display only and never affects calculation (Owner confirmation 19 Nov 2026) | 03, 05, D3, ADR-012 | CONFIRMED |
| DEC-04 | Tracking gaps | Flag only; show unaccounted time = tracking-off minutes inside the shift minus the break | 05, ADR-018 | CONFIRMED |
| DEC-05 | Missing exit | Estimate from last location, mark for review ("Estimated exit") | 05, ADR-018 | CONFIRMED |
| DEC-06 | Salary changes | From the next payroll month; mid-month special cases outside the system | 06 | CONFIRMED |
| DEC-07 | Pay period | Calendar month | 06 | CONFIRMED |
| DEC-09 | Budget-only roles | Company-setting list (pre-filled from job-item staff types); never scheduled or tracked; included in the budget | 03, 04 | CONFIRMED |
| DEC-10 | Reporting links | Fixed crew structure: a WORKER has exactly 1 supervisor (role SUPERVISOR). Superintendents and Engineers attach ONLY to supervisors. Workers inherit superintendents and engineers transitively for scope and approvals. Direct worker links to superintendents/engineers not allowed. Deactivation with audit log, never hard delete (Owner confirmation 19 Nov 2026) | 02, 07, ADR-011, ADR-024 | CONFIRMED |
| DEC-11 | Large per-occurrence hours | days = hours / 9 (job unit day) | 04 | CONFIRMED |
| DEC-12 | Midday break and Ramadan hours | Handled by dated time rules (DEC-41); values entered by Admin/Engineers in the system | 03, D3 | CONFIRMED |
| DEC-15 | Worker login | Merged into DEC-53 (employee ID + default password, forced change, device binding) | 02, 09 | CONFIRMED |
| DEC-18 | Country packs | Merged into DEC-34 and DEC-54 | 03, 13 | CONFIRMED |
| DEC-22 | Staff type vocabulary | Controlled list with aliases; suggestions by grade group, exact staff type first (DEC-52) | 04, 11 | CONFIRMED |
| DEC-23 | Job numbers | One number per job in the final template; hyphenated or combined numbers are rejected on import | 03, 11 | CONFIRMED |
| DEC-26 | Document types for Saudi Arabia | Add national ID / iqama types when Saudi data is loaded | 07 | PROPOSED |
| DEC-13 | Extra event fields | `location_captured_at_utc`, `is_mock_location`, accommodation hint | 05, 09, ADR-018 | PROPOSED |
| DEC-14 | Clock tampering | Batch device clock; skew flags events; times never rewritten; append-only trigger | 05, 09, ADR-018 | PROPOSED |
| DEC-16 | Attendance record creation | One per employee/date with assignments or events | 05, ADR-018 | PROPOSED |
| DEC-17 | Status | PRESENT = all assigned sites visited; PARTIAL = some; ABSENT = none | 05, 12, ADR-018 | CONFIRMED |
| DEC-19 | Rounding | Minutes integer; money half-up 2 dp per line | 06 | PROPOSED |
| DEC-21 | Weekly off | Worker's own weekly off day (stored in employee.weekly_off_day). Missing weekly_off_day does not default to Sunday; raises NO_WEEKLY_OFF_DAY flag (Owner confirmation 19 Nov 2026) | 03, 04, 05, ADR-025 | CONFIRMED |
| DEC-24 | Minimum time at site | Setting (default 10 min) for a visit to count | 05, ADR-018 | CONFIRMED |
| DEC-25 | WPS / Mudad | Out of scope | 06 | CONFIRMED |
| DEC-27 | Driver break | Deducted from accommodation-to-accommodation time | 05, ADR-018 | PROPOSED |
| DEC-28 | Utilization | Productive / transit / idle split, transit capped at `max_transit_minutes` | 05, 12, ADR-018 | PROPOSED |
| DEC-29 | Job budget | Per contract, dynamic from assigned revision code (fallback country active revision) and job items; manual override optional; actual vs pro-rated budget | 06, 12, ADR-020 | CONFIRMED |
| DEC-30 | Deductions | Missed hours (unpaid leave + shortfall) deducted via `missed_hours * (basic / 208)`; paid leaves incur 0 deduction; net pay = gross pay minus missed deductions (Owner confirmation 19 Nov 2026) | 06, ADR-020 | CONFIRMED |
| DEC-31 | Live map | Last known position with age and last contact | 10, 12, ADR-018 | CONFIRMED |
| DEC-32 | Pending visits | Day-close detection; OPEN > EXPLAINED > RESCHEDULED/CLOSED | 05, 12, ADR-018 | PROPOSED |
| DEC-33 | Document types | Visa, Passport, Emirates ID, Labour Card, Driving Licence; validity dates only; Admin alerted | 07, 12 | CONFIRMED |
| DEC-34 | Countries | One rule pack per country; each record carries a country | 03, 13 | CONFIRMED |
| DEC-35 | Effective-dated configuration | Settings and time rules resolved as of the work date | 03, ADR-008, ADR-012 | CONFIRMED |
| DEC-36 | Permanent vs Remote | PERMANENT: only that job that day; REMOTE: several while hours remain | 03, 04, ADR-014 | CONFIRMED |
| DEC-37 | Revision lookup (budget) | Latest revision containing the grade; partial revisions allowed; grade year suffix ignored | 06 | PROPOSED |
| DEC-38 | Retention | 13 months live, encrypted yearly archive for a fixed period, then deletion; payroll/attendance 7 years; AES-256-GCM archive implemented; automatic worker job archives with purge_live_events=False; purging live events stays an explicit manual Admin action until counsel/client confirmation | 14, legal, ADR-022, ADR-025 | HUMAN |
| DEC-39 | Provisions | Actual: five provisions from company settings, one value for everyone, plus calculated gratuity and leave salary, + 5% HR OH; budget: the revision file's own static provisions | 06, ADR-020 | CONFIRMED |
| DEC-40 | Out of scope | Checklists, manual shift confirmation, WPS | 01 | CONFIRMED |
| DEC-41 | Time rules | Five-point planned schedule (accommodation start, first site, break, last site, accommodation end); break resolves salary break -> time rule -> company default; engineers manage within scope (Owner confirmation 19 Nov 2026) | 05, D3, ADR-012 | CONFIRMED |
| DEC-42 | Planner | Yearly standing assignments, weekly roster as main view, allocated hours vs standard hours in a side panel, markers for skipped/off/leave/to-be-covered | 04, D1, ADR-014 | CONFIRMED |
| DEC-43 | Approvals | Engineer approves leave, temporary reassignments (3 days notice) and attendance rows with variation, flags or overtime; clean rows are automatic | 04, 05, D2, ADR-016, ADR-018 | CONFIRMED |
| DEC-44 | Transport | Drivers section and daily vehicle runs omitted by client in later meetings | D5 | DROPPED |
| DEC-45 | Month-end | Auto draft 5 days after month-end (`payroll_auto_run_delay_days`); Admin re-runs (increments run_no) and approves; approval locks attendance and creates immutable snapshots | 06, D4, ADR-020 | CONFIRMED |
| DEC-46 | Reports history | Month-end reports auto-generated and every file kept, named `<Company>_<Report>_<Country>_<Period>_generated-<datetime>.xlsx`; versioned and immutable; re-downloads verified | 12, D4, ADR-021 | CONFIRMED |
| DEC-47 | Report & cost visibility | Operational reports: Admin, Engineers, Superintendents, Supervisors; salary/cost reports, worksite budgets, and price-related figures: strictly ADMIN only (403/masked for other roles) (Owner confirmation 19 Nov 2026, Batch 6) | 12, ADR-021, ADR-026 | CONFIRMED |
| DEC-48 | Budget-only list | (see DEC-09) | 03 | CONFIRMED |
| DEC-49 | Who is measured how | Everyone by site visits; only drivers accommodation-to-accommodation minus break; no-accommodation workers have n/a accommodation columns (Owner confirmation 19 Nov 2026) | 05, ADR-018 | CONFIRMED |
| DEC-50 | Product name | Field Worker Tracker (FWT) | all | CONFIRMED |
| DEC-51 | Import & Export rules | Admin and Engineer only (Batch 6); preview with new/updated (old->new)/unchanged/clashes; blank keeps, `_` clears; no deletion, deactivate used records; keys editable on screen, not by import | 11, D6, ADR-013, ADR-026 | CONFIRMED |
| DEC-52 | Suggestions | Same grade group first-class eligible, exact staff type first | 04, ADR-014 | CONFIRMED |
| DEC-53 | Accounts | Username = worker ID; one default password for all (setting), forced change at first login, lock after `default_password_max_days`, Admin-only reset, workers bound to first device | 02, 09 | CONFIRMED |
| DEC-54 | Saudi Arabia | Separate stack inside the Kingdom when Saudi goes live; UAE stack stays; ADR-009 | 13, ADR-009 | HUMAN |
| DEC-55 | Hosting | Azure UAE North + UAE Central, managed PostgreSQL/PostGIS, quarterly restore drills; automated drill tool verified; ADR-022 | 14, ADR-009, ADR-022 | CONFIRMED |
| DEC-56 | Legal | Worker notice, DPIA, inventory, breach runbook; implemented; awaiting client/counsel review; Runbooks 01-05; ADR-022 | legal/, ADR-022 | HUMAN |
| DEC-57 | Worksite supervisors & scoping | Worksites can have multiple assigned field supervisors; supervisors see only assigned worksites and workers scheduled to their worksite's job items; superintendents/engineers see their subtree; admin sees all | 01, 07, ADR-026 | CONFIRMED |
