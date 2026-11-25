import React, { useEffect, useMemo, useRef, useState } from "react";
import { Search, MapPin, Loader2 } from "lucide-react";
import type { MapPort, PlaceSuggestion } from "./port";

interface PlaceSearchProps {
  map: MapPort | null;
}

/** Wait after the last keystroke before asking an autocomplete provider (Batch 8). */
export const SEARCH_DEBOUNCE_MS = 300;

/**
 * Place search over the active provider's search service (ADR-033). With Google it suggests
 * while typing (3 characters, 300 ms debounce, one session per pick); with the MapLibre fallback
 * it searches on Enter, as before. Picking a result only moves the map: nothing is stored.
 */
export const PlaceSearch: React.FC<PlaceSearchProps> = ({ map }) => {
  const service = useMemo(() => map?.placeSearch() ?? null, [map]);
  const [query, setQuery] = useState<string>("");
  const [results, setResults] = useState<PlaceSuggestion[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const abortRef = useRef<AbortController | null>(null);

  const run = async (q: string) => {
    if (!service || q.trim().length < service.minChars) {
      setResults([]);
      return;
    }
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setIsLoading(true);
    setIsOpen(true);
    try {
      const found = await service.suggest(q.trim(), ctrl.signal);
      if (!ctrl.signal.aborted) setResults(found);
    } catch (err) {
      if (!ctrl.signal.aborted) console.error("Place search failed:", err);
    } finally {
      if (abortRef.current === ctrl) setIsLoading(false);
    }
  };

  // Autocomplete providers: search while typing, debounced.
  useEffect(() => {
    if (!service || service.mode !== "autocomplete") return;
    const timer = setTimeout(() => void run(query), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query, service]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void run(query);
  };

  const handleSelectPlace = async (place: PlaceSuggestion) => {
    setIsOpen(false);
    if (!map || !service) return;
    try {
      const target = await service.resolve(place);
      if (!target) return;
      if (target.bbox) map.fitBounds(target.bbox, { padding: 40, maxZoom: 17 });
      else map.flyTo(target.center, 16);
    } catch (err) {
      console.error("Place lookup failed:", err);
    }
  };

  const placeholder =
    service?.mode === "autocomplete"
      ? "Search a place or address (UAE / KSA)..."
      : "Search place worldwide (e.g. Dubai, Riyadh, Kerala)...";

  return (
    <div className="absolute top-3 left-64 z-20 w-72">
      <form onSubmit={handleSubmit} className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          aria-label="Search place"
          className="w-full pl-8 pr-8 py-1.5 bg-white/95 backdrop-blur-sm border border-slate-300 rounded shadow-sm text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
        <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-400" />
        {isLoading && (
          <Loader2 className="absolute right-2.5 top-2 h-3.5 w-3.5 text-slate-400 animate-spin" />
        )}
      </form>

      {isOpen && results.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-lg max-h-48 overflow-y-auto z-30">
          {results.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={() => void handleSelectPlace(r)}
              className="w-full text-left px-3 py-2 text-xs hover:bg-indigo-50 flex items-start gap-2 border-b border-slate-100 last:border-b-0"
            >
              <MapPin className="h-3.5 w-3.5 text-indigo-600 shrink-0 mt-0.5" />
              <span className="text-slate-700 leading-tight line-clamp-2">{r.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
