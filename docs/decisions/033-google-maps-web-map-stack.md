# 033 - Google Maps for the web map stack
Status: Accepted (25 Nov 2026; revised the same day: Google Maps is the only provider)
Date: 2026-11-25
Supersedes: the renderer, basemap and geocoding parts of [ADR-006](006-map-stack-and-dependency-policy.md). ADR-006's dependency policy still applies.

## Context
- **Owner decision, 20 Nov 2026:** Google Maps replaces MapTiler, MapLibre and Nominatim in the web dashboard.
- **Owner, 25 Nov 2026 (first):** put it behind a `MAP_PROVIDER` setting with MapLibre as the fallback. Never trace satellite imagery.
- **Owner, 25 Nov 2026 (revised):** Google Maps is the **only** provider. Keep the shared map interface, but remove the MapLibre implementation, the MapLibre/MapTiler/Nominatim packages and code, and `VITE_MAP_PROVIDER`. There is no fallback.

Reasons:
- **The mobile app already uses the Google Maps SDK**, so supervisors see the same map on both.
- **Google's map data and imagery are fresher** in fast-changing parts of Dubai and KSA.
- **Google's geocoding works better** for site names and addresses in UAE and KSA.

Changes on Google's side that shape the design:
- **The Drawing Library** (`google.maps.drawing`) was deprecated in August 2025 and is unavailable since May 2026.
- **`google.maps.Marker` is deprecated.** Markers are `AdvancedMarkerElement`, which needs a Map ID.

## Options considered
1. **Google Maps behind a provider setting, with MapLibre as the fallback.** This was built first, then dropped by the owner the same day: two stacks to maintain and test for a fallback nobody asked to keep.
2. **Google Maps only, behind one map interface (chosen).**
3. **Stay on MapLibre and MapTiler.** This was rejected by the owner's decision.

## Decision
- **One map interface.** Pages use only `web/src/features/map/port.ts`. The Google implementation is in `web/src/features/map/google/`, and nothing else touches `google.maps`. A later provider change is one adapter (golden rule 3).
- **Keys** come only from environment variables at build time: `VITE_GOOGLE_MAPS_API_KEY` and `VITE_GOOGLE_MAPS_MAP_ID`. They are never in tracked files. Without them, map areas show "Map not configured" and the rest of the page works.
- **Map types** use Google's own control: road map, satellite and hybrid.
  - Every map opens on the **road map**.
  - The boundary editor stays on the road map by default until the legal question below is answered.
- **Drawing:**
  - Terra Draw with `terra-draw-google-maps-adapter`, never `google.maps.drawing`;
  - Turf and `geo.ts` for the instant checks; PostGIS stays authoritative.
- **Geometry stays PostGIS on the server.** Only the web edge converts (`geo.ts`: WKT to and from GeoJSON, ring closing and orientation, 7 decimals).

### Usage rules (owner, 25 Nov), to keep the bill and quotas small
- **One map per page, created once and reused.**
  - The map and its element are pooled (`google/mapPool.ts`). Switching tabs, reopening a boundary dialog or returning to the Live Map inside the app reuses it, so there is no new map load.
  - Markers and polygons are updated in place. Markers are `AdvancedMarkerElement`.
- **The script is loaded once, lazily,** and only on pages that show a map (`@googlemaps/js-api-loader`). Pages without a map load nothing from Google.
- **Lists and previews show the boundary as a small SVG** (`BoundaryThumbnail`). The real map opens only on the Boundary tab, on "Show on map", or in a boundary dialog.
- **Live Map never reloads the map** on refresh or on a stream reconnect. It only moves markers.
- **Geocoding:**
  - only on an explicit Search button press, with no autocomplete;
  - never reverse geocoding of live positions;
  - no server-side geocoding.
  - We store only what the user draws (the polygon) and at most a place ID. Today nothing from search is stored.
- **Quota or key failure:**
  - the map area shows "Map unavailable today (usage limit reached)", and the rest of the page keeps working;
  - a refused search says so in the search box, and the map stays.
- **Our own usage counter:**
  - The browser reports each map it creates (`MAP_LOAD`) and each Search press (`GEOCODE`) to `POST /api/v1/map-usage`. Counts are kept per environment and month.
  - Admin sees them in Settings > System, against soft limits (company settings `map_loads_soft_limit_month`, `geocodes_soft_limit_month`). A warning shows when a limit is reached.

### Keys and quotas
See `docs/runbooks/08-google-maps-keys.md`:
- a separate web key restricted by referrer (`localhost:5173`, the Render web URL) and to the **Maps JavaScript API** and **Geocoding API**;
- a Map ID;
- daily quotas to start: 300 map loads and 100 geocodes, with a quota alert at 80% and a budget alert.

## Why
- One provider means one code path to test. The interface still keeps Google-specific code in one folder.
- Reusing the map and avoiding map loads on lists keeps a normal session to **one map load**, measured on the demo data.
- Geocoding only on Search keeps geocodes to the presses users actually make.

## Terms to review (owner's legal reviewer)
From the Google Maps Platform Terms and Service Specific Terms; verify before going live:
- **Geocoding content** may not be stored or cached, except place IDs. Coordinates may be kept only temporarily. The app stores nothing from search: picking a result only moves the map.
- **Geocoding results must be shown on a Google map.** They always are, since there is no other map.
- **No tracing or digitising of features from Google imagery.** Boundaries are drawn by people who know the site, on the road map by default. *Flag for the legal reviewer:* drawing a boundary while satellite is shown may count as tracing. Until this is answered, the editor opens on the road map.
- **Billing:** map loads and geocodes are billed per use, above the monthly free usage. Billing must be enabled on the Google Cloud project. Quotas and budget alerts follow runbook 08.
- **Processor:** Google Maps Platform becomes a processor of the map view and the search text. It is not sent worker positions as data: positions are drawn as markers in the browser. This is recorded in `docs/legal/02-compliance-review.md`.

## Consequences
- **Web dependencies**, approved by the owner on 25 Nov:
  - `@googlemaps/js-api-loader` 2.1.3 (Apache-2.0);
  - `terra-draw-google-maps-adapter` 1.7.0 (MIT);
  - `@types/google.maps` 3.67.0 (MIT, dev).
- **Removed:** `maplibre-gl`, `react-map-gl`, `terra-draw-maplibre-gl-adapter`, MapTiler and Nominatim, `VITE_MAP_PROVIDER` and `VITE_MAP_API_KEY`.
- **The map code chunk** is about 14 kB; Google's script loads at run time.
- **Worker clustering** uses a small grid clusterer in our code (`gridCluster.ts`), with no extra dependency.
- **Backend:** a `map_usage_counters` table (migration 0028) and two endpoints. The backend has no map keys and never calls Google.
- **Mobile:** no change. The app already uses Google Maps.

Affects: `docs/10-ui-views.md`, `docs/13-architecture.md`, `docs/17-dependencies.md`, `docs/07-data-model.md`, `docs/08-api-spec.md`, `docs/legal/01-human-actions.md`, `docs/legal/02-compliance-review.md`, `docs/phases/PHASE-04-sites-boundaries-jobs.md`, ADR-002, ADR-006, ADR-010.
