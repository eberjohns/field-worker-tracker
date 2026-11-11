import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useAuth } from "../context/AuthContext";
import {
  MapPin,
  Hexagon,
  Building2,
  Home,
  CheckCircle2,
  AlertTriangle,
  Search,
  RefreshCw,
  X,
  Download,
  Upload,
  FileText,
} from "lucide-react";
import { MapContainer, PolygonEditor } from "../features/map";
import { Map as MapLibreMap } from "maplibre-gl";

interface QueueItem {
  id: string;
  entity_type: "WORKSITE" | "ACCOMMODATION";
  code: string;
  name: string;
  zone_name: string | null;
  country: string;
  has_boundary: boolean;
  rep_latitude?: number | string | null;
  rep_longitude?: number | string | null;
  boundary_geojson?: GeoJSON.Polygon | null;
}

interface BoundaryQueueData {
  total_count: number;
  done_count: number;
  unset_count: number;
  worksites_unset_count?: number;
  worksites_total_count?: number;
  worksites_done_count?: number;
  accommodations_unset_count?: number;
  accommodations_total_count?: number;
  accommodations_done_count?: number;
  items: QueueItem[];
}

interface BoundaryImportError {
  row: number;
  code: string;
  entity_type: string;
  reason: string;
}

interface BoundaryImportResponse {
  total_rows: number;
  updated_count: number;
  skipped_count: number;
  errors: BoundaryImportError[];
}

