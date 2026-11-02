# Field Worker Tracker

## Consolidated System Requirements and Data Structure

## 1. System Overview

The Field Worker Tracker manages employees, reporting
hierarchy, worksites, job requirements, recurring schedules, worker
assignments, temporary reassignment, location events, attendance,
attendance comments and approvals, salary calculations, staff-cost
provisions, payroll, reports, and mobile synchronization.

The system consists of: - **Web dashboard** for Admin, Engineer,
Supervisor, and Superintendent, according to their access permissions. -
**Mobile application** for Workers and operational roles that require
mobile access. - **Backend API** for authentication, master data,
scheduling, mobile synchronization, event processing, attendance
calculations, approvals, payroll calculations, and reports. -
**Relational database** for master data, assignments, raw event logs,
calculated attendance, approval history, salary revisions, payroll
snapshots, and audit history. - **Local mobile storage** for
schedules/configuration needed in the field and events waiting to
synchronize.

Core principles: - The backend is authoritative for schedules,
attendance, payroll, permissions, and final calculations. - The mobile
application collects observations, stores required data locally, and
synchronizes with the backend. - Raw mobile event logs are preserved.
Corrections and approvals are recorded separately. - Historical
attendance/payroll calculations retain the values used when finalized,
even if configuration changes later. - Client Excel files are imported
and normalized into the system's separate entities. - Referenced
business records are deactivated rather than deleted, preserving
historical relationships.

## 2. Roles and Access

  ------------------------------------------------------------------------------
  Role              Web dashboard     Mobile app        Responsibilities
  ----------------- ----------------- ----------------- ------------------------
  Admin             Yes               As applicable     Full system management,
                                                        imports, configuration,
                                                        user/account management,
                                                        master data, salary
                                                        revisions, device
                                                        reset/revocation

  Engineer          Yes               Yes               Operational management
                                                        within assigned scope,
                                                        reports, attendance
                                                        exception review and
                                                        approval

  Superintendent    Yes               Yes               Operational oversight
                                                        and reporting within
                                                        assigned scope

  Supervisor        Yes               Yes               View operational data
                                                        and reports, add
                                                        comments/explanations,
                                                        temporary worker
                                                        reassignment

  Worker            No automatic web  Yes               View own
                    account                             profile/schedule/map and
                                                        relevant payroll
                                                        information; generate
                                                        mobile events
  ------------------------------------------------------------------------------

### Access rules

-   Roles are fixed system roles; there is no generic configurable
    role/permission engine.
-   Employee and reporting relationships are referenced using Tally IDs
    resolved to internal employee records.
-   Multiple Supervisors may be associated with one Engineer.
-   Visibility is restricted to the employee's assigned reporting scope.
-   Supervisor can temporarily reassign workers and add operational
    comments. Supervisor cannot edit employee master data, permanent
    schedules, job definitions or other core master data.
-   Importing an employee with the role Supervisor, Superintendent or
    Engineer automatically provisions a web-dashboard account.
-   Worker accounts are mobile-only by default.
-   Passwords are not imported as plaintext. Account setup/reset is
    handled securely.
-   Only one active registered mobile device is permitted per worker.
    Admin can revoke/reset the registration so a replacement device can
    be registered.
-   Admin is the only role allowed to delete an unused entity.
    Referenced entities are deactivated instead of deleted.

## 3. Employee Master

Employee fields:

-   `id` --- internal primary key
-   `tally_id` --- business identifier from the source data
-   `name`
-   `phone` (optional)
-   `email` (optional)
-   `role` --- Worker, Supervisor, Superintendent, Engineer, Admin as
    applicable
-   `grade_code` --- salary-revision reference label, e.g. G2B26
-   `staff_grade_description` --- staffing reference label,
    e.g. Gardener Expert, Gardener Helper, Irrigation Technician
-   `supervisor_employee_id`
-   `superintendent_employee_id`
-   `engineer_employee_id`
-   `accommodation_id` (optional)
-   `weekly_off_day`
-   `break_override_minutes` (optional)
-   `join_date`
-   `employment_end_date` (optional)
-   `is_active`
-   timestamps

### Employee data rules

-   Operational role is separate from Grade Code and Staff Grade
    Description.
-   Grade Code is used to select the applicable salary revision.
-   Staff Grade Description is used to recommend workers for Job Items
    with a matching required Staff Grade Description.
