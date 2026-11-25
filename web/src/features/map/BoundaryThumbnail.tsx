// A boundary drawn as a small SVG for lists and previews (owner, 25 Nov: no map load there; the
// real map opens only on the Boundary tab or "Show on map"). No map library, no network.

import React from "react";

/**
 * SVG path data for the polygon fitted into a `size` x `size` box with `pad` pixels of margin.
 * Longitude is scaled by cos(latitude) so shapes keep their proportions. Null without a ring.
 */
export function thumbnailPath(polygon: GeoJSON.Polygon | null | undefined, size = 40, pad = 3): string | null {
  const rings = polygon?.coordinates?.filter((r) => r.length >= 3) ?? [];
  if (rings.length === 0) return null;
  const pts = rings.flat();
  const midLat = (Math.min(...pts.map((p) => p[1])) + Math.max(...pts.map((p) => p[1]))) / 2;
  const k = Math.cos((midLat * Math.PI) / 180);
  const xs = pts.map((p) => p[0] * k);
  const ys = pts.map((p) => p[1]);
  const minX = Math.min(...xs);
  const maxY = Math.max(...ys);
  const span = Math.max(Math.max(...xs) - minX, maxY - Math.min(...ys)) || 1;
  const scale = (size - 2 * pad) / span;
  const offX = (size - (Math.max(...xs) - minX) * scale) / 2;
  const offY = (size - (maxY - Math.min(...ys)) * scale) / 2;
  const fmt = (n: number) => (Math.round(n * 10) / 10).toString();
  return rings
    .map(
      (ring) =>
        ring
          .map((p, i) => `${i === 0 ? "M" : "L"}${fmt(offX + (p[0] * k - minX) * scale)} ${fmt(offY + (maxY - p[1]) * scale)}`)
          .join(" ") + " Z",
    )
    .join(" ");
}

export const BoundaryThumbnail: React.FC<{
  polygon: GeoJSON.Polygon | null | undefined;
  size?: number;
  className?: string;
  title?: string;
}> = ({ polygon, size = 40, className = "", title = "Boundary outline" }) => {
  const d = thumbnailPath(polygon, size);
  if (!d) return null;
  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label={title}
      className={`shrink-0 rounded border border-slate-200 bg-slate-50 ${className}`}
    >
      <title>{title}</title>
      <path d={d} fill="#3b82f6" fillOpacity={0.2} stroke="#2563eb" strokeWidth={1.5} fillRule="evenodd" />
    </svg>
  );
};
