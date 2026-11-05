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

        <div className="text-xs text-slate-500 flex items-center space-x-4">
          <div className="flex items-center space-x-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
            <span>Staffed</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
            <span>Partial / To Cover</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-red-500" />
            <span>Unstaffed</span>
          </div>
        </div>
      </div>

      {/* Main Table Container */}
      <div className="flex-1 overflow-auto p-6 space-y-6">
        {filteredWorksites.length === 0 ? (
          <div className="p-12 text-center text-slate-400 text-xs bg-white rounded-xl border border-slate-200 shadow-2xs">
            No job items found matching your filters.
          </div>
        ) : (
          filteredWorksites.map((worksite) => (
            <div
              key={worksite.worksite_id}
              className="border border-slate-200 rounded-xl overflow-hidden shadow-2xs bg-white"
            >
              {/* Job Header */}
              <div className="px-5 py-3.5 bg-slate-100/70 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center space-x-3">
                  <div className="h-8 w-8 rounded-lg bg-blue-600 text-white flex items-center justify-center font-bold text-xs shadow-xs">
                    <Building2 className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-sm text-slate-900 font-mono tracking-tight">
                        {worksite.job_number}
                      </span>
                      <span className="text-xs font-semibold text-slate-700">{worksite.job_name}</span>
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
                </div>

                <div className="text-xs text-slate-500 font-medium">
                  {worksite.items.length} job item requirement(s)
                </div>
              </div>

              {/* Items Table */}
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-bold text-[10px] uppercase tracking-wider">
                    <tr>
                      <th className="p-3 w-80">Job Item & Required Grade</th>
                      <th className="p-3 w-24 text-center">Req Staff</th>
                      <th className="p-3 w-20 text-center">Daily Hrs</th>
                      {daysHeader.map((d) => (
                        <th key={d} className="p-3 text-center min-w-[130px]">
                          {d}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {worksite.items.map((item) => (
                      <tr key={item.job_item_id} className="hover:bg-slate-50/50 transition">
                        {/* Job Item Info with Prominent Grade Code */}
                        <td className="p-3 align-top">
                          <div className="font-bold text-slate-900 text-xs">
                            Item {item.sub_item_code}: {item.staff_grade_description}
                          </div>
                          <div className="flex items-center space-x-2 mt-1.5">
                            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-blue-50 border border-blue-200 text-blue-700 shadow-2xs">
                              Required: {item.planned_grade_code}
                            </span>
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
                          const isFullyStaffed = hasRequirement && assignedCount >= day.required_staff_count;
                          const isUnderStaffed = hasRequirement && assignedCount < day.required_staff_count;

                          return (
                            <td
                              key={day.work_date}
                              onClick={() => onSlotClick(worksite.worksite_id, item, day)}
                              className={`p-2 align-top text-center cursor-pointer transition border-l border-slate-100 group ${
                                !hasRequirement
                                  ? "bg-slate-50/40 text-slate-400"
                                  : isUnderStaffed
                                  ? "bg-amber-50/40 hover:bg-amber-100/50 border-b-2 border-b-amber-400"
                                  : "bg-emerald-50/20 hover:bg-emerald-100/40 border-b-2 border-b-emerald-400"
                              }`}
                            >
                              {hasRequirement ? (
                                <div className="space-y-1.5">
                                  {/* Status Ratio Pill */}
                                  <div className="flex items-center justify-between">
                                    <span
                                      className={`text-[11px] font-bold ${
                                        isFullyStaffed
                                          ? "text-emerald-700"
                                          : assignedCount === 0
                                          ? "text-red-700 font-extrabold"
                                          : "text-amber-700"
                                      }`}
                                    >
                                      {assignedCount} / {day.required_staff_count}
                                    </span>

                                    {isFullyStaffed ? (
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
                                      {day.assigned_workers.map((wName, wIdx) => (
                                        <div
                                          key={wIdx}
                                          className="text-[10px] font-medium bg-white/90 border border-slate-200 px-1.5 py-0.5 rounded text-slate-800 truncate shadow-2xs"
                                          title={wName}
                                        >
                                          • {wName}
                                        </div>
                                      ))}
                                    </div>
                                  )}

                                  {/* Quick assign prompt on hover */}
                                  {isUnderStaffed && (
                                    <div className="pt-1 opacity-0 group-hover:opacity-100 transition">
                                      <span className="inline-flex items-center justify-center w-full py-0.5 rounded bg-blue-600 text-white text-[10px] font-bold shadow-xs">
                                        <Plus className="h-3 w-3 mr-0.5" />
                                        Assign
                                      </span>
                                    </div>
                                  )}
                                </div>
                              ) : (
                                <div className="py-3 text-[10px] text-slate-300 font-mono">-</div>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
