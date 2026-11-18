# 023 - Single Standalone System Administrator (Decoupled from Employees)

Status: Accepted  
Date: 2026-11-18  

## Context
Previously, `users.employee_id` had a `NOT NULL` foreign key to `employees.id`, and `employees.role` allowed `'ADMIN'`. As a result:
1. Bootstrapping the system administrator (`ADMIN001`) required inserting a dummy row into `employees`.
2. That dummy `ADMIN001` employee leaked into operational queries — including payroll runs (`PayrollRepository.get_active_employees_for_country`), salary listings, attendance recalculation, weekly roster reports, leave summaries, and org hierarchy trees — unless every query manually filtered `role != 'ADMIN'`.
3. There was no database or API guardrail preventing additional `ADMIN` users or employees from being created through API endpoints, imports, or tests.

## Options considered
1. **Manual query filtering (`WHERE role != 'ADMIN'`) everywhere:** Fragile; any new report, export, or service query that omits the filter re-introduces Admin into operational data. Does not prevent multiple Admins.
2. **Decouple `ADMIN` from `employees` + enforce single-Admin DB constraints (chosen):** Make `users.employee_id` nullable exclusively for `role = 'ADMIN'`, remove `'ADMIN'` from `employees.role`, and add a PostgreSQL partial unique index allowing at most one `ADMIN` user.

## Decision
1. **Standalone Admin Account (`users` table, migration `0017_single_standalone_admin`):**
   - `users.employee_id` is nullable, enforced by `CHECK ((role = 'ADMIN' AND employee_id IS NULL) OR (role <> 'ADMIN' AND employee_id IS NOT NULL))`.
   - Partial unique index `uq_users_single_admin ON users ((true)) WHERE role = 'ADMIN'` guarantees at most **one** `ADMIN` account (`ADMIN001`) exists across the database.
2. **Operational-Only `employees` Table:**
   - `check_employees_role_valid` restricts `employees.role` strictly to `('WORKER', 'SUPERVISOR', 'SUPERINTENDENT', 'ENGINEER')`.
3. **API, Import & Test Guardrails:**
   - `OrgService.create_employee`, `OrgService.update_employee`, `UserService.update_user`, and the Excel import registry reject assigning `role = 'ADMIN'` (`400 ADMIN_ROLE_RESERVED`), reserving `ADMIN001` (`400 RESERVED_TALLY_ID`), and deactivating the system admin.
   - `POST /api/v1/settings/reset-database`, seed scripts, and integration tests reuse the single standalone `ADMIN001` user via `UserService.get_or_create_system_admin()`.

## Why
Structural separation guarantees by construction that the System Administrator can never appear in scheduling, attendance, leave, salaries, payroll runs, reports, hierarchy, or mobile device sync — while PostgreSQL enforces the single-Admin invariant even against direct SQL or scripts.

## Consequences
- `UserRead.employee_id` and JWT `"employee_id"` claim are `null` for `ADMIN001`; all code inspecting `user.employee_id` handles `None` safely (and mobile worker endpoints return `403` for Admin).
- Related docs updated: [02-roles-and-permissions.md](../02-roles-and-permissions.md), [07-data-model.md](../07-data-model.md).
