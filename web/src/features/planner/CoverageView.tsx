import React from "react";
import { CoverageResponse, CoverageItemRow, CoverageDayCell } from "./types";
import { Building2 } from "lucide-react";

interface CoverageViewProps {
  coverage: CoverageResponse;
  onSlotClick: (worksiteId: string, item: CoverageItemRow, day: CoverageDayCell) => void;
}

export const CoverageView: React.FC<CoverageViewProps> = ({ coverage, onSlotClick }) => {
  const daysHeader = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  return (
    <div className="flex-1 flex flex-col bg-white overflow-auto p-6 space-y-6">
      <div className="text-xs text-slate-500 font-medium">
        Job Coverage View for week <span className="font-bold text-slate-800">{coverage.week_start}</span> to{" "}
        <span className="font-bold text-slate-800">{coverage.week_end}</span>. Click any understaffed slot to assign workers.
      </div>

      {coverage.worksites.length === 0 ? (
        <div className="p-12 text-center text-slate-400 text-xs bg-slate-50 rounded-xl border border-slate-200">
          No worksites found for this scope.
        </div>
      ) : (
        coverage.worksites.map((worksite) => (
          <div
            key={worksite.worksite_id}
            className="border border-slate-200 rounded-xl overflow-hidden shadow-2xs bg-white"
          >
            {/* Worksite Header */}
            <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Building2 className="h-4 w-4 text-blue-600" />
                <span className="font-bold text-sm text-slate-900">{worksite.job_number}</span>
                <span className="text-xs text-slate-600 font-medium">{worksite.job_name}</span>
              </div>
              <span className="text-xs text-slate-400 font-semibold">
                {worksite.items.length} job item(s)
              </span>
            </div>

            {/* Items Table */}
            <table className="w-full text-left text-xs border-collapse">
              <thead className="bg-slate-100/70 border-b border-slate-200 text-slate-600 font-semibold text-[10px] uppercase">
                <tr>
                  <th className="p-2.5 w-72">Job Item & Requirement</th>
                  <th className="p-2.5 w-20 text-center">Req Staff</th>
                  <th className="p-2.5 w-20 text-center">Hours</th>
                  {daysHeader.map((d) => (
                    <th key={d} className="p-2 text-center w-28">
                      {d}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {worksite.items.map((item) => (
                  <tr key={item.job_item_id} className="hover:bg-slate-50/60 transition">
                    <td className="p-2.5">
                      <div className="font-bold text-slate-800">
                        Item {item.sub_item_code}: {item.staff_grade_description}
                      </div>
                      <div className="text-[10px] text-slate-400 flex items-center space-x-1.5 mt-0.5">
                        <span className="font-semibold text-blue-700">{item.planned_grade_code}</span>
                        <span>•</span>
                        <span className="font-medium">{item.deployment_type}</span>
                      </div>
                    </td>
                    <td className="p-2.5 text-center font-bold text-slate-700">
                      {item.required_staff_count}
                    </td>
                    <td className="p-2.5 text-center text-slate-600 font-semibold">
                      {item.hours_per_occurrence}h
                    </td>

                    {/* 7 Days Staffing Cells */}
                    {item.days.map((day) => {
                      const isUncovered = day.is_to_be_covered;
                      const hasRequirement = day.required_staff_count > 0;

                      return (
                        <td
                          key={day.work_date}
                          onClick={() => onSlotClick(worksite.worksite_id, item, day)}
                          className={`p-1.5 text-center cursor-pointer transition border-l border-slate-100 ${
                            isUncovered
                              ? "bg-red-50/70 hover:bg-red-100/70"
                              : hasRequirement
                              ? "bg-emerald-50/50 hover:bg-emerald-100/50"
                              : "hover:bg-slate-100/50"
                          }`}
                        >
                          {hasRequirement ? (
                            <div className="space-y-0.5">
                              <div
                                className={`text-xs font-bold ${
                                  isUncovered ? "text-red-700" : "text-emerald-700"
                                }`}
                              >
                                {day.assigned_staff_count} / {day.required_staff_count}
                              </div>
                              {isUncovered ? (
                                <span className="inline-block px-1 py-0.2 bg-red-100 text-red-800 text-[9px] font-bold rounded">
                                  COVER
                                </span>
                              ) : (
                                <span className="inline-block px-1 py-0.2 bg-emerald-100 text-emerald-800 text-[9px] font-semibold rounded">
                                  STAFFED
                                </span>
                              )}
                            </div>
                          ) : (
                            <span className="text-slate-300 text-[10px]">-</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))
      )}
    </div>
  );
};