-   Grade Code and Staff Grade Description are separate reference
    labels. There is no mapping table between them.
-   There is no separate designation/grade mapping or worker-type
    mapping requirement.
-   Staff Grade Description values must be consistent between employee
    and Job Item data for matching recommendations.
-   Reporting relationships are linked using Tally IDs; names are not
    used as relationship keys.
-   The employee import consolidates records across hierarchy worksheets
    using Tally ID.
-   Tally ID is treated as the client's business identifier.
-   Employee schedule heatmap shows Monday--Sunday. Shade intensity
    increases with the number of scheduled assignments on each weekday.
-   Weekly off day can be set directly in the employee view.
-   Authorized users can select multiple employees and bulk-update
    accommodation, break duration and weekly off day.
-   Employees are displayed grouped by assigned Supervisor, with
    Superintendent and Engineer available as hierarchy fields/filters.
-   Employee visibility follows the assigned reporting scope.

## 4. Worksite / Parent Job Number

The client's Job Number, such as `32A14119`, represents the parent
physical worksite/job record. One parent Job Number has one shared
boundary and can contain multiple sub-items such as A, B, C.

Parent Job fields:

-   `id`
-   `job_number` --- e.g. 32A14119
-   `job_name` / common description
-   `renewal_reference` --- e.g. R1, R2
-   `group_id`
-   `zone_id`
-   `customer_type` (where supplied)
-   `start_date`
-   `end_date`
-   `boundary_polygon`
-   `representative_latitude`
-   `representative_longitude`
-   `is_active`
-   timestamps

### Worksite behavior

-   All A/B/C Job Items under the same parent Job Number share the same
    boundary.
-   The boundary is configured after bulk import using the map GUI.
-   The Admin can search for the imported parent Job Number and
    draw/edit its polygon.
-   The system may derive a representative point from the polygon for
    map display; the polygon is the authoritative geofence boundary.
-   Display the current map location while configuring a boundary.
-   Group and Zone are normalized entities with codes and names, linked
    to the parent job.
-   The source Site Grouping workbook contains Job Number, Job Name,
    Group Code, Group Name, Zone Code, Zone Name and Customer Type.

## 5. Group and Zone

### Group

-   `id`
-   `group_code`
-   `group_name`
-   `is_active`

### Zone

-   `id`
-   `zone_code`
-   `zone_name`
-   `is_active`

A Group or Zone can be associated with multiple parent jobs. Parent jobs
reference these records through foreign keys.

## 6. Job Items / Sub-items

One parent Job Number may have several Job Items, usually identified by
A, B, C, etc. A unique Job Item is identified by the parent Job Number
and sub-item code.

Job Item fields:

-   `id`
-   `parent_job_id`
-   `sub_item_code`
-   `staff_grade_description` --- required
-   `frequency_unit` --- Daily, Weekly, Monthly, Quarterly, Yearly or
    supported recurrence
-   `frequency_count` --- e.g. two times per week or three times per
    year
-   `activities_per_year`
-   `required_staff_count`
-   `hours_per_frequency_per_staff`
-   `days_per_frequency`
-   `total_hours_per_year`
-   `break_override_minutes` (optional)
-   `is_active`
-   timestamps

### Job staffing and hour rules

-   `hours_per_frequency_per_staff` is the expected duration for each
    assigned worker per occurrence.
-   Example: 3 required workers × 9 hours per worker = 27 man-hours per
    occurrence.
-   Hours must not be divided equally among workers; each assigned
    worker is expected to work the specified hours per occurrence unless
    an authorized assignment override applies.
-   Annual total man-hours can be calculated as
    `activities_per_year × required_staff_count × hours_per_frequency_per_staff`.
-   The imported annual total should be compared with the calculated
    value. Differences should be visible for validation.
-   Parent Job Number holds common information and boundary; each Job
    Item holds its own Staff Grade Description, frequency, staff count
    and hours.

### Frequency and occurrence behavior

-   Supported frequencies include daily, N times per week, weekly,
    monthly, quarterly, yearly and N times per year.
-   Occurrences are generated from frequency and the job's active
    period.
-   For N occurrences per year, occurrence windows are distributed
    evenly across the year.
-   For weekly recurrence, the user can define weekday patterns that
    repeat through the active period.
