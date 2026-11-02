# PHASE-11 - Month-end payroll and job budget

**Depends on:** PHASE-08

## Goal
Automatic draft payroll after month-end, re-run and Admin approval with immutable snapshots; job budget from the revision file.

## Context (read only these)
- `AGENTS.md`
- `.agents/rules/*`
- `docs/decisions/decision-register.md` (the rows named below)
- `docs/06-payroll-and-cost.md`
- `docs/design/D4-month-end-and-reports.md` (draft page)
- `docs/07-data-model.md` (payroll_runs, payroll_records, salary_revisions, salary_revision_lines, job_cost_allocations)
- `docs/08-api-spec.md` (payroll, salary)
- `docs/10-ui-views.md` (3.8)
- DEC-01, DEC-29, DEC-30, DEC-39, DEC-45

## Deliverables
- Pure payroll formulas in `rules/payroll` with unit tests (OT rates, gratuity, leave salary, provisions, HR OH, final total staff cost)
- Draft run job at `payroll_auto_run_delay_days`, re-run, issues, approve, snapshots, month lock
- Worker's own approved payroll endpoint for the mobile app (employee side only)
- Revision import sheets and budget calculation (grade cost with revision provisions, contract budget, manual override), actual allocation and variance
- Web: salary structures (from Phase 03 data), payroll runs, draft page, record detail, budget vs actual

## Out of scope
- Report files and the Generated Reports section (Phase 12)

## Checklist (tick each before asking for review)
- [ ] The documented example reproduces: OT1 rate (1100/208)*1.25 = 6.61, OT2 = 7.93
- [ ] Gratuity and leave salary use the formula for everyone
- [ ] Per-month provision = five provisions + gratuity + leave salary; HR OH 5% added to total staff cost for the final figure
- [ ] Approved run does not change when settings or later events change
- [ ] Engineers see their scope read-only; Supervisors see nothing
- [ ] Budget report states the provision basis difference
- [ ] Docs updated in the same change (`.agents/rules/documentation.md`), ADR written for any design decision, CHANGELOG entry
- [ ] Pull request opened with the template; nothing merged by the agent

## Demo script
- Generate a draft for the previous month, upload extra events, re-run, approve, then show the immutable record.

## When done
Ask the owner to review, merge, then set this phase to **done** in `phases/README.md`.
