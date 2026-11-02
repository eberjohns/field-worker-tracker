# 03 - Business Rules

Rule IDs (BR-...) can be cited in code comments and PRs. Rules marked **[DEC-nn]** depend on a decision in `decisions/decision-register.md` and must be implemented behind a setting.
Detailed algorithms live in docs 04, 05 and 06.

## 1. Conventions
- **BR-CV-01** All instants are stored in UTC. The **work date** is the local calendar date in the site's country time zone (`Asia/Dubai` AE, `Asia/Riyadh` SA). Shifts crossing local midnight are out of scope for v1: flag `CROSSES_MIDNIGHT` for review.
- **BR-CV-02** Durations are whole minutes. **Variation = Actual - Planned**; negative means shortfall. Use this signed convention everywhere.
- **BR-CV-03** Money is `numeric(14,2)`, rounded half-up at the line level. Rates may keep more precision internally (e.g. hourly rate to 6 dp) but displayed and stored amounts are 2 dp.
- **BR-CV-04** `is_active=false` replaces deletion for referenced records. Only Admin may hard-delete, and only if nothing references the record.
- **BR-CV-05** Every state change is audited (actor, action, entity, safe diff, reason, UTC time).
- **BR-CV-06** Editable records have a `version` integer. Updates must send the version; a mismatch returns `409`.

## 2. Employees and hierarchy
- **BR-EM-01** Tally ID is the business key, unique, text. Names are never relationship keys.
- **BR-EM-02** Operational **role** is separate from **Grade Code** and **Staff Grade Description**.
- **BR-EM-03** Grade Code selects the salary line. SGD matches workers to Job Items. There is no mapping table between them.
- **BR-EM-04** SGD values come from a controlled list with an alias table (`Gardner Helper` -> `Gardener Helper`). Unknown values import as warnings and require review.
- **BR-EM-05** Reporting lines are links `(employee, manager, relationship)`. A person may have **several superintendents and several engineers** and at most one supervisor. Scope is the union of all links **[DEC-10]**.
- **BR-EM-06** Hierarchy validation: no self-link; no cycles; managers must exist and be active; at most one SUPERVISOR per employee.
- **BR-EM-07** Changing an employee's Grade Code records a history row (old, new, who, when, reason, effective date).
- **BR-EM-08** `is_driver` marks drivers. A driver's work time runs from accommodation departure to accommodation return and their transit counts as productive.
- **BR-EM-09** Weekly off day: each employee can have their own; if blank, the country's default weekly off day setting applies **[DEC-21]**.
- **BR-EM-10** Bulk update is allowed for accommodation, break minutes and weekly off day, in scope, with one audit entry per employee.
- **BR-EM-11** Every employee, worksite and salary revision carries a **country** (AE or SA). The country decides the rule pack, holidays, currency and salary scale used for that record **[DEC-34]**.

## 3. Worksites and Job Items
- **BR-JB-01** One Worksite = one job number = one boundary. Format: 2 digits + letter (A outdoor, B indoor, C water feature) + 5 digits, one number per record, no hyphens or combined numbers. `is_outdoor` is an explicit Y/N on the worksite.
- **BR-JB-02** All Job Items of a Worksite share its boundary. A Job Item is unique by (worksite, sub_item_code).
- **BR-JB-03** `staff_grade_description` is required on a Job Item and must be in the controlled list.
- **BR-JB-04** Frequency is structured: `frequency_unit` (WEEK/MONTH/QUARTER/YEAR) x `occurrences_per_period` x `period_interval`. Free-text frequencies are normalized at import (see 11).
- **BR-JB-05** `hours_per_occurrence_per_staff` is the time **each** worker must give per occurrence. It is never divided among workers. Example: 3 workers x 9 h = 27 man-hours.
- **BR-JB-06** Expected activities and annual hours are **calculated by the system** from the structured frequency (6 per week = 6 x 52, monthly = 12, quarterly = 4, 3 per year = 3). Figures declared by the client are optional and informational; a difference is shown as info and the calculated value is used.
- **BR-JB-07** Staff types listed in the company setting **budget-only staff types** (HSE Engineer, Project Manager, Irrigation Engineer...) exist only for the budget: never scheduled, never tracked. The list is pre-filled with the distinct staff types found in job items **[DEC-09, DEC-48]**.
- **BR-JB-08** Renewal reference (R1, R2) is a label. It never selects a salary revision.
- **BR-JB-09** The boundary is set after import through the map UI. A Worksite without a boundary cannot be synced to phones and shows a "no boundary" warning in the scheduler.
- **BR-JB-10** Group and Zone are normalized entities linked by code.
- **BR-JB-11** `deployment_type`: **PERMANENT** = a worker assigned to this job on a day does only this job that day (no other assignment may be added that day); **REMOTE** = a worker can take several jobs in a day while assigned hours do not exceed the day's capacity **[DEC-36]**.
- **BR-JB-12** Suggestions: workers whose **grade group** (G1 to G7) equals the job item's planned grade group are eligible, exact staff type first. Empty list = neutral message. Assignment is done in the system **[DEC-52]**.