-   Monthly/quarterly and other low-frequency jobs can have their actual
    dates assigned manually.
-   A pattern selected for one recurrence window can be applied to
    equivalent future windows where appropriate.
-   Completed historical occurrences are preserved if frequency
    configuration changes.

## 7. Accommodation Master

Accommodation is a separate shared entity; multiple employees may use
the same accommodation.

Fields: - `id` - `accommodation_code` - `name` - `address` -
`boundary_polygon` (optional) - `representative_latitude` -
`representative_longitude` - `is_active` - timestamps

The accommodation boundary can be configured through the map GUI. A
representative point may be derived from the polygon or entered as a
point location.

Accommodation is used in movement reporting and the driver work-time
rule.

## 8. Salary Revisions and Staff Cost

The salary revision workbook contains grade-based salary/cost fields
including Grade Code, Designation, Basic, Special Allowance, 8 Hrs
Total, FOT, Bonus, CTC, Leave Salary, Gratuity, Accommodation, Uniform,
Medical, Air Ticket, Visa, Transportation Cost, OH and Total Cost.

### Salary revision model

-   Salary data is stored as versioned salary revisions and revision
    lines.
-   A revision line contains a revision identifier, Grade Code, salary
    components and applicable effective information.
-   The employee's Grade Code selects the applicable salary row in the
    effective salary revision.
-   Employee Grade Code can be changed in employee management with a
    record of the change.
-   Job `renewal_reference` (R1/R2) is a label for the job and does not
    select the employee salary revision.
-   Salary components are not duplicated as an independent source of
    truth on Employee.
-   Finalized payroll stores a snapshot of the values used.

### Salary, provisions and operational cost

Derived formulas:

-   `Gratuity = (Basic Salary / 365) × 30`
-   `Leave Salary = Basic Salary / 12`
-   `Total Provision = Gratuity + Leave Salary + Visa + Air Ticket + Uniform + Accommodation + Medical`
-   `Total Staff Cost = Employee Salary + Total Provision`
-   `Final Operational Cost = Total Staff Cost × (1 + HR OH Rate)`

Company Settings control the provision values for Visa, Air Ticket,
Uniform, Accommodation and Medical. HR OH is currently 5% and
configurable. Some employees may have no allocation for one or more
provision components.

These provisions represent employer cost and are not additional cash
paid directly to the employee. Employee payroll and employer cost must
be shown separately.

Gratuity and Leave Salary may be derived dynamically for reports, but
finalized payroll/cost records preserve the calculated values and
formulas used so that historical results remain reproducible.

### Overtime

-   Standard divisor: 208 hours = 26 working days × 8 hours.
-   Basic hourly rate = Basic Salary / 208.
-   OT1 = Basic hourly rate × 1.25.
-   OT2 = Basic hourly rate × 1.50.
-   Sunday and public holiday work uses OT2, regardless of the
    employee's weekly off day.
-   Public holidays are organization-wide.
-   Insufficient required work time triggers an alert/review; it does
    not automatically deduct salary.
-   Salary revision overtime fields are mapped explicitly so fixed OT
    and calculated OT are not double-counted.

## 9. Company Settings

Company settings include:

### Planned schedule defaults

-   Planned accommodation departure
-   Planned first-site start
-   Default break duration
-   Planned last-site end
-   Planned accommodation return
-   Standard required working hours/shift rules, where applicable

Schedule override hierarchy: 1. Individual employee override 2. Labour
group/team override, where configured 3. Company default

Overrides have applicable dates/effective ranges. Historical finalized
attendance is not rewritten by future changes.

### Attendance, payroll and notifications

-   Grace period, e.g. 10 minutes
-   OT1/OT2 rules
-   Standard OT divisor (208)
-   Organization-wide public holidays
-   Annual provision defaults
-   HR OH percentage, currently 5%
-   Document-expiry notification lead time
-   Other approved notification settings

### Grace period

If required time is 8:00, actual work time is 7:55 and grace period is
10 minutes: - Actual work time remains 7:55. - Shortfall remains 5
minutes. - Attendance can be treated as satisfied under the grace
rule. - The system records that grace was applied and the rule used. -
Raw events and actual time are never altered to equal planned time.

## 10. Scheduling UX and Rules

### Week-view scheduler

Scheduling is a visual week view, not a long form of dropdowns.

