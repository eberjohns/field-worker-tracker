# PHASE-13 - Hardening, archive, backup and go-live

**Depends on:** all

## Goal
A system that can be operated safely: backups with restore drills, yearly archive, retention, security and privacy tooling, deployment per country.

## Context (read only these)
- `AGENTS.md`
- `.agents/rules/*`
- `docs/decisions/decision-register.md` (the rows named below)
- `docs/14-nonfunctional.md`
- `docs/legal/` (all five files)
- `docs/decisions/009-country-deployments-and-hosting.md`
- `docs/13-architecture.md` (sections 8-11)
- DEC-38, DEC-54, DEC-55, DEC-56

## Deliverables
- Production deployment to the chosen host (UAE stack), secrets, TLS, monitoring and alerts
- Backups with point-in-time recovery and a **documented restore drill**
- Yearly archive job: export, encrypt, checksum, downloadable encrypted copy, verified restore, purge; archive viewer
- Retention and anonymisation jobs per the agreed schedule
- Employee data export, consent withdrawal handling, audit of location views
- Security review and fixes, performance checks against 14, load test (300 workers)
- Runbooks: deploy, restore, incident (breach), sync failure; admin guide
- Go-live checklist including the human actions in `legal/01-human-actions.md`

## Out of scope
- Saudi stack (separate deployment later, same code)

## Checklist (tick each before asking for review)
- [ ] Restore drill completed and recorded
- [ ] Archive then restore of a sample year verified
- [ ] Performance targets in 14 met
- [ ] Security review items closed
- [ ] All human actions in legal/01 have an owner and status
- [ ] Pilot run with any team completed and compared with manual records
- [ ] Production deployment repeatable from the pipeline
- [ ] Docs updated in the same change (`.agents/rules/documentation.md`), ADR written for any design decision, CHANGELOG entry
- [ ] Pull request opened with the template; nothing merged by the agent

## Demo script
- Restore last night's backup to a scratch database; run the archive for a test year.

## When done
Ask the owner to review, merge, then set this phase to **done** in `phases/README.md`.
