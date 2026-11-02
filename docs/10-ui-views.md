# 10 - Web Dashboard: Views and Sections

React + Vite + TypeScript. Desktop-first (tablet usable). English first; layout must not block RTL/Arabic later. All times display in the **site's local time zone** with the zone shown on detail screens.
The scope and role rules in `02-roles-and-permissions.md` apply to every screen: hide what a role cannot do **and** rely on the API to enforce it.

## 1. Shell and shared patterns
- **Layout**: left navigation (collapsible), top bar with search, alerts bell, user menu. Navigation items depend on role (see section 2).
- **Lists**: server-side filtering, sorting and cursor pagination; saved filter chips; column chooser; CSV/XLSX export where the report catalog allows.
- **Detail pages**: header with key facts and status chips, tabs for sections, "History" tab showing audit entries for that record.
- **Forms**: inline validation from API error `errors[]`; optimistic-lock conflict shows "changed by someone else - reload".
- **Empty / loading / error states** are designed for every list (skeleton rows; a clear empty message with the next action).
- **Warnings pattern**: scheduling warnings appear in a confirmation dialog listing each warning; the user acknowledges to proceed.
- **Maps**: MapLibre GL JS via `react-map-gl`, Terra Draw for polygon editing, Turf for instant geometry checks (ADR-006). Streets and satellite styles come from a configurable tile provider; satellite is the default when drawing boundaries. Worker coordinates are drawn from our API as overlays and never sent to the tile provider. Map code lives in `web/src/features/map/` behind a small wrapper. The map shows the user's current location (with permission) while drawing boundaries.
- **Accessibility**: keyboard operable, visible focus, ARIA for the scheduler grid, colour never the only signal (icons/text on status chips), drag-and-drop always has a button alternative.
- **Status chips**: business status (PRESENT/PARTIAL/ABSENT) and review status (AUTO/PENDING_REVIEW/APPROVED/REJECTED) are always separate chips.

## 2. Navigation by role
| Section | Admin | Engineer | Superintendent | Supervisor |
|---|---|---|---|---|
| Overview | yes | yes | yes | yes |
| Documents (expiry) | yes | read (scope) | read (scope) | read (scope) |
| Live Map | yes | yes (scope) | yes (scope) | yes (scope) |
| Approvals inbox | yes | yes | - | - |
| Drivers and Transport | yes | yes | read | yes (scope) |
| Generated Reports | yes | yes | operational only | operational only |
| Pending Visits | yes | yes (manage) | read | read + explain |
| Employees | yes | yes (scope) | yes (scope) | yes (scope) |
| Worksites and Jobs | yes | yes | yes | yes (read) |
| Planner (roster, year plan) | yes | yes | read + reassignment request | read + reassignment request |
| Leave and Gaps | yes | yes | read | read |
| Attendance | yes | yes (+approve) | read | read + comment |
| Payroll and Cost | yes | read (scope) | - | - |
| Reports | all | scope | scope | operational only |
| Settings | yes | read | - | - |
| Imports | yes | - | - | - |
| Users and Devices | yes | - | - | - |
| Audit | yes | - | - | - |

## 3. Screens

### 3.1 Auth
Login (email + password), invite acceptance (set password), forgot/reset. Session expiry returns to login with the return URL.

### 3.2 Overview (`/`)
Role-aware widgets (derived or cached, never editable):
- **Today** (management dashboard): attendance so far (PRESENT / PARTIAL / ABSENT / not yet started), **active vs offline workers**, **pending visits**, **late arrivals**, **overtime hours today** (provisional), entries logged, no-activity alerts, PENDING_REVIEW count.
- **Staffing**: understaffed occurrences this week, open staffing gaps, boundaries still to draw (n of m).
- **Devices**: stale devices, devices with sync lag, location-permission problems.
- **Documents**: expiring in the next N days.
- **Admin/Engineer only**: payroll run status, items blocking finalization.
Each widget links to the filtered list.

### 3.3 Employees
**List** (`/employees`): grouped by Supervisor (toggle to flat). Columns: Tally ID, name, role, SGD, grade code (Admin/Engineer), supervisor, superintendent, engineer, weekly off, accommodation, active. Bulk-select -> **Bulk update** dialog (accommodation, break minutes, weekly off day).
**Detail** (`/employees/:id`) tabs:
1. *Profile* - editable per role; weekly off day editable inline.
2. *Hierarchy* - supervisor, superintendent(s) and engineer(s) (several allowed), and team members.
3. *Schedule* - Mon-Sun **heatmap** (shade = number of assignments per weekday) and this week's ordered assignments.
4. *Attendance* - recent days with statuses.
5. *Documents* - visa/passport/ID/licence validity with expiry chips.
6. *Compensation* (Admin, Engineer-read) - Grade Code with history, salary line preview, provision overrides.
7. *Device* (Admin) - registered device, last seen, last acked cursor, sync lag, **Reset to default password** (Admin only), **Reset device binding**.
8. *History* - audit.
**Hierarchy view** (`/employees/hierarchy`): tree Engineer > Superintendent > Supervisor > Workers.

