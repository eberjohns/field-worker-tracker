import React, { useState, useEffect } from "react";
import { useParams, Link } from "@tanstack/react-router";
import { useAuth } from "../context/AuthContext";
import {
  Building2,
  ArrowLeft,
  MapPin,
  Calendar,
  Layers,
  ShieldCheck,
  Plus,
  Edit2,
  Copy,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  Sun,
  Home,
  X,
  Sparkles,
} from "lucide-react";
import { MapContainer, PolygonEditor, PlaceSearch } from "../features/map";
import { Map as MapLibreMap } from "maplibre-gl";
import { JobItemModal } from "../components/jobs/JobItemModal";
import { JobItemValidationModal } from "../components/jobs/JobItemValidationModal";
import { CopyBoundaryModal } from "../components/jobs/CopyBoundaryModal";

interface WorksiteDetail {
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
  has_boundary: boolean;
  boundary_geojson: GeoJSON.Polygon | null;
  boundary_area_sqm: number | null;
  rep_latitude: number | null;
  rep_longitude: number | null;
  budget_amount: number | null;
  is_active: boolean;
  version: number;
  job_items: any[];
  items?: any[];
}

interface Occurrence {
  id: string;
  job_item_id: string;
  sub_item_code: string | null;
  staff_grade_description: string | null;
  window_start: string;
  window_end: string;
  due_date: string;
  slot_index: number;
  required_staff_count: number;
  required_hours_per_staff: number;
  status: string;
}

