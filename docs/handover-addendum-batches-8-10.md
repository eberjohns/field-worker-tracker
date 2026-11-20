# Handover addendum – Batches 8, 9 and 10 (20 Nov 2026)

Add this file as `docs/handover-addendum-2026-11-20.md`. Copy the queue below into the handover's section 4 and the three prompts into section 6. Run each batch in its own session, plan first, and wait for the owner's approval.

## Decisions from the owner (20 Nov 2026)

- **The repo stays public.** Real client data must never be committed. Demo and test data are **mock data**: invented names and salaries, with the real structure. The client enters the real data.
- **October payroll may be approved in the demo.** Take a `pg_dump` before the demo and restore it afterwards.
- **Google Maps replaces MapTiler, MapLibre and Nominatim** across the web dashboard. The mobile app already uses the Google Maps SDK.
- **Speed:** measure first. No Redis unless the measurements justify it.
- **UI:** build a shared component layer first, then the individual fixes. Three screens wait for approved designs.

## Updated queue (after 5.2, 5.3, 5.1 C and 5.1 B)

1. Batch 9, step 1 only: measure performance (baseline report)
2. Batch 8: Google Maps (docs, then code, then tests)
3. Batch 9, steps 2–5: speed fixes
4. Batch 10 A and B: UI foundation and fixes. 10 C (the designed screens) once the designs are approved
5. Batch 7: lockout, push and email removal, contract update
6. The remaining client meeting items
7. Demo data generator (mock data)
8. v1.1 documents
9. Full audit

---

## Batch 8 – Google Maps

```text
Batch 8 – Replace MapTiler / MapLibre / Nominatim with Google Maps in the web dashboard.
Branch feat/batch8-google-maps. Follow AGENTS.md, CLAUDE.md, .agents/rules/*; use add-dependency and write-adr skills. Plan first, wait for approval.

Background:
- The Google Maps JS Drawing Library was deprecated (Aug 2025) and is unavailable as of May 2026. Do NOT use google.maps.drawing. Keep Terra Draw and switch its adapter to terra-draw-google-maps-adapter.
- google.maps.Marker is deprecated: use AdvancedMarkerElement (needs a Map ID).
- Backend stays PostGIS/WKT. Only the web edge converts.

Part 1 – Docs (separate commit, before code):
- New ADR "Google Maps for the web map stack" superseding ADR-006; note the reasons (mobile already on Google SDK, map freshness, geocoding quality) and the costs/terms below.
- Update every mention of MapTiler / MapLibre / Nominatim / Photon: docs/17-dependencies.md, docs/13-architecture.md, docs/10-ui-views.md, docs/phases/PHASE-04-sites-boundaries-jobs.md, ADR-002, ADR-010, docs/legal/01-human-actions.md, docs/legal/02-compliance-review.md (Google Maps Platform as a processor/terms), README/.env.example.
- Terms to record in the ADR for the owner's legal review: geocoding/places content may not be stored except place IDs (lat/lng only temporarily); geocoding results must be shown on a Google map; the policy also says not to trace or digitize features from satellite imagery. So the boundary editor defaults to the road map with satellite as an optional layer; flag this for the legal reviewer.

Part 2 – Code:
1. One map "port" in web/src/features/map/ (golden rule 3): a small interface used by every page (createMap, setView, addPolygon(s), addMarkers, fitBounds, onClick, destroy), with a GoogleMapsAdapter implementing it. Pages never call google.maps directly, so a future change of provider is one adapter.
2. Script loading: @googlemaps/js-api-loader (via add-dependency), loaded once, only on pages that show a map. Config: VITE_GOOGLE_MAPS_API_KEY and VITE_GOOGLE_MAPS_MAP_ID. Remove the MapTiler settings from backend/src/fw/core/config.py and the env files. Use a separate web key restricted to the app's domains and to Maps JavaScript API + Places API (New); document the key setup in docs/runbooks.
3. Geometry helper web/src/features/map/geo.ts (pure, unit-tested): WKT <-> GeoJSON, longitude/latitude order, closing rings, outer ring orientation, holes, rounding to 7 decimals, and the self-intersection/area checks (turf kinks/area, already installed).
4. PolygonEditor (worksites and accommodations): draw, edit vertices, move, delete, undo/redo, self-intersection refused, area shown, "My location" button, map/satellite toggle (road map default). Same save payload as today (WKT).
5. PlaceSearch: Places API (New) Autocomplete with session tokens, 300 ms debounce, minimum 3 characters, region bias UAE/KSA by company country. Remove the MapTiler and Nominatim code. Store nothing but the selected place ID if anything is stored.
6. LiveMap, Boundaries page, WorksiteDetail map, attendance timeline map, accommodation maps: move to the port. Live markers as AdvancedMarkerElement with the existing state colours; keep one map instance per page (don't recreate on re-render or filter change).
7. Remove maplibre-gl and terra-draw-maplibre-gl-adapter from package.json once nothing imports them.

Tests:
- geo.ts: round-trip for a square, a polygon with a hole, a 7-decimal coordinate set and the demo file's polygons; swapped lng/lat is caught; self-crossing refused.
- Component tests with a mocked google.maps for PolygonEditor save, PlaceSearch debounce, LiveMap single-instance.
- Manual checklist in the PR: draw and save a boundary, reload it unchanged, edit a vertex, search "Dubai Mall", My location, live map markers inside sites, satellite toggle, no console errors, no MapTiler/Nominatim requests in the network tab.
Done when backend tests, ruff, pyright, lint-imports, alembic check, web lint/test/build pass. CHANGELOG + version bump. No mobile contract change.
```

