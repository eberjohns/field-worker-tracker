# 18 - Company Settings Catalog & Configuration Guide

This document is the definitive reference for all effective-dated company configuration parameters in Field Worker Tracker (FWT). It defines the parameter keys, supported data types, default values, country scopes, and operational business rules governing their behavior.

---

## 1. Architecture & Precedence

All company settings are stored in the `company_setting_values` table and managed through the `SettingsService`. Every setting is **effective-dated** (`effective_from`, `effective_to`), allowing policies and provision rates to evolve without distorting historic payroll runs or past attendance records.

### Resolution Precedence
When resolving a setting for a worker, worksite, or process:
1. **Direct Entity Override** (e.g. Worksite `salary_revision_code` or Employee `weekly_off_day`) takes highest priority.
2. **Country-Specific Setting**: A setting matching the worker's or worksite's operating country (`country = 'AE'` or `country = 'SA'`) with `effective_from <= target_date` (ordered by `effective_from DESC`).
3. **Global Setting**: A fallback setting where `country IS NULL` with `effective_from <= target_date`.
4. **Hardcoded System Default**: Safe fallback defined in service code if the setting key is missing.

---

## 2. Settings Catalog

### 2.1 Financial, Overtime & Provisions

| Setting Key | Data Type | Default Value | Unit | Country Scope | Status | Business Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `currency` | string | `AED` (AE), `SAR` (SA) | — | Country | GIVEN_BY_CLIENT | ISO 4217 currency symbol used for payslips, payroll runs, tenders, and job budgets. |
| `standard_ot_divisor_hours` | decimal | `208` | hours | Global | GIVEN_BY_CLIENT | Monthly standard hours divisor used to derive hourly base rate for overtime calculations (`basic_salary / 208`). |
| `ot1_multiplier` | decimal | `1.25` | ratio | Global | GIVEN_BY_CLIENT | Overtime multiplier applied to normal working day excess hours (`1.25x`). |
| `ot2_multiplier` | decimal | `1.50` | ratio | Global | GIVEN_BY_CLIENT | Overtime multiplier applied to weekly rest day (OT2 weekday) and public holiday hours (`1.50x`). |
| `ot2_weekdays` | JSON array | `["SUNDAY"]` (AE), `["FRIDAY"]` (SA) | list | Country | GIVEN_BY_CLIENT | Calendar weekdays that qualify for statutory weekend overtime rate (OT2). |
| `hr_overhead_rate` | decimal | `0.05` | fraction | Global | GIVEN_BY_CLIENT | Corporate HR management and administrative overhead applied to total labor cost in job costing (5%). |
| `provision_visa` | decimal | `132.00` | currency/mo | Global | GIVEN_BY_CLIENT | Monthly amortized visa and residency permit accrual provision per employee. |
| `provision_air_ticket` | decimal | `65.00` | currency/mo | Global | GIVEN_BY_CLIENT | Monthly air ticket allowance provision per employee for annual repatriation travel. |
| `provision_uniform` | decimal | `30.00` | currency/mo | Global | GIVEN_BY_CLIENT | Monthly uniform, safety gear, and PPE allocation provision per employee. |
| `provision_accommodation` | decimal | `550.00` | currency/mo | Global | GIVEN_BY_CLIENT | Monthly base camp housing and camp facility provision per accommodated employee. |
| `provision_medical` | decimal | `65.00` | currency/mo | Global | GIVEN_BY_CLIENT | Monthly mandatory health insurance and medical services provision per employee. |
| `gratuity_days_per_year` | integer | `30` | days | Global | GIVEN_BY_CLIENT | Statutory end-of-service gratuity entitlement days credited per completed year of service. |
| `leave_salary_divisor` | integer | `12` | months | Global | GIVEN_BY_CLIENT | Annual leave salary provision divisor across payroll months. |
| `default_salary_revision_code` | string | `REV-2026-01` | code | Country | PROPOSED_DEFAULT | Default salary revision code used to look up grade hourly rates for worksites that have not specified an explicit revision code. |

---

### 2.2 Working Hours & Scheduling Defaults

