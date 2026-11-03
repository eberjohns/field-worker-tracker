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
import { CheckCircle2, AlertCircle, Trash2, Save, MousePointer, Hexagon } from "lucide-react";

interface PolygonEditorProps {
  map: MapLibreMap | null;
  initialPolygon?: GeoJSON.Polygon | null;
  onSave: (polygon: GeoJSON.Polygon) => Promise<void> | void;
  isSaving?: boolean;
}

export const PolygonEditor: React.FC<PolygonEditorProps> = ({
  map,
  initialPolygon,
  onSave,
  isSaving = false,
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
          }),
          new TerraDrawRenderMode({ modeName: "render", styles: {} as any }),
        ],
      });

      draw.start();
      drawRef.current = draw;

      // Load initial polygon if exists
      if (initialPolygon && initialPolygon.coordinates && initialPolygon.coordinates.length > 0) {
        draw.addFeatures([
          {
            type: "Feature",
            geometry: initialPolygon,
            properties: { mode: "polygon" },
          },
        ]);
        evaluateGeometry(initialPolygon);
      }

      draw.on("change", () => {
        const snapshot = draw.getSnapshot();
        const polygonFeature = snapshot.find(
          (f) => f.geometry.type === "Polygon" && (f.properties?.mode === "polygon" || f.geometry.coordinates.length > 0)
        );

        if (polygonFeature && polygonFeature.geometry.type === "Polygon") {
          const geom = polygonFeature.geometry as GeoJSON.Polygon;
          setCurrentPolygon(geom);
          evaluateGeometry(geom);
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
    <div className="absolute bottom-3 left-3 right-3 z-20 flex flex-wrap items-center justify-between gap-3 bg-white/95 backdrop-blur-sm p-3 rounded-lg border border-slate-200 shadow-md">
      {/* Drawing Toolbar Modes */}
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={() => handleSetMode("polygon")}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition ${
            currentMode === "polygon"
              ? "bg-indigo-600 text-white shadow-sm"
              : "bg-slate-100 hover:bg-slate-200 text-slate-700"
          }`}
          title="Click vertices on map to draw polygon"
        >
          <Hexagon className="h-3.5 w-3.5" />
          Draw Polygon
        </button>

        <button
          type="button"
          onClick={() => handleSetMode("select")}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition ${
            currentMode === "select"
              ? "bg-indigo-600 text-white shadow-sm"
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
          className="flex items-center gap-1 px-2.5 py-1.5 bg-slate-100 hover:bg-red-50 hover:text-red-600 rounded text-xs font-medium text-slate-600 transition"
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
          <span className="bg-slate-100 text-slate-800 px-2.5 py-1 rounded font-mono font-medium">
            Area: {formatArea(areaSqM)}
          </span>
        )}

        {/* Save Button */}
        <button
          type="button"
          disabled={!currentPolygon || !isValid || areaSqM <= 0 || isSaving}
          onClick={handleSave}
          className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded text-xs font-medium transition shadow-sm ${
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
  );
};
