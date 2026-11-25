// The MapLibre adapter against a fake map: the layers it adds, updates through setData,
// click handling, cluster zoom (MapLibre 6 promise API) and keeping `top` overlays above
// Terra Draw's layers.
import { test } from "node:test";
import assert from "node:assert/strict";
import { MapLibreAdapter } from "./MapLibreAdapter.ts";

type Handler = (e?: any) => void;

class FakeMap {
  sources = new Map<string, { data: any; setData: (d: any) => void; getClusterExpansionZoom: (id: number) => Promise<number>; opts: any }>();
  layers: { id: string; type: string; filter?: unknown; paint?: any }[] = [];
  handlers: { event: string; layer?: string; fn: Handler }[] = [];
  eased: any[] = [];
  canvas = { style: { cursor: "" } };

  addSource(id: string, opts: any) {
    const src = {
      data: opts.data,
      opts,
      setData(d: any) {
        src.data = d;
      },
      getClusterExpansionZoom: async () => 15,
    };
    this.sources.set(id, src);
  }
  getSource(id: string) {
    return this.sources.get(id);
  }
  removeSource(id: string) {
    this.sources.delete(id);
  }
  addLayer(layer: any) {
    this.layers.push(layer);
  }
  getLayer(id: string) {
    return this.layers.find((l) => l.id === id);
  }
  removeLayer(id: string) {
    this.layers = this.layers.filter((l) => l.id !== id);
  }
  moveLayer(id: string) {
    const l = this.getLayer(id)!;
    this.removeLayer(id);
    this.layers.push(l);
  }
  getStyle() {
    return { layers: this.layers };
  }
  isStyleLoaded() {
    return true;
  }
  on(event: string, a: any, b?: any) {
    if (typeof a === "function") this.handlers.push({ event, fn: a });
    else this.handlers.push({ event, layer: a, fn: b });
  }
  off(event: string, fn: Handler) {
    this.handlers = this.handlers.filter((h) => !(h.event === event && h.fn === fn));
  }
  fire(event: string, layer: string | undefined, e?: any) {
    for (const h of this.handlers) if (h.event === event && h.layer === layer) h.fn(e);
  }
  queryRenderedFeatures() {
    return [{ properties: { cluster_id: 7 }, geometry: { type: "Point", coordinates: [55, 25] } }];
  }
  easeTo(opts: any) {
    this.eased.push(opts);
  }
  flyTo(opts: any) {
    this.eased.push({ fly: opts });
  }
  fitBounds(b: any, o: any) {
    this.eased.push({ fit: b, o });
  }
  getCanvas() {
    return this.canvas;
  }
}

const square: GeoJSON.Feature<GeoJSON.Polygon> = {
  type: "Feature",
  properties: {},
  geometry: { type: "Polygon", coordinates: [[[55, 25], [56, 25], [56, 26], [55, 25]]] },
};
const pt = (id: string): GeoJSON.Feature<GeoJSON.Point> => ({
  type: "Feature",
  properties: { employee_id: id, live_state: "ACTIVE" },
  geometry: { type: "Point", coordinates: [55, 25] },
});

function make() {
  const map = new FakeMap();
  return { map, port: new MapLibreAdapter(map as any) };
}

test("setPolygons adds fill and outline once, then only updates the data", () => {
  const { map, port } = make();
  const style = { fillColor: "#a855f7", fillOpacity: 0.15, strokeColor: "#9333ea", strokeWidth: 2, dashed: true };
  port.setPolygons("acc", [square], style);
  assert.deepEqual(map.layers.map((l) => l.id), ["acc-fill", "acc-outline"]);
  assert.deepEqual(map.getLayer("acc-outline")!.paint["line-dasharray"], [2, 2]);
  port.setPolygons("acc", [], style);
  assert.equal(map.layers.length, 2);
  assert.deepEqual(map.sources.get("acc")!.data.features, []);
});

