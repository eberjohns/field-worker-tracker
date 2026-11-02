# PHASE-12 - Reports and the Generated Reports section

**Depends on:** PHASE-11

## Goal
All 16 reports, Excel export for every report, automatic month-end generation, generated-report history with proper names and visibility.

## Context (read only these)
- `AGENTS.md`
- `.agents/rules/*`
- `docs/decisions/decision-register.md` (the rows named below)
- `docs/12-reports.md`
- `docs/design/D4-month-end-and-reports.md`
- `docs/design/D3-time-rules-and-attendance-report.md` (daily table)
- `docs/07-data-model.md` (generated_reports)
- `docs/08-api-spec.md` (reports, generated-reports)
- `docs/10-ui-views.md` (3.9, 3.18)
- DEC-46, DEC-47

## Deliverables
- Report registry with typed filters, scope, columns, Excel/CSV/PDF formatters
- Reports not yet built: movement, site visits, utilization, transportation time, late/early, project attendance summary, monthly attendance, staffing gaps, document expiry, weekly roster, driver run sheet, payroll, provisions-staff-cost, job costing
- Month-end job generating the report set after the draft and final copies on approval
- Generated Reports section: list, filter, download again; names `<Company>_<Report>_<Country>_<Period>_generated-<date>.xlsx`; versions; visibility by role
- Notifications when ready

## Out of scope
- -

## Checklist (tick each before asking for review)
- [ ] Every report exports to Excel and respects scope
- [ ] Salary and cost reports hidden from Superintendents and Supervisors
- [ ] Month-end files appear automatically with the right names and versions
- [ ] Re-downloading an old file returns the same content
- [ ] Large exports run as background jobs
- [ ] Each report matches its definition in 12
- [ ] Docs updated in the same change (`.agents/rules/documentation.md`), ADR written for any design decision, CHANGELOG entry
- [ ] Pull request opened with the template; nothing merged by the agent

## Demo script
- Approve a payroll run and open the Generated Reports list; download the payroll-cost file.

## When done
Ask the owner to review, merge, then set this phase to **done** in `phases/README.md`.