-   Rows are grouped by parent Job Number/worksite.
-   Job Items A/B/C are nested under the parent.
-   Each row shows Staff Grade Description, frequency, required staff
    count, hours per worker and current allocation.
-   Day cells show allocation and staffing status.
-   Selecting a day cell opens a panel to assign eligible workers.
-   Worker view shows that employee's ordered assignments for each day
    and weekly workload.
-   Support explicit sequence controls or drag/drop with an accessible
    alternative.
-   Show required versus assigned staff, required versus assigned hours,
    and conflicts.
-   Employee selection can be grouped by Supervisor.

### Worker recommendations

Recommend workers when employee Staff Grade Description matches the Job
Item's required Staff Grade Description. Grade Code is used for salary
revision, not for matching staff to a job.

Show warnings for weekly off, approved leave, conflicting assignments,
inactive employees/jobs, job dates, reporting scope, understaffing and
assignment constraints. Matching is a recommendation; an authorized user
confirms the assignment.

### Multiple worksites per day

A worker may have several separate assignments on one day. Each
assignment has its own Job Item, date, worksite, assigned hours,
sequence and status.

Example: 1. Site A / Job A --- 3 assigned hours 2. Site B / Job B --- 2
assigned hours 3. Site C / Job C --- 3 assigned hours

The scheduler shows 8 assigned hours, but not a guaranteed elapsed day
duration because travel time varies. Actual movement times come from
mobile event logs.

### Temporary reassignment

-   Supervisor can create temporary reassignment only; they cannot
    permanently edit master data or recurring job definitions.
-   Temporary reassignment must be created at least one day in advance.
-   Record original assignment, replacement assignment, date,
    reason/comment, creator and timestamps.
-   Preserve the original assignment history.
-   The new assignment appears in the worker's next synchronization.
-   If the phone is offline, the server retains the authoritative
    schedule and records that the device has not synchronized the
    change. The mobile app continues to show its cached schedule until
    sync.
-   The operational expectation is that the mobile app connects to the
    internet at least once per day.
-   Server-side validation prevents conflicting or duplicate
    assignments.

### Leave and spare staff

-   Approved leave blocks ordinary scheduling on the affected dates.
-   The system identifies staffing gaps.
-   Authorized personnel manually select spare workers and assign cover.
-   Coverage is recorded as an explicit assignment change with history.

## 11. Mobile Application and Synchronization

### Mobile functionality

-   Authenticated profile and employee information
-   Current/future assignments and sequence
-   Worksite address and map with boundary
-   Current location when permission is granted
-   Relevant schedule/contract calendar
-   Weekly scorecard/working-time information supplied by backend
-   Movement/location events
-   Notifications and relevant payroll information
-   First-login consent and permission flow

Checklist functionality is not included.

### Consent and permissions

-   Show the required notice/consent for location, background location
    where required, device permissions and applicable privacy terms.
-   Request only permissions required by the agreed features.
-   Record policy/consent version and timestamp as appropriate.
-   Location permission failure must be handled clearly; the system must
    not fabricate location events.

### Initial synchronization

On login/initial sync, the backend supplies relevant profile,
current/future assignments, Job Item and worksite data, polygons, weekly
off, schedule settings and other information required for offline use.
The app stores this data locally.

### Incremental synchronization

-   The server maintains a schedule/data version or sync cursor.
-   The phone sends its last successful cursor/version.
-   The server returns changed, added, cancelled or deactivated records
    and a new cursor.
-   The phone applies changes transactionally, then stores the new
    cursor.
-   If sync fails, the cursor is not advanced.
-   Pending event uploads are retried using unique event IDs to avoid
    duplicates.
-   Batch upload and retry/backoff are used.
-   The server schedule remains authoritative if the phone has stale
    data.

## 12. Mobile Event Logs and Location Processing

### Event fields

-   `event_id` --- device-generated UUID
-   `employee_id` --- validated from authenticated identity
-   `device_id`
-   `job_id` or `job_item_id`, nullable where no job can be associated
-   `event_type`
-   `event_timestamp_utc`
-   `latitude`
-   `longitude`
-   `accuracy_meters`
-   `sequence_number` (if used)
-   `received_at_utc` --- server-generated
-   processing status/error reason as applicable

Do not include the previously removed generic `source` field.