test("setPoints: clustering, colour by property, click gives the properties", () => {
  const { map, port } = make();
  const clicked: unknown[] = [];
  port.setPoints(
    "workers",
    [pt("e1")],
    { color: { by: "live_state", values: { ACTIVE: "#10b981" }, fallback: "#64748b" }, radius: 8 },
    { cluster: { maxZoom: 13, radius: 40 }, onClick: (p) => clicked.push(p.employee_id) },
  );
  assert.equal(map.sources.get("workers")!.opts.cluster, true);
  assert.equal(map.sources.get("workers")!.opts.clusterMaxZoom, 13);
  assert.deepEqual(map.layers.map((l) => l.id), ["workers-clusters", "workers-cluster-count", "workers-points"]);
  assert.deepEqual(map.getLayer("workers-points")!.paint["circle-color"], [
    "match",
    ["get", "live_state"],
    "ACTIVE",
    "#10b981",
    "#64748b",
  ]);
  map.fire("click", "workers-points", { features: [{ properties: { employee_id: "e1" } }] });
  assert.deepEqual(clicked, ["e1"]);
});

test("clicking a cluster zooms to its expansion zoom (promise API)", async () => {
  const { map, port } = make();
  port.setPoints("workers", [pt("e1")], { color: "#000", radius: 8 }, { cluster: { maxZoom: 13, radius: 40 } });
  map.fire("click", "workers-clusters", { point: { x: 1, y: 1 } });
  await new Promise((r) => setTimeout(r, 0));
  assert.deepEqual(map.eased, [{ center: [55, 25], zoom: 15 }]);
});

test("top overlays sit above Terra Draw's layers, fills under lines under points", () => {
  const { map, port } = make();
  for (const id of ["td-polygon", "td-polygon-outline", "td-linestring", "td-point", "td-point-marker"]) {
    map.addLayer({ id, type: "x" });
  }
  port.setPolygons("pf", [square], { fillColor: "#000", fillOpacity: 1, strokeColor: "#000", strokeWidth: 0 }, { top: true });
  port.setLine("pl", [[55, 25], [56, 26]], { color: "#000", width: 4 }, { top: true });
  port.setPoints("pp", [pt("x")], { color: "#000", radius: 7 }, { top: true });
  map.addLayer({ id: "late-tiles", type: "raster" });
  map.fire("idle", undefined);
  assert.deepEqual(map.layers.map((l) => l.id), [
    "late-tiles",
    "td-polygon",
    "pf-fill",
    "td-polygon-outline",
    "td-linestring",
    "pf-outline",
    "pl-line",
    "td-point",
    "td-point-marker",
    "pp-points",
  ]);
});

test("removeOverlay removes layers and source; nothing happens after dispose", () => {
  const { map, port } = make();
  port.setLine("trail", [[55, 25], [56, 26]], { color: "#000", width: 3, dashed: true });
  assert.deepEqual(map.getLayer("trail-line")!.paint["line-dasharray"], [1, 1]);
  port.removeOverlay("trail");
  assert.equal(map.layers.length, 0);
  assert.equal(map.sources.size, 0);
  port.dispose();
  port.setLine("trail", [[55, 25], [56, 26]], { color: "#000", width: 3 });
  port.easeTo([55, 25], { zoom: 16 });
  assert.equal(map.layers.length, 0);
  assert.deepEqual(map.eased, []);
  assert.equal(map.handlers.filter((h) => h.event === "idle").length, 0);
});

test("easeTo, flyTo and fitBounds translate to MapLibre options", () => {
  const { map, port } = make();
  port.easeTo([55, 25], { zoom: 16, durationMs: 250 });
  port.flyTo([46, 24], 16);
  port.fitBounds([55, 25, 56, 26]);
  assert.deepEqual(map.eased, [
    { center: [55, 25], zoom: 16, duration: 250 },
    { fly: { center: [46, 24], zoom: 16, essential: true } },
    { fit: [[55, 25], [56, 26]], o: { padding: 80, maxZoom: 18 } },
  ]);
});
