import React, { useEffect, useRef, useState } from "react";
import { Map as MapLibreMap } from "maplibre-gl";
import {
  TerraDraw,
  TerraDrawPolygonMode,
  TerraDrawSelectMode,
  TerraDrawRenderMode,
} from "terra-draw";
import { TerraDrawMapLibreGLAdapter } from "terra-draw-maplibre-gl-adapter";
import area from "@turf/area";
import booleanValid from "@turf/boolean-valid";
import kinks from "@turf/kinks";
import { CheckCircle2, AlertCircle, Trash2, Save, MousePointer, Hexagon, Info } from "lucide-react";

interface PolygonEditorProps {
  map: MapLibreMap | null;
  initialPolygon?: GeoJSON.Polygon | null;
  onSave: (polygon: GeoJSON.Polygon) => Promise<void> | void;
  isSaving?: boolean;
  className?: string;
}

const PREVIEW_SOURCE_ID = "fwt-boundary-preview-src";
const PREVIEW_FILL_ID = "fwt-boundary-preview-fill";
const PREVIEW_LINE_ID = "fwt-boundary-preview-line";
const PREVIEW_POINTS_ID = "fwt-boundary-preview-points";
const PREVIEW_CLOSING_ID = "fwt-boundary-preview-closing";

const ALL_BOUNDARY_LAYERS = [
  "td-polygon",
  PREVIEW_FILL_ID,
  "td-polygon-outline",
  "td-linestring",
  PREVIEW_LINE_ID,
  "td-point",
  PREVIEW_POINTS_ID,
  "td-point-marker",
  PREVIEW_CLOSING_ID,
];

/**
 * Builds high-contrast GeoJSON features (fill, outline, vertices, closing point)
 * so MapLibre directly renders the boundary on top of all raster/vector tile layers.
 */
function buildPreviewFeatures(polygon: GeoJSON.Polygon | null): GeoJSON.FeatureCollection {
  if (!polygon || !polygon.coordinates || polygon.coordinates.length === 0) {
    return { type: "FeatureCollection", features: [] };
  }
  const ring = polygon.coordinates[0];
  if (!ring || ring.length === 0) {
    return { type: "FeatureCollection", features: [] };
  }

  const features: GeoJSON.Feature[] = [];

  // 1. Polygon fill (when 3 or more coordinates exist)
  if (ring.length >= 3) {
    let fillRing = [...ring];
    const first = fillRing[0];
    const last = fillRing[fillRing.length - 1];
    if (first[0] !== last[0] || first[1] !== last[1]) {
      fillRing.push([first[0], first[1]]);
    }
    if (fillRing.length >= 4) {
      features.push({
        type: "Feature",
        properties: { kind: "fill" },
        geometry: {
          type: "Polygon",
          coordinates: [fillRing],
        },
      });
    }
  }

  // 2. Outline line connecting points
  if (ring.length >= 2) {
    features.push({
      type: "Feature",
      properties: { kind: "outline" },
      geometry: {
        type: "LineString",
        coordinates: ring,
      },
    });
  }

  // 3. Vertices (deduplicated consecutive positions)
  const distinctCoords: [number, number][] = [];
  for (let i = 0; i < ring.length; i++) {
    const pt = ring[i];
    if (
      distinctCoords.length === 0 ||
      pt[0] !== distinctCoords[distinctCoords.length - 1][0] ||
      pt[1] !== distinctCoords[distinctCoords.length - 1][1]
    ) {
      distinctCoords.push([pt[0], pt[1]]);
    }
  }

  const isClosed =
    distinctCoords.length > 2 &&
    distinctCoords[0][0] === distinctCoords[distinctCoords.length - 1][0] &&
    distinctCoords[0][1] === distinctCoords[distinctCoords.length - 1][1];

  const activePoints = isClosed ? distinctCoords.slice(0, -1) : distinctCoords;

  activePoints.forEach((coord, idx) => {
    if (idx === 0) {
      // First point is the target to close the polygon
      features.push({
        type: "Feature",
        properties: { kind: "closing" },
        geometry: {
          type: "Point",
          coordinates: coord,
        },
      });
    } else {
      features.push({
        type: "Feature",
        properties: { kind: "vertex", index: idx },
        geometry: {
          type: "Point",
          coordinates: coord,
        },
      });
    }
  });

  return { type: "FeatureCollection", features };
}

