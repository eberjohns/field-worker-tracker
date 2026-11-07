# PHASE-06 - Leave, temporary reassignment and approvals

**Depends on:** PHASE-05

## Goal
Leave and temporary reassignments work end to end with Engineer approval, cover-needed alerts and the approvals inbox.

## Context (read only these)
- `AGENTS.md`
- `.agents/rules/*`
- `docs/decisions/decision-register.md` (the rows named below)
- `docs/design/D2-leave-and-reassignment.md`
- `docs/04-scheduling-engine.md` (sections 6, 9)
- `docs/03-business-rules.md` (BR-SC-04, BR-SC-05)
- `docs/07-data-model.md` (leave_requests, reassignment_requests, alerts)
- `docs/08-api-spec.md` (leave, reassignment requests, approvals)
- `docs/10-ui-views.md` (3.16)
- DEC-43, DEC-46

## Deliverables
- Leave: supervisor records, engineer approves, TO_BE_COVERED slots, leave-taken counts, optional Leave import sheet
- Reassignment requests (REPLACE, MOVE, ADD, CANCEL) with notice-period validation (3 days), preview of worker hours, approval, effect on Scheduled Work (origin EXCEPTION, originals kept)
- Approvals inbox (leave, reassignments; attendance rows added in Phase 08) with counts and badge
- Cover-needed list and daily alerts; notifications via the adapter
- Roster/coverage badges for covered slots

## Out of scope
- Phone sync of the changes (Phase 07)

## Checklist (tick each before asking for review)
- [x] A request under 3 days is refused (any role)
- [x] Approval writes rows and keeps originals; rejection needs a reason
- [x] Leave approval creates uncovered slots and alerts
- [x] Overlapping leave refused; cancelling restores slots
- [x] Leave taken counts per worker/type/year correct
- [x] Engineer sees only their scope; Admin all
- [x] Late approval flagged LATE_APPROVAL
- [x] Docs updated in the same change (`.agents/rules/documentation.md`), ADR written for any design decision, CHANGELOG entry
- [x] Pull request opened with the template; nothing merged by the agent

## Demo script
- Record leave, approve it, request a cover 3+ days ahead, approve it, see the badge on the roster.

## When done
Ask the owner to review, merge, then set this phase to **done** in `phases/README.md`.
