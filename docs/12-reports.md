# 12 - Reports, Live Monitoring and Alerts

Sources: the client's *SGS Field Tracker - Inputs and Outputs* document (section 4: Outputs; copy in `reference/`) and the requirements spec (section 15). Where they differ, the difference is recorded in `reference/client-io-document-summary.md` and the decision register.

## 1. Rules for every report
- **Every report exports to Excel (XLSX).** CSV is also offered; PDF only for daily attendance and the payroll sheet. (Client: "All reports can be exported to Excel".)
- Role- and **reporting-scope** restricted (see `02-roles-and-permissions.md`). Supervisors never see salary, provision, payroll or cost reports.
- Filters common to all: date range, group, zone, worksite, supervisor, superintendent, engineer, employee, SGD.
- Figures are **traceable**: each row links to its attendance record, visits and raw events. Inferred values are labelled INFERRED.
- **Generated history**: month-end reports run automatically and **every generated file is kept** in the Generated Reports section (nothing is overwritten; re-generations get a new version). Names: `<Company>_<Report>_<Country>_<Period>_generated-<date>.xlsx`, e.g. `FieldWorkerTracker_Payroll-Cost_AE_2026-10_generated-2026-11-06.xlsx`.
- Reports read **derived tables** (`attendance_records`, `attendance_calculations`, `site_visits`, `pending_visits`, `payroll_records`, `job_cost_allocations`), never raw events. Large exports run as background jobs (`report_exports`).
- Excel exports contain one header row, one row per record, no merged cells, ISO dates, numbers as numbers, and a second sheet "Filters" recording the parameters used.
- Dashboard statistics are derived or cached, never manually edited.

## 2. Traceability: client's list to our reports
The client named ten reports (section 4.1). The requirements spec adds four more, and the weekly roster and driver run sheet are added from their schedule and transport. All sixteen are below.

