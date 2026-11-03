# PHASE-01 - Access and people

**Depends on:** PHASE-00

## Goal
Users can log in with role-based, scope-limited access; Admin can manage people, reporting links, groups, zones and accommodations; everything is audited.

## Context (read only these)
- `AGENTS.md`
- `.agents/rules/*`
- `docs/decisions/decision-register.md` (the rows named below)
- `docs/02-roles-and-permissions.md`
- `docs/03-business-rules.md` (BR-EM-*, BR-CV-*)
- `docs/07-data-model.md` (employees, employee_reporting_lines, users, registered_devices, groups, zones, accommodations, employee_documents, audit_logs)
- `docs/08-api-spec.md` (Auth, Employees, Groups/Zones/Accommodations, Users)
- `docs/10-ui-views.md` (3.1, 3.3, 3.12)
- DEC-10, DEC-33, DEC-53

## Deliverables
- Modules `identity`, `audit`, `org`
- Login (username = employee ID), default password, forced change, lock after `default_password_max_days`, Admin-only reset, change own password
- Roles, `require_role`, reporting-scope filter built from reporting links (several superintendents/engineers)
- Employees CRUD, bulk update, hierarchy view, grade history, employment dates, `is_driver`, weekly off day, country
- Reporting links CRUD with validation (one supervisor, no cycles)
- Groups, zones, accommodations (without boundary yet), document expiry dates per employee
- Audit log writing and viewing
- Web: login, change password, employees list/detail (tabs), users admin, audit log
- Fictional seed data (never client data)

## Out of scope
- Import from Excel (Phase 03)
- Mobile login (Phase 07)
- Salary data (Phase 03)

## Checklist (tick each before asking for review)
- [x] Each role sees only its scope (matrix in 02) - verified with seed users
- [x] Every write creates an audit entry
- [x] Optimistic locking returns 409 on conflict
- [x] Hierarchy cycles and a second supervisor are refused
- [x] Default password forces a change; an unchanged account locks after the configured days
- [x] Admin can reset a worker to the default; non-Admin cannot
- [x] Docs 02/07/08 updated for any difference; CHANGELOG entry
- [x] Docs updated in the same change (`.agents/rules/documentation.md`), ADR written for any design decision, CHANGELOG entry
- [ ] Pull request opened with the template; nothing merged by the agent

## Demo script
- Log in as Admin, create a worker with two superintendents, log in as the supervisor and see only their team.

## When done
Ask the owner to review, merge, then set this phase to **done** in `phases/README.md`.
