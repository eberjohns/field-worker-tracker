# 013 - Import Pipeline Framework, Registry Single-Source, and Salary Structures

Status: Accepted  
Date: 2026-11-03  

## Context
Phase 03 establishes the master data import framework and worker salary structures for the Field Worker Tracker.
Per client requirements and decisions DEC-39 and DEC-51:
1. The bulk-import Excel workbook contains 14 sheets spanning multiple phases (Groups, Zones, Accommodations, Employees, Reporting, Salary, Settings, Time Rules, Holidays in Phase 03; Worksites, Job Items in Phase 04; Leave in Phase 06; Revisions in Phase 11).
2. The import framework must guarantee safe, idempotent execution: blank cells preserve existing values, underscore `_` explicitly clears optional values, and absent rows are never deleted.
3. Users require preview before committing: showing `NEW`, `UPDATED` (with field-level `old -> new` diffs), `UNCHANGED`, `REACTIVATED`, and row-level validation error codes.
4. Salary structures are effective-dated: a change records history, calculates total fixed salary portion, identifies last change date and difference, and applies from the 1st day of the upcoming calendar month by default.

## Options considered
- **Template Generation & Schema Registry**:
  - *Option A (Static template file)*: Store a static `.xlsx` file on disk and parse it with ad-hoc dictionaries.
  - *Option B (Code-driven registry)*: A single-source Python registry defines sheets, column constraints, validations, and examples. Both parser/validator and the template generator read directly from this registry.
- **Out-of-Scope Sheets in Phase 03**:
  - *Option A (Reject if present)*: Fail the upload if Worksites, Job Items, or Leave sheets contain data.
  - *Option B (Validate headers & report SKIPPED)*: Validate header structure on row 4 and report all rows in future sheets as `SKIPPED` (info status), enabling the full master workbook to be uploaded without blocking Phase 03 master data.
- **Foreign Key References Within the Same Workbook**:
  - *Option A (Database-only lookup)*: Only resolve foreign keys against pre-existing database records.
  - *Option B (Composite lookup)*: Resolve references against pre-existing database entities combined with natural keys defined in earlier sheets of the same file (e.g. `Employees` referencing new `Accommodations`, `Employee_Salary` referencing new `Employees`).
- **Batch Rollback**:
  - *Option A (Hard delete / purge)*: Delete all rows created by the batch.
  - *Option B (Guarded safe rollback)*: Check downstream references before reverting created/updated records; if referenced, reject rollback with an audit warning.

## Decision
- Adopt **Option B (Code-driven registry)**: `SHEET_REGISTRY` in `backend/src/fw/modules/imports/registry.py` is the single source of truth for sheet definitions, commit order, validations, and template generation.
- Adopt **Option B (Validate headers & report SKIPPED)**: Out-of-scope sheets in Phase 03 (Worksites, Job Items, Leave, Salary Revisions) are inspected for header integrity and logged as `SKIPPED`, allowing complete master workbooks to pass cleanly.
- Adopt **Option B (Composite lookup)**: Validation in `parse_and_preview` indexes natural keys in the current workbook alongside DB records, allowing self-contained multi-sheet master data files to import in one transaction.
- Adopt **Option B (Guarded safe rollback)**: `POST /imports/{id}/rollback` checks for downstream entity references before deactivating created records and restoring previous values.
- **Salary Effective Dates**: Effective from date defaults to the 1st day of the upcoming calendar month if omitted. Fixed portion sums `basic_salary`, `special_allowance`, `fixed_ot_amount`, `bonus`, `telephone_allowance`, and `housing_transport_allowance`.
- **User Provisioning**: Employees imported with web roles (`SUPERVISOR`, `SUPERINTENDENT`, `ENGINEER`, `ADMIN`) are automatically provisioned with active `User` accounts requiring password change on first login. Workers without web access do not receive web accounts.
- **Mobile Change Sync**: Moving `sync_changes` mobile fan-out to Phase 07 to coordinate with the mobile sync endpoint contract.

## Why
- A code-driven registry eliminates drift between documentation, the Excel template, validators, and database schemas.
- Composite same-file foreign key resolution allows clients to onboard entire operations (accommodations, staff, reporting hierarchies, salaries, and shift rules) in a single workbook upload.
- Guarded rollback prevents orphan records and preserves database referential integrity.

## Consequences
- `backend/src/fw/modules/imports/` and `backend/src/fw/modules/payroll/` modular monolith services handle import batches and salary structures.
- Alembic migration `0004_import_and_salary.py` creates `import_batches`, `import_rows`, and `employee_salary` tables.
- Pure business rules in `backend/src/fw/rules/imports/` and `backend/src/fw/rules/payroll/salary.py` enforce cell semantics, normalizations, and salary arithmetic without database or framework ties.
- React web dashboard provides `/imports` (upload, preview diffs, commit, history, error download) and `/salary-structures` (active portions, last change deltas, revision modals).

