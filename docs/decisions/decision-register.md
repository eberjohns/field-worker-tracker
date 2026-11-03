# Decision Register (final, v1)

All client questions are answered. **CONFIRMED** = the client decided; **PROPOSED** = our default, built behind a setting and easy to change; **HUMAN** = needs a person outside development (see `../legal/01-human-actions.md`). Answer history: `../reference/client-answers-round-1.md`, `../reference/client-answers-round-2.md`.

| ID | Topic | Final decision | Docs | Status |
|---|---|---|---|---|
| DEC-01 | Overtime | OT rate = basic / 208 x 1.25 (OT1) or x 1.5 (OT2). OT2 = all hours on public holidays and OT2 weekdays (default Sunday, setting). OT1 = hours beyond the worker's **standard hours** (8/10/12 from the salary structure) on normal assigned days, and **all hours** on weekly-off days and days with no assignment. Fixed OT paid as given. OT is reviewed and approved before payment | 03, 05, 06 | CONFIRMED |
| DEC-03 | Break and planned times | Resolved from time rules (employee > team > drivers > company, season, outdoor/indoor); job-item break override; effective-dated | 03, 05, D3, ADR-012 | CONFIRMED |
| DEC-04 | Tracking gaps | Flag only; show unaccounted time = tracking-off minutes inside the shift minus the break | 05 | CONFIRMED |
| DEC-05 | Missing exit | Estimate from last location, mark for review ("Estimated exit") | 05 | CONFIRMED |
| DEC-06 | Salary changes | From the next payroll month; mid-month special cases outside the system | 06 | CONFIRMED |
| DEC-07 | Pay period | Calendar month | 06 | CONFIRMED |
| DEC-09 | Budget-only roles | Company-setting list (pre-filled from job-item staff types); never scheduled or tracked; included in the budget | 03, 04 | CONFIRMED |
| DEC-10 | Reporting links | Links with relationship; several superintendents/engineers, one supervisor; teams = people linked to a manager | 02, 07 | CONFIRMED |
| DEC-11 | Large per-occurrence hours | days = hours / 9 (job unit day) | 04 | CONFIRMED |
| DEC-12 | Midday break and Ramadan hours | Handled by dated time rules (DEC-41); values entered by Admin/Engineers in the system | 03, D3 | CONFIRMED |
| DEC-15 | Worker login | Merged into DEC-53 (employee ID + default password, forced change, device binding) | 02, 09 | CONFIRMED |
| DEC-18 | Country packs | Merged into DEC-34 and DEC-54 | 03, 13 | CONFIRMED |
| DEC-22 | Staff type vocabulary | Controlled list with aliases; suggestions by grade group, exact staff type first (DEC-52) | 04, 11 | CONFIRMED |
| DEC-23 | Job numbers | One number per job in the final template; hyphenated or combined numbers are rejected on import | 03, 11 | CONFIRMED |
| DEC-26 | Document types for Saudi Arabia | Add national ID / iqama types when Saudi data is loaded | 07 | PROPOSED |
| DEC-13 | Extra event fields | `location_captured_at_utc`, `is_mock_location`, accommodation hint | 05, 09 | PROPOSED |
| DEC-14 | Clock tampering | Batch device clock; skew flags events; times never rewritten | 05, 09 | PROPOSED |
| DEC-16 | Attendance record creation | One per employee/date with assignments or events | 05 | PROPOSED |
| DEC-17 | Status | PRESENT = all assigned sites visited; PARTIAL = some; ABSENT = none | 05, 12 | CONFIRMED |
| DEC-19 | Rounding | Minutes integer; money half-up 2 dp per line | 06 | PROPOSED |
| DEC-21 | Weekly off | Per worker, else company default **Sunday** (setting); skipping only where defined | 03, 04 | CONFIRMED |
| DEC-24 | Minimum time at site | Setting (default 10 min) for a visit to count | 05 | CONFIRMED |
| DEC-25 | WPS / Mudad | Out of scope | 06 | CONFIRMED |
| DEC-27 | Driver break | Deducted from accommodation-to-accommodation time | 05 | PROPOSED |
| DEC-28 | Utilization | Productive / transit / idle split, transit capped at `max_transit_minutes` | 05, 12 | PROPOSED |
| DEC-29 | Job budget | Per contract, for display; from the salary revision file (grade cost incl. its provisions and HR OH) and job items; manual override optional; actual vs pro-rated budget | 06, 12 | CONFIRMED |
| DEC-30 | Deductions | None; net pay = gross pay | 06 | CONFIRMED |
| DEC-31 | Live map | Last known position with age and last contact | 10, 12 | CONFIRMED |
| DEC-32 | Pending visits | Day-close detection; OPEN > EXPLAINED > RESCHEDULED/CLOSED | 05, 12 | PROPOSED |
| DEC-33 | Document types | Visa, Passport, Emirates ID, Labour Card, Driving Licence; validity dates only; Admin alerted | 07, 12 | CONFIRMED |
| DEC-34 | Countries | One rule pack per country; each record carries a country | 03, 13 | CONFIRMED |
| DEC-35 | Effective-dated configuration | Settings and time rules resolved as of the work date | 03, ADR-008, ADR-012 | CONFIRMED |
| DEC-36 | Permanent vs Remote | PERMANENT: only that job that day; REMOTE: several while hours remain | 03, 04 | CONFIRMED |
| DEC-37 | Revision lookup (budget) | Latest revision containing the grade; partial revisions allowed; grade year suffix ignored | 06 | PROPOSED |
| DEC-38 | Retention | 13 months live, encrypted yearly archive for a fixed period, then deletion; payroll/attendance 7 years. Client wants "forever" | 14, legal | HUMAN |
| DEC-39 | Provisions | Actual: five provisions from company settings, one value for everyone, plus calculated gratuity and leave salary; budget: the revision file's own provisions | 06 | CONFIRMED |
| DEC-40 | Out of scope | Checklists, manual shift confirmation, WPS | 01 | CONFIRMED |
| DEC-41 | Time rules | Five-point planned schedule (accommodation start, first site, break, last site, accommodation end); company default, overridden for a team, drivers or one person, by season and outdoor/indoor; engineers manage within scope | 05, D3, ADR-012 | CONFIRMED |
| DEC-42 | Planner | Yearly standing assignments, weekly roster as main view, allocated hours vs standard hours in a side panel, markers for skipped/off/leave/to-be-covered | 04, D1 | CONFIRMED |
| DEC-43 | Approvals | Engineer approves leave, temporary reassignments (3 days notice) and attendance rows with variation, flags or overtime; clean rows are automatic | 04, 05, D2 | CONFIRMED |
| DEC-44 | Transport | Drivers section: vehicles and daily runs (driver, ordered stops, passengers) synced to the driver and the workers | D5 | CONFIRMED |
| DEC-45 | Month-end | Auto draft 5 days after month-end (setting); Admin re-runs and approves; later events ignored; abnormal cases outside the system | 06, D4 | CONFIRMED |
| DEC-46 | Reports history | Month-end reports auto-generated and every file kept, named `<Company>_<Report>_<Country>_<Period>_generated-<date>.xlsx`; leave taken is counted, no balances | 12, D4 | CONFIRMED |
| DEC-47 | Report visibility | Operational reports: Admin, Engineers, Superintendents, Supervisors; salary/cost reports: Admin and Engineers | 12 | CONFIRMED |
| DEC-48 | Budget-only list | (see DEC-09) | 03 | CONFIRMED |
| DEC-49 | Who is measured how | Everyone by site visits; only drivers accommodation-to-accommodation; no-accommodation workers have n/a accommodation columns | 05 | CONFIRMED |
| DEC-50 | Product name | Field Worker Tracker (FWT) | all | CONFIRMED |
| DEC-51 | Import rules | Admin only; preview with new/updated (old->new)/unchanged/clashes; blank keeps, `_` clears; no deletion, deactivate used records; keys editable on screen, not by import | 11, D6 | CONFIRMED |
| DEC-52 | Suggestions | Same grade group first-class eligible, exact staff type first | 04 | CONFIRMED |
| DEC-53 | Accounts | Username = worker ID; one default password for all (setting), forced change at first login, lock after `default_password_max_days`, Admin-only reset, workers bound to first device | 02, 09 | CONFIRMED |
| DEC-54 | Saudi Arabia | Separate stack inside the Kingdom when Saudi goes live; UAE stack stays; ADR-009 | 13, ADR-009 | HUMAN |
| DEC-55 | Hosting | Azure UAE North + UAE Central, managed PostgreSQL/PostGIS, quarterly restore drills; off-region copy only if counsel agrees | 14, ADR-009 | CONFIRMED (direction) |
| DEC-56 | Legal | Worker notice, DPIA, inventory, breach runbook drafted; counsel review, contract clause, DPAs, incident owner outstanding | legal/ | HUMAN |
