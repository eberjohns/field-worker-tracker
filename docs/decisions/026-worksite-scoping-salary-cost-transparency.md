# 026 - Batch 6: Worksite Scoping, Multi-Supervisor Assignment, RBAC Hardening & Salary Cost Transparency
Status: Accepted
Date: 2026-11-20

## Context
Operational feedback and client security reviews required refined access controls, employee attribute governance, and worksite supervisor assignment capabilities:
1. **RBAC & Financial Privacy**:
   - Worksite budgets, planned labor rates, and pricing figures must be strictly visible only to `ADMIN` (hidden from `ENGINEER`, `SUPERINTENDENT`, `SUPERVISOR`, and `WORKER`).
   - Excel workbook imports and exports (`/worksites/export`, `/employees/export`, `/imports/*`) must be permitted strictly for `ADMIN` and `ENGINEER`.
2. **Multi-Supervisor Worksite Scoping**:
   - A worksite can have multiple assigned field supervisors (`worksite_supervisors` table).
   - Field supervisors must only see their assigned worksites and workers assigned to their worksite's job items.
   - Superintendents and engineers see entities under their reporting tree; admin sees all.
3. **Employee Attribute Lifecycle & Audit Trail**:
   - Designations and grade codes must be strictly controlled dropdowns.
   - Profile modifications (designation, grade code, driver status) must record an immutable change log in `employee_attribute_history` with actor role and reason.
   - Inline initial salary structure creation during employee onboarding.
   - Confirmation dialogs on reporting line reassignments.
4. **Salary Structures Cost Transparency & Revision Governance**:
   - The Salary Structures table must display the full DEC-39 cost breakdown: Basic Salary, Allowances, Total Salary Portion, Gratuity `((Basic/365)*30)`, Leave Salary `(Basic/12)`, Monthly Provisions (sum of company settings provisions + Gratuity + Leave Salary), Total Staff Cost, HR Overhead (5%), and Final Cost.
   - Future-dated salary revisions can be edited and deleted by Admin prior to their effective date (guarded by `effective_from > site_today(country)` per DEC-06 immutability).
   - Revisions append revision code suffixes to grade lines (e.g. `G3C-2026`, `G3C-2027`) with base grade code fallback matching.
5. **Worksite & Accommodation Operational UX**:
   - Dynamic Group and Zone creation (`+ Add New...` / "__NEW__").
   - Geolocation centering and place search on boundary drawing modals.
   - Inline job items creation in the Add Worksite modal.
   - Worksite Excel exports include a secondary `Job_Items` sheet tab.

## Options Considered
- **Direct supervisor_id column on worksites**: Only allowed a single supervisor per worksite; rejected because large projects frequently share 2-3 supervisors across shifts or zones.
- **Dynamic in-memory tree traversal for scoping**: Recomputed transitive employee visibility on every request; optimized with `JobsService.get_scoped_worksite_ids` respecting the modular monolith layering (`jobs` > `org`).
- **Mutable historical salary structures**: Rejected per DEC-06; historical and active salary structures remain strictly immutable once effective, while future-dated revisions can be adjusted or removed prior to becoming active.

## Decision
1. **Worksite Supervisors & Operational Scoping**:
   - Added `worksite_supervisors` table (`0020_worksite_supervisors.py`) linking `worksite_id` and `supervisor_id` with cascading cleanup.
   - Implemented `GET /api/v1/worksites/{id}/supervisors`, `POST .../supervisors`, and `DELETE .../supervisors/{supervisor_id}`.
   - Scoped `list_worksites` and `list_employees` to assigned worksites for `SUPERVISOR` role.
2. **Employee Attribute History**:
   - Added `employee_attribute_history` table (`0021_employee_attribute_history.py`) logging `STAFF_GRADE_DESCRIPTION`, `GRADE_CODE`, and `IS_DRIVER` modifications with `old_value`, `new_value`, `effective_from`, `reason`, `changed_by_user_id`, and `actor_role`.
   - Exposed `PATCH /api/v1/employees/{id}/profile-details` and `GET /api/v1/employees/{id}/attribute-history`.
3. **RBAC Hardening & Financial Privacy**:
   - Budget amount on worksites is masked (`None`) for all non-admin roles in API responses.
   - `/api/v1/salary-structures` and employee salary history restricted strictly to `ADMIN` (DEC-47).
   - Imports and exports restricted to `ADMIN` and `ENGINEER`.
4. **Salary Structure Calculations & Future Revisions**:
   - Implemented `PATCH` and `DELETE /api/v1/employees/{id}/salary/{salary_id}` strictly validating `effective_from > site_today(employee.country)`.
   - Injected DEC-39 cost calculations into `SalaryStructureListItem` and web `SalaryStructures.tsx`.
   - Suffixing salary revision grade lines with `"-{rev_code}"` and enabling fallback base grade matching in side-by-side diffs and template exports.
5. **Worksite Excel Export**:
   - Generated multi-tab workbook with Sheet 1: `Worksites` and Sheet 2: `Job_Items`.

## Why
Delivers operational granularity for field supervisors, safeguards sensitive client cost and budget figures from unauthorized visibility, and establishes an immutable audit log for employee promotion and credential changes.

## Consequences
- Supervisors only access data directly relevant to their assigned job sites.
- Future-dated salary adjustments can be refined prior to payroll activation without violating historical audit immutability.
- Worksite Excel exports provide complete operational coverage across both worksite parameters and scheduled job items.
