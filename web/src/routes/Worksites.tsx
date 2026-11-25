import React, { useState, useEffect } from "react";
import { RENEWAL_HINT, RENEWAL_LABEL } from "../components/worksites/RenewalLabel";
import { currencyForCountry, formatMoney } from "../features/format/money";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
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
  Download,
  Upload,
  ArrowUpDown,
  Edit2,
  PowerOff,
} from "lucide-react";
import { MapContainer, PolygonEditor, PlaceSearch } from "../features/map";
import { Map as MapLibreMap } from "maplibre-gl";
import SupervisorProposalsModal from "../components/jobs/SupervisorProposalsModal";
import { AddWorksiteWizard } from "../components/worksites/AddWorksiteWizard";
import { ensureOk, Modal, useDialogs, useToast } from "../ui";

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
  salary_revision_code: string | null;
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
  is_active?: boolean;
}

interface Zone {
  id: string;
  code: string;
  name: string;
  is_active?: boolean;
}

export const Worksites: React.FC = () => {
  const toast = useToast();
  const dialogs = useDialogs();
  const navigate = useNavigate();
  const { token, user } = useAuth();
  // The menu item "Accommodations" opens this page with ?tab=accommodations.
  const tabParam = useRouterState({ select: (st) => (st.location.search as { tab?: string }).tab });
  const [activeTab, setActiveTab] = useState<"worksites" | "accommodations">(
    tabParam === "accommodations" ? "accommodations" : "worksites",
  );
  useEffect(() => {
    setActiveTab(tabParam === "accommodations" ? "accommodations" : "worksites");
  }, [tabParam]);
  const [worksites, setWorksites] = useState<Worksite[]>([]);
  const [accommodations, setAccommodations] = useState<AccommodationItem[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [loading, setLoading] = useState(true);

  // Accommodation boundary modal
  const [drawingAccommodation, setDrawingAccommodation] = useState<AccommodationItem | null>(null);
  const [mapInstance, setMapInstance] = useState<MapLibreMap | null>(null);
  const [savingAccommodationBoundary, setSavingAccommodationBoundary] = useState(false);

  // Edit Accommodation modal state
  const [editingAccommodation, setEditingAccommodation] = useState<AccommodationItem | null>(null);
  const [editAccName, setEditAccName] = useState("");
  const [editAccAddress, setEditAccAddress] = useState("");
  const [savingAcc, setSavingAcc] = useState(false);

  // Filters & Sorting
  const [search, setSearch] = useState("");
  const [groupFilter, setGroupFilter] = useState("");
  const [zoneFilter, setZoneFilter] = useState("");
  const [countryFilter, setCountryFilter] = useState("");
  const [revisionFilter, setRevisionFilter] = useState("");
  const [revisions, setRevisions] = useState<{ code: string; name: string; country: string }[]>([]);
  const [boundaryFilter, setBoundaryFilter] = useState<string>("SET");
  const [statusFilter, setStatusFilter] = useState<"active" | "inactive" | "all">("active");
  // DEC-57 (Admin): worksites with no active supervisor, and the "assign from crews" review.
  const [unassignedOnly, setUnassignedOnly] = useState(false);
  const [showProposals, setShowProposals] = useState(false);
  const [sortBy, setSortBy] = useState<"job_number" | "name">("job_number");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");

  // Create Modal
  const [modalOpen, setModalOpen] = useState(false);
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await fetch("/api/v1/worksites/export", {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("Failed to export worksites");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `worksites_export_${new Date().toISOString().slice(0, 10)}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      toast.error(err, "Export failed");
    } finally {
      setExporting(false);
    }
  };

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
      if (user?.role === "ADMIN" && unassignedOnly) params.set("unassigned", "true");

      const accParams = new URLSearchParams();
      if (user?.role === "ADMIN") {
        if (statusFilter === "active") {
          params.set("is_active", "true");
          accParams.set("is_active", "true");
        } else if (statusFilter === "inactive") {
          params.set("is_active", "false");
          accParams.set("is_active", "false");
        }
      } else {
        params.set("is_active", "true");
        accParams.set("is_active", "true");
      }

      const accQs = accParams.toString() ? `?${accParams.toString()}` : "";
      const [wsRes, gRes, zRes, accRes, revRes] = await Promise.all([
        fetch(`/api/v1/worksites?${params.toString()}`, { headers }),
        fetch("/api/v1/groups", { headers }),
        fetch("/api/v1/zones", { headers }),
        fetch(`/api/v1/accommodations${accQs}`, { headers }),
        fetch("/api/v1/salary-revisions", { headers }),
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
      if (revRes && revRes.ok) {
        setRevisions(await revRes.json());
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [search, groupFilter, zoneFilter, countryFilter, boundaryFilter, statusFilter, unassignedOnly]);

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

      await ensureOk(res, "Failed to save boundary.");

      setDrawingAccommodation(null);
      fetchData();
    } catch (err: any) {
      toast.error(err, "Failed to save accommodation boundary");
    } finally {
      setSavingAccommodationBoundary(false);
    }
  };

  const handleSaveAccommodation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingAccommodation) return;
    setSavingAcc(true);
    try {
      const res = await fetch(`/api/v1/accommodations/${editingAccommodation.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({
          name: editAccName.trim(),
          address: editAccAddress.trim() || null,
          version: editingAccommodation.version,
        }),
      });
      await ensureOk(res, "Failed to update accommodation");
      setEditingAccommodation(null);
      fetchData();
    } catch (err: any) {
      toast.error(err, "Failed to update accommodation");
    } finally {
      setSavingAcc(false);
    }
  };

  const handleToggleAccommodationActive = async (acc: AccommodationItem) => {
    const action = acc.is_active ? "deactivate" : "reactivate";
    if (!(await dialogs.confirm({ title: "Change accommodation status?", message: `Are you sure you want to ${action} accommodation '${acc.name}' (${acc.accommodation_code})?`, confirmLabel: "Confirm" }))) return;
    try {
      const res = await fetch(`/api/v1/accommodations/${acc.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({
          is_active: !acc.is_active,
          version: acc.version,
        }),
      });
      await ensureOk(res, `Failed to ${action} accommodation`);
      fetchData();
    } catch (err: any) {
      toast.error(err, `Failed to ${action} accommodation`);
    }
  };

  const isAdminOrEngineer = user?.role === "ADMIN" || user?.role === "ENGINEER";
  const isAdmin = user?.role === "ADMIN";

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

  const filteredWorksites = worksites.filter((ws) => {
    if (revisionFilter) {
      if (revisionFilter === "UNASSIGNED") {
        if (ws.salary_revision_code) return false;
      } else if (ws.salary_revision_code !== revisionFilter) {
        return false;
      }
    }
    return true;
  });

  const sortedAndFilteredWorksites = [...filteredWorksites].sort((a, b) => {
    let cmp = 0;
    if (sortBy === "job_number") {
      cmp = a.job_number.localeCompare(b.job_number, undefined, { numeric: true });
    } else {
      cmp = a.job_name.localeCompare(b.job_name, undefined, { numeric: true });
    }
    return sortOrder === "asc" ? cmp : -cmp;
  });

  return (
    <div className="w-full max-w-7xl mx-auto space-y-6">
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

        <div className="flex flex-wrap items-center gap-3 [&>button]:whitespace-nowrap">
          {user?.role === "ADMIN" && (
            <button
              onClick={() => setShowProposals(true)}
              className="flex items-center gap-1.5 px-3 py-2 border border-indigo-200 bg-indigo-50 text-indigo-700 rounded-md text-sm font-medium hover:bg-indigo-100 transition shadow-xs"
              title="Suggest worksite supervisors from current crews, review, then confirm"
            >
              Assign supervisors from crews
            </button>
          )}
          {isAdminOrEngineer && (
            <>
              <button
                onClick={handleExport}
                disabled={exporting}
                className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 bg-white text-slate-700 rounded-md text-sm font-medium hover:bg-slate-50 transition shadow-xs disabled:opacity-50"
                title="Export Worksites to Excel"
              >
                <Download className="h-4 w-4 text-slate-500" />
                {exporting ? "Exporting..." : "Export"}
              </button>

              {isAdmin && (
                <Link
                  to="/imports"
                  className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 bg-white text-slate-700 rounded-md text-sm font-medium hover:bg-slate-50 transition shadow-xs"
                  title="Import Worksites from Excel (Admin)"
                >
                  <Upload className="h-4 w-4 text-slate-500" />
                  Import
                </Link>
              )}
            </>
          )}

          <Link
            to="/boundaries"
            className="flex items-center gap-2 px-3.5 py-2 rounded-md bg-amber-50 hover:bg-amber-100 border border-amber-200 text-amber-900 text-sm font-medium transition"
          >
            <AlertTriangle className="h-4 w-4 text-amber-600" />
            Boundary Setup Queue
          </Link>

          {isAdmin && (
            <button
              onClick={() => setModalOpen(true)}
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
          onClick={() => navigate({ to: "/worksites", search: {} as never })}
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
          onClick={() => navigate({ to: "/worksites", search: { tab: "accommodations" } as never })}
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
          <div className="relative flex-1 min-w-[12rem] max-w-xs">
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

          {user?.role === "ADMIN" && (
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as "active" | "inactive" | "all")}
              className="text-sm border border-slate-300 rounded-md py-1.5 px-3 focus:outline-none focus:ring-1 focus:ring-indigo-500 bg-white font-medium text-slate-700"
              title="Admin Only: Filter active or deactivated records"
            >
              <option value="active">Status: Active</option>
              <option value="inactive">Status: Deactivated</option>
              <option value="all">Status: All</option>
            </select>
          )}

          {user?.role === "ADMIN" && activeTab === "worksites" && (
            <label
              className="flex items-center gap-1.5 text-sm text-slate-700 border border-slate-300 rounded-md py-1.5 px-3 bg-white cursor-pointer"
              title="Admin only: worksites with no active supervisor. Non-admins cannot see these (DEC-57)."
            >
              <input
                type="checkbox"
                checked={unassignedOnly}
                onChange={(e) => setUnassignedOnly(e.target.checked)}
              />
              Unassigned only
            </label>
          )}

          {activeTab === "worksites" && (
            <>
              <select
                value={countryFilter}
                onChange={(e) => setCountryFilter(e.target.value)}
                className="text-sm border border-slate-300 rounded-md py-1.5 px-3 focus:outline-none focus:ring-1 focus:ring-indigo-500 bg-white"
              >
                <option value="">All Countries</option>
                <option value="AE">UAE (AE)</option>
                <option value="SA">KSA (SA)</option>
              </select>

              <select
                value={revisionFilter}
                onChange={(e) => setRevisionFilter(e.target.value)}
                className="max-w-full text-sm border border-slate-300 rounded-md py-1.5 px-3 focus:outline-none focus:ring-1 focus:ring-indigo-500 bg-white"
              >
                <option value="">All Revisions</option>
                <option value="UNASSIGNED">Unassigned (Default)</option>
                {revisions.map((r) => (
                  <option key={r.code} value={r.code}>
                    {r.code} - {r.name}
                  </option>
                ))}
              </select>

              <div className="flex items-center gap-1.5 border border-slate-300 rounded-md px-2.5 py-1 bg-white">
                <ArrowUpDown className="h-3.5 w-3.5 text-slate-400" />
                <select
                  value={`${sortBy}_${sortOrder}`}
                  onChange={(e) => {
                    const [sb, so] = e.target.value.split("_");
                    setSortBy(sb as "job_number" | "name");
                    setSortOrder(so as "asc" | "desc");
                  }}
                  className="text-xs bg-transparent border-0 focus:outline-none text-slate-700 cursor-pointer"
                >
                  <option value="job_number_asc">Sort: Job # (Asc)</option>
                  <option value="job_number_desc">Sort: Job # (Desc)</option>
                  <option value="name_asc">Sort: Name (A → Z)</option>
                  <option value="name_desc">Sort: Name (Z → A)</option>
                </select>
              </div>
            </>
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
                  <th
                    onClick={() => {
                      if (sortBy === "job_number") {
                        setSortOrder(sortOrder === "asc" ? "desc" : "asc");
                      } else {
                        setSortBy("job_number");
                        setSortOrder("asc");
                      }
                    }}
                    className="py-3 px-4 cursor-pointer hover:text-indigo-600 transition select-none"
                    title="Click to sort by Job Number"
                  >
                    <span className="inline-flex items-center gap-1">
                      Job Number
                      {sortBy === "job_number" && (sortOrder === "asc" ? " ↑" : " ↓")}
                    </span>
                  </th>
                  <th
                    onClick={() => {
                      if (sortBy === "name") {
                        setSortOrder(sortOrder === "asc" ? "desc" : "asc");
                      } else {
                        setSortBy("name");
                        setSortOrder("asc");
                      }
                    }}
                    className="py-3 px-4 cursor-pointer hover:text-indigo-600 transition select-none"
                    title="Click to sort by Job Name"
                  >
                    <span className="inline-flex items-center gap-1">
                      Job Name
                      {sortBy === "name" && (sortOrder === "asc" ? " ↑" : " ↓")}
                    </span>
                  </th>
                  <th className="py-3 px-4">Group & Zone</th>
                  <th className="py-3 px-4">Revision</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4">Country</th>
                  <th className="py-3 px-4">Boundary Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {loading ? (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-slate-400">
                      <RefreshCw className="h-6 w-6 animate-spin mx-auto text-indigo-600 mb-2" />
                      Loading worksites...
                    </td>
                  </tr>
                ) : sortedAndFilteredWorksites.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-12 text-center text-slate-400">
                      No worksites match your criteria.
                    </td>
                  </tr>
                ) : (
                  sortedAndFilteredWorksites.map((ws) => (
                    <tr
                      key={ws.id}
                      onClick={() => navigate({ to: "/worksites/$worksiteId", params: { worksiteId: ws.id } })}
                      className={`hover:bg-indigo-50/50 cursor-pointer transition ${
                        !ws.is_active ? "bg-slate-50/80 opacity-75" : ""
                      }`}
                    >
                      <td className="py-3.5 px-4 font-mono font-medium text-slate-900">
                        <div className="flex items-center gap-1.5">
                          <span>{ws.job_number}</span>
                          {!ws.is_active && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-100 text-rose-700 border border-rose-200">
                              DEACTIVATED
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3.5 px-4 font-medium text-slate-800">
                        <div className="flex items-center gap-1.5">
                          <span>{ws.job_name}</span>
                          {ws.renewal_reference && (
                            <span className="text-xs text-slate-400" title={`${RENEWAL_LABEL}. ${RENEWAL_HINT}`}>
                              ({ws.renewal_reference})
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-500 flex items-center gap-2 mt-0.5 font-normal">
                          <span>Period: {ws.start_date || "Start N/A"} – {ws.end_date || "Ongoing"}</span>
                          {ws.budget_amount != null && user?.role === "ADMIN" && (
                            <span>• Budget: {formatMoney(ws.budget_amount, currencyForCountry(ws.country))}/yr</span>
                          )}
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-xs text-slate-600">
                        <div>{ws.group_name || "-"}</div>
                        <div className="text-slate-400">{ws.zone_name || "-"}</div>
                      </td>
                      <td className="py-3.5 px-4">
                        {ws.salary_revision_code ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium bg-purple-50 text-purple-700 border border-purple-200">
                            {ws.salary_revision_code}
                          </span>
                        ) : (
                          <span className="text-xs text-slate-400 italic">Default</span>
                        )}
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
                      <td className="py-3.5 px-4 text-right space-x-1.5 whitespace-nowrap">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setDrawingAccommodation(acc);
                          }}
                          className={`px-2.5 py-1 rounded-md text-xs font-semibold inline-flex items-center gap-1 shadow-xs transition ${
                            acc.has_boundary
                              ? "bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200"
                              : "bg-blue-600 hover:bg-blue-700 text-white"
                          }`}
                        >
                          <MapPin className="h-3.5 w-3.5" />
                          {acc.has_boundary ? "Edit Boundary" : "Draw Boundary"}
                        </button>

                        {isAdminOrEngineer && (
                          <>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setEditingAccommodation(acc);
                                setEditAccName(acc.name);
                                setEditAccAddress(acc.address || "");
                              }}
                              className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md text-xs font-medium inline-flex items-center gap-1 transition"
                              title="Edit Accommodation Name & Address"
                            >
                              <Edit2 className="h-3 w-3 text-slate-600" />
                              Edit
                            </button>

                            {isAdmin && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleToggleAccommodationActive(acc);
                              }}
                              className={`px-2.5 py-1 rounded-md text-xs font-medium inline-flex items-center gap-1 transition ${
                                acc.is_active
                                  ? "bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200"
                                  : "bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200"
                              }`}
                              title={acc.is_active ? "Deactivate Accommodation" : "Reactivate Accommodation"}
                            >
                              <PowerOff className="h-3 w-3" />
                              {acc.is_active ? "Deactivate" : "Activate"}
                            </button>
                            )}
                          </>
                        )}
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
        <Modal
          open
          onClose={() => setDrawingAccommodation(null)}
          size="xl"
          title={<span className="inline-flex items-center gap-2"><Home className="h-5 w-5 text-blue-600" /> {drawingAccommodation.has_boundary ? "Edit" : "Draw"} Boundary for {drawingAccommodation.name} ({drawingAccommodation.accommodation_code})</span>}
          description="Worker living quarters / camp boundary for attendance and nightly rest verification."
        >
          <div className="p-4 space-y-4">
            <div className="relative">
              <PlaceSearch map={mapInstance} />
              <MapContainer
                initialZoom={15}
                onMapReady={(map) => setMapInstance(map)}
                onMapUnmount={() => setMapInstance(null)}
                className="w-full h-[450px]"
              />
            </div>

            <PolygonEditor
              map={mapInstance}
              initialPolygon={drawingAccommodation.boundary_geojson as GeoJSON.Polygon | null}
              onSave={handleSaveAccommodationBoundary}
              isSaving={savingAccommodationBoundary}
            />
          </div>
        </Modal>
      )}

      {/* Add Worksite wizard (Batch 5.1 B; Admin only, DEC-61) */}
      <AddWorksiteWizard
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        groups={groups}
        zones={zones}
        onGroupCreated={(u) => setGroups((prev) => [...prev, u])}
        onZoneCreated={(u) => setZones((prev) => [...prev, u])}
        revisions={revisions}
        onCreated={(id) => {
          setModalOpen(false);
          navigate({
            to: "/worksites/$worksiteId",
            params: { worksiteId: id },
            search: { created: "1" } as any,
          });
        }}
      />

      {/* Edit Accommodation Modal */}
      {editingAccommodation && (
        <Modal
          open
          onClose={() => setEditingAccommodation(null)}
          size="md"
          title={<span className="inline-flex items-center gap-2"><Edit2 className="h-5 w-5 text-indigo-600" /> Edit Accommodation ({editingAccommodation.accommodation_code})</span>}
        >
          <form onSubmit={handleSaveAccommodation} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Accommodation Name *
              </label>
              <input
                type="text"
                required
                value={editAccName}
                onChange={(e) => setEditAccName(e.target.value)}
                className="w-full p-2 border border-slate-300 rounded text-sm focus:ring-1 focus:ring-indigo-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Address / Location
              </label>
              <input
                type="text"
                value={editAccAddress}
                onChange={(e) => setEditAccAddress(e.target.value)}
                placeholder="e.g. Al Quoz Industrial Area 4, Dubai"
                className="w-full p-2 border border-slate-300 rounded text-sm focus:ring-1 focus:ring-indigo-500"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2 border-t">
              <button
                type="button"
                onClick={() => setEditingAccommodation(null)}
                className="px-4 py-2 border border-slate-300 rounded text-xs font-medium text-slate-700 hover:bg-slate-50 transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={savingAcc}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded text-xs font-semibold shadow-sm transition disabled:opacity-50"
              >
                {savingAcc ? "Saving..." : "Save Changes"}
              </button>
            </div>
          </form>
        </Modal>
      )}
      <SupervisorProposalsModal
        isOpen={showProposals}
        onClose={() => setShowProposals(false)}
        onAssigned={fetchData}
      />
    </div>
  );
};
