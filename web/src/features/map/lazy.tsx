/**
 * The map components, loaded on first render (Batch 9 step 3). The map library is about 1 MB,
 * so pages that show a map only in a tab or a dialog (Worksites, Worksite detail) load it when
 * the map first appears, not with the page.
 */
import React, { Suspense } from "react";
import type { MapContainer as MapContainerType } from "./MapContainer";
import type { PolygonEditor as PolygonEditorType } from "./PolygonEditor";
import type { PlaceSearch as PlaceSearchType } from "./PlaceSearch";
import { Skeleton } from "../../ui";

const LazyMapContainer = React.lazy(() => import("./MapContainer").then((m) => ({ default: m.MapContainer })));
const LazyPolygonEditor = React.lazy(() => import("./PolygonEditor").then((m) => ({ default: m.PolygonEditor })));
const LazyPlaceSearch = React.lazy(() => import("./PlaceSearch").then((m) => ({ default: m.PlaceSearch })));

type Props<C> = C extends React.FC<infer P> ? P : never;

export const MapContainer: React.FC<Props<typeof MapContainerType>> = (props) => (
  <Suspense fallback={<Skeleton className="h-full min-h-[320px] w-full" />}>
    <LazyMapContainer {...props} />
  </Suspense>
);

export const PolygonEditor: React.FC<Props<typeof PolygonEditorType>> = (props) => (
  <Suspense fallback={null}>
    <LazyPolygonEditor {...props} />
  </Suspense>
);

export const PlaceSearch: React.FC<Props<typeof PlaceSearchType>> = (props) => (
  <Suspense fallback={null}>
    <LazyPlaceSearch {...props} />
  </Suspense>
);
