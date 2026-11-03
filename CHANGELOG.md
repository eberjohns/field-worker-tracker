# Changelog
All notable changes. Format: Keep a Changelog. Mobile-contract changes are also logged in `docs/09-mobile-sync-contract.md`.

## [Unreleased]
### Added
- PHASE-00 (Foundation):
  - Monorepo structure (`backend/`, `web/`, `infra/`, `tools/`).
  - Docker Compose environment with PostGIS 16-3.4, FastAPI API container, Procrastinate worker, Vite/React web container, and Mailpit mail catcher.
  - Root `.env.example` and developer onboarding `README.md`.
  - Backend FastAPI app factory with `/health` (liveness) and `/health/ready` (database readiness).
  - Pydantic v2 settings with `DEPLOYMENT_COUNTRY` validation (`AE` or `SA`).
  - Async SQLAlchemy 2.0 session factory and Alembic migration baseline with PostGIS extension.
  - `core` shared libraries: RFC 7807 problem details error handling, UTC `Clock` port/adapters, JSON `structlog` logging, and domain event bus.
  - Country rule packs Protocol and implementations for UAE (`AE`) and Saudi Arabia (`SA`).
  - Architecture layers contract enforcement via `import-linter` (9 modular monolith layers + pure rules contract).
  - React 18 + Vite + TypeScript frontend shell with TanStack Router, Tailwind CSS, and OpenAPI code generator (`openapi-typescript`).
  - CI workflow (`.github/workflows/ci.yml`) covering linting, type-checking, architecture contract verification, database migration rollback, and web build.
  - PR template (`.github/pull_request_template.md`).
  - Full dependency verification audit in `docs/17-dependencies.md` and ADR 010.
- Documentation pack for Field Worker Tracker: requirements reference, 15 numbered docs, 6 design docs, 14 phase plans with context packs and checklists, decision register, ADRs 001-009, legal/compliance drafts, import template v1.0.
- Agent rules and skills (architecture, conventions, time and money, documentation, safety, dependencies, phase workflow; add-module, add-endpoint, add-synced-entity, db-migration, write-adr, import-column, add-dependency, start-phase, finish-phase).
### Decisions captured
- See `docs/decisions/decision-register.md` and the answers logs in `docs/reference/`.
