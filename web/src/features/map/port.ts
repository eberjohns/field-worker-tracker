// The map port (ADR-033). Pages and the map components talk to this interface only; each
// provider (MapLibre today, Google Maps once its packages and keys are in) implements it in
// its own folder. Nothing outside `features/map/<provider>/` imports a map library.
//
// Coordinates are always [longitude, latitude].

import type { TerraDraw } from "terra-draw";
import type { BBox } from "./geo";

export type LngLat = [number, number];
/** The adapter Terra Draw takes (terra-draw does not export the type by name). */
export type TerraDrawAdapter = ConstructorParameters<typeof TerraDraw>[0]["adapter"];
export type MapProviderName = "google" | "maplibre";

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

export interface OverlayOptions {
  /** Keep above everything else, the drawing tool included (the boundary preview). */
  top?: boolean;
}

export interface PointOverlayOptions extends OverlayOptions {
  cluster?: ClusterOptions;
  /** Called with the clicked point's properties. Clicking a cluster zooms into it. */
  onClick?: (properties: Record<string, unknown>) => void;
}

export interface PlaceSuggestion {
  id: string;
  label: string;
  /** Set when the result already carries a position (MapTiler, Nominatim). */
  center?: LngLat;
}

/**
 * Place search for the active provider. Search text goes to the provider; nothing from the
 * results is stored (Google's terms allow keeping place IDs only, and we keep nothing).
 */
export interface PlaceSearchService {
  /** "autocomplete": suggest while typing (debounced); "submit": search on Enter only. */
  readonly mode: "autocomplete" | "submit";
  readonly minChars: number;
  suggest(query: string, signal?: AbortSignal): Promise<PlaceSuggestion[]>;
  /** The position to move the map to. Ends the autocomplete session where there is one. */
  resolve(suggestion: PlaceSuggestion): Promise<{ center: LngLat; bbox?: BBox } | null>;
}

export interface MapPort {
  readonly provider: MapProviderName;

  flyTo(center: LngLat, zoom?: number): void;
  easeTo(center: LngLat, opts?: { zoom?: number; durationMs?: number }): void;
  fitBounds(bbox: BBox, opts?: { padding?: number; maxZoom?: number }): void;

  /** Creates or replaces the overlay `id`. Calling again with the same id updates its data. */
  setPolygons(id: string, features: GeoJSON.Feature<GeoJSON.Polygon>[], style: PolygonStyle, opts?: OverlayOptions): void;
  setLine(id: string, coordinates: LngLat[], style: LineStyle, opts?: OverlayOptions): void;
  setPoints(id: string, features: GeoJSON.Feature<GeoJSON.Point>[], style: PointStyle, opts?: PointOverlayOptions): void;
  removeOverlay(id: string): void;

  /** The Terra Draw adapter for this map (never `google.maps.drawing`). */
  createDrawAdapter(): Promise<TerraDrawAdapter>;
  /** Puts the `top` overlays back above the drawing layers (after Terra Draw redraws). */
  raiseTopOverlays(): void;

  placeSearch(): PlaceSearchService;
}

/** Reads the colour for one feature from a ColorSpec (used by adapters that style per feature). */
export function colorFor(spec: ColorSpec, properties: Record<string, unknown> | null | undefined): string {
  if (typeof spec === "string") return spec;
  const v = properties?.[spec.by];
  return (typeof v === "string" && spec.values[v]) || spec.fallback;
}