## 4. Scheduling (summary - see 04)
- **BR-SC-01** Occurrences are generated from frequency and the active period; low-frequency occurrences get their dates assigned manually.
- **BR-SC-02** Suggestions match on Staff Grade Description only and come only from employees who hold it. A user confirms assignments.
- **BR-SC-03** A worker may have several assignments per day, each with its own sequence and hours. The scheduler shows total assigned hours, not elapsed time.
- **BR-SC-04** Temporary reassignment: requested by Supervisors, Superintendents, Engineers or Admin **at least `reassignment_min_notice_days` (3) days ahead** and **approved by an Engineer** before it takes effect (Admin/Engineer requests can be self-approved). Original assignments are preserved **[DEC-43]**.
- **BR-SC-05** Leave: the supervisor records the request, an Engineer approves; approved leave blocks assignment and marks affected slots TO BE COVERED. Leave never changes pay; the system counts leave taken **[DEC-46]**.
- **BR-SC-06** Server-side validation rejects duplicates and hard conflicts, and warns on soft ones.
- **BR-SC-07** Planning is a yearly plan of **standing assignments** viewed as a weekly **roster**; assigned hours are shown against each worker's standard hours **[DEC-42]**.
- **BR-SC-08** Public holidays: jobs are skipped and shown as skipped. Weekly off and leave apply only where they exist. Uncovered slots are marked TO BE COVERED (no automatic relief).

## 5. Events and attendance (summary - see 05)
- **BR-AT-01** Raw events are immutable. The server never edits event time or location.
- **BR-AT-02** The server verifies each ENTRY/EXIT/PING against the stored polygons with PostGIS. The device's claim is stored; the **server verdict** drives attendance.
- **BR-AT-03** Regular worker: `worked = (last site exit - first site entry) - effective break`. Inter-site travel stays inside the interval. Accommodation commute is excluded.
- **BR-AT-04** Driver: `worked = accommodation return - accommodation departure`.
- **BR-AT-05** Grace: if shortfall <= grace minutes the requirement counts as satisfied; actual time and shortfall are unchanged and `grace_applied` is recorded.
- **BR-AT-06** Planned times and break come from the most specific **time rule** in force on the work date: employee, then team (supervisor/superintendent/engineer link), then drivers, then company, with a narrower `applies_to` (outdoor/indoor) winning over ALL; a job item's `break_override_minutes` (first site of the day) replaces the break. The value used and its source are saved with each calculation **[DEC-03, DEC-41]**.
- **BR-AT-07** Business status: PRESENT / PARTIAL / ABSENT. Review status: AUTO / PENDING_REVIEW / APPROVED / REJECTED (returned for correction). They are separate fields.
- **BR-AT-08** A tracking gap is recorded and flagged; it never changes worked time automatically. The report shows **unaccounted time** = tracking-off minutes inside the shift span minus the break minutes used, so location off during the break is not penalised **[DEC-04]**.
- **BR-AT-09** Any recalculation creates a new immutable calculation version; approvals point to the version they approved.
- **BR-AT-10** Inferred information (exit inferred from last ping, interpolated movement) is always labelled INFERRED **[DEC-05]**.
- **BR-AT-11** Comment types: EXPLANATION, OVERTIME_JUSTIFICATION, ATTENDANCE_CORRECTION, DISCIPLINARY_NOTE, PENDING_VISIT_EXPLANATION, OPERATIONAL, REVIEW_NOTE **[DEC-33]**. Comments never change events or master data.
- **BR-AT-12** Each calculation also stores the movement split: shift span, productive, transit and idle minutes (see 05 section 6b) **[DEC-28]**.
- **BR-AT-13** The planned schedule has five points: accommodation start, first-site start, break, last-site end, accommodation end. Planned total time = accommodation end - accommodation start; planned worked time = last-site end - first-site start - break **[DEC-41]**.
- **BR-AT-14** Supervisors, superintendents and engineers are tracked by **site visits** like workers. Only **drivers** use accommodation-to-accommodation time **[DEC-49]**.
- **BR-AT-15** Only rows with a variation beyond grace, a review flag, or overtime need review; the Engineer approves those. Clean rows are automatic **[DEC-43]**.
- **BR-AT-16** Workers without company accommodation have no accommodation times; planned and actual accommodation columns show n/a and total time = first site to last site.

