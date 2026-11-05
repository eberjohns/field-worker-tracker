import React from "react";
import { RosterResponse, RosterWorkerRow, RosterDayCell } from "./types";
import {
  AlertCircle,
  Download,
  Plus,
} from "lucide-react";

interface RosterViewProps {
  roster: RosterResponse;
  compactMode: boolean;
  onCellClick: (worker: RosterWorkerRow, day: RosterDayCell) => void;
  onWorkerSelect: (worker: RosterWorkerRow) => void;
  selectedWorkerId?: string | null;
  onExportExcel: () => void;
  exportingExcel: boolean;
}

export const RosterView: React.FC<RosterViewProps> = ({
  roster,
  compactMode,
  onCellClick,
  onWorkerSelect,
  selectedWorkerId,
  onExportExcel,
  exportingExcel,
}) => {
  const daysHeader = [
    { label: "Mon", dateKey: 0 },
    { label: "Tue", dateKey: 1 },
    { label: "Wed", dateKey: 2 },
    { label: "Thu", dateKey: 3 },
    { label: "Fri", dateKey: 4 },
    { label: "Sat", dateKey: 5 },
    { label: "Sun", dateKey: 6 },
  ];

  return (
    <div className="flex-1 flex flex-col bg-white overflow-hidden">
      {/* Top action row */}
      <div className="px-6 py-3 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
        <div className="text-xs text-slate-500 font-medium">
          Showing <span className="font-bold text-slate-800">{roster.total_workers}</span> workers
          for week <span className="font-semibold text-slate-700">{roster.week_start}</span> to{" "}
          <span className="font-semibold text-slate-700">{roster.week_end}</span>
        </div>
        <button
          onClick={onExportExcel}
          disabled={exportingExcel}
          className="inline-flex items-center space-x-1.5 px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-50 rounded-lg text-xs font-semibold text-slate-700 shadow-2xs transition disabled:opacity-50"
        >
          <Download className="h-3.5 w-3.5 text-slate-500" />
          <span>{exportingExcel ? "Generating Excel..." : "Export to Excel"}</span>
        </button>
      </div>

      {/* Roster Matrix Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full border-collapse text-left text-xs min-w-[1000px]">
          <thead className="sticky top-0 z-10 bg-slate-100 border-b border-slate-200 text-slate-700 font-bold uppercase text-[10px] tracking-wider">
            <tr>
              <th className="p-3 w-56 sticky left-0 bg-slate-100 border-r border-slate-200 shadow-2xs">
                Worker (Grade, Std H)
              </th>
              {daysHeader.map((d, idx) => {
                const dayDate = roster.workers[0]?.days[idx]?.work_date;
                return (
                  <th key={d.label} className="p-2.5 border-r border-slate-200 text-center w-36">
                    <div>{d.label}</div>
                    {dayDate && (
                      <div className="text-[9px] font-normal text-slate-500">
                        {dayDate.split("-").slice(1).join("/")}
                      </div>
                    )}
                  </th>
                );
              })}
              <th className="p-2.5 w-24 text-center border-r border-slate-200">Total Hours</th>
              <th className="p-2.5 w-44">Remarks</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {roster.workers.length === 0 ? (
              <tr>
                <td colSpan={10} className="p-12 text-center text-slate-400">
                  No workers match the selected criteria or filters.
                </td>
              </tr>
            ) : (
              roster.workers.map((worker) => {
                const isSelected = selectedWorkerId === worker.employee_id;
                return (
                  <tr
                    key={worker.employee_id}
                    className={`hover:bg-slate-50/80 transition ${
                      isSelected ? "bg-blue-50/50" : ""
                    }`}
                  >
                    {/* Fixed Worker Info Column */}
                    <td
                      onClick={() => onWorkerSelect(worker)}
                      className="p-3 sticky left-0 bg-white hover:bg-slate-50 border-r border-slate-200 cursor-pointer shadow-2xs"
                    >
                      <div className="font-semibold text-slate-900 truncate">{worker.name}</div>
                      <div className="text-[11px] text-slate-500 flex items-center space-x-1.5 mt-0.5">
                        <span className="font-mono text-slate-600">{worker.tally_id}</span>
                        <span>•</span>
                        <span className="font-bold text-blue-700">
                          {worker.grade_code || "N/A"}
                        </span>
                        <span>•</span>
                        <span className="font-semibold text-slate-600">
                          {worker.standard_hours}h
                        </span>
                      </div>
                      {worker.staff_grade_description && (
                        <div className="text-[10px] text-slate-400 truncate max-w-[200px]">
                          {worker.staff_grade_description}
                        </div>
                      )}
                    </td>

                    {/* 7 Days Cells */}
                    {worker.days.map((day) => {
                      const hasChips = day.chips.length > 0;
                      return (
                        <td
                          key={day.work_date}
                          onClick={() => onCellClick(worker, day)}
                          className="p-1.5 border-r border-slate-200 align-top cursor-pointer hover:bg-blue-50/40 transition relative group"
                        >
                          {hasChips ? (
                            <div className="space-y-1">
                              {compactMode ? (
                                <div className="p-1 rounded bg-blue-50 border border-blue-200 text-blue-900 text-[11px] font-semibold flex items-center justify-between">
                                  <span className="truncate">
                                    {day.chips.map((c) => `${c.job_number} ${c.sub_item_code}`).join(" + ")}
                                  </span>
                                  <span className="ml-1 text-[10px] font-bold text-blue-700">
                                    {day.day_total_hours}h
                                  </span>
                                </div>
                              ) : (
                                day.chips.map((chip) => (
                                  <div
                                    key={chip.scheduled_work_id}
                                    className="p-1 rounded bg-slate-100 hover:bg-blue-100 border border-slate-200 text-slate-800 text-[10px] flex items-center justify-between"
                                  >
                                    <div className="truncate font-semibold max-w-[85px]">
                                      {chip.job_number} {chip.sub_item_code}
                                    </div>
                                    <span className="font-bold text-slate-700">
                                      {chip.assigned_hours}h
                                    </span>
                                  </div>
                                ))
                              )}

                              {/* Day total under chips */}
                              <div className="flex items-center justify-between text-[10px] px-1 pt-0.5">
                                <span className="text-slate-400">Total:</span>
                                <span
                                  className={`font-bold ${
                                    day.is_over_standard
                                      ? "text-red-600"
                                      : day.is_under_standard
                                      ? "text-amber-600"
                                      : "text-slate-700"
                                  }`}
                                >
                                  {day.day_total_hours}h
                                </span>
                              </div>
                            </div>
                          ) : (
                            /* Explainable Day Marker */
                            <div className="h-full min-h-[48px] flex items-center justify-center p-1">
                              {day.marker === "SKIPPED" && (
                                <span className="px-2 py-1 rounded bg-amber-50 text-amber-800 font-bold text-[10px] border border-amber-200">
                                  SKIPPED (Holiday)
                                </span>
                              )}
                              {day.marker === "WEEKLY_OFF" && (
                                <span className="px-2 py-1 rounded bg-slate-100 text-slate-600 font-semibold text-[10px] border border-slate-200">
                                  WEEKLY-OFF
                                </span>
                              )}
                              {day.marker === "ON_LEAVE" && (
                                <span className="px-2 py-1 rounded bg-purple-50 text-purple-700 font-bold text-[10px] border border-purple-200">
                                  ON LEAVE
                                </span>
                              )}
                              {day.marker === "TO_BE_COVERED" && (
                                <span className="px-2 py-1 rounded bg-red-50 text-red-700 font-bold text-[10px] border border-red-200 flex items-center space-x-1">
                                  <AlertCircle className="h-3 w-3" />
                                  <span>COVER NEEDED</span>
                                </span>
                              )}
                              {day.marker === "FREE" && (
                                <span className="text-slate-300 text-[10px] font-medium group-hover:text-blue-500 flex items-center space-x-0.5">
                                  <Plus className="h-3 w-3 opacity-0 group-hover:opacity-100 transition" />
                                  <span>FREE</span>
                                </span>
                              )}
                            </div>
                          )}
                        </td>
                      );
                    })}

                    {/* Total Hours Column */}
                    <td className="p-2.5 border-r border-slate-200 text-center font-bold">
                      <div
                        className={`text-xs ${
                          worker.week_is_over
                            ? "text-red-600"
                            : worker.week_is_under
                            ? "text-amber-600"
                            : "text-slate-800"
                        }`}
                      >
                        {Number(worker.week_allocated_hours || 0).toFixed(1)} /{" "}
                        {Number(worker.week_standard_hours || 0).toFixed(1)}
                      </div>
                      <div className="text-[10px] font-normal text-slate-400">
                        {worker.week_is_over
                          ? `+${(
                              Number(worker.week_allocated_hours || 0) -
                              Number(worker.week_standard_hours || 0)
                            ).toFixed(1)}h OT`
                          : worker.week_is_under
                          ? `${(
                              Number(worker.week_standard_hours || 0) -
                              Number(worker.week_allocated_hours || 0)
                            ).toFixed(1)}h free`
                          : "standard"}
                      </div>
                    </td>

                    {/* Remarks Column */}
                    <td className="p-2.5 text-slate-600 text-[11px] truncate max-w-[180px]">
                      {worker.remarks || "-"}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