### Event types

The agreed movement event types include: - `ENTRY` - `EXIT` - `PING` -
`LOCATION_DISABLED` - `LOCATION_ENABLED`

Explicit `CLOCK_IN`/`CLOCK_OUT` are only used if included in the
approved workflow. Geofence entry/exit and manual clock actions must
have distinct meanings.

For `LOCATION_DISABLED`, preserve the last successful location if
available. For `LOCATION_ENABLED`, record the new observed location when
available. Inferred gaps must be labelled as inferred.

### Event processing

1.  Authenticate user/device.
2.  Validate schema, event type, coordinates and timestamp.
3.  Deduplicate by event ID.
4.  Persist the raw event.
5.  Process events chronologically with validation rules.
6.  Associate observations with worksite polygons and assignments where
    possible.
7.  Identify entries, exits, visits and gaps.
8.  Calculate attendance or flag ambiguous/missing data.
9.  Preserve processing outcomes and calculation versions.
10. Keep reports traceable to source events.

Event time and server receipt time are stored separately in UTC. The
mobile device clock is not inherently trustworthy; implausible times are
flagged rather than silently rewritten.

### Timeline

The Employee Timeline is a derived view. It shows relevant events
chronologically on a map, worksite polygons, timestamps, site visits,
movement segments, attendance, break, worked time, overtime, comments
and approval status.

The default timeline view should suppress repetitive/noisy logs while
preserving raw records for audit. Straight-line interpolation between
GPS points is a visualization estimate, not proof of the actual route.
Distinguish observed events from inferred movement.

## 13. Attendance Calculation

### Regular workers

`Elapsed Site Period = Last Site Exit − First Site Entry`

`Actual Worked Time = Elapsed Site Period − Applicable Break`

For multiple sites, the interval starts at entry to the first site and
ends at exit from the last site. Inter-site travel remains inside the
interval. Accommodation commute is retained for movement reporting but
excluded from regular-worker worked time.

Example: - First site entry: 06:20 - Last site exit: 15:20 - Elapsed
site period: 9 hours - Applicable break: 30 minutes - Actual worked
time: 8 hours 30 minutes

### Drivers

For drivers, work time includes accommodation departure through
accommodation return because transportation itself is work activity.
This is a separate calculation rule.

### Planned versus actual

Attendance displays planned and actual: - Accommodation departure -
First-site entry - Break duration - Last-site exit - Accommodation
return - Total movement/time period - Worked time - Variation -
Supervisor comments - Engineer approval

Variation is derived as `Actual − Planned`, with a consistent
signed-duration convention.

### Break source and history

Break duration may come from Job override, employee override, group/team
override or company default according to the configured precedence. The
effective duration used by each daily calculation is saved with the
attendance transaction. Later configuration changes do not rewrite
historical finalized calculations.

### Attendance status

Business attendance status and review status are separate fields.

Business status includes: - `PRESENT` - `PARTIAL` - `ABSENT`

Review status includes: - `CALCULATED` - `PENDING_REVIEW` - `APPROVED` -
`REJECTED` or returned for correction

If some assigned jobs are completed and others are not, show assigned
versus completed counts and mark the day partial.

### Daily calculation record

Store: - employee/date - schedule/assignment references - planned values
used - first-site entry and last-site exit - accommodation
departure/return if available - break duration used - elapsed site
period - actual worked minutes - grace period and whether it applied -
shortfall/variation - OT1/OT2 hours/rates where applicable -
assigned/completed work counts - business and review status -
calculation version/time - source event references

Recalculation due to late events or approved corrections creates a
traceable new version.

## 14. Comments and Approval

Supervisor comments are operational explanations and do not modify raw
events or master data.

### Attendance comment fields

-   `id`
-   `attendance_id`
-   `author_user_id`
-   `comment_type`
-   `comment_text`
-   `created_at_utc`
-   optional linked assignment/job occurrence

### Attendance approval fields

-   `id`
-   `attendance_id`
-   `reviewer_user_id`
-   `decision`
-   `comment`
-   `created_at_utc`
-   status/calculation version reference

Workflow: 1. Backend calculates attendance. 2.
Exceptions/partial/absence records enter review where required. 3.
Supervisor adds comments/explanations. 4. Engineer reviews and approves
or returns/rejects with a reason. 5. The system records decision and
timestamp. 6. Corrections create traceable new versions; prior history
is retained.

