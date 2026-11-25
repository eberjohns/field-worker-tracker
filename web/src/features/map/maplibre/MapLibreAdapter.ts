// MapLibre implementation of the map port (ADR-033 fallback). The layers, paints and
// clustering are the ones the pages used directly before Batch 8.

import type { GeoJSONSource, Map as MapLibreMap, MapLayerMouseEvent } from "maplibre-gl";

import type { BBox } from "../geo";
import type {
  ColorSpec,
  TerraDrawAdapter,
  LineStyle,
  LngLat,
  MapPort,
  OverlayOptions,
  PlaceSearchService,
  PointOverlayOptions,
  PointStyle,
  PolygonStyle,
} from "../port";
import { createMapLibrePlaceSearch } from "./placeSearch";

type Kind = "fill" | "line" | "point";

interface Overlay {
  layers: { id: string; kind: Kind }[];
  top: boolean;
  onClick?: (properties: Record<string, unknown>) => void;
}

// Terra Draw's MapLibre layers, in drawing order. `top` overlays are interleaved with them so a
// boundary preview stays visible over satellite tiles and the drawing tool.
const TD_FILL = ["td-polygon"];
const TD_LINE = ["td-polygon-outline", "td-linestring"];
const TD_POINT = ["td-point", "td-point-marker"];

function colorExpression(spec: ColorSpec): unknown {
  if (typeof spec === "string") return spec;
  const pairs = Object.entries(spec.values).flat();
  return ["match", ["get", spec.by], ...pairs, spec.fallback];
}

export class MapLibreAdapter implements MapPort {
  readonly provider = "maplibre" as const;
  private overlays = new Map<string, Overlay>();
  private disposed = false;
  private readonly keepOnTop = () => {
    if (!this.disposed && this.map.isStyleLoaded()) this.raiseTopOverlays();
  };

  constructor(readonly map: MapLibreMap) {
    map.on("styledata", this.keepOnTop);
    map.on("sourcedata", this.keepOnTop);
    map.on("idle", this.keepOnTop);
  }

  /** Called by the map view just before `map.remove()`; later calls do nothing. */
  dispose(): void {
    this.disposed = true;
    this.map.off("styledata", this.keepOnTop);
    this.map.off("sourcedata", this.keepOnTop);
    this.map.off("idle", this.keepOnTop);
  }

  flyTo(center: LngLat, zoom?: number): void {
    if (this.disposed) return;
    this.map.flyTo({ center, ...(zoom !== undefined ? { zoom } : {}), essential: true });
  }

  easeTo(center: LngLat, opts: { zoom?: number; durationMs?: number } = {}): void {
    if (this.disposed) return;
    this.map.easeTo({
      center,
      ...(opts.zoom !== undefined ? { zoom: opts.zoom } : {}),
      ...(opts.durationMs !== undefined ? { duration: opts.durationMs } : {}),
    });
  }

  fitBounds(bbox: BBox, opts: { padding?: number; maxZoom?: number } = {}): void {
    if (this.disposed) return;
    this.map.fitBounds(
      [
        [bbox[0], bbox[1]],
        [bbox[2], bbox[3]],
      ],
      { padding: opts.padding ?? 80, maxZoom: opts.maxZoom ?? 18 },
    );
  }

  private setData(id: string, data: GeoJSON.FeatureCollection): boolean {
    const src = this.map.getSource(id) as GeoJSONSource | undefined;
    if (!src) return false;
    src.setData(data);
    return true;
  }

  private register(id: string, overlay: Overlay): void {
    this.overlays.set(id, overlay);
    if (overlay.top) this.raiseTopOverlays();
  }

  setPolygons(
    id: string,
    features: GeoJSON.Feature<GeoJSON.Polygon>[],
    style: PolygonStyle,
    opts: OverlayOptions = {},
  ): void {
    if (this.disposed) return;
    const data: GeoJSON.FeatureCollection = { type: "FeatureCollection", features };
    if (this.setData(id, data)) return;
    this.map.addSource(id, { type: "geojson", data });
    this.map.addLayer({
      id: `${id}-fill`,
      type: "fill",
      source: id,
      paint: { "fill-color": style.fillColor, "fill-opacity": style.fillOpacity },
    });
    this.map.addLayer({
      id: `${id}-outline`,
      type: "line",
      source: id,
      paint: {
        "line-color": style.strokeColor,
        "line-width": style.strokeWidth,
        ...(style.dashed ? { "line-dasharray": [2, 2] } : {}),
      },
    });
    this.register(id, {
      layers: [
        { id: `${id}-fill`, kind: "fill" },
        { id: `${id}-outline`, kind: "line" },
      ],
      top: Boolean(opts.top),
    });
  }

