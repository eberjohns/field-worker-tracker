import React, { useEffect, useRef, useState } from "react";
import {
  TerraDraw,
  TerraDrawPolygonMode,
  TerraDrawSelectMode,
  TerraDrawRenderMode,
} from "terra-draw";
import type { MapPort } from "./port";
import { bboxOf, checkPolygon, closeRing, parsePolygonInput } from "./geo";
import { CheckCircle2, AlertCircle, Trash2, Save, MousePointer, Hexagon, Info, Clipboard, Crosshair } from "lucide-react";
import { Modal, useToast } from "../../ui";

interface PolygonEditorProps {
  map: MapPort | null;
  initialPolygon?: GeoJSON.Polygon | null;
  /** Deployment country, for the swapped longitude/latitude check (optional). */
  country?: string;
  onSave: (polygon: GeoJSON.Polygon) => Promise<void> | void;
  isSaving?: boolean;
  className?: string;
}

const PREVIEW_FILL_ID = "fwt-boundary-preview-fill";
const PREVIEW_LINE_ID = "fwt-boundary-preview-line";
const PREVIEW_POINTS_ID = "fwt-boundary-preview-points";
const PREVIEW_CLOSING_ID = "fwt-boundary-preview-closing";
const PREVIEW_IDS = [PREVIEW_FILL_ID, PREVIEW_LINE_ID, PREVIEW_POINTS_ID, PREVIEW_CLOSING_ID];

type Pt = GeoJSON.Feature<GeoJSON.Point>;
const point = (coordinates: number[], properties: Record<string, unknown> = {}): Pt => ({
  type: "Feature",
  properties,
  geometry: { type: "Point", coordinates },
});

/**
 * Draws a high-contrast copy of the boundary (fill, outline, vertices, the green closing point)
 * above the map and the drawing tool, through the map port, so it stays visible on satellite.
 */
function renderPreview(map: MapPort | null, polygon: GeoJSON.Polygon | null) {
  if (!map) return;
  const ring = polygon?.coordinates?.[0] ?? [];
  const fillRing = ring.length >= 3 ? closeRing(ring) : [];
  const fills: GeoJSON.Feature<GeoJSON.Polygon>[] =
    fillRing.length >= 4
      ? [{ type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [fillRing] } }]
      : [];

  // Vertices without consecutive repeats; the first one is the closing target.
  const distinct: number[][] = [];
  for (const pt of ring) {
    const prev = distinct[distinct.length - 1];
    if (!prev || prev[0] !== pt[0] || prev[1] !== pt[1]) distinct.push([pt[0], pt[1]]);
  }
  const first = distinct[0];
  const last = distinct[distinct.length - 1];
  const closed = distinct.length > 2 && first[0] === last[0] && first[1] === last[1];
  const active = closed ? distinct.slice(0, -1) : distinct;

  const top = { top: true };
  map.setPolygons(
    PREVIEW_FILL_ID,
    fills,
    { fillColor: "#2563eb", fillOpacity: 0.35, strokeColor: "#1d4ed8", strokeWidth: 0 },
    top,
  );
  map.setLine(
    PREVIEW_LINE_ID,
    ring.length >= 2 ? ring.map((p) => [p[0], p[1]] as [number, number]) : [],
    { color: "#1d4ed8", width: 4 },
    top,
  );
  map.setPoints(
    PREVIEW_POINTS_ID,
    active.slice(1).map((c, i) => point(c, { index: i + 1 })),
    { color: "#2563eb", radius: 7, strokeColor: "#ffffff", strokeWidth: 2.5 },
    top,
  );
  map.setPoints(
    PREVIEW_CLOSING_ID,
    active.length > 0 ? [point(active[0])] : [],
    { color: "#10b981", radius: 11, strokeColor: "#ffffff", strokeWidth: 3 },
    top,
  );
}

function fitTo(map: MapPort, polygon: GeoJSON.Polygon) {
  const bbox = bboxOf(polygon);
  if (!bbox) return;
  try {
    map.fitBounds(bbox, { padding: 80, maxZoom: 18 });
  } catch (err) {
    console.warn("Failed to fit bounds:", err);
  }
}

