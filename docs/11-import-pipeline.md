# 11 - Bulk Import Pipeline

The client's original files are not normalized. We give them the **template workbook** (`import-templates/FieldWorkerTracker_Import_Template_v1.0.xlsx`). The importer reads the template; an optional converter (section 8) can read the client's legacy files.

## 1. Principles
- One entity per sheet, flat rows, no merged cells, ISO dates, IDs as text.
- **Idempotent**: re-uploading the same file creates nothing new. Rows match on their natural key and are created, updated, or reported unchanged.
- **Preview before commit**: nothing is written until the Admin confirms.
- **All-or-nothing commit** per batch (one database transaction).
- The importer **never deletes** records that are absent from the file. Deactivation is a UI action.
- Rows with anything in column A (`#`) are ignored (examples and comments).

## 2. Flow and the import experience
```mermaid
flowchart LR
  U[Upload xlsx] --> P[Parse sheets by header row 4]
  P --> N[Normalize: trim, aliases, grade suffix, types]
  N --> V[Validate + compare with existing records]
  V --> R[(import_rows)]
  R --> PV[Preview: new / updated / unchanged / clashes]
  PV -->|Admin confirms| C[Commit in one transaction]
  C --> S[Summary + downloadable result]
```
1. Upload (`POST /imports`): Admin only. File hashed, batch created, template version detected.
2. Parse and normalize (grade codes `G5-C`, `G5C`, `G5C26` all become `G5C`).
3. **Compare with the database by primary key** and classify every row:
   - **NEW**: key not in the database -> will be created.
   - **UPDATED**: key exists and values differ -> the preview shows **old value -> new value per field**.
   - **UNCHANGED**: key exists and nothing differs.
   - **REACTIVATED**: key matches a deactivated record.
   - **CLASH / ERROR**: duplicate key in the file with different data, reference not found, invalid value, forbidden change (shown with a stable code).
4. **Preview** shows counts per sheet and a filterable row table; Admin can download it. **Nothing is written until Admin confirms.**
5. Commit applies everything in one transaction; the result lists what was created and updated. Each change is audited with the batch ID.
6. **Cell rules (stated on the template README and the preview screen)**: a **blank cell keeps the existing value**; a cell containing **`_`** (single underscore) **clears** the value (only allowed for optional fields).
7. **Nothing is ever deleted** by an import; records absent from the file are untouched. Records already used (history) are **deactivated on screen**, never deleted; unused records may be deleted by Admin.
8. Records imported can be inspected and edited in their own sections (employees, worksites, ...); key fields (worker ID, job number) can be corrected on screen by Admin (history links to internal IDs); an import cannot rename a key (a changed key is a new record).

## 3. Sheet registry and commit order
One registry in code (`modules/imports/registry.py`) defines sheets, columns, types, enums, keys and validators. **The template workbook, validators and docs are generated from it** (see `.agents/skills/import-column`).

**Primary keys**
| Sheet | Primary key |
|---|---|
| Groups / Zones | group_code / zone_code |
| Accommodations | accommodation_code |
| Employees | tally_id |
| Employee_Reporting | employee_tally_id + manager_tally_id + relationship |
| Employee_Salary | tally_id + effective_from |
| Worksites | job_number |
| Job_Items | job_number + sub_item_code |
| Leave | tally_id + from_date |
| Public_Holidays | holiday_date + country |
| Salary_Revisions / Salary_Revision_Lines | revision_code / revision_code + grade_code |
| Company_Settings | setting_key + country + effective_from |
| Time_Rules | rule_name + scope_type + scope_id + start_date |

**Commit order**: 1 Groups, 2 Zones, 3 Accommodations, 4 Employees (also creates document expiry dates), 5 Employee_Reporting, 6 Employee_Salary, 7 Worksites, 8 Job_Items, 9 Leave, 10 Public_Holidays, 11 Salary_Revisions, 12 Salary_Revision_Lines, 13 Company_Settings, 14 Time_Rules. Employees are linked afterwards through Employee_Reporting, so row order never matters. Boundaries are **not** imported (they appear in the boundary setup queue). Salary rows with no `effective_from` take effect from the first day of the next payroll month.

## 4. Normalization rules
- Trim whitespace, collapse internal spaces, normalize non-breaking spaces. IDs stay text.
- **Staff Grade Description**: case-insensitive match to the controlled list, else the `SGD_Aliases` table (`Gardner Helper` -> `Gardener Helper`, `Irrigation Technitian` -> `Irrigation Technician`, `Forman With DL` -> `Foreman With DL`, `Superintent` -> `Superintendent`...). Alias use -> `SGD_ALIAS_APPLIED` (info). Unknown value -> `SGD_UNKNOWN` (warning; stored, flagged for review).
- **Booleans** `Y/N`. **Dates** `YYYY-MM-DD` (Excel date cells accepted). **Times** `HH:MM`. Decimals accept `.` only.
- **Frequency** is structured in the template. For the legacy converter, free text is parsed:

| Pattern (case/space-insensitive) | Result |
|---|---|
| `daily` + 6 per week | WEEK, 6, 1 |
| `weekly`, `one time / week` | WEEK, 1, 1 |
| `one time / 2 week` | WEEK, 1, 2 |
| `two/three time / week` | WEEK, 2/3, 1 |
| `monthly` | MONTH, 1, 1 |
| `two time / month` | MONTH, 2, 1 |
| `quarterly`, `quaterly` | QUARTER, 1, 1 |
| `N time / year` (`three`, `six`, `four`) | YEAR, N, 1 |

- **Job number**: exactly `[0-9]{2}[A-Z][0-9]{5}`. Anything else -> `BAD_JOB_NUMBER` error with the original text (combined numbers like `82A11204 & 82B11204`, suffixes like `12A14301 - 4`). (BR-JB-01)
- **Items with 0 activities and 0 hours** in legacy files are placeholders and are skipped by the converter.

