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
  Calendar,
  ShieldAlert,
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

  useEffect(() => {
    if (token) {
      fetchOperationalData();
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

  // Open operational action modal
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

    // Load candidate recommendations for this item
    setLoadingCandidates(true);
    try {
      const res = await fetch(
        `/api/v1/scheduling/suggestions/candidates?job_item_id=${it.job_item_id}&work_date=${cell.work_date}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) {
        const data = await res.json();
        setCandidates(data.candidates || []);
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

  // Candidate worker details for modal warnings
  const selectedCandidateObj = useMemo(() => {
    return candidates.find((c) => c.employee_id === selectedWorkerId);
  }, [candidates, selectedWorkerId]);

  return (
    <div className="flex flex-col h-full bg-slate-50 dark:bg-slate-950">
      {/* Header & Controls Bar */}
      <header className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-6 py-4 sticky top-0 z-20">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <CalendarDays className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
              <h1 className="text-xl font-bold text-slate-900 dark:text-white">
                Operational Planner (Live Daily Schedule)
              </h1>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                Live Operations
              </span>
            </div>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Active shifts, leave covers, and operational adjustments. Base blueprint shifts appear muted; operational overrides appear solid.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Lens Switcher */}
            <div className="bg-slate-100 dark:bg-slate-800 p-1 rounded-lg flex items-center text-xs font-semibold">
              <button
                type="button"
                onClick={() => setActiveLens("COVERAGE")}
                className={`px-3 py-1.5 rounded-md transition-all flex items-center gap-1.5 ${
                  activeLens === "COVERAGE"
                    ? "bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-sm"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
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
                    ? "bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-sm"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
                }`}
              >
                <Users className="h-3.5 w-3.5" />
                Worker Roster
              </button>
            </div>

            {/* Week Navigator */}
            <div className="flex items-center gap-1 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg p-1 shadow-sm">
              <button
                onClick={handlePrevWeek}
                title="Previous Week"
                className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="font-semibold text-xs px-2 text-slate-800 dark:text-slate-200">
                {formatReadableWeek(weekStartDate)}
              </span>
              <button
                onClick={handleNextWeek}
                title="Next Week"
                className="p-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
              <button
                onClick={handleCurrentWeek}
                className="ml-1 text-[11px] font-bold px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200"
              >
                Current Week
              </button>
            </div>
          </div>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 dark:text-slate-400 mt-3 pt-3 border-t border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-indigo-100 dark:bg-indigo-950/60 border border-dashed border-indigo-400 opacity-60"></span>
            <span>Base Blueprint (Muted)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-indigo-600 shadow-sm"></span>
            <span className="font-semibold text-slate-700 dark:text-slate-300">Operational Override / Cover (Solid)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-amber-100 dark:bg-amber-950 border border-dashed border-amber-500"></span>
            <span className="text-amber-700 dark:text-amber-400 font-semibold">TO_BE_COVERED (Leave Gap)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full ring-2 ring-cyan-500"></span>
            <span>Recommended Window Target</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-purple-100 text-purple-700">Excess</span>
            <span>Excess Visit</span>
          </div>
        </div>
      </header>

      {/* Main Grid Content */}
      <main className="flex-1 overflow-auto p-6">
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
          /* Coverage Matrix */
          <div className="space-y-6">
            {coverageData.worksites.map((ws) => (
              <div
                key={ws.worksite_id}
                className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm overflow-hidden"
              >
                {/* Worksite Header */}
                <div className="px-6 py-3 bg-slate-50/80 dark:bg-slate-800/40 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm font-bold text-indigo-600 dark:text-indigo-400">
                      {ws.job_number}
                    </span>
                    <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                      {ws.job_name}
                    </h2>
                    {ws.customer_type && (
                      <span className="text-[10px] px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-700 font-medium">
                        {ws.customer_type}
                      </span>
                    )}
                  </div>

                  <div className="text-xs text-slate-500 flex items-center gap-3">
                    <span>Contract: {ws.start_date || "N/A"} to {ws.end_date || "Ongoing"}</span>
                    {ws.budget_amount && (
                      <span className="font-semibold text-slate-700 dark:text-slate-300">
                        {Number(ws.budget_amount).toLocaleString()} AED/yr
                      </span>
                    )}
                  </div>
                </div>

                {/* Coverage Matrix Table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="bg-slate-100/60 dark:bg-slate-800/20 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                        <th className="px-4 py-2.5 font-semibold w-72">Job Item & Quota</th>
                        {/* 7 Days Headers */}
                        {ws.items[0]?.days.map((d) => (
                          <th
                            key={d.work_date}
                            className={`px-3 py-2 text-center border-l border-slate-200 dark:border-slate-800 min-w-[130px] ${
                              d.is_public_holiday ? "bg-amber-50/50 dark:bg-amber-950/20" : ""
                            }`}
                          >
                            <div className="font-bold text-slate-800 dark:text-slate-200">
                              {d.weekday}
                            </div>
                            <div className="text-[10px] text-slate-400">{d.work_date.slice(5)}</div>
                            {d.is_public_holiday && (
                              <div
                                className="text-[9px] font-bold text-amber-700 dark:text-amber-300 truncate max-w-[120px] mx-auto mt-0.5"
                                title={d.holiday_name || "Public Holiday"}
                              >
                                {d.holiday_name || "Holiday"}
                              </div>
                            )}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {ws.items.map((it) => (
                        <tr key={it.job_item_id} className="hover:bg-slate-50/40 dark:hover:bg-slate-800/20">
                          {/* Item Info */}
                          <td className="px-4 py-3">
                            <div className="font-semibold text-slate-900 dark:text-white flex items-center gap-1.5">
                              <span className="font-mono text-indigo-600 dark:text-indigo-400">
                                {it.sub_item_code}
                              </span>
                              <span>{it.staff_grade_description}</span>
                            </div>
                            <div className="text-[11px] text-slate-500 mt-0.5">
                              Quota: {it.quota_assigned} / {it.quota_target} {it.frequency_unit.toLowerCase()} visits
                              {it.quota_satisfied && (
                                <span className="ml-1.5 text-emerald-600 dark:text-emerald-400 font-bold">
                                  ✓ Quota Met
                                </span>
                              )}
                            </div>
                          </td>

                          {/* 7 Daily Cells */}
                          {it.days.map((cell) => {
                            const isRecommended = cell.is_recommended_target;
                            const isExcess = cell.is_excess;
                            const hasCoverIssue = cell.is_to_be_covered;

                            return (
                              <td
                                key={cell.work_date}
                                onClick={() => handleCellClick(ws, it, cell)}
                                className={`px-2 py-2 border-l border-slate-200 dark:border-slate-800 cursor-pointer transition-colors relative hover:bg-indigo-50/40 dark:hover:bg-indigo-950/20 ${
                                  isRecommended ? "ring-1 ring-inset ring-cyan-400/60" : ""
                                } ${cell.is_public_holiday ? "bg-amber-50/30 dark:bg-amber-950/10" : ""}`}
                              >
                                <div className="space-y-1 min-h-[50px] flex flex-col justify-between">
                                  {/* Badges top */}
                                  <div className="flex items-center justify-between gap-1">
                                    {isExcess && (
                                      <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300">
                                        Excess
                                      </span>
                                    )}
                                    {isRecommended && !isExcess && (
                                      <span className="text-[9px] font-semibold text-cyan-600 dark:text-cyan-400">
                                        Target
                                      </span>
                                    )}
                                    {cell.is_quota_met && (
                                      <CheckCircle2 className="h-3 w-3 text-emerald-500 ml-auto" />
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
                                              className="p-1 rounded text-[10px] font-semibold bg-amber-50 dark:bg-amber-950/80 text-amber-800 dark:text-amber-200 border border-dashed border-amber-400 flex items-center justify-between"
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
                                                : "bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300 border border-dashed border-indigo-300 opacity-60"
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
                                    <div className="text-[10px] text-slate-300 dark:text-slate-700 text-center py-2">
                                      —
                                    </div>
                                  )}

                                  {/* Bottom status */}
                                  {hasCoverIssue && (
                                    <div className="text-[9px] font-bold text-amber-600 text-center">
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
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-100/60 dark:bg-slate-800/20 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                    <th className="px-4 py-3 font-semibold w-64">Worker & Total Hours</th>
                    {rosterData.workers[0]?.days.map((d) => (
                      <th
                        key={d.work_date}
                        className={`px-3 py-2 text-center border-l border-slate-200 dark:border-slate-800 min-w-[110px] ${
                          d.is_public_holiday ? "bg-amber-50/50 dark:bg-amber-950/20" : ""
                        }`}
                      >
                        <div className="font-bold text-slate-800 dark:text-slate-200">{d.weekday}</div>
                        <div className="text-[10px] text-slate-400">{d.work_date.slice(5)}</div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {rosterData.workers.map((w) => (
                    <tr key={w.employee_id} className="hover:bg-slate-50/40 dark:hover:bg-slate-800/20">
                      <td className="px-4 py-3">
                        <div className="font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                          <span>{w.name}</span>
                          <span className="font-mono text-[10px] text-slate-400">({w.tally_id})</span>
                        </div>
                        <div className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-2">
                          <span>{w.staff_grade_description || "Worker"}</span>
                          <span>•</span>
                          <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                            {w.total_week_hours} / {w.standard_week_hours} hrs
                          </span>
                        </div>
                      </td>

                      {w.days.map((d) => (
                        <td
                          key={d.work_date}
                          className={`px-2 py-2 border-l border-slate-200 dark:border-slate-800 text-center ${
                            d.is_weekly_off ? "bg-slate-50 dark:bg-slate-800/40 text-slate-400" : ""
                          }`}
                        >
                          {d.is_weekly_off ? (
                            <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300">
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
                                      : "bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 opacity-60"
                                  }`}
                                >
                                  {s.assigned_hours}h Shift
                                </div>
                              ))}
                            </div>
                          ) : (
                            <span className="text-slate-300 dark:text-slate-700 text-[10px]">—</span>
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

      {/* Single-Action Operational Modal */}
      {selectedCell && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-800 w-full max-w-lg overflow-hidden flex flex-col">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <Calendar className="h-5 w-5 text-indigo-600" />
                  Operational Shift Action
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  {selectedCell.cell.weekday} {selectedCell.cell.work_date} • {selectedCell.worksite.job_number} (
                  {selectedCell.item.sub_item_code})
                </p>
              </div>

              <button
                onClick={() => setSelectedCell(null)}
                className="p-1 rounded text-slate-400 hover:text-slate-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-4 flex-1 overflow-y-auto">
              {/* Existing Assigned Workers */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold uppercase text-slate-500">
                  Currently Scheduled Staff ({selectedCell.cell.workers.length})
                </h4>

                {selectedCell.cell.workers.length === 0 ? (
                  <p className="text-xs text-slate-400 italic">No workers currently scheduled for this slot.</p>
                ) : (
                  <div className="space-y-1.5">
                    {selectedCell.cell.workers.map((w, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40"
                      >
                        <div>
                          <div className="text-xs font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                            <span>{w.employee_name}</span>
                            <span className="text-[10px] px-1.5 py-0.2 rounded font-bold bg-slate-200 dark:bg-slate-700">
                              {w.display_type}
                            </span>
                          </div>
                          <div className="text-[11px] text-slate-400 mt-0.5">
                            {w.assigned_hours} hrs • {w.reason || "Standard shift"}
                          </div>
                        </div>

                        {w.shift_id && (
                          <button
                            onClick={() => handleDeleteShift(w.shift_id!)}
                            className="p-1.5 rounded text-red-600 hover:bg-red-50 text-xs font-semibold flex items-center gap-1"
                          >
                            <Trash2 className="h-3.5 w-3.5" /> Remove
                          </button>
                        )}
                        {!w.shift_id && (
                          <button
                            onClick={() => setReplacementTargetId(w.employee_id)}
                            className="px-2.5 py-1 rounded bg-indigo-50 text-indigo-700 text-xs font-semibold hover:bg-indigo-100"
                          >
                            Replace Cover
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Public Holiday Warning */}
              {selectedCell.cell.is_public_holiday && (
                <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800 flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
                  <span>
                    <strong>Public Holiday:</strong> {selectedCell.cell.holiday_name || "Public Holiday"}. Public holiday overtime rates apply.
                  </span>
                </div>
              )}

              {/* Form: Assign Shift / Cover */}
              <div className="pt-3 border-t border-slate-200 dark:border-slate-800 space-y-3">
                <h4 className="text-xs font-bold uppercase text-slate-500">
                  {replacementTargetId ? "Assign Replacement Cover Worker" : "Assign Single-Day Operational Shift"}
                </h4>

                {replacementTargetId && (
                  <div className="p-2 rounded bg-indigo-50 text-indigo-700 text-xs flex items-center justify-between">
                    <span>
                      Replacing base worker:{" "}
                      <strong>
                        {selectedCell.cell.workers.find((w) => w.employee_id === replacementTargetId)?.employee_name}
                      </strong>
                    </span>
                    <button
                      onClick={() => setReplacementTargetId(null)}
                      className="text-indigo-900 font-bold hover:underline"
                    >
                      Clear
                    </button>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Select Worker
                  </label>
                  {loadingCandidates ? (
                    <div className="text-xs text-slate-400 py-2">Loading candidates...</div>
                  ) : (
                    <select
                      value={selectedWorkerId}
                      onChange={(e) => setSelectedWorkerId(e.target.value)}
                      className="w-full text-xs py-2 px-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                    >
                      <option value="">-- Choose a worker --</option>
                      {candidates.map((cand) => (
                        <option key={cand.employee_id} value={cand.employee_id}>
                          {cand.name} ({cand.staff_grade_description}) - Off: {cand.weekly_off_day || "None"}
                        </option>
                      ))}
                    </select>
                  )}
                </div>

                {/* Rest day warning for selected worker */}
                {selectedCandidateObj &&
                  selectedCandidateObj.weekly_off_day?.toUpperCase() === selectedCell.cell.weekday && (
                    <div className="p-2.5 rounded bg-amber-50 border border-amber-200 text-xs text-amber-800 flex items-center gap-2">
                      <ShieldAlert className="h-4 w-4 text-amber-600 shrink-0" />
                      <span>
                        <strong>Rest Day Overtime:</strong> {selectedCandidateObj.name} has their weekly off on {selectedCell.cell.weekday}. Overtime will apply.
                      </span>
                    </div>
                  )}

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                      Assigned Hours
                    </label>
                    <input
                      type="number"
                      step="0.5"
                      value={shiftHours}
                      onChange={(e) => setShiftHours(e.target.value)}
                      className="w-full text-xs py-2 px-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                      Reason / Note
                    </label>
                    <input
                      type="text"
                      placeholder={replacementTargetId ? "Sick leave cover" : "Extra shift"}
                      value={overrideReason}
                      onChange={(e) => setOverrideReason(e.target.value)}
                      className="w-full text-xs py-2 px-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setSelectedCell(null)}
                className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-100"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={handleCreateShift}
                disabled={savingShift || !selectedWorkerId}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-1.5 shadow-sm"
              >
                {savingShift && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                {replacementTargetId ? "Confirm Replacement" : "Assign Shift"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
