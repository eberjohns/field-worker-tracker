# 02 - Roles and Permissions

Roles are **fixed**: ADMIN, ENGINEER, SUPERINTENDENT, SUPERVISOR, WORKER. There is no configurable permission engine.

## Accounts
- Every person has a login: **username = worker/employee ID**. All users receive the **same default password** (a company setting). It must be changed at first login; an account that has not changed it within `default_password_max_days` is locked until Admin resets it.
- Users can change their own password at any time. **Only Admin can reset** any user (workers included) back to the default password. Workers who forget ask their supervisor, who asks Admin.
- Workers are **bound to the first device** they log in from (device model, OS, app version stored); other devices are refused and logged; Admin resets the binding when a worker changes phone.
- Accounts are created from the employee import; no emails are required.

## Reporting scope
Visibility is by reporting relationship. Reporting lines are stored as links `(employee, manager, relationship)` in `employee_reporting_lines`, where relationship is SUPERVISOR, SUPERINTENDENT or ENGINEER. A person may have **several superintendents and several engineers** (and at most one supervisor). For user U (an employee), `scope(U)` is the set of employees E where:
- `E.id = U.id` (self), or
- a link exists with `manager_id = U.id` and `employee_id = E.id` (any relationship).

ADMIN sees everything. WORKER sees self only. Superintendents are view-only, except that they may create temporary reassignments (see the matrix).

Derived visibility:
- **Employees**: `scope(U)`.
- **Worksites / Job Items**: those with scheduled work or occurrences involving any employee in `scope(U)`, plus any a Supervisor/Engineer is explicitly assigned. (Admin: all.)
- **Attendance, comments, events, payroll**: for employees in `scope(U)`.
Every list and detail endpoint must apply the scope filter in the service/repository layer, not only in the UI.

## Permission matrix
C = create, R = read, U = update, D = delete (unused records only), A = approve/decide, X = not allowed. "scope" means limited to reporting scope.

| Resource | Admin | Engineer | Superintendent | Supervisor | Worker (mobile) |
|---|---|---|---|---|---|
| Employees | CRUD | R scope; U weekly-off, accommodation, break (bulk) in scope | R scope | R scope | R self |
| Employee grade code | U | X | X | X | X |
| Accounts, devices | CRUD, revoke | X | X | X | X |
| Groups, Zones, Accommodations | CRUD | R | R | R | X |
| Worksites + boundaries | CRUD | CRU (creates sites and draws boundaries) | R scope | R scope | R own sites |
| Job Items | CRUD | CRU | R | R | R own |
| Occurrences, weekly patterns | CRUD | CRU scope | R | R | X |
| Scheduled Work (permanent) | CRUD | CRUD scope | R | R | R self |
| Temporary reassignment | CRUD (auto-approved) | CRUD scope, **approve** | C (request) scope | C (request) scope | R self |
| Leave | CRUD, approve | CRUD scope, **approve** | R | C (records the request) scope | R self |
| Events (raw) | R | R scope | R scope | R scope | C own |
| Attendance | R, recalc | R scope, A | R scope | R scope | R self (summary) |
| Attendance comments | CRU | CRU | R | C own comments | X |
| Attendance review / approval (rows with variation, flags or OT) | A | A (scope) | X | X | X |
| Time rules (planned times, break, seasons) | CRUD all | CRUD for their scope (team, individual) | R | R | R own |
| Drivers and transport runs | CRUD | CRUD scope | R | CRU scope | R own run |
| Approvals inbox | all | leave, reassignments, overtime, variation rows | X | X | X |
| Passwords | reset any user to default | own | own | own | own |
| Salary revisions, settings | CRUD | R | X | X | X |
| Payroll run (draft, re-run, approve) | CRUD, approve | R scope (draft and approved) | X | X | R self (approved) |
| Reports | All | Scope | Scope | Scope (operational only, no salary) | X |
| Live map and dashboard | R all | R scope | R scope | R scope | X |
| Pending visits | R, close | R scope, manage (reschedule, close) | R scope | R scope; explain (comment) | X |
| Contract labour budget override | CRU | R | X | X | X |
| Import / export | CRUD | X | X | X | X |
| Audit log | R | X | X | X | X |

Notes:
- Supervisors cannot see salary/cost reports or payroll data.
- A site created by an Engineer is visible to that Engineer even before any employee is scheduled there.
- Superintendents cannot edit permanent schedules, jobs or master data; their only write action is temporary reassignment.
- Engineers can view payroll/cost reports for their scope; only Admin finalizes payroll.
- A Supervisor cannot edit master data, permanent schedules or job definitions.
- Only Admin may hard-delete, and only records with no references (otherwise deactivate).

## Implementation notes
- A single `require_role(...)` dependency plus a `scope_filter(user)` helper used by every repository query.
- Permission checks have unit tests in the `rules/` or `modules/identity` area using example users.
- Log denied access attempts to the audit log with reason `FORBIDDEN`.
