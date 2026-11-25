import React, { useMemo, useState } from "react";
import { Search, MapPin, Loader2 } from "lucide-react";
import type { MapPort, PlaceResult } from "./port";

interface PlaceSearchProps {
  map: MapPort | null;
}

/**
 * Place search (ADR-033, owner 25 Nov): one geocode per press of Search (or Enter), never while
 * typing. Picking a result only moves the map; nothing from the result is stored.
 */
export const PlaceSearch: React.FC<PlaceSearchProps> = ({ map }) => {
  const service = useMemo(() => map?.placeSearch() ?? null, [map]);
  const [query, setQuery] = useState<string>("");
  const [results, setResults] = useState<PlaceResult[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isOpen, setIsOpen] = useState<boolean>(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!service || isLoading || query.trim().length < 2) return;
    setIsLoading(true);
    setIsOpen(true);
    setMessage(null);
    try {
      const found = await service.search(query);
      setResults(found);
      if (found.length === 0) setMessage("No place found.");
    } catch (err) {
      setResults([]);
      setMessage(err instanceof Error && /unavailable/i.test(err.message) ? err.message : "Search failed. Try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectPlace = (place: PlaceResult) => {
    setIsOpen(false);
    if (!map) return;
    if (place.bbox) map.fitBounds(place.bbox, { padding: 40, maxZoom: 17 });
    else map.flyTo(place.center, 16);
  };

  return (
    <div className="absolute top-3 left-3 sm:left-64 z-20 w-72 max-w-[calc(100%-1.5rem)]">
      <form onSubmit={handleSubmit} className="flex items-stretch gap-1">
        <div className="relative flex-1">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Place or address (UAE / KSA)"
            aria-label="Search place"
            className="w-full pl-8 pr-2 py-1.5 bg-white/95 backdrop-blur-sm border border-slate-300 rounded shadow-sm text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
          <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-400" />
        </div>
        <button
          type="submit"
          disabled={!service || isLoading || query.trim().length < 2}
          className="px-2.5 py-1.5 rounded border border-indigo-600 bg-indigo-600 text-white text-xs font-semibold shadow-sm disabled:opacity-50 inline-flex items-center gap-1"
        >
          {isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
          Search
        </button>
      </form>

      {isOpen && (results.length > 0 || message) && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-lg max-h-48 overflow-y-auto z-30">
          {message && <p className="px-3 py-2 text-xs text-slate-600">{message}</p>}
          {results.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={() => handleSelectPlace(r)}
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
