import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  PanelRightOpen,
  PanelRightClose,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import {
  RosterResponse,
  CoverageResponse,
  RosterWorkerRow,
  CoverageItemRow,
  CoverageDayCell,
  WorkerAllocationResponse,
  CandidateRecommendation,
} from "../features/planner/types";
import { RosterView } from "../features/planner/RosterView";
import { CoverageView } from "../features/planner/CoverageView";
import { WorkersSidePanel } from "../features/planner/WorkersSidePanel";
import { AssignModal } from "../features/planner/AssignModal";

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

export const Planner: React.FC = () => {
  const { token } = useAuth();

  // Navigation & Tabs
  const [activeTab, setActiveTab] = useState<"ROSTER" | "COVERAGE">("COVERAGE");
  const [weekStartDate, setWeekStartDate] = useState<string>(() => {
    const now = new Date();
    const day = now.getDay();
    const diff = now.getDate() - day + (day === 0 ? -6 : 1); // adjust when day is sunday
    const monday = new Date(now.setDate(diff));
    return monday.toISOString().split("T")[0];
  });

  // Filters & Display
  const [compactMode, setCompactMode] = useState<boolean>(false);
  const [problemsOnly, setProblemsOnly] = useState<boolean>(false);
  const [staffTypeFilter, setStaffTypeFilter] = useState<string>("");
  const [gradeGroupFilter, setGradeGroupFilter] = useState<string>("");
  const [isSidePanelOpen, setIsSidePanelOpen] = useState<boolean>(true);
  const [supervisorsList, setSupervisorsList] = useState<{ id: string; name: string }[]>([]);
  const [selectedSupervisorId, setSelectedSupervisorId] = useState<string | null>(null);

  // Data State
  const [rosterData, setRosterData] = useState<RosterResponse | null>(null);
  const [coverageData, setCoverageData] = useState<CoverageResponse | null>(null);
  const [availableJobItems, setAvailableJobItems] = useState<any[]>([]);
  const [candidates, setCandidates] = useState<CandidateRecommendation[]>([]);
  const [selectedWorkerAllocation, setSelectedWorkerAllocation] =
    useState<WorkerAllocationResponse | null>(null);

  // Selection & Modal State
  const [selectedWorkerId, setSelectedWorkerId] = useState<string | null>(null);
  const [isAssignModalOpen, setIsAssignModalOpen] = useState<boolean>(false);
  const [modalInitialWorkerId, setModalInitialWorkerId] = useState<string | null>(null);
  const [modalInitialDate, setModalInitialDate] = useState<string | null>(null);
  const [modalInitialJobItemId, setModalInitialJobItemId] = useState<string | null>(null);

  // Coverage Selected Slot State
  const [selectedCoverageItem, setSelectedCoverageItem] = useState<CoverageItemRow | null>(null);
  const [selectedCoverageDay, setSelectedCoverageDay] = useState<CoverageDayCell | null>(null);
  const [selectedWorksiteInfo, setSelectedWorksiteInfo] = useState<{
    id: string;
    job_number: string;
    job_name: string;
  } | null>(null);

  const [loading, setLoading] = useState<boolean>(false);
  const [exportingExcel, setExportingExcel] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const selectedSupervisorName =
    supervisorsList.find((s) => s.id === selectedSupervisorId)?.name || null;

  // Headers helper
  const authHeaders = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  // Navigate week
  const changeWeek = (offsetDays: number) => {
    const cur = new Date(weekStartDate);
    cur.setDate(cur.getDate() + offsetDays);
    setWeekStartDate(cur.toISOString().split("T")[0]);
  };

  // Fetch data
  const fetchData = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const rosterParams = new URLSearchParams({
        week_start: weekStartDate,
        problems_only: problemsOnly ? "true" : "false",
      });
      if (staffTypeFilter) rosterParams.append("staff_type", staffTypeFilter);
      if (gradeGroupFilter) rosterParams.append("grade_group", gradeGroupFilter);

      const [covRes, rosRes] = await Promise.all([
        fetch(`/api/v1/schedule/coverage?week_start=${weekStartDate}`, { headers: authHeaders }),
        fetch(`/api/v1/roster?${rosterParams.toString()}`, { headers: authHeaders }),
      ]);

      if (covRes.ok) {
        const data: CoverageResponse = await covRes.json();
        setCoverageData(data);
      } else if (activeTab === "COVERAGE") {
        throw new Error("Failed to load coverage view.");
      }

      if (rosRes.ok) {
        const data: RosterResponse = await rosRes.json();
        setRosterData(data);
      } else if (activeTab === "ROSTER") {
        throw new Error("Failed to load weekly roster.");
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to load scheduling data.");
    } finally {
      setLoading(false);
    }
  };

  // Fetch supervisors for crew filter
  const fetchSupervisors = async () => {
    try {
      const res = await fetch("/api/v1/employees?role=SUPERVISOR&limit=200", {
        headers: authHeaders,
      });
      if (res.ok) {
        const data = await res.json();
        const items = data.items || data || [];
        const list = items.map((emp: any) => ({
          id: emp.id,
          name: emp.name || emp.tally_id || "Supervisor",
          tally_id: emp.tally_id,
        }));
        setSupervisorsList(list);
      }
    } catch (err) {
      console.error("Failed to fetch supervisors:", err);
    }
  };

  // Fetch available job items for assignment modal
  const fetchJobItems = async () => {
    try {
      const res = await fetch("/api/v1/worksites?limit=200", { headers: authHeaders });
      if (res.ok) {
        const worksites = await res.json();
        const itemsList: any[] = [];
        for (const ws of worksites) {
          if (ws.items) {
            for (const it of ws.items) {
              itemsList.push({
                id: it.id,
                worksite_id: ws.id,
                job_number: ws.job_number,
                job_name: ws.job_name,
                sub_item_code: it.sub_item_code,
                staff_grade_description: it.staff_grade_description,
                planned_grade_code: it.planned_grade_code,
                deployment_type: it.deployment_type,
                hours_per_occurrence: parseFloat(it.hours_per_occurrence_per_staff) || 8.0,
                weekday_pattern: it.weekday_pattern,
              });
            }
          }
        }
        setAvailableJobItems(itemsList);
      }
    } catch (err) {
      console.error("Failed to fetch job items:", err);
    }
  };

  // Fetch candidate recommendations
  const fetchCandidates = async (jobItemId?: string, targetDate?: string) => {
    try {
      const dateParam = targetDate || weekStartDate;
      const url = jobItemId
        ? `/api/v1/job-items/${jobItemId}/recommendations?date=${dateParam}`
        : `/api/v1/roster?week_start=${weekStartDate}`; // fallback

      if (jobItemId) {
        const res = await fetch(url, { headers: authHeaders });
        if (res.ok) {
          const data: CandidateRecommendation[] = await res.json();
          setCandidates(data);
        }
      } else if (rosterData && rosterData.workers) {
        // Map from roster workers
        const mapped: CandidateRecommendation[] = rosterData.workers.map((w) => {
          const weekHours = Number(w.week_allocated_hours || 0);
          return {
            employee_id: w.employee_id,
            name: w.name,
            tally_id: w.tally_id,
            grade_code: w.grade_code,
            staff_grade_description: w.staff_grade_description,
            standard_hours: Number(w.standard_hours || 8),
            exact_staff_type_match: false,
            ranking_score: 50.0,
            reasons: [],
            warnings: [],
            today_allocated_hours: 0,
            weekly_allocated_hours: weekHours,
            monthly_allocated_hours: weekHours * 4,
          };
        });
        setCandidates(mapped);
      }
    } catch (err) {
      console.error("Failed to fetch candidates:", err);
    }
  };

  // Fetch worker allocation for side panel spotlight
  const fetchWorkerAllocation = async (workerId: string) => {
    try {
      const res = await fetch(
        `/api/v1/workers/${workerId}/allocation?work_date=${weekStartDate}`,
        { headers: authHeaders }
      );
      if (res.ok) {
        const data: WorkerAllocationResponse = await res.json();
        setSelectedWorkerAllocation(data);
      }
    } catch (err) {
      console.error("Failed to fetch worker allocation:", err);
    }
  };

  useEffect(() => {
    fetchData();
    fetchJobItems();
    fetchSupervisors();
  }, [activeTab, weekStartDate, problemsOnly, staffTypeFilter, gradeGroupFilter]);

  // Synchronize supervisors list with roster workers
  useEffect(() => {
    if (!rosterData?.workers) return;
    setSupervisorsList((prev) => {
      const map = new Map<string, string>();
      prev.forEach((s) => map.set(s.id, s.name));
      rosterData.workers.forEach((w) => {
        if (w.supervisor_id && !map.has(w.supervisor_id)) {
          map.set(w.supervisor_id, w.supervisor_name || "Supervisor");
        }
      });
      return Array.from(map.entries()).map(([id, name]) => ({ id, name }));
    });
  }, [rosterData]);

  // Export Excel handler
  const handleExportExcel = async () => {
    setExportingExcel(true);
    try {
      const res = await fetch(`/api/v1/roster?week_start=${weekStartDate}&format=xlsx`, {
        headers: authHeaders,
      });
      if (!res.ok) throw new Error("Failed to export Excel roster.");

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `roster_${weekStartDate}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(err.message || "Failed to download Excel export.");
    } finally {
      setExportingExcel(false);
    }
  };

  // Worker select
  const handleWorkerSelect = (worker: RosterWorkerRow) => {
    setSelectedWorkerId(worker.employee_id);
    fetchWorkerAllocation(worker.employee_id);
    setIsSidePanelOpen(true);
  };

  // Slot click in Coverage view
  const handleCoverageSlotClick = (
    worksiteId: string,
    item: CoverageItemRow,
    day: CoverageDayCell
  ) => {
    setSelectedCoverageItem(item);
    setSelectedCoverageDay(day);
    const ws = coverageData?.worksites.find((w) => w.worksite_id === worksiteId);
    setSelectedWorksiteInfo(
      ws ? { id: ws.worksite_id, job_number: ws.job_number, job_name: ws.job_name } : null
    );
    setModalInitialJobItemId(item.job_item_id);
    setModalInitialDate(day.work_date);
    setModalInitialWorkerId(null);
    fetchCandidates(item.job_item_id, day.work_date);
    setIsAssignModalOpen(true);
  };

  return (
    <div className="flex flex-col h-full bg-slate-100 overflow-hidden">
      {/* Top Planner Navigation Bar */}
      <div className="px-6 py-4 bg-white border-b border-slate-200 flex flex-wrap items-center justify-between gap-4 shrink-0 shadow-2xs">
        <div className="flex items-center space-x-3">
          <div className="h-10 w-10 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-600">
            <CalendarDays className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-slate-900 leading-tight">Planner & Roster</h1>
            <p className="text-xs text-slate-500">
              Manage the year plan, inspect weekly roster, and balance worker capacity
            </p>
          </div>
        </div>

        {/* View Lens Tabs */}
        <div className="flex items-center bg-slate-100 p-1 rounded-xl">
          <button
            onClick={() => setActiveTab("COVERAGE")}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition ${
              activeTab === "COVERAGE"
                ? "bg-white text-blue-700 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Job Items Planning
          </button>
          <button
            onClick={() => setActiveTab("ROSTER")}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition ${
              activeTab === "ROSTER"
                ? "bg-white text-blue-700 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Weekly Worker Roster
          </button>
        </div>

        {/* Week navigation, Crew Filter & Side panel toggle */}
        <div className="flex items-center space-x-2">
          {/* Crew / Supervisor Filter Dropdown */}
          <div className="flex items-center space-x-1">
            <select
              value={selectedSupervisorId || ""}
              onChange={(e) => setSelectedSupervisorId(e.target.value || null)}
              className="px-2.5 py-1.5 text-xs font-medium border border-slate-200 rounded-lg bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-2xs cursor-pointer max-w-[200px] truncate"
              title="Filter by Supervisor's Crew"
            >
              <option value="">All Crews ({supervisorsList.length})</option>
              {supervisorsList.map((sup) => (
                <option key={sup.id} value={sup.id}>
                  Crew: {sup.name}
                </option>
              ))}
            </select>
            {selectedSupervisorId && (
              <button
                onClick={() => setSelectedSupervisorId(null)}
                className="text-xs text-slate-400 hover:text-slate-700 px-1 py-1"
                title="Clear crew filter"
              >
                ✕
              </button>
            )}
          </div>

          <div className="flex items-center bg-slate-100 rounded-lg p-0.5 border border-slate-200">
            <button
              onClick={() => changeWeek(-7)}
              title="Previous Week"
              className="p-1.5 text-slate-600 hover:text-slate-900 hover:bg-white rounded transition"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="px-3 text-xs font-bold text-slate-800 font-sans">
              {formatReadableWeek(weekStartDate)}
            </span>
            <button
              onClick={() => changeWeek(7)}
              title="Next Week"
              className="p-1.5 text-slate-600 hover:text-slate-900 hover:bg-white rounded transition"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          <button
            onClick={() => setIsSidePanelOpen(!isSidePanelOpen)}
            className={`p-2 rounded-lg border text-xs font-semibold flex items-center space-x-1.5 transition ${
              isSidePanelOpen
                ? "bg-blue-50 border-blue-200 text-blue-700"
                : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
            }`}
          >
            {isSidePanelOpen ? (
              <PanelRightClose className="h-4 w-4" />
            ) : (
              <PanelRightOpen className="h-4 w-4" />
            )}
            <span className="hidden sm:inline">Capacity Panel</span>
          </button>
        </div>
      </div>

      {/* Filter and Mode Bar */}
      {activeTab === "ROSTER" && (
        <div className="px-6 py-2.5 bg-slate-50 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3 shrink-0 text-xs text-slate-600">
          <div className="flex items-center space-x-4">
            <label className="flex items-center space-x-1.5 cursor-pointer font-medium">
              <input
                type="checkbox"
                checked={problemsOnly}
                onChange={(e) => setProblemsOnly(e.target.checked)}
                className="rounded text-blue-600 focus:ring-blue-500 h-3.5 w-3.5"
              />
              <span className={problemsOnly ? "font-bold text-red-600" : ""}>
                Show only problems (Over/Under hours)
              </span>
            </label>

            <label className="flex items-center space-x-1.5 cursor-pointer font-medium">
              <input
                type="checkbox"
                checked={compactMode}
                onChange={(e) => setCompactMode(e.target.checked)}
                className="rounded text-blue-600 focus:ring-blue-500 h-3.5 w-3.5"
              />
              <span>Compact chip mode</span>
            </label>
          </div>

          <div className="flex items-center space-x-3">
            <input
              type="text"
              placeholder="Filter Staff Type..."
              value={staffTypeFilter}
              onChange={(e) => setStaffTypeFilter(e.target.value)}
              className="px-2.5 py-1 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500 w-36"
            />
            <input
              type="text"
              placeholder="Grade Group (e.g. G1)..."
              value={gradeGroupFilter}
              onChange={(e) => setGradeGroupFilter(e.target.value)}
              className="px-2.5 py-1 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500 w-36"
            />
          </div>
        </div>
      )}

      {/* Main Workspace with Content and Side Panel */}
      <div className="flex-1 flex overflow-hidden">
        {/* Content View */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {loading && (
            <div className="px-6 py-2 bg-blue-50 border-b border-blue-100 flex items-center space-x-2 text-xs text-blue-700">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Loading scheduling data...</span>
            </div>
          )}

          {errorMsg && (
            <div className="m-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-xl text-xs flex items-center space-x-2">
              <AlertTriangle className="h-4 w-4 shrink-0 text-red-600" />
              <span>{errorMsg}</span>
            </div>
          )}

          {activeTab === "ROSTER" && rosterData && (
            <RosterView
              roster={rosterData}
              compactMode={compactMode}
              onWorkerSelect={handleWorkerSelect}
              selectedWorkerId={selectedWorkerId}
              onExportExcel={handleExportExcel}
              exportingExcel={exportingExcel}
            />
          )}

          {activeTab === "COVERAGE" && coverageData && (
            <CoverageView coverage={coverageData} onSlotClick={handleCoverageSlotClick} />
          )}
        </div>

        {/* Worker Capacity Side Panel */}
        {isSidePanelOpen && (
          <WorkersSidePanel
            workers={rosterData?.workers || []}
            candidates={candidates}
            selectedWorkerId={selectedWorkerId}
            selectedSupervisorId={selectedSupervisorId}
            onSelectWorker={(workerId) => {
              setSelectedWorkerId(workerId);
              fetchWorkerAllocation(workerId);
            }}
            allocation={selectedWorkerAllocation}
            targetDate={weekStartDate}
            onClose={() => setIsSidePanelOpen(false)}
          />
        )}
      </div>

      {/* Assignment Modal */}
      {isAssignModalOpen && (
        <AssignModal
          isOpen={isAssignModalOpen}
          onClose={() => setIsAssignModalOpen(false)}
          onSuccess={() => {
            fetchData();
            if (selectedWorkerId) fetchWorkerAllocation(selectedWorkerId);
          }}
          token={token}
          targetJobItem={selectedCoverageItem}
          targetDay={selectedCoverageDay}
          worksiteInfo={selectedWorksiteInfo}
          initialWorkerId={modalInitialWorkerId}
          initialDate={modalInitialDate}
          initialJobItemId={modalInitialJobItemId}
          availableJobItems={availableJobItems}
          selectedSupervisorId={selectedSupervisorId}
          selectedSupervisorName={selectedSupervisorName}
        />
      )}
    </div>
  );
};
