import React, { useState, useEffect, useCallback } from "react";
import {
  Truck,
  Calendar,
  Users,
  Clock,
  Printer,
  Copy,
  Plus,
  Send,
  Trash2,
  AlertTriangle,
  CheckCircle2,
  Car,
  X,
  Sparkles,
  Building,
  Home,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

interface Vehicle {
  id: string;
  label: string;
  type: string;
  notes?: string | null;
  is_active: boolean;
  version: number;
}

interface Driver {
  employee_id: string;
  tally_id: string;
  name: string;
  phone?: string | null;
  accommodation_id?: string | null;
  accommodation_name?: string | null;
  runs_this_week: number;
}

interface Passenger {
  id: string;
  employee_id: string;
  tally_id: string;
  name: string;
  phone?: string | null;
  worksite_name?: string | null;
}

interface Stop {
  id: string;
  sequence: number;
  stop_type: "SITE" | "ACCOMMODATION";
  worksite_id?: string | null;
  worksite_name?: string | null;
  accommodation_id?: string | null;
  accommodation_name?: string | null;
  planned_time?: string | null;
  passengers: Passenger[];
}

interface TransportRun {
  id: string;
  run_date: string;
  direction: "MORNING" | "EVENING";
  driver_id: string;
  driver_name: string;
  driver_phone?: string | null;
  driver_tally_id?: string | null;
  vehicle_id?: string | null;
  vehicle_label?: string | null;
  status: "DRAFT" | "PUBLISHED";
  needs_update: boolean;
  version: number;
  stops: Stop[];
  total_passengers: number;
}

interface UnassignedWorker {
  employee_id: string;
  tally_id: string;
  name: string;
  phone?: string | null;
  accommodation_id?: string | null;
  accommodation_name?: string | null;
  worksite_id?: string | null;
  worksite_name?: string | null;
  job_number?: string | null;
  assigned_hours?: number | null;
}

interface WorksiteOption {
  id: string;
  job_number: string;
  job_name: string;
}

interface AccommodationOption {
  id: string;
  name: string;
}

export const Transport: React.FC = () => {
  const { user } = useAuth();
  const token = localStorage.getItem("fwt_token");

  const [selectedDate, setSelectedDate] = useState<string>(() => {
    return new Date().toISOString().split("T")[0];
  });
  const [direction, setDirection] = useState<"MORNING" | "EVENING">("MORNING");

  const [runs, setRuns] = useState<TransportRun[]>([]);
  const [unassignedWorkers, setUnassignedWorkers] = useState<UnassignedWorker[]>([]);
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [worksites, setWorksites] = useState<WorksiteOption[]>([]);
  const [accommodations, setAccommodations] = useState<AccommodationOption[]>([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Modals
  const [isVehicleModalOpen, setIsVehicleModalOpen] = useState(false);
  const [isCopyModalOpen, setIsCopyModalOpen] = useState(false);
  const [isRunModalOpen, setIsRunModalOpen] = useState(false);
  const [editingRunId, setEditingRunId] = useState<string | null>(null);
  const [printRun, setPrintRun] = useState<TransportRun | null>(null);
  const [copyTargetDate, setCopyTargetDate] = useState<string>(() => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return d.toISOString().split("T")[0];
  });
  const [copyOmittedResult, setCopyOmittedResult] = useState<Array<{ name: string; reason: string }> | null>(null);

  // Run Form State
  const [formDriverId, setFormDriverId] = useState<string>("");
  const [formVehicleId, setFormVehicleId] = useState<string>("");
  const [formStops, setFormStops] = useState<
    Array<{
      sequence: number;
      stop_type: "SITE" | "ACCOMMODATION";
      worksite_id?: string;
      accommodation_id?: string;
      planned_time?: string;
      passengers: Array<{ employee_id: string; name?: string; tally_id?: string }>;
    }>
  >([]);

  // Vehicle Form State
  const [vehLabel, setVehLabel] = useState("");
  const [vehType, setVehType] = useState("VAN");
  const [vehNotes, setVehNotes] = useState("");

  const canEdit = user?.role === "ADMIN" || user?.role === "ENGINEER" || user?.role === "SUPERVISOR";

  const fetchBaseData = useCallback(async () => {
    if (!token) return;
    try {
      const [vRes, dRes, wRes, aRes] = await Promise.all([
        fetch("/api/v1/vehicles?active_only=false", { headers: { Authorization: `Bearer ${token}` } }),
        fetch("/api/v1/drivers", { headers: { Authorization: `Bearer ${token}` } }),
        fetch("/api/v1/worksites", { headers: { Authorization: `Bearer ${token}` } }),
        fetch("/api/v1/accommodations", { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (vRes.ok) setVehicles(await vRes.json());
      if (dRes.ok) setDrivers(await dRes.json());
      if (wRes.ok) setWorksites(await wRes.json());
      if (aRes.ok) setAccommodations(await aRes.json());
    } catch (err) {
      console.error("Failed to load reference data", err);
    }
  }, [token]);

  const fetchRunsAndUnassigned = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const [rRes, uRes] = await Promise.all([
        fetch(`/api/v1/transport-runs?run_date=${selectedDate}&direction=${direction}`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch(`/api/v1/transport-runs/unassigned-workers?run_date=${selectedDate}&direction=${direction}`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);
      if (rRes.ok) {
        setRuns(await rRes.json());
      } else {
        const errJson = await rRes.json();
        setError(errJson.detail || "Failed to load runs");
      }
      if (uRes.ok) {
        setUnassignedWorkers(await uRes.json());
      }
    } catch {
      setError("Network error loading transport data");
    } finally {
      setLoading(false);
    }
  }, [selectedDate, direction, token]);

  useEffect(() => {
    fetchBaseData();
  }, [fetchBaseData]);

  useEffect(() => {
    fetchRunsAndUnassigned();
  }, [fetchRunsAndUnassigned]);

  // Actions
  const handlePublishRun = async (runId: string) => {
    if (!token) return;
    try {
      const res = await fetch(`/api/v1/transport-runs/${runId}/publish`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setActionSuccess("Run published successfully and synced to driver and passengers.");
        setTimeout(() => setActionSuccess(null), 4000);
        fetchRunsAndUnassigned();
      } else {
        const errJson = await res.json();
        setError(errJson.detail || "Failed to publish run");
      }
    } catch {
      setError("Failed to publish run");
    }
  };

  const handleDeleteRun = async (runId: string) => {
    if (!window.confirm("Are you sure you want to cancel and delete this run?")) return;
    if (!token) return;
    try {
      const res = await fetch(`/api/v1/transport-runs/${runId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setActionSuccess("Run deleted.");
        setTimeout(() => setActionSuccess(null), 3000);
        fetchRunsAndUnassigned();
      } else {
        const errJson = await res.json();
        setError(errJson.detail || "Failed to delete run");
      }
    } catch {
      setError("Failed to delete run");
    }
  };

  const handleSuggest = async () => {
    if (!token) return;
    setLoading(true);
    try {
      const res = await fetch("/api/v1/transport-runs/suggest", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ run_date: selectedDate, direction }),
      });
      if (res.ok) {
        const data = await res.json();
        setActionSuccess(`Suggested ${data.suggested_runs.length} runs from schedule.`);
        setTimeout(() => setActionSuccess(null), 4000);
        fetchRunsAndUnassigned();
      } else {
        const err = await res.json();
        setError(err.detail || "Failed to suggest runs");
      }
    } catch {
      setError("Failed to suggest runs");
    } finally {
      setLoading(false);
    }
  };

  const handleCopyRuns = async () => {
    if (!token) return;
    try {
      const res = await fetch("/api/v1/transport-runs/copy", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          source_date: selectedDate,
          target_date: copyTargetDate,
          direction,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.omitted_passengers && data.omitted_passengers.length > 0) {
          setCopyOmittedResult(data.omitted_passengers);
        } else {
          setIsCopyModalOpen(false);
          setActionSuccess(`Successfully copied ${data.created_runs.length} runs.`);
          setTimeout(() => setActionSuccess(null), 4000);
        }
        fetchRunsAndUnassigned();
      } else {
        const err = await res.json();
        setError(err.detail || "Failed to copy runs");
      }
    } catch {
      setError("Failed to copy runs");
    }
  };

  // Open Create Modal
  const openCreateRunModal = () => {
    setEditingRunId(null);
    setFormDriverId(drivers[0]?.employee_id || "");
    setFormVehicleId(vehicles[0]?.id || "");
    // Default morning stops: 1 Accommodation, 2 Worksite
    setFormStops([
      {
        sequence: 1,
        stop_type: "ACCOMMODATION",
        accommodation_id: accommodations[0]?.id || undefined,
        passengers: [],
      },
      {
        sequence: 2,
        stop_type: "SITE",
        worksite_id: worksites[0]?.id || undefined,
        passengers: [],
      },
    ]);
    setIsRunModalOpen(true);
  };

  // Open Edit Modal
  const openEditRunModal = (run: TransportRun) => {
    setEditingRunId(run.id);
    setFormDriverId(run.driver_id);
    setFormVehicleId(run.vehicle_id || "");
    setFormStops(
      run.stops.map((s) => ({
        sequence: s.sequence,
        stop_type: s.stop_type,
        worksite_id: s.worksite_id || undefined,
        accommodation_id: s.accommodation_id || undefined,
        planned_time: s.planned_time || undefined,
        passengers: s.passengers.map((p) => ({
          employee_id: p.employee_id,
          name: p.name,
          tally_id: p.tally_id,
        })),
      }))
    );
    setIsRunModalOpen(true);
  };

  const handleSaveRun = async () => {
    if (!token) return;
    if (!formDriverId) {
      alert("Please select a driver");
      return;
    }
    const payload = {
      run_date: selectedDate,
      direction,
      driver_id: formDriverId,
      vehicle_id: formVehicleId || null,
      stops: formStops.map((s, idx) => ({
        sequence: idx + 1,
        stop_type: s.stop_type,
        worksite_id: s.stop_type === "SITE" ? s.worksite_id : null,
        accommodation_id: s.stop_type === "ACCOMMODATION" ? s.accommodation_id : null,
        planned_time: s.planned_time || null,
        passengers: s.passengers.map((p) => ({ employee_id: p.employee_id })),
      })),
    };

    try {
      const url = editingRunId
        ? `/api/v1/transport-runs/${editingRunId}`
        : "/api/v1/transport-runs";
      const method = editingRunId ? "PATCH" : "POST";

      const res = await fetch(url, {
        method,
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        setIsRunModalOpen(false);
        setActionSuccess(editingRunId ? "Run updated." : "Run created.");
        setTimeout(() => setActionSuccess(null), 3000);
        fetchRunsAndUnassigned();
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to save run");
      }
    } catch {
      alert("Failed to save run");
    }
  };

  // Quick Assign Unassigned Worker to a Stop in Create/Edit Modal
  const assignWorkerToStop = (worker: UnassignedWorker, stopIdx: number) => {
    const updated = [...formStops];
    // Check if worker already in this stop
    if (updated[stopIdx].passengers.some((p) => p.employee_id === worker.employee_id)) return;
    updated[stopIdx].passengers.push({
      employee_id: worker.employee_id,
      name: worker.name,
      tally_id: worker.tally_id,
    });
    setFormStops(updated);
  };

  const removeWorkerFromStop = (stopIdx: number, pIdx: number) => {
    const updated = [...formStops];
    updated[stopIdx].passengers.splice(pIdx, 1);
    setFormStops(updated);
  };

  const handleCreateVehicle = async () => {
    if (!token || !vehLabel.trim()) return;
    try {
      const res = await fetch("/api/v1/vehicles", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ label: vehLabel, type: vehType, notes: vehNotes }),
      });
      if (res.ok) {
        setVehLabel("");
        setVehNotes("");
        fetchBaseData();
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to add vehicle");
      }
    } catch {
      alert("Error adding vehicle");
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-blue-50 text-blue-600 rounded-lg">
            <Truck className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">Drivers & Daily Transport Runs</h1>
            <p className="text-sm text-slate-500">
              Manage vehicle runs, ordered stops, passenger manifests, and driver mobile sync.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Date Picker */}
          <div className="flex items-center bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-sm">
            <Calendar className="h-4 w-4 text-slate-400 mr-2" />
            <input
              type="date"
              className="bg-transparent text-slate-800 font-medium focus:outline-none"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
            />
          </div>

          {/* Direction Toggle */}
          <div className="flex bg-slate-100 p-1 rounded-lg border border-slate-200 text-xs font-semibold">
            <button
              onClick={() => setDirection("MORNING")}
              className={`px-3 py-1.5 rounded-md transition ${
                direction === "MORNING"
                  ? "bg-white text-blue-700 shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Morning (to Site)
            </button>
            <button
              onClick={() => setDirection("EVENING")}
              className={`px-3 py-1.5 rounded-md transition ${
                direction === "EVENING"
                  ? "bg-white text-blue-700 shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Evening (Return)
            </button>
          </div>

          {canEdit && (
            <>
              <button
                onClick={handleSuggest}
                disabled={loading}
                className="flex items-center gap-1.5 px-3 py-2 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded-lg text-sm font-medium transition"
                title="Propose runs grouped by accommodation and worksite"
              >
                <Sparkles className="h-4 w-4" />
                Suggest Runs
              </button>
              <button
                onClick={() => setIsCopyModalOpen(true)}
                className="flex items-center gap-1.5 px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-sm font-medium transition"
              >
                <Copy className="h-4 w-4" />
                Copy Day
              </button>
              <button
                onClick={openCreateRunModal}
                className="flex items-center gap-1.5 px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium shadow-sm transition"
              >
                <Plus className="h-4 w-4" />
                New Run
              </button>
              <button
                onClick={() => setIsVehicleModalOpen(true)}
                className="p-2 border border-slate-200 text-slate-600 hover:bg-slate-50 rounded-lg transition"
                title="Manage Vehicles"
              >
                <Car className="h-4 w-4" />
              </button>
            </>
          )}
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3 text-sm text-red-700">
          <AlertTriangle className="h-5 w-5 flex-shrink-0 text-red-500" />
          <span>{error}</span>
        </div>
      )}
      {actionSuccess && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg flex items-center gap-3 text-sm text-emerald-800">
          <CheckCircle2 className="h-5 w-5 flex-shrink-0 text-emerald-500" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {/* Stats Summary Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <div className="text-xs uppercase font-bold text-slate-500">Total Runs</div>
            <div className="text-2xl font-bold text-slate-900 mt-1">{runs.length}</div>
          </div>
          <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
            <Truck className="h-5 w-5" />
          </div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <div className="text-xs uppercase font-bold text-slate-500">Assigned Passengers</div>
            <div className="text-2xl font-bold text-slate-900 mt-1">
              {runs.reduce((acc, r) => acc + r.total_passengers, 0)}
            </div>
          </div>
          <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
            <Users className="h-5 w-5" />
          </div>
        </div>
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between">
          <div>
            <div className="text-xs uppercase font-bold text-slate-500">Unassigned Workers</div>
            <div className="text-2xl font-bold text-amber-600 mt-1">{unassignedWorkers.length}</div>
          </div>
          <div className="p-2 bg-amber-50 text-amber-600 rounded-lg">
            <AlertTriangle className="h-5 w-5" />
          </div>
        </div>
      </div>

      {/* Main Grid: Runs List + Unassigned Workers Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Runs Main Column (3 Cols) */}
        <div className="lg:col-span-3 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900">
              {direction === "MORNING" ? "Morning Runs" : "Evening Runs"} ({runs.length})
            </h2>
            <span className="text-xs text-slate-500">Synced to worker mobile app</span>
          </div>

          {runs.length === 0 ? (
            <div className="bg-white p-12 text-center rounded-xl border border-slate-200 shadow-sm space-y-3">
              <div className="h-12 w-12 bg-slate-100 text-slate-400 rounded-full flex items-center justify-center mx-auto">
                <Truck className="h-6 w-6" />
              </div>
              <p className="text-sm font-medium text-slate-700">No transport runs scheduled for this date & direction.</p>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                Click &quot;Suggest Runs&quot; to auto-group scheduled workers, or create a new run manually.
              </p>
              {canEdit && (
                <button
                  onClick={openCreateRunModal}
                  className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold"
                >
                  <Plus className="h-3.5 w-3.5" />
                  Create First Run
                </button>
              )}
            </div>
          ) : (
            runs.map((run) => (
              <div
                key={run.id}
                className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-4 hover:border-slate-300 transition"
              >
                {/* Run Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-slate-100 gap-3">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 bg-blue-50 text-blue-700 rounded-lg flex items-center justify-center font-bold">
                      <Truck className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-900 text-base">{run.driver_name}</span>
                        {run.vehicle_label ? (
                          <span className="px-2 py-0.5 bg-slate-100 text-slate-700 rounded text-xs font-medium">
                            {run.vehicle_label}
                          </span>
                        ) : (
                          <span className="text-xs text-slate-400 italic">No vehicle</span>
                        )}
                        {run.needs_update && (
                          <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs font-bold flex items-center gap-1">
                            <AlertTriangle className="h-3 w-3" /> Needs Update
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-slate-500 mt-0.5">
                        ID: {run.driver_tally_id || "N/A"} • Phone: {run.driver_phone || "Not set"}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                        run.status === "PUBLISHED"
                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          : "bg-slate-100 text-slate-700 border border-slate-200"
                      }`}
                    >
                      {run.status}
                    </span>

                    <button
                      onClick={() => setPrintRun(run)}
                      className="p-1.5 text-slate-600 hover:text-slate-900 border border-slate-200 rounded-lg hover:bg-slate-50 transition"
                      title="Print Run Sheet"
                    >
                      <Printer className="h-4 w-4" />
                    </button>

                    {canEdit && (
                      <>
                        <button
                          onClick={() => openEditRunModal(run)}
                          className="px-2.5 py-1 text-xs border border-slate-200 hover:bg-slate-50 text-slate-700 font-medium rounded-lg transition"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handlePublishRun(run.id)}
                          className="flex items-center gap-1 px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold shadow-sm transition"
                        >
                          <Send className="h-3 w-3" />
                          {run.status === "PUBLISHED" ? "Re-sync" : "Publish"}
                        </button>
                        <button
                          onClick={() => handleDeleteRun(run.id)}
                          className="p-1.5 text-red-500 hover:bg-red-50 rounded-lg transition"
                          title="Delete run"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {/* Ordered Stops List */}
                <div className="space-y-3">
                  <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    Stops in Order ({run.stops.length}) • Total Passengers: {run.total_passengers}
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {run.stops.map((stop) => (
                      <div
                        key={stop.id}
                        className="bg-slate-50 rounded-lg p-3 border border-slate-200 space-y-2"
                      >
                        <div className="flex items-center justify-between text-xs">
                          <div className="flex items-center gap-1.5 font-bold text-slate-700">
                            <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-[10px]">
                              {stop.sequence}
                            </span>
                            {stop.stop_type === "ACCOMMODATION" ? (
                              <span className="flex items-center gap-1 text-amber-700">
                                <Home className="h-3.5 w-3.5" /> Camp Pickup
                              </span>
                            ) : (
                              <span className="flex items-center gap-1 text-blue-700">
                                <Building className="h-3.5 w-3.5" /> Site Drop-off
                              </span>
                            )}
                          </div>
                          {stop.planned_time && (
                            <span className="text-slate-500 font-mono text-[11px] flex items-center gap-1">
                              <Clock className="h-3 w-3" /> {stop.planned_time}
                            </span>
                          )}
                        </div>

                        <div className="text-sm font-semibold text-slate-800">
                          {stop.stop_type === "ACCOMMODATION"
                            ? stop.accommodation_name || "Accommodation"
                            : stop.worksite_name || "Worksite"}
                        </div>

                        {/* Passenger Chips */}
                        <div className="space-y-1">
                          <div className="text-[11px] font-medium text-slate-500">
                            Passengers ({stop.passengers.length}):
                          </div>
                          <div className="flex flex-wrap gap-1.5">
                            {stop.passengers.length === 0 ? (
                              <span className="text-xs text-slate-400 italic">No passengers assigned</span>
                            ) : (
                              stop.passengers.map((p) => (
                                <span
                                  key={p.employee_id}
                                  className="inline-flex items-center gap-1 px-2 py-0.5 bg-white border border-slate-200 rounded text-xs font-medium text-slate-700 shadow-2xs"
                                >
                                  <span>{p.name}</span>
                                  <span className="text-[10px] text-slate-400">({p.tally_id})</span>
                                </span>
                              ))
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Unassigned Scheduled Workers Sidebar (1 Col) */}
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <Users className="h-4 w-4 text-amber-500" />
                <h3 className="font-bold text-slate-900 text-sm">Unassigned Workers</h3>
              </div>
              <span className="px-2 py-0.5 bg-amber-50 text-amber-700 border border-amber-200 rounded-full text-xs font-bold">
                {unassignedWorkers.length}
              </span>
            </div>
            <p className="text-xs text-slate-500">
              Scheduled to work on {selectedDate} but not yet assigned to any {direction.toLowerCase()} run.
            </p>

            <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
              {unassignedWorkers.length === 0 ? (
                <div className="p-4 text-center text-xs text-slate-400">
                  <CheckCircle2 className="h-6 w-6 text-emerald-400 mx-auto mb-1" />
                  All scheduled workers are assigned to runs!
                </div>
              ) : (
                unassignedWorkers.map((w) => (
                  <div
                    key={w.employee_id}
                    className="p-2.5 rounded-lg border border-slate-100 bg-slate-50 hover:bg-slate-100 text-xs space-y-1 transition"
                  >
                    <div className="font-bold text-slate-800 flex items-center justify-between">
                      <span>{w.name}</span>
                      <span className="text-[10px] font-mono text-slate-400">{w.tally_id}</span>
                    </div>
                    {w.worksite_name && (
                      <div className="text-slate-600 flex items-center gap-1 text-[11px]">
                        <Building className="h-3 w-3 text-slate-400 shrink-0" />
                        <span className="truncate">{w.worksite_name}</span>
                      </div>
                    )}
                    {w.accommodation_name && (
                      <div className="text-slate-500 flex items-center gap-1 text-[11px]">
                        <Home className="h-3 w-3 text-slate-400 shrink-0" />
                        <span className="truncate">{w.accommodation_name}</span>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* -------------------------------------------------------------------- */}
      {/* Create / Edit Run Modal */}
      {/* -------------------------------------------------------------------- */}
      {isRunModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-5">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="font-bold text-lg text-slate-900">
                {editingRunId ? "Edit Transport Run" : "Create New Transport Run"}
              </h3>
              <button
                onClick={() => setIsRunModalOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                  Driver *
                </label>
                <select
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  value={formDriverId}
                  onChange={(e) => setFormDriverId(e.target.value)}
                >
                  <option value="">Select a designated driver</option>
                  {drivers.map((d) => (
                    <option key={d.employee_id} value={d.employee_id}>
                      {d.name} ({d.tally_id})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                  Vehicle (Optional)
                </label>
                <select
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  value={formVehicleId}
                  onChange={(e) => setFormVehicleId(e.target.value)}
                >
                  <option value="">No vehicle assigned</option>
                  {vehicles.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.label} ({v.type})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Stops Config */}
            <div className="space-y-3 pt-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-bold text-slate-800">
                  Ordered Stops ({formStops.length})
                </label>
                <button
                  type="button"
                  onClick={() =>
                    setFormStops([
                      ...formStops,
                      {
                        sequence: formStops.length + 1,
                        stop_type: "SITE",
                        worksite_id: worksites[0]?.id,
                        passengers: [],
                      },
                    ])
                  }
                  className="text-xs text-blue-600 hover:text-blue-800 font-bold flex items-center gap-1"
                >
                  <Plus className="h-3.5 w-3.5" /> Add Stop
                </button>
              </div>

              <div className="space-y-4">
                {formStops.map((stop, sIdx) => (
                  <div
                    key={sIdx}
                    className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="w-6 h-6 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-xs">
                          {sIdx + 1}
                        </span>
                        <select
                          className="border border-slate-300 bg-white rounded-md text-xs font-bold p-1"
                          value={stop.stop_type}
                          onChange={(e) => {
                            const updated = [...formStops];
                            updated[sIdx].stop_type = e.target.value as "SITE" | "ACCOMMODATION";
                            setFormStops(updated);
                          }}
                        >
                          <option value="ACCOMMODATION">Accommodation (Camp)</option>
                          <option value="SITE">Worksite (Job)</option>
                        </select>
                      </div>

                      <div className="flex items-center gap-2">
                        <input
                          type="time"
                          className="border border-slate-300 rounded p-1 text-xs"
                          value={stop.planned_time || ""}
                          onChange={(e) => {
                            const updated = [...formStops];
                            updated[sIdx].planned_time = e.target.value;
                            setFormStops(updated);
                          }}
                        />
                        <button
                          type="button"
                          onClick={() => {
                            const updated = formStops.filter((_, idx) => idx !== sIdx);
                            setFormStops(updated);
                          }}
                          className="text-red-500 hover:text-red-700"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    </div>

                    {/* Stop Destination Selection */}
                    <div>
                      {stop.stop_type === "ACCOMMODATION" ? (
                        <select
                          className="w-full border border-slate-300 bg-white rounded-lg p-2 text-xs"
                          value={stop.accommodation_id || ""}
                          onChange={(e) => {
                            const updated = [...formStops];
                            updated[sIdx].accommodation_id = e.target.value;
                            setFormStops(updated);
                          }}
                        >
                          {accommodations.map((a) => (
                            <option key={a.id} value={a.id}>
                              {a.name}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <select
                          className="w-full border border-slate-300 bg-white rounded-lg p-2 text-xs"
                          value={stop.worksite_id || ""}
                          onChange={(e) => {
                            const updated = [...formStops];
                            updated[sIdx].worksite_id = e.target.value;
                            setFormStops(updated);
                          }}
                        >
                          {worksites.map((w) => (
                            <option key={w.id} value={w.id}>
                              {w.job_number} - {w.job_name}
                            </option>
                          ))}
                        </select>
                      )}
                    </div>

                    {/* Passengers at this stop */}
                    <div className="space-y-2 pt-2 border-t border-slate-200">
                      <div className="text-xs font-semibold text-slate-700 flex items-center justify-between">
                        <span>Assigned Passengers ({stop.passengers.length})</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {stop.passengers.map((p, pIdx) => (
                          <span
                            key={p.employee_id}
                            className="inline-flex items-center gap-1.5 bg-white border border-slate-300 rounded px-2 py-0.5 text-xs text-slate-800"
                          >
                            <span>{p.name || p.employee_id}</span>
                            <button
                              type="button"
                              onClick={() => removeWorkerFromStop(sIdx, pIdx)}
                              className="text-slate-400 hover:text-red-600 font-bold"
                            >
                              ×
                            </button>
                          </span>
                        ))}
                      </div>

                      {/* Quick Add from Unassigned */}
                      {unassignedWorkers.length > 0 && (
                        <div className="pt-2">
                          <span className="text-[11px] text-slate-500 font-medium mr-2">
                            Add unassigned worker:
                          </span>
                          <div className="flex flex-wrap gap-1 pt-1">
                            {unassignedWorkers.map((u) => (
                              <button
                                key={u.employee_id}
                                type="button"
                                onClick={() => assignWorkerToStop(u, sIdx)}
                                className="px-2 py-0.5 bg-slate-200 hover:bg-blue-100 text-slate-700 hover:text-blue-700 rounded text-[11px] transition"
                              >
                                + {u.name}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t">
              <button
                type="button"
                onClick={() => setIsRunModalOpen(false)}
                className="px-4 py-2 border rounded-lg text-sm text-slate-600 hover:bg-slate-50 font-medium"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveRun}
                className="px-5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-semibold shadow-sm"
              >
                Save Run
              </button>
            </div>
          </div>
        </div>
      )}

      {/* -------------------------------------------------------------------- */}
      {/* Manage Vehicles Modal */}
      {/* -------------------------------------------------------------------- */}
      {isVehicleModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="font-bold text-lg text-slate-900 flex items-center gap-2">
                <Car className="h-5 w-5 text-blue-600" /> Manage Vehicles
              </h3>
              <button
                onClick={() => setIsVehicleModalOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="text"
                  placeholder="Label (e.g. Hiace 01)"
                  className="border rounded p-2 text-xs"
                  value={vehLabel}
                  onChange={(e) => setVehLabel(e.target.value)}
                />
                <select
                  className="border rounded p-2 text-xs"
                  value={vehType}
                  onChange={(e) => setVehType(e.target.value)}
                >
                  <option value="VAN">Van / Minibus</option>
                  <option value="BUS">Bus</option>
                  <option value="OTHER">Other</option>
                </select>
              </div>
              <input
                type="text"
                placeholder="Optional notes or capacity"
                className="w-full border rounded p-2 text-xs"
                value={vehNotes}
                onChange={(e) => setVehNotes(e.target.value)}
              />
              <button
                type="button"
                onClick={handleCreateVehicle}
                className="w-full py-2 bg-blue-600 text-white rounded text-xs font-semibold hover:bg-blue-700 transition"
              >
                + Add Vehicle
              </button>
            </div>

            <div className="border-t pt-3 space-y-2 max-h-60 overflow-y-auto">
              <span className="text-xs font-bold text-slate-500 uppercase">Registered Fleet ({vehicles.length})</span>
              {vehicles.map((v) => (
                <div key={v.id} className="p-2 border rounded flex items-center justify-between text-xs">
                  <div>
                    <span className="font-bold text-slate-800">{v.label}</span>
                    <span className="ml-2 text-slate-400">({v.type})</span>
                    {v.notes && <p className="text-[11px] text-slate-500 mt-0.5">{v.notes}</p>}
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      v.is_active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-400"
                    }`}
                  >
                    {v.is_active ? "Active" : "Inactive"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* -------------------------------------------------------------------- */}
      {/* Copy Runs Modal */}
      {/* -------------------------------------------------------------------- */}
      {isCopyModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="font-bold text-lg text-slate-900 flex items-center gap-2">
                <Copy className="h-5 w-5 text-blue-600" /> Copy Day Runs Forward
              </h3>
              <button
                onClick={() => {
                  setIsCopyModalOpen(false);
                  setCopyOmittedResult(null);
                }}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {copyOmittedResult ? (
              <div className="space-y-3">
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900 space-y-1">
                  <div className="font-bold flex items-center gap-1.5 text-amber-800">
                    <AlertTriangle className="h-4 w-4" /> Copy Finished with Omissions
                  </div>
                  <p>
                    Runs copied forward to {copyTargetDate}. The following workers were omitted from the runs because they are not scheduled or on leave:
                  </p>
                </div>

                <div className="max-h-56 overflow-y-auto space-y-1.5 text-xs">
                  {copyOmittedResult.map((o, idx) => (
                    <div key={idx} className="p-2 border rounded bg-slate-50 flex items-center justify-between">
                      <span className="font-medium text-slate-800">{o.name}</span>
                      <span className="text-slate-500 italic text-[11px]">{o.reason}</span>
                    </div>
                  ))}
                </div>

                <button
                  type="button"
                  onClick={() => {
                    setIsCopyModalOpen(false);
                    setCopyOmittedResult(null);
                  }}
                  className="w-full py-2 bg-blue-600 text-white rounded text-sm font-semibold"
                >
                  Done
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="text-xs text-slate-600">
                  Copy all {runs.length} runs from <strong className="text-slate-900">{selectedDate}</strong> forward to:
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                    Target Date
                  </label>
                  <input
                    type="date"
                    className="w-full border rounded-lg p-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                    value={copyTargetDate}
                    onChange={(e) => setCopyTargetDate(e.target.value)}
                  />
                </div>

                <p className="text-xs text-slate-500">
                  Workers not scheduled or on leave on the target date will be omitted with explicit reasons.
                </p>

                <div className="flex items-center justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsCopyModalOpen(false)}
                    className="px-3 py-1.5 border rounded-lg text-xs text-slate-600 hover:bg-slate-50 font-medium"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleCopyRuns}
                    className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-sm"
                  >
                    Confirm Copy
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* -------------------------------------------------------------------- */}
      {/* Printable Run Sheet Dialog */}
      {/* -------------------------------------------------------------------- */}
      {printRun && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full max-h-[95vh] overflow-y-auto p-8 space-y-6">
            <div className="flex items-center justify-between border-b pb-4 print:hidden">
              <div className="flex items-center gap-2">
                <Printer className="h-5 w-5 text-blue-600" />
                <h3 className="font-bold text-lg text-slate-900">Print Driver Run Sheet</h3>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => window.print()}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-semibold flex items-center gap-1.5 shadow-sm"
                >
                  <Printer className="h-4 w-4" /> Print Document
                </button>
                <button
                  type="button"
                  onClick={() => setPrintRun(null)}
                  className="p-2 border rounded-lg text-slate-500 hover:text-slate-800"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            {/* Actual Printable Page Layout */}
            <div className="border border-slate-300 p-8 rounded-lg bg-white space-y-6 text-slate-900 printable-area">
              {/* Header */}
              <div className="border-b-2 border-slate-800 pb-4 flex items-center justify-between">
                <div>
                  <h1 className="text-2xl font-black tracking-tight uppercase">Driver Run Sheet</h1>
                  <p className="text-xs text-slate-500 tracking-wider uppercase mt-0.5">
                    Field Worker Tracker • Operational Transportation Manifest
                  </p>
                </div>
                <div className="text-right">
                  <div className="text-lg font-bold">{printRun.run_date}</div>
                  <div className="text-xs font-semibold px-2 py-0.5 bg-slate-100 rounded inline-block mt-0.5">
                    {printRun.direction} RUN
                  </div>
                </div>
              </div>

              {/* Manifest Info */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 bg-slate-50 rounded-lg border border-slate-200 text-xs">
                <div>
                  <span className="font-bold text-slate-500 uppercase block">Driver</span>
                  <span className="text-sm font-bold text-slate-900">{printRun.driver_name}</span>
                  <span className="text-slate-500 block">ID: {printRun.driver_tally_id || "N/A"}</span>
                </div>
                <div>
                  <span className="font-bold text-slate-500 uppercase block">Contact Phone</span>
                  <span className="text-sm font-semibold text-slate-800">{printRun.driver_phone || "Not recorded"}</span>
                </div>
                <div>
                  <span className="font-bold text-slate-500 uppercase block">Assigned Vehicle</span>
                  <span className="text-sm font-bold text-slate-900">{printRun.vehicle_label || "Unassigned"}</span>
                </div>
                <div>
                  <span className="font-bold text-slate-500 uppercase block">Total Passengers</span>
                  <span className="text-sm font-bold text-blue-700">{printRun.total_passengers} Workers</span>
                </div>
              </div>

              {/* Stops & Passengers Table */}
              <div className="space-y-4">
                <h3 className="font-bold text-sm uppercase tracking-wider text-slate-700">
                  Route Sequence & Passenger Manifest
                </h3>
                <div className="space-y-4">
                  {printRun.stops.map((stop) => (
                    <div
                      key={stop.id}
                      className="border border-slate-300 rounded-lg overflow-hidden text-xs"
                    >
                      <div className="bg-slate-100 p-2.5 font-bold flex items-center justify-between border-b border-slate-300">
                        <div className="flex items-center gap-2">
                          <span className="w-5 h-5 rounded-full bg-slate-900 text-white flex items-center justify-center text-[10px]">
                            {stop.sequence}
                          </span>
                          <span className="text-sm">
                            {stop.stop_type === "ACCOMMODATION" ? "Camp Origin:" : "Site Destination:"}{" "}
                            {stop.stop_type === "ACCOMMODATION"
                              ? stop.accommodation_name
                              : stop.worksite_name}
                          </span>
                        </div>
                        {stop.planned_time && (
                          <span className="font-mono text-slate-600">Planned Time: {stop.planned_time}</span>
                        )}
                      </div>

                      <div className="p-3">
                        <table className="w-full text-left">
                          <thead>
                            <tr className="border-b text-slate-500 font-bold text-[11px]">
                              <th className="pb-1 w-12">Check</th>
                              <th className="pb-1 w-24">Worker ID</th>
                              <th className="pb-1">Worker Name</th>
                              <th className="pb-1">Contact Phone</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {stop.passengers.length === 0 ? (
                              <tr>
                                <td colSpan={4} className="py-2 text-slate-400 italic">
                                  No passengers at this stop.
                                </td>
                              </tr>
                            ) : (
                              stop.passengers.map((p) => (
                                <tr key={p.employee_id} className="hover:bg-slate-50">
                                  <td className="py-2">
                                    <div className="w-4 h-4 border border-slate-400 rounded-xs" />
                                  </td>
                                  <td className="py-2 font-mono font-medium text-slate-600">
                                    {p.tally_id}
                                  </td>
                                  <td className="py-2 font-bold text-slate-900">{p.name}</td>
                                  <td className="py-2 text-slate-600">{p.phone || "—"}</td>
                                </tr>
                              ))
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Signatures */}
              <div className="pt-8 border-t grid grid-cols-2 gap-8 text-xs">
                <div>
                  <div className="border-b border-slate-400 pb-8" />
                  <span className="font-bold text-slate-700 mt-1 block">Driver Signature & Date</span>
                </div>
                <div>
                  <div className="border-b border-slate-400 pb-8" />
                  <span className="font-bold text-slate-700 mt-1 block">Supervisor Verification</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