  setLine(id: string, coordinates: LngLat[], style: LineStyle, opts: OverlayOptions = {}): void {
    if (this.disposed) return;
    const data: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features:
        coordinates.length > 1
          ? [{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates } }]
          : [],
    };
    if (this.setData(id, data)) return;
    this.map.addSource(id, { type: "geojson", data });
    this.map.addLayer({
      id: `${id}-line`,
      type: "line",
      source: id,
      layout: { "line-join": "round", "line-cap": "round" },
      paint: {
        "line-color": style.color,
        "line-width": style.width,
        "line-opacity": 1,
        ...(style.dashed ? { "line-dasharray": [1, 1] } : {}),
      },
    });
    this.register(id, { layers: [{ id: `${id}-line`, kind: "line" }], top: Boolean(opts.top) });
  }

  setPoints(
    id: string,
    features: GeoJSON.Feature<GeoJSON.Point>[],
    style: PointStyle,
    opts: PointOverlayOptions = {},
  ): void {
    if (this.disposed) return;
    const existing = this.overlays.get(id);
    if (existing) existing.onClick = opts.onClick;
    const data: GeoJSON.FeatureCollection = { type: "FeatureCollection", features };
    if (this.setData(id, data)) return;

    const { map } = this;
    map.addSource(id, {
      type: "geojson",
      data,
      ...(opts.cluster ? { cluster: true, clusterMaxZoom: opts.cluster.maxZoom, clusterRadius: opts.cluster.radius } : {}),
    });
    const layers: Overlay["layers"] = [];
    const pointsId = `${id}-points`;
    const clustersId = `${id}-clusters`;

    if (style.halo) {
      map.addLayer({
        id: `${id}-halo`,
        type: "circle",
        source: id,
        paint: { "circle-color": style.halo.color, "circle-radius": style.halo.radius, "circle-opacity": style.halo.opacity },
      });
      layers.push({ id: `${id}-halo`, kind: "point" });
    }
    if (opts.cluster) {
      map.addLayer({
        id: clustersId,
        type: "circle",
        source: id,
        filter: ["has", "point_count"],
        paint: {
          "circle-color": ["step", ["get", "point_count"], "#3b82f6", 10, "#f59e0b", 30, "#ef4444"],
          "circle-radius": ["step", ["get", "point_count"], 18, 10, 24, 30, 30],
          "circle-stroke-width": 2,
          "circle-stroke-color": "#ffffff",
        },
      });
      map.addLayer({
        id: `${id}-cluster-count`,
        type: "symbol",
        source: id,
        filter: ["has", "point_count"],
        layout: { "text-field": "{point_count_abbreviated}", "text-size": 12 },
        paint: { "text-color": "#ffffff" },
      });
      layers.push({ id: clustersId, kind: "point" }, { id: `${id}-cluster-count`, kind: "point" });
    }
    map.addLayer({
      id: pointsId,
      type: "circle",
      source: id,
      ...(opts.cluster ? { filter: ["!", ["has", "point_count"]] } : {}),
      paint: {
        "circle-color": colorExpression(style.color) as string,
        "circle-radius": style.radius,
        "circle-stroke-width": style.strokeWidth ?? 0,
        "circle-stroke-color": style.strokeColor ?? "#ffffff",
      },
    });
    layers.push({ id: pointsId, kind: "point" });

    const overlay: Overlay = { layers, top: Boolean(opts.top), onClick: opts.onClick };
    this.register(id, overlay);

    const pointer = () => (map.getCanvas().style.cursor = "pointer");
    const unpointer = () => (map.getCanvas().style.cursor = "");
    map.on("click", pointsId, (e: MapLayerMouseEvent) => {
      const props = e.features?.[0]?.properties;
      if (props && overlay.onClick) overlay.onClick(props as Record<string, unknown>);
    });
    map.on("mouseenter", pointsId, () => overlay.onClick && pointer());
    map.on("mouseleave", pointsId, unpointer);

    if (opts.cluster) {
      map.on("click", clustersId, (e: MapLayerMouseEvent) => {
        const feature = map.queryRenderedFeatures(e.point, { layers: [clustersId] })[0];
        const clusterId = feature?.properties?.cluster_id;
        const src = map.getSource(id) as GeoJSONSource | undefined;
        if (clusterId === undefined || !src) return;
        const center = (feature.geometry as GeoJSON.Point).coordinates as LngLat;
        // MapLibre 6 returns a promise (the callback form used before Batch 8 never fired).
        src
          .getClusterExpansionZoom(clusterId)
          .then((zoom) => !this.disposed && map.easeTo({ center, zoom }))
          .catch(() => undefined);
      });
      map.on("mouseenter", clustersId, pointer);
      map.on("mouseleave", clustersId, unpointer);
    }
  }

  removeOverlay(id: string): void {
    const overlay = this.overlays.get(id);
    this.overlays.delete(id);
    if (this.disposed || !overlay) return;
    try {
      for (const layer of [...overlay.layers].reverse()) {
        if (this.map.getLayer(layer.id)) this.map.removeLayer(layer.id);
      }
      if (this.map.getSource(id)) this.map.removeSource(id);
    } catch {
      // the style may be mid-switch; the map is rebuilt in that case anyway
    }
  }

  raiseTopOverlays(): void {
    if (this.disposed) return;
    const top = [...this.overlays.values()].filter((o) => o.top).flatMap((o) => o.layers);
    if (top.length === 0) return;
    const ids = (kind: Kind) => top.filter((l) => l.kind === kind).map((l) => l.id);
    const wanted = [...TD_FILL, ...ids("fill"), ...TD_LINE, ...ids("line"), ...TD_POINT, ...ids("point")];
    const style = this.map.getStyle();
    const order = style?.layers?.map((l) => l.id) ?? [];
    const present = wanted.filter((id) => order.includes(id));
    const tail = order.slice(-present.length);
    if (present.every((id, i) => tail[i] === id)) return;
    for (const id of present) {
      try {
        this.map.moveLayer(id);
      } catch {
        // ignore a layer removed mid-operation
      }
    }
  }

  async createDrawAdapter(): Promise<TerraDrawAdapter> {
    const { TerraDrawMapLibreGLAdapter } = await import("terra-draw-maplibre-gl-adapter");
    return new TerraDrawMapLibreGLAdapter({ map: this.map }) as unknown as TerraDrawAdapter;
  }

  placeSearch(): PlaceSearchService {
    return createMapLibrePlaceSearch();
  }
}