## 15. Payroll and Reports

### Payroll workflow

1.  Synchronize and validate raw events.
2.  Resolve assignments and worksite events.
3.  Calculate daily attendance/work time.
4.  Select salary revision by employee Grade Code and applicable
    effective date.
5.  Calculate overtime.
6.  Calculate salary components and provisions.
7.  Generate monthly payroll preview or automatic payroll as configured.
8.  Review attendance/exception issues.
9.  Finalize payroll.
10. Save a payroll snapshot and expose authorized results to web/mobile
    users.

Insufficient required hours trigger alerts/review; they do not
automatically reduce salary.

### Payroll snapshot fields

-   employee/pay period
-   Grade Code and salary revision used
-   salary component values
-   daily attendance references
-   OT1/OT2 hours, rates and amounts
-   salary totals
-   provision components and totals
-   HR OH rate/amount
-   total staff cost and final operational cost
-   rounding/calculation version
-   generated/finalized timestamps
-   status and approving user where applicable

Finalized payroll does not change when salary, break, provision or
overhead configuration changes later.

### Reports

1.  Daily attendance: planned/actual times, total time, worked time,
    break, variation, comments and approval.
2.  Monthly employee attendance and cumulative worked time.
3.  Employee movement report/timeline.
4.  Site visit report.
5.  Employee utilization report.
6.  Job costing report, comparing actual labour cost with job/project
    budget where maintained.
7.  Payroll report with salary components and OT.
8.  Employer provisions and total staff-cost report.
9.  Transportation/movement-time report.
10. Late arrival, early departure and shortfall report.
11. Attendance summary by job/worksite/group/zone.
12. Pending/uncompleted visits and staffing gaps.
13. Document-expiry alerts.

Dashboard statistics are derived from current data or a defined cache;
they are not independent manually edited source records.

## 16. Employee Documents and Expiry Notifications

Store only: - employee reference - document type: Visa, Passport,
Emirates ID, optional Driving Licence - start date - validity/expiry
date - active status/timestamps if needed

Do not store document number or full document scan. Notification lead
time is configurable in Company Settings. Expiry notifications use the
configured notification integration.

## 17. Logical Database Entities and Relationships

### Identity and organization

-   **Employee:** employee details, role, Tally ID, Grade Code, Staff
    Grade Description, reporting links, accommodation, weekly off,
    active status.
-   **User:** login/authentication linked to Employee where applicable;
    username, password hash, role, active state, last login.
-   **RegisteredDevice:** employee/device, platform/app version,
    registered/last-seen/revoked timestamps, active state.
-   **Accommodation:** shared location and polygon.
-   **EmployeeDocument:** document type, start date and validity date
    only.
-   **Group:** group code/name.
-   **Zone:** zone code/name.

### Work and planning

-   **ParentJob/Worksite:** Job Number, common description, renewal
    reference, group, zone, dates, polygon, active status.
-   **JobItem:** parent job + sub-item code A/B/C, required Staff Grade
    Description, frequency, required staff, hours per worker and annual
    values.
-   **JobOccurrence:** generated/manual occurrence window, due date,
    status and occurrence requirements.
-   **JobWeeklyPattern/Recurrence Rule:** recurring weekday
    configuration.
-   **ScheduledWork:** one employee + date + Job Item/occurrence +
    worksite + assigned hours + sequence + status.
-   **LeaveRequest:** employee, leave type, date range, reason, status,
    approver and timestamps.
-   **TemporaryReassignment/ScheduleChange:** original/new assignment,
    date, reason, creator and timestamp.

### Attendance, payroll and audit

-   **MobileEventLog:** immutable event facts, device event time and
    server receipt time.
-   **AttendanceRecord/CalculationVersion:** daily calculated values,
    applied configuration snapshot, statuses and source-event links.
-   **AttendanceComment:** authored operational comments.
-   **AttendanceApproval:** reviewer decisions and history.
-   **SalaryRevision / SalaryRevisionLine:** versioned grade-based
    salary components and effective rules.
-   **PayrollRun:** payroll period, status and timestamps.
-   **PayrollRecord/Snapshot:** per-employee finalized values and
    component snapshot.
-   **AuditLog:** actor, action, entity, old/new values or safe diff,
    reason and UTC timestamp.
