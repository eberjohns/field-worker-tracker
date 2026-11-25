// Geometry at the web edge (Batch 8, ADR-033). Pure functions, no map library.
//
// The server keeps boundaries as PostGIS geometry and the API speaks GeoJSON Polygons. Here:
// WKT <-> GeoJSON (paste and "Copy WKT"), closing rings, ring orientation (RFC 7946: outer ring
// counter-clockwise, holes clockwise), rounding to 7 decimals (about 1 cm), and the instant
// checks the editor shows (too few points, self-crossing, invalid, swapped longitude/latitude).
// Coordinates are always [longitude, latitude].

import area from "@turf/area";
import booleanValid from "@turf/boolean-valid";
import kinks from "@turf/kinks";

export type Position = [number, number];
export type Ring = Position[];

export const DECIMALS = 7;

export function round7(n: number): number {
  const f = 10 ** DECIMALS;
  const r = Math.round(n * f) / f;
  return Object.is(r, -0) ? 0 : r;
}

/** Drops repeated consecutive points and closes the ring (first point repeated at the end). */
export function closeRing(ring: readonly (readonly number[])[]): Ring {
  const out: Ring = [];
  for (const p of ring) {
    const pt: Position = [p[0], p[1]];
    const prev = out[out.length - 1];
    if (!prev || prev[0] !== pt[0] || prev[1] !== pt[1]) out.push(pt);
  }
  if (out.length > 0) {
    const first = out[0];
    const last = out[out.length - 1];
    if (out.length === 1 || first[0] !== last[0] || first[1] !== last[1]) out.push([first[0], first[1]]);
  }
  return out;
}

/** Shoelace sum over a closed ring: > 0 counter-clockwise, < 0 clockwise (lng/lat plane). */
export function ringSignedArea(ring: Ring): number {
  let sum = 0;
  for (let i = 0; i < ring.length - 1; i++) {
    sum += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1];
  }
  return sum / 2;
}

function orient(ring: Ring, counterClockwise: boolean): Ring {
  const ccw = ringSignedArea(ring) > 0;
  return ccw === counterClockwise ? ring : [...ring].reverse();
}

/** Rounded to 7 decimals, rings closed, outer ring counter-clockwise and holes clockwise. */
export function normalizePolygon(poly: GeoJSON.Polygon): GeoJSON.Polygon {
  const rings = poly.coordinates.map((ring, i) => {
    const rounded = closeRing(ring.map((p) => [round7(p[0]), round7(p[1])]));
    return orient(rounded, i === 0);
  });
  return { type: "Polygon", coordinates: rings };
}

const fmt = (n: number) => String(round7(n));

/** `POLYGON((lng lat, ...), (hole...))`, rings closed. */
export function polygonToWkt(poly: GeoJSON.Polygon | GeoJSON.Feature<GeoJSON.Polygon> | null | undefined): string {
  const geom = poly && "geometry" in poly ? poly.geometry : poly;
  if (!geom || geom.type !== "Polygon" || !geom.coordinates?.[0]?.length) return "";
  const rings = geom.coordinates.map((r) => `(${closeRing(r).map((p) => `${fmt(p[0])} ${fmt(p[1])}`).join(", ")})`);
  return `POLYGON(${rings.join(", ")})`;
}

function parseRingText(text: string): Ring | null {
  const pts: Ring = [];
  for (const pair of text.split(",")) {
    const parts = pair.trim().split(/\s+/).map(Number);
    if (parts.length < 2 || !Number.isFinite(parts[0]) || !Number.isFinite(parts[1])) return null;
    pts.push([parts[0], parts[1]]);
  }
  return pts.length >= 3 ? closeRing(pts) : null;
}

/** POLYGON with holes, or a MULTIPOLYGON holding one polygon. Null for anything else. */
export function wktToPolygon(text: string): GeoJSON.Polygon | null {
  const t = text.trim().replace(/^SRID=\d+;/i, "");
  const m = t.match(/^(MULTI)?POLYGON\s*(Z|M|ZM)?\s*\(([\s\S]*)\)\s*$/i);
  if (!m) return null;
  let body = m[3].trim();
  if (m[1]) {
    // MULTIPOLYGON(((...)), ((...))): accept exactly one polygon.
    const polys = body.match(/\(\s*\([^()]*\)(\s*,\s*\([^()]*\))*\s*\)/g);
    if (!polys || polys.length !== 1) return null;
    body = polys[0].trim().slice(1, -1);
  }
  const ringTexts = body.match(/\(([^()]*)\)/g);
  if (!ringTexts || ringTexts.length === 0) return null;
  const rings: Ring[] = [];
  for (const rt of ringTexts) {
    const ring = parseRingText(rt.slice(1, -1));
    if (!ring) return null;
    rings.push(ring);
  }
  return { type: "Polygon", coordinates: rings };
}

