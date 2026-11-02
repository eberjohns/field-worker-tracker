# 17 - Dependency Register

Policy: `.agents/rules/dependencies.md`. Every library or service in the stack is listed here with when it was verified and its status. **Do not add a dependency that is not active.** Verified means: release recency, maintenance activity, licence, and compatibility with our other pinned versions were checked on the date shown.

Status: **VERIFIED** (checked), **GATE** (checked, but a compatibility test is required before pinning), **TO VERIFY** (not yet checked - must be verified in M0 before it is pinned), **REJECTED**.

| Area | Dependency | Status | Verified | Notes |
|---|---|---|---|---|
| Map renderer | maplibre-gl 6.x | VERIFIED | 2026-10-28 | v6.15 released 18 Oct 2026; ESM-only, WebGL2 required, BSD |
| Map wrapper | react-map-gl 8.1.2 (`/maplibre`) | VERIFIED | 2026-10-28 | released 29 Jul 2026; supports MapLibre v6 |
| Map drawing | terra-draw + terra-draw-maplibre-gl-adapter | **GATE** | 2026-10-28 | maintained; adapter docs list MapLibre v4/v5; v6 support unconfirmed (ADR-006 gate). Fallback: pin maplibre-gl 5.x |
| Geometry (web) | @turf/* 7.3.x (modular) | VERIFIED | 2026-10-28 | MIT; released through 2026; import only needed modules |
| Basemap tiles | MapTiler Cloud (alt: Stadia Maps) | VERIFIED (service) | 2026-10-28 | planet data release cycle visible; confirm plan/pricing at purchase; satellite imagery recency unverified |
| Place search | MapTiler Geocoding API (or the chosen provider's) | TO VERIFY | - | browser-side "search a place and focus the map"; query text only; confirm terms and pricing |
| Job queue | procrastinate 3.x | VERIFIED, WATCH | 2026-10-28 | active (3.5.x); project publicly seeks additional maintainers - keep behind the `JobQueue` port; alternative adapter ready if risk grows |
| Map renderer | Leaflet | **REJECTED** | - | not actively updated; do not reintroduce |
| Backend | FastAPI, Pydantic v2, Starlette, uvicorn | TO VERIFY | - | |
| Backend | SQLAlchemy 2.x, asyncpg, Alembic | TO VERIFY | - | |
| Backend | GeoAlchemy2, Shapely | TO VERIFY | - | |
| Backend | PyJWT, argon2-cffi, structlog | TO VERIFY | - | |
| Backend | openpyxl, XlsxWriter | TO VERIFY | - | openpyxl releases are infrequent; check before relying on it for writes |
| Backend tooling | uv, ruff, pyright, import-linter | TO VERIFY | - | |
| Frontend | React 18/19, Vite, TypeScript | TO VERIFY | - | |
| Frontend | TanStack Router/Query/Table | TO VERIFY | - | |
| Frontend | Tailwind CSS, shadcn/ui | TO VERIFY | - | |
| Frontend | react-hook-form, zod, Recharts | TO VERIFY | - | |
| Frontend | date-fns-tz | TO VERIFY | - | check whether still needed or superseded by current date-fns |
| Frontend | openapi-typescript | TO VERIFY | - | |
| Database | PostgreSQL 16+, PostGIS 3.x | TO VERIFY | - | confirm managed-service support in the chosen UAE region |

## Process
- M0 includes a **dependency verification pass**: the agent checks every TO VERIFY row (latest release date, activity, licence, compatibility), proposes exact pins, and updates this table. Anything inactive for about 12 months is proposed for replacement with an ADR.
- Re-check this register at the start of each milestone and when any library is upgraded by a major version.
- Lock files are committed; automated update PRs (Dependabot/Renovate) run monthly.