-   **NotificationLog:** recipient, type, delivery status, provider
    reference and timestamps, if persisted.

### Relationship summary

-   Employee may have a User account; role controls access.
-   Employee reporting references resolve Tally IDs to internal Employee
    IDs.
-   Many Employees share one Accommodation.
-   One Group and one Zone can each relate to many Parent Jobs.
-   One Parent Job has many Job Items.
-   One Job Item has many Job Occurrences.
-   One Job Item/Occurrence has many Scheduled Work records.
-   One Employee has many Scheduled Work records.
-   One Employee has many Mobile Event Logs and Attendance Records.
-   Attendance has many comments, approval-history records and
    calculation versions.
-   Employee Grade Code selects a Salary Revision Line for an effective
    date.
-   One Payroll Run has many Payroll Snapshots.
-   Historical records remain available after master data deactivation.

### Delete/deactivation rules

-   Do not hard-delete records referenced by assignments, events,
    attendance, payroll or audit history.
-   Prefer `is_active = false` for employees, accommodations, groups,
    zones, parent jobs, job items and reference values.
-   Admin may delete a genuinely unused record only after checking
    references.
-   Do not cascade-delete historical records when a master record is
    deactivated.
-   Use foreign keys and delete restrictions.

## 18. API Inputs and Synchronization

### API areas

-   Authentication and device registration/reset
-   Employees and hierarchy
-   Accommodation
-   Group and Zone
-   Parent Jobs/Worksites and polygons
-   Job Items and occurrence generation
-   Schedule views and assignments
-   Temporary reassignment
-   Leave and spare-staff allocation
-   Mobile sync and event batch upload
-   Attendance, comments, approvals and recalculation
-   Salary revisions and company settings
-   Payroll preview/finalization/history
-   Reports and exports
-   Import preview/validation/commit
-   Notifications/document expiry
-   Audit history and health checks

### Mobile event API

The event API accepts batches and validates user/device, schema, event
type, coordinates and timestamps. It deduplicates by `event_id`,
persists accepted raw events before acknowledging, and returns per-event
accepted/duplicate/rejected statuses. It supports retries without
duplicate effects. The backend does not trust client-calculated payroll
or arbitrary employee identity.

### Schedule sync API

The client supplies the last sync cursor/version and optional date
range. The server returns changed assignments, cancellations and updated
relevant data, plus a new cursor. The mobile applies changes
transactionally and advances the cursor only after successful
application.

### Import API

1.  Upload workbook.
2.  Select worksheet and map columns if needed.
3.  Parse and normalize.
4.  Validate required values, duplicates, references and formula
    consistency.
5.  Show preview and row-level errors/warnings.
6.  Confirm import.
7.  Commit through a controlled transaction/import batch.
8.  Return summary and downloadable error report.
9.  Make repeated imports safe and avoid duplicate records.

## 19. Bulk Import Requirements

### Employee hierarchy workbook

Logical content: - Tally ID - employee name - role - Grade Code - Staff
Grade Description - Supervisor Tally ID - Superintendent Tally ID -
Engineer Tally ID - weekly off day - accommodation reference - break
override if supplied - contact/employment fields present in the source

The importer consolidates rows across hierarchy worksheets and resolves
reporting relationships after employees are loaded. It reports
duplicate/conflicting rows, missing references, self-references and
hierarchy cycles.

### Site grouping workbook

-   Job Number
-   Job Name
-   Group Code
-   Group Name
-   Zone Code
-   Zone Name
-   Customer Type if present

Group and Zone are normalized and linked by code. Conflicting names for
one code are reported.

### Job workbook

Logical content: - Parent Job Number - sub-item code A/B/C - common
description and renewal reference - Group/Zone codes - start/end dates -
Staff Grade Description - frequency/count - activities per year -
required staff count - hours per frequency per staff - days per
frequency - total annual hours - break time if supplied - other approved
source fields

The importer splits denormalized source rows into Parent Job and Job
Item records.

### Salary revision workbook

-   Revision identifier/name and effective date/status
-   Grade Code
-   salary component columns present in the approved workbook
-   Basic Salary and overtime-related fields
-   source-provided or derived Leave Salary/Gratuity
-   provisions and operational-cost fields
-   OH field and its meaning

Source values are mapped explicitly and derived values are validated
against the formulas.

