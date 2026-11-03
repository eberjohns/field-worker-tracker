import React, { useState } from "react";
import { Map as MapLibreMap } from "maplibre-gl";
import { Search, MapPin, Loader2 } from "lucide-react";

interface PlaceSearchProps {
  map: MapLibreMap | null;
}

interface PlaceResult {
  place_name: string;
  center: [number, number]; // [lng, lat]
}

export const PlaceSearch: React.FC<PlaceSearchProps> = ({ map }) => {
  const [query, setQuery] = useState<string>("");
  const [results, setResults] = useState<PlaceResult[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const apiKey = (import.meta as any).env?.VITE_MAP_API_KEY;

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setIsOpen(true);
    try {
      if (apiKey) {
        const url = `https://api.maptiler.com/geocoding/${encodeURIComponent(
          query.trim()
        )}.json?key=${apiKey}&limit=5`;
        const res = await fetch(url);
        if (res.ok) {
          const data = await res.json();
          const features = data.features || [];
          if (features.length > 0) {
            setResults(
              features.map((f: any) => ({
                place_name: f.place_name,
                center: f.center,
              }))
            );
            return;
          }
        }
      }

      // Fallback to OpenStreetMap Nominatim (works worldwide including Kerala, India, Dubai without API key)
      const nomUrl = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(
        query.trim()
      )}&limit=5`;
      const nomRes = await fetch(nomUrl, {
        headers: { "Accept-Language": "en" },
      });
      if (nomRes.ok) {
        const nomData = await nomRes.json();
        setResults(
          nomData.map((item: any) => ({
            place_name: item.display_name,
            center: [parseFloat(item.lon), parseFloat(item.lat)],
          }))
        );
      }
    } catch (err) {
      console.error("Geocoding search failed:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectPlace = (place: PlaceResult) => {
    if (map) {
      map.flyTo({
        center: place.center,
        zoom: 16,
        essential: true,
      });
    }
    setIsOpen(false);
  };

  return (
    <div className="absolute top-3 left-64 z-20 w-72">
      <form onSubmit={handleSearch} className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search place worldwide (e.g. Dubai, Riyadh, Kerala)..."
          className="w-full pl-8 pr-8 py-1.5 bg-white/95 backdrop-blur-sm border border-slate-300 rounded shadow-sm text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
        <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-400" />
        {isLoading && (
          <Loader2 className="absolute right-2.5 top-2 h-3.5 w-3.5 text-slate-400 animate-spin" />
        )}
      </form>

      {/* Results dropdown */}
      {isOpen && results.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-lg max-h-48 overflow-y-auto z-30">
          {results.map((r, i) => (
            <button
              key={i}
              type="button"
              onClick={() => handleSelectPlace(r)}
              className="w-full text-left px-3 py-2 text-xs hover:bg-indigo-50 flex items-start gap-2 border-b border-slate-100 last:border-b-0"
            >
              <MapPin className="h-3.5 w-3.5 text-indigo-600 shrink-0 mt-0.5" />
              <span className="text-slate-700 leading-tight line-clamp-2">{r.place_name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

