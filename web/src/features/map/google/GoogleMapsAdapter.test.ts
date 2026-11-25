// The Google Maps adapter, map pool, loader helpers and search against a mocked `google.maps`
// (ADR-033): shapes and markers update in place, clusters split on zoom and zoom in on click,
// search counts one geocode per press and maps quota errors, the pool reuses one map.
import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";

// --- a tiny DOM and google.maps global for node -----------------------------------------------

class FakeEl {
  style: Record<string, string> = {};
  dataset: Record<string, string> = {};
  textContent = "";
  children: FakeEl[] = [];
  parent: FakeEl | null = null;
  appendChild(c: FakeEl) {
    c.parent = this;
    this.children.push(c);
  }
  remove() {
    if (this.parent) this.parent.children = this.parent.children.filter((c) => c !== this);
    this.parent = null;
  }
}
(globalThis as any).document = { createElement: () => new FakeEl() };
const onceListeners: { target: unknown; event: string; fn: () => void }[] = [];
(globalThis as any).google = {
  maps: {
    event: {
      addListenerOnce: (target: unknown, event: string, fn: () => void) => onceListeners.push({ target, event, fn }),
    },
  },
};

const { GoogleMapsAdapter, SearchUnavailableError, createGeocodeSearch } = await import("./GoogleMapsAdapter.ts");
const { acquireMap, releaseMap, resetMapPool, mapsCreated } = await import("./mapPool.ts");
const { readGoogleConfig, reportUsage } = await import("./loader.ts");

class FakeMap {
  zoom = 10;
  center: any = null;
  options: any;
  listeners: { event: string; fn: () => void; removed: boolean }[] = [];
  fitted: any[] = [];
  constructor(_div?: unknown, options: any = {}) {
    this.options = options;
    if (options.zoom !== undefined) this.zoom = options.zoom;
  }
  getZoom() {
    return this.zoom;
  }
  setZoom(z: number) {
    this.zoom = z;
  }
  panTo(c: any) {
    this.center = c;
  }
  setCenter(c: any) {
    this.center = c;
  }
  setOptions(o: any) {
    this.options = { ...this.options, ...o };
  }
  fitBounds(b: any, p: any) {
    this.fitted.push({ b, p });
  }
  addListener(event: string, fn: () => void) {
    const l = { event, fn, removed: false };
    this.listeners.push(l);
    return { remove: () => (l.removed = true) };
  }
  fire(event: string) {
    for (const l of this.listeners) if (l.event === event && !l.removed) l.fn();
  }
}

class Shape {
  static made = 0;
  options: any;
  map: unknown;
  constructor(o: any) {
    Shape.made += 1;
    this.options = o;
    this.map = o.map;
  }
  setOptions(o: any) {
    this.options = o;
    this.map = o.map;
  }
  setMap(m: unknown) {
    this.map = m;
  }
}

class Marker {
  static all: Marker[] = [];
  map: unknown;
  position: any;
  content: any;
  gmpClickable: boolean;
  handlers: Record<string, () => void> = {};
  constructor(o: any) {
    this.map = o.map;
    this.position = o.position;
    this.content = o.content;
    this.gmpClickable = o.gmpClickable;
    Marker.all.push(this);
  }
  addListener(e: string, fn: () => void) {
    this.handlers[e] = fn;
  }
}

class Bounds {
  constructor(
    readonly sw: any,
    readonly ne: any,
  ) {}
}

let geocodeImpl: (req: any) => Promise<any> = async () => ({ results: [] });
class Geocoder {
  geocode(req: any) {
    return geocodeImpl(req);
  }
}

const libs = {
  maps: { Polygon: Shape, Polyline: Shape },
  marker: { AdvancedMarkerElement: Marker },
  geocoding: { Geocoder },
  core: { LatLngBounds: Bounds },
} as any;

function make() {
  const map = new FakeMap();
  return { map, port: new GoogleMapsAdapter(libs, map as any) };
}

const square: GeoJSON.Feature<GeoJSON.Polygon> = {
  type: "Feature",
  properties: {},
  geometry: { type: "Polygon", coordinates: [[[55, 25], [56, 25], [56, 26], [55, 25]]] },
};
const worker = (id: string, lng = 55.27, lat = 25.2): GeoJSON.Feature<GeoJSON.Point> => ({
  type: "Feature",
  id,
  properties: { employee_id: id, live_state: "ACTIVE" },
  geometry: { type: "Point", coordinates: [lng, lat] },
});
const live = (m: Marker) => m.map !== null;