export const PolygonEditor: React.FC<PolygonEditorProps> = ({
  map,
  initialPolygon,
  country,
  onSave,
  isSaving = false,
  className = "w-full",
}) => {
  const toast = useToast();
  const drawRef = useRef<TerraDraw | null>(null);
  const currentPolygonRef = useRef<GeoJSON.Polygon | null>(initialPolygon || null);
  const [currentMode, setCurrentMode] = useState<string>("select");
  const [currentPolygon, setCurrentPolygon] = useState<GeoJSON.Polygon | null>(initialPolygon || null);
  const [areaSqM, setAreaSqM] = useState<number>(0);
  const [isValid, setIsValid] = useState<boolean>(true);
  const [validationMessage, setValidationMessage] = useState<string>("");
  const [showPasteModal, setShowPasteModal] = useState<boolean>(false);
  const [pasteInput, setPasteInput] = useState<string>("");
  const [locating, setLocating] = useState<boolean>(false);

  const handleLocateMe = () => {
    if (!navigator.geolocation) {
      toast.warning("Geolocation is not supported by your browser");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false);
        const { longitude, latitude } = pos.coords;
        map?.flyTo([longitude, latitude], 16);
      },
      (err) => {
        setLocating(false);
        toast.error(err, "Could not get GPS location");
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  // Initialize Terra Draw & preview layers once map is ready
  useEffect(() => {
    if (!map) return;

    let isDisposed = false;

    const setupEditor = async () => {
      if (isDisposed) return;
      try {
        const adapter = await map.createDrawAdapter();
        if (isDisposed) return;
        const draw = new TerraDraw({
          adapter,
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

        renderPreview(map, existingPolygon ?? null);

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

          fitTo(map, existingPolygon);
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
            renderPreview(map, geom);
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
            renderPreview(map, geom);

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
              renderPreview(map, lineGeom);
              setCurrentPolygon(lineGeom);
              setIsValid(false);
              setValidationMessage(
                "Drawing in progress. Click corners, then click green dot to close."
              );
            } else {
              currentPolygonRef.current = null;
              renderPreview(map, null);
              setCurrentPolygon(null);
              setAreaSqM(0);
              setIsValid(true);
              setValidationMessage("No boundary drawn yet.");
            }
          }
        });

      } catch (err) {
        console.error("TerraDraw init error:", err);
      }
    };

    void setupEditor();

    return () => {
      isDisposed = true;
      try {
        if (drawRef.current) {
          drawRef.current.stop();
        }
      } catch {
        // ignore cleanup error
      }
      drawRef.current = null;

      for (const id of PREVIEW_IDS) map.removeOverlay(id);
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

    renderPreview(map, initialPolygon);
  }, [initialPolygon, map]);

  const evaluateGeometry = (geom: GeoJSON.Polygon) => {
    try {
      const result = checkPolygon(geom, country);
      setAreaSqM(result.areaSqM);
      setIsValid(result.ok);
      setValidationMessage(result.ok ? "Valid boundary polygon" : result.message);
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
      map?.raiseTopOverlays();
      return;
    }
    drawRef.current.setMode(mode);
    setCurrentMode(mode);
    map?.raiseTopOverlays();
  };

  const handleClear = () => {
    if (!drawRef.current) return;
    drawRef.current.clear();
    setCurrentPolygon(null);
    currentPolygonRef.current = null;
    setAreaSqM(0);
    setIsValid(false);
    setValidationMessage("Boundary cleared. Click corners on map to draw new boundary.");
    renderPreview(map, null);
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

  const handleApplyPastedPolygon = () => {
    const polygon = parsePolygonInput(pasteInput);
    if (!polygon) {
      toast.error("Invalid polygon format. Please paste valid GeoJSON coordinates or WKT POLYGON((lng lat, ...)).");
      return;
    }
    if (!drawRef.current || !map) return;

    drawRef.current.clear();
    drawRef.current.addFeatures([
      {
        type: "Feature",
        geometry: polygon,
        properties: { mode: "polygon" },
      },
    ]);
    drawRef.current.setMode("select");
    setCurrentMode("select");
    setCurrentPolygon(polygon);
    currentPolygonRef.current = polygon;
    evaluateGeometry(polygon);
    renderPreview(map, polygon);

    fitTo(map, polygon);

    setShowPasteModal(false);
    setPasteInput("");
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
            onClick={handleLocateMe}
            disabled={locating}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md text-xs font-semibold transition"
            title="Focus map to my current GPS location"
          >
            <Crosshair className={`h-3.5 w-3.5 text-indigo-600 ${locating ? "animate-spin" : ""}`} />
            {locating ? "Locating..." : "My Location"}
          </button>

          <button
            type="button"
            onClick={() => setShowPasteModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-indigo-50 hover:text-indigo-700 rounded-md text-xs font-semibold text-slate-700 transition"
            title="Paste GeoJSON or WKT polygon from clipboard"
          >
            <Clipboard className="h-3.5 w-3.5 text-indigo-600" />
            Paste Polygon
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

      {/* Paste Polygon Modal */}
      {showPasteModal && (
        <Modal
          open
          onClose={() => {
                  setShowPasteModal(false);
                  setPasteInput("");
                }}
          size="md"
          title="Paste Boundary Polygon"
          footer={
            <div className="flex w-full flex-wrap items-center justify-end gap-2">
              <button
                  type="button"
                  onClick={() => {
                    setShowPasteModal(false);
                    setPasteInput("");
                  }}
                  className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={!pasteInput.trim()}
                  onClick={handleApplyPastedPolygon}
                  className="px-4 py-1.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg disabled:opacity-50 transition"
                >
                  Apply Boundary
                </button>
            </div>
          }
        >
          <div className="space-y-4">
            <p className="text-xs text-slate-500">
              Paste a <strong>GeoJSON Polygon</strong> or <strong>WKT string</strong> (e.g. copied from the Mobile Tester Proxy) to load and save as this boundary.
            </p>
            <textarea
              rows={6}
              value={pasteInput}
              onChange={(e) => setPasteInput(e.target.value)}
              placeholder="Paste GeoJSON: [[ [55.38, 25.13], ... ]] or WKT: POLYGON((55.38 25.13, ...))"
              className="w-full font-mono text-xs p-3 rounded-lg border border-slate-300 focus:outline-none focus:border-indigo-600 focus:ring-1 focus:ring-indigo-600 bg-slate-50"
            />
          </div>
        </Modal>
      )}
    </div>
  );
};