function isMapReady(map: MapLibreMap | null): boolean {
  if (!map) return false;
  try {
    const style = map.getStyle();
    return Boolean(style && style.layers && style.layers.length > 0);
  } catch {
    return false;
  }
}

/**
 * Ensures all Terra Draw and boundary preview layers are positioned at the very top of
 * the MapLibre layer stack so satellite and street tiles cannot occlude them.
 */
function bringBoundaryLayersToTop(map: MapLibreMap) {
  if (!isMapReady(map)) return;
  const style = map.getStyle();
  if (!style || !style.layers || style.layers.length === 0) return;

  const currentOrder = style.layers.map((l) => l.id);
  const presentLayers = ALL_BOUNDARY_LAYERS.filter((id) => currentOrder.includes(id));
  if (presentLayers.length === 0) return;

  // If already at the top in exact order, no moveLayer calls needed
  const tail = currentOrder.slice(-presentLayers.length);
  const alreadyAtTop = presentLayers.every((id, idx) => tail[idx] === id);
  if (alreadyAtTop) return;

  for (const layerId of presentLayers) {
    try {
      map.moveLayer(layerId);
    } catch {
      // ignore mid-operation error
    }
  }
}

/**
 * Creates or updates the native preview GeoJSON source and layers.
 */
function initPreviewLayers(map: MapLibreMap, initialGeom: GeoJSON.Polygon | null = null) {
  if (!map) return;
  if (!isMapReady(map)) {
    map.once("styledata", () => initPreviewLayers(map, initialGeom));
    return;
  }

  const initialData = buildPreviewFeatures(initialGeom);
  (window as any).__previewData = initialData;

  if (!map.getSource(PREVIEW_SOURCE_ID)) {
    map.addSource(PREVIEW_SOURCE_ID, {
      type: "geojson",
      data: initialData,
    });
  } else if (initialGeom) {
    const src = map.getSource(PREVIEW_SOURCE_ID) as any;
    if (src && typeof src.setData === "function") {
      src.setData(initialData);
    }
  }

  if (!map.getLayer(PREVIEW_FILL_ID)) {
    map.addLayer({
      id: PREVIEW_FILL_ID,
      type: "fill",
      source: PREVIEW_SOURCE_ID,
      filter: ["==", ["get", "kind"], "fill"],
      paint: {
        "fill-color": "#2563eb",
        "fill-opacity": 0.35,
      },
    });
  }

  if (!map.getLayer(PREVIEW_LINE_ID)) {
    map.addLayer({
      id: PREVIEW_LINE_ID,
      type: "line",
      source: PREVIEW_SOURCE_ID,
      filter: ["==", ["get", "kind"], "outline"],
      paint: {
        "line-color": "#1d4ed8",
        "line-width": 4,
        "line-opacity": 1,
      },
    });
  }

  if (!map.getLayer(PREVIEW_POINTS_ID)) {
    map.addLayer({
      id: PREVIEW_POINTS_ID,
      type: "circle",
      source: PREVIEW_SOURCE_ID,
      filter: ["==", ["get", "kind"], "vertex"],
      paint: {
        "circle-radius": 7,
        "circle-color": "#2563eb",
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": 2.5,
      },
    });
  }

  if (!map.getLayer(PREVIEW_CLOSING_ID)) {
    map.addLayer({
      id: PREVIEW_CLOSING_ID,
      type: "circle",
      source: PREVIEW_SOURCE_ID,
      filter: ["==", ["get", "kind"], "closing"],
      paint: {
        "circle-radius": 11,
        "circle-color": "#10b981",
        "circle-stroke-color": "#ffffff",
        "circle-stroke-width": 3,
      },
    });
  }

  bringBoundaryLayersToTop(map);
  map.triggerRepaint();
}

/**
 * Updates the native preview source data and repaints the canvas.
 */
