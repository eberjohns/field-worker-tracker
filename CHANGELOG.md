# Changelog
All notable changes. Format: Keep a Changelog. Mobile-contract changes are also logged in `docs/09-mobile-sync-contract.md`.

## [Unreleased]
### Added
- PHASE-02 (Settings, time rules and calendars):
  - Pure domain rules resolver for time rules (`fw.rules.time_rules`): scope hierarchy (`EMPLOYEE > TEAM > DRIVERS > COMPANY`), manager relationship weighting (`SUPERVISOR > SUPERINTENDENT > ENGINEER`), specificity (`OUTDOOR_ONLY` / `INDOOR_ONLY` > `ALL`), and field-level inheritance with full explainability.
  - Verification of the client 5-point planned schedule calculation: 05:00 / 06:00 / 0:30 / 15:30 / 17:00 => 12:00 total (720 min), 09:00 worked (540 min).
  - Database migration `0003_settings_and_time_rules.py` adding `time_rules`, `public_holidays`, and `consent_policies` tables with foreign keys and check constraints; seeded catalog settings, default company time rule, statutory public holidays (AE & SA), and consent policy v1.
  - Settings service & schemas supporting effective-dated updates (closing prior active records at `new_effective_from - 1 day`), setting history tracking, and time rule CRUD with scope protection for Engineers.
  - Explainer API endpoint `GET /time-rules/resolve` returning effective schedule, planned total/worked minutes, standard hours adjustments, winning primary rule, and field-level source traces.
  - Public holidays endpoints (`GET /public-holidays`, `POST /public-holidays`, `DELETE /public-holidays/{id}`) and consent policy endpoints (`GET /consent-policies`, `POST /consent-policies`).
  - Web Dashboard Settings view (`web/src/routes/Settings.tsx`): 7 tabs (Company Settings with effective-dated edit modal & history drawer, Time Rules table with create modal, Resolver Check Tool with visual 5-point schedule & candidate trace, Public Holidays, Budget-Only Staff Types checklist, Default Password policy, and Consent Notice publisher).
  - ADR-012: Time rules resolver hierarchy, field inheritance, and scope.
  - Automated demo script for Phase 02 (`backend/tools/demo_phase02.py`).
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
