# 010 - Foundation dependency pins and verification
Status: Accepted
Date: 2026-11-02

## Context
Per `.agents/rules/dependencies.md` and Phase 00 requirements, all candidate libraries in `docs/17-dependencies.md` marked `TO VERIFY` must undergo a verification audit (recency, maintenance activity, licence, and mutual compatibility) before exact pins are locked in version control.

## Options considered
1. Bleeding-edge React 19 vs stable React 18.3.1.
2. Legacy `date-fns-tz` vs modern `date-fns` v4 with `@date-fns/tz`.
3. Single general-purpose Excel engine vs splitting `openpyxl` (read) and `XlsxWriter` (streaming write).
4. Unpinned dependencies vs exact lock files (`uv.lock`, `pnpm-lock.yaml`).

## Decision
- **React**: Pin React to 18.3.1 with Vite 5.x and TypeScript 5.x. This ensures rock-solid compatibility with MapLibre GL wrappers (`react-map-gl`), TanStack Router/Table, and UI components without peer-dependency friction.
- **Date & Timezone**: Adopt `date-fns` v4 with `@date-fns/tz` for timezone calculations (`Asia/Dubai`, `Asia/Riyadh`), superseding the unmaintained `date-fns-tz` v2 package.
- **Excel Division**: Enforce strict separation: `openpyxl` is pinned for read-only parsing of uploaded client workbooks; `XlsxWriter` is pinned for generating fast, memory-efficient reports and workbook templates.
- **Lock Files**: All Python dependencies are pinned via `uv.lock` (managed by `uv 0.13.6` with Python 3.12 target); all frontend dependencies are pinned via `pnpm-lock.yaml` (pnpm 12.x).
- **PostGIS & Database**: Pinned to PostgreSQL 16 with PostGIS 3.4 (`postgis/postgis:16-3.4`), matching Azure Database for PostgreSQL Flexible Server in UAE North.

## Why
This locks in proven, actively maintained packages across both stacks, avoids the 12-month inactivity pitfall (which led to the rejection of Leaflet), and guarantees reproducible CI and local builds.

## Consequences
All CI pipelines and local workflows use `uv` and `pnpm` with immutable lockfiles. Any dependency addition or upgrade must follow the `add-dependency` skill and update `docs/17-dependencies.md`.