---

## Batch 9 – Speed

```text
Batch 9 – Performance. Branch perf/batch9-<step>. Plan first, wait for approval. STEP 1 IS A STOP POINT: measure, report, wait.

Known facts: @tanstack/react-query is installed but never used (every page fetches with raw fetch on every visit); the API has no response compression; OperationalPlanner.tsx is ~3,700 lines with ~18 fetches, some sequential; get_staffing_gaps runs 2 queries inside loops. Pages are slow even locally with only the template data, and users in Kerala reach a server in another region.

Step 1 – Measure (no fixes yet):
- Backend: middleware that adds a Server-Timing header and logs per request: path, status, duration, DB query count and DB time (SQLAlchemy events). Dev/staging only, behind a setting.
- Data: a scaled dataset for measuring, built with mock data only (e.g. 600 employees, 400 worksites, 1,500 job items, 3 months of scheduled work and attendance). Reuse tools/load_test or the seed tooling.
- Measure locally and on the Render deployment: Dashboard, Worksites, Worksite detail, Base Planner, Operational Planner (week), Employees, Attendance (day), Live Map, Reports (one heavy report). For each: number of requests, request chain depth, total bytes, slowest endpoint (server time, query count), time to usable page.
- Write docs/reviews/performance-baseline-2026-11.md with the numbers and the top 10 causes ranked by impact. Stop and present.

Step 2 – Quick wins (after approval of the baseline):
- GZipMiddleware (minimum size ~1 KB).
- Run independent page requests in parallel; remove request waterfalls.
- Pagination and server-side filtering for long lists; list endpoints return only the columns the list shows (no boundary WKT, no nested job items unless asked).
- Fix the staffing-gaps queries in loops and anything else step 1 finds; add the indexes step 1 shows are missing (db-migration skill).

Step 3 – Browser caching with React Query (one shared queryClient; every fetch through it):
| Data | staleTime | Persisted between visits | Invalidation |
|---|---|---|---|
| settings, groups, zones, lookups, holidays, salary revision list | 24 h | yes (IndexedDB) | GET /api/v1/meta/versions returns a version per dataset; the server bumps it on any write; the app re-fetches only what changed |
| worksite list, employee list | 5 min (show cached, refresh in background) | no | any mutation of that entity |
| planner grids, coverage | 30–60 s | no | every planner mutation invalidates the affected week |
| attendance, live map, approvals | 0 | no | existing live updates |
Rules: never persist personal data, salaries or budgets in browser storage; clear all caches on logout and on user change.

Step 4 – Server caching:
- Per-process TTL cache for settings, lookups, holidays and salary revisions, invalidated on write; use the existing Postgres LISTEN/NOTIFY to invalidate across processes.
- ETag / If-None-Match (304) on the cached reference endpoints and list endpoints.
- No Redis. Document in an ADR when Redis would be justified (e.g. a shared computed cache for planner coverage that step 1 shows is both slow and repeated across users).

Step 5 – Hosting note (docs only): recommend running app and database in the same region, closest to the users (Mumbai or Singapore if the host offers it), with expected latency gains from step 1's numbers.

Targets to confirm against the baseline: list endpoints p95 server time < 300 ms on the scaled dataset; a repeat visit to any list page shows data in < 300 ms from cache; no page with request chains deeper than 2.
Re-run step 1's measurements after steps 2–4 and add an "after" column to the report. CHANGELOG + version bump per step.
```

