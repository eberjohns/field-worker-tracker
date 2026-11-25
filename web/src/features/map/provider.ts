// Which map provider the dashboard uses (ADR-033). Pure, so it can be tested.
//
// VITE_MAP_PROVIDER=google needs VITE_GOOGLE_MAPS_API_KEY and VITE_GOOGLE_MAPS_MAP_ID, and the
// Google adapter itself; without any of them the MapLibre fallback is used and the reason logged.

import type { MapProviderName } from "./port";

export interface MapEnv {
  VITE_MAP_PROVIDER?: string;
  VITE_GOOGLE_MAPS_API_KEY?: string;
  VITE_GOOGLE_MAPS_MAP_ID?: string;
}

export interface ProviderChoice {
  provider: MapProviderName;
  /** Why the requested provider was not used; null when it was. */
  fallbackReason: string | null;
  google?: { apiKey: string; mapId: string };
}

/**
 * Set to true once the Google packages are approved and the Google adapter is built (Batch 8,
 * part 3). Until then `google` falls back with a clear reason.
 */
export const GOOGLE_ADAPTER_AVAILABLE = false;

export function chooseMapProvider(env: MapEnv, googleAvailable: boolean = GOOGLE_ADAPTER_AVAILABLE): ProviderChoice {
  const requested = (env.VITE_MAP_PROVIDER ?? "").trim().toLowerCase();
  if (requested === "" || requested === "maplibre") return { provider: "maplibre", fallbackReason: null };
  if (requested !== "google") {
    return { provider: "maplibre", fallbackReason: `Unknown VITE_MAP_PROVIDER "${requested}"; using MapLibre.` };
  }
  const apiKey = (env.VITE_GOOGLE_MAPS_API_KEY ?? "").trim();
  const mapId = (env.VITE_GOOGLE_MAPS_MAP_ID ?? "").trim();
  const missing = [!apiKey && "VITE_GOOGLE_MAPS_API_KEY", !mapId && "VITE_GOOGLE_MAPS_MAP_ID"].filter(Boolean);
  if (missing.length > 0) {
    return { provider: "maplibre", fallbackReason: `Google Maps needs ${missing.join(" and ")}; using MapLibre.` };
  }
  if (!googleAvailable) {
    return { provider: "maplibre", fallbackReason: "The Google Maps adapter is not in this build yet; using MapLibre." };
  }
  return { provider: "google", fallbackReason: null, google: { apiKey, mapId } };
}

let logged = false;

/** The choice for this build, logged once to the browser console when it falls back. */
export function activeMapProvider(): ProviderChoice {
  const env = ((import.meta as unknown as { env?: MapEnv }).env ?? {}) as MapEnv;
  const choice = chooseMapProvider(env);
  if (choice.fallbackReason && !logged) {
    logged = true;
    console.warn(`[map] ${choice.fallbackReason}`);
  }
  return choice;
}