## 5. Validation codes
Stable codes shown in the preview and error report.

| Code | Level | Meaning |
|---|---|---|
| HEADER_MISSING / TEMPLATE_VERSION_MISMATCH | error | headers differ from the registry |
| REQUIRED_MISSING | error | required value empty |
| INVALID_TYPE / INVALID_DATE / INVALID_ENUM / NEGATIVE_VALUE | error | wrong type, date, enum value or sign |
| END_BEFORE_START | error | end date before start date |
| DUPLICATE_KEY_IN_FILE | error | same natural key twice with different data |
| REFERENCE_NOT_FOUND | error | group, zone, accommodation, worksite, employee, revision not found |
| SELF_REFERENCE / HIERARCHY_CYCLE | error | reporting loop |
| BAD_JOB_NUMBER | error | job number not a single valid number |
| MULTIPLE_SUPERVISORS | error | an employee has more than one SUPERVISOR link |
| BUDGET_INCOMPLETE | info | job items without a planned grade: the calculated contract budget is incomplete |
| BAD_FREQUENCY | error | unit/count/interval/pattern inconsistent (pattern length != count) |
| ENGINEER_MISSING | warning | worker has no engineer |
| HIERARCHY_ROLE_MISMATCH | warning | referenced supervisor/superintendent/engineer has a different role |
| SGD_ALIAS_APPLIED | info | alias normalized |
| SGD_UNKNOWN | warning | SGD not in the controlled list |
| ACTIVITIES_MISMATCH / ANNUAL_HOURS_MISMATCH | info | declared figures differ from the calculated ones (the calculated value is used) |
| GRADE_CODE_NOT_IN_REVISION | warning | employee grade code has no salary line in the active revision |
| RECONCILIATION_MISMATCH | warning | derived salary values differ from `client_*` by more than 0.01 |
| PLACEHOLDER_ID | warning | tally id marked as placeholder in notes |
| UNCHANGED / UPDATED / CREATED | info | action the commit will take |
| NEW / UPDATED / UNCHANGED / REACTIVATED | info | classification shown in the preview (old -> new values for UPDATED) |
| KEY_CLASH | error | same key twice in the file with different data |
| CLEAR_ON_REQUIRED | error | `_` used on a required field |
| SALARY_MISSING | warning | an employee with no salary structure (payroll will flag it) |
| STANDARD_HOURS_MISSING | info | salary row without standard hours (default 8 used) |

## 6. Commit behaviour
- Upsert by natural key inside one transaction. Fields that are blank in the file **do not overwrite** existing values unless the column is marked "blank clears" in the registry (none in v1).
- Each created/updated record writes an audit entry with the batch id.
- Sync fan-out: committing changes that affect workers (profile, jobs, boundaries) writes `sync_changes` in the same transaction.
- Employees with a web role get an account and an invite email (queued after commit, via the email port).
- Occurrence generation for new/changed Job Items is queued after commit.
- **Rollback**: allowed only while nothing created by the batch is referenced by later records (scheduled work, events, payroll). Otherwise the UI offers deactivation instead.

## 7. Reconciliation outputs
After commit, show a reconciliation page for the Admin: counts by entity vs rows in the file, jobs per group/zone, employees per supervisor, SGD coverage (job items needing an SGD vs employees holding it), annual hours totals, and salary revision derived-vs-client totals.

## 8. Legacy converter (optional tool, `tools/legacy_converter/`)
Reads the client's four original workbooks and writes a filled template for the Admin to review. We run it ourselves, assign IDs to engineers (who have none), turn merged cells into explicit `Employee_Reporting` links (several superintendents/engineers allowed) and send the normalised workbook back for the client to verify. Parsing rules learned from the real files:
- **Staff hierarchy**: the Supervisor column is a **merged block** over each supervisor's team and the superintendent column is merged across a whole sheet - resolve merged cells before reading. Supervisor/superintendent cells hold `Name (GradeCode) TallyID [D/L]` strings: extract the last 4-digit number as the Tally ID. Names end with `- IP`/`- TS` (just labels, dropped) and optionally `D/L` (= driver): split into `name` and `is_driver`. The Engineers column holds names (`Renin`, `Mohammed`, `Renin/ Mohammed`) with no IDs: **we assign each engineer an ID**; `A/B` yields two ENGINEER links. Every relationship becomes a row in `Employee_Reporting` (employee, manager ID, relationship); a person under two superintendents gets two SUPERINTENDENT rows. The same Tally ID appears on several sheets; consolidate on Tally ID and report differences.
- **Site grouping**: clean table; group/zone codes are numeric. It has **no labour budget**: by default the contract budget is calculated from the job items; a manual whole-contract figure can be given in `labour_budget_amount`.
- **Job model**: only the current-year sheet (`2026`) is imported (to be confirmed). The job number appears only on the first row of each block; items follow (A, B, C...). Skip placeholder items (0 activities). The Tally numbers in the trailing columns are **ignored**: staff are assigned inside the system. The 'Permanent'/'Remote' column becomes `deployment_type`. The planned staff grade becomes `planned_grade_code` (used for the budget estimate). Frequencies are normalised to structured form; the calculated activities per year is used and any difference from the file is shown as info.
- **Salary review**: use the sheet that has Grade Codes (`Revised 2rd July 26`). Group header rows (`G7`, `G6`...) carry the group title and duty hours; the column the file labels `OH` is the **total provision**; FOT is a fixed amount paid as given (no logic). Provision columns J to Q become the per-grade provision columns.
Findings summary: `reference/client-data-findings.md`.
