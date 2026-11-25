// Google Maps implementation of the map port (ADR-033).
//
// Shapes and markers are updated in place: a refresh or a live-stream reconnect moves the existing
// markers and reshapes the existing polygons; the map itself is never rebuilt. Markers are
// AdvancedMarkerElement (google.maps.Marker is deprecated). Worker clustering uses our grid
// clusterer, re-run when the zoom changes.

import type { BBox } from "../geo";
import { gridCluster, clusterStyle } from "../gridCluster";
import {
  colorFor,
  type LineStyle,
  type LngLat,
  type MapPort,
  type PlaceResult,
  type PlaceSearchService,
  type PointOverlayOptions,
  type PointStyle,
  type PolygonStyle,
  type TerraDrawAdapter,
} from "../port";
import { reportUsage } from "./loader";

/** The parts of the Google libraries the adapter uses (tests pass fakes). */
export interface AdapterLibs {
  maps: Pick<google.maps.MapsLibrary, "Polygon" | "Polyline">;
  marker: Pick<google.maps.MarkerLibrary, "AdvancedMarkerElement">;
  geocoding: Pick<google.maps.GeocodingLibrary, "Geocoder">;
  core: Pick<google.maps.CoreLibrary, "LatLngBounds">;
}

/** Search bias: UAE and KSA (the two deployments, ADR-009). */
export const SEARCH_BOUNDS = { south: 16.2, west: 34.4, north: 32.3, east: 56.6 };

export class SearchUnavailableError extends Error {
  constructor(readonly status: string) {
    super(
      status === "REQUEST_DENIED"
        ? "Place search unavailable: the map key does not allow the Geocoding API (runbook 08)"
        : "Place search unavailable today (usage limit reached)",
    );
  }
}

const toLatLng = ([lng, lat]: LngLat | number[]): google.maps.LatLngLiteral => ({ lat, lng });

function dashIcons(color: string, width: number): google.maps.IconSequence[] {
  return [
    {
      icon: { path: "M 0,-1 0,1", strokeOpacity: 1, strokeColor: color, scale: Math.max(1, width) },
      offset: "0",
      repeat: `${Math.max(6, width * 4)}px`,
    },
  ];
}

function alphaHex(opacity: number): string {
  return Math.round(Math.max(0, Math.min(1, opacity)) * 255)
    .toString(16)
    .padStart(2, "0");
}

/** A round marker element, centred on its position (advanced markers anchor at bottom centre). */
export function dotElement(color: string, style: PointStyle, label?: string, radius = style.radius): HTMLElement {
  const el = document.createElement("div");
  const size = radius * 2;
  el.style.width = `${size}px`;
  el.style.height = `${size}px`;
  el.style.borderRadius = "50%";
  el.style.background = color;
  el.style.boxSizing = "border-box";
  el.style.border = `${style.strokeWidth ?? 0}px solid ${style.strokeColor ?? "#ffffff"}`;
  el.style.transform = "translateY(50%)";
  if (style.halo) {
    const spread = Math.max(0, style.halo.radius - radius);
    el.style.boxShadow = `0 0 0 ${spread}px ${style.halo.color}${alphaHex(style.halo.opacity)}`;
  }
  if (label !== undefined) {
    el.textContent = label;
    el.style.color = "#ffffff";
    el.style.font = "600 12px system-ui, sans-serif";
    el.style.display = "flex";
    el.style.alignItems = "center";
    el.style.justifyContent = "center";
  }
  el.dataset.color = color;
  return el;
}

interface PolygonOverlay {
  kind: "polygons";
  shapes: google.maps.Polygon[];
  dashes: google.maps.Polyline[];
}
interface LineOverlay {
  kind: "line";
  line: google.maps.Polyline;
}
interface PointsOverlay {
  kind: "points";
  markers: Map<string, google.maps.marker.AdvancedMarkerElement>;
  props: Map<string, Record<string, unknown>>;
  clusterZoom: Map<string, { center: LngLat; zoom: number }>;
  features: GeoJSON.Feature<GeoJSON.Point>[];
  style: PointStyle;
  opts: PointOverlayOptions;
  zoomListener?: google.maps.MapsEventListener;
  lastZoom?: number;
}
type Overlay = PolygonOverlay | LineOverlay | PointsOverlay;

export class GoogleMapsAdapter implements MapPort {
  private overlays = new Map<string, Overlay>();
  private disposed = false;

  constructor(
    private readonly libs: AdapterLibs,
    readonly map: google.maps.Map,
  ) {}

  /** Removes everything this page drew; the map itself goes back to the pool. */
  dispose(): void {
    for (const id of [...this.overlays.keys()]) this.removeOverlay(id);
    this.disposed = true;
  }

  // --- camera ----------------------------------------------------------------------------------

  flyTo(center: LngLat, zoom?: number): void {
    this.easeTo(center, { zoom });
  }

