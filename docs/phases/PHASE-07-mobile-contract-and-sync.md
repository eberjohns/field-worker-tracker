# PHASE-07 - Mobile contract, login and sync

**Depends on:** PHASE-06

## Goal
The mobile team can build against a working contract: login, device binding, snapshot/changes/ack, DAY_PLAN, events endpoint skeleton, simulator.

## Context (read only these)
- `AGENTS.md`
- `.agents/rules/*`
- `docs/decisions/decision-register.md` (the rows named below)
- `docs/09-mobile-sync-contract.md`
- `docs/decisions/003-sync-change-log.md`
- `docs/07-data-model.md` (sync_changes, registered_devices, consent)
- `docs/08-api-spec.md` (mobile tag notes)
- `docs/13-architecture.md` (section 4 domain events)
- `.agents/skills/add-synced-entity/SKILL.md`
- DEC-53, DEC-35

## Deliverables
- Mobile auth (employee ID + password, forced change, device binding, mismatch handling), consent endpoints, policy text endpoint
- Change log module `sync`: domain-event handlers writing `sync_changes` in the same transaction; snapshot, changes, ack, heartbeat, resync floor, nightly window extension
- Entities: PROFILE, SETTINGS, DAY_PLAN (resolved planned times, alarm time, markers), SCHEDULE_ITEM, JOB, SITE_BOUNDARY (with geofence circle), ACCOMMODATION
- Push adapter (FCM + null) for the nudge
- Device status in the web (last seen, sync lag, bindings, reset)
- `openapi-mobile.json` export and GPS **event simulator** (tools/); sample sites and test accounts
- Events batch endpoint accepting and validating events (processing in Phase 08)

## Out of scope
- Event processing and attendance (Phase 08)
- Transport entity (Phase 10)

## Checklist (tick each before asking for review)
- [x] A simulated phone logs in, changes password, snapshots, receives a schedule change as a delta and acks
- [x] Second device is refused; Admin reset allows rebinding
- [x] Cursor too old triggers resync
- [x] A holiday/season change updates DAY_PLAN and alarm times
- [x] `openapi-mobile.json` generated in CI; contract changelog updated
- [x] Data from other workers never appears in a worker's sync
- [x] Docs updated in the same change (`.agents/rules/documentation.md`), ADR written for any design decision, CHANGELOG entry
- [x] Pull request opened with the template; nothing merged by the agent

## Demo script
- Run the simulator through login, snapshot, a roster change and an ack; show the device sync lag in the web.

## When done
Ask the owner to review, merge, then set this phase to **done** in `phases/README.md`.
