// A small screen-grid clusterer for providers without built-in clustering (Google, ADR-033).
// MapLibre clusters in its own GeoJSON source and doesn't use this.
//
// Points are projected to Web Mercator pixels at the current zoom and grouped by grid cell of
// `radius` pixels. Above `maxZoom` nothing is clustered. Pure: no map library.

import type { LngLat } from "./port";

export interface ClusterInput<T> {
  position: LngLat;
  item: T;
}

export type ClusterOutput<T> =
  | { kind: "point"; position: LngLat; item: T }
  | { kind: "cluster"; position: LngLat; count: number; items: T[]; expansionZoom: number };

const TILE = 256;

export function lngLatToPixel([lng, lat]: LngLat, zoom: number): [number, number] {
  const scale = TILE * 2 ** zoom;
  const x = ((lng + 180) / 360) * scale;
  const s = Math.sin((Math.max(-85.05112878, Math.min(85.05112878, lat)) * Math.PI) / 180);
  const y = (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * scale;
  return [x, y];
}

export function gridCluster<T>(
  points: ClusterInput<T>[],
  zoom: number,
  opts: { radius: number; maxZoom: number },
): ClusterOutput<T>[] {
  const z = Math.floor(zoom);
  if (z > opts.maxZoom) return points.map((p) => ({ kind: "point", position: p.position, item: p.item }));

  const cells = new Map<string, ClusterInput<T>[]>();
  for (const p of points) {
    const [x, y] = lngLatToPixel(p.position, z);
    const key = `${Math.floor(x / opts.radius)}:${Math.floor(y / opts.radius)}`;
    const cell = cells.get(key);
    if (cell) cell.push(p);
    else cells.set(key, [p]);
  }

  const out: ClusterOutput<T>[] = [];
  for (const cell of cells.values()) {
    if (cell.length === 1) {
      out.push({ kind: "point", position: cell[0].position, item: cell[0].item });
      continue;
    }
    const lng = cell.reduce((s, p) => s + p.position[0], 0) / cell.length;
    const lat = cell.reduce((s, p) => s + p.position[1], 0) / cell.length;
    out.push({
      kind: "cluster",
      position: [lng, lat],
      count: cell.length,
      items: cell.map((p) => p.item),
      expansionZoom: Math.min(z + 2, opts.maxZoom + 1),
    });
  }
  return out;
}

/** The same steps as the MapLibre cluster layer: blue under 10, amber under 30, red above. */
export function clusterStyle(count: number): { color: string; radius: number; label: string } {
  const label = count >= 1000 ? `${Math.round(count / 100) / 10}k` : String(count);
  if (count >= 30) return { color: "#ef4444", radius: 30, label };
  if (count >= 10) return { color: "#f59e0b", radius: 24, label };
  return { color: "#3b82f6", radius: 18, label };
}