## 6. Payroll and cost (summary - see 06)
- **BR-PY-01** Pay comes from the worker's own **salary structure** (effective-dated; changes apply from the next month). Grade code is not used for pay. Grade revisions are for the job budget only **[DEC-06, DEC-37]**.
- **BR-PY-02** Gratuity = Basic / 365 x 30. Leave salary = Basic / 12.
- **BR-PY-03** Provisions (actual) = visa + air ticket + uniform + accommodation + medical from company settings (one value for everyone) plus gratuity (basic/365 x 30) and leave salary (basic/12), calculated for everyone. Transportation is not a provision **[DEC-39]**.
- **BR-PY-04** Gross pay = salary portion + OT. Total staff cost = gross pay + per-month provision. HR OH (5%) is added: **final total staff cost = total staff cost + HR OH**.
- **BR-PY-05** OT hourly rate = basic / 208 x multiplier (1.25, 1.5; settings). **OT2 (1.5)** = all hours on public holidays and on the OT2 weekdays (default Sunday; setting). **OT1 (1.25)** = hours beyond the worker's **standard hours** on normal assigned days, and **all hours** on a weekly off day or a day with no assignment. Fixed OT is paid as given. Overtime is reviewed and approved before it is paid **[DEC-01]**.
- **BR-PY-06** Insufficient hours raise alerts/review. They never reduce salary automatically.
- **BR-PY-07** Employee payroll and employer cost are shown separately. Provisions are employer cost, not cash to the employee.
- **BR-PY-08** Finalized payroll is an immutable snapshot.
- **BR-PY-09** No deductions in v1: net pay equals gross pay. The `net_pay` field exists so deductions can be added later **[DEC-30]**.
- **BR-PY-10** Month-end: `payroll_auto_run_delay_days` (5) after month-end the system creates a **draft** payroll and the month-end reports; Admin re-runs as needed and **approves**; events uploaded after approval are ignored for that month; abnormal cases are handled outside the system **[DEC-45]**.
- **BR-PY-11** The job budget uses the salary revision file (grade cost with its own provisions) and the job items; it is for display and comparison only **[DEC-29]**.