### 3.4 Worksites and Jobs
**Worksite list** (`/worksites`): search by job number/name; filters group, zone, country, has-boundary, active. Warning chips: "No boundary".
**Worksite detail** (`/worksites/:id`) tabs: *Overview* (group, zone, dates, renewal ref, **contract labour budget** (calculated from the job items, optional manual override) and a "boundary not set" warning), *Job Items* (table A/B/C...), *Boundary*, *Schedule* (this worksite's weeks), *Cost* (if authorized), *History*.
**Job Item editor**: structured frequency (unit + count + interval + weekday pattern), staff count, hours per worker, SGD (dropdown from the controlled list), planned grade, outdoor flag, break override. A **validation panel** shows declared vs computed activities/annual hours, expected occurrences count, and "N eligible employees for this SGD" (red if zero).
**Boundary setup queue** (`/boundaries`, Admin and Engineer): after an import every worksite and accommodation shows **"boundary not set"**. The queue lists them with progress (n of m done); "Draw" opens the boundary editor and returns to the next item. New sites can also be created directly in the UI.
**Boundary editor** (`/worksites/:id/boundary`): **search a place** (provider geocoding, query text only) to focus the map, then draw the polygon and save. search a job number, centre on the map (or current location), draw/edit a polygon, show area, validate (closed ring, no self-intersection), save -> sync fan-out notice ("will update N workers' phones").
**Groups / Zones / Accommodations** (`/settings/org` or under Worksites): simple CRUD tables; accommodation has its own boundary editor.

### 3.5 Planner (`/planner`)   (full design: `design/D1-planner.md`, `design/D2-leave-and-reassignment.md`)
- **Roster** (default): workers down, days across (Mon-Sat plus Sunday), each cell a list of **site chips with hours** or a marker (SKIPPED holiday, WEEKLY_OFF, ON_LEAVE, TO_BE_COVERED, FREE). Row totals show allocated vs standard hours; filters by supervisor, engineer, group, staff type; compact and expanded modes; **export to Excel in the client's layout**.
- **Coverage** view: job-centred (worksite > item > day cells with assigned/required, TO_BE_COVERED slots).
- **Year plan**: standing assignments by job item with date range and weekday pattern; the **workers side panel** lists workers with allocated hours this week/month against standard hours and leave, ranked by grade group (exact staff type first).
- Assign by click or drag with a button alternative; warnings (over standard hours, weekly off, grade-group mismatch) in a confirmation dialog.
- **Leave** and **temporary reassignment** open from any cell or slot; requests go to the Approvals inbox.

### 3.6 Attendance   (daily table layout: `design/D3-time-rules-and-attendance-report.md`)
**List** (`/attendance`): date range, supervisor, employee, review status, business status, flags. Columns: date, employee, planned vs actual first entry/last exit, break, worked, variation (signed), OT, assigned/completed, business chip, review chip, flags.
**Exceptions queue** (`/attendance/exceptions`): PENDING_REVIEW items grouped by supervisor; filters by flag; bulk-open next.
**Detail / timeline** (`/attendance/:id`):
- Header: employee, date, chips, calculation version selector.
- **Planned vs actual** table (accommodation departure, first-site entry, break, last-site exit, accommodation return, total period, worked, variation).
- **Timeline + map**: events, worksite polygons, location points, visits, **tracking gaps**, accommodation departure/return; each item tagged OBSERVED or INFERRED; "show raw pings" toggle. Straight lines are labelled "estimated path".
- **Flags** panel explaining each flag in plain words.
- **Comments** (Supervisor can add) and **Approval history**.
- Decision bar (Engineer/Admin): Approve, or Reject with required reason.
- *Versions* tab: each calculation version with the reason it was created.

### 3.7 Alerts (`/alerts`)
No-activity, stale device, sync lag, document expiry, staffing gaps. Resolve with a note.

### 3.8 Payroll and Cost (`/payroll`)   (design: `design/D4-month-end-and-reports.md`)
- **Salary structures**: per-worker table with standard hours, salary portion, last change date and difference; history per worker; imported from the salary template.
- **Payroll runs**: the automatic **draft** for the previous month appears `payroll_auto_run_delay_days` after month-end. Run page: totals, **issues** (attendance still pending review, workers without salary, missing standard hours), records table, **Re-run** (Admin), **Approve** (Admin). Approved runs are read-only.
- **Record detail**: salary portion, OT1/OT2 hours and amounts, gross/net pay (employee side) and, separately, provisions, per-month provision, total staff cost, HR OH 5% and **final total staff cost** (employer side).
- **Job budget** (revision file) with budget vs actual per job.

### 3.9 Reports (`/reports`)
Hub listing the reports available to the role (14 reports: daily attendance, monthly attendance, employee movement, site visits, employee utilization, job costing, payroll, provisions and staff cost, transportation time, late arrival / early departure, project attendance summary, pending visits, staffing gaps, document expiry); each opens a filter bar, results table, chart where useful, and **Export to Excel** (CSV/PDF where defined). See `12-reports.md`.

### 3.10 Settings (`/settings`)
Tabs: *Company* (settings by group, per-country values, every change effective-dated with history), **Time rules** (`design/D3-time-rules-and-attendance-report.md`: planned times and break for the company, a team, the drivers or one person, by season and outdoor/indoor), *Public holidays*, **Budget-only staff types** (tick the types found in job items), *Provision values*, **Default password**, **Consent notice** (versions per language).
Banner on every change: "affects dates from <start date>; earlier days and approved payroll are unchanged".

### 3.11 Imports (`/imports`)
Upload -> **Preview** (counts per sheet: create/update/unchanged, warnings, errors; filterable row table with stable codes) -> Commit -> Result summary; download error report; history of batches with rollback where allowed. Link to download the template.

### 3.12 Users, Devices and Audit (Admin)
Users list (invite, resend, deactivate). Devices list with sync lag and last seen, revoke. Audit log with filters.

### 3.15 Documents (`/documents`)
Admin's expiry section (also visible read-only to other roles in scope): documents (Visa, Passport, Emirates ID, Labour Card, Driving Licence) by employee with expiry date, days left and status (OK / expiring within `document_expiry_lead_days` / expired), filters by type and supervisor, and a count tile on the dashboard. Dates are optional per employee and can be added or edited later here or on the employee's Documents tab.

### 3.13 Live Map (`/live`)
Near-real-time view of in-scope workers' **last known verified position** (not a continuous GPS stream; see `12-reports.md` section 4).
- Map with streets/satellite toggle. Layers: worksite polygons and geofence circles (today's sites emphasised), accommodation polygons, **worker markers** coloured by state (ACTIVE / OFFLINE / tracking disabled) with a "last seen n min ago" label, accuracy circle on selection, clustering at low zoom.
- Side list with search and filters (supervisor, group, zone, state, SGD); click a worker to centre the map and open a card: name, supervisor, today's assignments, last event and age, tracking state, link to today's attendance timeline.
- Updates arrive over the SSE stream with a polling fallback; a connection indicator shows "live" or "refreshing every 30 s".
- Each worker card shows **two ages**: the position's age (event time) and the device's last contact, so "last location 3 h ago, last contact 25 min ago" is distinguishable from a phone that has been offline for days (events may be uploaded a day or more later). Stale positions are visibly dimmed. Scope-filtered like everything else.

### 3.14 Pending Visits (`/pending-visits`)
The follow-up list from `12-reports.md` 3.10: filters by status, date, worksite, supervisor; rows show worksite, job item, assignee, due date, age, status and the latest explanation. Actions: Supervisor **Explain** (comment); Engineer **Reschedule** (opens the assign panel pre-filled, source FOLLOW_UP) or **Close** (reason required). Escalation badge after N days. Excel export.

### 3.16 Approvals inbox (`/approvals`)   (design: D2)
One list for Engineers (Admin sees all): **leave requests**, **temporary reassignment requests**, **overtime and variation rows** from attendance. Tabs with counts, bulk approve for attendance rows, reason required to reject, links to the cell or the attendance timeline. Badge in the top bar.

### 3.17 Drivers and Transport (`/transport`)   (design: D5)
Drivers section: driver list (with vehicle label), a day/week view of **runs** (morning and evening), each run with ordered stops and passengers per stop; suggest from schedule, copy last week, publish to the driver and workers' phones.

### 3.18 Generated Reports (`/reports/generated`)   (design: D4)
Every month-end and on-demand file with its name, period, country, version and generated time; filter and download again; shows who may see it. Month-end files appear automatically after the draft run.

## 4. Front-end stack (see ADR-002, ADR-006 and 13-architecture)
React, TypeScript, Vite; TanStack Router/Query/Table; Tailwind + shadcn/ui; react-hook-form + zod; Recharts; API client generated from OpenAPI (`openapi-typescript`); maps: MapLibre GL JS 6.x + `react-map-gl` (MapLibre entry) + Terra Draw + Turf modules (ADR-006; Terra Draw/MapLibre v6 compatibility is a gate in M3). Exact versions are verified and pinned per `17-dependencies.md`; Leaflet is rejected.