### Accommodation/document imports

If source data exists: - Accommodation code/name/address and available
coordinates/polygon - Employee Tally ID, document type, start date and
validity date only

No document number or scan is imported.

## 20. System Views and Sections

### Admin dashboard

-   Overview/statistics
-   Employee management and hierarchy
-   Worksite/Parent Job and Job Item management
-   Map boundary editor
-   Group and Zone management
-   Accommodation management
-   Salary revisions and employee compensation
-   Company Settings
-   Public holidays
-   Imports and exports
-   User/account/device reset management
-   Reports
-   Audit history

### Engineer dashboard

-   Operational overview within assigned scope
-   Employee/worksite/job data management according to role
-   Schedule and staffing visibility
-   Attendance exceptions and approval
-   Comments/history
-   Payroll and operational reports as authorized

### Superintendent dashboard

-   Operational overview within assigned scope
-   Employee/worksite/job and schedule visibility according to role
-   Reports and operational monitoring
-   Access to mobile functions

### Supervisor dashboard

-   Workers grouped by reporting hierarchy
-   Schedule and job/site information
-   Reports
-   Temporary reassignment
-   Attendance/partial-work comments
-   Operational explanations
-   No core master-data editing or permanent schedule editing

### Worker mobile app

-   Profile
-   Today/current and future schedule
-   Ordered daily assignments
-   Worksite map and geofence
-   Current location when permitted
-   Schedule/contract calendar
-   Weekly scorecard
-   Attendance/location events
-   Alerts
-   Relevant payroll information

### Scheduling view

-   Week navigation
-   Parent Job/worksite grouping
-   Nested A/B/C Job Items
-   Required versus assigned workers
-   Assigned hours and sequence
-   Worker recommendations by Staff Grade Description
-   Worker daily/weekly workload
-   Conflicts, leave, weekly off and staffing gaps
-   Temporary reassignment workflow for authorized users

### Attendance timeline

-   Relevant event sequence
-   Worksite polygons and location points
-   First-site entry and last-site exit
-   Accommodation departure/return where applicable
-   Break and worked time
-   Movement/site visit summaries
-   Comments and approval history
-   Distinction between observed and inferred information

## 21. Security, Audit and Data Retention

-   Enforce role and reporting-scope authorization on every API
    endpoint.
-   Use TLS and secure secret management.
-   Hash passwords and never log tokens/passwords.
-   Do not store employee document numbers or scans.
-   Validate uploaded workbooks.
-   Preserve event logs, audit logs, attendance history and payroll
    snapshots according to the applicable retention policy.
-   High-volume data includes location pings, event logs,
    synchronization diagnostics and notification logs.
-   Archive/export old data with stable IDs and integrity checks; do not
    delete events needed to explain finalized attendance/payroll without
    an approved retention policy.
-   Maintain backups and a restore process.
-   Record important changes with actor, action, entity, old/new values
    or safe diff, reason and UTC timestamp.
-   Keep external map/notification/storage providers replaceable through
    adapters.

## 22. Operational Behavior Summary

1.  Admin imports employee, hierarchy, site grouping, job and salary
    revision workbooks.
2.  Import logic validates and normalizes source data into Employee,
    Parent Job, Job Item, Group, Zone and Salary Revision entities.
3.  Admin configures worksite/accommodation boundaries using the map UI
    and configures Company Settings.
4.  Authorized users schedule work through a week view; recurring
    occurrences and daily worker sequences are represented separately.
5.  Worker mobile apps download schedules/configuration and store them
    locally.
6.  Mobile apps record location/movement events and queue them offline
    if needed.
7.  Backend receives events, deduplicates, preserves raw data,
    associates them with jobs/sites and calculates attendance.
8.  Grace and break rules are applied to the calculation without
    modifying raw actual time.
9.  Supervisor adds comments where required; Engineer reviews/approves
    exceptions.
10. Monthly payroll/cost reports use the applicable salary revision and
    preserved daily calculations.
11. Finalized payroll stores a snapshot of salary components, overtime,
    provisions and operational cost.
12. Later changes to schedules, break, salary revisions or company
    settings do not rewrite finalized historical results.
13. Reports and mobile views show authorized information from backend
    records.
14. Referenced records are deactivated rather than deleted, preserving
    relationships and history.