  easeTo(center: LngLat, opts: { zoom?: number; durationMs?: number } = {}): void {
    if (this.disposed) return;
    if (opts.zoom !== undefined) this.map.setZoom(opts.zoom);
    this.map.panTo(toLatLng(center));
  }

  fitBounds(bbox: BBox, opts: { padding?: number; maxZoom?: number } = {}): void {
    if (this.disposed) return;
    const bounds = new this.libs.core.LatLngBounds({ lat: bbox[1], lng: bbox[0] }, { lat: bbox[3], lng: bbox[2] });
    this.map.fitBounds(bounds, opts.padding ?? 80);
    const maxZoom = opts.maxZoom ?? 18;
    google.maps.event.addListenerOnce(this.map, "idle", () => {
      const z = this.map.getZoom();
      if (z !== undefined && z > maxZoom) this.map.setZoom(maxZoom);
    });
  }

  // --- overlays --------------------------------------------------------------------------------

  setPolygons(id: string, features: GeoJSON.Feature<GeoJSON.Polygon>[], style: PolygonStyle): void {
    if (this.disposed) return;
    let o = this.overlays.get(id);
    if (!o || o.kind !== "polygons") {
      if (o) this.removeOverlay(id);
      o = { kind: "polygons", shapes: [], dashes: [] };
      this.overlays.set(id, o);
    }
    const ov = o;
    features.forEach((f, i) => {
      const paths = f.geometry.coordinates.map((ring) => ring.map(toLatLng));
      const options: google.maps.PolygonOptions = {
        paths,
        fillColor: style.fillColor,
        fillOpacity: style.fillOpacity,
        strokeColor: style.strokeColor,
        strokeWeight: style.dashed ? 0 : style.strokeWidth,
        strokeOpacity: style.dashed ? 0 : 1,
        clickable: false,
        map: this.map,
      };
      if (ov.shapes[i]) ov.shapes[i].setOptions(options);
      else ov.shapes[i] = new this.libs.maps.Polygon(options);
      if (style.dashed) {
        const outline = { path: paths[0], strokeOpacity: 0, icons: dashIcons(style.strokeColor, style.strokeWidth), clickable: false, map: this.map };
        if (ov.dashes[i]) ov.dashes[i].setOptions(outline);
        else ov.dashes[i] = new this.libs.maps.Polyline(outline);
      }
    });
    for (const extra of ov.shapes.splice(features.length)) extra.setMap(null);
    for (const extra of ov.dashes.splice(style.dashed ? features.length : 0)) extra.setMap(null);
  }

  setLine(id: string, coordinates: LngLat[], style: LineStyle): void {
    if (this.disposed) return;
    const options: google.maps.PolylineOptions = {
      path: coordinates.map(toLatLng),
      strokeColor: style.color,
      strokeWeight: style.width,
      strokeOpacity: style.dashed ? 0 : 1,
      icons: style.dashed ? dashIcons(style.color, style.width) : [],
      clickable: false,
      map: this.map,
    };
    const o = this.overlays.get(id);
    if (o && o.kind === "line") {
      o.line.setOptions(options);
      return;
    }
    if (o) this.removeOverlay(id);
    this.overlays.set(id, { kind: "line", line: new this.libs.maps.Polyline(options) });
  }

  setPoints(
    id: string,
    features: GeoJSON.Feature<GeoJSON.Point>[],
    style: PointStyle,
    opts: PointOverlayOptions = {},
  ): void {
    if (this.disposed) return;
    let o = this.overlays.get(id);
    if (!o || o.kind !== "points") {
      if (o) this.removeOverlay(id);
      const created: PointsOverlay = {
        kind: "points",
        markers: new Map(),
        props: new Map(),
        clusterZoom: new Map(),
        features,
        style,
        opts,
      };
      if (opts.cluster) {
        created.zoomListener = this.map.addListener("idle", () => {
          if (this.map.getZoom() !== created.lastZoom) this.renderPoints(created);
        });
      }
      this.overlays.set(id, created);
      o = created;
    }
    o.features = features;
    o.style = style;
    o.opts = opts;
    this.renderPoints(o);
  }