/** What a user may paste: a GeoJSON Polygon or Feature, a coordinates array, or WKT. */
export function parsePolygonInput(text: string): GeoJSON.Polygon | null {
  const trimmed = text.trim();
  if (!trimmed) return null;
  if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
    try {
      const parsed = JSON.parse(trimmed);
      if (parsed?.type === "Polygon" && Array.isArray(parsed.coordinates)) {
        return { type: "Polygon", coordinates: parsed.coordinates.map((r: Ring) => closeRing(r)) };
      }
      if (parsed?.type === "Feature" && parsed.geometry?.type === "Polygon") {
        return { type: "Polygon", coordinates: parsed.geometry.coordinates.map((r: Ring) => closeRing(r)) };
      }
      if (Array.isArray(parsed) && Array.isArray(parsed[0])) {
        if (Array.isArray(parsed[0][0])) return { type: "Polygon", coordinates: (parsed as Ring[]).map(closeRing) };
        if (typeof parsed[0][0] === "number") return { type: "Polygon", coordinates: [closeRing(parsed as Ring)] };
      }
    } catch {
      // not JSON: try WKT
    }
    return null;
  }
  return wktToPolygon(trimmed);
}

export type BBox = [number, number, number, number]; // minLng, minLat, maxLng, maxLat

export function bboxOf(geom: GeoJSON.Polygon | GeoJSON.LineString | GeoJSON.Point | Position[]): BBox | null {
  const pts: number[][] = Array.isArray(geom)
    ? geom
    : geom.type === "Polygon"
      ? geom.coordinates.flat()
      : geom.type === "LineString"
        ? geom.coordinates
        : [geom.coordinates];
  if (pts.length === 0) return null;
  const b: BBox = [Infinity, Infinity, -Infinity, -Infinity];
  for (const p of pts) {
    b[0] = Math.min(b[0], p[0]);
    b[1] = Math.min(b[1], p[1]);
    b[2] = Math.max(b[2], p[0]);
    b[3] = Math.max(b[3], p[1]);
  }
  return b;
}

/** Rough country boxes for the swapped-axis check (ADR-009: one deployment per country). */
export const COUNTRY_BOUNDS: Record<string, BBox> = {
  AE: [51.0, 22.4, 56.6, 26.4],
  SA: [34.4, 16.2, 55.8, 32.3],
};

const inside = (p: number[], b: BBox) => p[0] >= b[0] && p[0] <= b[2] && p[1] >= b[1] && p[1] <= b[3];

/** True when the polygon lies outside the country but would lie inside it with each pair swapped. */
export function looksSwapped(poly: GeoJSON.Polygon, country: string): boolean {
  const b = COUNTRY_BOUNDS[country];
  const pts = poly.coordinates.flat();
  if (!b || pts.length === 0) return false;
  return !pts.every((p) => inside(p, b)) && pts.every((p) => inside([p[1], p[0]], b));
}

export type PolygonCheck =
  | { ok: true; areaSqM: number }
  | { ok: false; code: "TOO_FEW_POINTS" | "OUT_OF_RANGE" | "SWAPPED_AXES" | "SELF_INTERSECTION" | "INVALID"; message: string; areaSqM: number };

/** The editor's instant checks; the server (PostGIS) still decides. */
export function checkPolygon(poly: GeoJSON.Polygon, country?: string): PolygonCheck {
  const ring = poly.coordinates?.[0];
  if (!ring || closeRing(ring).length < 4) {
    return { ok: false, code: "TOO_FEW_POINTS", message: "Polygon ring must have at least 4 positions.", areaSqM: 0 };
  }
  if (poly.coordinates.flat().some((p) => Math.abs(p[0]) > 180 || Math.abs(p[1]) > 90)) {
    return { ok: false, code: "OUT_OF_RANGE", message: "A point is outside longitude ±180 / latitude ±90.", areaSqM: 0 };
  }
  if (country && looksSwapped(poly, country)) {
    return {
      ok: false,
      code: "SWAPPED_AXES",
      message: "Longitude and latitude look swapped (expected [longitude, latitude]).",
      areaSqM: 0,
    };
  }
  const sqM = area(poly);
  if (kinks(poly).features.length > 0) {
    return { ok: false, code: "SELF_INTERSECTION", message: "Self-intersecting polygon (lines cross).", areaSqM: sqM };
  }
  if (!booleanValid(poly)) {
    return { ok: false, code: "INVALID", message: "Invalid polygon ring structure.", areaSqM: sqM };
  }
  return { ok: true, areaSqM: sqM };
}
