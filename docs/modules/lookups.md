# Lookups Module (`fw.modules.lookups`)

## Purpose
Managed lists of values chosen in dropdowns: staff types (`staff_grade_description`, the client's
"Designation") and grade codes. Values are added on screen by Admin or Engineer, deactivated by Admin
and never deleted. Decision: DEC-60, ADR-030.

## Owned tables
- `lookup_values`: `list_key`, `value`, `value_key` (unique per list, case- and space-insensitive),
  `source` (SEED, SCREEN, IMPORT), `is_active`, `created_by_user_id`, `deactivated_at`,
  `deactivated_by_user_id`, `version`.

## Public interface (`fw.modules.lookups`)
- `LookupService.list_values` / `active_values`: sorted lists (grades in natural order).
- `LookupService.ensure_value`: validates a value chosen on screen and returns the list's spelling;
  the record's current value is always accepted.
- `LookupService.add_value` / `set_active`: add (duplicate and near-match checks) and deactivate or
  reactivate, audited.
- `LookupService.lists_for_import`, `add_imported_grades`: used by the import preview and commit.
- `LookupService.reseed`: "Reset database".

Routes are in `fw.api.lookups` (`GET/POST /lookups/{list_key}`, `PATCH /lookups/{list_key}/{id}`)
because the list also shows values in use on employees, job items and revision lines, which live in
higher modules. Pure rules (cleaning, keys, near matches, sort, seed list) are in `fw.rules.lookups`.

## Dependencies and layer
Own layer between `org` and `settings | identity | audit`: `jobs`, `org` and `imports` validate
against it, and it writes audit entries.

## Why a separate module
The lists are shared by employees (org), job items (jobs), imports and settings (budget-only staff
types). Putting them in any one of those would make the others depend on it sideways.
