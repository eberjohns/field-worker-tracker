import React, { useState } from "react";
import { StandingAssignmentRead } from "./types";
import { Calendar, Clock, Plus, CalendarOff } from "lucide-react";

interface YearPlanViewProps {
  standingAssignments: StandingAssignmentRead[];
  onOpenAssignModal: () => void;
  onEndAssignment: (id: string, version: number) => void;
}

export const YearPlanView: React.FC<YearPlanViewProps> = ({
  standingAssignments,
  onOpenAssignModal,
  onEndAssignment,
}) => {
  const [selectedAssignmentToEnd, setSelectedAssignmentToEnd] = useState<StandingAssignmentRead | null>(
    null
  );
  const [endDateInput, setEndDateInput] = useState<string>(
    new Date().toISOString().split("T")[0]
  );

  return (
    <div className="flex-1 flex flex-col bg-white overflow-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-slate-900">Year Plan (Standing Assignments)</h2>
          <p className="text-xs text-slate-500">
            Long-term recurring team allocations. Daily work is generated automatically for a 13-month rolling horizon.
          </p>
        </div>
        <button
          onClick={onOpenAssignModal}
          className="inline-flex items-center space-x-1.5 px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold shadow-sm transition"
        >
          <Plus className="h-4 w-4" />
          <span>Add Standing Team</span>
        </button>
      </div>

      {standingAssignments.length === 0 ? (
        <div className="p-12 text-center text-slate-400 text-xs bg-slate-50 rounded-xl border border-slate-200">
          No active standing assignments found. Click "Add Standing Team" to assign workers.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {standingAssignments.map((assignment) => (
            <div
              key={assignment.id}
              className="p-4 rounded-xl border border-slate-200 bg-white hover:border-blue-300 transition shadow-2xs space-y-3"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-bold text-sm text-slate-900">
                    {assignment.job_number} Item {assignment.sub_item_code}
                  </div>
                  <div className="text-xs text-slate-500 font-medium">
                    Worker:{" "}
                    <span className="font-semibold text-slate-800">
                      {assignment.employee_name || "Unknown"}
                    </span>
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                  ACTIVE
                </span>
              </div>

              <div className="space-y-1.5 text-xs text-slate-600 border-t border-slate-100 pt-2">
                <div className="flex items-center space-x-2">
                  <Calendar className="h-3.5 w-3.5 text-slate-400" />
                  <span>
                    {assignment.start_date} → {assignment.end_date || "Continuous"}
                  </span>
                </div>
                <div className="flex items-center space-x-2">
                  <Clock className="h-3.5 w-3.5 text-slate-400" />
                  <span>{assignment.hours_per_day || 8.0} hours / working day</span>
                </div>
                {assignment.weekday_pattern && (
                  <div className="flex flex-wrap gap-1 pt-1">
                    {assignment.weekday_pattern.map((day) => (
                      <span
                        key={day}
                        className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 text-[10px] font-mono font-semibold"
                      >
                        {day}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="pt-2 border-t border-slate-100 flex justify-end">
                <button
                  type="button"
                  onClick={() => setSelectedAssignmentToEnd(assignment)}
                  className="inline-flex items-center space-x-1 text-xs text-red-600 hover:text-red-800 font-semibold transition"
                >
                  <CalendarOff className="h-3.5 w-3.5" />
                  <span>End Assignment...</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* End Assignment Modal */}
      {selectedAssignmentToEnd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 w-full max-w-md p-6 space-y-4">
            <h3 className="text-base font-bold text-slate-900">End Standing Assignment</h3>
            <p className="text-xs text-slate-500">
              Ending this standing assignment will permanently end this worker's recurring assignment from the specified date forward and cancel unstarted scheduled work beyond that date.
            </p>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Effective End Date</label>
              <input
                type="date"
                value={endDateInput}
                onChange={(e) => setEndDateInput(e.target.value)}
                className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg p-2.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setSelectedAssignmentToEnd(null)}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  onEndAssignment(selectedAssignmentToEnd.id, selectedAssignmentToEnd.version);
                  setSelectedAssignmentToEnd(null);
                }}
                className="px-4 py-2 text-xs font-bold bg-red-600 text-white rounded-lg hover:bg-red-700"
              >
                Confirm End Assignment
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