| Setting Key | Data Type | Default Value | Unit | Country Scope | Status | Business Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `default_weekly_off_day` | string | `SUNDAY` (AE), `FRIDAY` (SA) | — | Country | GIVEN_BY_CLIENT | Default weekly rest day assigned to employees upon initial onboarding or import if not explicitly specified. |
| `standard_hours_default` | decimal | `8.0` | hours | Global | GIVEN_BY_CLIENT | Default contractual standard daily working hours used when employee salary structure is not yet assigned. |
| `planned_workday_hours` | decimal | `9.0` | hours | Global | GIVEN_BY_CLIENT | Default expected daily operational window including work and unpaid midday break. |
| `reassignment_min_notice_days` | integer | `3` | days | Global | PROPOSED_DEFAULT | Advance notice required before an operational shift or replacement reassignment can be dispatched. |
| `occurrence_horizon_months` | integer | `13` | months | Global | PROPOSED_DEFAULT | Number of months into the future for which recurring contract job slots are automatically materialized. |
| `budget_only_staff_types` | JSON array | `["Project Manager", "HSE Engineer", "QA/QC Engineer", "Irrigation Engineer"]` | list | Global | PROPOSED_DEFAULT | Job staff grades budgeted on contract items but excluded from field occurrence generation and worker planning grids. Actual cost is credited equal to planned cost in job costing. On Excel import, intersected case-insensitively with resolved staff grades across active employees and job items; any previously saved roles not currently in active records remain visible as removable chips in Settings and apply automatically if matching staff/jobs are added. |

---

### 2.3 Attendance, Geofencing & Tracking Parameters

| Setting Key | Data Type | Default Value | Unit | Country Scope | Status | Business Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `default_accommodation_start` | string | `05:00` | HH:MM | Global | PROPOSED_DEFAULT | Baseline planned departure time from accommodation camp when no scoped TimeRule specifies camp departure. |
| `default_first_site_start` | string | `06:00` | HH:MM | Global | PROPOSED_DEFAULT | Baseline planned arrival and work commencement time at first worksite when no scoped TimeRule specifies site start. |
| `default_break_minutes` | integer | `30` | minutes | Global | PROPOSED_DEFAULT | Baseline fallback unpaid midday lunch/rest break duration deducted from on-site elapsed time when neither worker salary structure break nor seasonal time rule specifies a break. |
| `default_last_site_end` | string | `15:30` | HH:MM | Global | PROPOSED_DEFAULT | Baseline planned work finish and departure time from last worksite when no scoped TimeRule specifies site end. |
| `default_accommodation_end` | string | `17:00` | HH:MM | Global | PROPOSED_DEFAULT | Baseline planned arrival time back at accommodation camp when no scoped TimeRule specifies camp return. |
| `grace_period_minutes` | integer | `10` | minutes | Global | PROPOSED_DEFAULT | Leniency window for late arrival or early departure before attendance status flags a discrepancy. |
| `min_visit_minutes` | integer | `10` | minutes | Global | PROPOSED_DEFAULT | Minimum continuous presence duration inside a worksite geofence to register a legitimate `SiteVisit`. |
| `gap_flag_minutes` | integer | `15` | minutes | Global | PROPOSED_DEFAULT | Threshold of continuous missing location pings or disabled GPS during working hours that triggers a `TrackingGap`. |
| `max_transit_minutes` | integer | `90` | minutes | Global | PROPOSED_DEFAULT | Maximum expected travel duration between camp and worksites before transit is flagged as abnormal. |
| `geofence_circle_radius_m` | integer | `300` | meters | Global | PROPOSED_DEFAULT | Default geofence radius applied around representative coordinates when a worksite or camp lacks a polygon boundary. |
| `approach_polling_interval_s` | integer | `60` | seconds | Global | PROPOSED_DEFAULT | GPS capture interval used by worker mobile devices when approaching within 500m of a scheduled geofence. |
| `confirmation_polling_interval_s` | integer | `300` | seconds | Global | PROPOSED_DEFAULT | Periodic GPS heartbeat interval used by worker mobile devices during confirmed stationary site visits. |
| `day_close_delay_minutes` | integer | `120` | minutes | Global | PROPOSED_DEFAULT | Delay in minutes after local midnight (02:00 local time) before daily attendance records are auto-locked. |
| `alarm_lead_minutes` | integer | `30` | minutes | Global | PROPOSED_DEFAULT | Minutes before planned camp departure (`accommodation_start`) to schedule the mobile morning wake-up alarm (replaces legacy `day_plan_alarm_lead_minutes`). |
| `pending_visit_reminder_hours` | integer | `24` | hours | Global | PROPOSED_DEFAULT | Delay before unassigned site visits trigger an automated supervisor review alert. |
| `pending_visit_escalation_days` | integer | `7` | days | Global | PROPOSED_DEFAULT | Days before an open unresolved pending visit escalates to Engineer/Admin review. |

