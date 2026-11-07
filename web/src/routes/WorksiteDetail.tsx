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
  Clock,
  Users,
  ChevronLeft,
  ChevronRight,
  CalendarDays,
  List,
  Info,
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
  start_date: string | null;
  end_date: string | null;
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
  planned_grade_code: string | null;
  window_start: string;
  window_end: string;
  due_date: string | null;
  slot_index: number;
  required_staff_count: number;
  required_hours_per_staff: number;
  status: string;
  needs_review?: boolean;
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

  // Occurrences View and Filter States
  const [occViewMode, setOccViewMode] = useState<"calendar" | "table">("calendar");
  const [occGradeFilter, setOccGradeFilter] = useState<string>("");
  const [occMonthFilter, setOccMonthFilter] = useState<string>("");
  const [occStatusFilter, setOccStatusFilter] = useState<string>("");
  const [calendarMonth, setCalendarMonth] = useState<string>(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  });

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
  const [editStartDate, setEditStartDate] = useState("");
  const [editEndDate, setEditEndDate] = useState("");

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
      setEditStartDate(data.start_date || "");
      setEditEndDate(data.end_date || "");

      // Fetch occurrences
      const occRes = await fetch(`/api/v1/occurrences?worksite_id=${worksiteId}&limit=500`, { headers });
      if (occRes.ok) {
        const rawOccs = await occRes.json();
        const items = data.items || data.job_items || [];
        const itemsMap = new Map(items.map((i: any) => [i.id, i]));
        const enriched: Occurrence[] = rawOccs.map((occ: any) => {
          const parent = itemsMap.get(occ.job_item_id);
          return {
            ...occ,
            sub_item_code: occ.sub_item_code || parent?.sub_item_code || null,
            staff_grade_description:
              occ.staff_grade_description || parent?.staff_grade_description || null,
            planned_grade_code:
              occ.planned_grade_code || parent?.planned_grade_code || null,
          };
        });
        setOccurrences(enriched);
        if (enriched.length > 0) {
          const firstMonth = (enriched[0].due_date || enriched[0].window_start).substring(0, 7);
          setCalendarMonth((prev) => {
            const hasPrev = enriched.some((o) => (o.due_date || o.window_start).startsWith(prev));
            return hasPrev ? prev : firstMonth;
          });
        }
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
          start_date: editStartDate.trim() || null,
          end_date: editEndDate.trim() || null,
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
                    <label className="block font-semibold text-slate-700 mb-1">Contract Start Date</label>
                    <input
                      type="date"
                      value={editStartDate}
                      onChange={(e) => setEditStartDate(e.target.value)}
                      className="w-full px-3 py-1.5 border border-slate-300 rounded focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Contract End Date</label>
                    <input
                      type="date"
                      value={editEndDate}
                      onChange={(e) => setEditEndDate(e.target.value)}
                      className="w-full px-3 py-1.5 border border-slate-300 rounded focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>
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
                    Annual Operating Budget (AED / year)
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
                  <span className="text-slate-400 block mb-0.5">Contract Validity Period</span>
                  <span className="font-semibold text-slate-800">
                    {worksite.start_date || "Start N/A"} – {worksite.end_date || "Ongoing"}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block mb-0.5">Annual Operating Budget</span>
                  <span className="font-semibold text-slate-800">
                    {worksite.budget_amount != null
                      ? `${Number(worksite.budget_amount).toLocaleString()} AED / year`
                      : "Not Specified"}
                  </span>
                </div>
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
                  <span className="text-slate-400 block mb-0.5">Deployment Type</span>
                  <span className="font-semibold text-slate-800">
                    {worksite.is_outdoor ? "Outdoor Maintenance" : "Indoor / Facilities"}
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
              onMapUnmount={() => setMapInstance(null)}
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
      {activeTab === "schedule" && (() => {
        const totalOccurrences = occurrences.length;
        const totalPlannedHours = occurrences.reduce(
          (sum, o) => sum + Number(o.required_staff_count) * Number(o.required_hours_per_staff),
          0
        );
        const distinctRoles = Array.from(
          new Set(occurrences.map((o) => o.staff_grade_description).filter(Boolean))
        ) as string[];

        const distinctMonths = Array.from(
          new Set(occurrences.map((o) => (o.due_date || o.window_start).substring(0, 7)))
        ).sort();

        const minDate = occurrences.length > 0 ? occurrences[0].window_start : "—";
        const maxDate = occurrences.length > 0 ? occurrences[occurrences.length - 1].window_end : "—";

        const getRoleBadgeStyle = (role: string | null) => {
          const r = (role || "").toUpperCase();
          if (r.includes("GARDEN")) return "bg-emerald-50 text-emerald-800 border-emerald-200";
          if (r.includes("IRRIGAT")) return "bg-sky-50 text-sky-800 border-sky-200";
          if (r.includes("FOREMAN") || r.includes("SUPERVIS"))
            return "bg-purple-50 text-purple-800 border-purple-200";
          if (r.includes("DRIVER")) return "bg-amber-50 text-amber-800 border-amber-200";
          if (r.includes("CLEAN")) return "bg-teal-50 text-teal-800 border-teal-200";
          return "bg-indigo-50 text-indigo-800 border-indigo-200";
        };

        const formatShortDate = (dateStr: string | null) => {
          if (!dateStr) return "Flexible Window";
          const [y, m, d] = dateStr.split("-").map(Number);
          const dt = new Date(y, m - 1, d);
          return dt.toLocaleDateString("en-US", { weekday: "short", day: "2-digit", month: "short", year: "numeric" });
        };

        const formatMonthTitle = (monthStr: string) => {
          if (!monthStr || !monthStr.includes("-")) return monthStr;
          const [y, m] = monthStr.split("-").map(Number);
          const dt = new Date(y, m - 1, 1);
          return dt.toLocaleDateString("en-US", { month: "long", year: "numeric" });
        };

        const handlePrevMonth = () => {
          const [y, m] = calendarMonth.split("-").map(Number);
          const prev = new Date(y, m - 2, 1);
          setCalendarMonth(`${prev.getFullYear()}-${String(prev.getMonth() + 1).padStart(2, "0")}`);
        };

        const handleNextMonth = () => {
          const [y, m] = calendarMonth.split("-").map(Number);
          const next = new Date(y, m, 1);
          setCalendarMonth(`${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}`);
        };

        const handleCurrentMonth = () => {
          const d = new Date();
          setCalendarMonth(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`);
        };

        // Filtered occurrences for Calendar View (scoped to calendarMonth)
        const calendarOccurrences = occurrences.filter((o) => {
          const dStr = o.due_date || o.window_start;
          if (!dStr.startsWith(calendarMonth)) return false;
          if (occGradeFilter && o.staff_grade_description !== occGradeFilter) return false;
          if (occStatusFilter && o.status !== occStatusFilter) return false;
          return true;
        });

        // Group calendar occurrences by week window_start
        const calendarWeeksMap = new Map<string, { windowStart: string; windowEnd: string; items: Occurrence[] }>();
        for (const occ of calendarOccurrences) {
          const key = occ.window_start;
          if (!calendarWeeksMap.has(key)) {
            calendarWeeksMap.set(key, { windowStart: occ.window_start, windowEnd: occ.window_end, items: [] });
          }
          calendarWeeksMap.get(key)!.items.push(occ);
        }
        const calendarWeeks = Array.from(calendarWeeksMap.values()).sort((a, b) =>
          a.windowStart.localeCompare(b.windowStart)
        );

        // Filtered occurrences for Table View
        const tableOccurrences = occurrences.filter((o) => {
          const dStr = o.due_date || o.window_start;
          if (occMonthFilter && !dStr.startsWith(occMonthFilter)) return false;
          if (occGradeFilter && o.staff_grade_description !== occGradeFilter) return false;
          if (occStatusFilter && o.status !== occStatusFilter) return false;
          return true;
        });

        return (
          <div className="space-y-5">
            {/* Contextual Info Banner */}
            <div className="bg-indigo-50/70 border border-indigo-200/80 rounded-xl p-4 text-xs text-indigo-950 flex flex-col md:flex-row md:items-center justify-between gap-3 shadow-xs">
              <div className="flex items-start gap-3">
                <Info className="h-5 w-5 text-indigo-600 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <div className="font-bold text-sm text-indigo-900">
                    Operational Shift Schedule & Rolling Horizon (13 Months)
                  </div>
                  <p className="text-slate-600 leading-relaxed max-w-3xl">
                    Every contracted job item produces scheduled calendar slots across rolling calendar windows.
                    Each slot defines the <strong>exact staff role</strong>, <strong>crew count</strong>, and <strong>shift hours</strong>.
                    In <strong>Phase 05+</strong>, supervisors roster field workers to these slots, and daily mobile GPS geofence check-ins confirm attendance.
                  </p>
                </div>
              </div>
              <button
                onClick={() => handleGenerateOccurrences()}
                className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold flex items-center gap-2 shadow-xs shrink-0 self-start md:self-auto transition"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Regenerate All Slots
              </button>
            </div>

            {/* KPI Metric Summary Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs">
                <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block">
                  Total Planned Visits
                </span>
                <div className="flex items-baseline gap-1.5 mt-1">
                  <span className="text-2xl font-bold font-mono text-slate-900">{totalOccurrences}</span>
                  <span className="text-xs text-slate-400">slots</span>
                </div>
              </div>

              <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs">
                <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block">
                  Contracted Effort
                </span>
                <div className="flex items-baseline gap-1.5 mt-1">
                  <span className="text-2xl font-bold font-mono text-slate-900">
                    {Math.round(totalPlannedHours).toLocaleString()}
                  </span>
                  <span className="text-xs text-slate-400">man-hours</span>
                </div>
              </div>

              <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs">
                <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block">
                  Contracted Roles
                </span>
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {distinctRoles.length === 0 ? (
                    <span className="text-xs text-slate-400">None</span>
                  ) : (
                    distinctRoles.map((role) => (
                      <span
                        key={role}
                        className={`px-2 py-0.5 rounded text-[10px] font-bold border ${getRoleBadgeStyle(role)}`}
                      >
                        {role}
                      </span>
                    ))
                  )}
                </div>
              </div>

              <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs">
                <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block">
                  Planning Horizon
                </span>
                <div className="mt-1 text-xs font-mono text-slate-700">
                  <div className="font-semibold text-slate-900">{minDate}</div>
                  <div className="text-slate-400 text-[10px]">to {maxDate}</div>
                </div>
              </div>
            </div>

            {/* Filter and View Mode Switcher */}
            <div className="flex flex-wrap items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200 shadow-xs">
              <div className="flex items-center gap-2">
                <div className="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200">
                  <button
                    onClick={() => setOccViewMode("calendar")}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition ${
                      occViewMode === "calendar"
                        ? "bg-white text-indigo-700 shadow-xs"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    <CalendarDays className="h-3.5 w-3.5" />
                    Calendar & Timeline
                  </button>
                  <button
                    onClick={() => setOccViewMode("table")}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition ${
                      occViewMode === "table"
                        ? "bg-white text-indigo-700 shadow-xs"
                        : "text-slate-600 hover:text-slate-900"
                    }`}
                  >
                    <List className="h-3.5 w-3.5" />
                    Structured List
                  </button>
                </div>

                <div className="h-5 w-px bg-slate-200 mx-1" />

                {/* Role filter */}
                <select
                  value={occGradeFilter}
                  onChange={(e) => setOccGradeFilter(e.target.value)}
                  className="px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg bg-white text-slate-700 font-medium focus:outline-none focus:ring-1 focus:ring-indigo-500"
                >
                  <option value="">All Staff Roles ({distinctRoles.length})</option>
                  {distinctRoles.map((role) => (
                    <option key={role} value={role}>
                      {role}
                    </option>
                  ))}
                </select>

                {/* Status filter */}
                <select
                  value={occStatusFilter}
                  onChange={(e) => setOccStatusFilter(e.target.value)}
                  className="px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg bg-white text-slate-700 font-medium focus:outline-none focus:ring-1 focus:ring-indigo-500"
                >
                  <option value="">All Statuses</option>
                  <option value="GENERATED">Generated (Unassigned)</option>
                  <option value="ASSIGNED">Assigned</option>
                  <option value="COMPLETED">Completed</option>
                  <option value="CANCELLED">Cancelled</option>
                </select>

                {/* Table mode month filter */}
                {occViewMode === "table" && (
                  <select
                    value={occMonthFilter}
                    onChange={(e) => setOccMonthFilter(e.target.value)}
                    className="px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg bg-white text-slate-700 font-medium focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  >
                    <option value="">All Months ({distinctMonths.length})</option>
                    {distinctMonths.map((m) => (
                      <option key={m} value={m}>
                        {formatMonthTitle(m)}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div className="text-xs text-slate-500">
                Showing{" "}
                <strong className="text-slate-900 font-mono">
                  {occViewMode === "calendar" ? calendarOccurrences.length : tableOccurrences.length}
                </strong>{" "}
                of <span className="font-mono">{totalOccurrences}</span> slots
              </div>
            </div>

            {/* VIEW 1: Calendar & Timeline View */}
            {occViewMode === "calendar" && (
              <div className="space-y-4">
                {/* Month Navigator Header */}
                <div className="flex items-center justify-between bg-white px-4 py-3 rounded-xl border border-slate-200 shadow-xs">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handlePrevMonth}
                      className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-600 transition"
                      title="Previous Month"
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </button>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-slate-900">
                        {formatMonthTitle(calendarMonth)}
                      </span>
                      <select
                        value={calendarMonth}
                        onChange={(e) => setCalendarMonth(e.target.value)}
                        className="text-xs border border-slate-200 rounded px-2 py-0.5 bg-slate-50 text-slate-700 font-medium"
                      >
                        {distinctMonths.map((m) => (
                          <option key={m} value={m}>
                            {formatMonthTitle(m)}
                          </option>
                        ))}
                      </select>
                    </div>
                    <button
                      onClick={handleNextMonth}
                      className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-600 transition"
                      title="Next Month"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </button>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleCurrentMonth}
                      className="px-2.5 py-1 text-xs border border-slate-200 hover:bg-slate-50 rounded-md font-medium text-slate-700 transition"
                    >
                      This Month
                    </button>
                    <span className="text-xs text-slate-500">
                      <strong>{calendarOccurrences.length}</strong> shifts scheduled
                    </span>
                  </div>
                </div>

                {calendarWeeks.length === 0 ? (
                  <div className="p-12 text-center bg-white border border-slate-200 rounded-xl space-y-2">
                    <CalendarDays className="h-8 w-8 text-slate-300 mx-auto" />
                    <div className="text-sm font-semibold text-slate-700">
                      No visits scheduled in {formatMonthTitle(calendarMonth)}
                    </div>
                    <p className="text-xs text-slate-400">
                      Try selecting another month or clearing role/status filters.
                    </p>
                  </div>
                ) : (
                  calendarWeeks.map((week, idx) => {
                    const weekHours = week.items.reduce(
                      (acc, i) => acc + Number(i.required_staff_count) * Number(i.required_hours_per_staff),
                      0
                    );

                    return (
                      <div
                        key={week.windowStart}
                        className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-xs space-y-3 p-4"
                      >
                        {/* Week Header */}
                        <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
                          <div className="flex items-center gap-2">
                            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-slate-100 text-slate-700 font-mono">
                              Week {idx + 1}
                            </span>
                            <span className="text-xs font-semibold text-slate-900">
                              {formatShortDate(week.windowStart)} – {formatShortDate(week.windowEnd)}
                            </span>
                          </div>
                          <div className="flex items-center gap-3 text-xs text-slate-500">
                            <span>
                              <strong className="text-slate-800">{week.items.length}</strong> visits
                            </span>
                            <span>•</span>
                            <span>
                              <strong className="text-slate-800">{weekHours.toFixed(0)}</strong> man-hours
                            </span>
                          </div>
                        </div>

                        {/* Shift Cards Grid */}
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                          {week.items.map((occ) => {
                            const totalEffort =
                              Number(occ.required_staff_count) * Number(occ.required_hours_per_staff);

                            return (
                              <div
                                key={occ.id}
                                className="border border-slate-200/90 hover:border-indigo-300 rounded-xl p-3.5 bg-slate-50/50 hover:bg-white transition space-y-2.5 shadow-2xs"
                              >
                                {/* Top Row: Due Date & Visit # */}
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-1.5 text-xs font-bold text-slate-900">
                                    <Calendar className="h-3.5 w-3.5 text-indigo-600" />
                                    <span>{formatShortDate(occ.due_date)}</span>
                                  </div>
                                  <span className="font-mono text-[10px] font-bold px-2 py-0.5 bg-white border border-slate-200 rounded text-slate-700 shadow-2xs">
                                    Visit #{occ.slot_index + 1}
                                  </span>
                                </div>

                                {/* Middle Row: Role & Grade Code */}
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-1.5">
                                    <span
                                      className={`px-2 py-0.5 rounded text-xs font-bold border ${getRoleBadgeStyle(
                                        occ.staff_grade_description
                                      )}`}
                                    >
                                      {occ.staff_grade_description || "STAFF"}
                                    </span>
                                    {occ.planned_grade_code && (
                                      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-200/80 text-slate-700 font-semibold">
                                        {occ.planned_grade_code}
                                      </span>
                                    )}
                                  </div>
                                  <span className="text-[11px] font-mono text-slate-400">
                                    Scope: {occ.sub_item_code || "01"}
                                  </span>
                                </div>

                                {/* Staffing & Hours Details */}
                                <div className="bg-white border border-slate-100 rounded-lg p-2 text-xs grid grid-cols-2 gap-2 text-slate-700">
                                  <div className="flex items-center gap-1.5">
                                    <Users className="h-3.5 w-3.5 text-slate-400" />
                                    <span>
                                      <strong>{occ.required_staff_count}</strong> worker
                                      {occ.required_staff_count > 1 ? "s" : ""}
                                    </span>
                                  </div>
                                  <div className="flex items-center gap-1.5 text-right justify-end">
                                    <Clock className="h-3.5 w-3.5 text-slate-400" />
                                    <span>
                                      <strong>{Number(occ.required_hours_per_staff).toFixed(1)}h</strong> (
                                      {totalEffort.toFixed(1)}h total)
                                    </span>
                                  </div>
                                </div>

                                {/* Bottom Row: Status & Phase 05 note */}
                                <div className="flex items-center justify-between pt-1 border-t border-slate-100 text-[11px]">
                                  <span className="text-slate-400 font-mono text-[10px]">
                                    {occ.window_start} ~ {occ.window_end}
                                  </span>
                                  <span
                                    className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                      occ.status === "GENERATED"
                                        ? "bg-indigo-50 text-indigo-700 border border-indigo-200"
                                        : occ.status === "ASSIGNED"
                                        ? "bg-amber-50 text-amber-700 border border-amber-200"
                                        : occ.status === "COMPLETED"
                                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                        : "bg-red-50 text-red-700"
                                    }`}
                                  >
                                    {occ.status === "GENERATED" ? "Generated (Phase 05)" : occ.status}
                                  </span>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            )}

            {/* VIEW 2: Structured Table View */}
            {occViewMode === "table" && (
              <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-xs">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider text-[11px]">
                    <tr>
                      <th className="px-4 py-3">Contract Item & Role</th>
                      <th className="px-4 py-3">Scheduled Due Date</th>
                      <th className="px-4 py-3">Service Window</th>
                      <th className="px-4 py-3">Visit Sequence</th>
                      <th className="px-4 py-3 text-center">Staff Needed</th>
                      <th className="px-4 py-3 text-right">Hours / Staff</th>
                      <th className="px-4 py-3 text-right">Total Effort</th>
                      <th className="px-4 py-3 text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {tableOccurrences.map((occ) => {
                      const totalEffort =
                        Number(occ.required_staff_count) * Number(occ.required_hours_per_staff);

                      return (
                        <tr key={occ.id} className="hover:bg-slate-50/80 transition-colors">
                          <td className="px-4 py-3 font-medium text-slate-900">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-xs font-bold text-slate-700">
                                {occ.sub_item_code || "01"}
                              </span>
                              <span
                                className={`px-2 py-0.5 rounded text-[11px] font-bold border ${getRoleBadgeStyle(
                                  occ.staff_grade_description
                                )}`}
                              >
                                {occ.staff_grade_description || "STAFF"}
                              </span>
                              {occ.planned_grade_code && (
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-slate-100 text-slate-600">
                                  {occ.planned_grade_code}
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-4 py-3 font-medium text-slate-900">
                            <span className="font-bold text-indigo-900">
                              {formatShortDate(occ.due_date)}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-mono text-slate-500">
                            {occ.window_start} → {occ.window_end}
                          </td>
                          <td className="px-4 py-3 font-mono font-semibold text-slate-700">
                            Visit #{occ.slot_index + 1}
                          </td>
                          <td className="px-4 py-3 text-center font-bold text-slate-800">
                            {occ.required_staff_count} worker
                            {occ.required_staff_count > 1 ? "s" : ""}
                          </td>
                          <td className="px-4 py-3 text-right font-mono font-bold text-slate-800">
                            {Number(occ.required_hours_per_staff).toFixed(1)}h
                          </td>
                          <td className="px-4 py-3 text-right font-mono font-bold text-indigo-700">
                            {totalEffort.toFixed(1)}h
                          </td>
                          <td className="px-4 py-3 text-center">
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                occ.status === "GENERATED"
                                  ? "bg-indigo-50 text-indigo-700 border border-indigo-200"
                                  : occ.status === "ASSIGNED"
                                  ? "bg-amber-100 text-amber-800"
                                  : occ.status === "COMPLETED"
                                  ? "bg-emerald-100 text-emerald-800"
                                  : "bg-red-100 text-red-800"
                              }`}
                            >
                              {occ.status === "GENERATED" ? "Generated (Phase 05)" : occ.status}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                    {tableOccurrences.length === 0 && (
                      <tr>
                        <td colSpan={8} className="px-4 py-12 text-center text-slate-400">
                          No occurrences found matching your filters.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })()}

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
