# 033 - Google Maps for the web map stack, behind a provider setting
Status: Accepted (Google adapter enabled once the owner supplies the keys)
Date: 2026-11-25
Supersedes: the renderer, basemap and geocoding parts of [ADR-006](006-map-stack-and-dependency-policy.md). ADR-006's dependency policy still applies.

## Context
- **Owner decision, 20 Nov 2026:** Google Maps replaces MapTiler, MapLibre and Nominatim in the web dashboard.
- **Owner, 25 Nov 2026:** do it behind a `MAP_PROVIDER` setting, keep MapLibre as the fallback, and never trace satellite imagery.

Reasons:
- **The mobile app already uses the Google Maps SDK**, so supervisors see the same map on both.
- **Google's map data and imagery are fresher** in fast-changing parts of Dubai and KSA.
- **Google's geocoding and place search work better** for site names and addresses in UAE and KSA.

Changes on Google's side that shape the design:
- **The Drawing Library** (`google.maps.drawing`) was deprecated in August 2025 and is unavailable since May 2026.
- **`google.maps.Marker` is deprecated.** Markers must be `AdvancedMarkerElement`, which needs a Map ID.

## Options considered
1. **Google Maps only**, removing MapLibre now. This was rejected: it leaves the dashboard with no map until a key exists, and gives no fallback if Google is unavailable or its quota runs out.
2. **Google Maps behind a provider setting, with MapLibre as the fallback (chosen).** The fallback is today's map, unchanged: MapTiler tiles with `VITE_MAP_API_KEY`, else OpenStreetMap tiles, and the existing search.
3. **Stay on MapLibre and MapTiler.** This was rejected by the owner's decision.

## Decision
- **One map port.** `web/src/features/map/port.ts` is used by every page and has two adapters:
  - `GoogleMapsAdapter`: Maps JavaScript API, `AdvancedMarkerElement`, Places API (New);
  - `MapLibreAdapter`: today's stack.
  Pages never call `google.maps` or `maplibre-gl` directly, so a provider change is one adapter. This is golden rule 3.
- **Which adapter is used:**
  - `VITE_MAP_PROVIDER` is `google` or `maplibre`; the default is `maplibre` until the owner switches.
  - `google` needs `VITE_GOOGLE_MAPS_API_KEY` and `VITE_GOOGLE_MAPS_MAP_ID`. If either is missing, the app uses MapLibre and logs why.
  - The keys are set only as environment variables (local `web/.env.local`, or the hosting's settings), never in tracked files.
- **Drawing:**
  - Terra Draw stays, with its adapter for the active provider (`terra-draw-google-maps-adapter` for Google).
  - Never `google.maps.drawing`.
  - Turf stays for the instant self-intersection and area checks; PostGIS stays authoritative.
- **Geometry stays PostGIS and WKT on the server.** Only the web edge converts (`geo.ts`: WKT to and from GeoJSON, ring closing and orientation, 7 decimals).
- With Google, maps open on the **road map** (the boundary editor too); satellite is an optional layer. The MapLibre fallback keeps today's default (satellite).
- **Google keys:**
  - The web key is separate from the mobile one.
  - It is restricted to the app's domains and to the Maps JavaScript API and Places API (New).
  - Setup: `docs/runbooks/08-google-maps-keys.md`.
- **The backend's unused MapTiler settings are removed** (`MAP_STYLE_*`, `MAP_API_KEY` in `core/config.py` and `.env.example`). The backend never served map configuration.

## Why
- The provider setting lets the switch happen without a release, and lets it be undone the same way.
- The port keeps the provider-specific code (about a fifth of the map code) in one folder.
- Keeping Terra Draw keeps the editor's behaviour (vertex editing, undo, kinks check) the same for both providers.

## Terms to review (owner's legal reviewer)
From the Google Maps Platform Terms and Service Specific Terms; verify before going live:
- **Places and geocoding content:** it may not be stored or cached, except place IDs. Coordinates may be kept only temporarily. The app stores nothing from search: picking a result only moves the map.
- **Geocoding and Places results must be shown on a Google map**, which they are when the provider is `google`. With the MapLibre fallback, search uses the fallback's own geocoder (MapTiler or Nominatim), never Google's.
- **No tracing or digitising of features from Google imagery.** Boundaries are drawn by people who know the site, on the road map by default; satellite is an optional reference layer. *Flag for the legal reviewer:* drawing a site boundary while satellite is shown may count as tracing. Options are to hide the satellite layer while drawing, or to accept the risk with the client's site plans as the source.
- **Billing:**
  - Dynamic Maps loads and Places Autocomplete sessions are billed per use, above the monthly free usage.
  - For about 100 dashboard users this should stay small. Confirm current pricing and set a quota cap and budget alert in Google Cloud.
- **Processor:** Google Maps Platform becomes a processor of the map view and search text. It is not sent worker positions as data: positions are drawn as overlays in the browser. This is recorded in `docs/legal/02-compliance-review.md`.

## Consequences
- New web dependencies (owner approval and the dependency check per `docs/17-dependencies.md`):
  - `@googlemaps/js-api-loader` (Apache-2.0);
  - `terra-draw-google-maps-adapter` (MIT);
  - `@types/google.maps` (MIT, dev).
- `maplibre-gl`, `react-map-gl` and `terra-draw-maplibre-gl-adapter` stay while the fallback exists.
- Each map page loads only the active provider's code.
- Live map markers use the same state colours with both providers. Clustering is MapLibre's own with MapLibre, and a small grid clusterer in our code with Google (no extra dependency).
- Mobile: no change (it already uses Google Maps).

Affects: `docs/10-ui-views.md`, `docs/13-architecture.md`, `docs/17-dependencies.md`, `docs/legal/01-human-actions.md`, `docs/legal/02-compliance-review.md`, `docs/phases/PHASE-04-sites-boundaries-jobs.md`, ADR-002, ADR-010.