---

### 2.4 System, Sync & Security Defaults

| Setting Key | Data Type | Default Value | Unit | Country Scope | Status | Business Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `company_name` | string | `FWT` | text | Global | PROPOSED_DEFAULT | Short company name prefix used in generated report filenames (`<Company>_<Report>_<Country>_<Period>.xlsx`). |
| `default_password` | string | `Welcome@123` | text | Global | PROPOSED_DEFAULT | **Single unified** initial password assigned to all operational accounts (web dashboard and mobile worker first-login provisioning) upon onboarding, import, or Admin password reset (DEC-53). |
| `default_password_max_days` | integer | `7` | days | Global | PROPOSED_DEFAULT | Maximum number of days an auto-provisioned default password remains valid before mandatory password change is enforced. |
| `schedule_sync_window_days` | integer | `30` | days | Global | PROPOSED_DEFAULT | Future time horizon in days synchronized down to worker mobile devices during cursor synchronization. |
| `live_active_window_minutes` | integer | `15` | minutes | Global | PROPOSED_DEFAULT | Time window in minutes within which the latest worker location ping is rendered as "Active/Online" on Live Map. |
| `document_expiry_lead_days` | integer | `30` | days | Global | PROPOSED_DEFAULT | Advance notification window before passport, residency visa, or driving license expiration triggers an HR alert. |
| `payroll_auto_run_delay_days` | integer | `5` | days | Global | PROPOSED_DEFAULT | Working days after calendar month-end before automated draft payroll calculations are triggered for approval review. |
| `scope_site_worker_window_days` | integer | `31` | days | Global | PROPOSED_DEFAULT | DEC-57: a worker counts as "on my worksite" for the Employees list when they hold an active standing assignment there today, or have scheduled work there within this many days before or after today. |

---

## 3. Managed lists (DEC-60)

Staff types (Staff Grade Description, "Designation") and grade codes are managed lists, not settings, but they are kept under **Settings → Managed Lists**:
- Every staff type and grade dropdown offers the active values; the last option "Other – add new…" lets Admin and Engineer add one, available to everyone at once.
- Duplicates (ignoring case and spaces) are refused; a near spelling or known alias asks "Did you mean …?" and needs "Add anyway". Grade codes must be base codes (`G3C`; a `-2026` suffix is removed); a new grade with no line in an active salary revision is added with a warning.
- Admin can deactivate a value: it leaves the dropdowns, records that use it keep it. Values are never deleted. Changes are audited.
- Imports never add staff types (an unknown one is an error); new grade codes in an import are added when it is committed. The template's Lists sheet carries the current lists.
- `budget_only_staff_types` is chosen from the staff type list.
- Reset database clears both lists and re-seeds the staff types.

## 4. Editing and Overriding Company Settings

Settings can be managed and reviewed via two mechanisms:
1. **Settings Screen in Web Dashboard**: Navigate to `/settings` to inspect active values, audit changes, and update keys.
2. **Bulk Import Template (`Company_Settings` sheet)**:
   - Administrators can download the comprehensive Excel import template from `/imports`.
   - The `Company_Settings` sheet is pre-populated with example rows for all catalog settings above.
   - Re-uploading this sheet applies effective-dated updates to settings idempotently.