beforeEach(() => {
  Marker.all = [];
  Shape.made = 0;
  onceListeners.length = 0;
});

// --- overlays ---------------------------------------------------------------------------------

test("setPolygons creates shapes once and reshapes them in place", () => {
  const { map, port } = make();
  const style = { fillColor: "#3b82f6", fillOpacity: 0.15, strokeColor: "#2563eb", strokeWidth: 2 };
  port.setPolygons("sites", [square, square], style);
  assert.equal(Shape.made, 2);
  port.setPolygons("sites", [square], style);
  assert.equal(Shape.made, 2, "no new shape on update");
  port.removeOverlay("sites");
  assert.equal(map.listeners.length, 0);
});

test("dashed polygons draw a dashed outline polyline, not a stroke", () => {
  const { port } = make();
  port.setPolygons("acc", [square], { fillColor: "#a855f7", fillOpacity: 0.15, strokeColor: "#9333ea", strokeWidth: 2, dashed: true });
  assert.equal(Shape.made, 2); // polygon + outline
});

test("worker markers are moved, not replaced, when positions refresh", () => {
  const { port } = make();
  const style = { color: { by: "live_state", values: { ACTIVE: "#10b981" }, fallback: "#64748b" }, radius: 8 };
  port.setPoints("workers", [worker("a", 55.0, 25.0), worker("b", 56.0, 26.0)], style);
  assert.equal(Marker.all.length, 2);
  const first = Marker.all[0];
  assert.equal(first.content.dataset.color, "#10b981");
  port.setPoints("workers", [worker("a", 55.1, 25.1)], style);
  assert.equal(Marker.all.length, 2, "no new marker");
  assert.deepEqual(first.position, { lat: 25.1, lng: 55.1 });
  assert.equal(live(Marker.all[1]), false, "b was removed");
});

test("clusters below maxZoom, splits after zooming in, and a cluster click zooms in", () => {
  const { map, port } = make();
  map.zoom = 10;
  const clicked: unknown[] = [];
  port.setPoints("workers", [worker("a"), worker("b", 55.2701, 25.2001)], { color: "#000", radius: 8 }, {
    cluster: { maxZoom: 13, radius: 40 },
    onClick: (p) => clicked.push(p.employee_id),
  });
  const clusters = Marker.all.filter(live);
  assert.equal(clusters.length, 1);
  assert.equal(clusters[0].content.textContent, "2");
  clusters[0].handlers.click();
  assert.ok(map.zoom > 10);

  map.zoom = 15;
  map.fire("idle");
  const points = Marker.all.filter(live);
  assert.equal(points.length, 2);
  points[0].handlers.click();
  assert.equal(clicked.length, 1);
});

test("dispose removes every marker and listener", () => {
  const { map, port } = make();
  port.setPoints("workers", [worker("a")], { color: "#000", radius: 8 }, { cluster: { maxZoom: 13, radius: 40 } });
  port.setLine("trail", [[55, 25], [56, 26]], { color: "#3b82f6", width: 3, dashed: true });
  port.dispose();
  assert.ok(Marker.all.every((m) => !live(m)));
  assert.ok(map.listeners.every((l) => l.removed));
  port.setLine("trail", [[55, 25], [56, 26]], { color: "#000", width: 3 });
  port.easeTo([1, 2], { zoom: 4 });
  assert.equal(map.zoom, 10, "nothing happens after dispose");
});

test("fitBounds pads, then caps the zoom when the map is idle", () => {
  const { map, port } = make();
  port.fitBounds([55, 25, 55.001, 25.001], { padding: 40, maxZoom: 17 });
  assert.equal(map.fitted[0].p, 40);
  map.zoom = 21;
  onceListeners[0].fn();
  assert.equal(map.zoom, 17);
});

// --- search -----------------------------------------------------------------------------------

