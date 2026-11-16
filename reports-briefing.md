# Field Worker Tracker — Reports Architecture & Specifications

This document details all 16 reports for the Field Worker Tracker system, their contents, data dependencies, generation schedules (on-demand vs. automated month-end), calculation logic, and role-based access boundaries.

---

## 1. Overview & Core Principles

1. **Every Report Exports to Excel (`.xlsx`)**: One header row, typed values (dates as ISO dates, numbers as numbers), no merged cells, and a secondary sheet named **`Filters`** documenting the exact parameters used for generation.
2. **Additional Formats**:
   - **CSV**: Offered for all tabular reports.
   - **PDF**: Generated exclusively for `daily-attendance` and `payroll` (printable layout).
3. **Traceability**: All figures derive from calculated/stored tables (`attendance_records`, `attendance_calculations`, `site_visits`, `pending_visits`, `payroll_records`, `job_cost_allocations`). Raw GPS pings are never queried directly by reports. Inferred values are explicitly tagged **`INFERRED`**.
4. **Role Visibility (DEC-47)**:
   - **Operational Reports**: Accessible to `Admin`, `Engineer`, `Superintendent`, and `Supervisor` (scoped strictly to their assigned workers and worksites).
   - **Salary & Cost Reports** (`payroll`, `provisions-staff-cost`, `job-costing`): Strictly restricted to `Admin` and `Engineer`. Never visible to Supervisors or Superintendents.
5. **Generated Reports History (DEC-46)**:
   - Every generated file is permanently stored and tracked in `generated_reports`.
   - Re-runs create new versions (`v1`, `v2`, etc.); older files are never overwritten.
   - File naming pattern: `<Company>_<Report>_<Country>_<Period>_generated-<datetime>.xlsx` (with an `APPROVED` tag on final runs).

---

## 2. Report Classification Matrix

| # | Report Key | Display Title | Kind | Formats | Primary Data Source | Auto-Run at Month-End? | Visibility Roles |
|---|---|---|---|---|---|:---:|---|
| 1 | `daily-attendance` | Daily Attendance Report | Operational | XLSX, CSV, PDF | `attendance_records`, `attendance_calculations` | **Yes** | Admin, Eng, Supt, Sup |
| 2 | `monthly-attendance` | Monthly Attendance Summary | Operational | XLSX, CSV | `attendance_records`, `attendance_calculations` | **Yes** | Admin, Eng, Supt, Sup |
| 3 | `employee-movement` | Employee Movement Report | Operational | XLSX, CSV | `attendance_records`, `site_visits`, `tracking_gaps` | **Yes** | Admin, Eng, Supt, Sup |
| 4 | `site-visits` | Site Visit Report | Operational | XLSX, CSV | `site_visits`, `scheduled_works` | **Yes** | Admin, Eng, Supt, Sup |
| 5 | `employee-utilization` | Employee Utilization Report | Operational | XLSX, CSV | `attendance_calculations` (DEC-28) | **Yes** | Admin, Eng, Supt, Sup |
| 6 | `transportation-time` | Transportation Time Report | Operational | XLSX, CSV | `attendance_calculations`, `site_visits` | **Yes** | Admin, Eng, Supt, Sup |
| 7 | `late-early-departure` | Late Arrival / Early Departure | Operational | XLSX, CSV | `attendance_records`, `attendance_calculations` | **Yes** | Admin, Eng, Supt, Sup |
| 8 | `project-attendance-summary` | Project Attendance Summary | Operational | XLSX, CSV | `scheduled_works`, `site_visits`, `attendance_records` | **Yes** | Admin, Eng, Supt, Sup |
| 9 | `pending-visits` | Pending Visits List | Operational | XLSX, CSV | `pending_visits` (DEC-32) | No (Live list) | Admin, Eng, Supt, Sup |
| 10 | `staffing-gaps` | Staffing Gaps Report | Operational | XLSX, CSV | `leave_requests`, `scheduled_works`, `job_occurrences` | No (Live list) | Admin, Eng, Supt, Sup |
| 11 | `document-expiry` | Document Expiry Report | Compliance | XLSX, CSV | `employee_documents`, `employees` | No (Live list) | Admin, Eng, Supt, Sup |
| 12 | `weekly-roster` | Weekly Roster Export | Operational | XLSX, CSV | `scheduled_works`, `standing_assignments`, `leaves` | No (Planner on-demand) | Admin, Eng, Supt, Sup |
| 13 | `driver-run-sheet` | Driver Run Sheet | Operational | XLSX, CSV | `transport_runs`, `vehicles` | No (Transport on-demand)| Admin, Eng, Sup |
| 14 | `payroll` | Payroll Report | Salary/Cost | XLSX, CSV, PDF | `payroll_records`, `employee_salaries` | **Yes** | Admin, Eng only |
| 15 | `provisions-staff-cost` | Provisions & Total Staff Cost | Salary/Cost | XLSX, CSV | `payroll_records`, `company_settings` (DEC-39) | **Yes** | Admin, Eng only |
| 16 | `job-costing` | Job Costing Report | Salary/Cost | XLSX, CSV | `job_cost_allocations`, `worksites` (DEC-29) | **Yes** | Admin, Eng only |

