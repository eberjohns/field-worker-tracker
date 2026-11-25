// Loads the Google Maps JavaScript API once, lazily, only when a map page needs it (ADR-033).
// The key and Map ID come from VITE_GOOGLE_MAPS_API_KEY / VITE_GOOGLE_MAPS_MAP_ID at build time.
//
// It also watches for key or quota failures (Google calls `window.gm_authFailure`, or the script
// fails to load) so the map component can show "Map unavailable today" while the page keeps
// working, and reports our own usage counts to the API.

import { importLibrary, setOptions } from "@googlemaps/js-api-loader";

export interface GoogleMapsConfig {
  apiKey: string;
  mapId: string;
}

export interface GoogleLibs {
  maps: google.maps.MapsLibrary;
  marker: google.maps.MarkerLibrary;
  geocoding: google.maps.GeocodingLibrary;
  core: google.maps.CoreLibrary;
}

export function readGoogleConfig(env: Record<string, string | undefined>): GoogleMapsConfig | null {
  const apiKey = (env.VITE_GOOGLE_MAPS_API_KEY ?? "").trim();
  const mapId = (env.VITE_GOOGLE_MAPS_MAP_ID ?? "").trim();
  return apiKey && mapId ? { apiKey, mapId } : null;
}

export function googleConfig(): GoogleMapsConfig | null {
  return readGoogleConfig(((import.meta as unknown as { env?: Record<string, string> }).env ?? {}) as Record<string, string>);
}

// --- failure state -----------------------------------------------------------------------------

export type MapFailure = "not_configured" | "unavailable";
let failure: MapFailure | null = null;
const listeners = new Set<(f: MapFailure) => void>();

export function mapFailure(): MapFailure | null {
  return failure;
}

export function onMapFailure(fn: (f: MapFailure) => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function reportMapFailure(f: MapFailure): void {
  if (failure === f) return;
  failure = f;
  for (const fn of listeners) fn(f);
}

// --- loading -----------------------------------------------------------------------------------

let loading: Promise<GoogleLibs> | null = null;

export function loadGoogleMaps(): Promise<GoogleLibs> {
  if (loading) return loading;
  const cfg = googleConfig();
  if (!cfg) {
    reportMapFailure("not_configured");
    return Promise.reject(new Error("Google Maps key or Map ID not set"));
  }
  // Google calls this on an invalid, restricted or over-quota key.
  (window as unknown as { gm_authFailure?: () => void }).gm_authFailure = () => reportMapFailure("unavailable");
  setOptions({ key: cfg.apiKey, v: "weekly", mapIds: [cfg.mapId] });
  loading = Promise.all([
    importLibrary("maps"),
    importLibrary("marker"),
    importLibrary("geocoding"),
    importLibrary("core"),
  ]).then(
    ([maps, marker, geocoding, core]) => ({ maps, marker, geocoding, core }),
    (err) => {
      loading = null; // a later page may retry (network blip)
      reportMapFailure("unavailable");
      throw err;
    },
  );
  return loading;
}

// --- our usage counter -------------------------------------------------------------------------

export type UsageKind = "MAP_LOAD" | "GEOCODE";

/** Fire-and-forget POST /api/v1/map-usage; usage counting must never break the map. */
export function reportUsage(kind: UsageKind, fetchImpl: typeof fetch = (...a) => fetch(...a)): void {
  let token: string | null = null;
  try {
    token = localStorage.getItem("fwt_token");
  } catch {
    token = null;
  }
  if (!token) return;
  void fetchImpl("/api/v1/map-usage", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ kind }),
    keepalive: true,
  }).catch(() => undefined);
}
