// One Google map, created once and reused (ADR-033, owner 25 Nov).
//
// Google bills a "map load" each time a `google.maps.Map` is created. The map pages show one map
// at a time, so the map and its <div> are kept when a page, tab or dialog closes and moved into
// the next container that asks for one: switching to a worksite's Boundary tab again, reopening
// a boundary dialog or going back to the Live Map costs no new map load. A second map at the
// same time (never needed today) would be created and pooled too.

import { reportUsage } from "./loader";

export interface PooledMap {
  map: google.maps.Map;
  div: HTMLDivElement;
}

export interface MapViewOptions {
  center: google.maps.LatLngLiteral;
  zoom: number;
  /** "cooperative": Ctrl/Cmd+wheel zooms (maps inside a scrolling page). */
  gestureHandling: "cooperative" | "greedy";
}

const free: PooledMap[] = [];
let created = 0;

/** How many Google maps this browser tab created (for the usage check in the PR). */
export function mapsCreated(): number {
  return created;
}

export function acquireMap(
  mapsLib: Pick<google.maps.MapsLibrary, "Map">,
  container: HTMLElement,
  mapId: string,
  view: MapViewOptions,
  onCreate: () => void = () => reportUsage("MAP_LOAD"),
): PooledMap {
  let pooled = free.pop();
  if (pooled) {
    pooled.map.setOptions({ gestureHandling: view.gestureHandling, mapTypeId: "roadmap" });
    pooled.map.setCenter(view.center);
    pooled.map.setZoom(view.zoom);
  } else {
    const div = document.createElement("div");
    div.style.width = "100%";
    div.style.height = "100%";
    const map = new mapsLib.Map(div, {
      mapId,
      center: view.center,
      zoom: view.zoom,
      // Owner, 25 Nov: road map by default (boundary editor too, until the legal question on
      // drawing over imagery is answered); satellite and hybrid through Google's own control.
      mapTypeId: "roadmap",
      mapTypeControl: true,
      mapTypeControlOptions: { mapTypeIds: ["roadmap", "satellite", "hybrid"] },
      streetViewControl: false,
      fullscreenControl: false,
      clickableIcons: false,
      gestureHandling: view.gestureHandling,
    });
    pooled = { map, div };
    created += 1;
    onCreate();
  }
  container.appendChild(pooled.div);
  return pooled;
}

export function releaseMap(pooled: PooledMap): void {
  pooled.div.remove();
  if (!free.includes(pooled)) free.push(pooled);
}

/** Test helper: forget pooled maps. */
export function resetMapPool(): void {
  free.length = 0;
  created = 0;
}
