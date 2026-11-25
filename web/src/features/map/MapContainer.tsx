// The map component pages render (ADR-033). It picks the provider once per build
// (provider.ts) and hands the page a MapPort when the map is ready.

import React from "react";
import type { MapPort } from "./port";
import { activeMapProvider } from "./provider";
import { MapLibreView } from "./maplibre/MapLibreView";

export interface MapViewProps {
  initialCenter?: [number, number]; // [lng, lat]
  initialZoom?: number;
  onMapReady?: (map: MapPort) => void;
  /** Called just before the map is destroyed (style switch or unmount). Use to null-out any stored map reference. */
  onMapUnmount?: () => void;
  className?: string;
  /**
   * For maps embedded in a scrolling page: the wheel scrolls the page and Ctrl/Cmd+wheel
   * (or two fingers) zooms the map, so the page and the map don't both scroll (Batch 10 B).
   */
  cooperativeGestures?: boolean;
  children?: React.ReactNode;
}

export const MapContainer: React.FC<MapViewProps> = (props) => {
  // Only the MapLibre view exists until the Google adapter lands (provider.ts falls back).
  activeMapProvider();
  return <MapLibreView {...props} />;
};