---

## 3. Detailed Specification per Report

### 3.1 `daily-attendance`
* **Purpose**: Comprehensive daily log comparing the planned schedule against actual movements, variations, supervisor remarks, and review/approval status.
* **Columns / Content**:
  * **Planned Block (7 cols)**: Accommodation start, First-site start, Break minutes, Last-site end, Accommodation end, Total planned time, Planned worked time.
  * **Actual Block (7 cols)**: Accommodation departure, First-site entry, Break applied, Last-site exit, Accommodation return, Total actual time, Actual worked time.
  * **Variations**:
    * Variation in total time (`actual_total - planned_total`, signed minutes).
    * Variation in worked time (`actual_worked - planned_worked`, signed minutes).
  * **Metadata & Approvals**: Worker ID, Worker Name, Date, Status (`PRESENT` = all assigned sites visited, `PARTIAL` = some, `ABSENT` = none), OT1 hours, OT2 hours, Review Flags (`FLAG_ESTIMATED_EXIT`, `FLAG_TRACKING_GAP`, `FLAG_SHORT_HOURS`, etc.), Supervisor Comments, Engineer Approval status (`APPROVED`, `REJECTED`, or `AUTO` for clean rows without deviations).
  * *Workers without accommodation*: Display `n/a` in accommodation columns; total time spans first to last site. Drivers use accommodation times only.
* **Dependencies**: `attendance_records`, `attendance_calculations`, `attendance_comments`, `attendance_approvals`, effective `time_rules`.
* **Execution**: On-demand (any date range & org filters) and Auto-run at Month-End.

---

### 3.2 `monthly-attendance`
* **Purpose**: Monthly attendance overview showing cumulative working time and review progress per worker.
* **Columns / Content**: Worker ID, Worker Name, Month, Days Present, Days Partial, Days Absent, Days with Shortfall beyond grace, Total Worked Minutes/Hours, Cumulative Running Worked Time (day-by-day progression), Total OT1 Hours, Total OT2 Hours, Days Pending Review.
* **Dependencies**: `attendance_records`, `attendance_calculations`.
* **Execution**: On-demand and Auto-run at Month-End.

---

### 3.3 `employee-movement`
* **Purpose**: Full reconstructed chronological chain of movement throughout the day: Accommodation $\rightarrow$ Site 1 $\rightarrow$ Site 2 $\rightarrow$ Accommodation.
* **Columns / Content**: Worker ID, Worker Name, Date, Item Order, Segment Type (`ACCOMMODATION`, `TRANSIT`, `WORKSITE`, `TRACKING_GAP`), Location Name, Start Time, End Time, Duration (minutes), Inferred/Observed Tag (`OBSERVED` for geofence pings, `INFERRED` for estimates/inter-site straight lines), Unaccounted Time (`tracking_off_minutes - break_minutes` inside shift).
* **Dependencies**: `attendance_records`, `site_visits`, `tracking_gaps`, `attendance_calculations`.
* **Execution**: On-demand and Auto-run at Month-End.

---

