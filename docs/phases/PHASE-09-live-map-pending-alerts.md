# PHASE-09 - Live map, pending visits, alerts and documents

**Depends on:** PHASE-08

## Goal
Supervision tools: live map of last known positions, pending-visit follow-up, alerts, document-expiry section, dashboard tiles.

## Context (read only these)
- `AGENTS.md`
- `.agents/rules/*`
- `docs/decisions/decision-register.md` (the rows named below)
- `docs/12-reports.md` (sections 3.10, 3.14, 4, 5)
- `docs/13-architecture.md` (section 12 live positions)
- `docs/05-attendance-engine.md` (6c, 10)
- `docs/07-data-model.md` (employee_last_position, pending_visits, alerts)
- `docs/08-api-spec.md` (live, pending visits, alerts)
- `docs/10-ui-views.md` (3.2, 3.13, 3.14, 3.15)
- DEC-31, DEC-32

## Deliverables
- `employee_last_position` (newest-wins), SSE stream with ticket and polling fallback
- Live map screen: markers, state, two ages (event and last contact), polygons, clustering
- Pending visits detection at day close, follow-up workflow, reminders
- Alerts: tracking interrupted, no activity, stale device, document expiry, cover needed; alert centre
- Documents (expiry) screen for Admin; dashboard tiles (today's attendance, active/offline, pending visits, late arrivals, OT today)

## Out of scope
- Transport (Phase 10)

## Checklist (tick each before asking for review)
- [x] A late upload never overwrites a newer position
- [x] Active/offline states follow `live_active_window_minutes`
- [x] LOCATION_DISABLED raises an alert to in-scope supervisors/engineers; ENABLED clears it
- [x] Pending visit lifecycle works and reminders fire
- [x] Expiring documents list and alert at the configured lead days
- [x] Every view of live location is audit-logged
- [x] Docs updated in the same change (`.agents/rules/documentation.md`), ADR written for any design decision, CHANGELOG entry
- [x] Pull request opened with the template; nothing merged by the agent

## Demo script
- Run the simulator, watch markers move and go offline, turn location off and receive the alert.

## When done
Ask the owner to review, merge, then set this phase to **done** in `phases/README.md`.
