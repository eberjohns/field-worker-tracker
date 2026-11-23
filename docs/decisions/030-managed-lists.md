# ADR-030: Managed lists for staff types and grade codes

- **Status:** Accepted
- **Date:** 2026-11-23
- **Batch:** 5.1 C (`feat/batch5.1c-managed-lists`), migration `0024_lookup_values`
- **Register:** DEC-60 (new); replaces the "controlled list" part of DEC-22; builds on DEC-58 (base grade codes)
- **Amended:** 2026-11-23, owner decision (see the end); `fix/test-db-isolation-and-lists`, migration `0025_grade_list_from_revisions`

## Context
The client meeting of 19 Nov (item 2) asks for Grade Code and Designation (`staff_grade_description`)
dropdowns "populated with the unique values already available in the system", everywhere they are
used. Staff types were a hard-coded set of 16 in the server (`CONTROLLED_SGDS`) and the web, so a new
trade needed a release. Grade dropdowns showed codes in use (Batch 5.3b) with no way to add one. Job
items rejected unknown staff types, employees accepted anything, and the Job_Items import only warned.

## Options considered
1. Keep code constants and add values by release.
2. Free text with suggestions (no list).
3. **One table of managed values, seeded from what is in use, with add on screen and deactivate.**

## Decision
- **Table `lookup_values`** (`list_key` = `staff_grade_description` or `grade_code`, `value`,
  `value_key` = lower case without spaces, unique per list; `source` SEED/SCREEN/IMPORT; `is_active`).
  Migration 0024 seeds staff types from the former controlled list plus values on employees and job
  items, and grade codes from employees, job items and revision lines (base codes only).
- **Adding (Admin, Engineer):** trimmed, spaces collapsed; duplicates ignoring case and spaces are
  refused (`LOOKUP_DUPLICATE`); a known alias or a close spelling asks "Did you mean …?" and needs "Add
  anyway" (`LOOKUP_NEAR_MATCH`). Grade codes must parse as DEC-58 base codes; a grade with no line in an
  active revision is added with the warning `NO_REVISION_LINE` (codes only, no money). Audited.
  *(Superseded by the amendment below.)*
- **Deactivating (Admin only):** the value leaves the dropdowns and new uses are refused
  (`LOOKUP_VALUE_INACTIVE`); records that already use it keep it and can still be saved. Never deleted.
- **Validation on every screen** (job items, employee create and update, grade change, profile details)
  against the active list: `INVALID_STAFF_GRADE_DESCRIPTION` / `UNKNOWN_GRADE_CODE` with a hint.
- **Imports:** an unknown staff type is an **error** with a hint (staff types are added on screen); aliases
  resolve on every sheet. A valid grade code that is not in the list is a **warning**
  (`GRADE_ADDED_TO_LIST`) and joins the list on commit (plan approved 23 Nov: a fresh or reset database has no
  grades, and they arrive with Employees, Job_Items and revision lines).
- **Reset database** clears both lists and re-seeds the staff types.
- **Module** `fw.modules.lookups` (own layer between `org` and `settings | identity | audit`); routes in
  `fw.api.lookups`, which also lists values in use that are missing from the table.
- **Web:** one `<LookupSelect>` (searchable, last option "Other – add new…") wherever a staff type or
  grade is chosen; a Managed Lists tab in Settings.

## Why
One list per field gives the client's "unique values already in the system" and lets them grow it
without a release, while duplicates and misspellings ("Gardner Helper") are stopped where they start.
Keeping staff types strict in imports avoids silent new trades from a typo; grades are format-checked,
so adding them from imports is safe and keeps a fresh install importable.

## Consequences
- A Job_Items row with an unknown staff type is now an import error (it used to be a warning and was
  saved). An alias on the Employees sheet now resolves (it used to fail as `INVALID_ENUM`).
- `GET /grades` and `GET /settings/staff-grades` return the managed lists (kept, deprecated).
- The import template's Lists sheet is filled from the lists when downloaded.
- Tests register the grade codes they use (a fresh database seeds none).

## Amendment, 23 Nov 2026 (owner decision)
The first version let Admin and Engineer add values from any dropdown and let imports add grade
codes. The owner changed that the same day:

- **Plain dropdowns.** Staff type and grade dropdowns (job item form, Add Worksite rows, employee
  create, profile edit) have no "Other – add new…" and no search. The record's current value stays
  selectable, marked "(not in list)" when it has left the list.
- **Staff types:** only Admin adds, deactivates and reactivates them, in Settings > Managed Lists
  (`POST /lookups/staff_grade_description` is Admin-only; Engineers get 403). Imports unchanged: an
  unknown value is an error with a hint.
- **Grade codes come only from salary revisions.** The grade list is the base codes with a line in
  an ACTIVE revision. `POST` and `PATCH /lookups/grade_code` return 422 `GRADE_FROM_REVISION_ONLY`;
  the `NO_REVISION_LINE` warning is gone. Org and jobs validate grades but sit below payroll, so the
  list stays in `lookup_values` and **only payroll writes it**: `PayrollService.refresh_grade_list`
  runs after every change to revisions (create, import commit; reset clears both) and calls
  `LookupService.sync_grades`, which adds codes (source `REVISION`), deactivates codes no active
  revision has, and reactivates returning ones (audited `GRADE_LIST_SYNCED`). Migration 0025
  rebuilds the grade rows this way.
- **Imports:** a grade on Employees or Job_Items with no line in an active revision, in the
  database or in the same file's Salary_Revision_Lines, is an error `UNKNOWN_GRADE_CODE` with a
  hint. `GRADE_ADDED_TO_LIST` is removed; nothing is ever added to a list by import.
- **Groups and zones** (client meeting item 3): the group and zone dropdowns in Add Worksite and the
  worksite edit get "Other – add new…" (Admin, Engineer). It saves at once and selects the new value.
  A group needs only its name: the next free 3-digit code after the highest in use is generated
  (151 -> 152; past 999 the lowest free from 100). A zone needs code and name. Duplicate names
  (ignoring case and spaces) and codes are refused (409 `DUPLICATE_NAME`, `DUPLICATE_CODE`); a near
  name gives 422 `NEAR_MATCH` until confirmed. A new group code given in an import or the API must
  be 3 digits (`INVALID_GROUP_CODE`); existing groups keep their codes. The worksite edit can now
  change the group and zone (`PATCH /worksites/{id}` applies `group_id`/`zone_id`).

Why: a grade without a revision line has no rate, so allowing one anywhere else only produced
budget gaps; keeping staff types with Admin keeps one owner for the vocabulary. Groups are named by
people, numbered by the system, which is how the client's sheets use them (3-digit codes).
