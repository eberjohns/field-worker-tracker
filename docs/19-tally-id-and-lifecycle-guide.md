# Tally ID Management & Entity Lifecycle Guide

This guide explains how **Field Worker Tracker (FWT)** handles:
1. Changing an employee's **Tally ID** (e.g., transitioning a newly onboarded worker from a temporary probation ID to a permanent Tally payroll number).
2. What happens to the **old Tally ID**, why historical records stay intact, and the **reuse guardrail**.
3. **Admin-only Deactivation** and **Option A Clean Reactivation** for Employees, Worksites, and Job Items.

---

## 1. How Identity Works in FWT (Surrogate UUID vs. Business Key)

Every employee in FWT has two identifiers:
- **Internal Surrogate Key (`employees.id` — UUID):** Permanent, immutable primary key generated once when the employee is created. Every operational table (`users`, `scheduled_work`, `base_roster_entries`, `standing_assignments`, `leave_requests`, `reassignment_requests`, `mobile_event_logs`, `attendance_daily`, `payroll_records`, `employee_salary`, `employee_documents`, `registered_devices`) links to the employee via `employees.id` (UUID).
- **Business Key (`employees.tally_id` — unique string):** The human-facing Tally / ERP employee number used for login (`users.username`), Excel imports, payroll exports, and on-screen search.

> **Why this matters:** Because all internal links use the immutable UUID, updating `employees.tally_id` never breaks foreign keys, past attendance, GPS history, or approved payroll snapshots.

---

## 2. Changing an Employee's Tally ID (Temp → Permanent Workflow)

### When to use it
Use **Change Tally ID** when a probationary or temporary worker receives their permanent Tally payroll number, or when correcting a typo in an employee's Tally number.

### Who can perform it
- **Admin only** (`ADMIN` role).

### Step-by-step SOP
1. Navigate to **Employees → [Employee Name]** (`EmployeeDetail`).
2. Click **Change Tally ID** next to the employee's current Tally ID badge.
3. Enter the **New Tally ID** (e.g., `PERM-1042`).
   - FWT performs a live check (`GET /api/v1/employees/check-tally-id`) before submission:
     - **Blocked (HTTP 409 `DUPLICATE_TALLY_ID`):** If another employee (active **or** deactivated) currently holds that `tally_id`, it cannot be assigned.
     - **Guardrail Warning (HTTP 409 `TALLY_ID_PREVIOUSLY_USED`):** If the ID was previously held by another employee who has since changed their Tally ID, FWT displays an amber warning listing the former holder(s), replacement ID, and change date. The Admin must explicitly check **"I understand this Tally ID was previously used and confirm reuse"** (`confirm_reuse = true`) to proceed.
4. Enter a **Reason for Change** (mandatory, e.g. *"Probation completed — assigned permanent Tally ID"*).
5. Click **Update Tally ID** (`POST /api/v1/employees/{employee_id}/change-tally-id`).

### What happens automatically on commit
- `employees.tally_id` is updated to the new value (the employee record now carries **only** the new Tally ID in all live screens and new exports).
- The linked `users.username` (if a login account exists) is updated atomically in the same database transaction to match the new `tally_id`.
- An immutable audit entry (`action = 'CHANGE_TALLY_ID'`) is written to `audit_logs` recording `old_tally_id`, `new_tally_id`, `reason`, `actor_user_id`, and timestamp. The old Tally ID remains visible **only** in the **Audit Trail** tab on the Employee Detail page.
- **No forced logout:** Active mobile/web sessions remain valid until natural expiry. The supervisor/HR notifies the worker to sign in with their new Tally ID on their next login.

### What happens to the old Tally ID?
| Context | Behavior after Tally ID change |
|---|---|
| **Login (`POST /api/v1/auth/login`)** | Old Tally ID is **no longer valid** for login. The employee must use the new Tally ID on next sign-in. |
| **Historical Payroll / Attendance inside FWT** | Still linked to the same employee via UUID. Live UI queries show the employee's current name & new Tally ID. Approved payroll `snapshot` JSON preserves the Tally ID that was in force at approval time. |
| **Excel Master Data Imports** | Imports match employees by `tally_id`. **Always update your Excel sheets to the new Tally ID** before re-importing. Uploading a row with the old Tally ID will trigger the **Previously Used Tally ID Guardrail** (or create a separate employee if reuse is explicitly confirmed). |
| **Audit Trail** | `Employee Detail → History` permanently displays `CHANGE_TALLY_ID` with `old_tally_id → new_tally_id` and reason. |

### Reusing a retired Tally ID (Caveats & Guardrail)
If your HR/Tally system later recycles an old temporary number (e.g., `TEMP-01`) for a new hire:
1. **Inside FWT:** Data integrity is **completely safe** — the old worker and the new worker have distinct UUIDs, so shifts, attendance, and payroll will never collide inside the database.
2. **External Excel / Tally Risk:** Reusing a number can cause human confusion when comparing old exported Excel files (which printed `TEMP-01` for Worker A) with new exports (which print `TEMP-01` for Worker B).
3. **System Guardrail:** Both **Create Employee** (`POST /api/v1/employees`) and **Change Tally ID** (`POST /api/v1/employees/{id}/change-tally-id`) automatically scan `audit_logs` for past `CHANGE_TALLY_ID` records. If the target Tally ID was ever retired before, FWT blocks the request with `409 TALLY_ID_PREVIOUSLY_USED` and displays the prior holder's name and date until the Admin explicitly confirms reuse.
4. **Best Practice:** Prefer monotonically increasing temporary IDs (e.g. `T-2026-001`, `T-2026-002`, ...) rather than recycling old temporary numbers.

---

