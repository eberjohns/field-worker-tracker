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
  Download,
  Upload,
  ArrowUpDown,
  Edit2,
  PowerOff,
  Trash2,
} from "lucide-react";
import { MapContainer, PolygonEditor, PlaceSearch } from "../features/map";
import { Map as MapLibreMap } from "maplibre-gl";
import {
  CONTROLLED_STAFF_GRADE_DESCRIPTIONS,
  DEFAULT_GRADE_CODES,
} from "../components/jobs/jobItemUtils";

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
}

interface Zone {
  id: string;
  code: string;
  name: string;
}

interface InitialJobItem {
  sub_item_code: string;
  staff_grade_description: string;
  planned_grade_code: string;
  start_date: string;
  end_date: string;
  required_staff_count: number;
  hours_per_occurrence_per_staff: number;
  frequency_unit: string;
  occurrences_per_period: number;
  period_interval: number;
  deployment_type: string;
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
  const [sortBy, setSortBy] = useState<"job_number" | "name">("job_number");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");

  // Create Modal
  const [modalOpen, setModalOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [formNumber, setFormNumber] = useState("");
  const [formName, setFormName] = useState("");
  const [formGroupId, setFormGroupId] = useState("");
  const [newGroupName, setNewGroupName] = useState("");
  const [newGroupCode, setNewGroupCode] = useState("");
  const [formZoneId, setFormZoneId] = useState("");
  const [newZoneName, setNewZoneName] = useState("");
  const [newZoneCode, setNewZoneCode] = useState("");
  const [formCountry, setFormCountry] = useState("AE");
  const [formCustomerType, setFormCustomerType] = useState("Direct");
  const [formRenewalRef, setFormRenewalRef] = useState("");
  const [formBudget, setFormBudget] = useState("");
  const [initialJobItems, setInitialJobItems] = useState<InitialJobItem[]>([]);
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
      alert(err.message || "Export failed");
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
  }, [search, groupFilter, zoneFilter, countryFilter, boundaryFilter, statusFilter]);

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
      let effectiveGroupId = formGroupId;
      if (formGroupId === "__NEW__") {
        if (!newGroupName.trim()) throw new Error("Please enter a name for the new Customer Group.");
        const code = (newGroupCode.trim() || newGroupName.trim().toUpperCase().replace(/[^A-Z0-9]/g, "_")).slice(0, 16);
        const gRes = await fetch("/api/v1/groups", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
          body: JSON.stringify({ name: newGroupName.trim(), code }),
        });
        if (!gRes.ok) {
          const gErr = await gRes.json().catch(() => ({}));
          throw new Error(gErr.detail || "Failed to create new customer group.");
        }
        const createdG = await gRes.json();
        effectiveGroupId = createdG.id;
        setGroups((prev) => [...prev, createdG]);
      }

      let effectiveZoneId = formZoneId;
      if (formZoneId === "__NEW__") {
        if (!newZoneName.trim()) throw new Error("Please enter a name for the new Zone.");
        const code = (newZoneCode.trim() || newZoneName.trim().toUpperCase().replace(/[^A-Z0-9]/g, "_")).slice(0, 16);
        const zRes = await fetch("/api/v1/zones", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
          body: JSON.stringify({ name: newZoneName.trim(), code, country: formCountry }),
        });
        if (!zRes.ok) {
          const zErr = await zRes.json().catch(() => ({}));
          throw new Error(zErr.detail || "Failed to create new zone.");
        }
        const createdZ = await zRes.json();
        effectiveZoneId = createdZ.id;
        setZones((prev) => [...prev, createdZ]);
      }

      const res = await fetch("/api/v1/worksites", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          job_number: cleanedNumber,
          job_name: formName.trim(),
          group_id: effectiveGroupId,
          zone_id: effectiveZoneId,
          country: formCountry,
          customer_type: formCustomerType || null,
          renewal_reference: formRenewalRef.trim() || null,
          budget_amount: user?.role === "ADMIN" && formBudget ? parseFloat(formBudget) : null,
        }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to create worksite");
      }

      const createdWs = await res.json();

      // Create initial job items if added
      for (const item of initialJobItems) {
        if (!item.sub_item_code.trim()) continue;
        await fetch(`/api/v1/worksites/${createdWs.id}/job-items`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            sub_item_code: item.sub_item_code.trim(),
            staff_grade_description: item.staff_grade_description,
            planned_grade_code: item.planned_grade_code,
            start_date: item.start_date || new Date().toISOString().slice(0, 10),
            end_date: item.end_date || null,
            frequency_unit: item.frequency_unit,
            occurrences_per_period: item.occurrences_per_period,
            period_interval: item.period_interval,
            required_staff_count: item.required_staff_count,
            hours_per_occurrence_per_staff: item.hours_per_occurrence_per_staff,
            deployment_type: item.deployment_type,
          }),
        });
      }

      setModalOpen(false);
      setFormNumber("");
      setFormName("");
      setFormGroupId("");
      setNewGroupName("");
      setNewGroupCode("");
      setFormZoneId("");
      setNewZoneName("");
      setNewZoneCode("");
      setFormRenewalRef("");
      setFormBudget("");
      setInitialJobItems([]);
      fetchData();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to create worksite");
    } finally {
      setCreateLoading(false);
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
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to update accommodation");
      }
      setEditingAccommodation(null);
      fetchData();
    } catch (err: any) {
      alert(err.message || "Failed to update accommodation");
    } finally {
      setSavingAcc(false);
    }
  };

  const handleToggleAccommodationActive = async (acc: AccommodationItem) => {
    const action = acc.is_active ? "deactivate" : "reactivate";
    if (!window.confirm(`Are you sure you want to ${action} accommodation '${acc.name}' (${acc.accommodation_code})?`)) return;
    try {
      const res = await fetch(`/api/v1/accommodations/${acc.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({
          is_active: !acc.is_active,
          version: acc.version,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Failed to ${action} accommodation`);
      }
      fetchData();
    } catch (err: any) {
      alert(err.message || `Failed to ${action} accommodation`);
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

              <Link
                to="/imports"
                className="flex items-center gap-1.5 px-3 py-2 border border-slate-200 bg-white text-slate-700 rounded-md text-sm font-medium hover:bg-slate-50 transition shadow-xs"
                title="Import Worksites from Excel"
              >
                <Upload className="h-4 w-4 text-slate-500" />
                Import
              </Link>
            </>
          )}

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
                className="text-sm border border-slate-300 rounded-md py-1.5 px-3 focus:outline-none focus:ring-1 focus:ring-indigo-500 bg-white"
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
                            <span className="text-xs text-slate-400">({ws.renewal_reference})</span>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-500 flex items-center gap-2 mt-0.5 font-normal">
                          <span>Period: {ws.start_date || "Start N/A"} – {ws.end_date || "Ongoing"}</span>
                          {ws.budget_amount != null && user?.role === "ADMIN" && (
                            <span>• Budget: {Number(ws.budget_amount).toLocaleString()} AED/yr</span>
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
          </div>
        </div>
      )}

      {/* Create Worksite Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-2xl w-full p-6 space-y-4 my-8 max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between border-b pb-3">
              <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Building2 className="h-5 w-5 text-indigo-600" />
                Create New Worksite
              </h2>
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {errorMsg && (
              <div className="p-3 bg-red-50 border border-red-200 rounded text-xs text-red-700 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0 text-red-500" />
                {errorMsg}
              </div>
            )}

            <form onSubmit={handleCreateWorksite} className="space-y-4 flex-1 overflow-y-auto pr-1">
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
                    <option value="__NEW__">+ Add New Group...</option>
                  </select>
                  {formGroupId === "__NEW__" && (
                    <div className="mt-2 space-y-1.5 p-2.5 bg-slate-50 border border-slate-200 rounded">
                      <input
                        type="text"
                        required
                        placeholder="New Group Name (e.g. Emaar)"
                        value={newGroupName}
                        onChange={(e) => setNewGroupName(e.target.value)}
                        className="w-full px-2.5 py-1 text-xs border border-slate-300 rounded bg-white"
                      />
                      <input
                        type="text"
                        placeholder="Group Code (Optional, e.g. EMAAR)"
                        value={newGroupCode}
                        onChange={(e) => setNewGroupCode(e.target.value.toUpperCase())}
                        className="w-full px-2.5 py-1 text-xs font-mono border border-slate-300 rounded bg-white"
                      />
                    </div>
                  )}
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
                    <option value="__NEW__">+ Add New Zone...</option>
                  </select>
                  {formZoneId === "__NEW__" && (
                    <div className="mt-2 space-y-1.5 p-2.5 bg-slate-50 border border-slate-200 rounded">
                      <input
                        type="text"
                        required
                        placeholder="New Zone Name (e.g. Dubai Marina)"
                        value={newZoneName}
                        onChange={(e) => setNewZoneName(e.target.value)}
                        className="w-full px-2.5 py-1 text-xs border border-slate-300 rounded bg-white"
                      />
                      <input
                        type="text"
                        placeholder="Zone Code (Optional, e.g. MARINA)"
                        value={newZoneCode}
                        onChange={(e) => setNewZoneCode(e.target.value.toUpperCase())}
                        className="w-full px-2.5 py-1 text-xs font-mono border border-slate-300 rounded bg-white"
                      />
                    </div>
                  )}
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

                {user?.role === "ADMIN" && (
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">
                      Labour Budget (AED)
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
                )}
              </div>

              {/* Inline Job Items Section */}
              <div className="border-t border-slate-200 pt-3 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-xs font-bold text-slate-900">Job Items (Staff Requirements)</h3>
                    <p className="text-[11px] text-slate-500">Optional: Add staffing lines directly with this worksite.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      const nextNum = String(initialJobItems.length + 1).padStart(2, "0");
                      setInitialJobItems((prev) => [
                        ...prev,
                        {
                          sub_item_code: nextNum,
                          staff_grade_description: CONTROLLED_STAFF_GRADE_DESCRIPTIONS[6] || "Gardener Helper",
                          planned_grade_code: DEFAULT_GRADE_CODES[8] || "G3C",
                          start_date: new Date().toISOString().slice(0, 10),
                          end_date: "",
                          required_staff_count: 1,
                          hours_per_occurrence_per_staff: 8.0,
                          frequency_unit: "MONTH",
                          occurrences_per_period: 26,
                          period_interval: 1,
                          deployment_type: "SCHEDULED",
                        },
                      ]);
                    }}
                    className="flex items-center gap-1 px-2.5 py-1 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded text-xs font-semibold transition"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Add Job Item
                  </button>
                </div>

                {initialJobItems.map((item, idx) => (
                  <div key={idx} className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-700">Item #{idx + 1} ({item.sub_item_code})</span>
                      <button
                        type="button"
                        onClick={() => setInitialJobItems((prev) => prev.filter((_, i) => i !== idx))}
                        className="text-red-500 hover:text-red-700 p-0.5"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        <label className="block text-[10px] text-slate-500 mb-0.5">Sub-Item Code</label>
                        <input
                          type="text"
                          required
                          value={item.sub_item_code}
                          onChange={(e) => {
                            const val = e.target.value;
                            setInitialJobItems((prev) => prev.map((it, i) => i === idx ? { ...it, sub_item_code: val } : it));
                          }}
                          className="w-full p-1 border rounded bg-white text-xs font-mono"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] text-slate-500 mb-0.5">Staff Designation</label>
                        <select
                          value={item.staff_grade_description}
                          onChange={(e) => {
                            const val = e.target.value;
                            setInitialJobItems((prev) => prev.map((it, i) => i === idx ? { ...it, staff_grade_description: val } : it));
                          }}
                          className="w-full p-1 border rounded bg-white text-xs"
                        >
                          {CONTROLLED_STAFF_GRADE_DESCRIPTIONS.map((d) => (
                            <option key={d} value={d}>{d}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-[10px] text-slate-500 mb-0.5">Planned Grade</label>
                        <select
                          value={item.planned_grade_code}
                          onChange={(e) => {
                            const val = e.target.value;
                            setInitialJobItems((prev) => prev.map((it, i) => i === idx ? { ...it, planned_grade_code: val } : it));
                          }}
                          className="w-full p-1 border rounded bg-white text-xs font-mono"
                        >
                          {DEFAULT_GRADE_CODES.map((g) => (
                            <option key={g} value={g}>{g}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div className="grid grid-cols-4 gap-2">
                      <div>
                        <label className="block text-[10px] text-slate-500 mb-0.5">Start Date</label>
                        <input
                          type="date"
                          required
                          value={item.start_date}
                          onChange={(e) => {
                            const val = e.target.value;
                            setInitialJobItems((prev) => prev.map((it, i) => i === idx ? { ...it, start_date: val } : it));
                          }}
                          className="w-full p-1 border rounded bg-white text-[11px]"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] text-slate-500 mb-0.5">Staff Count</label>
                        <input
                          type="number"
                          min="1"
                          value={item.required_staff_count}
                          onChange={(e) => {
                            const val = Number(e.target.value) || 1;
                            setInitialJobItems((prev) => prev.map((it, i) => i === idx ? { ...it, required_staff_count: val } : it));
                          }}
                          className="w-full p-1 border rounded bg-white text-xs"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] text-slate-500 mb-0.5">Hours / Staff</label>
                        <input
                          type="number"
                          step="0.5"
                          min="0.5"
                          value={item.hours_per_occurrence_per_staff}
                          onChange={(e) => {
                            const val = Number(e.target.value) || 8;
                            setInitialJobItems((prev) => prev.map((it, i) => i === idx ? { ...it, hours_per_occurrence_per_staff: val } : it));
                          }}
                          className="w-full p-1 border rounded bg-white text-xs"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] text-slate-500 mb-0.5">Occurrences / Period</label>
                        <input
                          type="number"
                          min="1"
                          value={item.occurrences_per_period}
                          onChange={(e) => {
                            const val = Number(e.target.value) || 1;
                            setInitialJobItems((prev) => prev.map((it, i) => i === idx ? { ...it, occurrences_per_period: val } : it));
                          }}
                          className="w-full p-1 border rounded bg-white text-xs"
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-slate-200">
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

      {/* Edit Accommodation Modal */}
      {editingAccommodation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <Edit2 className="h-5 w-5 text-indigo-600" />
                Edit Accommodation ({editingAccommodation.accommodation_code})
              </h2>
              <button
                type="button"
                onClick={() => setEditingAccommodation(null)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
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
          </div>
        </div>
      )}
    </div>
  );
};
