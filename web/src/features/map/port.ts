// The map port (ADR-033). Pages and the map components talk to this interface only; the Google
// Maps implementation lives in `google/`. Nothing outside `features/map/google/` touches
// `google.maps`, so a provider change stays one adapter.
//
// Coordinates are always [longitude, latitude].

import type { TerraDraw } from "terra-draw";
import type { BBox } from "./geo";

export type LngLat = [number, number];
/** The adapter Terra Draw takes (terra-draw does not export the type by name). */
export type TerraDrawAdapter = ConstructorParameters<typeof TerraDraw>[0]["adapter"];

/** A colour, or a colour picked from a feature property (with a fallback). */
export type ColorSpec = string | { by: string; values: Record<string, string>; fallback: string };

export interface PolygonStyle {
  fillColor: string;
  fillOpacity: number;
  strokeColor: string;
  strokeWidth: number;
  dashed?: boolean;
}

export interface LineStyle {
  color: string;
  width: number;
  dashed?: boolean;
}

export interface PointStyle {
  color: ColorSpec;
  /** Radius in screen pixels. */
  radius: number;
  strokeColor?: string;
  strokeWidth?: number;
  /** A soft circle drawn under the point (the replay marker). */
  halo?: { color: string; radius: number; opacity: number };
}

export interface ClusterOptions {
  /** Points stop clustering above this zoom. */
  maxZoom: number;
  /** Cluster radius in screen pixels. */
  radius: number;
}

export interface PointOverlayOptions {
  cluster?: ClusterOptions;
  /** Called with the clicked point's properties. Clicking a cluster zooms into it. */
  onClick?: (properties: Record<string, unknown>) => void;
}

export interface PlaceResult {
  /** The provider's place ID: the only thing we may keep (we keep nothing). */
  id: string;
  label: string;
  center: LngLat;
  bbox?: BBox;
}

/**
 * Place search. Runs only when the user presses Search (no autocomplete); the search text goes
 * to the provider and nothing from the results is stored.
 */
export interface PlaceSearchService {
  search(query: string): Promise<PlaceResult[]>;
}

export interface MapPort {
  flyTo(center: LngLat, zoom?: number): void;
  easeTo(center: LngLat, opts?: { zoom?: number; durationMs?: number }): void;
  fitBounds(bbox: BBox, opts?: { padding?: number; maxZoom?: number }): void;

  /**
   * Creates or updates the overlay `id` in place: calling again with the same id moves, restyles
   * or removes its shapes and markers; it never rebuilds the map.
   */
  setPolygons(id: string, features: GeoJSON.Feature<GeoJSON.Polygon>[], style: PolygonStyle): void;
  setLine(id: string, coordinates: LngLat[], style: LineStyle): void;
  /** Points keep their marker across updates when the feature has an `id`. */
  setPoints(id: string, features: GeoJSON.Feature<GeoJSON.Point>[], style: PointStyle, opts?: PointOverlayOptions): void;
  removeOverlay(id: string): void;

  /** The Terra Draw adapter for this map (never `google.maps.drawing`). */
  createDrawAdapter(): Promise<TerraDrawAdapter>;

  placeSearch(): PlaceSearchService;
}

/** Reads the colour for one feature from a ColorSpec. */
export function colorFor(spec: ColorSpec, properties: Record<string, unknown> | null | undefined): string {
  if (typeof spec === "string") return spec;
  const v = properties?.[spec.by];
  return (typeof v === "string" && spec.values[v]) || spec.fallback;
}
