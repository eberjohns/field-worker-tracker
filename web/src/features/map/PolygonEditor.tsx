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

export const PolygonEditor: React.FC<PolygonEditorProps> = ({
  map,
  initialPolygon,
  onSave,
  isSaving = false,
  className = "w-full",
}) => {
  const drawRef = useRef<TerraDraw | null>(null);
  const [currentMode, setCurrentMode] = useState<string>("select");
  const [currentPolygon, setCurrentPolygon] = useState<GeoJSON.Polygon | null>(initialPolygon || null);
  const [areaSqM, setAreaSqM] = useState<number>(0);
  const [isValid, setIsValid] = useState<boolean>(true);
  const [validationMessage, setValidationMessage] = useState<string>("");

  // Initialize Terra Draw once map is ready
  useEffect(() => {
    if (!map) return;

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

      // Preserve any in-progress polygon or initial polygon
      const existingPolygon = currentPolygon || initialPolygon;
      const hasInitial = Boolean(
        existingPolygon && existingPolygon.coordinates && existingPolygon.coordinates.length > 0
      );

      // Start in select mode if polygon already exists; otherwise start in polygon mode ready to draw
      const startingMode = hasInitial ? "select" : "polygon";
      draw.setMode(startingMode);
      setCurrentMode(startingMode);

      // Load existing polygon if exists
      if (hasInitial && existingPolygon && existingPolygon.coordinates?.length > 0) {
        const loadResult = draw.addFeatures([
          {
            type: "Feature",
            geometry: existingPolygon,
            properties: { mode: "polygon" },
          },
        ]);
        if (loadResult && loadResult[0] && !loadResult[0].valid) {
          console.warn("TerraDraw initial addFeatures failed:", loadResult[0].reason);
        }
        evaluateGeometry(existingPolygon);

        // Fit map bounds to the polygon
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

      // When user completes/closes a polygon, switch to select mode so handles are visible
      draw.on("finish", () => {
        draw.setMode("select");
        setCurrentMode("select");
      });

      draw.on("change", () => {
        const snapshot = draw.getSnapshot();
        const polygonFeature = snapshot.find(
          (f) => f.geometry.type === "Polygon" && f.geometry.coordinates.length > 0
        );

        if (polygonFeature && polygonFeature.geometry.type === "Polygon") {
          const geom = polygonFeature.geometry as GeoJSON.Polygon;
          const isDrawing = Boolean(polygonFeature.properties?.currentlyDrawing);

          if (isDrawing) {
            setCurrentPolygon(geom);
            setIsValid(false);
            setValidationMessage("Drawing in progress. Click corners, then click green dot / double-click / press Enter to close.");
          } else {
            setCurrentPolygon(geom);
            evaluateGeometry(geom);
          }
        } else {
          setCurrentPolygon(null);
          setAreaSqM(0);
          setIsValid(true);
          setValidationMessage("No boundary drawn yet.");
        }
      });

      return () => {
        try {
          draw.stop();
        } catch (e) {
          // ignore cleanup error
        }
        drawRef.current = null;
      };
    } catch (err) {
      console.error("TerraDraw init error:", err);
    }
  }, [map]);

  // Sync if initialPolygon arrives or updates after initial map load
  useEffect(() => {
    if (!drawRef.current || !map || !initialPolygon) return;
    const snapshot = drawRef.current.getSnapshot();
    if (snapshot.length === 0 && initialPolygon.coordinates?.length > 0) {
      drawRef.current.addFeatures([
        {
          type: "Feature",
          geometry: initialPolygon,
          properties: { mode: "polygon" },
        },
      ]);
      drawRef.current.setMode("select");
      setCurrentMode("select");
      evaluateGeometry(initialPolygon);
    }
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

      // Check self-intersection kinks
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
      // Clear existing feature so user can trace fresh boundary vertices
      drawRef.current.clear();
      setCurrentPolygon(null);
      setAreaSqM(0);
      setIsValid(false);
      setValidationMessage("Click corners on the map to draw new boundary.");
    }
    drawRef.current.setMode(mode);
    setCurrentMode(mode);
  };

  const handleClear = () => {
    if (!drawRef.current) return;
    drawRef.current.clear();
    setCurrentPolygon(null);
    setAreaSqM(0);
    setIsValid(true);
    setValidationMessage("Boundary cleared.");
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
