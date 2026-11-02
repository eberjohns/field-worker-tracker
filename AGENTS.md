# Field Worker Tracker (FWT)

Backend (FastAPI + PostgreSQL/PostGIS) and a web dashboard (React) that plan field work, collect location events from workers' phones, calculate attendance and payroll, and produce reports. The worker **mobile app is built by another team**; it only collects location events and shows data we sync. We publish its contract (`docs/09-mobile-sync-contract.md`).

## How to work
1. The system is built **phase by phase** (`docs/phases/README.md`). One phase per conversation. Use the `start-phase` skill.
2. Read, in order: this file, `.agents/rules/*`, the phase file, and **only** the files in its Context section.
3. Ask questions, then plan, then **wait for approval** before writing files.
4. Work on a branch, open a pull request, never merge. Use `finish-phase` when done.
5. Documentation is part of every change. Record design decisions as ADRs (`write-adr`). Before adding any dependency use `add-dependency`.
6. The client requirements (`docs/reference/field_workforce_system_requirements.md`) and the decision register (`docs/decisions/decision-register.md`) are the source of truth. If documents disagree, stop and ask. Never change a requirement silently.
7. Items marked PROPOSED in the register are built behind a setting, never hard-coded.

## Golden rules
1. Modular monolith: a module imports another only through its public `__init__.py`; layers per `docs/13-architecture.md`.
2. Business rules are pure Python in `backend/src/fw/rules/` (no database, no HTTP).
3. Outside services (push, email, storage) only through ports and adapters.
4. Raw location events are immutable. Attendance and payroll are versioned; approved payroll is a snapshot.
5. Referenced records are deactivated, never deleted. Imports never delete.
6. All timestamps UTC; the work date is the site's local date. Money is `Decimal`; durations whole minutes.
7. Configuration is effective-dated: attendance for a date uses the settings and time rules in force on that date.
8. Never run anything against a database other than the local docker-compose one. Never commit secrets or client data files.
9. Mobile contract fields are never renamed or removed without a version bump and the owner's approval.

## Repository layout
```
backend/   FastAPI app (src/fw/...), Alembic migrations
web/       React dashboard
docs/      all documentation (start at docs/README.md)
.agents/   rules and skills for the AI agent
infra/     docker-compose, deployment files
tools/     GPS event simulator, template generator
```
