import React, { useState, useEffect } from "react";
import {
  X,
  AlertTriangle,
  ArrowUp,
  ArrowDown,
  GripVertical,
  Layers,
} from "lucide-react";
import { CandidateRecommendation, ValidationReport } from "./types";

interface JobItemOption {
  id: string;
  worksite_id: string;
  job_number: string;
  job_name: string;
  sub_item_code: string;
  staff_grade_description: string;
  planned_grade_code: string;
  deployment_type: string;
  hours_per_occurrence: number;
  weekday_pattern?: string[] | null;
}

interface ExistingVisitItem {
  id: string;
  job_number: string;
  sub_item_code: string;
  assigned_hours: number;
  sequence: number;
}

interface AssignModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  token: string | null;
  initialWorkerId?: string | null;
  initialDate?: string | null;
  initialJobItemId?: string | null;
  availableJobItems: JobItemOption[];
  candidates: CandidateRecommendation[];
  existingVisitsForDate?: ExistingVisitItem[];
}

export const AssignModal: React.FC<AssignModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  token,
  initialWorkerId,
  initialDate,
  initialJobItemId,
  availableJobItems,
  candidates,
  existingVisitsForDate = [],
}) => {
  const [assignmentMode, setAssignmentMode] = useState<"SINGLE" | "RANGE" | "STANDING">("SINGLE");
  const [selectedWorkerId, setSelectedWorkerId] = useState<string>(initialWorkerId || "");
  const [selectedJobItemId, setSelectedJobItemId] = useState<string>(initialJobItemId || "");
  const [targetDate, setTargetDate] = useState<string>(
    initialDate || new Date().toISOString().split("T")[0]
  );
  const [endDate, setEndDate] = useState<string>("");
  const [assignedHours, setAssignedHours] = useState<number>(8.0);
  const [selectedWeekdays, setSelectedWeekdays] = useState<string[]>([
    "MON",
    "TUE",
    "WED",
    "THU",
    "FRI",
    "SAT",
  ]);

  // Reordering state for visits on targetDate
  const [visitList, setVisitList] = useState<ExistingVisitItem[]>(existingVisitsForDate);
  const [validationReport, setValidationReport] = useState<ValidationReport | null>(null);
  const [acknowledgeWarnings, setAcknowledgeWarnings] = useState(false);
  const [loading, setLoading] = useState(false);
  const [validating, setValidating] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    if (initialWorkerId) setSelectedWorkerId(initialWorkerId);
    if (initialJobItemId) setSelectedJobItemId(initialJobItemId);
    if (initialDate) setTargetDate(initialDate);
    if (existingVisitsForDate && existingVisitsForDate.length > 0) {
      setVisitList(existingVisitsForDate);
    } else {
      setVisitList([]);
    }
  }, [isOpen, initialWorkerId, initialJobItemId, initialDate]);

  // Pre-fill hours from selected job item
  useEffect(() => {
    if (!isOpen || !selectedJobItemId) return;
    const item = availableJobItems.find((j) => j.id === selectedJobItemId);
    if (item) {
      setAssignedHours(item.hours_per_occurrence);
      if (item.weekday_pattern && item.weekday_pattern.length > 0) {
        setSelectedWeekdays(item.weekday_pattern);
      }
    }
  }, [isOpen, selectedJobItemId]);

  // Run dry-run validation on change
  useEffect(() => {
    if (!selectedWorkerId || !selectedJobItemId || !targetDate || assignmentMode !== "SINGLE") {
      setValidationReport(null);
      return;
    }

    const runValidation = async () => {
      setValidating(true);
      setErrorMsg(null);
      try {
        const res = await fetch("/api/v1/scheduled-work/validate", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            employee_id: selectedWorkerId,
            job_item_id: selectedJobItemId,
            work_date: targetDate,
            assigned_hours: assignedHours,
          }),
        });
        if (res.ok) {
          const data: ValidationReport = await res.json();
          setValidationReport(data);
        }
      } catch (err) {
        console.error("Validation error:", err);
      } finally {
        setValidating(false);
      }
    };

    const timer = setTimeout(runValidation, 300);
    return () => clearTimeout(timer);
  }, [selectedWorkerId, selectedJobItemId, targetDate, assignedHours, assignmentMode, token]);

  if (!isOpen) return null;

  // Move visit up/down
  const moveVisit = (index: number, direction: "up" | "down") => {
    const newIdx = direction === "up" ? index - 1 : index + 1;
    if (newIdx < 0 || newIdx >= visitList.length) return;
    const updated = [...visitList];
    const [moved] = updated.splice(index, 1);
    updated.splice(newIdx, 0, moved);
    setVisitList(updated);
  };

  // Submit assignment
  const handleAssignSubmit = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      if (assignmentMode === "STANDING") {
        const res = await fetch("/api/v1/standing-assignments", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            employee_id: selectedWorkerId,
            job_item_id: selectedJobItemId,
            start_date: targetDate,
            end_date: endDate || null,
            weekday_pattern: selectedWeekdays,
            hours_per_day: assignedHours,
          }),
        });
        if (!res.ok) {
          const errData = await res.json();
          throw new Error(errData.detail || "Failed to create standing assignment.");
        }
      } else {
        // Single or Range
        const datesToAssign: string[] = [targetDate];
        if (assignmentMode === "RANGE" && endDate) {
          const cur = new Date(targetDate);
          const end = new Date(endDate);
          while (cur < end) {
            cur.setDate(cur.getDate() + 1);
            datesToAssign.push(cur.toISOString().split("T")[0]);
          }
        }

        for (const d of datesToAssign) {
          const res = await fetch("/api/v1/scheduled-work", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            body: JSON.stringify({
              employee_id: selectedWorkerId,
              job_item_id: selectedJobItemId,
              work_date: d,
              assigned_hours: assignedHours,
              acknowledge_warnings: acknowledgeWarnings,
            }),
          });
          if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || `Failed to assign work for ${d}.`);
          }
        }
      }

      onSuccess();
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  };

  const weekdaysList = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center space-x-2">
            <div className="h-8 w-8 rounded-lg bg-blue-600 text-white flex items-center justify-center font-bold text-sm">
              <Layers className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">Assign Field Work</h2>
              <p className="text-xs text-slate-500">
                Create scheduled work, date range, or year plan standing team
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200 transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body Form */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {errorMsg && (
            <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-xl text-xs flex items-center space-x-2">
              <AlertTriangle className="h-4 w-4 shrink-0 text-red-600" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Mode Tabs */}
          <div className="flex bg-slate-100 p-1 rounded-xl">
            {(["SINGLE", "RANGE", "STANDING"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setAssignmentMode(mode)}
                className={`flex-1 py-1.5 text-xs font-semibold rounded-lg transition ${
                  assignmentMode === mode
                    ? "bg-white text-blue-700 shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {mode === "SINGLE"
                  ? "Single Day"
                  : mode === "RANGE"
                  ? "Date Range"
                  : "Standing Team (Year Plan)"}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Worker Selection */}
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Worker</label>
              <select
                value={selectedWorkerId}
                onChange={(e) => setSelectedWorkerId(e.target.value)}
                className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg p-2.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="">-- Choose Worker --</option>
                {candidates.map((c) => (
                  <option key={c.employee_id} value={c.employee_id}>
                    {c.name} ({c.tally_id} - {c.grade_code || "No Grade"} - {c.staff_grade_description})
                  </option>
                ))}
              </select>
            </div>

            {/* Job Item Selection */}
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Worksite & Job Item
              </label>
              <select
                value={selectedJobItemId}
                onChange={(e) => setSelectedJobItemId(e.target.value)}
                className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg p-2.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="">-- Choose Job Item --</option>
                {availableJobItems.map((j) => (
                  <option key={j.id} value={j.id}>
                    {j.job_number} Item {j.sub_item_code}: {j.staff_grade_description} (
                    {j.deployment_type}, {j.hours_per_occurrence}h)
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Dates & Hours */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                {assignmentMode === "STANDING" ? "Start Date" : "Work Date"}
              </label>
              <input
                type="date"
                value={targetDate}
                onChange={(e) => setTargetDate(e.target.value)}
                className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg p-2.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {(assignmentMode === "RANGE" || assignmentMode === "STANDING") && (
              <div>
                <label className="block text-xs font-bold text-slate-700 mb-1">End Date</label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  placeholder="Optional end date"
                  className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg p-2.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">Hours / Day</label>
              <input
                type="number"
                step="0.5"
                min="0.5"
                max="24.0"
                value={assignedHours}
                onChange={(e) => setAssignedHours(parseFloat(e.target.value) || 0)}
                className="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg p-2.5 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Weekday Pattern (for Standing Assignment) */}
          {assignmentMode === "STANDING" && (
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1.5">
                Weekday Pattern (Recurring Working Days)
              </label>
              <div className="flex flex-wrap gap-2">
                {weekdaysList.map((day) => {
                  const isChecked = selectedWeekdays.includes(day);
                  return (
                    <button
                      key={day}
                      type="button"
                      onClick={() => {
                        setSelectedWeekdays((prev) =>
                          isChecked ? prev.filter((d) => d !== day) : [...prev, day]
                        );
                      }}
                      className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition ${
                        isChecked
                          ? "bg-blue-600 text-white border-blue-600"
                          : "bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100"
                      }`}
                    >
                      {day}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Reordering existing visits for the same date (both drag & drop and up/down buttons) */}
          {visitList.length > 1 && (
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
              <div className="flex items-center justify-between text-xs font-bold text-slate-700">
                <span>Daily Visit Sequence on {targetDate}</span>
                <span className="text-[10px] text-slate-400 font-normal">
                  Use buttons or drag to order visits
                </span>
              </div>
              <div className="space-y-1">
                {visitList.map((visit, index) => (
                  <div
                    key={visit.id}
                    className="flex items-center justify-between p-2 bg-white rounded-lg border border-slate-200 text-xs shadow-2xs"
                  >
                    <div className="flex items-center space-x-2">
                      <GripVertical className="h-4 w-4 text-slate-300 cursor-grab" />
                      <span className="font-bold text-blue-700 w-5">#{index + 1}</span>
                      <span className="font-semibold text-slate-800">
                        {visit.job_number} Item {visit.sub_item_code}
                      </span>
                      <span className="text-slate-500">({visit.assigned_hours}h)</span>
                    </div>
                    <div className="flex items-center space-x-1">
                      <button
                        type="button"
                        disabled={index === 0}
                        onClick={() => moveVisit(index, "up")}
                        className="p-1 text-slate-400 hover:text-slate-700 disabled:opacity-20 rounded"
                        title="Move Up"
                      >
                        <ArrowUp className="h-3.5 w-3.5" />
                      </button>
                      <button
                        type="button"
                        disabled={index === visitList.length - 1}
                        onClick={() => moveVisit(index, "down")}
                        className="p-1 text-slate-400 hover:text-slate-700 disabled:opacity-20 rounded"
                        title="Move Down"
                      >
                        <ArrowDown className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Dry-run Validation Feedback */}
          {validationReport && (
            <div className="space-y-2 pt-2 border-t border-slate-100">
              {validationReport.errors.length > 0 && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-xl space-y-1">
                  <div className="font-bold text-red-800 text-xs flex items-center space-x-1.5">
                    <AlertTriangle className="h-4 w-4 text-red-600" />
                    <span>Blocking Validation Errors</span>
                  </div>
                  <ul className="list-disc list-inside text-xs text-red-700 space-y-0.5 pl-1">
                    {validationReport.errors.map((e, idx) => (
                      <li key={idx}>{e.message}</li>
                    ))}
                  </ul>
                </div>
              )}

              {validationReport.warnings.length > 0 && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl space-y-2">
                  <div className="font-bold text-amber-800 text-xs flex items-center space-x-1.5">
                    <AlertTriangle className="h-4 w-4 text-amber-600" />
                    <span>Planning Warnings (Needs Confirmation)</span>
                  </div>
                  <ul className="list-disc list-inside text-xs text-amber-700 space-y-0.5 pl-1">
                    {validationReport.warnings.map((w, idx) => (
                      <li key={idx}>{w.message}</li>
                    ))}
                  </ul>
                  <label className="flex items-center space-x-2 pt-1 text-xs text-amber-900 font-semibold cursor-pointer">
                    <input
                      type="checkbox"
                      checked={acknowledgeWarnings}
                      onChange={(e) => setAcknowledgeWarnings(e.target.checked)}
                      className="rounded text-amber-600 focus:ring-amber-500 h-4 w-4"
                    />
                    <span>I acknowledge these warnings and confirm this assignment</span>
                  </label>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-200 rounded-lg transition"
          >
            Cancel
          </button>
          <div className="flex items-center space-x-2">
            {validating && (
              <span className="text-[11px] text-slate-400">Checking conflicts...</span>
            )}
            <button
              type="button"
              disabled={Boolean(
                loading ||
                !selectedWorkerId ||
                !selectedJobItemId ||
                (validationReport && !validationReport.is_valid) ||
                (validationReport && validationReport.warnings.length > 0 && !acknowledgeWarnings)
              )}
              onClick={handleAssignSubmit}
              className="px-5 py-2 text-xs font-bold bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-40 transition shadow-sm"
            >
              {loading ? "Assigning..." : "Confirm Assignment"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
