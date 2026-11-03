# PHASE-00 - Foundation

**Depends on:** -

## Goal
A running, empty system: repository skeleton, local environment, CI, shared core code and verified dependencies. No business features.

## Context (read only these)
- `AGENTS.md`
- `.agents/rules/*`
- `docs/decisions/decision-register.md` (the rows named below)
- `docs/13-architecture.md` (sections 1-8)
- `docs/15-dev-process.md`
- `docs/17-dependencies.md`
- `docs/decisions/001-modular-monolith.md`, `002-stack-fastapi-react.md`, `006-map-stack-and-dependency-policy.md`, `009-country-deployments-and-hosting.md`

## Deliverables
- Monorepo layout from 13 section 3 (`backend/`, `web/`, `infra/`, `tools/`)
- docker-compose: PostGIS database, API, worker, web, mail catcher; `.env.example`
- FastAPI app factory, `/health` and `/health/ready`, settings via pydantic-settings (`DEPLOYMENT_COUNTRY`)
- Async SQLAlchemy session, Alembic baseline with the PostGIS extension
- `core`: RFC 7807 errors, clock, structlog, domain-event bus, audit hook
- `import-linter` contract for the module layers in 13 section 4
- CI workflow (ruff, pyright, import-linter, alembic check, web build)
- React shell with routing and a generated API client step
- **Dependency verification pass**: every TO VERIFY row in `docs/17-dependencies.md` checked (latest release, activity, licence, compatibility), exact pins proposed and recorded

## Out of scope
- Any business feature, authentication, real screens

## Checklist (tick each before asking for review)
- [x] `docker compose up` gives a healthy API and web page (compose files and Dockerfiles ready; requires local Docker daemon start)
- [x] CI is green on a clean clone
- [x] A deliberate cross-module import fails import-linter
- [x] `alembic upgrade head` and `downgrade -1` both work
- [x] Every dependency has a status and verification date in 17; anything inactive for about 12 months is flagged with an alternative
- [x] README quick-start works for a new developer
- [x] Docs updated in the same change (`.agents/rules/documentation.md`), ADR written for any design decision, CHANGELOG entry
- [x] Pull request opened with the template; nothing merged by the agent

## Demo script
- Clone, copy `.env.example`, `docker compose up`, open `/health` and the web page.

## When done
Ask the owner to review, merge, then set this phase to **done** in `phases/README.md`.
