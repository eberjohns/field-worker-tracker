# PHASE-04 - Sites, boundaries and job items

**Depends on:** PHASE-03

## Goal
All jobs and their items are defined, outdoor/indoor flagged, boundaries are drawn on the map, and occurrences exist.

## Context (read only these)
- `AGENTS.md`
- `.agents/rules/*`
- `docs/decisions/decision-register.md` (the rows named below)
- `docs/03-business-rules.md` (BR-JB-*)
- `docs/04-scheduling-engine.md` (sections 2-4)
- `docs/design/D6-import-and-setup.md` (boundary queue)
- `docs/07-data-model.md` (worksites, job_items, job_occurrences)
- `docs/08-api-spec.md` (Worksites, job items, boundary queue)
- `docs/10-ui-views.md` (3.4)
- `docs/decisions/006-map-stack-and-dependency-policy.md`, `docs/17-dependencies.md` (map rows)
- DEC-09, DEC-11, DEC-36

## Deliverables
- **Map-stack compatibility gate first** (ADR-006): MapLibre + react-map-gl + Terra Draw + Turf installed together, polygon drawn/edited/saved, satellite imagery checked for Dubai/KSA; pin or fall back as the ADR says
- Module `jobs`: worksites (job number format check, `is_outdoor`), job items (structured frequency, PERMANENT/REMOTE, planned grade, break override), occurrence generation (rolling horizon, idempotent), budget-only staff types excluded
- Boundary editor with place search, validity check, area; **boundary setup queue**; **copy boundary to other jobs**; accommodation boundaries
- Import sheets: Worksites, Job_Items (with registry/template update)
- Job item validation panel (calculated activities/annual hours, expected occurrences)
- Web: worksites list/detail, job item editor, boundary editor, queue

## Out of scope
- Assignments and scheduling (Phase 05)

## Checklist (tick each before asking for review)
- [x] Gate documented in ADR-006 and the dependency register
- [x] Frequency table in 04 gives the expected activities per year
- [x] Large hours split into 9-hour days (42.688 h = 4 x 9 + 6.688)
- [x] Regenerating keeps assigned/completed occurrences
- [x] Hyphenated or combined job numbers are rejected on import
- [x] Boundary queue counts progress; copy-to works; invalid polygons refused
- [x] Budget-only staff types never produce occurrences
- [x] Docs updated in the same change (`.agents/rules/documentation.md`), ADR written for any design decision, CHANGELOG entry
- [x] Pull request opened with the template; nothing merged by the agent

## Demo script
- Import two jobs with items, draw one boundary, copy it to the second, view occurrences for a month.

## When done
Ask the owner to review, merge, then set this phase to **done** in `phases/README.md`.
