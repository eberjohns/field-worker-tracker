import React, { useState, useEffect, useMemo } from "react";
import { useAuth } from "../context/AuthContext";
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Users,
  Building2,
  AlertTriangle,
  CheckCircle2,
  Trash2,
  X,
  Loader2,
  Search,
  UserCheck,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import {
  OperationalCoverageResponse,
  OperationalWorksiteRow,
  OperationalJobItemRow,
  OperationalDayCell,
  OperationalRosterResponse,
  OperationalShiftCreate,
  CandidateRecommendation,
} from "../features/planner/types";

function formatReadableWeek(weekStartStr: string): string {
  try {
    const parts = weekStartStr.split("-").map(Number);
    const start = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
    const end = new Date(start);
    end.setUTCDate(start.getUTCDate() + 6);

    const monthName = start.toLocaleString("en-US", { month: "short", timeZone: "UTC" }).toUpperCase();
    const year = start.getUTCFullYear();
    const dayOfMonth = start.getUTCDate();
    const weekNum = Math.ceil(dayOfMonth / 7);

    const startDay = String(start.getUTCDate()).padStart(2, "0");
    const endDay = String(end.getUTCDate()).padStart(2, "0");
    const endMonth = end.toLocaleString("en-US", { month: "short", timeZone: "UTC" });

    return `Week ${weekNum} - ${monthName} ${year} (${startDay} - ${endDay} ${endMonth})`;
  } catch {
    return `Week of ${weekStartStr}`;
  }
}

interface SupervisorOption {
  id: string;
  name: string;
  tally_id?: string;
}

