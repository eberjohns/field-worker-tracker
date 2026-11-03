# Changelog
All notable changes. Format: Keep a Changelog. Mobile-contract changes are also logged in `docs/09-mobile-sync-contract.md`.

## [Unreleased]
### Added
- PHASE-01 (Access and people):
  - Pure domain rules for hierarchy validation: cycle prevention in directed management graph, single supervisor constraint, and transitive descendant scope resolution (`fw.rules.hierarchy`).
  - Pure password policy rules: default password detection, strength validation, and expiration/locking after `default_password_max_days` (`fw.rules.password`).
  - Database migration `0002_access_and_people.py` introducing `audit_logs`, `users`, `user_sessions`, `employees`, `employee_reporting_lines`, `employee_grade_history`, `groups`, `zones`, `accommodations`, `employee_documents`, `registered_devices`, and `company_setting_values`.
  - Identity module with Argon2id password hashing, rotating refresh token sessions in httpOnly cookies, forced password change on default password, and Admin reset-to-default capability.
  - Org module providing Employees CRUD with optimistic locking (`version`), bulk update of operational settings, Grade Code change tracking, reporting lines management, groups/zones/accommodations, and documents/devices tracking.
  - Audit module recording append-only audit entries on all state-changing actions with actor, diff, entity_id, and timestamp.
  - Full Web API routers mounted under `/api/v1` for Auth, Employees, Users, Org Entities, Devices, and Audit Logs.
  - React Web Dashboard additions: Login view with forced password change flow, role-filtered Shell navigation, Employees table with supervisor grouping and bulk update modal, Employee Detail view with Profile/Hierarchy/Documents/Device/History tabs, Users Admin view, and Audit Log viewer.
  - ADR-011: Transitive reporting scope resolution and session token rotation.
  - Fictional seed script (`tools/seed_phase01.py`) and automated demo script (`tools/demo_phase01.py`).
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
