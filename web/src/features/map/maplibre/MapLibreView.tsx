import React, { useEffect, useRef, useState } from "react";
import { Map as MapLibreMap, NavigationControl, setWorkerUrl } from "maplibre-gl";
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import "maplibre-gl/dist/maplibre-gl.css";
import { AlertTriangle } from "lucide-react";
import type { MapViewProps } from "../MapContainer";
import { MapLibreAdapter } from "./MapLibreAdapter";

// Ensure MapLibre Web Worker loads correctly in Vite development and production builds
setWorkerUrl(maplibreWorkerUrl);

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

/** The MapLibre map (ADR-033 fallback): MapTiler styles with VITE_MAP_API_KEY, else OSM. */
export const MapLibreView: React.FC<MapViewProps> = ({
  initialCenter = DEFAULT_CENTER,
  initialZoom = 14,
  onMapReady,
  onMapUnmount,
  className = "w-full h-[500px]",
  cooperativeGestures = false,
  children,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const portRef = useRef<MapLibreAdapter | null>(null);
  const currentCenterRef = useRef<[number, number]>(initialCenter);
  const currentZoomRef = useRef<number>(initialZoom);
  const [mapStyle, setMapStyle] = useState<"streets" | "satellite" | "osm">("satellite");
  const apiKey = (import.meta as any).env?.VITE_MAP_API_KEY;

  const getStyleUrl = (style: "streets" | "satellite" | "osm"): any => {
    if (style === "osm" || !apiKey) {
      return FALLBACK_STYLE;
    }
    if (style === "satellite") {
      return `https://api.maptiler.com/maps/satellite/style.json?key=${apiKey}`;
    }
    return `https://api.maptiler.com/maps/streets-v2/style.json?key=${apiKey}`;
  };

  useEffect(() => {
    if (!containerRef.current) return;

    const initialStyleUrl = getStyleUrl(mapStyle);
    const map = new MapLibreMap({
      container: containerRef.current,
      style: initialStyleUrl,
      center: currentCenterRef.current,
      zoom: currentZoomRef.current,
      attributionControl: { compact: true },
      maxTileCacheSize: 200,
      cooperativeGestures,
    });

    map.addControl(new NavigationControl({ showCompass: true }), "top-right");

    map.on("moveend", () => {
      const c = map.getCenter();
      currentCenterRef.current = [c.lng, c.lat];
      currentZoomRef.current = map.getZoom();
    });

    map.on("error", (e) => {
      console.warn("MapLibre error:", e);
      if (mapStyle === "streets" && e?.error?.message?.includes("Failed to fetch")) {
        setMapStyle("osm");
      }
    });

    map.on("load", () => {
      mapRef.current = map;
      const port = new MapLibreAdapter(map);
      portRef.current = port;
      map.resize();
      setTimeout(() => map.resize(), 100);
      setTimeout(() => map.resize(), 500);
      if (onMapReady) {
        onMapReady(port);
      }
    });

    return () => {
      // Notify parent BEFORE destroying the map so it can null-out any stored reference
      // (e.g. PolygonEditor's map prop). This prevents Terra Draw from re-initializing
      // against an already-destroyed map instance.
      if (onMapUnmount) {
        onMapUnmount();
      }
      portRef.current?.dispose();
      portRef.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, [mapStyle, apiKey]);

  // If initialCenter changes (e.g. worksite data arrives after initial render), fly to it
  useEffect(() => {
    if (portRef.current && initialCenter) {
      currentCenterRef.current = initialCenter;
      currentZoomRef.current = initialZoom;
      portRef.current?.flyTo(initialCenter, initialZoom);
    }
  }, [initialCenter[0], initialCenter[1], initialZoom]);

  const handleStyleChange = (nextStyle: "streets" | "satellite" | "osm") => {
    if (nextStyle !== mapStyle) {
      setMapStyle(nextStyle);
    }
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
      <div className="absolute top-3 left-3 z-20 flex items-center bg-white/95 backdrop-blur-sm border border-slate-300 rounded shadow-sm overflow-hidden text-xs font-medium">
        <button
          type="button"
          onClick={() => handleStyleChange("satellite")}
          className={`px-2.5 py-1.5 transition ${
            mapStyle === "satellite"
              ? "bg-indigo-600 text-white font-semibold"
              : "text-slate-700 hover:bg-slate-100"
          }`}
        >
          Satellite
        </button>
        <button
          type="button"
          onClick={() => handleStyleChange("streets")}
          className={`px-2.5 py-1.5 border-l border-slate-200 transition ${
            mapStyle === "streets"
              ? "bg-indigo-600 text-white font-semibold"
              : "text-slate-700 hover:bg-slate-100"
          }`}
        >
          Vector Streets
        </button>
        <button
          type="button"
          onClick={() => handleStyleChange("osm")}
          className={`px-2.5 py-1.5 border-l border-slate-200 transition ${
            mapStyle === "osm"
              ? "bg-indigo-600 text-white font-semibold"
              : "text-slate-700 hover:bg-slate-100"
          }`}
          title="OpenStreetMap Standard Raster (Reliable fallback)"
        >
          OSM Streets
        </button>
      </div>

      {/* Map Canvas */}
      <div ref={containerRef} className="w-full h-full" />

      {/* Child Overlay Components (e.g. Toolbar, PlaceSearch) */}
      {children}
    </div>
  );
};
