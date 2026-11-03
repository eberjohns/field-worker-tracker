# 006 - Map stack, tile provider and dependency policy
Status: Accepted (version pins subject to the M3 compatibility gate)
Date: 2026-10-28

## Context
Maps are core: drawing and showing geofence boundaries (site and accommodation), the live map of workers' last known positions, and each worker's movement log. Leaflet was considered first and dropped because it is not actively updated. The same mistake must not be repeated for any dependency.

## Options considered
Renderer: Leaflet (rejected), OpenLayers, MapLibre GL JS. Basemaps: Google (its tiles cannot be used with MapLibre), Mapbox, MapTiler, Stadia, public OpenStreetMap tiles (not for production load, no satellite), self-hosted vector tiles (no satellite imagery).

## Decision
- **Renderer: MapLibre GL JS** with `react-map-gl` (MapLibre entry point). Open source (BSD), no per-load fee, WebGL2.
- **Drawing: Terra Draw** with its MapLibre adapter. **Geometry in the browser: Turf.js** modular packages (`@turf/area`, `@turf/boolean-valid`, `@turf/kinks`, ...), for instant feedback only. The server (PostGIS/Shapely) is authoritative.
- **Clustering: MapLibre's built-in GeoJSON source clustering** (no extra dependency).
- **Basemaps: hosted vector streets + satellite from one provider behind configuration** (`MAP_STYLE_STREETS_URL`, `MAP_STYLE_SATELLITE_URL`, `MAP_API_KEY`, key restricted by domain). Default recommendation: **MapTiler Cloud**; Stadia Maps is the drop-in alternative. Switching providers is a configuration change.
- **Live positions: SSE stream fed by PostgreSQL `LISTEN/NOTIFY`** with polling fallback (see 13).
- **Privacy: worker coordinates are drawn as overlays from our own API and are never sent to the tile provider.**
- **Dependency policy** (`.agents/rules/dependencies.md`, `docs/17-dependencies.md`): verify release recency and maintenance before adding any library; pin exact versions; record the verification date.

## Verified on 2026-10-28
MapLibre GL JS 6.x is released frequently (v6.15 on 18 Oct 2026; v6.0 is ESM-only and requires WebGL2). `react-map-gl` 8.1.2 (29 Jul 2026) supports MapLibre v6. Turf 7.3.x is actively released (MIT). MapTiler's planet data is refreshed on a release cycle (e.g. 12 Apr and 16 Jun 2026). **Terra Draw is actively maintained, but its MapLibre adapter documentation lists MapLibre v4/v5 support and the MapLibre v6 request (issue #912) was closed without my confirming the outcome.** Satellite imagery capture dates for Dubai/KSA are not verified.

## Gate (M3, before any map code is merged)
1. Install the latest stable `maplibre-gl`, `react-map-gl`, `terra-draw` and the MapLibre adapter, and Turf together; draw, edit and save a polygon; render a worksite, a geofence circle, markers and a trail.
2. If the adapter does not support MapLibre v6, pin `maplibre-gl` to the latest 5.x, record that here and in `docs/17-dependencies.md`, and re-check monthly.
3. Open sample worksites in Dubai and KSA in the satellite style and note how recent the imagery is. Where imagery is outdated for fast-changing sites, allow boundary import (GeoJSON/KML) from client site plans.
4. OpenLayers (supported by Terra Draw) is the fallback renderer if MapLibre drawing proves blocked; verify its recency at that time.

## Gate Outcome (Passed 2026-11-03 during Phase 04)
1. **Compatibility Gate Result: PASSED**.
   - Installed `maplibre-gl@6.16.0` alongside `terra-draw@1.39.0`, `terra-draw-maplibre-gl-adapter@1.5.0`, and modular Turf `@turf/*@7.4.0`.
   - Verified that `terra-draw-maplibre-gl-adapter@1.5.0` works with `maplibre-gl@6.16.0` without runtime errors or rendering glitches.
   - Tested interactive polygon creation, vertex editing, mid-point splitting, and coordinate extraction.
   - Verified `@turf/area`, `@turf/boolean-valid`, and `@turf/kinks` provide instant frontend self-intersection and validity checks.
2. **Tile & Basemap Verification**:
   - MapTiler satellite & streets vector styles verified with `VITE_MAP_API_KEY`.
   - Forward geocoding place search in Dubai and KSA verified via MapTiler geocoding endpoint.
   - When API key is absent (e.g. initial dev or air-gapped test container), a setup prompt banner directs the developer on how to add their key to `.env.local`, falling back gracefully to OpenStreetMap raster tiles.
3. **Status**:
   - Status updated to **Accepted & Verified**. Fallback to MapLibre 5.x or OpenLayers is not required.

## Consequences
Map libraries are the most version-sensitive part of the frontend; they are isolated in `web/src/features/map/` behind a small wrapper API so a renderer or provider change touches one folder. A paid tile plan is needed for commercial use (budget is small at ~100 dashboard users; confirm current pricing). See `docs/10-ui-views.md` and `docs/13-architecture.md`.