export const OperationalPlanner: React.FC = () => {
  const { token } = useAuth();

  // Navigation & Lens
  const [activeLens, setActiveLens] = useState<"COVERAGE" | "ROSTER">("COVERAGE");
  const [weekStartDate, setWeekStartDate] = useState<string>(() => {
    const now = new Date();
    const day = now.getDay();
    const diff = now.getDate() - day + (day === 0 ? -6 : 1);
    const monday = new Date(now.setDate(diff));
    return monday.toISOString().split("T")[0];
  });

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Supervisor filter
  const [supervisorsList, setSupervisorsList] = useState<SupervisorOption[]>([]);
  const [selectedSupervisorId, setSelectedSupervisorId] = useState<string>("");

  // Data states
  const [coverageData, setCoverageData] = useState<OperationalCoverageResponse | null>(null);
  const [rosterData, setRosterData] = useState<OperationalRosterResponse | null>(null);

  // Modal State for Operational Action
  const [selectedCell, setSelectedCell] = useState<{
    worksite: OperationalWorksiteRow;
    item: OperationalJobItemRow;
    cell: OperationalDayCell;
  } | null>(null);

  const [selectedWorkerId, setSelectedWorkerId] = useState<string>("");
  const [replacementTargetId, setReplacementTargetId] = useState<string | null>(null);
  const [shiftHours, setShiftHours] = useState<string>("8.0");
  const [overrideReason, setOverrideReason] = useState<string>("");
  const [candidates, setCandidates] = useState<CandidateRecommendation[]>([]);
  const [candidateSearch, setCandidateSearch] = useState<string>("");
  const [filterToSupervisorCrew, setFilterToSupervisorCrew] = useState<boolean>(true);
  const [loadingCandidates, setLoadingCandidates] = useState<boolean>(false);
  const [savingShift, setSavingShift] = useState<boolean>(false);

  // Fetch Operational Data
  const fetchOperationalData = async () => {
    setLoading(true);
    setError(null);
    try {
      if (activeLens === "COVERAGE") {
        const res = await fetch(
          `/api/v1/operational-planner/coverage?week_start=${weekStartDate}`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (!res.ok) throw new Error("Failed to load Operational Coverage");
        const data: OperationalCoverageResponse = await res.json();
        setCoverageData(data);
      } else {
        const res = await fetch(
          `/api/v1/operational-planner/roster?week_start=${weekStartDate}`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (!res.ok) throw new Error("Failed to load Operational Roster");
        const data: OperationalRosterResponse = await res.json();
        setRosterData(data);
      }
    } catch (err: any) {
      setError(err.message || "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  // Fetch Supervisors
  const fetchSupervisors = async () => {
    try {
      const res = await fetch("/api/v1/employees?role=SUPERVISOR&limit=200", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        const items = data.items || data || [];
        const list: SupervisorOption[] = items.map((emp: any) => ({
          id: emp.id,
          name: emp.name || emp.tally_id || "Supervisor",
          tally_id: emp.tally_id,
        }));
        setSupervisorsList(list);
      }
    } catch (e) {
      console.error("Failed to fetch supervisors:", e);
    }
  };

  useEffect(() => {
    if (token) {
      fetchOperationalData();
      fetchSupervisors();
    }
  }, [token, weekStartDate, activeLens]);

  // Week navigation helpers
  const handlePrevWeek = () => {
    const parts = weekStartDate.split("-").map(Number);
    const d = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2] - 7));
    setWeekStartDate(d.toISOString().split("T")[0]);
  };

  const handleNextWeek = () => {
    const parts = weekStartDate.split("-").map(Number);
    const d = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2] + 7));
    setWeekStartDate(d.toISOString().split("T")[0]);
  };

  const handleCurrentWeek = () => {
    const now = new Date();
    const day = now.getDay();
    const diff = now.getDate() - day + (day === 0 ? -6 : 1);
    const monday = new Date(now.setDate(diff));
    setWeekStartDate(monday.toISOString().split("T")[0]);
  };

  // Open operational action modal on cell click
  const handleCellClick = async (
    ws: OperationalWorksiteRow,
    it: OperationalJobItemRow,
    cell: OperationalDayCell
  ) => {
    setSelectedCell({ worksite: ws, item: it, cell });
    setSelectedWorkerId("");
    setReplacementTargetId(null);
    setShiftHours(String(it.hours_per_occurrence || "8.0"));
    setOverrideReason("");
    setCandidateSearch("");
    setFilterToSupervisorCrew(Boolean(selectedSupervisorId));

    // Load candidate recommendations for this item
    setLoadingCandidates(true);
    try {
      const res = await fetch(
        `/api/v1/job-items/${it.job_item_id}/recommendations?date=${cell.work_date}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) {
        const data = await res.json();
        setCandidates(data || []);
      }
    } catch (e) {
      console.error("Failed to load candidates", e);
    } finally {
      setLoadingCandidates(false);
    }
  };

  // Create Operational Shift / Cover
  const handleCreateShift = async () => {
    if (!selectedCell || !selectedWorkerId) return;
    setSavingShift(true);
    try {
      const isReplacement = !!replacementTargetId;
      const payload: OperationalShiftCreate = {
        job_item_id: selectedCell.item.job_item_id,
        work_date: selectedCell.cell.work_date,
        employee_id: selectedWorkerId,
        original_employee_id: replacementTargetId || undefined,
        assigned_hours: Number(shiftHours),
        override_reason: overrideReason || (isReplacement ? "Leave Cover" : "Single-day assignment"),
        source: isReplacement ? "OVERRIDE" : "DIRECT",
        acknowledge_warnings: true,
      };

      const res = await fetch("/api/v1/operational-planner/shifts", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || "Failed to create shift");
      }

      await fetchOperationalData();
      setSelectedCell(null);
    } catch (err: any) {
      alert(`Error creating shift: ${err.message}`);
    } finally {
      setSavingShift(false);
    }
  };

  // Cancel Operational Shift
  const handleDeleteShift = async (shiftId: string) => {
    if (!confirm("Are you sure you want to cancel this operational shift?")) return;
    try {
      const res = await fetch(`/api/v1/operational-planner/shifts/${shiftId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to delete shift");
      await fetchOperationalData();
      setSelectedCell(null);
    } catch (err: any) {
      alert(`Error cancelling shift: ${err.message}`);
    }
  };

  // Filter worksites in Coverage View
  const filteredCoverageWorksites = useMemo(() => {
    if (!coverageData) return [];
    const q = searchQuery.toLowerCase().trim();
    if (!q) return coverageData.worksites;
    return coverageData.worksites.filter(
      (ws) =>
        ws.job_number.toLowerCase().includes(q) ||
        ws.job_name.toLowerCase().includes(q) ||
        (ws.customer_type && ws.customer_type.toLowerCase().includes(q))
    );
  }, [coverageData, searchQuery]);

  // Filter candidates in modal
  const filteredCandidates = useMemo(() => {
    let pool = candidates;

    if (filterToSupervisorCrew && selectedSupervisorId) {
      pool = pool.filter((c) => c.supervisor_id === selectedSupervisorId);
    }

    const q = candidateSearch.toLowerCase().trim();
    if (q) {
      pool = pool.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          c.tally_id.toLowerCase().includes(q) ||
          (c.staff_grade_description && c.staff_grade_description.toLowerCase().includes(q))
      );
    }

    return [...pool].sort((a, b) => {
      if (a.exact_staff_type_match !== b.exact_staff_type_match) {
        return a.exact_staff_type_match ? -1 : 1;
      }
      return (b.ranking_score || 0) - (a.ranking_score || 0);
    });
  }, [candidates, candidateSearch, filterToSupervisorCrew, selectedSupervisorId]);

  const selectedCandidateObj = useMemo(() => {
    return candidates.find((c) => c.employee_id === selectedWorkerId);
  }, [candidates, selectedWorkerId]);

  return (
    <div className="flex flex-col h-full bg-slate-50">
      {/* Top Controls Bar - Light Enterprise Styling */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 sticky top-0 z-20">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <CalendarDays className="h-6 w-6 text-indigo-600" />
              <h1 className="text-xl font-bold text-slate-900">
                Operational Planner (Live Daily Schedule)
              </h1>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                Live Operations
              </span>
            </div>
            <p className="text-sm text-slate-500 mt-1">
              Active shifts, leave covers, and operational adjustments. Base blueprint shifts appear muted; operational overrides appear solid.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Lens Switcher */}
            <div className="bg-slate-100 p-1 rounded-lg flex items-center text-xs font-semibold">
              <button
                type="button"
                onClick={() => setActiveLens("COVERAGE")}
                className={`px-3 py-1.5 rounded-md transition-all flex items-center gap-1.5 ${
                  activeLens === "COVERAGE"
                    ? "bg-white text-indigo-700 shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <Building2 className="h-3.5 w-3.5" />
                Coverage View (Jobs)
              </button>
              <button
                type="button"
                onClick={() => setActiveLens("ROSTER")}
                className={`px-3 py-1.5 rounded-md transition-all flex items-center gap-1.5 ${
                  activeLens === "ROSTER"
                    ? "bg-white text-indigo-700 shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <Users className="h-3.5 w-3.5" />
                Worker Roster
              </button>
            </div>

            {/* Supervisor Crew Filter Dropdown */}
            <div className="flex items-center gap-2 bg-white border border-slate-200 rounded-lg px-3 py-1.5 shadow-sm">
              <UserCheck className="h-4 w-4 text-slate-400" />
              <span className="text-xs font-semibold text-slate-700">Supervisor Crew:</span>
              <select
                value={selectedSupervisorId}
                onChange={(e) => setSelectedSupervisorId(e.target.value)}
                className="text-xs bg-transparent border-0 font-medium text-slate-800 focus:outline-none cursor-pointer"
              >
                <option value="">All Crews (Company-Wide)</option>
                {supervisorsList.map((sup) => (
                  <option key={sup.id} value={sup.id}>
                    {sup.name} ({sup.tally_id || "Crew"})
                  </option>
                ))}
              </select>
            </div>

            {/* Week Navigator */}
            <div className="flex items-center gap-1 bg-white border border-slate-200 rounded-lg p-1 shadow-sm">
              <button
                onClick={handlePrevWeek}
                title="Previous Week"
                className="p-1 rounded hover:bg-slate-100 text-slate-600"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="font-semibold text-xs px-2 text-slate-800">
                {formatReadableWeek(weekStartDate)}
              </span>
              <button
                onClick={handleNextWeek}
                title="Next Week"
                className="p-1 rounded hover:bg-slate-100 text-slate-600"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
              <button
                onClick={handleCurrentWeek}
                className="ml-1 text-[11px] font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700 hover:bg-slate-200"
              >
                Current Week
              </button>
            </div>

            {/* Worksite Search */}
            {activeLens === "COVERAGE" && (
              <div className="relative w-56">
                <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search worksite..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-sm"
                />
              </div>
            )}
          </div>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 mt-3 pt-3 border-t border-slate-100">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-indigo-50 border border-dashed border-indigo-400 opacity-60"></span>
            <span>Base Blueprint (Muted)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-indigo-600 shadow-sm"></span>
            <span className="font-semibold text-slate-700">Operational Override / Cover (Solid)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-amber-50 border border-dashed border-amber-400"></span>
            <span className="text-amber-700 font-semibold">TO_BE_COVERED (Leave Gap)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
            <span className="text-emerald-700 font-medium">Quota Met</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-purple-100 text-purple-700">Excess</span>
            <span>Excess Visit</span>
          </div>
        </div>
      </header>

      {/* Main Grid Content */}
      <main className="flex-1 overflow-auto p-6 space-y-6">
        {loading ? (
          <div className="flex flex-col items-center justify-center h-64 text-slate-400">
            <Loader2 className="h-8 w-8 animate-spin mb-2" />
            <p className="text-sm font-medium">Loading Operational Schedule...</p>
          </div>
        ) : error ? (
          <div className="p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">
            {error}
          </div>
        ) : activeLens === "COVERAGE" && coverageData ? (
          /* Coverage Matrix View */
          <div className="space-y-6">
            {filteredCoverageWorksites.map((ws) => (
              <div
                key={ws.worksite_id}
                className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden"
              >
                {/* Worksite Banner Bar */}
                <div className="px-6 py-3.5 bg-slate-50 border-b border-slate-200 flex flex-col md:flex-row md:items-center justify-between gap-3">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2.5">
                      <span className="font-mono text-sm font-bold text-indigo-600">
                        {ws.job_number}
                      </span>
                      <h2 className="text-sm font-bold text-slate-900">
                        {ws.job_name}
                      </h2>
                      {ws.customer_type && (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-slate-200 text-slate-700 font-medium">
                          {ws.customer_type}
                        </span>
                      )}
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded font-medium ${
                          ws.is_outdoor
                            ? "bg-amber-100 text-amber-800"
                            : "bg-blue-100 text-blue-800"
                        }`}
                      >
                        {ws.is_outdoor ? "Outdoor Site" : "Indoor Site"}
                      </span>
                    </div>

                    <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 pt-0.5">
                      <div>
                        <span className="font-medium text-slate-700">Contract Validity:</span>{" "}
                        {ws.start_date || "N/A"} to {ws.end_date || "Ongoing"}
                      </div>
                      <div>
                        <span className="font-medium text-slate-700">Annual Budget:</span>{" "}
                        {ws.budget_amount ? `${Number(ws.budget_amount).toLocaleString()} AED / yr` : "Not specified"}
                      </div>
                      <div>
                        <span className="font-medium text-slate-700">Items:</span> {ws.items.length} contract lines
                      </div>
                    </div>
                  </div>
                </div>

                {/* 7-Day Coverage Table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="bg-slate-100/70 text-slate-500 border-b border-slate-200">
                        <th className="px-4 py-2.5 font-semibold w-72">Job Item & Quota</th>
                        {ws.items[0]?.days.map((d) => (
                          <th
                            key={d.work_date}
                            className={`px-3 py-2 text-center border-l border-slate-200 min-w-[130px] ${
                              d.is_public_holiday ? "bg-sky-50" : ""
                            }`}
                          >
                            <div className="font-bold text-slate-800">{d.weekday}</div>
                            <div className="text-[10px] text-slate-400">{d.work_date.slice(5)}</div>
                            {d.is_public_holiday && (
                              <div
                                className="text-[9px] font-bold text-sky-800 truncate max-w-[120px] mx-auto mt-0.5 bg-sky-100/80 px-1 py-0.2 rounded border border-sky-200"
                                title={d.holiday_name || "Public Holiday"}
                              >
                                {d.holiday_name || "Holiday"}
                              </div>
                            )}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {ws.items.map((it) => (
                        <tr key={it.job_item_id} className="hover:bg-slate-50/50 transition-colors">
                          {/* Item Info Column */}
                          <td className="px-4 py-3">
                            <div className="font-semibold text-slate-900 flex items-center gap-1.5">
                              <span className="font-mono text-indigo-600">{it.sub_item_code}</span>
                              <span>{it.staff_grade_description}</span>
                            </div>
                            <div className="text-[11px] text-slate-500 mt-0.5">
                              Quota: {it.quota_assigned} / {it.quota_target} {it.frequency_unit.toLowerCase()} visits
                            </div>
                            <div className="flex items-center gap-1.5 mt-1">
                              {it.quota_satisfied && (
                                <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.2 rounded border border-emerald-200">
                                  <CheckCircle2 className="h-3 w-3" /> Quota Met
                                </span>
                              )}
                              <span className="text-[10px] text-slate-400">
                                {it.required_staff_count} staff • {it.hours_per_occurrence}h/visit
                              </span>
                            </div>
                          </td>

                          {/* 7 Daily Cells */}
                          {it.days.map((cell) => {
                            const isExcess = cell.is_excess;
                            const hasCoverIssue = cell.is_to_be_covered;

                            return (
                              <td
                                key={cell.work_date}
                                onClick={() => handleCellClick(ws, it, cell)}
                                className={`px-2 py-2 border-l border-slate-200 cursor-pointer transition-colors relative hover:bg-indigo-50/60 ${
                                  cell.is_public_holiday ? "bg-sky-50/40" : ""
                                }`}
                              >
                                <div className="space-y-1 min-h-[52px] flex flex-col justify-between">
                                  {/* Badges top */}
                                  <div className="flex items-center justify-between gap-1 text-[9px]">
                                    {isExcess && (
                                      <span className="font-bold px-1.5 py-0.2 rounded bg-purple-100 text-purple-700">
                                        Excess
                                      </span>
                                    )}
                                    {cell.is_quota_met && (
                                      <CheckCircle2 className="h-3 w-3 text-emerald-600 ml-auto" />
                                    )}
                                  </div>

                                  {/* Workers List */}
                                  {cell.workers.length > 0 ? (
                                    <div className="space-y-1">
                                      {cell.workers.map((w, idx) => {
                                        const isWarning = w.opacity_class === "warning";
                                        const isSolid = w.opacity_class === "solid";

                                        if (isWarning) {
                                          return (
                                            <div
                                              key={idx}
                                              className="p-1 rounded text-[10px] font-semibold bg-amber-50 text-amber-900 border border-dashed border-amber-400 flex items-center justify-between"
                                            >
                                              <span className="truncate">{w.employee_name}</span>
                                              <AlertTriangle className="h-3 w-3 text-amber-500 shrink-0" />
                                            </div>
                                          );
                                        }

                                        return (
                                          <div
                                            key={idx}
                                            className={`p-1 rounded text-[10px] font-medium flex items-center justify-between ${
                                              isSolid
                                                ? "bg-indigo-600 text-white shadow-sm font-semibold"
                                                : "bg-indigo-50 text-indigo-900 border border-dashed border-indigo-300 opacity-60"
                                            }`}
                                          >
                                            <span className="truncate max-w-[90px]" title={w.employee_name}>
                                              {w.employee_name}
                                            </span>
                                            {isSolid && (
                                              <span className="text-[8px] bg-indigo-700 px-1 rounded uppercase">
                                                Cover
                                              </span>
                                            )}
                                          </div>
                                        );
                                      })}
                                    </div>
                                  ) : (
                                    <div className="text-[10px] text-slate-300 text-center py-2">—</div>
                                  )}

                                  {/* Bottom status */}
                                  {hasCoverIssue && (
                                    <div className="text-[9px] font-bold text-amber-700 text-center">
                                      Needs Cover
                                    </div>
                                  )}
                                </div>
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        ) : activeLens === "ROSTER" && rosterData ? (
          /* Worker Roster View */
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-100/70 text-slate-500 border-b border-slate-200">
                    <th className="px-4 py-3 font-semibold w-64">Worker & Total Hours</th>
                    {rosterData.workers[0]?.days.map((d) => (
                      <th
                        key={d.work_date}
                        className={`px-3 py-2 text-center border-l border-slate-200 min-w-[110px] ${
                          d.is_public_holiday ? "bg-sky-50" : ""
                        }`}
                      >
                        <div className="font-bold text-slate-800">{d.weekday}</div>
                        <div className="text-[10px] text-slate-400">{d.work_date.slice(5)}</div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {rosterData.workers.map((w) => (
                    <tr key={w.employee_id} className="hover:bg-slate-50/50">
                      <td className="px-4 py-3">
                        <div className="font-bold text-slate-900 flex items-center gap-1.5">
                          <span>{w.name}</span>
                          <span className="font-mono text-[10px] text-slate-400">({w.tally_id})</span>
                        </div>
                        <div className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-2">
                          <span>{w.staff_grade_description || "Worker"}</span>
                          <span>•</span>
                          <span className="font-semibold text-indigo-600">
                            {w.total_week_hours} / {w.standard_week_hours} hrs
                          </span>
                        </div>
                      </td>

                      {w.days.map((d) => (
                        <td
                          key={d.work_date}
                          className={`px-2 py-2 border-l border-slate-200 text-center ${
                            d.is_weekly_off ? "bg-slate-50 text-slate-400" : ""
                          }`}
                        >
                          {d.is_weekly_off ? (
                            <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-slate-200 text-slate-600">
                              WEEKLY OFF
                            </span>
                          ) : d.shifts.length > 0 ? (
                            <div className="space-y-1">
                              {d.shifts.map((s, idx) => (
                                <div
                                  key={idx}
                                  className={`p-1 rounded text-[10px] font-semibold ${
                                    s.opacity_class === "solid"
                                      ? "bg-indigo-600 text-white shadow-sm"
                                      : "bg-indigo-50 text-indigo-900 border border-indigo-200 opacity-60"
                                  }`}
                                >
                                  {s.assigned_hours}h Shift
                                </div>
                              ))}
                            </div>
                          ) : (
                            <span className="text-slate-300 text-[10px]">—</span>
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </main>

      {/* Single-Action Operational Modal - Light Theme Enterprise */}
      {selectedCell && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 w-full max-w-xl max-h-[90vh] flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div>
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <CalendarDays className="h-5 w-5 text-indigo-600" />
                  Operational Shift Action
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  {selectedCell.cell.weekday} {selectedCell.cell.work_date} • {selectedCell.worksite.job_number} (
                  {selectedCell.item.sub_item_code} - {selectedCell.item.staff_grade_description})
                </p>
              </div>

              <button
                onClick={() => setSelectedCell(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-4 flex-1 overflow-y-auto">
              {/* Existing Assigned Workers in Slot */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase text-slate-600">
                  Currently Scheduled Staff ({selectedCell.cell.workers.length})
                </h4>

                {selectedCell.cell.workers.length === 0 ? (
                  <p className="text-xs text-slate-400 italic">No workers currently scheduled for this slot.</p>
                ) : (
                  <div className="space-y-1.5">
                    {selectedCell.cell.workers.map((w, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-2.5 rounded-lg border border-slate-200 bg-slate-50"
                      >
                        <div>
                          <div className="text-xs font-bold text-slate-900 flex items-center gap-2">
                            <span>{w.employee_name}</span>
                            <span className="text-[10px] px-1.5 py-0.2 rounded font-bold bg-slate-200 text-slate-700">
                              {w.display_type}
                            </span>
                          </div>
                          <div className="text-[11px] text-slate-500 mt-0.5">
                            {w.assigned_hours} hrs • {w.reason || "Standard shift"}
                          </div>
                        </div>

                        {w.shift_id ? (
                          <button
                            onClick={() => handleDeleteShift(w.shift_id!)}
                            className="p-1.5 rounded text-red-600 hover:bg-red-50 text-xs font-semibold flex items-center gap-1"
                          >
                            <Trash2 className="h-3.5 w-3.5" /> Remove Shift
                          </button>
                        ) : (
                          <button
                            onClick={() => setReplacementTargetId(w.employee_id)}
                            className="px-2.5 py-1 rounded bg-indigo-50 text-indigo-700 text-xs font-semibold hover:bg-indigo-100 border border-indigo-200"
                          >
                            Replace with Cover
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Public Holiday Warning Banner */}
              {selectedCell.cell.is_public_holiday && (
                <div className="p-3 rounded-lg bg-sky-50 border border-sky-200 text-xs text-sky-900 flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-sky-600 shrink-0" />
                  <span>
                    <strong>Public Holiday:</strong> {selectedCell.cell.holiday_name || "Public Holiday"}. Statutory holiday overtime rates apply.
                  </span>
                </div>
              )}

              {/* Form: Assign Shift / Cover */}
              <div className="pt-3 border-t border-slate-200 space-y-3">
                <h4 className="text-xs font-bold uppercase text-slate-600">
                  {replacementTargetId ? "Assign Replacement Cover Worker" : "Assign Single-Day Operational Shift"}
                </h4>

                {replacementTargetId && (
                  <div className="p-2.5 rounded-lg bg-indigo-50 border border-indigo-200 text-indigo-800 text-xs flex items-center justify-between">
                    <span>
                      Replacing base worker:{" "}
                      <strong>
                        {selectedCell.cell.workers.find((w) => w.employee_id === replacementTargetId)?.employee_name}
                      </strong>
                    </span>
                    <button
                      onClick={() => setReplacementTargetId(null)}
                      className="text-indigo-950 font-bold hover:underline"
                    >
                      Clear
                    </button>
                  </div>
                )}

                {/* Candidate Selection Header with In-Modal Crew Filter */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1">
                  <div className="flex items-center gap-1.5">
                    <Sparkles className="h-4 w-4 text-indigo-600" />
                    <span className="text-xs font-bold text-slate-700">Select Worker</span>
                  </div>

                  {selectedSupervisorId && (
                    <label className="text-xs font-medium text-indigo-700 flex items-center gap-1.5 cursor-pointer bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200">
                      <input
                        type="checkbox"
                        checked={filterToSupervisorCrew}
                        onChange={(e) => setFilterToSupervisorCrew(e.target.checked)}
                        className="rounded border-indigo-300 text-indigo-600 focus:ring-indigo-500 h-3.5 w-3.5"
                      />
                      <span>Filter to Selected Supervisor's Crew</span>
                    </label>
                  )}
                </div>

                {/* Candidate Search */}
                <div className="relative">
                  <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
                  <input
                    type="text"
                    placeholder="Search candidate by name, ID or grade..."
                    value={candidateSearch}
                    onChange={(e) => setCandidateSearch(e.target.value)}
                    className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                {/* Candidate List */}
                {loadingCandidates ? (
                  <div className="text-xs text-slate-400 py-3 text-center">Loading candidates...</div>
                ) : (
                  <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                    {filteredCandidates.map((cand) => {
                      const isSelected = selectedWorkerId === cand.employee_id;
                      const isOffDay = (cand.weekly_off_day || "").toUpperCase() === selectedCell.cell.weekday;

                      return (
                        <div
                          key={cand.employee_id}
                          onClick={() => setSelectedWorkerId(cand.employee_id)}
                          className={`p-2 rounded-lg border cursor-pointer flex items-center justify-between text-xs transition-colors ${
                            isSelected
                              ? "bg-indigo-50 border-indigo-400 text-indigo-900 font-semibold"
                              : "bg-white border-slate-200 hover:border-indigo-300 text-slate-800"
                          }`}
                        >
                          <div>
                            <div className="flex items-center gap-2">
                              <span>{cand.name}</span>
                              <span className="font-mono text-[10px] text-slate-400">({cand.tally_id})</span>
                              {cand.exact_staff_type_match && (
                                <span className="text-[9px] font-bold text-amber-700 bg-amber-50 px-1 rounded">
                                  * Exact Match
                                </span>
                              )}
                            </div>
                            <div className="text-[10px] text-slate-500 flex items-center gap-2 mt-0.5">
                              <span>{cand.staff_grade_description}</span>
                              <span>•</span>
                              <span className={isOffDay ? "text-amber-700 font-bold" : ""}>
                                Off: {cand.weekly_off_day || "None"}
                              </span>
                            </div>
                          </div>

                          <button
                            type="button"
                            className={`px-2.5 py-1 rounded text-[11px] font-semibold ${
                              isSelected
                                ? "bg-indigo-600 text-white"
                                : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                            }`}
                          >
                            {isSelected ? "Selected" : "Select"}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Rest day warning for selected worker */}
                {selectedCandidateObj &&
                  selectedCandidateObj.weekly_off_day?.toUpperCase() === selectedCell.cell.weekday && (
                    <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800 flex items-center gap-2">
                      <ShieldAlert className="h-4 w-4 text-amber-600 shrink-0" />
                      <span>
                        <strong>Rest Day Overtime:</strong> {selectedCandidateObj.name} has their weekly off on {selectedCell.cell.weekday}. Statutory overtime will apply.
                      </span>
                    </div>
                  )}

                <div className="grid grid-cols-2 gap-3 pt-1">
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">
                      Assigned Hours
                    </label>
                    <input
                      type="number"
                      step="0.5"
                      value={shiftHours}
                      onChange={(e) => setShiftHours(e.target.value)}
                      className="w-full text-xs py-2 px-3 rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">
                      Reason / Note
                    </label>
                    <input
                      type="text"
                      placeholder={replacementTargetId ? "Sick leave cover" : "Extra shift"}
                      value={overrideReason}
                      onChange={(e) => setOverrideReason(e.target.value)}
                      className="w-full text-xs py-2 px-3 rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setSelectedCell(null)}
                className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-200 transition-colors"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={handleCreateShift}
                disabled={savingShift || !selectedWorkerId}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-1.5 shadow-sm transition-colors"
              >
                {savingShift && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                {replacementTargetId ? "Confirm Replacement Cover" : "Assign Operational Shift"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
