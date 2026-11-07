import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useAuth } from "../context/AuthContext";
import {
  Search,
  Plus,
  Building2,
  CheckCircle2,
  AlertTriangle,
  Sun,
  Home,
  RefreshCw,
  ExternalLink,
  MapPin,
  X,
} from "lucide-react";
import { MapContainer, PolygonEditor } from "../features/map";
import { Map as MapLibreMap } from "maplibre-gl";

interface Worksite {
  id: string;
  job_number: string;
  job_name: string;
  renewal_reference: string | null;
  group_id: string;
  group_name: string | null;
  zone_id: string;
  zone_name: string | null;
  customer_type: string | null;
  is_outdoor: boolean;
  country: string;
  start_date: string | null;
  end_date: string | null;
  has_boundary: boolean;
  rep_latitude: string | number | null;
  rep_longitude: string | number | null;
  budget_amount: string | number | null;
  is_active: boolean;
  version: number;
}

interface AccommodationItem {
  id: string;
  accommodation_code: string;
  name: string;
  address: string | null;
  rep_latitude: string | number | null;
  rep_longitude: string | number | null;
  has_boundary: boolean;
  boundary_geojson?: GeoJSON.Polygon | null;
  is_active: boolean;
  version: number;
}

interface Group {
  id: string;
  code: string;
  name: string;
}

interface Zone {
  id: string;
  code: string;
  name: string;
}