function updatePreviewSource(map: MapLibreMap | null, geom: GeoJSON.Polygon | null) {
  if (!map) return;
  if (!isMapReady(map)) {
    map.once("styledata", () => updatePreviewSource(map, geom));
    return;
  }
  const features = buildPreviewFeatures(geom);
  (window as any).__previewData = features;
  const src = map.getSource(PREVIEW_SOURCE_ID) as any;
  if (!src || typeof src.setData !== "function") {
    initPreviewLayers(map, geom);
    return;
  }
  src.setData(features);
  bringBoundaryLayersToTop(map);
  map.triggerRepaint();
}

export const PolygonEditor: React.FC<PolygonEditorProps> = ({
  map,
  initialPolygon,
  onSave,
  isSaving = false,
  className = "w-full",
}) => {
  const drawRef = useRef<TerraDraw | null>(null);
  const currentPolygonRef = useRef<GeoJSON.Polygon | null>(initialPolygon || null);
  const [currentMode, setCurrentMode] = useState<string>("select");
  const [currentPolygon, setCurrentPolygon] = useState<GeoJSON.Polygon | null>(initialPolygon || null);
  const [areaSqM, setAreaSqM] = useState<number>(0);
  const [isValid, setIsValid] = useState<boolean>(true);
  const [validationMessage, setValidationMessage] = useState<string>("");

  // Initialize Terra Draw & preview layers once map is ready
  useEffect(() => {
    if (!map) return;

    let isDisposed = false;

    const setupEditor = () => {
      if (isDisposed) return;
      try {
        const draw = new TerraDraw({
          adapter: new TerraDrawMapLibreGLAdapter({ map }),
          modes: [
            new TerraDrawPolygonMode({
              pointerDistance: 40,
              showCoordinatePoints: true,
              styles: {
                fillColor: "#2563eb",
                fillOpacity: 0.35,
                outlineColor: "#1d4ed8",
                outlineWidth: 3,
                outlineOpacity: 1,
                closingPointColor: "#10b981",
                closingPointWidth: 9,
                closingPointOutlineColor: "#ffffff",
                closingPointOutlineWidth: 2,
                coordinatePointColor: "#2563eb",
                coordinatePointWidth: 7,
                coordinatePointOutlineColor: "#ffffff",
                coordinatePointOutlineWidth: 2,
              },
            }),
            new TerraDrawSelectMode({
              flags: {
                polygon: {
                  feature: {
                    draggable: true,
                    rotateable: false,
                    scaleable: false,
                    coordinates: {
                      midpoints: true,
                      draggable: true,
                      deletable: true,
                    },
                  },
                },
              },
              styles: {
                selectedPolygonColor: "#3b82f6",
                selectedPolygonFillOpacity: 0.4,
                selectedPolygonOutlineColor: "#1d4ed8",
                selectedPolygonOutlineWidth: 3,
                selectionPointColor: "#ffffff",
                selectionPointOutlineColor: "#1d4ed8",
                selectionPointWidth: 6,
                midPointColor: "#60a5fa",
                midPointWidth: 5,
              },
            }),
            new TerraDrawRenderMode({ modeName: "render", styles: {} as any }),
          ],
        });

        draw.start();
        drawRef.current = draw;
        (window as any).__draw = draw;

        // Initialize our native preview layers on top
        const existingPolygon = currentPolygonRef.current || initialPolygon;
        const hasInitial = Boolean(
          existingPolygon && existingPolygon.coordinates && existingPolygon.coordinates.length > 0
        );

        initPreviewLayers(map, existingPolygon);

        const startingMode = hasInitial ? "select" : "polygon";
        draw.setMode(startingMode);
        setCurrentMode(startingMode);

        if (hasInitial && existingPolygon && existingPolygon.coordinates?.length > 0) {
          draw.addFeatures([
            {
              type: "Feature",
              geometry: existingPolygon,
              properties: { mode: "polygon" },
            },
          ]);
          evaluateGeometry(existingPolygon);

          // Fit map bounds to polygon
          try {
            const ring = existingPolygon.coordinates[0];
            if (ring && ring.length > 0) {
              const bounds = ring.reduce(
                (b, c) => [
                  Math.min(b[0], c[0]),
                  Math.min(b[1], c[1]),
                  Math.max(b[2], c[0]),
                  Math.max(b[3], c[1]),
                ],
                [ring[0][0], ring[0][1], ring[0][0], ring[0][1]]
              );
              map.fitBounds(
                [
                  [bounds[0], bounds[1]],
                  [bounds[2], bounds[3]],
                ],
                { padding: 80, maxZoom: 18 }
              );
            }
          } catch (fitErr) {
            console.warn("Failed to fit bounds:", fitErr);
          }
        }

        draw.on("finish", () => {
          draw.setMode("select");
          setCurrentMode("select");
          const snapshot = draw.getSnapshot();
          const polygonFeature = snapshot.find(
            (f) => f.geometry.type === "Polygon" && f.geometry.coordinates.length > 0
          );
          if (polygonFeature && polygonFeature.geometry.type === "Polygon") {
            const geom = polygonFeature.geometry as GeoJSON.Polygon;
            currentPolygonRef.current = geom;
            setCurrentPolygon(geom);
            evaluateGeometry(geom);
            updatePreviewSource(map, geom);
          }
        });

        draw.on("change", () => {
          const snapshot = draw.getSnapshot();
          const polygonFeature = snapshot.find(
            (f) => f.geometry.type === "Polygon" && f.geometry.coordinates.length > 0
          );

          if (polygonFeature && polygonFeature.geometry.type === "Polygon") {
            const geom = polygonFeature.geometry as GeoJSON.Polygon;
            const isDrawing = Boolean(polygonFeature.properties?.currentlyDrawing);

            currentPolygonRef.current = geom;
            updatePreviewSource(map, geom);

            if (isDrawing) {
              setCurrentPolygon(geom);
              setIsValid(false);
              setValidationMessage(
                "Drawing in progress. Click corners, then click green dot / double-click / press Enter to close."
              );
            } else {
              setCurrentPolygon(geom);
              evaluateGeometry(geom);
            }
          } else {
            const lineFeature = snapshot.find(
              (f) => f.geometry.type === "LineString" && f.geometry.coordinates.length > 0
            );
            if (lineFeature && lineFeature.geometry.type === "LineString") {
              const lineGeom: GeoJSON.Polygon = {
                type: "Polygon",
                coordinates: [lineFeature.geometry.coordinates as [number, number][]],
              };
              currentPolygonRef.current = lineGeom;
              updatePreviewSource(map, lineGeom);
              setCurrentPolygon(lineGeom);
              setIsValid(false);
              setValidationMessage(
                "Drawing in progress. Click corners, then click green dot to close."
              );
            } else {
              currentPolygonRef.current = null;
              updatePreviewSource(map, null);
              setCurrentPolygon(null);
              setAreaSqM(0);
              setIsValid(true);
              setValidationMessage("No boundary drawn yet.");
            }
          }
        });

        // Ensure layers stay on top whenever style or tiles update
        const handleStyleData = () => {
          if (!map || !map.isStyleLoaded()) return;
          if (!map.getSource(PREVIEW_SOURCE_ID)) {
            initPreviewLayers(map, currentPolygonRef.current);
          } else {
            bringBoundaryLayersToTop(map);
          }
        };

        const handleSourceData = () => {
          if (!map || !map.isStyleLoaded()) return;
          bringBoundaryLayersToTop(map);
        };

        const handleIdle = () => {
          if (!map || !map.isStyleLoaded()) return;
          bringBoundaryLayersToTop(map);
        };

        map.on("styledata", handleStyleData);
        map.on("sourcedata", handleSourceData);
        map.on("idle", handleIdle);

        return () => {
          map.off("styledata", handleStyleData);
          map.off("sourcedata", handleSourceData);
          map.off("idle", handleIdle);
        };
      } catch (err) {
        console.error("TerraDraw init error:", err);
      }
    };

    let cleanupListeners: (() => void) | undefined;

    const runSetup = () => {
      if (isDisposed || cleanupListeners) return;
      cleanupListeners = setupEditor();
    };

    if (isMapReady(map)) {
      runSetup();
    } else {
      map.once("styledata", runSetup);
      map.once("load", runSetup);
    }

    return () => {
      isDisposed = true;
      if (cleanupListeners) {
        cleanupListeners();
      }
      try {
        if (drawRef.current) {
          drawRef.current.stop();
        }
      } catch {
        // ignore cleanup error
      }
      drawRef.current = null;

      try {
        if (map && map.isStyleLoaded()) {
          if (map.getLayer(PREVIEW_CLOSING_ID)) map.removeLayer(PREVIEW_CLOSING_ID);
          if (map.getLayer(PREVIEW_POINTS_ID)) map.removeLayer(PREVIEW_POINTS_ID);
          if (map.getLayer(PREVIEW_LINE_ID)) map.removeLayer(PREVIEW_LINE_ID);
          if (map.getLayer(PREVIEW_FILL_ID)) map.removeLayer(PREVIEW_FILL_ID);
          if (map.getSource(PREVIEW_SOURCE_ID)) map.removeSource(PREVIEW_SOURCE_ID);
        }
      } catch {
        // ignore style cleanup error
      }
    };
  }, [map]);

  // Sync if initialPolygon arrives or updates after initial map load
  useEffect(() => {
    if (!drawRef.current || !map || !initialPolygon) return;
    const ring = initialPolygon.coordinates?.[0];
    if (!ring || ring.length === 0) return;

    currentPolygonRef.current = initialPolygon;
    setCurrentPolygon(initialPolygon);
    evaluateGeometry(initialPolygon);

    const snapshot = drawRef.current.getSnapshot();
    if (snapshot.length === 0) {
      drawRef.current.addFeatures([
        {
          type: "Feature",
          geometry: initialPolygon,
          properties: { mode: "polygon" },
        },
      ]);
      drawRef.current.setMode("select");
      setCurrentMode("select");
    }

    updatePreviewSource(map, initialPolygon);
  }, [initialPolygon, map]);

  const evaluateGeometry = (geom: GeoJSON.Polygon) => {
    try {
      const sqM = area(geom);
      setAreaSqM(sqM);

      const ring = geom.coordinates[0];
      if (!ring || ring.length < 4) {
        setIsValid(false);
        setValidationMessage("Polygon ring must have at least 4 positions.");
        return;
      }

      const kinkFeatures = kinks(geom);
      if (kinkFeatures.features.length > 0) {
        setIsValid(false);
        setValidationMessage("Self-intersecting polygon (lines cross).");
        return;
      }

      const valid = booleanValid(geom);
      if (!valid) {
        setIsValid(false);
        setValidationMessage("Invalid polygon ring structure.");
        return;
      }

      setIsValid(true);
      setValidationMessage("Valid boundary polygon");
    } catch (err: any) {
      setIsValid(false);
      setValidationMessage(err.message || "Invalid geometry");
    }
  };

  const handleSetMode = (mode: "polygon" | "select") => {
    if (!drawRef.current) return;
    if (mode === "polygon" && currentPolygon) {
      // Keep existing polygon visible and editable in select mode
      drawRef.current.setMode("select");
      setCurrentMode("select");
      setValidationMessage("Boundary is loaded. Drag corner handles to reshape, or click Clear to redraw from scratch.");
      if (map) {
        bringBoundaryLayersToTop(map);
      }
      return;
    }
    drawRef.current.setMode(mode);
    setCurrentMode(mode);
    if (map) {
      bringBoundaryLayersToTop(map);
    }
  };

  const handleClear = () => {
    if (!drawRef.current) return;
    drawRef.current.clear();
    setCurrentPolygon(null);
    currentPolygonRef.current = null;
    setAreaSqM(0);
    setIsValid(false);
    setValidationMessage("Boundary cleared. Click corners on map to draw new boundary.");
    updatePreviewSource(map, null);
    drawRef.current.setMode("polygon");
    setCurrentMode("polygon");
  };

  const handleSave = async () => {
    if (!currentPolygon || !isValid || areaSqM <= 0) return;
    await onSave(currentPolygon);
  };

  const formatArea = (sqM: number) => {
    if (sqM <= 0) return "0 m²";
    const ha = (sqM / 10000).toFixed(2);
    const formattedSqM = Math.round(sqM).toLocaleString();
    return `${formattedSqM} m² (${ha} ha)`;
  };

  return (
    <div className={`space-y-2.5 ${className}`}>
      {/* Visual Step-by-Step Helper Banner */}
      <div
        className={`px-3.5 py-2 rounded-lg text-xs flex items-center justify-between border transition ${
          currentMode === "polygon"
            ? "bg-blue-50 border-blue-200 text-blue-900"
            : "bg-slate-50 border-slate-200 text-slate-700"
        }`}
      >
        <div className="flex items-center gap-2">
          <Info className="h-4 w-4 shrink-0 text-blue-600" />
          {currentMode === "polygon" ? (
            <span>
              <strong>Drawing Mode Active:</strong> Click corners on the map to trace the site. Click the{" "}
              <strong className="text-emerald-700 underline">green starting point</strong>, press{" "}
              <strong className="underline">Enter</strong>, or <strong>double-click</strong> to close and complete the boundary.
            </span>
          ) : (
            <span>
              <strong>Select & Edit Mode:</strong> Click the polygon to select it. Drag corner handles to reshape, or drag midpoints to add vertices.
            </span>
          )}
        </div>
        <span className="font-mono text-[11px] font-semibold uppercase px-2 py-0.5 rounded bg-white border border-slate-200">
          Mode: {currentMode === "polygon" ? "Drawing" : "Select/Edit"}
        </span>
      </div>

      {/* Main Control Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-3 rounded-lg border border-slate-200 shadow-xs">
        {/* Drawing Toolbar Modes */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => handleSetMode("polygon")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition ${
              currentMode === "polygon"
                ? "bg-indigo-600 text-white shadow-xs"
                : "bg-slate-100 hover:bg-slate-200 text-slate-700"
            }`}
            title="Click corners on map to draw polygon"
          >
            <Hexagon className="h-3.5 w-3.5" />
            Draw Polygon
          </button>

          <button
            type="button"
            onClick={() => handleSetMode("select")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition ${
              currentMode === "select"
                ? "bg-indigo-600 text-white shadow-xs"
                : "bg-slate-100 hover:bg-slate-200 text-slate-700"
            }`}
            title="Drag vertices or move polygon"
          >
            <MousePointer className="h-3.5 w-3.5" />
            Select / Edit
          </button>

          <button
            type="button"
            onClick={handleClear}
            className="flex items-center gap-1 px-2.5 py-1.5 bg-slate-100 hover:bg-red-50 hover:text-red-600 rounded-md text-xs font-medium text-slate-600 transition"
            title="Delete current boundary"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Clear
          </button>
        </div>

        {/* Geometry Status & Area Display */}
        <div className="flex items-center gap-3 text-xs">
          {currentPolygon && (
            <div className="flex items-center gap-1.5">
              {isValid && areaSqM > 0 ? (
                <span className="flex items-center gap-1 text-emerald-700 font-medium">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  {validationMessage}
                </span>
              ) : (
                <span className="flex items-center gap-1 text-red-700 font-medium">
                  <AlertCircle className="h-4 w-4 text-red-600" />
                  {validationMessage}
                </span>
              )}
            </div>
          )}

          {areaSqM > 0 && (
            <span className="bg-slate-100 text-slate-800 px-2.5 py-1 rounded font-mono font-bold text-xs">
              Area: {formatArea(areaSqM)}
            </span>
          )}

          {/* Save Button */}
          <button
            type="button"
            disabled={!currentPolygon || !isValid || areaSqM <= 0 || isSaving}
            onClick={handleSave}
            className={`flex items-center gap-1.5 px-4 py-1.5 rounded-md text-xs font-bold transition shadow-xs ${
              !currentPolygon || !isValid || areaSqM <= 0 || isSaving
                ? "bg-slate-200 text-slate-400 cursor-not-allowed"
                : "bg-emerald-600 hover:bg-emerald-700 text-white"
            }`}
          >
            <Save className="h-3.5 w-3.5" />
            {isSaving ? "Saving..." : "Save Boundary"}
          </button>
        </div>
      </div>
    </div>
  );
};