export const WorksiteDetail: React.FC = () => {
  const { worksiteId } = useParams({ strict: false }) as { worksiteId: string };
  const { token, user } = useAuth();

  const searchParams = new URLSearchParams(typeof window !== "undefined" ? window.location.search : "");
  const requestedTab = searchParams.get("tab");
  const initialTab =
    requestedTab === "boundary" || requestedTab === "items" || requestedTab === "schedule"
      ? (requestedTab as "overview" | "items" | "boundary" | "schedule")
      : "overview";

  const [worksite, setWorksite] = useState<WorksiteDetail | null>(null);
  const [occurrences, setOccurrences] = useState<Occurrence[]>([]);
  const [activeTab, setActiveTab] = useState<"overview" | "items" | "boundary" | "schedule">(initialTab);
  const [loading, setLoading] = useState(true);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Map reference
  const [mapInstance, setMapInstance] = useState<MapLibreMap | null>(null);
  const [savingBoundary, setSavingBoundary] = useState(false);

  // Job Item Modals
  const [isItemModalOpen, setIsItemModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<any | null>(null);
  const [validatingItemId, setValidatingItemId] = useState<string | null>(null);

  // Copy Boundary Modals
  const [copyModalMode, setCopyModalMode] = useState<"COPY_FROM" | "COPY_TO" | null>(null);

  // Metadata edit form
  const [isEditingMetadata, setIsEditingMetadata] = useState(false);
  const [editName, setEditName] = useState("");
  const [editCustomerType, setEditCustomerType] = useState("");
  const [editRenewalRef, setEditRenewalRef] = useState("");
  const [editBudget, setEditBudget] = useState("");

  const fetchData = async () => {
    if (!worksiteId) return;
    setLoading(true);
    setErrorMessage(null);
    try {
      const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

      const res = await fetch(`/api/v1/worksites/${worksiteId}`, { headers });
      if (!res.ok) {
        throw new Error("Failed to load worksite.");
      }
      const data: WorksiteDetail = await res.json();
      setWorksite(data);

      setEditName(data.job_name);
      setEditCustomerType(data.customer_type || "");
      setEditRenewalRef(data.renewal_reference || "");
      setEditBudget(data.budget_amount != null ? String(data.budget_amount) : "");

      // Fetch occurrences
      const occRes = await fetch(`/api/v1/occurrences?worksite_id=${worksiteId}&limit=100`, { headers });
      if (occRes.ok) {
        setOccurrences(await occRes.json());
      }
    } catch (err: any) {
      setErrorMessage(err.message || "An error occurred.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [worksiteId]);

  useEffect(() => {
    const params = new URLSearchParams(typeof window !== "undefined" ? window.location.search : "");
    const tab = params.get("tab");
    if (tab === "boundary" || tab === "items" || tab === "schedule" || tab === "overview") {
      setActiveTab(tab);
    }
  }, [typeof window !== "undefined" ? window.location.search : ""]);

  const handleSaveMetadata = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!worksite) return;
    setErrorMessage(null);
    try {
      const res = await fetch(`/api/v1/worksites/${worksite.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          job_name: editName.trim(),
          customer_type: editCustomerType.trim() || null,
          renewal_reference: editRenewalRef.trim() || null,
          budget_amount: editBudget ? parseFloat(editBudget) : null,
          version: worksite.version,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to update worksite.");
      }

      setStatusMessage("Worksite updated successfully.");
      setIsEditingMetadata(false);
      fetchData();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to update worksite.");
    }
  };

  const handleSaveBoundary = async (polygon: GeoJSON.Polygon) => {
    if (!worksite) return;
    setSavingBoundary(true);
    setErrorMessage(null);
    try {
      const res = await fetch(`/api/v1/worksites/${worksite.id}/boundary`, {
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

      setStatusMessage("Boundary saved and validated successfully.");
      fetchData();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to save boundary.");
    } finally {
      setSavingBoundary(false);
    }
  };

  const handleGenerateOccurrences = async (itemId?: string) => {
    if (!worksite) return;
    setErrorMessage(null);
    try {
      if (itemId) {
        const res = await fetch(`/api/v1/job-items/${itemId}/generate-occurrences`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({}),
        });
        if (!res.ok) throw new Error("Failed to generate occurrences.");
      } else {
        // Generate for all active items
        const currentItems = worksite.items || worksite.job_items || [];
        for (const item of currentItems) {
          await fetch(`/api/v1/job-items/${item.id}/generate-occurrences`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            body: JSON.stringify({}),
          });
        }
      }
      setStatusMessage("Occurrences generated across rolling 13-month horizon.");
      fetchData();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to generate occurrences.");
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <RefreshCw className="h-6 w-6 animate-spin text-indigo-600" />
      </div>
    );
  }

  if (!worksite) {
    return (
      <div className="p-8 text-center">
        <p className="text-sm text-slate-500">Worksite not found.</p>
        <Link to="/worksites" className="mt-4 inline-block text-xs text-indigo-600 font-semibold">
          &larr; Back to Worksites
        </Link>
      </div>
    );
  }

  const itemsList = worksite.items || worksite.job_items || [];

  const initialCenter: [number, number] =
    worksite.rep_longitude && worksite.rep_latitude
      ? [Number(worksite.rep_longitude), Number(worksite.rep_latitude)]
      : [55.2708, 25.2048]; // Dubai default

  return (
    <div className="space-y-6">
      {/* Top Breadcrumb & Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-200 pb-4">
        <div>
          <Link
            to="/worksites"
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 transition-colors mb-2"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Worksites & Jobs</span>
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900 font-mono">
              {worksite.job_number}
            </h1>
            <span className="text-lg font-medium text-slate-600">{worksite.job_name}</span>
            <span
              className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                worksite.is_outdoor
                  ? "bg-amber-100 text-amber-800 border border-amber-200"
                  : "bg-blue-100 text-blue-800 border border-blue-200"
              }`}
            >
              {worksite.is_outdoor ? (
                <>
                  <Sun className="h-3 w-3" /> Outdoor Worksite
                </>
              ) : (
                <>
                  <Home className="h-3 w-3" /> Indoor / Water Feature
                </>
              )}
            </span>
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
                worksite.has_boundary
                  ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                  : "bg-red-50 text-red-700 border border-red-200"
              }`}
            >
              <MapPin className="h-3 w-3" />
              {worksite.has_boundary ? "Boundary Configured" : "Boundary Missing"}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setCopyModalMode("COPY_FROM")}
            className="px-3 py-1.5 border border-slate-300 rounded-lg text-xs font-medium text-slate-700 hover:bg-slate-50 flex items-center gap-1.5 shadow-xs"
          >
            <Copy className="h-3.5 w-3.5 text-slate-500" />
            Copy Boundary From...
          </button>
          <button
            onClick={() => setCopyModalMode("COPY_TO")}
            className="px-3 py-1.5 border border-slate-300 rounded-lg text-xs font-medium text-slate-700 hover:bg-slate-50 flex items-center gap-1.5 shadow-xs"
          >
            <Copy className="h-3.5 w-3.5 text-indigo-600" />
            Copy Boundary To...
          </button>
        </div>
      </div>

      {/* Notifications */}
      {statusMessage && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg flex items-center justify-between text-xs text-emerald-800">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
            <span>{statusMessage}</span>
          </div>
          <button onClick={() => setStatusMessage(null)}>
            <X className="h-3.5 w-3.5 text-emerald-600" />
          </button>
        </div>
      )}
      {errorMessage && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-center justify-between text-xs text-red-800">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-red-600 shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button onClick={() => setErrorMessage(null)}>
            <X className="h-3.5 w-3.5 text-red-600" />
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-slate-200 flex gap-6 text-sm font-medium">
        <button
          onClick={() => setActiveTab("overview")}
          className={`pb-3 border-b-2 flex items-center gap-2 transition-colors ${
            activeTab === "overview"
              ? "border-indigo-600 text-indigo-600 font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Building2 className="h-4 w-4" />
          Overview
        </button>
        <button
          onClick={() => setActiveTab("items")}
          className={`pb-3 border-b-2 flex items-center gap-2 transition-colors ${
            activeTab === "items"
              ? "border-indigo-600 text-indigo-600 font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Layers className="h-4 w-4" />
          Job Items ({itemsList.length})
        </button>
        <button
          onClick={() => setActiveTab("boundary")}
          className={`pb-3 border-b-2 flex items-center gap-2 transition-colors ${
            activeTab === "boundary"
              ? "border-indigo-600 text-indigo-600 font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <MapPin className="h-4 w-4" />
          Boundary & Area
        </button>
        <button
          onClick={() => setActiveTab("schedule")}
          className={`pb-3 border-b-2 flex items-center gap-2 transition-colors ${
            activeTab === "schedule"
              ? "border-indigo-600 text-indigo-600 font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Calendar className="h-4 w-4" />
          Occurrences & Schedule ({occurrences.length})
        </button>
      </div>

      {/* Tab 1: Overview */}
      {activeTab === "overview" && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-2 bg-white rounded-xl border border-slate-200 p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="font-bold text-slate-900 text-base">Worksite Information</h3>
              {user?.role === "ADMIN" && (
                <button
                  onClick={() => setIsEditingMetadata(!isEditingMetadata)}
                  className="px-2.5 py-1 text-xs border border-slate-200 rounded text-slate-700 hover:bg-slate-50 flex items-center gap-1.5"
                >
                  <Edit2 className="h-3 w-3" />
                  {isEditingMetadata ? "Cancel" : "Edit Metadata"}
                </button>
              )}
            </div>

            {isEditingMetadata ? (
              <form onSubmit={handleSaveMetadata} className="space-y-4 text-xs">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Job Name</label>
                  <input
                    type="text"
                    required
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded focus:ring-1 focus:ring-indigo-500"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Customer Type</label>
                    <input
                      type="text"
                      value={editCustomerType}
                      onChange={(e) => setEditCustomerType(e.target.value)}
                      className="w-full px-3 py-1.5 border border-slate-300 rounded focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">
                      Renewal Reference
                    </label>
                    <input
                      type="text"
                      value={editRenewalRef}
                      onChange={(e) => setEditRenewalRef(e.target.value)}
                      className="w-full px-3 py-1.5 border border-slate-300 rounded focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">
                    Manual Budget Amount (AED)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={editBudget}
                    onChange={(e) => setEditBudget(e.target.value)}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded focus:ring-1 focus:ring-indigo-500"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsEditingMetadata(false)}
                    className="px-3 py-1 border border-slate-300 rounded hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-3 py-1 bg-indigo-600 text-white rounded hover:bg-indigo-700 font-semibold"
                  >
                    Save Changes
                  </button>
                </div>
              </form>
            ) : (
              <div className="grid grid-cols-2 gap-4 text-xs">
                <div>
                  <span className="text-slate-400 block mb-0.5">Customer Group</span>
                  <span className="font-semibold text-slate-800">
                    {worksite.group_name || worksite.group_id}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block mb-0.5">Zone & Country</span>
                  <span className="font-semibold text-slate-800">
                    {worksite.zone_name || worksite.zone_id} ({worksite.country})
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block mb-0.5">Renewal Reference</span>
                  <span className="font-semibold text-slate-800">
                    {worksite.renewal_reference || "None"}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block mb-0.5">Customer Type</span>
                  <span className="font-semibold text-slate-800">
                    {worksite.customer_type || "Standard"}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block mb-0.5">Budget Amount</span>
                  <span className="font-semibold text-slate-800">
                    {worksite.budget_amount != null
                      ? `${Number(worksite.budget_amount).toLocaleString()} AED`
                      : "Not Specified"}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block mb-0.5">Record Version</span>
                  <span className="font-mono text-slate-600">v{worksite.version}</span>
                </div>
              </div>
            )}
          </div>

          {/* Quick Metrics */}
          <div className="space-y-4">
            <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-3">
              <span className="text-xs font-bold text-slate-600 uppercase tracking-wider block">
                Geographic Profile
              </span>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500">Polygon Area</span>
                  <span className="font-bold text-slate-800">
                    {worksite.boundary_area_sqm != null
                      ? `${Math.round(worksite.boundary_area_sqm).toLocaleString()} m² (${(
                          worksite.boundary_area_sqm / 10000
                        ).toFixed(2)} ha)`
                      : "No boundary"}
                  </span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-slate-100">
                  <span className="text-slate-500">Representative Point</span>
                  <span className="font-mono text-slate-700">
                    {worksite.rep_latitude && worksite.rep_longitude
                      ? `${Number(worksite.rep_latitude).toFixed(5)}, ${Number(
                          worksite.rep_longitude
                        ).toFixed(5)}`
                      : "Unset"}
                  </span>
                </div>
                <div className="flex justify-between items-center py-1">
                  <span className="text-slate-500">Total Scopes (Items)</span>
                  <span className="font-bold text-indigo-600">
                    {itemsList.length} items
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4 text-xs text-indigo-900 space-y-1">
              <span className="font-bold block">13-Month Horizon Scheduler</span>
              <p className="text-[11px] text-indigo-700 leading-relaxed">
                Occurrences are automatically generated when job items are modified or created. To
                re-sync all items idempotently:
              </p>
              <button
                onClick={() => handleGenerateOccurrences()}
                className="mt-2 w-full px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded font-semibold text-xs transition-colors flex items-center justify-center gap-1.5"
              >
                <Sparkles className="h-3.5 w-3.5" />
                Generate All Occurrences
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Job Items */}
      {activeTab === "items" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-500">
              Each job item specifies frequency, staff grade, required headcount, and shift hours.
            </span>
            {["ADMIN", "ENGINEER"].includes(user?.role || "") && (
              <button
                onClick={() => {
                  setEditingItem(null);
                  setIsItemModalOpen(true);
                }}
                className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-xs"
              >
                <Plus className="h-3.5 w-3.5" />
                Add Job Item
              </button>
            )}
          </div>

          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="px-4 py-3">Sub-Item</th>
                  <th className="px-4 py-3">Staff Grade (SGD)</th>
                  <th className="px-4 py-3">Frequency</th>
                  <th className="px-4 py-3 text-center">Staff Count</th>
                  <th className="px-4 py-3 text-right">Hours / Occ</th>
                  <th className="px-4 py-3">Deployment</th>
                  <th className="px-4 py-3 text-right">Break</th>
                  <th className="px-4 py-3 text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {itemsList.map((item: any) => (
                  <tr key={item.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-4 py-3 font-mono font-bold text-slate-900">
                      {item.sub_item_code}
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-medium text-slate-800">
                        {item.staff_grade_description}
                      </span>
                      {item.planned_grade_code && (
                        <span className="block text-[10px] text-slate-400">
                          {item.planned_grade_code}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-semibold text-slate-700">
                        {item.occurrences_per_period}x / {item.period_interval}{" "}
                        {item.frequency_unit.toLowerCase()}
                      </span>
                      {item.weekday_pattern && (
                        <span className="block text-[10px] text-slate-400">
                          Days: {item.weekday_pattern.join(", ")}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center font-bold text-slate-800">
                      {item.required_staff_count}
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-bold text-slate-800">
                      {Number(item.hours_per_occurrence_per_staff).toFixed(
                        item.hours_per_occurrence_per_staff % 1 === 0 ? 0 : 3
                      )}
                      h
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                          item.deployment_type === "PERMANENT"
                            ? "bg-purple-50 text-purple-700 border border-purple-200"
                            : "bg-blue-50 text-blue-700 border border-blue-200"
                        }`}
                      >
                        {item.deployment_type}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-slate-600">
                      {item.break_override_minutes != null
                        ? `${item.break_override_minutes}m`
                        : "Default"}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-1.5">
                        <button
                          onClick={() => setValidatingItemId(item.id)}
                          className="px-2 py-1 rounded border border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 font-semibold text-[11px] flex items-center gap-1"
                          title="View validation calculations"
                        >
                          <ShieldCheck className="h-3 w-3" />
                          Validation
                        </button>
                        {["ADMIN", "ENGINEER"].includes(user?.role || "") && (
                          <>
                            <button
                              onClick={() => {
                                setEditingItem(item);
                                setIsItemModalOpen(true);
                              }}
                              className="p-1 rounded text-slate-500 hover:text-slate-800 hover:bg-slate-100"
                              title="Edit item"
                            >
                              <Edit2 className="h-3.5 w-3.5" />
                            </button>
                            <button
                              onClick={() => handleGenerateOccurrences(item.id)}
                              className="p-1 rounded text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50"
                              title="Regenerate occurrences"
                            >
                              <RefreshCw className="h-3.5 w-3.5" />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {itemsList.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-slate-400">
                      No job items configured for this worksite.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 3: Boundary & Area */}
      {activeTab === "boundary" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500">
              Draw or edit geofence polygon for check-in detection. Vertices must not self-intersect.
            </span>
            <div className="flex items-center gap-3">
              <span className="font-semibold text-slate-700">
                Area:{" "}
                <span className="font-bold text-slate-900">
                  {worksite.boundary_area_sqm != null
                    ? `${Math.round(worksite.boundary_area_sqm).toLocaleString()} m²`
                    : "0 m²"}
                </span>
              </span>
            </div>
          </div>

          <div className="relative rounded-xl overflow-hidden border border-slate-200 bg-white">
            <MapContainer
              initialCenter={initialCenter}
              initialZoom={worksite.has_boundary ? 17 : 14}
              onMapReady={(map) => setMapInstance(map)}
              className="w-full h-[600px]"
            >
              <PlaceSearch map={mapInstance} />
            </MapContainer>

            <div className="p-4 bg-white border-t border-slate-200">
              <PolygonEditor
                map={mapInstance}
                initialPolygon={worksite.boundary_geojson}
                onSave={handleSaveBoundary}
                isSaving={savingBoundary}
              />
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: Schedule / Occurrences */}
      {activeTab === "schedule" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-500">
              Generated occurrence slots across 13 months for staff assignments (Phases 05+).
            </span>
            <button
              onClick={() => handleGenerateOccurrences()}
              className="px-3 py-1.5 bg-indigo-50 border border-indigo-200 text-indigo-700 hover:bg-indigo-100 rounded-lg text-xs font-semibold flex items-center gap-1.5"
            >
              <RefreshCw className="h-3 w-3" />
              Regenerate All Slots
            </button>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="px-4 py-3">Scope / Item</th>
                  <th className="px-4 py-3">Slot #</th>
                  <th className="px-4 py-3">Window Start</th>
                  <th className="px-4 py-3">Window End</th>
                  <th className="px-4 py-3">Due Date</th>
                  <th className="px-4 py-3 text-center">Staff Needed</th>
                  <th className="px-4 py-3 text-right">Hours</th>
                  <th className="px-4 py-3 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {occurrences.map((occ) => (
                  <tr key={occ.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-4 py-3 font-medium text-slate-900">
                      {occ.sub_item_code ? (
                        <>
                          <span className="font-mono font-bold">{occ.sub_item_code}</span>{" "}
                          <span className="text-slate-500">({occ.staff_grade_description})</span>
                        </>
                      ) : (
                        "Scope Item"
                      )}
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-600">#{occ.slot_index}</td>
                    <td className="px-4 py-3 font-mono text-slate-700">{occ.window_start}</td>
                    <td className="px-4 py-3 font-mono text-slate-700">{occ.window_end}</td>
                    <td className="px-4 py-3 font-mono font-bold text-slate-900">{occ.due_date}</td>
                    <td className="px-4 py-3 text-center font-bold text-slate-800">
                      {occ.required_staff_count}
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-bold text-slate-800">
                      {Number(occ.required_hours_per_staff).toFixed(
                        occ.required_hours_per_staff % 1 === 0 ? 0 : 3
                      )}
                      h
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          occ.status === "SCHEDULED"
                            ? "bg-slate-100 text-slate-700"
                            : occ.status === "COMPLETED"
                            ? "bg-emerald-100 text-emerald-800"
                            : occ.status === "IN_PROGRESS"
                            ? "bg-amber-100 text-amber-800"
                            : "bg-red-100 text-red-800"
                        }`}
                      >
                        {occ.status}
                      </span>
                    </td>
                  </tr>
                ))}
                {occurrences.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-slate-400">
                      No occurrences found. Click "Generate All Occurrences" to schedule slots.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Job Item Modal */}
      <JobItemModal
        isOpen={isItemModalOpen}
        onClose={() => {
          setIsItemModalOpen(false);
          setEditingItem(null);
        }}
        worksiteId={worksite.id}
        initialData={editingItem}
        onSuccess={() => {
          setStatusMessage("Job item saved and occurrences updated.");
          fetchData();
        }}
      />

      {/* Validation Panel Modal */}
      <JobItemValidationModal
        isOpen={validatingItemId !== null}
        onClose={() => setValidatingItemId(null)}
        jobItemId={validatingItemId}
        worksiteJobNumber={worksite.job_number}
      />

      {/* Copy Boundary Modal */}
      {copyModalMode && (
        <CopyBoundaryModal
          isOpen={true}
          onClose={() => setCopyModalMode(null)}
          worksiteId={worksite.id}
          worksiteJobNumber={worksite.job_number}
          mode={copyModalMode}
          onSuccess={() => {
            setStatusMessage("Boundary copied successfully.");
            setCopyModalMode(null);
            fetchData();
          }}
        />
      )}
    </div>
  );
};
