import React, { useState, useEffect } from "react";
import { Link } from "@tanstack/react-router";
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

export const Boundaries: React.FC = () => {
  const { token } = useAuth();
  const [data, setData] = useState<BoundaryQueueData | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("ALL");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  // Accommodation boundary modal
  const [drawingAccommodation, setDrawingAccommodation] = useState<QueueItem | null>(null);
  const [mapInstance, setMapInstance] = useState<MapLibreMap | null>(null);
  const [savingBoundary, setSavingBoundary] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

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
        <button
          onClick={fetchData}
          className="px-3.5 py-2 border border-slate-300 rounded-lg text-xs font-semibold text-slate-700 hover:bg-slate-50 flex items-center gap-2 shadow-xs"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh Queue
        </button>
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
              <option value="ALL">All Statuses</option>
              <option value="SET">Boundary Set Only</option>
              <option value="UNSET">Missing Boundary (Queue)</option>
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
              <tr key={item.id} className="hover:bg-slate-50/80 transition-colors">
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
                      onClick={() => setDrawingAccommodation(item)}
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
    </div>
  );
};