### 3.4 `site-visits`
* **Purpose**: Time spent and arrival/departure verification worker-wise at each worksite.
* **Columns / Content**: Grouped by worker with totals. Date, Worksite Code & Name, Job Item, Scheduled Hours at Site, Entry Time, Exit Time, Time Spent (minutes), Exit Tag (`OBSERVED` vs `INFERRED`), Counted as Completed (`Yes` if time spent $\ge$ `min_visit_minutes` [default 10 min], else `No`), Exceptions/Flags.
* **Dependencies**: `site_visits`, `scheduled_works`, `worksites`, `job_items`.
* **Execution**: On-demand and Auto-run at Month-End.

---

### 3.5 `employee-utilization` [DEC-28]
* **Purpose**: Breakdown of the working day into productive work, travel, and idle time.
* **Logic / Formulas**:
  $$\text{shift\_span} = \text{accommodation\_return} - \text{accommodation\_departure}$$
  $$\text{productive} = \max(0, \sum \text{counted visit minutes at assigned sites} - \text{break\_minutes\_used})$$
  $$\text{travel} = \sum \text{transit segments between polygons} \quad (\le \text{max\_transit\_minutes [90 min]})$$
  $$\text{idle} = \max(0, \text{shift\_span} - \text{productive} - \text{travel} - \text{break\_minutes\_used})$$
  $$\text{utilization\_pct} = \frac{\text{productive}}{\text{shift\_span}}$$
  * *Drivers*: Transit is classified as productive work (`BR-AT-04`).
  * Transit intervals $> 90\text{ min}$ are classified as off-site/unaccounted inside `idle`.
* **Columns**: Worker ID, Name, Date, Shift Span, Productive Minutes, Travel Minutes, Idle Minutes, Break Used, Utilization %, Scheduled Minutes, Worked Minutes, Scheduled vs Worked %.
* **Dependencies**: `attendance_calculations` (metrics precomputed by attendance engine).
* **Execution**: On-demand and Auto-run at Month-End.

---

### 3.6 `transportation-time`
* **Purpose**: Analysis of time spent travelling between accommodation and worksites.
* **Columns / Content**: Worker ID, Name, Date, Commute Out Time (Accommodation $\rightarrow$ First Site), Inter-Site Travel Time, Commute Back Time (Last Site $\rightarrow$ Accommodation), Total Transit Time, Driver Flag (highlighting driver days), Inferred Tag.
* **Dependencies**: `attendance_calculations`, `site_visits`.
* **Execution**: On-demand and Auto-run at Month-End.

---

### 3.7 `late-early-departure`
* **Purpose**: Exceptions log identifying deviations from scheduled hours exceeding the grace period.
* **Logic**:
  $$\text{late\_arrival} = \max(0, \text{first\_site\_entry} - \text{planned\_first\_site\_start})$$
  $$\text{late\_departure\_acc} = \max(0, \text{actual\_acc\_dep} - \text{planned\_acc\_dep})$$
  $$\text{early\_departure} = \max(0, \text{planned\_last\_site\_end} - \text{last\_site\_exit})$$
  $$\text{shortfall} = \max(0, \text{required\_standard\_minutes} - \text{worked\_minutes})$$
* **Columns**: Worker ID, Name, Date, Deviation Type, Deviation Minutes, Grace Applied (Y/N), Shortfall Minutes, Supervisor Overtime Justification / Comments, Review Status.
* **Dependencies**: `attendance_records`, `attendance_calculations`, resolved `time_rules`.
* **Execution**: On-demand and Auto-run at Month-End.

---

### 3.8 `project-attendance-summary`
* **Purpose**: Manpower deployed per worksite/project over a period against planned targets.
* **Columns / Content**: Worksite Code & Name, Group, Zone, Scheduled Worker-Days, Scheduled Man-Hours, Deployed Unique Workers, Deployed Worker-Days (days with counted visit $\ge 10\text{m}$), Total Actual Man-Hours on Site, Manpower Breakdown by SGD (Staff Type / Grade Group), Present / Partial / Absent counts, Understaffed Days count.
* **Dependencies**: `scheduled_works`, `site_visits`, `attendance_records`, `worksites`, `employees`.
* **Execution**: On-demand and Auto-run at Month-End.

---

