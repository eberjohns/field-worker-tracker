# PHASE-05 - Planner: yearly plan and weekly roster

**Depends on:** PHASE-04

## Goal
Admin and Engineers build the year plan with standing assignments and see/adjust it as a weekly roster with allocated hours against standard hours.

## Context (read only these)
- `AGENTS.md`
- `.agents/rules/*`
- `docs/decisions/decision-register.md` (the rows named below)
- `docs/04-scheduling-engine.md`
- `docs/design/D1-planner.md`
- `docs/07-data-model.md` (standing_assignments, scheduled_work)
- `docs/08-api-spec.md` (roster, coverage, standing assignments, allocation)
- `docs/10-ui-views.md` (3.5)
- DEC-36, DEC-42, DEC-52

## Deliverables
- Module `scheduling`: standing assignments, generation of daily Scheduled Work, day markers (SKIPPED holiday, WEEKLY_OFF, ON_LEAVE, TO_BE_COVERED, FREE)
- Validation and warnings from 04 section 7 (PERMANENT exclusivity, standard hours, grade-group mismatch)
- Suggestions by grade group, exact staff type first
- Allocation endpoint (hours per day/week/month vs standard hours)
- Roster and Coverage endpoints; roster Excel export in the client's layout
- Web: Roster, Coverage, Year plan, assign panel, workers side panel, filters
- Standard hours read from salary structure (default 8) and time rules (Ramadan -2 h)

## Out of scope
- Leave/reassignment/approvals (Phase 06)
- Sync to phones (Phase 07)

## Checklist (tick each before asking for review)
- [x] Roster reproduces the client's sample week layout
- [x] Daily and weekly totals reconcile with the side panel
- [x] Holiday shows SKIPPED; weekly off and leave show markers; an unavailable slot shows TO_BE_COVERED
- [x] PERMANENT job blocks other assignments that day; REMOTE jobs combine up to standard hours
- [x] Over/under standard hours show warnings/info
- [x] Excel export opens with the same rows
- [x] Performance: roster for 300 workers loads in under 2 s
- [x] Docs updated in the same change (`.agents/rules/documentation.md`), ADR written for any design decision, CHANGELOG entry
- [x] Pull request opened with the template; nothing merged by the agent

## Demo script
- Create a standing team for a daily job, view the roster for a week with a holiday, assign a REMOTE job, export to Excel.

## When done
Ask the owner to review, merge, then set this phase to **done** in `phases/README.md`.
