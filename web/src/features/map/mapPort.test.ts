import { test } from "node:test";
import assert from "node:assert/strict";
import { chooseMapProvider } from "./provider.ts";
import { clusterStyle, gridCluster, lngLatToPixel } from "./gridCluster.ts";
import { colorFor } from "./port.ts";
import { createMapLibrePlaceSearch } from "./maplibre/placeSearch.ts";

// --- provider choice -------------------------------------------------------------------------

test("provider: maplibre by default and when asked", () => {
  assert.deepEqual(chooseMapProvider({}), { provider: "maplibre", fallbackReason: null });
  assert.equal(chooseMapProvider({ VITE_MAP_PROVIDER: "MapLibre" }).provider, "maplibre");
});

test("provider: google needs both values, else falls back with the missing names", () => {
  const r = chooseMapProvider({ VITE_MAP_PROVIDER: "google", VITE_GOOGLE_MAPS_API_KEY: "k" }, true);
  assert.equal(r.provider, "maplibre");
  assert.match(r.fallbackReason ?? "", /VITE_GOOGLE_MAPS_MAP_ID/);
  assert.doesNotMatch(r.fallbackReason ?? "", /VITE_GOOGLE_MAPS_API_KEY/);
  const none = chooseMapProvider({ VITE_MAP_PROVIDER: "google" }, true);
  assert.match(none.fallbackReason ?? "", /VITE_GOOGLE_MAPS_API_KEY and VITE_GOOGLE_MAPS_MAP_ID/);
});

test("provider: google with both values and the adapter present", () => {
  const env = { VITE_MAP_PROVIDER: "google", VITE_GOOGLE_MAPS_API_KEY: " k ", VITE_GOOGLE_MAPS_MAP_ID: "m" };
  assert.deepEqual(chooseMapProvider(env, true), {
    provider: "google",
    fallbackReason: null,
    google: { apiKey: "k", mapId: "m" },
  });
  const pending = chooseMapProvider(env, false);
  assert.equal(pending.provider, "maplibre");
  assert.match(pending.fallbackReason ?? "", /not in this build/);
});

test("provider: an unknown name falls back", () => {
  const r = chooseMapProvider({ VITE_MAP_PROVIDER: "bing" });
  assert.equal(r.provider, "maplibre");
  assert.match(r.fallbackReason ?? "", /Unknown/);
});

// --- grid clusterer --------------------------------------------------------------------------

test("lngLatToPixel: the world is 256 px wide at zoom 0, centred on 0,0", () => {
  assert.deepEqual(lngLatToPixel([0, 0], 0), [128, 128]);
  assert.equal(lngLatToPixel([180, 0], 1)[0], 512);
});

test("gridCluster groups nearby points and keeps far ones apart", () => {
  const pts = [
    { position: [55.27, 25.2] as [number, number], item: "a" },
    { position: [55.2701, 25.2001] as [number, number], item: "b" },
    { position: [46.7, 24.7] as [number, number], item: "riyadh" },
  ];
  const out = gridCluster(pts, 10, { radius: 40, maxZoom: 13 });
  const cluster = out.find((o) => o.kind === "cluster");
  assert.ok(cluster && cluster.kind === "cluster");
  assert.equal(cluster.count, 2);
  assert.deepEqual([...cluster.items].sort(), ["a", "b"]);
  assert.ok(cluster.expansionZoom > 10);
  assert.ok(out.some((o) => o.kind === "point" && o.item === "riyadh"));
});

test("gridCluster: nothing is clustered above maxZoom", () => {
  const pts = [
    { position: [55.27, 25.2] as [number, number], item: 1 },
    { position: [55.27, 25.2] as [number, number], item: 2 },
  ];
  const out = gridCluster(pts, 14, { radius: 40, maxZoom: 13 });
  assert.equal(out.length, 2);
  assert.ok(out.every((o) => o.kind === "point"));
});

test("clusterStyle uses the MapLibre steps", () => {
  assert.equal(clusterStyle(3).color, "#3b82f6");
  assert.equal(clusterStyle(10).radius, 24);
  assert.equal(clusterStyle(30).color, "#ef4444");
  assert.equal(clusterStyle(1500).label, "1.5k");
});

test("colorFor reads a property with a fallback", () => {
  const spec = { by: "live_state", values: { ACTIVE: "#10b981" }, fallback: "#64748b" };
  assert.equal(colorFor(spec, { live_state: "ACTIVE" }), "#10b981");
  assert.equal(colorFor(spec, { live_state: "OTHER" }), "#64748b");
  assert.equal(colorFor("#fff", null), "#fff");
});

// --- MapLibre fallback search ----------------------------------------------------------------

function fakeFetch(routes: Record<string, unknown>, calls: string[]): typeof fetch {
  return (async (url: string) => {
    calls.push(url);
    const host = Object.keys(routes).find((h) => url.includes(h));
    const body = host ? routes[host] : null;
    return { ok: body !== null, json: async () => body } as Response;
  }) as unknown as typeof fetch;
}

test("fallback search: MapTiler first when a key is set", async () => {
  const calls: string[] = [];
  const svc = createMapLibrePlaceSearch(
    "KEY",
    fakeFetch({ "api.maptiler.com": { features: [{ place_name: "Dubai Mall", center: [55.28, 25.19] }] } }, calls),
  );
  assert.equal(svc.mode, "submit");
  const found = await svc.suggest("dubai mall");
  assert.equal(found[0].label, "Dubai Mall");
  assert.deepEqual(await svc.resolve(found[0]), { center: [55.28, 25.19] });
  assert.equal(calls.length, 1);
});

test("fallback search: Nominatim without a key", async () => {
  const calls: string[] = [];
  const svc = createMapLibrePlaceSearch(
    undefined,
    fakeFetch({ "nominatim.openstreetmap.org": [{ display_name: "Riyadh", lon: "46.7", lat: "24.7", place_id: 9 }] }, calls),
  );
  const found = await svc.suggest("riyadh");
  assert.deepEqual(found, [{ id: "osm-9", label: "Riyadh", center: [46.7, 24.7] }]);
  assert.ok(calls[0].includes("nominatim"));
  assert.deepEqual(await svc.suggest("  "), []);
});