### 3.9 `pending-visits` [DEC-32]
* **Purpose**: Follow-up workflow for assignments where a scheduled site was not completed.
* **Status Lifecycle**: `OPEN` $\rightarrow$ `EXPLAINED` (Supervisor enters comment) $\rightarrow$ `RESCHEDULED` (new assignment created) or `CLOSED` (Engineer closes with reason).
* **Columns**: Worksite, Job Item, Assigned Worker(s), Supervisor, Due Date, Age (days since due date), Follow-up Status, Latest Explanation, Escalation Flag.
* **Dependencies**: `pending_visits`, `worksites`, `job_items`.
* **Execution**: On-demand only (Live operational list; not archived at month-end).

---

### 3.10 `staffing-gaps`
* **Purpose**: Detection of uncovered shifts and operational deficits.
* **Columns / Content**: Date, Worksite, Job Item, Gap Reason (`LEAVE_UNCOVERED`, `UNDERSTAFFED_OCCURRENCE`, `MISSING_BOUNDARY`), Required Staff Type, Required Hours, Current Allocated Hours, Deficit Hours, Action Status.
* **Dependencies**: `leave_requests`, `scheduled_works`, `job_occurrences`, `worksites`.
* **Execution**: On-demand only (Live operational list).

---

### 3.11 `document-expiry`
* **Purpose**: Compliance tracking for mandatory identity and labor documents.
* **Tracked Documents**: Visa, Passport, Emirates ID, Labour Card, Driving Licence.
* **Columns**: Worker ID, Worker Name, Document Type, Document Number, Expiry Date, Days Remaining, Expiry Status (`OK`, `EXPIRING_SOON` [$\le \text{document\_expiry\_lead\_days}$], `EXPIRED`), Supervisor.
* **Dependencies**: `employee_documents`, `employees`.
* **Execution**: On-demand only (Live compliance list).

---

### 3.12 `weekly-roster`
* **Purpose**: Full weekly planner exported in the client's spreadsheet layout.
* **Columns / Content**: Worker ID, Worker Name, Grade, Supervisor, Engineer, Transport Remark, Mon–Sun daily cells (Worksite job number & name, planned hours, markers: `Free`, `Weekly-OFF`, `Skipped`, `Leave`), Weekly Total Planned Hours vs. Standard Hours.
* **Dependencies**: `scheduled_works`, `standing_assignments`, `leave_requests`, `employees`.
* **Execution**: On-demand (accessible from Reports Hub & Planner).

---

