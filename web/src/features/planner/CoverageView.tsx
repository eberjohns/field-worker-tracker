import React, { useState } from "react";
import { CoverageResponse, CoverageItemRow, CoverageDayCell } from "./types";
import { Building2, Search, Users, CheckCircle2, Plus } from "lucide-react";

interface CoverageViewProps {
  coverage: CoverageResponse;
  onSlotClick: (worksiteId: string, item: CoverageItemRow, day: CoverageDayCell) => void;
}

export const CoverageView: React.FC<CoverageViewProps> = ({ coverage, onSlotClick }) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [gradeFilter, setGradeFilter] = useState("");

  const daysHeader = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  // Filter worksites and items
  const filteredWorksites = coverage.worksites
    .map((ws) => {
      const matchesWs =
        ws.job_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
        ws.job_name.toLowerCase().includes(searchTerm.toLowerCase());

      const matchedItems = ws.items.filter((it) => {
        const matchesItem =
          matchesWs ||
          it.sub_item_code.toLowerCase().includes(searchTerm.toLowerCase()) ||
          it.staff_grade_description.toLowerCase().includes(searchTerm.toLowerCase()) ||
          it.planned_grade_code.toLowerCase().includes(searchTerm.toLowerCase());

        const matchesGrade = !gradeFilter || it.planned_grade_code.toUpperCase().startsWith(gradeFilter.toUpperCase());

        return matchesItem && matchesGrade;
      });

      return { ...ws, items: matchedItems };
    })
    .filter((ws) => ws.items.length > 0);

  return (
    <div className="flex-1 flex flex-col bg-slate-50 overflow-hidden">
      {/* Subheader Filters */}
      <div className="px-6 py-3 bg-white border-b border-slate-200 flex flex-wrap items-center justify-between gap-4 shrink-0 shadow-2xs">
        <div className="flex items-center space-x-3">
          <div className="relative">
            <Search className="h-4 w-4 absolute left-2.5 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search job #, name, staff grade..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500 w-64"
            />
          </div>
          <input
            type="text"
            placeholder="Filter Grade (e.g. G1)..."
            value={gradeFilter}
            onChange={(e) => setGradeFilter(e.target.value)}
            className="px-2.5 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500 w-40"
          />
        </div>

        {/* Visual Legend */}
        <div className="flex flex-wrap items-center gap-3 text-xs bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600">
          <span className="font-bold text-slate-800">Legend:</span>
          <div className="flex items-center space-x-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
            <span className="text-emerald-700 font-medium">Fully Staffed</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
            <span className="text-amber-700 font-medium">Under-Staffed</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-teal-500" />
            <span className="text-teal-700 font-medium">Quota Met</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-purple-500" />
            <span className="text-purple-700 font-medium">Excess Assigned</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-sky-500" />
            <span className="text-sky-700 font-medium">Public Holiday</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-slate-300" />
            <span className="text-slate-400 font-medium">No Requirement</span>
          </div>
        </div>
      </div>

      {/* Main Table Container with Sticky Persistent Header */}
      <div className="flex-1 overflow-auto p-6">
        {filteredWorksites.length === 0 ? (
          <div className="p-12 text-center text-slate-400 text-xs bg-white rounded-xl border border-slate-200 shadow-2xs">
            No job items found matching your filters.
          </div>
        ) : (
          <div className="border border-slate-200 rounded-xl overflow-hidden shadow-2xs bg-white">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="sticky top-0 z-20 bg-slate-100 border-b border-slate-300 text-slate-600 font-bold text-[10px] uppercase tracking-wider shadow-xs">
                  <tr>
                    <th className="p-3 w-80 min-w-[280px]">Job Item & Required Grade</th>
                    <th className="p-3 w-24 text-center min-w-[90px]">Req Staff</th>
                    <th className="p-3 w-20 text-center min-w-[80px]">Daily Hrs</th>
                    {daysHeader.map((d) => (
                      <th key={d} className="p-3 text-center min-w-[130px]">
                        {d}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredWorksites.map((worksite) => (
                    <React.Fragment key={worksite.worksite_id}>
                      {/* Worksite Banner Row */}
                      <tr className="bg-slate-50/90 border-y border-slate-200">
                        <td colSpan={10} className="px-5 py-3">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="flex items-center space-x-3">
                              <div className="h-7 w-7 rounded-lg bg-blue-600 text-white flex items-center justify-center font-bold text-xs shadow-xs">
                                <Building2 className="h-4 w-4" />
                              </div>
                              <div className="flex items-center space-x-2">
                                <span className="font-bold text-sm text-slate-900 font-mono tracking-tight">
                                  {worksite.job_number}
                                </span>
                                <span className="text-xs font-semibold text-slate-800">{worksite.job_name}</span>
                                {worksite.customer_type && (
                                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-200 text-slate-700">
                                    {worksite.customer_type}
                                  </span>
                                )}
                                <span
                                  className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                    worksite.is_outdoor
                                      ? "bg-amber-100 text-amber-800"
                                      : "bg-blue-100 text-blue-800"
                                  }`}
                                >
                                  {worksite.is_outdoor ? "Outdoor" : "Indoor"}
                                </span>
                              </div>
                            </div>

                            <div className="text-xs text-slate-500 font-medium">
                              {worksite.items.length} job item requirement(s)
                            </div>
                          </div>
                        </td>
                      </tr>

                      {/* Worksite Job Item Rows */}
                      {worksite.items.map((item) => (
                        <tr key={item.job_item_id} className="hover:bg-slate-50/50 transition">
                          {/* Job Item Info with Prominent Grade Code */}
                          <td className="p-3 align-top">
                            <div className="font-bold text-slate-900 text-xs">
                              Item {item.sub_item_code}: {item.staff_grade_description}
                            </div>
                            <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                              <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-blue-50 border border-blue-200 text-blue-700 shadow-2xs">
                                Required: {item.planned_grade_code}
                              </span>
                              {item.frequency_unit && (
                                <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-200">
                                  {item.frequency_unit === "WEEK"
                                    ? Number(item.occurrences_per_period || 6) >= 6
                                      ? "Daily (6d/wk)"
                                      : `${Number(item.occurrences_per_period || 1).toFixed(0)}x/week`
                                    : item.frequency_unit === "MONTH"
                                    ? `${Number(item.occurrences_per_period || 1).toFixed(0)}x/month`
                                    : `${Number(item.occurrences_per_period || 1).toFixed(0)}x/${item.frequency_unit.toLowerCase()}`}
                                </span>
                              )}
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600">
                                {item.deployment_type}
                              </span>
                            </div>
                          </td>

                          {/* Required Staff */}
                          <td className="p-3 text-center align-top font-bold text-slate-800 text-sm">
                            <div className="flex items-center justify-center space-x-1">
                              <Users className="h-3.5 w-3.5 text-slate-400" />
                              <span>{item.required_staff_count}</span>
                            </div>
                          </td>

                          {/* Daily Hours */}
                          <td className="p-3 text-center align-top text-slate-600 font-semibold">
                            {Number(item.hours_per_occurrence).toFixed(1)}h
                          </td>

                          {/* 7 Days Staffing Cells */}
                          {item.days.map((day) => {
                            const hasRequirement = day.required_staff_count > 0;
                            const assignedCount = day.assigned_staff_count;
                            const neededCount = Math.max(0, day.required_staff_count - assignedCount);
                            const isExcess =
                              day.is_excess ||
                              (assignedCount > day.required_staff_count) ||
                              (!hasRequirement && assignedCount > 0);
                            const isFullyStaffed = hasRequirement && assignedCount === day.required_staff_count;
                            const isUnderStaffed = hasRequirement && assignedCount < day.required_staff_count;
                            const excessCount = !hasRequirement
                              ? assignedCount
                              : Math.max(1, assignedCount - day.required_staff_count);

                            return (
                              <td
                                key={day.work_date}
                                onClick={() => onSlotClick(worksite.worksite_id, item, day)}
                                className={`p-2 align-top text-center cursor-pointer transition border-l border-slate-100 group ${
                                  isExcess
                                    ? "bg-purple-50/60 hover:bg-purple-100/70 border-b-2 border-b-purple-500"
                                    : day.is_holiday && assignedCount === 0
                                    ? "bg-sky-50/50 hover:bg-sky-100/60 border-b-2 border-sky-400 text-sky-800"
                                    : day.is_quota_met && assignedCount === 0
                                    ? "bg-teal-50/30 hover:bg-teal-50/50 border-b border-teal-300 text-teal-800"
                                    : !hasRequirement
                                    ? "bg-slate-50/40 text-slate-400"
                                    : isUnderStaffed
                                    ? "bg-amber-50/40 hover:bg-amber-100/50 border-b-2 border-b-amber-400"
                                    : "bg-emerald-50/20 hover:bg-emerald-100/40 border-b-2 border-b-emerald-400"
                                }`}
                              >
                                {hasRequirement || assignedCount > 0 ? (
                                  <div className="space-y-1.5">
                                    {/* Status Ratio Pill */}
                                    <div className="flex items-center justify-between">
                                      <span
                                        className={`text-[11px] font-bold ${
                                          isExcess
                                            ? "text-purple-700 font-extrabold"
                                            : isFullyStaffed
                                            ? "text-emerald-700"
                                            : assignedCount === 0
                                            ? "text-red-700 font-extrabold"
                                            : "text-amber-700"
                                        }`}
                                      >
                                        {assignedCount} / {day.required_staff_count}
                                      </span>

                                      {isExcess ? (
                                        <span className="inline-flex items-center px-1.5 py-0.2 rounded text-[9px] font-bold bg-purple-100 text-purple-800 border border-purple-200 shadow-2xs">
                                          +{excessCount} Excess
                                        </span>
                                      ) : isFullyStaffed ? (
                                        <span className="inline-flex items-center text-emerald-600">
                                          <CheckCircle2 className="h-3.5 w-3.5" />
                                        </span>
                                      ) : (
                                        <span className="inline-flex items-center px-1.5 py-0.2 rounded text-[9px] font-bold bg-amber-100 text-amber-800">
                                          +{neededCount} needed
                                        </span>
                                      )}
                                    </div>

                                    {/* Assigned Workers Chips */}
                                    {day.assigned_workers.length > 0 && (
                                      <div className="space-y-0.5 text-left">
                                        {day.assigned_workers.map((wName, wIdx) => {
                                          const isWorkerExcess =
                                            !hasRequirement || wIdx >= day.required_staff_count;
                                          return (
                                            <div
                                              key={wIdx}
                                              className={`text-[10px] font-medium px-1.5 py-0.5 rounded truncate shadow-2xs ${
                                                isWorkerExcess
                                                  ? "bg-purple-50 border border-purple-300 text-purple-900 font-semibold"
                                                  : "bg-white/90 border border-slate-200 text-slate-800"
                                              }`}
                                              title={isWorkerExcess ? `${wName} (Excess Staff)` : wName}
                                            >
                                              • {wName}{" "}
                                              {isWorkerExcess && (
                                                <span className="text-[9px] text-purple-600 font-bold">
                                                  (Excess)
                                                </span>
                                              )}
                                            </div>
                                          );
                                        })}
                                      </div>
                                    )}

                                    {/* Quick assign / edit prompt on hover */}
                                    <div className="pt-1 opacity-0 group-hover:opacity-100 transition">
                                      <span
                                        className={`inline-flex items-center justify-center w-full py-0.5 rounded text-[10px] font-bold shadow-xs ${
                                          isExcess
                                            ? "bg-purple-700 text-white"
                                            : isUnderStaffed
                                            ? "bg-blue-600 text-white"
                                            : "bg-slate-800 text-white"
                                        }`}
                                      >
                                        {isUnderStaffed ? (
                                          <>
                                            <Plus className="h-3 w-3 mr-0.5" />
                                            Assign
                                          </>
                                        ) : (
                                          "Edit / Unassign"
                                        )}
                                      </span>
                                    </div>
                                  </div>
                                ) : day.is_holiday ? (
                                  <div className="py-2 px-1 text-center space-y-1">
                                    <span className="inline-block px-1.5 py-0.5 rounded text-[9px] font-bold bg-sky-100 text-sky-800 border border-sky-200 shadow-2xs">
                                      HOLIDAY
                                    </span>
                                    <p
                                      className="text-[10px] font-semibold text-sky-900 truncate"
                                      title={day.holiday_name || "Official Public Holiday"}
                                    >
                                      {day.holiday_name || "Public Holiday"}
                                    </p>
                                  </div>
                                ) : day.is_quota_met ? (
                                  <div className="py-2.5 text-center space-y-0.5">
                                    <div className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold bg-teal-100/80 text-teal-800 border border-teal-200 shadow-2xs">
                                      <CheckCircle2 className="h-3 w-3 text-teal-600" />
                                      <span>Quota Met</span>
                                    </div>
                                  </div>
                                ) : (
                                  <div className="py-3 text-[10px] text-slate-300 font-mono">-</div>
                                )}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
