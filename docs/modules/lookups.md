# Lookups Module (`fw.modules.lookups`)

## Purpose
Managed lists of values chosen in dropdowns: staff types (`staff_grade_description`, the client's
"Designation") and grade codes. Staff types are added and deactivated by Admin in Settings and never
deleted. The grade list is the base codes with a line in an ACTIVE salary revision, kept by payroll.
Decision: DEC-60 (amended 23 Nov 2026), ADR-030.

## Owned tables
- `lookup_values`: `list_key`, `value`, `value_key` (unique per list, case- and space-insensitive),
  `source` (SEED, SCREEN, IMPORT), `is_active`, `created_by_user_id`, `deactivated_at`,
  `deactivated_by_user_id`, `version`.

## Public interface (`fw.modules.lookups`)
- `LookupService.list_values` / `active_values`: sorted lists (grades in natural order).
- `LookupService.ensure_value`: validates a value chosen on screen and returns the list's spelling;
  the record's current value is always accepted.
- `LookupService.add_value` / `set_active`: add a staff type (duplicate and near-match checks) and
  deactivate or reactivate one, audited. Grade codes are refused (`GRADE_FROM_REVISION_ONLY`).
- `LookupService.sync_grades`: called only by `PayrollService.refresh_grade_list` after every change
  to salary revisions; makes the active grade list match the active revisions (audited).
- `LookupService.lists_for_import`: both lists for the import preview.
- `LookupService.reseed`: "Reset database".

Routes are in `fw.api.lookups` (`GET/POST /lookups/{list_key}`, `PATCH /lookups/{list_key}/{id}`)
because the list also shows values in use on employees, job items and revision lines, which live in
higher modules. Pure rules (cleaning, keys, near matches, sort, seed list) are in `fw.rules.lookups`.

## Dependencies and layer
Own layer between `org` and `settings | identity | audit`: `jobs`, `org` and `imports` validate
against it, and it writes audit entries. Payroll (higher) keeps the grade rows, so org and jobs can
check grades without reading payroll tables.

## Why a separate module
The lists are shared by employees (org), job items (jobs), imports and settings (budget-only staff
types). Putting them in any one of those would make the others depend on it sideways.
