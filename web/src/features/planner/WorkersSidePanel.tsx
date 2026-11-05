import React, { useState, useMemo } from "react";
import { RosterWorkerRow, CandidateRecommendation, WorkerAllocationResponse } from "./types";
import { Search, ChevronDown, ChevronRight, X, User } from "lucide-react";

interface WorkersSidePanelProps {
  workers?: RosterWorkerRow[];
  candidates?: CandidateRecommendation[];
  selectedWorkerId?: string | null;
  onSelectWorker?: (workerId: string) => void;
  allocation?: WorkerAllocationResponse | null;
  targetJobTitle?: string;
  targetDate?: string;
  onClose?: () => void;
}

export const WorkersSidePanel: React.FC<WorkersSidePanelProps> = ({
  workers = [],
  selectedWorkerId,
  onSelectWorker,
  allocation,
  targetJobTitle,
  targetDate,
  onClose,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [filterType, setFilterType] = useState<"ALL" | "AVAILABLE" | "OVERTIME">("ALL");
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});

  const toggleGroup = (groupName: string) => {
    setCollapsedGroups((prev) => ({
      ...prev,
      [groupName]: !prev[groupName],
    }));
  };

  // Filter workers based on search and capacity filter
  const filteredWorkers = useMemo(() => {
    return workers.filter((w) => {
      const q = searchTerm.toLowerCase().trim();
      const matchesSearch =
        !q ||
        w.name.toLowerCase().includes(q) ||
        w.tally_id.toLowerCase().includes(q) ||
        (w.grade_code && w.grade_code.toLowerCase().includes(q)) ||
        (w.staff_grade_description && w.staff_grade_description.toLowerCase().includes(q)) ||
        (w.supervisor_name && w.supervisor_name.toLowerCase().includes(q));

      if (!matchesSearch) return false;

      if (filterType === "AVAILABLE") {
        return w.week_is_under;
      }
      if (filterType === "OVERTIME") {
        return w.week_is_over;
      }
      return true;
    });
  }, [workers, searchTerm, filterType]);

  // Group workers by supervisor crew
  const groupedByCrew = useMemo(() => {
    const groups: Record<string, { crewName: string; workers: RosterWorkerRow[]; totalAllocated: number; totalStandard: number }> = {};

    for (const w of filteredWorkers) {
      const crew = w.supervisor_name || "Direct / Independent Staff";
      if (!groups[crew]) {
        groups[crew] = {
          crewName: crew,
          workers: [],
          totalAllocated: 0,
          totalStandard: 0,
        };
      }
      groups[crew].workers.push(w);
      groups[crew].totalAllocated += Number(w.week_allocated_hours || 0);
      groups[crew].totalStandard += Number(w.week_standard_hours || 0);
    }

    return Object.values(groups).sort((a, b) => {
      if (a.crewName === "Direct / Independent Staff") return 1;
      if (b.crewName === "Direct / Independent Staff") return -1;
      return a.crewName.localeCompare(b.crewName);
    });
  }, [filteredWorkers]);

  return (
    <div className="w-80 md:w-96 bg-white border-l border-slate-200 flex flex-col h-full shadow-lg select-none">
      {/* Header */}
      <div className="p-3 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
        <div>
          <div className="flex items-center space-x-2">
            <h3 className="font-bold text-slate-800 text-sm">Workers Capacity</h3>
            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-700">
              {filteredWorkers.length} staff
            </span>
          </div>
          {targetJobTitle && (
            <p className="text-[11px] text-blue-700 font-medium truncate max-w-[240px]">
              For: {targetJobTitle}
            </p>
          )}
          {targetDate && <p className="text-[10px] text-slate-400">Week of {targetDate}</p>}
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-200 transition"
            title="Close panel"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Selected Worker Spotlight (if selected) */}
      {allocation && (
        <div className="p-2.5 bg-blue-50/70 border-b border-blue-200 text-xs space-y-1.5">
          <div className="flex items-center justify-between font-semibold text-blue-900">
            <span className="truncate max-w-[180px] flex items-center space-x-1">
              <User className="h-3.5 w-3.5 text-blue-600" />
              <span>{allocation.employee_name}</span>
            </span>
            <span className="text-[11px] text-slate-500">Std: {Number(allocation.effective_daily_standard_hours).toFixed(0)}h/d</span>
          </div>
          <div className="grid grid-cols-3 gap-1.5 text-center text-[11px]">
            <div
              className={`p-1 rounded border ${
                allocation.today_is_over
                  ? "bg-red-50 border-red-200 text-red-700 font-semibold"
                  : "bg-white border-slate-200 text-slate-700"
              }`}
            >
              <div className="text-[9px] text-slate-400 uppercase font-semibold">Today</div>
              <div>
                {Number(allocation.today_allocated_hours).toFixed(1)} / {Number(allocation.today_standard_hours).toFixed(0)}h
              </div>
            </div>
            <div
              className={`p-1 rounded border ${
                allocation.week_is_over
                  ? "bg-red-50 border-red-200 text-red-700 font-semibold"
                  : allocation.week_is_under
                  ? "bg-amber-50 border-amber-200 text-amber-700 font-semibold"
                  : "bg-white border-slate-200 text-slate-700"
              }`}
            >
              <div className="text-[9px] text-slate-400 uppercase font-semibold">Week</div>
              <div>
                {Number(allocation.week_allocated_hours).toFixed(1)} / {Number(allocation.week_standard_hours).toFixed(0)}h
              </div>
            </div>
            <div className="p-1 rounded border bg-white border-slate-200 text-slate-700">
              <div className="text-[9px] text-slate-400 uppercase font-semibold">Month</div>
              <div>
                {Number(allocation.month_allocated_hours).toFixed(1)} / {Number(allocation.month_standard_hours).toFixed(0)}h
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Search and Quick Filters */}
      <div className="p-2.5 border-b border-slate-200 space-y-2 bg-white">
        <div className="relative">
          <Search className="h-3.5 w-3.5 absolute left-2.5 top-2.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search worker, ID, grade, role..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-8 pr-2.5 py-1 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <div className="flex items-center space-x-1 text-[11px]">
          <button
            onClick={() => setFilterType("ALL")}
            className={`px-2 py-0.5 rounded font-medium transition ${
              filterType === "ALL" ? "bg-slate-800 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            All
          </button>
          <button
            onClick={() => setFilterType("AVAILABLE")}
            className={`px-2 py-0.5 rounded font-medium transition flex items-center space-x-1 ${
              filterType === "AVAILABLE" ? "bg-blue-600 text-white" : "bg-blue-50 text-blue-700 hover:bg-blue-100"
            }`}
          >
            <span>Available (&lt;48h)</span>
          </button>
          <button
            onClick={() => setFilterType("OVERTIME")}
            className={`px-2 py-0.5 rounded font-medium transition flex items-center space-x-1 ${
              filterType === "OVERTIME" ? "bg-red-600 text-white" : "bg-red-50 text-red-700 hover:bg-red-100"
            }`}
          >
            <span>Overtime (&gt;48h)</span>
          </button>
        </div>
      </div>

      {/* Grouped Worker List */}
      <div className="flex-1 overflow-y-auto divide-y divide-slate-100 p-1.5 space-y-2">
        {groupedByCrew.length === 0 ? (
          <div className="p-8 text-center text-slate-400 text-xs">
            No active staff found matching current search.
          </div>
        ) : (
          groupedByCrew.map((group) => {
            const isCollapsed = collapsedGroups[group.crewName];
            return (
              <div key={group.crewName} className="border border-slate-200 rounded-lg overflow-hidden bg-white">
                {/* Crew Group Header */}
                <button
                  type="button"
                  onClick={() => toggleGroup(group.crewName)}
                  className="w-full flex items-center justify-between p-2 bg-slate-50 hover:bg-slate-100 text-left transition"
                >
                  <div className="flex items-center space-x-1.5 truncate pr-2">
                    {isCollapsed ? (
                      <ChevronRight className="h-3.5 w-3.5 text-slate-400 flex-shrink-0" />
                    ) : (
                      <ChevronDown className="h-3.5 w-3.5 text-slate-400 flex-shrink-0" />
                    )}
                    <span className="font-semibold text-xs text-slate-800 truncate">
                      {group.crewName}
                    </span>
                    <span className="text-[10px] text-slate-500 font-medium bg-slate-200/70 px-1.5 py-0.2 rounded-full">
                      {group.workers.length}
                    </span>
                  </div>
                  <div className="text-[10px] font-semibold text-slate-600 whitespace-nowrap">
                    {group.totalAllocated.toFixed(0)}/{group.totalStandard.toFixed(0)}h
                  </div>
                </button>

                {/* Worker Rows inside Crew */}
                {!isCollapsed && (
                  <div className="divide-y divide-slate-100">
                    {group.workers.map((worker) => {
                      const isSelected = selectedWorkerId === worker.employee_id;
                      const allocatedH = Number(worker.week_allocated_hours || 0);
                      const standardH = Number(worker.week_standard_hours || 48);
                      const pct = Math.min(100, Math.round((allocatedH / (standardH || 1)) * 100));

                      let statusBadge = (
                        <span className="text-[10px] font-medium text-emerald-700 bg-emerald-50 px-1 py-0.2 rounded">
                          {allocatedH.toFixed(1)} / {standardH.toFixed(0)}h
                        </span>
                      );
                      if (worker.week_is_under) {
                        const freeH = standardH - allocatedH;
                        statusBadge = (
                          <span className="text-[10px] font-medium text-blue-700 bg-blue-50 px-1 py-0.2 rounded">
                            {allocatedH.toFixed(1)} / {standardH.toFixed(0)}h (-{freeH.toFixed(0)}h)
                          </span>
                        );
                      } else if (worker.week_is_over) {
                        const overH = allocatedH - standardH;
                        statusBadge = (
                          <span className="text-[10px] font-bold text-red-700 bg-red-50 px-1 py-0.2 rounded">
                            {allocatedH.toFixed(1)} / {standardH.toFixed(0)}h (+{overH.toFixed(0)}h)
                          </span>
                        );
                      }

                      return (
                        <div
                          key={worker.employee_id}
                          onClick={() => onSelectWorker && onSelectWorker(worker.employee_id)}
                          className={`p-2 cursor-pointer transition text-xs space-y-1 ${
                            isSelected
                              ? "bg-blue-50/90 border-l-4 border-blue-600"
                              : "hover:bg-slate-50/80"
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-1.5 truncate pr-1">
                              <span className="font-semibold text-slate-800 truncate text-[11px]">
                                {worker.name}
                              </span>
                              <span className="text-[10px] font-mono text-slate-400">
                                #{worker.tally_id}
                              </span>
                            </div>
                            {worker.grade_code && (
                              <span className="px-1 py-0.2 rounded text-[9px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-100 flex-shrink-0">
                                {worker.grade_code}
                              </span>
                            )}
                          </div>

                          <div className="flex items-center justify-between text-[10px]">
                            <span className="text-slate-500 truncate max-w-[170px]">
                              {worker.staff_grade_description || "Field Staff"}
                            </span>
                            {statusBadge}
                          </div>

                          {/* Space-efficient mini progress bar */}
                          <div className="w-full bg-slate-100 h-1 rounded-full overflow-hidden">
                            <div
                              className={`h-full transition-all duration-300 ${
                                worker.week_is_over
                                  ? "bg-red-500"
                                  : worker.week_is_under
                                  ? "bg-blue-500"
                                  : "bg-emerald-500"
                              }`}
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