## 7. Settings and overrides
- **BR-ST-01** Schedule/break values resolve by precedence employee, then team (supervisor's team), then the country's value, then the global value, **as of the work date**. Overrides have effective date ranges.
- **BR-ST-02** Changing a setting never rewrites finalized attendance or payroll.
- **BR-ST-03** Public holidays are organization-wide per country.
- **BR-ST-04** All settings, time rules and overrides are **effective-dated**. Attendance for a date is always judged by the values in force on that date, including when it is recalculated later **[DEC-35]**.
- **BR-ST-05** **Work-period rules** (Ramadan, summer midday break, any seasonal rule) apply between two dates, per country, to all jobs or outdoor jobs only. They can change the day's working minutes, the break, and/or define a blocked window that counts as break. The scheduler's daily capacity and attendance's required time follow them **[DEC-35]**.

## 8. Countries
Each employee, worksite, salary revision, public holiday and country-scoped setting carries a **country** (AE or SA). A **Country Rule Pack** supplies defaults for a country: rest days, OT2 weekdays, time zone, currency, gratuity formula, holiday source and time-rule templates. The pack is chosen by the record's country (the site's for scheduling and attendance, the employee's for payroll); engines never branch on country. **Each country runs as its own stack** (ADR-009): the UAE stack first, a separate Saudi stack inside the Kingdom when Saudi goes live, same code and images **[DEC-34, DEC-54]**.

## 9. Reports, monitoring and follow-up
- **BR-RP-01** Every report exports to Excel (XLSX); CSV also offered; PDF for daily attendance and the payroll sheet. Reports are scope-restricted and traceable to source records (see 12).
- **BR-RP-02** Utilization splits the shift into productive, transit and idle minutes. Transit = time between leaving one polygon and entering the next, up to `max_transit_minutes`; longer intervals count as off-site idle. Transit/idle are INFERRED. Drivers' transit counts as productive **[DEC-28]**.
- **BR-RP-03** Job costing compares actual allocated cost with the contract budget calculated from the salary revision file and job items (manual override optional). Variance = actual - budget **[DEC-29]**.
- **BR-RP-04** Live monitoring shows the last known verified position per worker with its **age** (event time) and the device's last contact. ACTIVE = accepted event within `live_active_window_minutes` and tracking not disabled; OFFLINE = scheduled today but otherwise. Late-uploaded events never overwrite a newer position **[DEC-31]**.
- **BR-RP-05** A pending visit is an ACTIVE assignment whose day closed without a counted visit (or an occurrence window that ended unmet). Follow-up status: OPEN, EXPLAINED, RESCHEDULED, CLOSED. Engineers manage it; Supervisors explain **[DEC-32]**.
- **BR-RP-06** Alerts: `TRACKING_INTERRUPTED` on an accepted LOCATION_DISABLED event (to in-scope Supervisors/Engineers), `PENDING_VISIT` reminders while OPEN, `DOC_EXPIRY` to Admin/HR. Shift-start reminders and arrival/departure confirmations on the worker's phone are app-side.
- **BR-RP-07** Month-end reports are generated automatically and every generated file is kept in the **Generated reports** section, named `<Company>_<Report>_<Country>_<Period>_generated-<date>.xlsx`; all copies stay downloadable **[DEC-46]**.
- **BR-RP-08** Operational reports are visible to Admin, Engineers, Superintendents and Supervisors in scope; salary and cost reports to Admin and Engineers only **[DEC-47]**.

## 10. Settings catalog
Effective-dated values in `company_setting_values` (country-scoped where noted).

| Key | Default | Unit | Source |
|---|---|---|---|
| `currency` | AED (AE) / SAR (SA) | - | proposed |
| `default_weekly_off_day` | SUNDAY | - | from client schedule |
| `ot2_weekdays` | SUNDAY | list | client |
| `standard_ot_divisor_hours` | 208 | h | client |
| `ot1_multiplier` / `ot2_multiplier` | 1.25 / 1.5 | x | client |
| `hr_overhead_rate` | 0.05 | fraction | client |
| `provision_visa` / `air_ticket` / `uniform` / `accommodation` / `medical` | 132 / 65 / 30 / 550 / 65 | per month | client salary file |
| `gratuity_days_per_year` | 30 | days | client |
| `leave_salary_divisor` | 12 | - | client |
| `standard_hours_default` | 8 | h | proposed (used when a worker has none) |
| `planned_workday_hours` | 9 | h | job unit day for splitting job hours |
| `grace_period_minutes` | 10 | min | client |
| `min_visit_minutes` | 10 | min | client (a minimum time at site) |
| `gap_flag_minutes` | 15 | min | proposed |
| `max_transit_minutes` | 90 | min | proposed |
| `reassignment_min_notice_days` | 3 | days | client |
| `payroll_auto_run_delay_days` | 5 | days | client |
| `alarm_lead_minutes` | 30 | min | proposed (alarm = planned accommodation start - lead) |
| `geofence_circle_radius_m` | 300 | m | proposed |
| `approach_polling_interval_s` / `confirmation_polling_interval_s` | 60 / 300 | s | proposed |
| `schedule_sync_window_days` | 30 | days | client |
| `document_expiry_lead_days` | 30 | days | proposed |
| `live_active_window_minutes` | 15 | min | proposed |
| `pending_visit_reminder_hours` / `day_close_delay_minutes` | 24 / 120 | h / min | proposed |
| `occurrence_horizon_months` | 13 | months | proposed |
| `default_password_max_days` | 7 | days | proposed (lock if default not changed) |
| `budget_only_staff_types` | list | - | chosen by Admin from the staff types found in job items |
| `max_location_accuracy_m`, `clock_skew_tolerance_s`, `event_future_tolerance_s`, `event_max_age_days`, `no_activity_alert_after_minutes`, `stale_device_hours`, `location_policy_version` | 100, 120, 300, 7, 60, 24, 1 | - | proposed |
The default password itself is entered in the system by Admin (never in a file). Planned times and seasons live in **time rules** (`design/D3-time-rules-and-attendance-report.md`).

Notes: `provision_*` values are **defaults** used when a salary-revision line leaves that provision blank (per-grade values win). Country-specific settings (currency, default weekly off day, provisions, gratuity) are stored per country. Every value is effective-dated; changing one adds a new row with a start date.
