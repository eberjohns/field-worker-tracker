import React, { useEffect, useRef, useState } from "react";
import { Map as MapLibreMap, NavigationControl } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { AlertTriangle, Layers } from "lucide-react";

interface MapContainerProps {
  initialCenter?: [number, number]; // [lng, lat]
  initialZoom?: number;
  onMapReady?: (map: MapLibreMap) => void;
  className?: string;
  children?: React.ReactNode;
}

const DEFAULT_CENTER: [number, number] = [55.2708, 25.2048]; // Dubai
const FALLBACK_STYLE = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "&copy; OpenStreetMap Contributors",
    },
  },
  layers: [
    {
      id: "osm-layer",
      type: "raster",
      source: "osm",
      minzoom: 0,
      maxzoom: 19,
    },
  ],
};

export const MapContainer: React.FC<MapContainerProps> = ({
  initialCenter = DEFAULT_CENTER,
  initialZoom = 14,
  onMapReady,
  className = "w-full h-[500px]",
  children,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [mapStyle, setMapStyle] = useState<"streets" | "satellite">("streets");
  const apiKey = (import.meta as any).env?.VITE_MAP_API_KEY;

  useEffect(() => {
    if (!containerRef.current) return;

    let styleUrl: any = FALLBACK_STYLE;
    if (apiKey) {
      styleUrl =
        mapStyle === "satellite"
          ? `https://api.maptiler.com/maps/satellite/style.json?key=${apiKey}`
          : `https://api.maptiler.com/maps/streets-v2/style.json?key=${apiKey}`;
    }

    const map = new MapLibreMap({
      container: containerRef.current,
      style: styleUrl,
      center: initialCenter,
      zoom: initialZoom,
      attributionControl: { compact: true },
    });

    map.addControl(new NavigationControl({ showCompass: true }), "top-right");

    map.on("load", () => {
      mapRef.current = map;
      if (onMapReady) {
        onMapReady(map);
      }
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [mapStyle, apiKey]);

  const toggleStyle = () => {
    const nextStyle = mapStyle === "streets" ? "satellite" : "streets";
    setMapStyle(nextStyle);
  };

  return (
    <div className={`relative rounded-lg overflow-hidden border border-slate-200 ${className}`}>
      {/* Map API Key Missing Prompt Banner */}
      {!apiKey && (
        <div className="absolute top-3 left-3 right-3 z-30 bg-amber-50 border border-amber-300 rounded-md p-3 text-xs text-amber-900 shadow-md flex items-start gap-2.5">
          <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <span className="font-semibold text-amber-950">
              Map API Key Missing (VITE_MAP_API_KEY)
            </span>
            <p className="text-amber-800 leading-relaxed">
              Using public OpenStreetMap fallback. For high-resolution satellite imagery and search
              in Dubai/KSA:
            </p>
            <ol className="list-decimal list-inside space-y-0.5 text-amber-800">
              <li>
                Sign up for free at{" "}
                <a
                  href="https://cloud.maptiler.com"
                  target="_blank"
                  rel="noreferrer"
                  className="underline font-medium hover:text-amber-950"
                >
                  cloud.maptiler.com
                </a>
              </li>
              <li>
                Add <code className="bg-amber-100 px-1 py-0.5 rounded">VITE_MAP_API_KEY=your_key</code>{" "}
                to <code className="bg-amber-100 px-1 py-0.5 rounded">web/.env.local</code>
              </li>
              <li>Restart Vite dev server</li>
            </ol>
          </div>
        </div>
      )}

      {/* Satellite / Street Switcher Button */}
      {apiKey && (
        <div className="absolute top-3 left-3 z-20">
          <button
            type="button"
            onClick={toggleStyle}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white hover:bg-slate-50 border border-slate-300 rounded shadow-sm text-xs font-medium text-slate-700 transition"
          >
            <Layers className="h-3.5 w-3.5 text-slate-500" />
            Switch to {mapStyle === "streets" ? "Satellite" : "Streets"}
          </button>
        </div>
      )}

      {/* Map Canvas */}
      <div ref={containerRef} className="w-full h-full" />

      {/* Child Overlay Components (e.g. Toolbar, PlaceSearch) */}
      {children}
    </div>
  );
};
