import React, { useState, useEffect, useMemo } from "react";
import { useAuth } from "../context/AuthContext";
import {
  CalendarRange,
  Search,
  Building2,
  CheckCircle2,
  ShieldAlert,
  Loader2,
  Plus,
  Trash2,
  X,
  Sparkles,
  UserCheck,
  Calendar,
  AlertTriangle,
} from "lucide-react";
import {
  BasePlannerResponse,
  BasePlannerWorksiteRow,
  BasePlannerItemRow,
  BaseRosterTemplateCreate,
  CandidateRecommendation,
} from "../features/planner/types";

const WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"] as const;

function isSameWeekday(offDay: string | null | undefined, weekdayCode: string): boolean {
  if (!offDay || !weekdayCode) return false;
  const off = offDay.trim().toUpperCase();
  const code = weekdayCode.trim().toUpperCase();
  return off === code || off.startsWith(code) || code.startsWith(off);
}

interface SupervisorOption {
  id: string;
  name: string;
  tally_id?: string;
}

export const BasePlanner: React.FC = () => {
  const { token } = useAuth();
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [worksites, setWorksites] = useState<BasePlannerWorksiteRow[]>([]);
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Supervisor filter
  const [supervisorsList, setSupervisorsList] = useState<SupervisorOption[]>([]);
  const [selectedSupervisorId, setSelectedSupervisorId] = useState<string>("");

  // Slot Assignment Modal state
  const [activeSlot, setActiveSlot] = useState<{
    worksite: BasePlannerWorksiteRow;
    item: BasePlannerItemRow;
    weekday: typeof WEEKDAYS[number];
  } | null>(null);

  // Modal form state
  const [fillWorkingDays, setFillWorkingDays] = useState<boolean>(false);
  const [selectedWeeksOfMonth, setSelectedWeeksOfMonth] = useState<number[]>([1]);
  const [selectedQuarterMonth, setSelectedQuarterMonth] = useState<number>(1);
  const [selectedQuarterWeek, setSelectedQuarterWeek] = useState<number>(1);

  const [slotEntries, setSlotEntries] = useState<
    {
      employee_id: string;
      employee_name: string;
      tally_id: string;
      weekly_off_day: string;
      staff_grade_description?: string;
      assigned_hours: number;
      sequence: number;
    }[]
  >([]);

  // Modal candidate recommendations
  const [candidates, setCandidates] = useState<CandidateRecommendation[]>([]);
  const [candidateSearch, setCandidateSearch] = useState<string>("");
  const [filterToSupervisorCrew, setFilterToSupervisorCrew] = useState<boolean>(true);
  const [loadingCandidates, setLoadingCandidates] = useState<boolean>(false);
  const [savingSlot, setSavingSlot] = useState<boolean>(false);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // Fetch Base Planner Worksites
  const fetchBasePlannerData = async (silent: boolean = false) => {
    if (!silent) setLoading(true);
    else setIsRefreshing(true);
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
      if (!silent) setLoading(false);
      else setIsRefreshing(false);
    }
  };

  // Fetch Supervisors for crew filter
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
      fetchBasePlannerData();
      fetchSupervisors();
    }
  }, [token]);

  // Click on a cell opens the assignment modal
  const handleCellClick = async (
    ws: BasePlannerWorksiteRow,
    it: BasePlannerItemRow,
    dow: typeof WEEKDAYS[number]
  ) => {
    setActiveSlot({ worksite: ws, item: it, weekday: dow });
    setFillWorkingDays(false);
    setCandidateSearch("");
    setFilterToSupervisorCrew(Boolean(selectedSupervisorId));

    // Extract current workers for this slot
    if (it.template && it.template.entries.length > 0) {
      const isMonthly = it.frequency_unit === "MONTH";
      const isQuarterly = it.frequency_unit === "QUARTER";

      // Find entries that match this weekday
      const currentMatching = it.template.entries.filter((e) => {
        const mask = e.weekday_mask.toUpperCase();
        if (mask === dow || mask === "ALL") return true;
        if (isMonthly && mask.includes(`_${dow}`)) return true;
        if (isQuarterly && mask.endsWith(`_${dow}`)) return true;
        return false;
      });

      // Populate cadence states if monthly/quarterly
      if (isMonthly && currentMatching.length > 0) {
        const weeks = new Set<number>();
        for (const e of currentMatching) {
          const match = e.weekday_mask.match(/W(\d)_/);
          if (match) weeks.add(Number(match[1]));
        }
        setSelectedWeeksOfMonth(weeks.size > 0 ? Array.from(weeks) : [1]);
      } else {
        setSelectedWeeksOfMonth([1]);
      }

      if (isQuarterly && currentMatching.length > 0) {
        const first = currentMatching[0].weekday_mask;
        const match = first.match(/M(\d)_W(\d)_/);
        if (match) {
          setSelectedQuarterMonth(Number(match[1]));
          setSelectedQuarterWeek(Number(match[2]));
        }
      } else {
        setSelectedQuarterMonth(1);
        setSelectedQuarterWeek(1);
      }

      // Deduplicate workers by employee_id for this slot
      const seen = new Set<string>();
      const entriesList: typeof slotEntries = [];
      for (const e of currentMatching) {
        if (!seen.has(e.employee_id)) {
          seen.add(e.employee_id);
          entriesList.push({
            employee_id: e.employee_id,
            employee_name: e.employee_name || "Unknown Worker",
            tally_id: e.tally_id || "",
            weekly_off_day: e.weekly_off_day || "",
            assigned_hours: Number(e.assigned_hours),
            sequence: e.sequence,
          });
        }
      }
      setSlotEntries(entriesList);
    } else {
      setSlotEntries([]);
      setSelectedWeeksOfMonth([1]);
      setSelectedQuarterMonth(1);
      setSelectedQuarterWeek(1);
    }

    // Fetch candidate recommendations for this specific weekday
    setLoadingCandidates(true);
    try {
      const cRes = await fetch(
        `/api/v1/job-items/${it.job_item_id}/recommendations?weekday=${dow}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (cRes.ok) {
        const cData = await cRes.json();
        setCandidates(cData || []);
      }
    } catch (e) {
      console.error("Failed to load candidates:", e);
    } finally {
      setLoadingCandidates(false);
    }
  };

  // Add candidate to current slot
  const handleAddCandidate = (cand: CandidateRecommendation) => {
    if (!activeSlot) return;
    const requiredHeadcount = activeSlot.item.required_staff_count || 1;
    if (slotEntries.length >= requiredHeadcount) return;
    if (cand.is_blocked) return;
    const exists = slotEntries.some((e) => e.employee_id === cand.employee_id);
    if (exists) return;

    setSlotEntries((prev) => [
      ...prev,
      {
        employee_id: cand.employee_id,
        employee_name: cand.name,
        tally_id: cand.tally_id,
        weekly_off_day: cand.weekly_off_day || "",
        staff_grade_description: cand.staff_grade_description || "",
        assigned_hours: Number(activeSlot.item.hours_per_occurrence),
        sequence: prev.length + 1,
      },
    ]);
  };

  // Remove worker from slot
  const handleRemoveEntry = (empId: string) => {
    setSlotEntries((prev) => prev.filter((e) => e.employee_id !== empId));
  };

  // Save template with explicit day preservation
  const handleSaveSlot = async () => {
    if (!activeSlot) return;
    setSavingSlot(true);
    try {
      const it = activeSlot.item;
      const targetDow = activeSlot.weekday;
      const existingEntries = it.template?.entries || [];
      const isMonthly = it.frequency_unit === "MONTH";
      const isQuarterly = it.frequency_unit === "QUARTER";

      // 1. Keep entries for all OTHER days/cadences completely intact
      const otherEntries = existingEntries
        .filter((e) => {
          const mask = e.weekday_mask.toUpperCase();
          if (fillWorkingDays) {
            // If filling Mon-Sat, keep Sunday and any periodic masks that don't collide
            return mask === "SUN";
          }
          if (isMonthly) {
            return !mask.includes(`_${targetDow}`) && mask !== targetDow;
          }
          if (isQuarterly) {
            return !mask.endsWith(`_${targetDow}`) && mask !== targetDow;
          }
          return mask !== targetDow && mask !== "ALL";
        })
        .map((e) => ({
          employee_id: e.employee_id,
          weekday_mask: e.weekday_mask,
          assigned_hours: Number(e.assigned_hours),
          sequence: e.sequence,
        }));

      // 2. Generate new entries for this slot
      const newEntries: {
        employee_id: string;
        weekday_mask: string;
        assigned_hours: number;
        sequence: number;
      }[] = [];

      if (fillWorkingDays) {
        // Convenience Fill: Copy these workers to MON, TUE, WED, THU, FRI, SAT explicitly!
        // Automatically skips any day that is the worker's weekly rest day!
        const workingDays = ["MON", "TUE", "WED", "THU", "FRI", "SAT"];
        for (const d of workingDays) {
          slotEntries.forEach((se, idx) => {
            if (isSameWeekday(se.weekly_off_day, d)) {
              return; // Skip worker on their weekly off day
            }
            newEntries.push({
              employee_id: se.employee_id,
              weekday_mask: d,
              assigned_hours: se.assigned_hours,
              sequence: idx + 1,
            });
          });
        }
      } else if (isMonthly) {
        // Monthly Cadence: generate W{week}_{dow}
        for (const w of selectedWeeksOfMonth) {
          slotEntries.forEach((se, idx) => {
            newEntries.push({
              employee_id: se.employee_id,
              weekday_mask: `W${w}_${targetDow}`,
              assigned_hours: se.assigned_hours,
              sequence: idx + 1,
            });
          });
        }
      } else if (isQuarterly) {
        // Quarterly Cadence: generate M{month}_W{week}_{dow}
        slotEntries.forEach((se, idx) => {
          newEntries.push({
            employee_id: se.employee_id,
            weekday_mask: `M${selectedQuarterMonth}_W${selectedQuarterWeek}_${targetDow}`,
            assigned_hours: se.assigned_hours,
            sequence: idx + 1,
          });
        });
      } else {
        // Standard Weekly: explicit weekday_mask
        slotEntries.forEach((se, idx) => {
          newEntries.push({
            employee_id: se.employee_id,
            weekday_mask: targetDow,
            assigned_hours: se.assigned_hours,
            sequence: idx + 1,
          });
        });
      }

      const payload: BaseRosterTemplateCreate = {
        job_item_id: it.job_item_id,
        allocation_mode: "DAY_OF_WEEK",
        start_date: activeSlot.worksite.start_date || new Date().toISOString().split("T")[0],
        end_date: activeSlot.worksite.end_date || null,
        entries: [...otherEntries, ...newEntries],
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

      const scrollPos = window.scrollY;
      await fetchBasePlannerData(true);
      setActiveSlot(null);
      setTimeout(() => {
        window.scrollTo({ top: scrollPos, behavior: "instant" });
      }, 0);
    } catch (err: any) {
      alert(`Error saving slot: ${err.message}`);
    } finally {
      setSavingSlot(false);
    }
  };

  // Filter worksites by search query
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

  // Quota calculation helper for modal
  const quotaStatusInModal = useMemo(() => {
    if (!activeSlot) return { isQuotaReached: false, maxOccurrences: 1, currentCount: 0 };
    const it = activeSlot.item;
    const maxOccurrences = Number(it.occurrences_per_period) || 1;

    // Count currently assigned days/cadences (excluding activeSlot.weekday if already in it)
    const existingEntries = it.template?.entries || [];
    const distinctDays = new Set<string>();

    for (const e of existingEntries) {
      const mask = e.weekday_mask.toUpperCase();
      if (WEEKDAYS.includes(mask as any)) {
        distinctDays.add(mask);
      } else if (mask.includes("_")) {
        distinctDays.add(mask);
      }
    }

    const isCurrentSlotAlreadyScheduled = distinctDays.has(activeSlot.weekday);
    const countExcludingCurrent = isCurrentSlotAlreadyScheduled
      ? distinctDays.size - 1
      : distinctDays.size;

    const isQuotaReached = countExcludingCurrent >= maxOccurrences;
    return {
      isQuotaReached,
      maxOccurrences,
      currentCount: distinctDays.size,
      isCurrentSlotAlreadyScheduled,
    };
  }, [activeSlot]);

  // Filter candidates in modal by search and supervisor crew toggle
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

    // Sort strictly by 3-tier priority (DEC-52):
    // 1. Same staff grade description (exact_staff_type_match)
    // 2. Ranking score
    return [...pool].sort((a, b) => {
      if (a.exact_staff_type_match !== b.exact_staff_type_match) {
        return a.exact_staff_type_match ? -1 : 1;
      }
      return (b.ranking_score || 0) - (a.ranking_score || 0);
    });
  }, [candidates, candidateSearch, filterToSupervisorCrew, selectedSupervisorId]);

  return (
    <div className="flex flex-col h-full bg-slate-50">
      {/* Top Controls Bar - Light Enterprise Styling */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 sticky top-0 z-20">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <CalendarRange className="h-6 w-6 text-indigo-600" />
              <h1 className="text-xl font-bold text-slate-900">
                Base Planner (Recurring Master Blueprint)
              </h1>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                Master Schedule
              </span>
              {isRefreshing && (
                <span className="text-xs text-indigo-600 flex items-center gap-1 font-medium bg-indigo-50/80 px-2 py-0.5 rounded border border-indigo-200 animate-pulse">
                  <Loader2 className="h-3 w-3 animate-spin" /> Saving & updating...
                </span>
              )}
            </div>
            <p className="text-sm text-slate-500 mt-1">
              Configure permanent weekly staffing across contract validity dates. Click any weekday slot to assign workers.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
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

            {/* Worksite Search */}
            <div className="relative w-64">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search job number or site..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-4 py-2 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-sm"
              />
            </div>
          </div>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 mt-3 pt-3 border-t border-slate-100">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-indigo-50 border border-indigo-300"></span>
            <span className="font-medium text-slate-700">Base Blueprint Shift</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full ring-2 ring-cyan-500"></span>
            <span>Recommended Target Slot</span>
          </div>
          <div className="flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
            <span className="text-emerald-700 font-medium">Quota Met</span>
          </div>
          <div className="flex items-center gap-1.5">
            <ShieldAlert className="h-3.5 w-3.5 text-amber-500" />
            <span className="text-amber-700 font-medium">Rest Day Warning</span>
          </div>
        </div>
      </header>

      {/* Main Grid Content */}
      <main className="flex-1 overflow-auto p-6 space-y-6">
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
          <div className="text-center py-16 text-slate-400 bg-white rounded-xl border border-slate-200">
            <Building2 className="h-12 w-12 mx-auto mb-3 opacity-30" />
            <p className="text-base font-semibold text-slate-700">No worksites found</p>
            <p className="text-sm mt-1">Try adjusting your search criteria</p>
          </div>
        ) : (
          <div className="space-y-6">
            {filteredWorksites.map((ws) => (
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

                {/* 7-Weekday Grid Table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="bg-slate-100/70 text-slate-500 border-b border-slate-200">
                        <th className="px-4 py-2.5 font-semibold w-72">Job Item & Quota</th>
                        {WEEKDAYS.map((dow) => (
                          <th
                            key={dow}
                            className="px-3 py-2 text-center border-l border-slate-200 min-w-[130px] font-bold text-slate-700"
                          >
                            {dow}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {ws.items.map((it) => {
                        const targetOccurrences = Number(it.occurrences_per_period) || 1;
                        const isWeekly = it.frequency_unit === "WEEK";
                        const isMonthly = it.frequency_unit === "MONTH";
                        const isQuarterly = it.frequency_unit === "QUARTER";

                        // Determine recommended target days (pure visual recommendation)
                        let recommendedWeekdays = it.weekday_pattern;
                        if (!recommendedWeekdays || recommendedWeekdays.length === 0) {
                          if (isWeekly) {
                            if (targetOccurrences >= 6) {
                              recommendedWeekdays = ["MON", "TUE", "WED", "THU", "FRI", "SAT"];
                            } else if (targetOccurrences === 5) {
                              recommendedWeekdays = ["MON", "TUE", "WED", "THU", "FRI"];
                            } else if (targetOccurrences === 1) {
                              recommendedWeekdays = ["MON"];
                            } else {
                              recommendedWeekdays = [];
                            }
                          } else {
                            recommendedWeekdays = [];
                          }
                        }

                        // Calculate assigned days count in template
                        const distinctAssignedSlots = new Set<string>();
                        if (it.template) {
                          for (const e of it.template.entries) {
                            distinctAssignedSlots.add(e.weekday_mask.toUpperCase());
                          }
                        }
                        const isQuotaMet = distinctAssignedSlots.size >= targetOccurrences;

                        return (
                          <tr key={it.job_item_id} className="hover:bg-slate-50/50 transition-colors">
                            {/* Job Item Info Column */}
                            <td className="px-4 py-3">
                              <div className="font-semibold text-slate-900 flex items-center gap-1.5">
                                <span className="font-mono text-indigo-600">{it.sub_item_code}</span>
                                <span>{it.staff_grade_description}</span>
                              </div>
                              <div className="text-[11px] text-slate-500 mt-0.5">
                                {isWeekly
                                  ? `Weekly (${it.occurrences_per_period}x/wk)`
                                  : isMonthly
                                  ? `Monthly (${it.occurrences_per_period}x/mo)`
                                  : `${it.frequency_unit} (${it.occurrences_per_period}x)`}{" "}
                                • {it.required_staff_count} staff • {it.hours_per_occurrence}h/visit
                              </div>
                              <div className="flex items-center gap-2 mt-1">
                                <span className="text-[10px] text-slate-600 font-medium">
                                  Planned: {distinctAssignedSlots.size} / {targetOccurrences} slots
                                </span>
                                {isQuotaMet && (
                                  <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.2 rounded border border-emerald-200">
                                    <CheckCircle2 className="h-3 w-3" /> Quota Met
                                  </span>
                                )}
                              </div>
                            </td>

                            {/* 7 Weekday Slot Cells */}
                            {WEEKDAYS.map((dow) => {
                              const isRecommended = recommendedWeekdays.includes(dow);

                              // Find workers scheduled for this weekday (weekly, or periodic cadence prefix)
                              const matchingEntries = (it.template?.entries || []).filter((e) => {
                                const mask = e.weekday_mask.toUpperCase();
                                if (mask === dow || mask === "ALL") return true;
                                if (isMonthly && mask.includes(`_${dow}`)) return true;
                                if (isQuarterly && mask.endsWith(`_${dow}`)) return true;
                                return false;
                              });

                              return (
                                <td
                                  key={dow}
                                  onClick={() => handleCellClick(ws, it, dow)}
                                  className={`px-2 py-2 border-l border-slate-200 cursor-pointer transition-colors relative hover:bg-indigo-50/60 ${
                                    isRecommended ? "ring-1 ring-inset ring-cyan-400" : ""
                                  }`}
                                >
                                  <div className="space-y-1 min-h-[52px] flex flex-col justify-between">
                                    {/* Top status */}
                                    <div className="flex items-center justify-between text-[9px]">
                                      {isRecommended ? (
                                        <span className="text-cyan-700 font-bold">Target</span>
                                      ) : (
                                        <span></span>
                                      )}
                                    </div>

                                    {/* Assigned Workers List */}
                                    {matchingEntries.length > 0 ? (
                                      <div className="space-y-1">
                                        {matchingEntries.map((e) => {
                                          const isOffDay = isSameWeekday(e.weekly_off_day, dow);
                                          // Format label with cadence prefix if monthly/quarterly
                                          let cadenceTag = "";
                                          if (isMonthly) {
                                            const m = e.weekday_mask.match(/W(\d)_/);
                                            if (m) cadenceTag = `W${m[1]}: `;
                                          } else if (isQuarterly) {
                                            const m = e.weekday_mask.match(/M(\d)_W(\d)_/);
                                            if (m) cadenceTag = `M${m[1]}W${m[2]}: `;
                                          }

                                          return (
                                            <div
                                              key={e.id}
                                              className={`p-1 rounded text-[10px] border flex items-center justify-between ${
                                                isOffDay
                                                  ? "bg-amber-50 border-amber-300 text-amber-900"
                                                  : "bg-indigo-50 border-indigo-200 text-indigo-900 font-medium"
                                              }`}
                                            >
                                              <span className="truncate max-w-[85px]" title={e.employee_name || "Worker"}>
                                                <strong className="text-indigo-700">{cadenceTag}</strong>
                                                {e.employee_name || "Worker"}
                                              </span>
                                              {isOffDay && (
                                                <span title="Rest Day Warning">
                                                  <ShieldAlert className="h-3 w-3 text-amber-600 shrink-0" />
                                                </span>
                                              )}
                                            </div>
                                          );
                                        })}
                                      </div>
                                    ) : (
                                      <div className="text-[10px] text-slate-400 hover:text-indigo-600 text-center py-2">
                                        + Assign
                                      </div>
                                    )}

                                    <div className="text-[9px] text-slate-400 text-right">
                                      {matchingEntries.length > 0 && `${matchingEntries.length}/${it.required_staff_count}`}
                                    </div>
                                  </div>
                                </td>
                              );
                            })}
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

      {/* Click-to-Assign Slot Modal - Light Theme Enterprise */}
      {activeSlot && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div>
                <div className="flex items-center gap-2">
                  <CalendarRange className="h-5 w-5 text-indigo-600" />
                  <h3 className="text-base font-bold text-slate-900">
                    Assign Recurring Staff to Slot
                  </h3>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  {activeSlot.worksite.job_number} - {activeSlot.worksite.job_name} • Item{" "}
                  <span className="font-semibold">{activeSlot.item.sub_item_code}</span> (
                  {activeSlot.item.staff_grade_description}) • Target:{" "}
                  <strong className="text-indigo-700">{activeSlot.weekday}</strong>
                </p>
              </div>

              <button
                onClick={() => setActiveSlot(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200 transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-5">
              {/* Quota limit warning banner in Base Planner */}
              {quotaStatusInModal.isQuotaReached && !quotaStatusInModal.isCurrentSlotAlreadyScheduled && (
                <div className="p-3 rounded-lg bg-amber-50 border border-amber-300 text-xs text-amber-900 flex items-start gap-2.5">
                  <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                  <div>
                    <p className="font-bold">Contract Quota Reached:</p>
                    <p className="mt-0.5 text-amber-800">
                      This contract line item specifies {quotaStatusInModal.maxOccurrences} visit(s). All {quotaStatusInModal.maxOccurrences} slots are already scheduled in the base blueprint. To schedule {activeSlot.weekday}, please remove another assigned day first.
                    </p>
                  </div>
                </div>
              )}

              {/* Periodic Cadence Selection: Monthly or Quarterly (Option B) */}
              {activeSlot.item.frequency_unit === "MONTH" && (
                <div className="p-3.5 rounded-lg bg-indigo-50/50 border border-indigo-100 space-y-2">
                  <label className="text-xs font-bold text-indigo-900 flex items-center gap-1.5">
                    <Calendar className="h-3.5 w-3.5 text-indigo-600" />
                    Target Weeks of the Month:
                  </label>
                  <p className="text-[11px] text-slate-500">
                    Select which week(s) of the month this recurring visit should take place:
                  </p>
                  <div className="flex flex-wrap items-center gap-3 pt-1">
                    {[1, 2, 3, 4].map((wk) => (
                      <label key={wk} className="flex items-center gap-1.5 text-xs font-semibold text-slate-700 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={selectedWeeksOfMonth.includes(wk)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedWeeksOfMonth((prev) => [...prev, wk]);
                            } else {
                              if (selectedWeeksOfMonth.length > 1) {
                                setSelectedWeeksOfMonth((prev) => prev.filter((w) => w !== wk));
                              }
                            }
                          }}
                          className="rounded border-indigo-300 text-indigo-600 focus:ring-indigo-500 h-4 w-4"
                        />
                        <span>Week {wk}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {activeSlot.item.frequency_unit === "QUARTER" && (
                <div className="p-3.5 rounded-lg bg-indigo-50/50 border border-indigo-100 space-y-3">
                  <label className="text-xs font-bold text-indigo-900 flex items-center gap-1.5">
                    <Calendar className="h-3.5 w-3.5 text-indigo-600" />
                    Target Cadence in Quarter:
                  </label>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <span className="block text-[11px] font-semibold text-slate-600 mb-1">Month of Quarter:</span>
                      <select
                        value={selectedQuarterMonth}
                        onChange={(e) => setSelectedQuarterMonth(Number(e.target.value))}
                        className="w-full text-xs py-1.5 px-2.5 rounded-lg border border-slate-200 bg-white"
                      >
                        <option value={1}>Month 1 (Jan / Apr / Jul / Oct)</option>
                        <option value={2}>Month 2 (Feb / May / Aug / Nov)</option>
                        <option value={3}>Month 3 (Mar / Jun / Sep / Dec)</option>
                      </select>
                    </div>

                    <div>
                      <span className="block text-[11px] font-semibold text-slate-600 mb-1">Week of Month:</span>
                      <select
                        value={selectedQuarterWeek}
                        onChange={(e) => setSelectedQuarterWeek(Number(e.target.value))}
                        className="w-full text-xs py-1.5 px-2.5 rounded-lg border border-slate-200 bg-white"
                      >
                        <option value={1}>Week 1</option>
                        <option value={2}>Week 2</option>
                        <option value={3}>Week 3</option>
                        <option value={4}>Week 4</option>
                      </select>
                    </div>
                  </div>
                </div>
              )}

              {/* Convenience Fill Action for Weekly Jobs */}
              {activeSlot.item.frequency_unit === "WEEK" && Number(activeSlot.item.occurrences_per_period) >= 5 && (
                <div className="p-3 rounded-lg bg-indigo-50/40 border border-indigo-100 flex items-center justify-between">
                  <div>
                    <label className="text-xs font-bold text-indigo-900 flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={fillWorkingDays}
                        onChange={(e) => setFillWorkingDays(e.target.checked)}
                        className="rounded border-indigo-300 text-indigo-600 focus:ring-indigo-500 h-4 w-4"
                      />
                      Fill Active Working Days (Mon–Sat) with this crew
                    </label>
                    <p className="text-[11px] text-slate-500 ml-6 mt-0.5">
                      Convenience shortcut: copies this crew across Mon–Sat while preserving Sunday completely.
                    </p>
                  </div>
                </div>
              )}

              {/* Currently Assigned Workers in this Slot */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs text-slate-600 font-semibold">
                  <span>
                    Currently Scheduled Workers ({slotEntries.length} / {activeSlot.item.required_staff_count || 1} Required)
                  </span>
                </div>

                {slotEntries.length >= (activeSlot.item.required_staff_count || 1) && (
                  <div className="p-2 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-medium flex items-center justify-between">
                    <span>✓ Slot Headcount Full ({slotEntries.length} of {activeSlot.item.required_staff_count || 1} staff assigned)</span>
                    <span className="text-[10px] text-emerald-700">Remove a worker using ✕ to replace</span>
                  </div>
                )}

                {slotEntries.length === 0 ? (
                  <p className="text-xs text-slate-400 italic py-2">
                    No workers assigned to this slot yet. Choose from the recommended candidates below.
                  </p>
                ) : (
                  <div className="space-y-1.5">
                    {slotEntries.map((e, idx) => {
                      const isOffDay = isSameWeekday(e.weekly_off_day, activeSlot.weekday);

                      return (
                        <div
                          key={e.employee_id}
                          className={`flex items-center justify-between p-2.5 rounded-lg border shadow-sm ${
                            isOffDay ? "bg-amber-50/50 border-amber-300" : "bg-white border-slate-200"
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <span className="text-xs font-mono font-bold text-slate-400">#{idx + 1}</span>
                            <div>
                              <div className="text-xs font-bold text-slate-900">
                                {e.employee_name}
                                <span className="text-slate-400 font-mono font-normal ml-1.5">
                                  ({e.tally_id})
                                </span>
                              </div>
                              <div className="text-[11px] text-slate-500 flex items-center gap-2 mt-0.5">
                                <span>{e.assigned_hours} hrs/day</span>
                                {e.weekly_off_day && (
                                  <span className="text-slate-600 font-medium">
                                    Weekly Off: {e.weekly_off_day}
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>

                          <div className="flex items-center gap-2">
                            {isOffDay && (
                              <span className="inline-flex items-center gap-1 text-[10px] font-bold text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                                <ShieldAlert className="h-3 w-3" /> Rest Day
                              </span>
                            )}
                            <button
                              onClick={() => handleRemoveEntry(e.employee_id)}
                              className="text-red-500 hover:text-red-700 p-1 rounded hover:bg-red-50 transition-colors"
                              title="Remove worker from slot"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Candidate Worker Recommendations Section */}
              <div className="space-y-3 pt-3 border-t border-slate-200">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <Sparkles className="h-4 w-4 text-indigo-600" />
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                      Candidate Worker Recommendations
                    </h4>
                  </div>

                  {/* Supervisor Crew Filter Toggle inside Modal */}
                  {selectedSupervisorId && (
                    <label className="text-xs font-medium text-indigo-700 flex items-center gap-1.5 cursor-pointer bg-indigo-50 px-2 py-1 rounded border border-indigo-200">
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

                {/* Candidate Search Box */}
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
                  <div className="text-center py-6 text-slate-400 text-xs flex items-center justify-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" /> Loading candidate pool...
                  </div>
                ) : filteredCandidates.length === 0 ? (
                  <p className="text-xs text-slate-400 py-3 text-center">
                    No matching candidates found. Try unchecking the crew filter or clearing the search.
                  </p>
                ) : (
                  <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                    {filteredCandidates.map((cand) => {
                      const requiredHeadcount = activeSlot.item.required_staff_count || 1;
                      const isSlotFull = slotEntries.length >= requiredHeadcount;
                      const isExactMatch = cand.exact_staff_type_match;
                      const isOffDay = isSameWeekday(cand.weekly_off_day, activeSlot.weekday);
                      const isAlreadyAssigned = slotEntries.some((e) => e.employee_id === cand.employee_id);
                      const isBlockedByQuota = quotaStatusInModal.isQuotaReached && !quotaStatusInModal.isCurrentSlotAlreadyScheduled;
                      const isBlockedByHeadcount = isSlotFull && !isAlreadyAssigned;
                      const isCandidateBlocked = cand.is_blocked;
                      const isDisabled = isAlreadyAssigned || isBlockedByQuota || isBlockedByHeadcount || isCandidateBlocked;

                      const remainingHours = Math.max(0, Number(cand.standard_hours) - Number(cand.today_allocated_hours || 0));

                      return (
                        <div
                          key={cand.employee_id}
                          className={`p-2.5 rounded-lg border flex items-center justify-between gap-3 transition-colors ${
                            isDisabled
                              ? "bg-slate-50 border-slate-200 opacity-60"
                              : "bg-white border-slate-200 hover:border-indigo-300"
                          }`}
                        >
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-bold text-slate-900">
                                {cand.name} {isExactMatch && <span className="text-amber-500 font-bold">*</span>}
                              </span>
                              <span className="text-[10px] text-slate-400 font-mono">
                                ({cand.tally_id})
                              </span>
                              {isExactMatch && (
                                <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-amber-50 text-amber-800 border border-amber-200">
                                  Exact Staff Match
                                </span>
                              )}
                            </div>

                            <div className="text-[11px] text-slate-500 flex flex-wrap items-center gap-2">
                              <span>{cand.staff_grade_description || "Staff"}</span>
                              <span>•</span>
                              <span className="font-mono text-slate-600">{cand.grade_code}</span>
                              <span>•</span>
                              <span className={isOffDay ? "text-amber-700 font-bold" : "text-slate-600"}>
                                Off: {cand.weekly_off_day || "None"}
                              </span>
                              {cand.supervisor_name && (
                                <>
                                  <span>•</span>
                                  <span>Supervisor: {cand.supervisor_name}</span>
                                </>
                              )}
                            </div>

                            {/* Capacity or Blocked badge */}
                            {cand.is_blocked ? (
                              <div className="text-[10px] text-rose-700 font-semibold flex items-center gap-1 mt-0.5">
                                <span className="px-1.5 py-0.2 rounded bg-rose-50 border border-rose-200">
                                  Blocked: {cand.blocked_reason}
                                </span>
                              </div>
                            ) : (
                              <div className="flex items-center gap-1.5 mt-0.5">
                                {Number(cand.today_allocated_hours || 0) > 0 ? (
                                  <span className="text-[9px] font-semibold text-indigo-700 bg-indigo-50 border border-indigo-200 px-1.5 py-0.5 rounded">
                                    Remote: {cand.today_allocated_hours}h / {cand.standard_hours}h ({remainingHours.toFixed(1)}h left)
                                  </span>
                                ) : (
                                  <span className="text-[9px] text-slate-500 bg-slate-50 border border-slate-200 px-1.5 py-0.5 rounded">
                                    Available ({cand.standard_hours}h standard)
                                  </span>
                                )}
                              </div>
                            )}

                            {isOffDay && (
                              <div className="text-[10px] text-amber-700 font-semibold flex items-center gap-1">
                                <ShieldAlert className="h-3 w-3" />
                                <span>Rest-Day Warning: Off day is {activeSlot.weekday}</span>
                              </div>
                            )}
                          </div>

                          <button
                            type="button"
                            onClick={() => handleAddCandidate(cand)}
                            disabled={isDisabled}
                            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1 transition-colors ${
                              isDisabled
                                ? "bg-slate-100 text-slate-400 cursor-not-allowed"
                                : "bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 shadow-sm"
                            }`}
                          >
                            <Plus className="h-3.5 w-3.5" />
                            {isAlreadyAssigned
                              ? "Assigned"
                              : isCandidateBlocked
                              ? "Blocked"
                              : isBlockedByHeadcount
                              ? `Slot Full (${slotEntries.length}/${requiredHeadcount})`
                              : isBlockedByQuota
                              ? "Quota Reached"
                              : "Add to Slot"}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setActiveSlot(null)}
                className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-200 transition-colors"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={handleSaveSlot}
                disabled={savingSlot}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors flex items-center gap-1.5 shadow-sm"
              >
                {savingSlot && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                Save Recurring Slot
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
