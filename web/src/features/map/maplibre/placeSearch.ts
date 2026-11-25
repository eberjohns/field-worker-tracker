// Place search for the MapLibre fallback, unchanged from before Batch 8: MapTiler geocoding
// when VITE_MAP_API_KEY is set, then OpenStreetMap Nominatim. Search runs on Enter only
// (Nominatim's usage policy does not allow search-as-you-type).

import type { PlaceSearchService, PlaceSuggestion } from "../port";

export function createMapLibrePlaceSearch(
  apiKey: string | undefined = (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_MAP_API_KEY,
  fetchImpl: typeof fetch = (...args) => fetch(...args),
): PlaceSearchService {
  return {
    mode: "submit",
    minChars: 1,
    async suggest(query: string, signal?: AbortSignal): Promise<PlaceSuggestion[]> {
      const q = query.trim();
      if (!q) return [];
      if (apiKey) {
        const url = `https://api.maptiler.com/geocoding/${encodeURIComponent(q)}.json?key=${apiKey}&limit=5`;
        const res = await fetchImpl(url, { signal });
        if (res.ok) {
          const data = await res.json();
          const features: { place_name: string; center: [number, number] }[] = data.features || [];
          if (features.length > 0) {
            return features.map((f, i) => ({ id: `mt-${i}`, label: f.place_name, center: f.center }));
          }
        }
      }
      const nomUrl = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(q)}&limit=5`;
      const nomRes = await fetchImpl(nomUrl, { headers: { "Accept-Language": "en" }, signal });
      if (!nomRes.ok) return [];
      const nomData: { display_name: string; lon: string; lat: string; place_id?: number }[] = await nomRes.json();
      return nomData.map((item, i) => ({
        id: `osm-${item.place_id ?? i}`,
        label: item.display_name,
        center: [parseFloat(item.lon), parseFloat(item.lat)],
      }));
    },
    async resolve(s: PlaceSuggestion) {
      return s.center ? { center: s.center } : null;
    },
  };
}