test("search: one geocode per press, biased to UAE/KSA, results mapped", async () => {
  let counted = 0;
  let request: any = null;
  geocodeImpl = async (req) => {
    request = req;
    return {
      results: [
        {
          place_id: "pid-1",
          formatted_address: "Dubai Mall",
          geometry: {
            location: { lng: () => 55.28, lat: () => 25.19 },
            viewport: {
              getSouthWest: () => ({ lng: () => 55.27, lat: () => 25.18 }),
              getNorthEast: () => ({ lng: () => 55.29, lat: () => 25.2 }),
            },
          },
        },
      ],
    };
  };
  const svc = createGeocodeSearch(libs.geocoding, () => counted++);
  const found = await svc.search(" dubai mall ");
  assert.equal(counted, 1);
  assert.equal(request.address, "dubai mall");
  assert.ok(request.bounds.east > 55 && request.bounds.west < 40);
  assert.deepEqual(found, [{ id: "pid-1", label: "Dubai Mall", center: [55.28, 25.19], bbox: [55.27, 25.18, 55.29, 25.2] }]);
  assert.deepEqual(await svc.search("a"), []);
  assert.equal(counted, 1, "too-short queries send nothing");
});

test("search: no results is empty, quota errors say unavailable", async () => {
  const svc = createGeocodeSearch(libs.geocoding, () => undefined);
  geocodeImpl = async () => {
    throw Object.assign(new Error("x"), { code: "ZERO_RESULTS" });
  };
  assert.deepEqual(await svc.search("nowhere"), []);
  geocodeImpl = async () => {
    throw Object.assign(new Error("x"), { code: "OVER_QUERY_LIMIT" });
  };
  await assert.rejects(svc.search("dubai"), SearchUnavailableError);
});

// --- pool and loader --------------------------------------------------------------------------

test("map pool: one map created, then reused on road map with the new view", () => {
  resetMapPool();
  let loads = 0;
  const container1 = new FakeEl() as any;
  const view = { center: { lat: 25, lng: 55 }, zoom: 14, gestureHandling: "greedy" as const };
  const a = acquireMap({ Map: FakeMap } as any, container1, "MAPID", view, () => loads++);
  assert.equal(loads, 1);
  assert.equal((a.map as any).options.mapTypeId, "roadmap");
  assert.deepEqual((a.map as any).options.mapTypeControlOptions.mapTypeIds, ["roadmap", "satellite", "hybrid"]);
  (a.map as any).setOptions({ mapTypeId: "satellite" });
  releaseMap(a);
  const container2 = new FakeEl() as any;
  const b = acquireMap({ Map: FakeMap } as any, container2, "MAPID", { ...view, zoom: 17, gestureHandling: "cooperative" }, () => loads++);
  assert.equal(b, a);
  assert.equal(loads, 1, "no second map load");
  assert.equal(mapsCreated(), 1);
  assert.equal((b.map as any).zoom, 17);
  assert.equal((b.map as any).options.mapTypeId, "roadmap");
  assert.equal((b.map as any).options.gestureHandling, "cooperative");
  assert.equal(container2.children[0], b.div);
});

test("readGoogleConfig needs both values", () => {
  assert.equal(readGoogleConfig({}), null);
  assert.equal(readGoogleConfig({ VITE_GOOGLE_MAPS_API_KEY: "k" }), null);
  assert.deepEqual(readGoogleConfig({ VITE_GOOGLE_MAPS_API_KEY: " k ", VITE_GOOGLE_MAPS_MAP_ID: "m" }), { apiKey: "k", mapId: "m" });
});

test("reportUsage posts the kind with the token, and skips without one", () => {
  const calls: any[] = [];
  const store: Record<string, string> = {};
  (globalThis as any).localStorage = { getItem: (k: string) => store[k] ?? null };
  const fake = ((url: string, init: any) => {
    calls.push({ url, init });
    return Promise.resolve({ ok: true });
  }) as any;
  reportUsage("MAP_LOAD", fake);
  assert.equal(calls.length, 0);
  store.fwt_token = "T";
  reportUsage("GEOCODE", fake);
  assert.equal(calls[0].url, "/api/v1/map-usage");
  assert.equal(calls[0].init.method, "POST");
  assert.equal(calls[0].init.headers.Authorization, "Bearer T");
  assert.deepEqual(JSON.parse(calls[0].init.body), { kind: "GEOCODE" });
});
