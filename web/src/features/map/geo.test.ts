import { test } from "node:test";
import assert from "node:assert/strict";
import {
  bboxOf,
  checkPolygon,
  closeRing,
  looksSwapped,
  normalizePolygon,
  parsePolygonInput,
  polygonToWkt,
  ringSignedArea,
  round7,
  wktToPolygon,
} from "./geo.ts";

// A small square near Dubai Marina, counter-clockwise, closed.
const SQUARE: GeoJSON.Polygon = {
  type: "Polygon",
  coordinates: [
    [
      [55.14, 25.08],
      [55.15, 25.08],
      [55.15, 25.09],
      [55.14, 25.09],
      [55.14, 25.08],
    ],
  ],
};

const WITH_HOLE: GeoJSON.Polygon = {
  type: "Polygon",
  coordinates: [
    SQUARE.coordinates[0],
    [
      [55.142, 25.082],
      [55.142, 25.084],
      [55.144, 25.084],
      [55.144, 25.082],
      [55.142, 25.082],
    ],
  ],
};

test("round7 keeps 7 decimals and never returns -0", () => {
  assert.equal(round7(55.123456789), 55.1234568);
  assert.equal(round7(-0.00000001), 0);
  assert.ok(!Object.is(round7(-0.00000001), -0));
});

test("closeRing closes an open ring and drops repeated points", () => {
  const ring = closeRing([
    [1, 1],
    [2, 1],
    [2, 1],
    [2, 2],
  ]);
  assert.deepEqual(ring, [
    [1, 1],
    [2, 1],
    [2, 2],
    [1, 1],
  ]);
  assert.deepEqual(closeRing(SQUARE.coordinates[0]), SQUARE.coordinates[0]);
});

test("WKT round trip keeps the polygon, holes included", () => {
  for (const poly of [SQUARE, WITH_HOLE]) {
    const wkt = polygonToWkt(poly);
    assert.deepEqual(wktToPolygon(wkt), poly);
  }
  assert.equal(
    polygonToWkt(SQUARE),
    "POLYGON((55.14 25.08, 55.15 25.08, 55.15 25.09, 55.14 25.09, 55.14 25.08))",
  );
});

test("WKT parsing accepts SRID, Z, an open ring and a one-polygon MULTIPOLYGON", () => {
  assert.deepEqual(
    wktToPolygon("SRID=4326;POLYGON((55.14 25.08, 55.15 25.08, 55.15 25.09, 55.14 25.09, 55.14 25.08))"),
    SQUARE,
  );
  assert.deepEqual(wktToPolygon("polygon z ((55.14 25.08 0, 55.15 25.08 0, 55.15 25.09 0, 55.14 25.09 0))"), SQUARE);
  assert.deepEqual(
    wktToPolygon("MULTIPOLYGON(((55.14 25.08, 55.15 25.08, 55.15 25.09, 55.14 25.09, 55.14 25.08)))"),
    SQUARE,
  );
});

test("WKT parsing rejects other shapes and bad numbers", () => {
  assert.equal(wktToPolygon("POINT(55 25)"), null);
  assert.equal(wktToPolygon("POLYGON((55 25, 56 25))"), null);
  assert.equal(wktToPolygon("POLYGON((55 25, x 25, 56 26))"), null);
  assert.equal(wktToPolygon("MULTIPOLYGON(((0 0, 1 0, 1 1, 0 0)), ((2 2, 3 2, 3 3, 2 2)))"), null);
  assert.equal(polygonToWkt(null), "");
});

test("parsePolygonInput takes GeoJSON, a Feature, coordinate arrays and WKT", () => {
  assert.deepEqual(parsePolygonInput(JSON.stringify(SQUARE)), SQUARE);
  assert.deepEqual(parsePolygonInput(JSON.stringify({ type: "Feature", properties: {}, geometry: SQUARE })), SQUARE);
  assert.deepEqual(parsePolygonInput(JSON.stringify(SQUARE.coordinates)), SQUARE);
  assert.deepEqual(parsePolygonInput(JSON.stringify(SQUARE.coordinates[0].slice(0, 4))), SQUARE);
  assert.deepEqual(parsePolygonInput(polygonToWkt(SQUARE)), SQUARE);
  assert.equal(parsePolygonInput("{not json"), null);
  assert.equal(parsePolygonInput("   "), null);
});

test("normalizePolygon makes the outer ring counter-clockwise and holes clockwise", () => {
  const clockwise: GeoJSON.Polygon = {
    type: "Polygon",
    coordinates: [[...SQUARE.coordinates[0]].reverse(), [...WITH_HOLE.coordinates[1]].reverse()],
  };
  const n = normalizePolygon(clockwise);
  assert.ok(ringSignedArea(n.coordinates[0] as [number, number][]) > 0);
  assert.ok(ringSignedArea(n.coordinates[1] as [number, number][]) < 0);
  const rounded = normalizePolygon({
    type: "Polygon",
    coordinates: [SQUARE.coordinates[0].map((p) => [p[0] + 1e-9, p[1] - 1e-9])],
  });
  assert.deepEqual(rounded, SQUARE);
});

test("checkPolygon: valid square, area about 1.1 km x 1.0 km", () => {
  const r = checkPolygon(SQUARE, "AE");
  assert.equal(r.ok, true);
  assert.ok(r.areaSqM > 1_000_000 && r.areaSqM < 1_200_000, String(r.areaSqM));
});

test("checkPolygon flags self-crossing, too few points, out of range and swapped axes", () => {
  const bowtie: GeoJSON.Polygon = {
    type: "Polygon",
    coordinates: [
      [
        [55.14, 25.08],
        [55.15, 25.09],
        [55.15, 25.08],
        [55.14, 25.09],
        [55.14, 25.08],
      ],
    ],
  };
  const r1 = checkPolygon(bowtie);
  assert.equal(r1.ok, false);
  assert.equal(!r1.ok && r1.code, "SELF_INTERSECTION");

  const r2 = checkPolygon({ type: "Polygon", coordinates: [[[55, 25], [56, 25], [55, 25]]] });
  assert.equal(!r2.ok && r2.code, "TOO_FEW_POINTS");

  const r3 = checkPolygon({ type: "Polygon", coordinates: [[[200, 25], [201, 25], [201, 26], [200, 25]]] });
  assert.equal(!r3.ok && r3.code, "OUT_OF_RANGE");

  const swapped: GeoJSON.Polygon = {
    type: "Polygon",
    coordinates: [SQUARE.coordinates[0].map((p) => [p[1], p[0]])],
  };
  assert.equal(looksSwapped(swapped, "AE"), true);
  assert.equal(looksSwapped(SQUARE, "AE"), false);
  const r4 = checkPolygon(swapped, "AE");
  assert.equal(!r4.ok && r4.code, "SWAPPED_AXES");
  // Without a country the check is skipped.
  assert.equal(checkPolygon(swapped).ok, true);
});

test("bboxOf covers polygons, lines and points", () => {
  assert.deepEqual(bboxOf(SQUARE), [55.14, 25.08, 55.15, 25.09]);
  assert.deepEqual(bboxOf({ type: "Point", coordinates: [55, 25] }), [55, 25, 55, 25]);
  assert.equal(bboxOf([]), null);
});
