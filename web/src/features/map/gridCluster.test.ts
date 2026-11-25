import { test } from "node:test";
import assert from "node:assert/strict";
import { clusterStyle, gridCluster, lngLatToPixel } from "./gridCluster.ts";
import { colorFor } from "./port.ts";

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

test("clusterStyle: blue under 10, amber under 30, red above", () => {
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