function parseImportText(text: string): { entity_type: string; code: string; polygon: string }[] {
  const trimmed = text.trim();
  if (!trimmed) return [];

  // If JSON
  if (trimmed.startsWith("[") || trimmed.startsWith("{")) {
    const parsed = JSON.parse(trimmed);
    const list = Array.isArray(parsed) ? parsed : parsed.items || [parsed];
    return list.map((item: any) => ({
      entity_type: item.entity_type || item.type || "WORKSITE",
      code: String(item.code || item.job_number || item.accommodation_code || ""),
      polygon: typeof item.polygon === "object" ? JSON.stringify(item.polygon) : String(item.polygon || ""),
    }));
  }

  // Parse CSV
  const lines = trimmed.split(/\r?\n/).filter((l) => l.trim().length > 0);
  const items: { entity_type: string; code: string; polygon: string }[] = [];

  let startIndex = 0;
  if (lines.length > 0) {
    const firstLower = lines[0].toLowerCase();
    if (firstLower.includes("entity_type") || firstLower.includes("code") || firstLower.includes("job")) {
      startIndex = 1;
    }
  }

  for (let i = startIndex; i < lines.length; i++) {
    const line = lines[i];
    const cells: string[] = [];
    let cur = "";
    let inQuotes = false;
    for (let c = 0; c < line.length; c++) {
      const char = line[c];
      if (char === '"' || char === "'") {
        inQuotes = !inQuotes;
      } else if (char === "," && !inQuotes) {
        cells.push(cur.trim());
        cur = "";
      } else {
        cur += char;
      }
    }
    cells.push(cur.trim());

    if (cells.length >= 2) {
      let entity_type = "WORKSITE";
      let code = "";
      let polygon = "";

      if (cells.length === 2) {
        code = cells[0].replace(/^["']|["']$/g, "");
        polygon = cells[1].replace(/^["']|["']$/g, "");
      } else if (cells.length === 3) {
        entity_type = cells[0].toUpperCase();
        code = cells[1].replace(/^["']|["']$/g, "");
        polygon = cells[2].replace(/^["']|["']$/g, "");
      } else {
        entity_type = cells[0].toUpperCase();
        code = cells[1].replace(/^["']|["']$/g, "");
        polygon = cells[cells.length - 1].replace(/^["']|["']$/g, "");
      }

      items.push({
        entity_type,
        code,
        polygon,
      });
    }
  }

  return items;
}

export const Boundaries: React.FC = () => {
  const navigate = useNavigate();
  const { token } = useAuth();
  const [data, setData] = useState<BoundaryQueueData | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("UNSET");

  // Accommodation boundary modal
  const [drawingAccommodation, setDrawingAccommodation] = useState<QueueItem | null>(null);
  const [mapInstance, setMapInstance] = useState<MapLibreMap | null>(null);
  const [savingBoundary, setSavingBoundary] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Import / Export boundaries state
  const [showImportModal, setShowImportModal] = useState(false);
  const [importText, setImportText] = useState("");
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<BoundaryImportResponse | null>(null);
  const [exporting, setExporting] = useState(false);

  const handleExport = async (format: "csv" | "json") => {
    setExporting(true);
    setErrorMsg(null);
    try {
      const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await fetch(`/api/v1/boundaries/export?format=${format}`, { headers });
      if (!res.ok) throw new Error("Failed to export boundaries.");

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `fwt_boundaries_export.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      setSuccessMsg(`Exported boundaries as ${format.toUpperCase()}.`);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to export boundaries.");
    } finally {
      setExporting(false);
    }
  };

  const handleProcessImport = async () => {
    if (!importText.trim()) {
      setErrorMsg("Please paste or upload boundary data to import.");
      return;
    }
    setImporting(true);
    setErrorMsg(null);
    try {
      const items = parseImportText(importText);
      if (items.length === 0) {
        throw new Error("No valid rows could be parsed. Check the format.");
      }

      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      };

      const res = await fetch("/api/v1/boundaries/import", {
        method: "POST",
        headers,
        body: JSON.stringify({ items }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to import boundaries.");
      }

      const dataRes: BoundaryImportResponse = await res.json();
      setImportResult(dataRes);
      if (dataRes.updated_count > 0) {
        fetchData();
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to import boundaries.");
    } finally {
      setImporting(false);
    }
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
      const params = new URLSearchParams({ limit: "200" });
      if (statusFilter !== "ALL") params.set("status", statusFilter);
      if (typeFilter !== "ALL") params.set("entity_type", typeFilter);
      const res = await fetch(`/api/v1/boundary-queue?${params.toString()}`, { headers });
      if (res.ok) {
        setData(await res.json());
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [statusFilter, typeFilter]);

  const handleSaveAccommodationBoundary = async (polygon: GeoJSON.Polygon) => {
    if (!drawingAccommodation) return;
    setSavingBoundary(true);
    setErrorMsg(null);
    try {
      const res = await fetch(`/api/v1/accommodations/${drawingAccommodation.id}/boundary`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ boundary: polygon }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to save accommodation boundary.");
      }

      setSuccessMsg(`Boundary saved for ${drawingAccommodation.name}.`);
      setDrawingAccommodation(null);
      fetchData();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to save boundary.");
    } finally {
      setSavingBoundary(false);
    }
  };

  const filteredItems = (data?.items || []).filter((item) => {
    if (typeFilter !== "ALL" && item.entity_type !== typeFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        item.code.toLowerCase().includes(q) ||
        item.name.toLowerCase().includes(q) ||
        (item.zone_name && item.zone_name.toLowerCase().includes(q))
      );
    }
    return true;
  });

  const totalAll = (data?.worksites_total_count || 0) + (data?.accommodations_total_count || 0);
  const unsetAll = (data?.worksites_unset_count || 0) + (data?.accommodations_unset_count || 0);
  const doneAll = totalAll - unsetAll;
  const progressPercent = totalAll > 0 ? Math.round((doneAll / totalAll) * 100) : 100;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2.5">
            <Hexagon className="h-6 w-6 text-indigo-600" />
            Boundary Setup Queue
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Prioritized work queue for sites and accommodations missing geofence polygon boundaries.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Export Buttons */}
          <button
            type="button"
            onClick={() => handleExport("csv")}
            disabled={exporting}
            className="px-3 py-2 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-50 flex items-center gap-1.5 shadow-xs"
            title="Export boundaries as CSV"
          >
            <Download className="h-3.5 w-3.5 text-slate-500" />
            Export CSV
          </button>
          <button
            type="button"
            onClick={() => handleExport("json")}
            disabled={exporting}
            className="px-3 py-2 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-50 flex items-center gap-1.5 shadow-xs"
            title="Export boundaries as GeoJSON / JSON"
          >
            <Download className="h-3.5 w-3.5 text-indigo-500" />
            Export JSON
          </button>

          {/* Import Button */}
          <button
            type="button"
            onClick={() => {
              setImportText("");
              setImportResult(null);
              setShowImportModal(true);
            }}
            className="px-3 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-xs transition-colors"
          >
            <Upload className="h-3.5 w-3.5" />
            Import Boundaries
          </button>

          <button
            type="button"
            onClick={fetchData}
            className="px-3.5 py-2 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-50 flex items-center gap-2 shadow-xs"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh Queue
          </button>
        </div>
      </div>

      {/* Notifications */}
      {successMsg && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg flex items-center justify-between text-xs text-emerald-800">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)}>
            <X className="h-3.5 w-3.5 text-emerald-600" />
          </button>
        </div>
      )}
      {errorMsg && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-center justify-between text-xs text-red-800">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-red-600 shrink-0" />
            <span>{errorMsg}</span>
          </div>
          <button onClick={() => setErrorMsg(null)}>
            <X className="h-3.5 w-3.5 text-red-600" />
          </button>
        </div>
      )}

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              Overall Progress
            </span>
            <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700">
              {progressPercent}% Done
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-slate-900">{unsetAll}</span>
            <span className="text-xs text-slate-500">pending boundaries across {totalAll} total</span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
            <div
              className="bg-indigo-600 h-2 rounded-full transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
              <Building2 className="h-4 w-4 text-amber-500" />
              Worksites Queue
            </span>
            <span className="text-xs font-semibold text-slate-600">
              {data ? (data.worksites_total_count ?? 0) - (data.worksites_unset_count ?? 0) : 0} /{" "}
              {data?.worksites_total_count || 0}
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-amber-600">
              {data?.worksites_unset_count || 0}
            </span>
            <span className="text-xs text-slate-500">worksites missing polygon</span>
          </div>
          <p className="text-[11px] text-slate-400">
            Attendance check-in requires a valid boundary polygon.
          </p>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
              <Home className="h-4 w-4 text-blue-500" />
              Accommodations Queue
            </span>
            <span className="text-xs font-semibold text-slate-600">
              {data ? (data.accommodations_total_count ?? 0) - (data.accommodations_unset_count ?? 0) : 0} /{" "}
              {data?.accommodations_total_count || 0}
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-blue-600">
              {data?.accommodations_unset_count || 0}
            </span>
            <span className="text-xs text-slate-500">camps missing polygon</span>
          </div>
          <p className="text-[11px] text-slate-400">
            Used for night-time rest and departure verification.
          </p>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 flex flex-col sm:flex-row gap-3 items-center justify-between shadow-xs">
        <div className="relative w-full sm:w-80">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by code, name, or zone..."
            className="w-full pl-9 pr-3 py-1.5 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
          <Search className="absolute left-3 top-2 h-3.5 w-3.5 text-slate-400" />
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-semibold text-slate-600">Type:</span>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="px-3 py-1.5 text-xs border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="ALL">All Entity Types</option>
              <option value="WORKSITE">Worksites Only</option>
              <option value="ACCOMMODATION">Accommodations Only</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-xs font-semibold text-slate-600">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-1.5 text-xs border border-slate-300 rounded-lg bg-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="UNSET">Missing Boundary (Queue)</option>
              <option value="ALL">All Statuses</option>
              <option value="SET">Boundary Set Only</option>
            </select>
          </div>
        </div>
      </div>

      {/* Queue Table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-xs">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider text-[11px]">
            <tr>
              <th className="px-5 py-3">Type</th>
              <th className="px-5 py-3">Code / Job #</th>
              <th className="px-5 py-3">Name</th>
              <th className="px-5 py-3">Zone / Location</th>
              <th className="px-5 py-3 text-center">Country</th>
              <th className="px-5 py-3 text-center">Boundary Status</th>
              <th className="px-5 py-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filteredItems.map((item) => (
              <tr
                key={item.id}
                onClick={() => {
                  if (item.entity_type === "WORKSITE") {
                    navigate({
                      to: "/worksites/$worksiteId",
                      params: { worksiteId: item.id },
                      search: { tab: "boundary" } as any,
                    });
                  } else {
                    setDrawingAccommodation(item);
                  }
                }}
                className="hover:bg-indigo-50/50 cursor-pointer transition-colors"
              >
                <td className="px-5 py-3.5">
                  <span
                    className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                      item.entity_type === "WORKSITE"
                        ? "bg-amber-100 text-amber-800"
                        : "bg-blue-100 text-blue-800"
                    }`}
                  >
                    {item.entity_type === "WORKSITE" ? (
                      <Building2 className="h-3 w-3" />
                    ) : (
                      <Home className="h-3 w-3" />
                    )}
                    {item.entity_type}
                  </span>
                </td>
                <td className="px-5 py-3.5 font-mono font-bold text-slate-900">{item.code}</td>
                <td className="px-5 py-3.5 font-medium text-slate-800">{item.name}</td>
                <td className="px-5 py-3.5 text-slate-600">{item.zone_name || "Unassigned"}</td>
                <td className="px-5 py-3.5 text-center font-semibold text-slate-700">
                  {item.country}
                </td>
                <td className="px-5 py-3.5 text-center">
                  {item.has_boundary ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                      <CheckCircle2 className="h-3 w-3" />
                      Boundary Set
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                      <AlertTriangle className="h-3 w-3" />
                      Missing
                    </span>
                  )}
                </td>
                <td className="px-5 py-3.5 text-right">
                  {item.entity_type === "WORKSITE" ? (
                    <Link
                      to="/worksites/$worksiteId"
                      params={{ worksiteId: item.id }}
                      search={{ tab: "boundary" } as any}
                      onClick={(e) => e.stopPropagation()}
                      className={`px-3 py-1.5 rounded-lg font-semibold text-xs inline-flex items-center gap-1.5 shadow-xs ${
                        item.has_boundary
                          ? "bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200"
                          : "bg-indigo-600 hover:bg-indigo-700 text-white"
                      }`}
                    >
                      <MapPin className="h-3 w-3" />
                      {item.has_boundary ? "Edit Boundary" : "Draw Boundary"}
                    </Link>
                  ) : (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setDrawingAccommodation(item);
                      }}
                      className={`px-3 py-1.5 rounded-lg font-semibold text-xs inline-flex items-center gap-1.5 shadow-xs ${
                        item.has_boundary
                          ? "bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200"
                          : "bg-blue-600 hover:bg-blue-700 text-white"
                      }`}
                    >
                      <MapPin className="h-3 w-3" />
                      {item.has_boundary ? "Edit Boundary" : "Draw Boundary"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {filteredItems.length === 0 && (
              <tr>
                <td colSpan={7} className="px-5 py-12 text-center text-slate-400">
                  {loading
                    ? "Loading boundary data..."
                    : "No matching items found for selected filters."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Accommodation Boundary Modal */}
      {drawingAccommodation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-3xl bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[90vh]">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div>
                <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <Home className="h-5 w-5 text-blue-600" />
                  {drawingAccommodation.has_boundary ? "Edit" : "Draw"} Boundary for {drawingAccommodation.name} ({drawingAccommodation.code})
                </h2>
                <p className="text-xs text-slate-500">
                  Camp / Accommodation polygon setup for night-time rest and departure verification.
                </p>
              </div>
              <button
                onClick={() => setDrawingAccommodation(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200/60"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-4 space-y-4 flex-1 overflow-y-auto">
              <MapContainer
                initialZoom={15}
                onMapReady={(map) => setMapInstance(map)}
                onMapUnmount={() => setMapInstance(null)}
                className="w-full h-[450px]"
              />

              <PolygonEditor
                map={mapInstance}
                initialPolygon={drawingAccommodation.boundary_geojson as GeoJSON.Polygon | null}
                onSave={handleSaveAccommodationBoundary}
                isSaving={savingBoundary}
              />
            </div>
          </div>
        </div>
      )}

      {/* Import Boundaries Modal */}
      {showImportModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-2xl bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[90vh]">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div>
                <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <Upload className="h-5 w-5 text-indigo-600" />
                  Import Boundary Polygons
                </h2>
                <p className="text-xs text-slate-500">
                  Bulk import worksite and accommodation boundaries from CSV or GeoJSON.
                </p>
              </div>
              <button
                onClick={() => {
                  setShowImportModal(false);
                  setImportResult(null);
                }}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200/60"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-6 space-y-4 flex-1 overflow-y-auto text-xs">
              {!importResult ? (
                <>
                  {/* Format Guidelines */}
                  <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-1.5 text-slate-600 text-[11px]">
                    <div className="font-bold text-slate-800 uppercase tracking-wider text-[10px]">
                      Supported CSV / Text Formats:
                    </div>
                    <div className="font-mono bg-white p-2 rounded border border-slate-200 text-slate-700 select-all">
                      entity_type, code, polygon<br />
                      WORKSITE, 12A14301, "POLYGON((55.385 25.120, 55.388 25.120, 55.388 25.125, 55.385 25.120))"<br />
                      ACCOMMODATION, WARSAN_01, "POLYGON((...))"
                    </div>
                    <p className="text-slate-500 text-[10px]">
                      • Worksite primary key is <strong>job_number</strong>; Accommodation primary key is <strong>accommodation_code</strong>.<br />
                      • Unmatched codes will be safely skipped and listed in the summary report.
                    </p>
                  </div>

                  {/* File Upload Shortcut */}
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-700 text-xs">Upload File or Paste Data:</span>
                    <label className="cursor-pointer px-3 py-1.5 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50 flex items-center gap-1.5 font-medium shadow-2xs">
                      <FileText className="h-3.5 w-3.5 text-indigo-600" />
                      Browse CSV / JSON
                      <input
                        type="file"
                        accept=".csv,.json,.txt"
                        className="hidden"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (!file) return;
                          const reader = new FileReader();
                          reader.onload = (ev) => {
                            setImportText(String(ev.target?.result || ""));
                          };
                          reader.readAsText(file);
                        }}
                      />
                    </label>
                  </div>

                  {/* Paste Textarea */}
                  <textarea
                    rows={8}
                    value={importText}
                    onChange={(e) => setImportText(e.target.value)}
                    placeholder="Paste CSV rows or JSON array here..."
                    className="w-full font-mono text-2xs p-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500 bg-slate-50"
                  />
                </>
              ) : (
                /* Import Results Summary */
                <div className="space-y-4">
                  <div className="grid grid-cols-3 gap-3 text-center">
                    <div className="bg-slate-50 border border-slate-200 p-3 rounded-lg">
                      <div className="text-xl font-bold text-slate-900">{importResult.total_rows}</div>
                      <div className="text-[11px] text-slate-500 uppercase font-bold">Total Rows</div>
                    </div>
                    <div className="bg-emerald-50 border border-emerald-200 p-3 rounded-lg">
                      <div className="text-xl font-bold text-emerald-700">{importResult.updated_count}</div>
                      <div className="text-[11px] text-emerald-600 uppercase font-bold">Updated</div>
                    </div>
                    <div className="bg-amber-50 border border-amber-200 p-3 rounded-lg">
                      <div className="text-xl font-bold text-amber-700">{importResult.skipped_count}</div>
                      <div className="text-[11px] text-amber-600 uppercase font-bold">Skipped</div>
                    </div>
                  </div>

                  {importResult.errors.length > 0 && (
                    <div className="border border-amber-200 rounded-lg overflow-hidden">
                      <div className="bg-amber-50 px-3 py-2 font-bold text-amber-800 text-[11px] border-b border-amber-200">
                        Skipped Rows Details ({importResult.errors.length})
                      </div>
                      <div className="max-h-48 overflow-y-auto divide-y divide-slate-100 text-2xs">
                        {importResult.errors.map((err, idx) => (
                          <div key={idx} className="p-2 flex items-start justify-between bg-white">
                            <div>
                              <span className="font-mono font-bold text-slate-700">Row {err.row}:</span>{" "}
                              <span className="font-mono text-indigo-700 font-bold">{err.code}</span>{" "}
                              <span className="text-slate-400">({err.entity_type})</span>
                            </div>
                            <span className="text-amber-700 text-[11px]">{err.reason}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {importResult.updated_count > 0 && (
                    <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800 flex items-center gap-2 text-xs">
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
                      <span>{importResult.updated_count} boundaries were successfully saved to the database.</span>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
              {!importResult ? (
                <>
                  <button
                    type="button"
                    onClick={() => setShowImportModal(false)}
                    className="px-4 py-1.5 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-100 font-medium"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    disabled={importing || !importText.trim()}
                    onClick={handleProcessImport}
                    className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-semibold disabled:opacity-50 flex items-center gap-1.5 transition-colors"
                  >
                    {importing ? "Importing..." : "Process Import"}
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    setShowImportModal(false);
                    setImportResult(null);
                  }}
                  className="w-full py-1.5 bg-slate-800 hover:bg-slate-900 text-white rounded-lg font-semibold transition-colors"
                >
                  Close & Refresh Queue
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