  private renderPoints(o: PointsOverlay): void {
    if (this.disposed) return;
    const zoom = this.map.getZoom() ?? 0;
    o.lastZoom = zoom;
    const wanted = new Map<string, { position: LngLat; color: string; label?: string; radius?: number }>();
    o.props.clear();
    o.clusterZoom.clear();

    const items = o.features.map((f, i) => ({
      key: `p:${f.id ?? (f.properties?.id as string | undefined) ?? i}`,
      position: f.geometry.coordinates as LngLat,
      props: (f.properties ?? {}) as Record<string, unknown>,
    }));
    const groups = o.opts.cluster
      ? gridCluster(
          items.map((it) => ({ position: it.position, item: it })),
          zoom,
          o.opts.cluster,
        )
      : items.map((it) => ({ kind: "point" as const, position: it.position, item: it }));

    for (const g of groups) {
      if (g.kind === "point") {
        wanted.set(g.item.key, { position: g.position, color: colorFor(o.style.color, g.item.props) });
        o.props.set(g.item.key, g.item.props);
      } else {
        const cs = clusterStyle(g.count);
        const key = `c:${g.items.map((it) => it.key).sort().join(",")}`;
        wanted.set(key, { position: g.position, color: cs.color, label: cs.label, radius: cs.radius });
        o.clusterZoom.set(key, { center: g.position, zoom: g.expansionZoom });
      }
    }

    for (const [key, marker] of o.markers) {
      if (!wanted.has(key)) {
        marker.map = null;
        o.markers.delete(key);
      }
    }
    for (const [key, w] of wanted) {
      const existing = o.markers.get(key);
      const clusterStroke: PointStyle = { ...o.style, strokeColor: "#ffffff", strokeWidth: 2, halo: undefined };
      if (existing) {
        existing.position = toLatLng(w.position);
        const el = existing.content as HTMLElement | null;
        if (el && el.dataset.color !== w.color) {
          existing.content = dotElement(w.color, w.label !== undefined ? clusterStroke : o.style, w.label, w.radius);
        }
        continue;
      }
      const isCluster = w.label !== undefined;
      const clickable = isCluster || Boolean(o.opts.onClick);
      const marker = new this.libs.marker.AdvancedMarkerElement({
        map: this.map,
        position: toLatLng(w.position),
        content: dotElement(w.color, isCluster ? clusterStroke : o.style, w.label, w.radius),
        gmpClickable: clickable,
      });
      if (clickable) {
        marker.addListener("click", () => {
          const target = o.clusterZoom.get(key);
          if (target) {
            this.easeTo(target.center, { zoom: target.zoom });
            return;
          }
          const props = o.props.get(key);
          if (props && o.opts.onClick) o.opts.onClick(props);
        });
      }
      o.markers.set(key, marker);
    }
  }

  removeOverlay(id: string): void {
    const o = this.overlays.get(id);
    this.overlays.delete(id);
    if (!o) return;
    if (o.kind === "polygons") {
      for (const s of o.shapes) s.setMap(null);
      for (const d of o.dashes) d.setMap(null);
    } else if (o.kind === "line") {
      o.line.setMap(null);
    } else {
      o.zoomListener?.remove();
      for (const m of o.markers.values()) m.map = null;
      o.markers.clear();
    }
  }

  // --- drawing and search ----------------------------------------------------------------------

  async createDrawAdapter(): Promise<TerraDrawAdapter> {
    const { TerraDrawGoogleMapsAdapter } = await import("terra-draw-google-maps-adapter");
    return new TerraDrawGoogleMapsAdapter({
      lib: google.maps,
      map: this.map,
      coordinatePrecision: 7,
      isolatedData: true,
    }) as unknown as TerraDrawAdapter;
  }

  placeSearch(): PlaceSearchService {
    return createGeocodeSearch(this.libs.geocoding);
  }
}

/**
 * Search on the Geocoding service, only when the user presses Search (owner, 25 Nov: no
 * autocomplete, no reverse geocoding, nothing stored). Each request is counted.
 */
export function createGeocodeSearch(
  geocoding: Pick<google.maps.GeocodingLibrary, "Geocoder">,
  count: () => void = () => reportUsage("GEOCODE"),
): PlaceSearchService {
  let geocoder: google.maps.Geocoder | null = null;
  return {
    async search(query: string): Promise<PlaceResult[]> {
      const q = query.trim();
      if (q.length < 2) return [];
      geocoder ??= new geocoding.Geocoder();
      count();
      try {
        const { results } = await geocoder.geocode({ address: q, bounds: SEARCH_BOUNDS, language: "en" });
        return results.slice(0, 5).map((r) => {
          const loc = r.geometry.location;
          const vp = r.geometry.viewport;
          return {
            id: r.place_id,
            label: r.formatted_address,
            center: [loc.lng(), loc.lat()] as LngLat,
            bbox: vp
              ? ([vp.getSouthWest().lng(), vp.getSouthWest().lat(), vp.getNorthEast().lng(), vp.getNorthEast().lat()] as BBox)
              : undefined,
          };
        });
      } catch (err) {
        const code = (err as { code?: string })?.code ?? "";
        if (code === "ZERO_RESULTS") return [];
        console.warn(`[map] place search failed: ${code || String(err)}`);
        if (code === "OVER_QUERY_LIMIT" || code === "OVER_DAILY_LIMIT" || code === "REQUEST_DENIED") {
          throw new SearchUnavailableError(code);
        }
        throw err;
      }
    },
  };
}
