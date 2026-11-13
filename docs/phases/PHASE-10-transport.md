# PHASE-10 - Drivers and transport runs

**Depends on:** PHASE-07 (needs Phase 05 for schedules)

## Goal
Drivers section with vehicles and daily runs synced to drivers and workers.

## Context (read only these)
- `AGENTS.md`
- `.agents/rules/*`
- `docs/decisions/decision-register.md` (the rows named below)
- `docs/design/D5-transport-and-drivers.md`
- `docs/07-data-model.md` (Transport)
- `docs/08-api-spec.md` (Transport)
- `docs/09-mobile-sync-contract.md` (TRANSPORT_RUN)
- `docs/10-ui-views.md` (3.17)
- DEC-44

## Deliverables
- Vehicles, runs, stops, passengers; validation against the schedule
- Suggest from schedule, copy day/week, publish
- TRANSPORT_RUN sync entity (driver sees all, passenger sees own)
- Roster remarks column fed from runs; driver run sheet report
- Flag when a reassignment changes a worker on a published run

## Out of scope
- Route optimisation or maps navigation

## Checklist (tick each before asking for review)
- [x] A day of runs can be suggested, edited and published
- [x] Driver phone receives stops and passengers; passenger receives driver, vehicle, own stop
- [x] A worker cannot be on two morning runs
- [x] Unassigned scheduled workers are listed
- [x] Run sheet prints correctly
- [x] Docs updated in the same change (`.agents/rules/documentation.md`), ADR written for any design decision, CHANGELOG entry
- [x] Pull request opened with the template; nothing merged by the agent

## Demo script
- Suggest runs for tomorrow, adjust, publish, and read them through the simulator as driver and passenger.

## When done
Ask the owner to review, merge, then set this phase to **done** in `phases/README.md`.
