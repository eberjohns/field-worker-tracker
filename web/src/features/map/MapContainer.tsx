// The map component pages render (ADR-033): a Google map from the pool (google/mapPool.ts),
// handed to the page as a MapPort when ready. If the key is missing, refused or over its quota,
// it shows "Map unavailable today" in place of the map; the rest of the page keeps working.

import React, { useEffect, useRef, useState } from "react";
import { MapPinOff } from "lucide-react";
import type { MapPort } from "./port";
import { googleConfig, loadGoogleMaps, mapFailure, onMapFailure, reportMapFailure, type MapFailure } from "./google/loader";
import { acquireMap, releaseMap, type PooledMap } from "./google/mapPool";
import { GoogleMapsAdapter } from "./google/GoogleMapsAdapter";

export interface MapViewProps {
  initialCenter?: [number, number]; // [lng, lat]
  initialZoom?: number;
  onMapReady?: (map: MapPort) => void;
  /** Called just before the map is handed back (unmount). Use to null-out any stored map reference. */
  onMapUnmount?: () => void;
  className?: string;
  /**
   * For maps embedded in a scrolling page: the wheel scrolls the page and Ctrl/Cmd+wheel
   * (or two fingers) zooms the map, so the page and the map don't both scroll (Batch 10 B).
   */
  cooperativeGestures?: boolean;
  children?: React.ReactNode;
}

const DEFAULT_CENTER: [number, number] = [55.2708, 25.2048]; // Dubai

export const MapUnavailable: React.FC<{ reason: MapFailure }> = ({ reason }) => (
  <div
    role="status"
    className="absolute inset-0 z-30 flex items-center justify-center bg-slate-50 p-6 text-center"
  >
    <div className="max-w-sm space-y-2">
      <MapPinOff className="mx-auto h-8 w-8 text-slate-400" />
      <p className="text-sm font-semibold text-slate-800">
        {reason === "not_configured" ? "Map not configured" : "Map unavailable today (usage limit reached)"}
      </p>
      <p className="text-xs text-slate-600">
        {reason === "not_configured"
          ? "The Google Maps key or Map ID is not set for this build (runbook 08)."
          : "Google Maps refused this request (daily limit or key restriction). Everything else on this page still works; try the map again tomorrow or ask an Admin."}
      </p>
    </div>
  </div>
);

export const MapContainer: React.FC<MapViewProps> = ({
  initialCenter = DEFAULT_CENTER,
  initialZoom = 14,
  onMapReady,
  onMapUnmount,
  className = "w-full h-[500px]",
  cooperativeGestures = false,
  children,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const portRef = useRef<GoogleMapsAdapter | null>(null);
  const [failure, setFailure] = useState<MapFailure | null>(() => (googleConfig() ? mapFailure() : "not_configured"));
  const [ready, setReady] = useState(false);
  const startRef = useRef({ center: initialCenter, zoom: initialZoom });

  useEffect(() => onMapFailure(setFailure), []);

  useEffect(() => {
    if (failure) return;
    let cancelled = false;
    let pooled: PooledMap | null = null;
    let observer: MutationObserver | null = null;

    loadGoogleMaps()
      .then((libs) => {
        if (cancelled || !containerRef.current) return;
        const cfg = googleConfig();
        if (!cfg) return;
        const { center, zoom } = startRef.current;
        pooled = acquireMap(libs.maps, containerRef.current, cfg.mapId, {
          center: { lng: center[0], lat: center[1] },
          zoom,
          gestureHandling: cooperativeGestures ? "cooperative" : "greedy",
        });
        // Google replaces the map with its own error box on quota or referrer errors.
        const div = pooled.div;
        observer = new MutationObserver(() => {
          if (div.querySelector(".gm-err-container")) reportMapFailure("unavailable");
        });
        observer.observe(div, { childList: true, subtree: true });
        const port = new GoogleMapsAdapter(libs, pooled.map);
        portRef.current = port;
        setReady(true);
        onMapReady?.(port);
      })
      .catch(() => {
        // loadGoogleMaps() already reported the failure; the panel shows.
      });

    return () => {
      cancelled = true;
      observer?.disconnect();
      if (portRef.current) {
        onMapUnmount?.();
        portRef.current.dispose();
        portRef.current = null;
      }
      if (pooled) releaseMap(pooled);
      setReady(false);
    };
    // The map is created once per mount; later prop changes move it (below), never rebuild it.
  }, [failure]);

  // When the page's centre arrives after the first render (worksite data), move there.
  useEffect(() => {
    startRef.current = { center: initialCenter, zoom: initialZoom };
    if (ready) portRef.current?.flyTo(initialCenter, initialZoom);
  }, [initialCenter[0], initialCenter[1], initialZoom]);

  return (
    <div className={`relative rounded-lg overflow-hidden border border-slate-200 ${className}`}>
      <div ref={containerRef} className="w-full h-full" />
      {failure ? <MapUnavailable reason={failure} /> : children}
    </div>
  );
};
