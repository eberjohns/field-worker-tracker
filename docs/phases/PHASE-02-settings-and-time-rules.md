# PHASE-02 - Settings, time rules and calendars

**Depends on:** PHASE-01

## Goal
All configuration is effective-dated and explainable: company settings, planned-time rules (company, team, drivers, individual, seasons), holidays, budget-only staff types, consent notice versions.

## Context (read only these)
- `AGENTS.md`
- `.agents/rules/*`
- `docs/decisions/decision-register.md` (the rows named below)
- `docs/03-business-rules.md` (BR-ST-*, section 10 settings catalog)
- `docs/design/D3-time-rules-and-attendance-report.md`
- `docs/07-data-model.md` (company_setting_values, time_rules, public_holidays, consent_policies)
- `docs/08-api-spec.md` (Settings, time rules, consent)
- `docs/10-ui-views.md` (3.10)
- `docs/decisions/008-effective-dated-configuration.md`
- DEC-03, DEC-21, DEC-35, DEC-41

## Deliverables
- Module `settings`: effective-dated values with country scope and history; defaults from the catalog
- Time rules model and **resolver** (employee > team > drivers > company; outdoor/indoor; season dates; blanks inherit) as pure code in `rules/`
- `GET /time-rules/resolve` explainer (which rule won)
- Public holidays per country
- Budget-only staff types setting (list pre-filled from job-item staff types later; here the setting and UI)
- Consent policy versions per language
- Web: Settings (company, time rules, holidays, budget-only types, default password, consent notice)
- Engineers can edit rules only for their scope

## Out of scope
- Attendance use of the rules (Phase 08)
- Import of settings/rules (Phase 03)

## Checklist (tick each before asking for review)
- [x] Resolver unit tests: company, team, driver, employee, season and outdoor/indoor precedence
- [x] The client example (05:00 / 06:00 / 0:30 / 15:30 / 17:00 => 12:00 total, 09:00 worked) computes
- [x] A change adds a new dated row; past dates still resolve to the old value
- [x] Engineer cannot edit another engineer's team rule
- [x] Banner and history view show effective dates
- [x] Docs 03/07/D3 updated
- [x] Docs updated in the same change (`.agents/rules/documentation.md`), ADR written for any design decision, CHANGELOG entry
- [x] Pull request opened with the template; nothing merged by the agent

## Demo script
- Add a Ramadan rule and a team rule, then use the explainer for a worker on two dates.

## When done
Ask the owner to review, merge, then set this phase to **done** in `phases/README.md`.
