# 17 - Dependency Register

Policy: `.agents/rules/dependencies.md`. Every library or service in the stack is listed here with when it was verified and its status. **Do not add a dependency that is not active.** Verified means: release recency, maintenance activity, licence, and compatibility with our other pinned versions were checked on the date shown.

Status: **VERIFIED** (checked), **GATE** (checked, but a compatibility test is required before pinning), **TO VERIFY** (not yet checked - must be verified in M0 before it is pinned), **REJECTED**.

| Area | Dependency | Status | Verified | Notes |
|---|---|---|---|---|
| Map renderer | maplibre-gl 6.x | VERIFIED | 2026-10-28 | v6.15 released 18 Oct 2026; ESM-only, WebGL2 required, BSD |
| Map wrapper | react-map-gl 8.1.2 (`/maplibre`) | VERIFIED | 2026-10-28 | released 29 Jul 2026; supports MapLibre v6 |
| Map drawing | terra-draw + terra-draw-maplibre-gl-adapter | VERIFIED | 2026-11-03 | terra-draw 1.39.0 + terra-draw-maplibre-gl-adapter 1.5.0 verified with maplibre-gl 6.16.0 (ADR-006 gate passed); polygon drawing, vertex dragging, area & kinks checks verified |
| Geometry (web) | @turf/* 7.3.x (modular) | VERIFIED | 2026-10-28 | MIT; released through 2026; import only needed modules |
| Basemap tiles | MapTiler Cloud (alt: Stadia Maps) | VERIFIED (service) | 2026-10-28 | planet data release cycle visible; confirm plan/pricing at purchase; satellite imagery recency unverified |
| Place search | MapTiler Geocoding API | VERIFIED (service) | 2026-11-02 | REST forward search endpoint; query text only; domain-restricted API key; free tier 100k req/mo |
| Job queue | procrastinate 3.x | VERIFIED, WATCH | 2026-10-28 | active (3.10.x); project seeks additional maintainers - keep behind `JobQueue` port; alternative adapter ready if needed |
| Map renderer | Leaflet | **REJECTED** | - | not actively updated; do not reintroduce |
| Backend | FastAPI, Pydantic v2, Starlette, uvicorn | VERIFIED | 2026-11-02 | FastAPI 0.162.x / Pydantic 2.14.x / Starlette 1.10.x / Uvicorn 0.54.x; MIT/BSD; pinned in uv.lock |
| Backend | SQLAlchemy 2.x, asyncpg, Alembic | VERIFIED | 2026-11-02 | SQLAlchemy 2.1.x / asyncpg 0.32.x / Alembic 1.20.x; MIT/Apache 2.0; asyncpg connection pool; pinned in uv.lock |
| Backend | GeoAlchemy2, Shapely | VERIFIED | 2026-11-02 | GeoAlchemy2 0.20.x / Shapely 2.2.x; PostGIS geometry integration; BSD/MIT; pinned in uv.lock |
| Backend | PyJWT, argon2-cffi, structlog | VERIFIED | 2026-11-02 | PyJWT 2.15.x / argon2-cffi 25.1.x / structlog 26.1.x; secure hashing & JSON logging; pinned in uv.lock |
| Backend | openpyxl, XlsxWriter | VERIFIED | 2026-11-02 | openpyxl 3.1.5 (MIT, read-only import workbook parsing); XlsxWriter 3.3.1 (BSD, active, report export streaming) |
| Backend tooling | uv, ruff, pyright, import-linter | VERIFIED | 2026-11-02 | uv 0.13.x / ruff 0.17.x / pyright 1.1.414 / import-linter 2.15; fast packaging & modular layer enforcement |
| Frontend | React 18, Vite 5, TypeScript 5 | VERIFIED | 2026-11-02 | React 18.3.1 pinned for map & UI ecosystem stability; Vite 5.4.x; TypeScript 5.9.x; pinned in pnpm-lock.yaml |
| Frontend | TanStack Router/Query/Table | VERIFIED | 2026-11-02 | Router 1.170.x / Query 5.105.x / Table 8.21.x; active, MIT; typed client-side routing & caching |
| Frontend | Tailwind CSS, shadcn/ui | VERIFIED | 2026-11-02 | Tailwind 3.4.x (active, MIT); shadcn/ui accessible headless primitives pattern |
| Frontend | react-hook-form, zod, Recharts | VERIFIED | 2026-11-02 | react-hook-form 7.54.x / zod 3.24.x / recharts 2.15.x; active form validation & charting; MIT |
| Frontend | date-fns & @date-fns/tz | VERIFIED | 2026-11-02 | date-fns v4 with official @date-fns/tz package for IANA time zones (Asia/Dubai, Asia/Riyadh), superseding legacy date-fns-tz |
| Frontend | openapi-typescript | VERIFIED | 2026-11-02 | openapi-typescript 7.13.x; generates static TS definitions from FastAPI OpenAPI JSON contract |
| Database | PostgreSQL 16+, PostGIS 3.x | VERIFIED | 2026-11-02 | postgis/postgis:16-3.4 image; verified on Azure Database for PostgreSQL Flexible Server in UAE North |

## Process
- M0 includes a **dependency verification pass**: the agent checks every TO VERIFY row (latest release date, activity, licence, compatibility), proposes exact pins, and updates this table. Anything inactive for about 12 months is proposed for replacement with an ADR.
- Re-check this register at the start of each milestone and when any library is upgraded by a major version.
- Lock files are committed; automated update PRs (Dependabot/Renovate) run monthly.
