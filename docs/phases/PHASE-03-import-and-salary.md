# PHASE-03 - Import framework, master data import and salary structures

**Depends on:** PHASE-02

## Goal
Admin can load master data from the template with a safe preview (new / updated with old->new / unchanged / clashes), and worker salary structures are stored with history.

## Context (read only these)
- `AGENTS.md`
- `.agents/rules/*`
- `docs/decisions/decision-register.md` (the rows named below)
- `docs/11-import-pipeline.md`
- `docs/design/D6-import-and-setup.md`
- `docs/06-payroll-and-cost.md` (sections 1-2)
- `docs/07-data-model.md` (import_batches, import_rows, employee_salary)
- `docs/08-api-spec.md` (Import, salary)
- `docs/import-templates/` (the template workbook)
- `.agents/skills/import-column/SKILL.md`
- DEC-51, DEC-39

## Deliverables
- Module `imports`: sheet registry (single source of truth), parser, normalizer (grade suffix, aliases), validators with stable codes, preview, atomic commit, result summary, history
- Template generator driven by the registry
- Cell rules: blank keeps, `_` clears (refused on required), never deletes; deactivation on screen
- Sheets: Groups, Zones, Accommodations, Employees (+ document dates), Employee_Reporting, Employee_Salary, Company_Settings, Time_Rules, Public_Holidays
- Salary structure: effective-dated rows, last change date and difference, history screen
- Web: import upload, preview with diffs and filters, commit, history; salary structures screen

## Out of scope
- Worksites, job items (Phase 04)
- Leave (Phase 06)
- Revision sheets (Phase 11)

## Checklist (tick each before asking for review)
- [ ] Uploading the sample template previews all sheets; re-upload is idempotent (all UNCHANGED)
- [ ] A file with duplicates, bad references and invalid values shows row-level codes
- [ ] UPDATED rows show old -> new per field
- [ ] `_` clears an optional field; blank leaves it
- [ ] Salary change records history and applies from the next month; difference is correct
- [ ] Commit is one transaction; nothing written before confirmation
- [ ] Template regenerates from the registry and matches `import-templates/`
- [ ] Docs updated in the same change (`.agents/rules/documentation.md`), ADR written for any design decision, CHANGELOG entry
- [ ] Pull request opened with the template; nothing merged by the agent

## Demo script
- Import the sample workbook, change two cells, re-upload and read the preview, commit, then open an employee's salary history.

## When done
Ask the owner to review, merge, then set this phase to **done** in `phases/README.md`.
