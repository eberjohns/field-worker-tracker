# PHASE-08 - Events and attendance

**Depends on:** PHASE-07

## Goal
Raw events become visits, gaps and a versioned daily attendance record with planned vs actual, variations, overtime and review.

## Context (read only these)
- `AGENTS.md`
- `.agents/rules/*`
- `docs/decisions/decision-register.md` (the rows named below)
- `docs/05-attendance-engine.md`
- `docs/design/D3-time-rules-and-attendance-report.md`
- `docs/03-business-rules.md` (BR-AT-*, BR-PY-05)
- `docs/07-data-model.md` (mobile_event_logs, site_visits, tracking_gaps, attendance_*)
- `docs/08-api-spec.md` (events, attendance)
- `docs/09-mobile-sync-contract.md` (section 7)
- `docs/decisions/005-immutable-events-versioned-calculations.md`
- DEC-01, DEC-04, DEC-05, DEC-17, DEC-24, DEC-41, DEC-43, DEC-49

## Deliverables
- Event ingestion (idempotent, validation, clock skew), PostGIS enrichment and verdicts
- Visit and gap building; unaccounted time; estimated exit
- Daily calculation (planned from time rules, actual, variations in total and worked time, break rule, grace, status, OT1/OT2 per the final rule), versioning by input hash, recalculation triggers
- Review routing: AUTO vs PENDING_REVIEW; named review reasons; comments (Supervisor) and approvals (Engineer); rows added to the approvals inbox
- Daily attendance table in the client's layout; attendance detail with timeline and map; exceptions queue
- Watchdogs: no activity, stale device
- Driver (accommodation to accommodation), workers without accommodation (n/a), supervisors by site visits

## Out of scope
- Live map and pending visits (Phase 09)

## Checklist (tick each before asking for review)
- [ ] Simulator scenarios A-H in 05 produce exactly the documented results (incl. the client's 12:00/09:00 vs 11:30/08:30 example)
- [ ] Replaying a batch creates no duplicates
- [ ] Rows with no variation, flag or OT are AUTO
- [ ] Recalculation creates a new version; approvals point to versions
- [ ] Weekly-off or unassigned work is all OT1; holiday/Sunday all OT2; beyond-standard OT1 otherwise
- [ ] Late events do not change dates in an approved payroll month
- [ ] Events table is append-only for the app role
- [ ] Docs updated in the same change (`.agents/rules/documentation.md`), ADR written for any design decision, CHANGELOG entry
- [ ] Pull request opened with the template; nothing merged by the agent

## Demo script
- Replay a simulated day with a late arrival, read the attendance row, comment as supervisor, approve as engineer.

## When done
Ask the owner to review, merge, then set this phase to **done** in `phases/README.md`.
