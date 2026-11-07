import React, { useState, useEffect, useMemo } from "react";
import { useAuth } from "../context/AuthContext";
import {
  CalendarRange,
  Search,
  Building2,
  AlertTriangle,
  Settings2,
  ShieldAlert,
  Loader2,
  Plus,
  Trash2,
  X,
  Sparkles,
} from "lucide-react";
import {
  BasePlannerResponse,
  BasePlannerWorksiteRow,
  BasePlannerItemRow,
  BaseRosterTemplateCreate,
  CandidateRecommendation,
} from "../features/planner/types";

const WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"] as const;

export const BasePlanner: React.FC = () => {
  const { token } = useAuth();
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [worksites, setWorksites] = useState<BasePlannerWorksiteRow[]>([]);
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Modal state
  const [activeItem, setActiveItem] = useState<{
    worksite: BasePlannerWorksiteRow;
    item: BasePlannerItemRow;
  } | null>(null);
  const [modalMode, setModalMode] = useState<"UNIFORM" | "DAY_OF_WEEK">("UNIFORM");
  const [templateEntries, setTemplateEntries] = useState<
    {
      employee_id: string;
      employee_name: string;
      tally_id: string;
      weekly_off_day: string;
      weekday_mask: string;
      assigned_hours: number;
      sequence: number;
    }[]
  >([]);
  const [candidates, setCandidates] = useState<CandidateRecommendation[]>([]);
  const [loadingCandidates, setLoadingCandidates] = useState<boolean>(false);
  const [savingTemplate, setSavingTemplate] = useState<boolean>(false);

  // Fetch Base Planner Worksites
  const fetchBasePlannerData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/base-planner/worksites", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to load Base Planner data");
      const data: BasePlannerResponse = await res.json();
      setWorksites(data.worksites || []);
    } catch (err: any) {
      setError(err.message || "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token) {
      fetchBasePlannerData();
    }
  }, [token]);

  // Open modal and initialize form state
  const handleOpenConfigModal = async (ws: BasePlannerWorksiteRow, it: BasePlannerItemRow) => {
    setActiveItem({ worksite: ws, item: it });
    setModalMode(it.template?.allocation_mode || "UNIFORM");

    if (it.template && it.template.entries.length > 0) {
      setTemplateEntries(
        it.template.entries.map((e) => ({
          employee_id: e.employee_id,
          employee_name: e.employee_name || "Unknown Worker",
          tally_id: e.tally_id || "",
          weekly_off_day: e.weekly_off_day || "",
          weekday_mask: e.weekday_mask,
          assigned_hours: Number(e.assigned_hours),
          sequence: e.sequence,
        }))
      );
    } else {
      setTemplateEntries([]);
    }

    // Fetch candidate suggestions
    setLoadingCandidates(true);
    try {
      const cRes = await fetch(
        `/api/v1/scheduling/suggestions/candidates?job_item_id=${it.job_item_id}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (cRes.ok) {
        const cData = await cRes.json();
        setCandidates(cData.candidates || []);
      }
    } catch (e) {
      console.error("Failed to load candidates", e);
    } finally {
      setLoadingCandidates(false);
    }
  };

  // Save template
  const handleSaveTemplate = async () => {
    if (!activeItem) return;
    setSavingTemplate(true);
    try {
      const payload: BaseRosterTemplateCreate = {
        job_item_id: activeItem.item.job_item_id,
        allocation_mode: modalMode,
        start_date: activeItem.worksite.start_date || new Date().toISOString().split("T")[0],
        end_date: activeItem.worksite.end_date || null,
        entries: templateEntries.map((e, idx) => ({
          employee_id: e.employee_id,
          weekday_mask: modalMode === "UNIFORM" ? "ALL" : e.weekday_mask,
          assigned_hours: e.assigned_hours,
          sequence: idx + 1,
        })),
      };

      const res = await fetch("/api/v1/base-planner/templates", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || "Failed to save template");
      }

      await fetchBasePlannerData();
      setActiveItem(null);
    } catch (err: any) {
      alert(`Error saving template: ${err.message}`);
    } finally {
      setSavingTemplate(false);
    }
  };

  // Add worker to template
  const handleAddWorker = (cand: CandidateRecommendation, targetDow: string = "ALL") => {
    if (!activeItem) return;
    const exists = templateEntries.some(
      (e) => e.employee_id === cand.employee_id && (modalMode === "UNIFORM" || e.weekday_mask === targetDow)
    );
    if (exists) return;

    setTemplateEntries((prev) => [
      ...prev,
      {
        employee_id: cand.employee_id,
        employee_name: cand.name,
        tally_id: cand.tally_id,
        weekly_off_day: cand.weekly_off_day || "",
        weekday_mask: modalMode === "UNIFORM" ? "ALL" : targetDow,
        assigned_hours: Number(activeItem.item.hours_per_occurrence),
        sequence: prev.length + 1,
      },
    ]);
  };

  const handleRemoveEntry = (index: number) => {
    setTemplateEntries((prev) => prev.filter((_, i) => i !== index));
  };

  // Filter worksites
  const filteredWorksites = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    if (!q) return worksites;
    return worksites.filter(
      (ws) =>
        ws.job_number.toLowerCase().includes(q) ||
        ws.job_name.toLowerCase().includes(q) ||
        (ws.customer_type && ws.customer_type.toLowerCase().includes(q))
    );
  }, [worksites, searchQuery]);

  // Compute rest day issues in modal
  const restDayWarningsInModal = useMemo(() => {
    if (!activeItem || modalMode !== "UNIFORM") return [];
    const jobWorkingDays = activeItem.item.weekday_pattern || ["MON", "TUE", "WED", "THU", "FRI", "SAT"];
    const issues: { name: string; offDay: string }[] = [];
    for (const e of templateEntries) {
      if (e.weekly_off_day && jobWorkingDays.includes(e.weekly_off_day.toUpperCase())) {
        issues.push({ name: e.employee_name, offDay: e.weekly_off_day.toUpperCase() });
      }
    }
    return issues;
  }, [activeItem, modalMode, templateEntries]);

  return (
    <div className="flex flex-col h-full bg-slate-50 dark:bg-slate-950">
      {/* Header */}
      <header className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 px-6 py-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <CalendarRange className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
              <h1 className="text-xl font-bold text-slate-900 dark:text-white">
                Base Planner (Recurring Blueprint Engine)
              </h1>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                Master Year Schedule
              </span>
            </div>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Configure permanent staffing templates across contract validity dates. Handles weekly off rotations and Mode A vs Mode B matrices.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative w-72">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search job number or site name..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-4 py-2 text-sm rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto p-6 space-y-6">
        {loading ? (
          <div className="flex flex-col items-center justify-center h-64 text-slate-400">
            <Loader2 className="h-8 w-8 animate-spin mb-2" />
            <p className="text-sm font-medium">Loading Base Planner Worksites...</p>
          </div>
        ) : error ? (
          <div className="p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">
            {error}
          </div>
        ) : filteredWorksites.length === 0 ? (
          <div className="text-center py-16 text-slate-400">
            <Building2 className="h-12 w-12 mx-auto mb-3 opacity-30" />
            <p className="text-base font-semibold text-slate-600 dark:text-slate-300">No worksites found</p>
            <p className="text-sm mt-1">Try adjusting your search criteria</p>
          </div>
        ) : (
          <div className="space-y-6">
            {filteredWorksites.map((ws) => (
              <div
                key={ws.worksite_id}
                className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm overflow-hidden"
              >
                {/* Worksite Overview Bar */}
                <div className="px-6 py-4 bg-slate-50/70 dark:bg-slate-800/40 border-b border-slate-200 dark:border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-sm font-bold text-indigo-600 dark:text-indigo-400">
                        {ws.job_number}
                      </span>
                      <h2 className="text-base font-semibold text-slate-900 dark:text-white">
                        {ws.job_name}
                      </h2>
                      {ws.customer_type && (
                        <span className="text-xs px-2 py-0.5 rounded bg-slate-200 dark:bg-slate-700 font-medium">
                          {ws.customer_type}
                        </span>
                      )}
                      <span
                        className={`text-xs px-2 py-0.5 rounded font-medium ${
                          ws.is_outdoor
                            ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                            : "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300"
                        }`}
                      >
                        {ws.is_outdoor ? "Outdoor Site" : "Indoor Site"}
                      </span>
                    </div>

                    <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 dark:text-slate-400 pt-1">
                      <div>
                        <span className="font-medium text-slate-700 dark:text-slate-300">Contract Validity:</span>{" "}
                        {ws.start_date || "N/A"} to {ws.end_date || "Ongoing"}
                      </div>
                      <div>
                        <span className="font-medium text-slate-700 dark:text-slate-300">Annual Budget:</span>{" "}
                        {ws.budget_amount ? `${Number(ws.budget_amount).toLocaleString()} AED / year` : "Not specified"}
                      </div>
                      <div>
                        <span className="font-medium text-slate-700 dark:text-slate-300">Contract Line Items:</span>{" "}
                        {ws.items.length} items
                      </div>
                    </div>
                  </div>
                </div>

                {/* Job Items Table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-slate-100/50 dark:bg-slate-800/20 text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider border-b border-slate-200 dark:border-slate-800">
                      <tr>
                        <th className="px-6 py-3">Code & Staff Grade</th>
                        <th className="px-6 py-3">Frequency & Schedule</th>
                        <th className="px-6 py-3">Headcount & Hours</th>
                        <th className="px-6 py-3">Base Template Configuration</th>
                        <th className="px-6 py-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {ws.items.map((it) => {
                        const hasTemplate = !!it.template && it.template.entries.length > 0;
                        const isUniform = it.template?.allocation_mode === "UNIFORM";

                        return (
                          <tr
                            key={it.job_item_id}
                            className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors"
                          >
                            <td className="px-6 py-4">
                              <div className="font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                                <span className="font-mono text-indigo-600 dark:text-indigo-400">
                                  {it.sub_item_code}
                                </span>
                                <span>{it.staff_grade_description}</span>
                              </div>
                              <div className="text-xs text-slate-400 mt-0.5">
                                Planned Grade: {it.planned_grade_code} • {it.deployment_type}
                              </div>
                            </td>

                            <td className="px-6 py-4 text-xs text-slate-600 dark:text-slate-300">
                              <div className="font-medium text-slate-800 dark:text-slate-200">
                                {it.frequency_unit === "WEEK"
                                  ? `Weekly (${it.occurrences_per_period} visits / week)`
                                  : it.frequency_unit === "MONTH"
                                  ? `Monthly (${it.occurrences_per_period} visits / month)`
                                  : `${it.frequency_unit} (${it.occurrences_per_period} visits)`}
                              </div>
                              <div className="text-slate-400 mt-0.5">
                                {it.weekday_pattern && it.weekday_pattern.length > 0
                                  ? `Active: ${it.weekday_pattern.join(", ")}`
                                  : "Default working days (Mon-Sat)"}
                              </div>
                            </td>

                            <td className="px-6 py-4 text-xs text-slate-600 dark:text-slate-300">
                              <div className="font-semibold text-slate-800 dark:text-slate-200">
                                {it.required_staff_count} Staff Required
                              </div>
                              <div className="text-slate-400 mt-0.5">
                                {it.hours_per_occurrence} hrs / occurrence / staff
                              </div>
                            </td>

                            <td className="px-6 py-4">
                              {hasTemplate ? (
                                <div className="space-y-1.5">
                                  <div className="flex items-center gap-2">
                                    <span
                                      className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                                        isUniform
                                          ? "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300"
                                          : "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300"
                                      }`}
                                    >
                                      {isUniform ? "Mode A: Uniform Crew" : "Mode B: Day-of-Week Crew Matrix"}
                                    </span>
                                    <span className="text-xs text-slate-400">
                                      ({it.template?.entries.length} assigned slots)
                                    </span>
                                  </div>

                                  {/* Worker badges */}
                                  <div className="flex flex-wrap gap-1.5 max-w-md">
                                    {it.template?.entries.map((entry) => (
                                      <span
                                        key={entry.id}
                                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700"
                                      >
                                        <span className="font-medium">
                                          {entry.employee_name || "Worker"}
                                        </span>
                                        {!isUniform && (
                                          <span className="text-[10px] text-purple-600 dark:text-purple-400 font-bold">
                                            [{entry.weekday_mask}]
                                          </span>
                                        )}
                                        {entry.weekly_off_day && (
                                          <span className="text-[10px] text-amber-600 dark:text-amber-400">
                                            (Off: {entry.weekly_off_day})
                                          </span>
                                        )}
                                      </span>
                                    ))}
                                  </div>
                                </div>
                              ) : (
                                <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-amber-50 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                                  <AlertTriangle className="h-3.5 w-3.5" />
                                  <span>No Recurring Template Configured</span>
                                </div>
                              )}
                            </td>

                            <td className="px-6 py-4 text-right">
                              <button
                                onClick={() => handleOpenConfigModal(ws, it)}
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-50 text-indigo-700 hover:bg-indigo-100 dark:bg-indigo-950/50 dark:text-indigo-300 dark:hover:bg-indigo-900 border border-indigo-200 dark:border-indigo-800 transition-colors"
                              >
                                <Settings2 className="h-3.5 w-3.5" />
                                {hasTemplate ? "Edit Template" : "Configure Template"}
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Template Configuration Modal */}
      {activeItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
          <div className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-800 w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <Settings2 className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                  <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                    Configure Base Roster Template
                  </h3>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  {activeItem.worksite.job_number} - {activeItem.worksite.job_name} • Item{" "}
                  <span className="font-semibold">{activeItem.item.sub_item_code}</span> (
                  {activeItem.item.staff_grade_description})
                </p>
              </div>

              <button
                onClick={() => setActiveItem(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Mode Selection Tabs */}
              <div className="bg-slate-100 dark:bg-slate-800 p-1 rounded-xl flex gap-1">
                <button
                  type="button"
                  onClick={() => setModalMode("UNIFORM")}
                  className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold transition-all ${
                    modalMode === "UNIFORM"
                      ? "bg-white dark:bg-slate-900 text-indigo-600 dark:text-indigo-400 shadow-sm"
                      : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
                  }`}
                >
                  Mode A: Uniform Daily Team
                  <span className="block text-[10px] font-normal text-slate-500 mt-0.5">
                    Assign once; same team attends all active days
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => setModalMode("DAY_OF_WEEK")}
                  className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold transition-all ${
                    modalMode === "DAY_OF_WEEK"
                      ? "bg-white dark:bg-slate-900 text-purple-600 dark:text-purple-400 shadow-sm"
                      : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
                  }`}
                >
                  Mode B: Day-of-Week Crew Matrix
                  <span className="block text-[10px] font-normal text-slate-500 mt-0.5">
                    Configure individual teams per day (resolves Friday off rotation)
                  </span>
                </button>
              </div>

              {/* Rest Day Warning Alert (for Mode A) */}
              {restDayWarningsInModal.length > 0 && (
                <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <ShieldAlert className="h-5 w-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                    <div className="text-xs text-amber-800 dark:text-amber-200">
                      <p className="font-semibold">Weekly Rest-Day Warning in Uniform Mode:</p>
                      <ul className="list-disc pl-4 mt-1 space-y-0.5">
                        {restDayWarningsInModal.map((w, idx) => (
                          <li key={idx}>
                            <span className="font-semibold">{w.name}</span> has {w.offDay} off, which is an active job day.
                          </li>
                        ))}
                      </ul>
                      <p className="mt-1 text-slate-600 dark:text-slate-400">
                        In Uniform Mode, these workers will be flagged with a Rest-Day warning. Switch to Day-of-Week Crew Matrix to schedule an alternate worker on that day.
                      </p>
                    </div>
                  </div>

                  <button
                    onClick={() => setModalMode("DAY_OF_WEEK")}
                    className="shrink-0 px-3 py-1.5 rounded-lg text-xs font-bold bg-amber-200 text-amber-900 hover:bg-amber-300 dark:bg-amber-800 dark:text-amber-100 transition-colors"
                  >
                    Switch to Mode B
                  </button>
                </div>
              )}

              {/* Roster Configuration Grid */}
              <div className="space-y-4">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  {modalMode === "UNIFORM"
                    ? "Uniform Crew (Applies to all active job working days)"
                    : "Day-of-Week Staffing Matrix"}
                </h4>

                {modalMode === "UNIFORM" ? (
                  <div className="border border-slate-200 dark:border-slate-800 rounded-xl p-4 bg-slate-50/50 dark:bg-slate-800/30 space-y-3">
                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <span>
                        Assigned Workers: {templateEntries.length} / Required:{" "}
                        {activeItem.item.required_staff_count}
                      </span>
                    </div>

                    {templateEntries.length === 0 ? (
                      <p className="text-xs text-slate-400 italic py-2">
                        No workers assigned to uniform crew yet. Select from the candidate pool below.
                      </p>
                    ) : (
                      <div className="space-y-2">
                        {templateEntries.map((e, idx) => (
                          <div
                            key={idx}
                            className="flex items-center justify-between p-2.5 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800"
                          >
                            <div className="flex items-center gap-3">
                              <span className="text-xs font-bold font-mono text-slate-400">#{idx + 1}</span>
                              <div>
                                <span className="text-sm font-semibold text-slate-900 dark:text-white">
                                  {e.employee_name}
                                </span>
                                <span className="text-xs text-slate-400 ml-2 font-mono">
                                  ({e.tally_id})
                                </span>
                              </div>
                              {e.weekly_off_day && (
                                <span className="text-xs px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                                  Weekly Off: {e.weekly_off_day}
                                </span>
                              )}
                            </div>

                            <button
                              onClick={() => handleRemoveEntry(idx)}
                              className="text-red-500 hover:text-red-700 p-1 rounded"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  /* Mode B: 7-Column Day-of-Week Matrix */
                  <div className="grid grid-cols-1 md:grid-cols-7 gap-2">
                    {WEEKDAYS.map((dow) => {
                      const dayEntries = templateEntries.filter((e) => e.weekday_mask === dow);
                      const isFriday = dow === "FRI";

                      return (
                        <div
                          key={dow}
                          className={`border rounded-xl p-3 flex flex-col justify-between min-h-[160px] ${
                            isFriday
                              ? "border-purple-300 dark:border-purple-800 bg-purple-50/30 dark:bg-purple-950/20"
                              : "border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                          }`}
                        >
                          <div>
                            <div className="flex items-center justify-between mb-2">
                              <span className="font-bold text-xs text-slate-900 dark:text-white">{dow}</span>
                              {isFriday && (
                                <span className="text-[10px] font-semibold text-purple-700 dark:text-purple-300">
                                  Friday Shift
                                </span>
                              )}
                            </div>

                            <div className="space-y-1.5">
                              {dayEntries.map((e, idx) => (
                                <div
                                  key={idx}
                                  className="text-[11px] p-1.5 rounded bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex items-center justify-between"
                                >
                                  <span className="truncate max-w-[80px]" title={e.employee_name}>
                                    {e.employee_name}
                                  </span>
                                  <button
                                    onClick={() => {
                                      const globalIdx = templateEntries.indexOf(e);
                                      if (globalIdx !== -1) handleRemoveEntry(globalIdx);
                                    }}
                                    className="text-red-400 hover:text-red-600 ml-1"
                                  >
                                    <X className="h-3 w-3" />
                                  </button>
                                </div>
                              ))}
                            </div>
                          </div>

                          <div className="mt-2 pt-2 border-t border-slate-100 dark:border-slate-800 text-[10px] text-slate-400 text-center">
                            {dayEntries.length} assigned
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Candidate Worker Suggestions */}
              <div className="space-y-3 pt-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-indigo-500" />
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                      Recommended Worker Candidates
                    </h4>
                  </div>
                  <span className="text-xs text-slate-400">
                    Matches grade {activeItem.item.planned_grade_code} & job requirements
                  </span>
                </div>

                {loadingCandidates ? (
                  <div className="text-center py-6 text-slate-400 text-xs flex items-center justify-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" /> Loading candidate pool...
                  </div>
                ) : candidates.length === 0 ? (
                  <p className="text-xs text-slate-400 py-2">No recommended candidates found.</p>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-56 overflow-y-auto">
                    {candidates.map((cand) => (
                      <div
                        key={cand.employee_id}
                        className="p-2.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex items-center justify-between gap-2 hover:border-indigo-300 dark:hover:border-indigo-700 transition-colors"
                      >
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-slate-900 dark:text-white">
                              {cand.name}
                            </span>
                            <span className="text-[10px] text-slate-400 font-mono">
                              ({cand.tally_id})
                            </span>
                          </div>
                          <div className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-2">
                            <span>{cand.staff_grade_description || "Staff"}</span>
                            <span>•</span>
                            <span className="text-indigo-600 dark:text-indigo-400">
                              Off: {cand.weekly_off_day || "None"}
                            </span>
                          </div>
                        </div>

                        {modalMode === "UNIFORM" ? (
                          <button
                            onClick={() => handleAddWorker(cand, "ALL")}
                            className="px-2.5 py-1 rounded text-xs font-semibold bg-indigo-50 text-indigo-700 hover:bg-indigo-100 dark:bg-indigo-950/60 dark:text-indigo-300 flex items-center gap-1"
                          >
                            <Plus className="h-3 w-3" /> Add
                          </button>
                        ) : (
                          <div className="flex items-center gap-1">
                            <select
                              defaultValue="FRI"
                              id={`select-dow-${cand.employee_id}`}
                              className="text-xs py-1 px-1.5 rounded border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800"
                            >
                              {WEEKDAYS.map((w) => (
                                <option key={w} value={w}>
                                  {w}
                                </option>
                              ))}
                            </select>
                            <button
                              onClick={() => {
                                const el = document.getElementById(
                                  `select-dow-${cand.employee_id}`
                                ) as HTMLSelectElement;
                                handleAddWorker(cand, el?.value || "FRI");
                              }}
                              className="px-2 py-1 rounded text-xs font-semibold bg-purple-50 text-purple-700 hover:bg-purple-100 dark:bg-purple-950/60 dark:text-purple-300"
                            >
                              Add
                            </button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setActiveItem(null)}
                className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={handleSaveTemplate}
                disabled={savingTemplate || templateEntries.length === 0}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors flex items-center gap-1.5 shadow-sm"
              >
                {savingTemplate && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                Save Master Template
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
