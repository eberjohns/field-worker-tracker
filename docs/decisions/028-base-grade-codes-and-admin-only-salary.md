# ADR-028: Base grade codes, budget warnings, Admin-only salary data

- **Status:** Accepted
- **Date:** 2026-11-23
- **Batch:** 5.3b (`fix/batch5.3b`), migration `0022_base_grade_codes`
- **Register:** DEC-58 (new), DEC-47 (tightened), DEC-06 (future salary rows)

## Context
PR #23 stored revision grade lines with the revision code glued on (`G3C-R2`) while job items held `G3C`.
The budget lookup missed and silently used a hard-coded 10.00/hour. Import normalisation removed hyphens
(`G3C-R2` -> `G3CR2`) and guessed at forms like `G3C26`. The client meeting of 19 Nov (item 10) asks to
*show* `G3C-2026` for the 2026 revision. Payroll also read setting names that are never seeded
(`visa_provision` instead of `provision_visa`, `ot_divisor` instead of `standard_ot_divisor_hours`)
and fell back to constants. Engineers could read revision lines, payroll runs and records (salaries).

## Options considered
1. Keep suffixed codes everywhere and match by stripping at lookup time.
2. **Store the base code everywhere; show the suffix only.**
3. A separate grades table (deferred to the managed-lists batch 5.1c).

## Decision
- One stored form: the **base code** (`G3C`, `G16A`, `G25`). `fw.rules.grades.base_grade_code()` removes only
  suffixes it recognises for certain: `-YYYY`, `-R<n>`, and a hyphen inside the code (`G5-C`). Anything
  else (`G3C26`, `G3CR2`, `S1`) is rejected with `INVALID_GRADE_CODE`; nothing is guessed.
- `salary_revisions.suffix_label` (default: year of `effective_from`) gives the display form
  `G3C-2026` (`display_grade_code` on revision lines).
- Budget: no fallback rate. A job item whose grade has no line in the revision is left out of the
  totals and reported as a `MISSING_GRADE_RATE` warning with its hours.
- Payroll and salary structures read the seeded setting names and stop with `SETTING_MISSING` when a
  money setting has no value. No constants.
- Future salary rows (DEC-06): hard delete only after the site-local today, full-row audit snapshot;
  later `CREW_BREAK` rows re-copy their amounts after an edit or delete; `CREW_BREAK` rows cannot be
  edited or deleted directly (`CREW_BREAK_ROW_LOCKED`).
- DEC-47: revision lines, revision template export, payroll runs, run detail, issues and records are
  Admin only. Engineers' imports skip the salary sheets (`SHEET_ADMIN_ONLY`) and money settings in
  Company_Settings (`SETTING_ADMIN_ONLY`) without storing their values; their template leaves them out;
  they cannot commit or roll back a batch that writes such data. The worker's own payslip
  (`/mobile/me/payroll`, `/payroll/my-records`) is unchanged (mobile contract).
- `GET /grades` returns the base codes in use (codes only) for all dropdowns.
- profile-details: grade validated; `staff_grade_description` must be on the controlled list and is locked
  for Supervisors, Superintendents and Engineers (meeting 19 Nov); a future `effective_from` is rejected
  (`FUTURE_PROFILE_CHANGE_NOT_SUPPORTED`); `actor_role` is stored.

## Why
One stored form removes every string-matching special case and makes the budget correct by construction.
Rejecting unknown forms surfaces bad data instead of hiding it. Money must come from settings
(`.agents/rules/time-and-money`), and salary data is Admin only under DEC-47.

## Consequences
- Draft payroll runs change when recalculated: provisions now follow settings (842 instead of the old 550).
- Import files with forms like `G3C26` now fail preview with `INVALID_GRADE_CODE` and must be corrected.
- After "Reset database" (which deletes company settings) payroll stops with `SETTING_MISSING` until
  Company_Settings is imported again.
- Migration 0022 cannot restore removed suffixes on downgrade (data only).
- Docs: `docs/07`, `docs/08`, `docs/11`; register DEC-58.