| # | Client wording (paraphrased intent) | Our key | Notes |
|---|---|---|---|
| 1 | **Daily Attendance Report**: check-in/out, hours worked, status by whether assigned sites were visited (Present = all, Partial = some, Absent = none) | `daily-attendance` | Check-in/out shown both as accommodation departure/return and first-site entry/last-site exit |
| 2 | **Employee Movement Report**: full daily movement from accommodation to site and back | `employee-movement` | Chronological chain, observed vs inferred |
| 3 | **Site Visit Report**: visit details and time at each site, worker-wise | `site-visits` | Grouped by worker, with totals |
| 4 | **Employee Utilization Report**: productive time versus idle or travel time | `employee-utilization` | Redefined: productive / travel / idle split (see 3.5) |
| 5 | **Job Costing Report**: actual labour cost by project vs the project budget entered at setup, variance per job | `job-costing` | Budget is a **setup input** on the worksite |
| 6 | **Payroll Report**: basic, overtime, allowances, deductions, net pay | `payroll` | Shows gross and net pay (equal in v1: the client has no deductions) |
| 7 | **Transportation Time Report**: time travelling between accommodation and sites | `transportation-time` | Uses the same transit segments as utilization |
| 8 | **Late Arrival / Early Departure Report**: deviations from scheduled working hours | `late-early-departure` | Also lists shortfall (requirements spec) |
| 9 | **Project Attendance Summary**: manpower deployed per project over a period | `project-attendance-summary` | Planned vs deployed manpower |
| 10 | **Pending Visits List**: sites not yet completed, flagged for follow-up | `pending-visits` | Follow-up workflow added (see 3.10) |
| - | (requirements spec) Monthly attendance and cumulative worked time | `monthly-attendance` | |
| - | (requirements spec) Employer provisions and total staff cost | `provisions-staff-cost` | Employer cost; never shown to workers or supervisors |
| - | (requirements spec) Staffing gaps | `staffing-gaps` | Split out of "pending visits and staffing gaps" |
| - | (requirements spec + client alert) Document expiry | `document-expiry` | Also drives alerts |
| - | (client's weekly schedule sheet) Weekly roster export | `weekly-roster` | Workers x days with sites and hours, in the client's layout |
| - | (transport) Driver run sheet | `driver-run-sheet` | A driver's stops in order with passengers |

Live monitoring (real-time map, management dashboard) and alerts are not reports; see sections 4 and 5.

## 3. Report definitions

### 3.1 `daily-attendance`  (client #1)   (layout: `design/D3-time-rules-and-attendance-report.md`)
**Intent**: for every worker and day, the planned schedule, what actually happened, the variation, and the comments and approval for rows that differ.
One row per employee/date with two blocks of **seven columns each** - *Planned*: start at accommodation, start at first site, break, end at last site, end at accommodation, total time used, total worked time; *Actual*: the same seven. Then **Variation in total time**, **Variation in worked time** (actual - planned, signed), **Comments** (Supervisor, mainly where planned and actual differ) and **Approval** (Engineer, only for rows with variation, a flag or overtime; clean rows show AUTO). Extra columns: status (PRESENT / PARTIAL / ABSENT), OT1/OT2 hours, flags. Workers without accommodation show n/a in the accommodation columns.
Example: planned 5:00 / 6:00 / 0:30 / 15:30 / 17:00 = total 12:00, worked 9:00; actual 5:20 / 6:20 / 0:30 / 15:20 / 16:50 = 11:30, 8:30; variations -0:30 and -0:30.
Status rule (DEC-17): PRESENT = all assigned sites visited; PARTIAL = some; ABSENT = none.

### 3.2 `monthly-attendance`  (requirements spec)
Per employee per month: days PRESENT/PARTIAL/ABSENT, days with shortfall beyond grace, total and **cumulative** worked time (running total by day), OT1/OT2 totals, days awaiting review.

### 3.3 `employee-movement`  (client #2)
**Intent**: reconstruct the worker's whole day on the move: accommodation -> site -> site -> ... -> accommodation.
For an employee and date range: chronological items with start/end time, place (accommodation / worksite / in transit), duration, tracking gaps with **unaccounted hours** (tracking-off minutes inside the shift minus the break, so location off during the break is not counted), and **OBSERVED / INFERRED** tags. Default collapses repeated pings inside one visit ("first ... last, n pings"); raw events on demand. Straight lines on the map are labelled "estimated path".

### 3.4 `site-visits`  (client #3)
**Intent**: what each worker did at each site and how long they stayed.
One row per visit, **grouped by worker** (with per-worker totals): date, worksite, job item, scheduled hours at that site, entry, exit (OBSERVED/INFERRED), **time spent**, counted-as-completed (>= `min_visit_minutes`), flags.

### 3.5 `employee-utilization`  (client #4)   **[DEC-28]**
**Intent**: how much of the working day was productive versus idle or spent travelling.
Per employee per day (and rolled up per period), all in minutes:
```
shift_span   = accommodation_return - accommodation_departure   (fallback: last_site_exit - first_site_entry, labelled)
productive   = max(0, sum(counted visit minutes at assigned worksites) - break_minutes_used)
travel       = sum of transit segments (see below)
idle         = max(0, shift_span - productive - travel - break_minutes_used)
utilization% = productive / shift_span
```
**Transit segment** = the interval between leaving one polygon (accommodation or worksite) and entering the next, within the day, provided it lasts <= `max_transit_minutes` (default 90). Longer intervals are not travel: they are counted as **off-site/unaccounted** inside `idle`. Time inside the accommodation polygon, or at a worksite with no assignment that day, during the shift span is idle.
**Drivers**: transit counts as productive (driving is work, BR-AT-04).
All travel/idle values are INFERRED (polygon entries/exits plus sparse pings) and labelled so. Extra columns: scheduled hours, worked (payable) minutes, scheduled-vs-worked %.

### 3.6 `payroll`  (client #6)   (rules: `06-payroll-and-cost.md`)
Per worker per approved month: standard hours, basic, special allowance, FOT, bonus, telephone and housing/transport allowances, **OT1** hours and amount, **OT2** hours and amount, **gross pay**, **net pay** (= gross; no deductions), last salary change date and difference. Totals by supervisor, group and zone. The Excel is the sheet management approves. Provisions and employer cost are not on this report.

### 3.7 `provisions-staff-cost`  (the payroll cost report; Admin and Engineers)
Per worker per month: salary portion, OT amounts, **gratuity**, **leave salary**, visa, air ticket, uniform, accommodation, medical, **per-month provision** (sum of all of these), **total staff cost** (gross pay + per-month provision), **HR OH 5%**, and **final total staff cost** (total staff cost + HR OH). Provisions use company settings. Labelled employer cost.

### 3.8 `job-costing`  (client #5)   [DEC-29]
**Intent**: for each project, actual labour cost against the budget, with variance per job (display only).
Budget per contract is calculated from the **salary revision file** (grade cost incl. its provisions and HR OH) and the job items, with an optional manual override on the worksite. Per worksite: budget, cumulative actual cost since contract start (final total staff cost allocated by worked minutes), budget pro-rated by elapsed days, variance (actual - budget) and %. The report notes that **budget provisions come from the revision file while actual provisions come from company settings**.

### 3.9 `transportation-time`  (client #7)
**Intent**: how much time workers spend travelling between accommodation and sites.
Per employee/day: accommodation -> first site (commute out), inter-site travel, last site -> accommodation (commute back), total transit; driver days highlighted. Uses the transit segments of 3.5; INFERRED.

### 3.10 `pending-visits`  (client #10)   **[DEC-32]**
**Intent**: a follow-up list of sites that should have been visited but were not.
A **pending visit** is an ACTIVE assignment whose date has passed (day closed) without a counted visit, or an occurrence whose window ended without its required hours. Today's not-yet-visited assignments show as "due today" until the day closes.
Columns: worksite, job item, assigned worker(s), supervisor, due date, age in days, **follow-up status**, latest explanation, escalation flag.
Follow-up workflow: `OPEN` -> `EXPLAINED` (Supervisor adds a *pending-visit explanation* comment) -> `RESCHEDULED` (a new assignment is created) or `CLOSED` (Engineer closes with a reason). Engineers manage the list. Open items trigger reminders (section 5).

### 3.11 `late-early-departure`  (client #8)
**Intent**: where workers deviated from the scheduled working hours.
Rows where any deviation exceeds the grace period:
```
late_arrival     = max(0, first_site_entry - planned_first_site_start)
late_departure_from_accommodation = max(0, accommodation_departure - planned_accommodation_departure)
early_departure  = max(0, planned_last_site_end - last_site_exit)
shortfall        = max(0, required_minutes - worked_minutes)
```
Shows each deviation in minutes, whether grace applied, comments (overtime justifications, corrections) and review state. Planned times come from the resolved schedule settings (employee, team, company).

### 3.12 `project-attendance-summary`  (client #9)
**Intent**: how much manpower was deployed on each project over a period.
Per worksite (grouping by group or zone selectable) per period: **planned manpower** (scheduled worker-days and hours), **deployed manpower** (distinct workers, worker-days with a counted visit, man-hours at site), breakdown by SGD, PRESENT/PARTIAL/ABSENT counts for assignments at that worksite, understaffed days. Day-level rows feed the chart.

### 3.13 `staffing-gaps`  (requirements spec)
Assigned work covered by approved leave and not yet covered, understaffed upcoming occurrences (including those caused by reduced time-rule capacity), worksites and accommodations without a boundary yet.

### 3.14 `document-expiry`  (requirements spec; client alert)
Documents (Visa, Passport, Emirates ID, **Labour Card**, optional Driving Licence) expiring within `document_expiry_lead_days` or already expired: employee, type, days left, supervisor. Same data drives the Admin/HR alert.

### 3.15 `weekly-roster`  (client's weekly schedule sheet)
The roster in the client's familiar layout: one row per worker (ID, name, grade, supervisor, engineer, transport remark), one block per day Mon-Sun with the **sites (job number and name) and hours** for that day, markers (Free, Weekly-OFF, Skipped), and a **daily total against standard hours**. Compact and expanded variants. Export from the Planner for any week.

### 3.16 `driver-run-sheet`
For a driver and date: morning and evening runs with ordered stops and the passengers at each. Printable.

## 4. Live monitoring (web)   **[DEC-31]**
**Real-time map** (client 4.2): all active field staff and their current location.
- Shows each in-scope worker's **last known verified position** with its age (event time), the device's last contact, tracking state and today's site polygons. A late upload never overwrites a newer position. It is near-real-time: phones upload event batches (pings roughly every `confirmation_polling_interval_s` while on site, queued when offline), not a continuous GPS stream.
- Worker state: **ACTIVE** = an accepted event within `live_active_window_minutes` (default 15) and tracking not disabled; **OFFLINE** = scheduled today but no event within the window, or last event is LOCATION_DISABLED; **NOT SCHEDULED** hidden by default.
- Layers, endpoints and screen: `10-ui-views.md` (3.13), `08-api-spec.md`, ADR-006.

**Management dashboard** (client 4.2): today's attendance (PRESENT / PARTIAL / ABSENT / not yet started), **active vs offline workers**, **pending visits**, **late arrivals**, **overtime hours today** (provisional, from current calculations). Every tile links to its filtered list; numbers are derived/cached, never edited.

## 5. Alerts and notifications (client 4.3)
| Audience | Client requirement | Our mechanism |
|---|---|---|
| Workers | Shift-start reminders | **App-side**: the morning alarm (planned accommodation start minus `alarm_lead_minutes`). No server push needed |
| Workers | Confirmation on arrival at / departure from a site | **App-side** local notification on its own ENTRY/EXIT. Optionally a server push if the mobile team wants it |
| Supervisors / Engineers | Alert when a worker's location tracking is interrupted | `TRACKING_INTERRUPTED` alert raised when a LOCATION_DISABLED event is accepted (in scope, in-app + push/email via adapters); cleared by LOCATION_ENABLED. Complements the end-of-day `TRACKING_GAP` flag |
| Supervisors / Engineers | Reminders for pending site visits | `PENDING_VISIT` reminders daily while a pending visit is OPEN (`pending_visit_reminder_hours`) |
| Admin / HR | Reminders for expiring documents (Emirates ID, passport, labour card) | `DOC_EXPIRY` alerts and notifications at `document_expiry_lead_days` |
Other system alerts: `NO_ACTIVITY`, `STALE_DEVICE`, `SYNC_LAG`, `STAFFING_GAP` (see 05).

## 6. Implementation notes
- Reports are modules in `modules/reports/` registered in a report registry: key, roles, typed filters, columns, a query function with scope applied, Excel/CSV/PDF formatters. Adding a report = adding one registry entry (and a docs row here).
- Index common filters (date, employee, worksite, review status). Use materialized views only after a measured need.
- Movement splits (productive, transit, idle, shift span) are computed once per attendance calculation and stored (see `07-data-model.md`), so reports do not recompute them.
- Excel via XlsxWriter/openpyxl; files go through the file-storage port with an expiry.

## 7. Month-end generation   [DEC-45, DEC-46]
`payroll_auto_run_delay_days` (5) after month-end the system creates the draft payroll and **automatically generates**: payroll, provisions-and-staff-cost, job-costing, daily and monthly attendance, project attendance summary, employee utilization, site visits, transportation time, late/early departure, employee movement. Live lists (pending visits, staffing gaps, document expiry) are always current and are not archived monthly. When Admin approves the run, the final copies are generated and stored (a new version). Visibility: **operational reports** to Admin, Engineers, Superintendents and Supervisors in scope; **salary and cost reports** (payroll, provisions-staff-cost, job-costing) to Admin and Engineers only. Admins and Engineers are notified (in-app) when the draft and the approved reports are ready.
