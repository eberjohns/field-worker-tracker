import React, { useState } from "react";
import { CandidateRecommendation, WorkerAllocationResponse } from "./types";
import { Search, Star, AlertTriangle, X } from "lucide-react";

interface WorkersSidePanelProps {
  candidates: CandidateRecommendation[];
  selectedWorkerId?: string | null;
  onSelectWorker?: (worker: CandidateRecommendation) => void;
  allocation?: WorkerAllocationResponse | null;
  targetJobTitle?: string;
  targetDate?: string;
  onClose?: () => void;
}

export const WorkersSidePanel: React.FC<WorkersSidePanelProps> = ({
  candidates,
  selectedWorkerId,
  onSelectWorker,
  allocation,
  targetJobTitle,
  targetDate,
  onClose,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [onlySameGradeGroup, setOnlySameGradeGroup] = useState(true);

  const filtered = candidates.filter((c) => {
    const matchesSearch =
      c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.tally_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (c.staff_grade_description &&
        c.staff_grade_description.toLowerCase().includes(searchTerm.toLowerCase()));
    return matchesSearch;
  });

  return (
    <div className="w-80 md:w-96 bg-white border-l border-slate-200 flex flex-col h-full shadow-lg">
      {/* Header */}
      <div className="p-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-slate-800 text-sm">Workers Capacity & Ranking</h3>
          {targetJobTitle && (
            <p className="text-xs text-blue-700 font-medium truncate max-w-[240px]">
              For: {targetJobTitle}
            </p>
          )}
          {targetDate && <p className="text-xs text-slate-500">Date: {targetDate}</p>}
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-200"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Selected Worker Allocation Spotlight (if available) */}
      {allocation && (
        <div className="p-3 bg-blue-50/60 border-b border-blue-100 text-xs space-y-2">
          <div className="flex items-center justify-between font-semibold text-blue-900">
            <span>Spotlight: {allocation.employee_name}</span>
            <span>Std: {allocation.effective_daily_standard_hours}h/d</span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div
              className={`p-1.5 rounded border ${
                allocation.today_is_over
                  ? "bg-red-50 border-red-200 text-red-700 font-semibold"
                  : "bg-white border-slate-200 text-slate-700"
              }`}
            >
              <div className="text-[10px] text-slate-500 uppercase">Today</div>
              <div>
                {allocation.today_allocated_hours}/{allocation.today_standard_hours}h
              </div>
            </div>
            <div
              className={`p-1.5 rounded border ${
                allocation.week_is_over
                  ? "bg-red-50 border-red-200 text-red-700 font-semibold"
                  : "bg-white border-slate-200 text-slate-700"
              }`}
            >
              <div className="text-[10px] text-slate-500 uppercase">Week</div>
              <div>
                {allocation.week_allocated_hours}/{allocation.week_standard_hours}h
              </div>
            </div>
            <div className="p-1.5 rounded border bg-white border-slate-200 text-slate-700">
              <div className="text-[10px] text-slate-500 uppercase">Month</div>
              <div>
                {allocation.month_allocated_hours}/{allocation.month_standard_hours}h
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Search and Filters */}
      <div className="p-3 border-b border-slate-200 space-y-2 bg-white">
        <div className="relative">
          <Search className="h-4 w-4 absolute left-2.5 top-2.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search candidate name, ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <div className="flex items-center justify-between text-xs text-slate-600">
          <label className="flex items-center space-x-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={onlySameGradeGroup}
              onChange={(e) => setOnlySameGradeGroup(e.target.checked)}
              className="rounded text-blue-600 focus:ring-blue-500 h-3.5 w-3.5"
            />
            <span>Eligible grade group</span>
          </label>
          <span className="text-slate-400">{filtered.length} candidate(s)</span>
        </div>
      </div>

      {/* Candidate List */}
      <div className="flex-1 overflow-y-auto divide-y divide-slate-100 p-2 space-y-1">
        {filtered.length === 0 ? (
          <div className="p-8 text-center text-slate-400 text-xs">
            No matching workers found for this grade requirement.
          </div>
        ) : (
          filtered.map((worker) => {
            const isSelected = selectedWorkerId === worker.employee_id;
            return (
              <div
                key={worker.employee_id}
                onClick={() => onSelectWorker && onSelectWorker(worker)}
                className={`p-2.5 rounded-lg cursor-pointer transition text-xs space-y-1.5 ${
                  isSelected
                    ? "bg-blue-50 border border-blue-300 shadow-sm"
                    : "hover:bg-slate-50 border border-transparent"
                }`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="font-semibold text-slate-800 flex items-center space-x-1">
                      <span>{worker.name}</span>
                      {worker.exact_staff_type_match && (
                        <span
                          title="Exact staff type match"
                          className="inline-flex items-center text-amber-500 font-bold"
                        >
                          <Star className="h-3 w-3 fill-amber-400 text-amber-500" />
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-500 flex items-center space-x-2">
                      <span className="font-mono">{worker.tally_id}</span>
                      <span>•</span>
                      <span className="font-medium text-slate-700">{worker.grade_code}</span>
                      <span>•</span>
                      <span className="truncate max-w-[130px]">
                        {worker.staff_grade_description}
                      </span>
                    </div>
                  </div>
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-slate-100 text-slate-600">
                    Std: {worker.standard_hours}h
                  </span>
                </div>

                {/* Capacity row */}
                <div className="grid grid-cols-2 gap-2 text-[11px] pt-1 border-t border-slate-100">
                  <div className="text-slate-600">
                    Today: <span className="font-semibold">{worker.today_allocated_hours}h</span>
                  </div>
                  <div className="text-slate-600">
                    Week: <span className="font-semibold">{worker.weekly_allocated_hours}h</span>
                  </div>
                </div>

                {/* Reasons / Warnings */}
                {worker.reasons.length > 0 && (
                  <div className="text-[10px] text-blue-700 flex flex-wrap gap-1">
                    {worker.reasons.slice(0, 2).map((r, idx) => (
                      <span key={idx} className="bg-blue-50 px-1 py-0.5 rounded">
                        ✓ {r}
                      </span>
                    ))}
                  </div>
                )}
                {worker.warnings.length > 0 && (
                  <div className="text-[10px] text-amber-700 bg-amber-50 p-1 rounded flex items-center space-x-1">
                    <AlertTriangle className="h-3 w-3 shrink-0" />
                    <span>{worker.warnings[0]}</span>
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