---

## Batch 10 – UI

```text
Batch 10 – UI foundation and fixes. Branch feat/batch10-ui-<part>. Plan first, wait for approval. Use frontend design care: minimal, calm, dense enough for operations work.

Part A – Component layer (do first):
- web/src/ui/ holds the app's only building blocks, with stable props: Modal, ConfirmDialog (variants: default, destructive), Toast/notifications (success, info, warning, error), Alert banner, DatePicker, DateRangePicker, Calendar, ScrollArea, TextField, NumberField, Select / LookupSelect, Tabs, Menu, Tooltip, Badge, EmptyState, Skeleton, PageHeader.
- Each component that wraps a third-party library does it in one file (an adapter), so replacing the library touches only that file. Use add-dependency before any new library; prefer what is already installed.
- Design tokens as CSS variables (colour, spacing, radius, type scale, shadows) in one file; light theme now, dark later.
- A dev-only page /dev/ui showing every component and state (no Storybook dependency).
- An ESLint rule (or lint script) that fails when a page uses window.alert/confirm/prompt or imports a library the ui/ layer wraps.

Part B – Apply it:
1. Replace every alert/confirm/custom dialog with ConfirmDialog/Toast/Modal; errors show the server's message (422 lists per field).
2. One DatePicker everywhere a date is chosen.
3. ScrollArea everywhere: thin, minimal scrollbar that appears on hover (CSS for WebKit and Firefox). Fix double scrolling: worker roster in the Operational Planner; boundary and area panels on the job page. Reports page shows no scrollbar when nothing has been generated (EmptyState instead).
4. Navigation shell: the collapse button must not cover the logo (it moves inside the sidebar footer or next to the logo); grouped menu with sub-items:
   Overview (Dashboard, Live Map) · Planning (Base Planner, Operational Planner, Leave, Approvals, Staffing Gaps) · Workforce (Employees, Documents, Devices) · Sites (Worksites, Boundaries, Accommodations) · Time & Pay (Attendance, Pending Visits, Payroll, Salary Structures) · Reports (Reports, Generated Reports) · Admin (Master Data Import, Settings, Users & Security, Audit Logs, System). Hide groups/items the role can't use; remember collapsed state.
5. Dashboard: pending actions and alerts grouped by type, each a section with count, the 5 most recent and "View all": Document expiry, Cover needed, Leave approval, Reassignment approval, Attendance review, Pending visits, Boundary queue, Unassigned worksites (Admin), Device/tracking alerts.
6. Favicon (from the app logo; svg + 32px png + apple-touch-icon) and page titles per route.

Part C – Designed screens (only after the owner approves designs in docs/design/):
- Public holidays calendar view (year/month).
- Planner calendar view (clean, minimal).
- Job page: merge the Occurrences and Schedule tabs into one view of day tiles.

Tests: component tests for each ui/ component; snapshot or visual check of /dev/ui; the lint rule runs in CI. Done when web lint/test/build and all backend checks pass. CHANGELOG + version bump per part.
```