export const Worksites: React.FC = () => {
  const navigate = useNavigate();
  const { token, user } = useAuth();
  const [activeTab, setActiveTab] = useState<"worksites" | "accommodations">("worksites");
  const [worksites, setWorksites] = useState<Worksite[]>([]);
  const [accommodations, setAccommodations] = useState<AccommodationItem[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [loading, setLoading] = useState(true);

  // Accommodation boundary modal
  const [drawingAccommodation, setDrawingAccommodation] = useState<AccommodationItem | null>(null);
  const [mapInstance, setMapInstance] = useState<MapLibreMap | null>(null);
  const [savingAccommodationBoundary, setSavingAccommodationBoundary] = useState(false);

  // Filters
  const [search, setSearch] = useState("");
  const [groupFilter, setGroupFilter] = useState("");
  const [zoneFilter, setZoneFilter] = useState("");
  const [countryFilter, setCountryFilter] = useState("");
  const [boundaryFilter, setBoundaryFilter] = useState<string>("SET");

  // Create Modal
  const [modalOpen, setModalOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [formNumber, setFormNumber] = useState("");
  const [formName, setFormName] = useState("");
  const [formGroupId, setFormGroupId] = useState("");
  const [formZoneId, setFormZoneId] = useState("");
  const [formCountry, setFormCountry] = useState("AE");
  const [formCustomerType, setFormCustomerType] = useState("Direct");
  const [formRenewalRef, setFormRenewalRef] = useState("");
  const [formBudget, setFormBudget] = useState("");

  const fetchData = async () => {
    setLoading(true);
    try {
      const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

      // 1. Worksites
      const params = new URLSearchParams();
      if (search) params.set("q", search);
      if (groupFilter) params.set("group_id", groupFilter);
      if (zoneFilter) params.set("zone_id", zoneFilter);
      if (countryFilter) params.set("country", countryFilter);
      if (boundaryFilter === "SET") params.set("has_boundary", "true");
      if (boundaryFilter === "UNSET") params.set("has_boundary", "false");

      const [wsRes, gRes, zRes, accRes] = await Promise.all([
        fetch(`/api/v1/worksites?${params.toString()}`, { headers }),
        fetch("/api/v1/groups", { headers }),
        fetch("/api/v1/zones", { headers }),
        fetch("/api/v1/accommodations", { headers }),
      ]);

      if (wsRes.ok) {
        setWorksites(await wsRes.json());
      }
      if (gRes.ok) {
        setGroups(await gRes.json());
      }
      if (zRes.ok) {
        setZones(await zRes.json());
      }
      if (accRes.ok) {
        setAccommodations(await accRes.json());
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [search, groupFilter, zoneFilter, countryFilter, boundaryFilter]);

  const handleSaveAccommodationBoundary = async (polygon: GeoJSON.Polygon) => {
    if (!drawingAccommodation) return;
    setSavingAccommodationBoundary(true);
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
        throw new Error(err.detail || "Failed to save boundary.");
      }

      setDrawingAccommodation(null);
      fetchData();
    } catch (err: any) {
      alert(err.message || "Failed to save accommodation boundary");
    } finally {
      setSavingAccommodationBoundary(false);
    }
  };

  const handleCreateWorksite = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");

    // Regex check: 2 digits + letter (A/B/C) + 5 digits
    const cleanedNumber = formNumber.trim().toUpperCase();
    if (!/^\d{2}[ABC]\d{5}$/.test(cleanedNumber)) {
      setErrorMsg(
        "Job number format must be 2 digits + letter (A outdoor, B indoor, C water feature) + 5 digits (e.g. 12A14301)."
      );
      return;
    }

    setCreateLoading(true);
    try {
      const res = await fetch("/api/v1/worksites", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          job_number: cleanedNumber,
          job_name: formName.trim(),
          group_id: formGroupId,
          zone_id: formZoneId,
          country: formCountry,
          customer_type: formCustomerType || null,
          renewal_reference: formRenewalRef.trim() || null,
          budget_amount: formBudget ? parseFloat(formBudget) : null,
        }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to create worksite");
      }

      setModalOpen(false);
      setFormNumber("");
      setFormName("");
      setFormRenewalRef("");
      setFormBudget("");
      fetchData();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to create worksite");
    } finally {
      setCreateLoading(false);
    }
  };

  const isAdminOrEngineer = user?.role === "ADMIN" || user?.role === "ENGINEER";

  const filteredAccommodations = accommodations.filter((acc) => {
    if (search) {
      const q = search.toLowerCase();
      const match =
        acc.accommodation_code.toLowerCase().includes(q) ||
        acc.name.toLowerCase().includes(q) ||
        (acc.address && acc.address.toLowerCase().includes(q));
      if (!match) return false;
    }
    if (boundaryFilter === "SET" && !acc.has_boundary) return false;
    if (boundaryFilter === "UNSET" && acc.has_boundary) return false;
    return true;
  });

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <Building2 className="h-6 w-6 text-indigo-600" />
            Worksites & Parent Jobs
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Manage contract jobs, staffing items, and boundary geofences (BR-JB-01).
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/boundaries"
            className="flex items-center gap-2 px-3.5 py-2 rounded-md bg-amber-50 hover:bg-amber-100 border border-amber-200 text-amber-900 text-sm font-medium transition"
          >
            <AlertTriangle className="h-4 w-4 text-amber-600" />
            Boundary Setup Queue
          </Link>

          {isAdminOrEngineer && (
            <button
              onClick={() => {
                setErrorMsg("");
                setModalOpen(true);
              }}
              className="flex items-center gap-2 px-4 py-2 rounded-md bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium shadow-sm transition"
            >
              <Plus className="h-4 w-4" />
              New Worksite
            </button>
          )}
        </div>
      </div>

      {/* Tab Switcher: Worksites vs Accommodations */}
      <div className="flex items-center gap-3 border-b border-slate-200 pb-2">
        <button
          onClick={() => setActiveTab("worksites")}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg transition ${
            activeTab === "worksites"
              ? "bg-indigo-50 text-indigo-700 border border-indigo-200"
              : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
          }`}
        >
          <Building2 className="h-4 w-4" />
          Worksites ({worksites.length})
        </button>
        <button
          onClick={() => setActiveTab("accommodations")}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-lg transition ${
            activeTab === "accommodations"
              ? "bg-indigo-50 text-indigo-700 border border-indigo-200"
              : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
          }`}
        >
          <Home className="h-4 w-4" />
          Accommodations ({filteredAccommodations.length})
        </button>
      </div>

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-wrap gap-4 items-center justify-between">
        <div className="flex flex-wrap items-center gap-3 flex-1 min-w-[280px]">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder={activeTab === "worksites" ? "Search job number or name..." : "Search code, name, address..."}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-sm border border-slate-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

          {activeTab === "worksites" && (
            <>
              <select
                value={groupFilter}
                onChange={(e) => setGroupFilter(e.target.value)}
                className="text-sm border border-slate-300 rounded-md py-1.5 px-3 focus:outline-none focus:ring-1 focus:ring-indigo-500 bg-white"
              >
                <option value="">All Groups</option>
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name} ({g.code})
                  </option>
                ))}
              </select>

              <select
                value={zoneFilter}
                onChange={(e) => setZoneFilter(e.target.value)}
                className="text-sm border border-slate-300 rounded-md py-1.5 px-3 focus:outline-none focus:ring-1 focus:ring-indigo-500 bg-white"
              >
                <option value="">All Zones</option>
                {zones.map((z) => (
                  <option key={z.id} value={z.id}>
                    {z.name}
                  </option>
                ))}
              </select>
            </>
          )}

          <select
            value={boundaryFilter}
            onChange={(e) => setBoundaryFilter(e.target.value)}
            className="text-sm border border-slate-300 rounded-md py-1.5 px-3 focus:outline-none focus:ring-1 focus:ring-indigo-500 bg-white"
          >
            <option value="SET">Boundaries Set (Active)</option>
            <option value="ALL">All Boundaries</option>
            <option value="UNSET">No Boundary</option>
          </select>

          {activeTab === "worksites" && (
            <select
              value={countryFilter}
              onChange={(e) => setCountryFilter(e.target.value)}
              className="text-sm border border-slate-300 rounded-md py-1.5 px-3 focus:outline-none focus:ring-1 focus:ring-indigo-500 bg-white"
            >
              <option value="">All Countries</option>
              <option value="AE">UAE (AE)</option>
              <option value="SA">KSA (SA)</option>
            </select>
          )}
        </div>

        <button
          onClick={fetchData}
          className="p-2 border border-slate-200 rounded-md hover:bg-slate-50 text-slate-600 transition"
          title="Refresh data"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin text-indigo-600" : ""}`} />
        </button>
      </div>

      {/* Content Table: Worksites or Accommodations */}
      {activeTab === "worksites" ? (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-slate-600 font-semibold text-xs tracking-wider uppercase">
                  <th className="py-3 px-4">Job Number</th>
                  <th className="py-3 px-4">Job Name</th>
                  <th className="py-3 px-4">Group & Zone</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4">Country</th>
                  <th className="py-3 px-4">Boundary Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {loading ? (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-slate-400">
                      <RefreshCw className="h-6 w-6 animate-spin mx-auto text-indigo-600 mb-2" />
                      Loading worksites...
                    </td>
                  </tr>
                ) : worksites.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-slate-400">
                      No worksites match your criteria.
                    </td>
                  </tr>
                ) : (
                  worksites.map((ws) => (
                    <tr
                      key={ws.id}
                      onClick={() => navigate({ to: "/worksites/$worksiteId", params: { worksiteId: ws.id } })}
                      className="hover:bg-indigo-50/50 cursor-pointer transition"
                    >
                      <td className="py-3.5 px-4 font-mono font-medium text-slate-900">
                        {ws.job_number}
                      </td>
                      <td className="py-3.5 px-4 font-medium text-slate-800">
                        <div className="flex items-center gap-1.5">
                          <span>{ws.job_name}</span>
                          {ws.renewal_reference && (
                            <span className="text-xs text-slate-400">({ws.renewal_reference})</span>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-500 flex items-center gap-2 mt-0.5 font-normal">
                          <span>Period: {ws.start_date || "Start N/A"} – {ws.end_date || "Ongoing"}</span>
                          {ws.budget_amount != null && (
                            <span>• Budget: {Number(ws.budget_amount).toLocaleString()} AED/yr</span>
                          )}
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-xs text-slate-600">
                        <div>{ws.group_name || "-"}</div>
                        <div className="text-slate-400">{ws.zone_name || "-"}</div>
                      </td>
                      <td className="py-3.5 px-4">
                        {ws.is_outdoor ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
                            <Sun className="h-3 w-3 text-amber-500" /> Outdoor (A)
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
                            <Home className="h-3 w-3 text-blue-500" /> Indoor / Other
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4">
                        <span className="px-2 py-0.5 rounded bg-slate-100 font-mono text-xs font-medium text-slate-600">
                          {ws.country}
                        </span>
                      </td>
                      <td className="py-3.5 px-4">
                        {ws.has_boundary ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                            Boundary Set
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
                            <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
                            No Boundary
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        {ws.has_boundary ? (
                          <Link
                            to="/worksites/$worksiteId"
                            params={{ worksiteId: ws.id }}
                            onClick={(e) => e.stopPropagation()}
                            className="inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-800"
                          >
                            View & Edit
                            <ExternalLink className="h-3 w-3" />
                          </Link>
                        ) : (
                          <Link
                            to="/worksites/$worksiteId"
                            params={{ worksiteId: ws.id }}
                            search={{ tab: "boundary" } as any}
                            onClick={(e) => e.stopPropagation()}
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded-md text-xs font-semibold shadow-xs"
                          >
                            <MapPin className="h-3 w-3" />
                            Draw Boundary
                          </Link>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-slate-600 font-semibold text-xs tracking-wider uppercase">
                  <th className="py-3 px-4">Camp Code</th>
                  <th className="py-3 px-4">Accommodation Name</th>
                  <th className="py-3 px-4">Address / Area</th>
                  <th className="py-3 px-4">Coordinates</th>
                  <th className="py-3 px-4">Boundary Status</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {loading ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-slate-400">
                      <RefreshCw className="h-6 w-6 animate-spin mx-auto text-indigo-600 mb-2" />
                      Loading accommodations...
                    </td>
                  </tr>
                ) : filteredAccommodations.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-slate-400">
                      No accommodations found matching your filter criteria.
                    </td>
                  </tr>
                ) : (
                  filteredAccommodations.map((acc) => (
                    <tr
                      key={acc.id}
                      onClick={() => setDrawingAccommodation(acc)}
                      className="hover:bg-indigo-50/50 cursor-pointer transition"
                    >
                      <td className="py-3.5 px-4 font-mono font-medium text-slate-900">
                        {acc.accommodation_code}
                      </td>
                      <td className="py-3.5 px-4 font-medium text-slate-800">{acc.name}</td>
                      <td className="py-3.5 px-4 text-xs text-slate-600">{acc.address || "—"}</td>
                      <td className="py-3.5 px-4 text-xs font-mono text-slate-500">
                        {acc.rep_latitude && acc.rep_longitude
                          ? `${Number(acc.rep_latitude).toFixed(4)}, ${Number(acc.rep_longitude).toFixed(4)}`
                          : "—"}
                      </td>
                      <td className="py-3.5 px-4">
                        {acc.has_boundary ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                            Boundary Set
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
                            <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
                            No Boundary
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setDrawingAccommodation(acc);
                          }}
                          className={`px-3 py-1.5 rounded-md text-xs font-semibold inline-flex items-center gap-1.5 shadow-xs transition ${
                            acc.has_boundary
                              ? "bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200"
                              : "bg-blue-600 hover:bg-blue-700 text-white"
                          }`}
                        >
                          <MapPin className="h-3.5 w-3.5" />
                          {acc.has_boundary ? "Edit Boundary" : "Draw Boundary"}
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Accommodation Boundary Modal */}
      {drawingAccommodation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-3xl bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[90vh]">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div>
                <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <Home className="h-5 w-5 text-blue-600" />
                  {drawingAccommodation.has_boundary ? "Edit" : "Draw"} Boundary for {drawingAccommodation.name} ({drawingAccommodation.accommodation_code})
                </h2>
                <p className="text-xs text-slate-500">
                  Worker living quarters / camp boundary for attendance and nightly rest verification.
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
                isSaving={savingAccommodationBoundary}
              />
            </div>
          </div>
        </div>
      )}

      {/* Create Worksite Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-lg w-full p-6 space-y-4">
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Building2 className="h-5 w-5 text-indigo-600" />
              Create New Worksite
            </h2>

            {errorMsg && (
              <div className="p-3 bg-red-50 border border-red-200 rounded text-xs text-red-700 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0 text-red-500" />
                {errorMsg}
              </div>
            )}

            <form onSubmit={handleCreateWorksite} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Job Number *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. 12A14301"
                    value={formNumber}
                    onChange={(e) => setFormNumber(e.target.value.toUpperCase())}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded text-sm font-mono focus:ring-1 focus:ring-indigo-500"
                  />
                  <p className="text-[10px] text-slate-400 mt-0.5">2 digits + letter (A/B/C) + 5 digits</p>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Country *
                  </label>
                  <select
                    value={formCountry}
                    onChange={(e) => setFormCountry(e.target.value)}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded text-sm focus:ring-1 focus:ring-indigo-500 bg-white"
                  >
                    <option value="AE">AE (United Arab Emirates)</option>
                    <option value="SA">SA (Saudi Arabia)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Job Name *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Dubai Marina Promenade"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="w-full px-3 py-1.5 border border-slate-300 rounded text-sm focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Customer Group *
                  </label>
                  <select
                    required
                    value={formGroupId}
                    onChange={(e) => setFormGroupId(e.target.value)}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded text-sm focus:ring-1 focus:ring-indigo-500 bg-white"
                  >
                    <option value="">Select Group...</option>
                    {groups.map((g) => (
                      <option key={g.id} value={g.id}>
                        {g.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Zone *
                  </label>
                  <select
                    required
                    value={formZoneId}
                    onChange={(e) => setFormZoneId(e.target.value)}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded text-sm focus:ring-1 focus:ring-indigo-500 bg-white"
                  >
                    <option value="">Select Zone...</option>
                    {zones.map((z) => (
                      <option key={z.id} value={z.id}>
                        {z.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Customer Type
                  </label>
                  <select
                    value={formCustomerType}
                    onChange={(e) => setFormCustomerType(e.target.value)}
                    className="w-full px-2 py-1.5 border border-slate-300 rounded text-xs bg-white"
                  >
                    <option value="Direct">Direct</option>
                    <option value="Indirect">Indirect</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Renewal Ref
                  </label>
                  <input
                    type="text"
                    placeholder="R1, R2..."
                    value={formRenewalRef}
                    onChange={(e) => setFormRenewalRef(e.target.value)}
                    className="w-full px-2 py-1.5 border border-slate-300 rounded text-xs"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Labour Budget
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    placeholder="e.g. 50000"
                    value={formBudget}
                    onChange={(e) => setFormBudget(e.target.value)}
                    className="w-full px-2 py-1.5 border border-slate-300 rounded text-xs"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-200">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2 border border-slate-300 rounded text-xs font-medium text-slate-700 hover:bg-slate-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createLoading}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded text-xs font-medium shadow-sm transition disabled:opacity-50"
                >
                  {createLoading ? "Creating..." : "Save Worksite"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
