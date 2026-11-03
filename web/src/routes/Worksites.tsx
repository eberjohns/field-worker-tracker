import React, { useState, useEffect } from "react";
import { Link } from "@tanstack/react-router";
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
} from "lucide-react";

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
  has_boundary: boolean;
  rep_latitude: string | number | null;
  rep_longitude: string | number | null;
  budget_amount: string | number | null;
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
  const { token, user } = useAuth();
  const [worksites, setWorksites] = useState<Worksite[]>([]);
  const [groups, setGroups] = useState<Group[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState("");
  const [groupFilter, setGroupFilter] = useState("");
  const [zoneFilter, setZoneFilter] = useState("");
  const [countryFilter, setCountryFilter] = useState("");
  const [boundaryFilter, setBoundaryFilter] = useState<string>("ALL");

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

      const [wsRes, gRes, zRes] = await Promise.all([
        fetch(`/api/v1/worksites?${params.toString()}`, { headers }),
        fetch("/api/v1/groups", { headers }),
        fetch("/api/v1/zones", { headers }),
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
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [search, groupFilter, zoneFilter, countryFilter, boundaryFilter]);

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

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-wrap gap-4 items-center justify-between">
        <div className="flex flex-wrap items-center gap-3 flex-1 min-w-[280px]">
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search job number or name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-sm border border-slate-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>

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

          <select
            value={boundaryFilter}
            onChange={(e) => setBoundaryFilter(e.target.value)}
            className="text-sm border border-slate-300 rounded-md py-1.5 px-3 focus:outline-none focus:ring-1 focus:ring-indigo-500 bg-white"
          >
            <option value="ALL">All Boundaries</option>
            <option value="SET">Boundary Set</option>
            <option value="UNSET">No Boundary</option>
          </select>

          <select
            value={countryFilter}
            onChange={(e) => setCountryFilter(e.target.value)}
            className="text-sm border border-slate-300 rounded-md py-1.5 px-3 focus:outline-none focus:ring-1 focus:ring-indigo-500 bg-white"
          >
            <option value="">All Countries</option>
            <option value="AE">UAE (AE)</option>
            <option value="SA">KSA (SA)</option>
          </select>
        </div>

        <button
          onClick={fetchData}
          className="p-2 border border-slate-200 rounded-md hover:bg-slate-50 text-slate-600 transition"
          title="Refresh worksites"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin text-indigo-600" : ""}`} />
        </button>
      </div>

      {/* Worksites Table */}
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
                  <tr key={ws.id} className="hover:bg-slate-50/80 transition">
                    <td className="py-3.5 px-4 font-mono font-medium text-slate-900">
                      {ws.job_number}
                    </td>
                    <td className="py-3.5 px-4 font-medium text-slate-800">
                      {ws.job_name}
                      {ws.renewal_reference && (
                        <span className="ml-2 text-xs text-slate-400">({ws.renewal_reference})</span>
                      )}
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
                      <Link
                        to="/worksites/$worksiteId"
                        params={{ worksiteId: ws.id }}
                        className="inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-800"
                      >
                        View & Edit
                        <ExternalLink className="h-3 w-3" />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

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