## 3. Admin-Only Deactivation & Clean Reactivation (Option A)

Per Golden Rule 5 (*"Referenced records are deactivated, never deleted"*), employees, worksites, and job items are **never hard-deleted**. Deactivation preserves historical attendance, GPS trails, payroll snapshots, and audit logs while cleanly detaching the entity from future operations.

### Security Requirements (Mandatory for both Deactivate & Reactivate)
- **Role:** **Admin only** (`ADMIN`).
- **Typed Confirmation:** Must type `DEACTIVATE` (or `REACTIVATE`).
- **Admin Password Verification:** Must enter the currently logged-in Admin's password (`verify_password`).
- **Mandatory Reason:** Logged permanently to `audit_logs`.
- **Optional Effective Date (Deactivation only):** Defaults to **Today**. Only schedules, occurrences, and assignments on or after `effective_date` are affected. Historical data before `effective_date` is completely untouched.

### 3.1 Deactivating an Employee
Endpoint: `POST /api/v1/employees/{employee_id}/deactivate` (Preview: `GET /api/v1/employees/{employee_id}/deactivation-impact?effective_date=YYYY-MM-DD`)

**What cascades automatically (single atomic transaction):**
1. **Employee Flag:** Sets `employees.is_active = False`.
2. **Immediate Login Revocation:** Sets linked `users.is_active = False` and revokes all active `UserSession` refresh tokens. Works for **all roles** (Workers, Supervisors, Superintendents, Engineers). Subsequent web/mobile API requests immediately fail with `HTTP 403 ACCOUNT_INACTIVE`.
   - *Safety guard:* Admin accounts (`role == 'ADMIN'`) cannot be deactivated via this flow.
3. **Base Planner Cleanup:** Deletes the worker's entries from active `BaseRosterEntry` templates so they are no longer generated into future rosters.
4. **Operational Schedule & Gap Surfacing (`>= effective_date`):**
   - Cancels all future `ACTIVE` `scheduled_work` rows with `override_reason = 'WORKER_DEACTIVATED'`.
   - Materializes 14-day gap markers for removed blueprint slots so the **Operational Planner** and **Staffing Gaps** report immediately highlight every vacated shift as **`Needs Cover (Worker Deactivated)`** — ensuring supervisors/engineers never miss an unstaffed site.
5. **Standing Assignments:** Ends active `StandingAssignment` records (`end_date = effective_date - 1`, `is_active = False`).
6. **Pending Requests:** Cancels `REQUESTED` leave requests and `PENDING` reassignment requests referencing the employee.
7. **Direct Reports Check:** If deactivating a Supervisor/Superintendent/Engineer who has active direct reports, the Impact Preview highlights the count so Admin can reassign their crew via the Hierarchy tab.

### 3.2 Deactivating a Worksite or Job Item
Endpoints:
- Worksite: `POST /api/v1/worksites/{worksite_id}/deactivate` (Preview: `GET /api/v1/worksites/{worksite_id}/deactivation-impact`)
- Job Item: `POST /api/v1/job-items/{job_item_id}/deactivate` (Preview: `GET /api/v1/job-items/{job_item_id}/deactivation-impact`)

**What cascades automatically:**
1. Sets `is_active = False` on the Worksite (and all its child `JobItem`s when deactivating a worksite).
2. Deactivates linked `BaseRosterTemplate`s (`is_active = False`).
3. Ends active `StandingAssignment`s (`is_active = False`, `end_date = effective_date - 1`).
4. Cancels future `ScheduledWork` rows (`work_date >= effective_date`, `override_reason = 'JOB_DEACTIVATED'`) and future `JobOccurrence` rows (`window_end >= effective_date`).
5. Cancels `PENDING` `ReassignmentRequest`s targeting those job items.
6. **Workers' schedules are immediately freed:** Any workers previously scheduled on the deactivated site/item instantly regain available capacity in the Operational Planner and candidate recommendations.

### 3.3 Option A — Clean Reactivation
Endpoints:
- `POST /api/v1/employees/{employee_id}/reactivate`
- `POST /api/v1/worksites/{worksite_id}/reactivate?reactivate_items=true|false`
- `POST /api/v1/job-items/{job_item_id}/reactivate`

**Why Option A (Clean Reactivation)?**
During the period an employee or worksite was deactivated, cover workers may have been assigned to those sites or freed workers may have been moved to other sites. Automatically resurrecting old schedules would silently create **double-bookings and over-staffing**.

Therefore, FWT implements **Option A (Clean Reactivation)**:
- Restores `is_active = True` (and `users.is_active = True` for employees, allowing them to sign in again).
- Restores visibility on planning, directory, and reporting screens.
- **Does NOT restore any previously cancelled `ScheduledWork`, `BaseRosterTemplate`, `BaseRosterEntry`, `StandingAssignment`, or `JobOccurrence` records.**
- Planners intentionally assign the reactivated employee or worksite into fresh schedules with full visibility of current capacity.

### 3.4 Visibility of Deactivated Records (Admin-Only)
- **Non-Admin roles (`ENGINEER`, `SUPERINTENDENT`, `SUPERVISOR`, `WORKER`):** Never see deactivated Employees, Worksites, Job Items, or Accommodations. Server-side list/export endpoints force `is_active = True` for non-admins, and direct detail lookups on deactivated records return `HTTP 404`.
- **Admin (`ADMIN`):** Sees an explicit **Status Filter (`Active` / `Deactivated` / `All`)** on the **Employees** and **Worksites** pages, plus a **"Show Deactivated Items"** toggle on **Worksite Detail → Job Items**, allowing Admins to inspect history, export DSARs, or trigger Clean Reactivation at any time.