### 3.13 `driver-run-sheet`
* **Purpose**: Daily transport run manifest for drivers and coordinators.
* **Columns / Content**: Driver Name, Vehicle Label/Plate, Date, Direction (`MORNING` / `EVENING`), Ordered Stops (Stop #, Location Name, Scheduled Arrival Time), Passenger Names per stop.
* **Dependencies**: `transport_runs`, `vehicles`, `employees` (handles empty/fallback state cleanly if transport module has no data).
* **Execution**: On-demand.

---

### 3.14 `payroll` [DEC-01, DEC-06, DEC-07, DEC-30]
* **Purpose**: Official payroll sheet for management approval.
* **Columns / Content**:
  * Worker ID, Name, Grade, Group, Zone, Supervisor.
  * Standard Hours, Basic Salary, Special Allowance, Fixed OT (FOT), Bonus, Telephone Allowance, Housing/Transport Allowance.
  * Overtime: OT1 Hours & Amount ($$\frac{\text{Basic}}{208} \times 1.25$$), OT2 Hours & Amount ($$\frac{\text{Basic}}{208} \times 1.5$$).
  * Deductions: Missed hours ($\text{Unpaid Leave} + \text{Shortfall beyond grace}$) deducted at $$\text{Missed Hours} \times \frac{\text{Basic}}{208}$$.
  * Gross Pay, Net Pay ($$\text{Gross} - \text{Deductions}$$).
  * Last Salary Change Date and Delta difference.
  * Subtotals by Supervisor, Group, and Zone.
* **Dependencies**: `payroll_runs`, `payroll_records`, `employee_salaries`.
* **Execution**: On-demand and Auto-run at Month-End.
* **Role Visibility**: **Admin & Engineer ONLY**.

---

### 3.15 `provisions-staff-cost` [DEC-39]
* **Purpose**: True employer cost analysis including statutory provisions and overheads.
* **Columns / Content**:
  * Worker ID, Name, Salary Portion (Basic + allowances), OT1 & OT2 amounts.
  * Statutory Provisions:
    * Gratuity Provision (per country rule pack formula).
    * Leave Salary Provision ($$\frac{30}{365} \times (\text{Basic} + \text{Housing})$$).
  * Company Setting Provisions: Visa, Air Ticket, Uniform, Accommodation, Medical.
  * Per-Month Provision Total (sum of all provisions above).
  * Total Staff Cost ($$\text{Gross Pay} + \text{Per-Month Provision}$$).
  * HR Overhead 5% ($$\text{Total Staff Cost} \times 0.05$$).
  * Final Total Staff Cost ($$\text{Total Staff Cost} + \text{HR OH}$$).
* **Dependencies**: `payroll_runs`, `payroll_records`, `company_settings`.
* **Execution**: On-demand and Auto-run at Month-End.
* **Role Visibility**: **Admin & Engineer ONLY**.

---

### 3.16 `job-costing` [DEC-29]
* **Purpose**: Project-level financial performance comparing contract budget against allocated labor costs.
* **Columns / Content**: Worksite Code & Name, Contract Start Date, Contract End Date, Contract Budget (from assigned salary revision code & job items, or manual override), Cumulative Actual Cost since contract start (final total staff cost allocated by actual worked minutes via `job_cost_allocations`), Pro-rated Budget (by elapsed calendar days), Variance Amount ($$\text{Actual} - \text{Budget}$$), Variance %.
* **Footnote**: *"Budget provisions derive from the salary revision file; actual provisions derive from company settings."*
* **Dependencies**: `job_cost_allocations`, `payroll_records`, `worksites`, `salary_revisions`.
* **Execution**: On-demand and Auto-run at Month-End.
* **Role Visibility**: **Admin & Engineer ONLY**.

---

## 4. Month-End Auto-Run Workflow & Lifecycle

```
[ Calendar Month Ends (e.g. 31 Oct) ]
                 │
                 ▼
[ Delay: payroll_auto_run_delay_days (5 days) ]
                 │
                 ▼
[ Auto-Draft Payroll Created (run_no = 1) ]
                 │
                 ├───────────────────────────────────────────────┐
                 ▼                                               ▼
[ Generate 11 Month-End Reports per Country ]       [ Send In-App Notification ]
  • payroll                                           "Draft Month-End Reports
  • provisions-staff-cost                             Ready for 2026-10 (AE)"
  • job-costing
  • daily-attendance
  • monthly-attendance
  • project-attendance-summary
  • employee-utilization
  • site-visits
  • transportation-time
  • late-early-departure
  • employee-movement
  File: <Company>_<Report>_<Country>_<Period>_generated-<datetime>.xlsx
  Version: v1
                 │
                 ▼
     [ Admin Reviews & Re-runs? ]
                 │
       Yes ──────┴──────> [ Increment run_no (v2) -> Re-generate Month-End Set ]
                 │
                 ▼ No
       [ Admin Approves Payroll ]
                 │
                 ├───────────────────────────────────────────────┐
                 ▼                                               ▼
[ Freeze Payroll & Lock Month Attendance ]        [ Generate Final Approved Reports ]
                                                    Tag: APPROVED, New Version
                                                    Permanent snapshot in generated_reports
                                                                 │
                                                                 ▼
                                                    [ Send In-App Notification ]
                                                      "Final Approved Reports
                                                      Ready for 2026-10 (AE)"
```

### Storage and Naming Conventions
* **Storage Location**: Local disk storage backend under `./storage/reports/` managed by `FileStorageAdapter`.
* **Filename Pattern**:
  `FieldWorkerTracker_Payroll-Cost_AE_2026-10_generated-20261106-090000.xlsx`
  * `<Company>`: Derived from company settings (sanitized for file systems, fallback `FieldWorkerTracker`).
  * `<Report>`: Capitalized kebab-to-title case (e.g. `Daily-Attendance`, `Payroll-Cost`).
  * `<Country>`: Active country code (`AE`, `SA`).
  * `<Period>`: Month `YYYY-MM`.
  * `<datetime>`: Timestamp of generation `YYYYMMDD-HHMMSS`.
  * Final approved copies carry an `APPROVED` tag recorded in `generated_reports.status` / `params`.
