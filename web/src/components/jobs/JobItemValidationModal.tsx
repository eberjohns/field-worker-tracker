import React, { useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { X, CheckCircle2, AlertTriangle, Users, Clock, Calendar, Split, ShieldCheck } from "lucide-react";

interface ValidationData {
  job_item_id: string;
  sub_item_code: string;
  staff_grade_description: string;
  planned_grade_code: string | null;
  frequency_unit: string;
  occurrences_per_period: number;
  period_interval: number;
  required_staff_count: number;
  hours_per_occurrence_per_staff: number;
  expected_activities_per_year: number;
  expected_annual_hours: number;
  days_per_occurrence: number;
  daily_hours_split: number[];
  eligible_workers_count: number;
  is_valid: boolean;
  warnings: string[];
}

interface JobItemValidationModalProps {
  isOpen: boolean;
  onClose: () => void;
  jobItemId: string | null;
  worksiteJobNumber: string;
}

export const JobItemValidationModal: React.FC<JobItemValidationModalProps> = ({
  isOpen,
  onClose,
  jobItemId,
  worksiteJobNumber,
}) => {
  const { token } = useAuth();
  const [data, setData] = useState<ValidationData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string>("");

  useEffect(() => {
    if (!isOpen || !jobItemId) {
      setData(null);
      return;
    }

    const fetchValidation = async () => {
      setLoading(true);
      setErrorMsg("");
      try {
        const res = await fetch(`/api/v1/job-items/${jobItemId}/validation`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        if (!res.ok) {
          throw new Error("Failed to load validation calculations.");
        }
        const valData = await res.json();
        setData(valData);
      } catch (err: any) {
        setErrorMsg(err.message || "An error occurred.");
      } finally {
        setLoading(false);
      }
    };

    fetchValidation();
  }, [isOpen, jobItemId, token]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-xl bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div>
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-indigo-600" />
              Job Item Validation & Feasibility Panel
            </h2>
            <p className="text-xs text-slate-500">
              Worksite {worksiteJobNumber} &bull; Sub-Item {data?.sub_item_code || "..."}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200/60"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-5 overflow-y-auto flex-1 text-xs">
          {loading ? (
            <div className="py-12 text-center text-slate-400">Loading calculations...</div>
          ) : errorMsg ? (
            <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700">
              {errorMsg}
            </div>
          ) : data ? (
            <>
              {/* Status Banner */}
              <div
                className={`p-3.5 rounded-lg border flex items-start gap-3 ${
                  data.is_valid && data.warnings.length === 0
                    ? "bg-emerald-50 border-emerald-200 text-emerald-900"
                    : "bg-amber-50 border-amber-200 text-amber-900"
                }`}
              >
                {data.is_valid && data.warnings.length === 0 ? (
                  <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
                ) : (
                  <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
                )}
                <div>
                  <span className="font-semibold block text-sm">
                    {data.is_valid && data.warnings.length === 0
                      ? "Configuration Verified & Feasible"
                      : "Feasibility Notice"}
                  </span>
                  <p className="mt-0.5 text-xs">
                    {data.warnings.length > 0
                      ? data.warnings.join(". ")
                      : "Staff requirements and shifts are fully compatible with current workforce and regulations."}
                  </p>
                </div>
              </div>

              {/* Metric Cards */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                  <div className="flex items-center gap-1.5 text-slate-500 mb-1">
                    <Calendar className="h-3.5 w-3.5 text-indigo-500" />
                    <span className="font-medium">Expected Annual Activities</span>
                  </div>
                  <span className="text-xl font-bold text-slate-900">
                    {data.expected_activities_per_year.toLocaleString()}
                  </span>
                  <p className="text-[11px] text-slate-500 mt-1">
                    {data.occurrences_per_period}x per {data.period_interval}{" "}
                    {data.frequency_unit.toLowerCase()}
                  </p>
                </div>

                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                  <div className="flex items-center gap-1.5 text-slate-500 mb-1">
                    <Clock className="h-3.5 w-3.5 text-indigo-500" />
                    <span className="font-medium">Expected Annual Hours</span>
                  </div>
                  <span className="text-xl font-bold text-indigo-600">
                    {data.expected_annual_hours.toLocaleString(undefined, {
                      maximumFractionDigits: 1,
                    })}{" "}
                    h
                  </span>
                  <p className="text-[11px] text-slate-500 mt-1">
                    {data.required_staff_count} worker(s) &times;{" "}
                    {data.hours_per_occurrence_per_staff}h/occ
                  </p>
                </div>
              </div>

              {/* 9-Hour Shift Chunking */}
              <div className="border border-slate-200 rounded-lg p-4 space-y-2 bg-white">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-800 flex items-center gap-1.5">
                    <Split className="h-4 w-4 text-indigo-600" />
                    Shift Split Calculation (9.0h Shift Max)
                  </span>
                  <span className="px-2 py-0.5 rounded bg-indigo-100 text-indigo-800 font-semibold text-[11px]">
                    {data.days_per_occurrence} Day{data.days_per_occurrence > 1 ? "s" : ""}
                  </span>
                </div>
                <p className="text-slate-500 text-[11px]">
                  Daily hours are capped at 9.0h per UAE labor law. Longer scopes are spread across
                  consecutive work days.
                </p>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2">
                  {data.daily_hours_split.map((chunk, idx) => (
                    <div
                      key={idx}
                      className="border border-slate-200 rounded p-2 text-center bg-slate-50"
                    >
                      <span className="block text-[10px] uppercase font-bold text-slate-500">
                        Day {idx + 1}
                      </span>
                      <span className="text-sm font-bold text-slate-800">
                        {chunk.toFixed(chunk % 1 === 0 ? 0 : 3)}h
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Workforce Availability */}
              <div className="border border-slate-200 rounded-lg p-4 bg-white flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600">
                    <Users className="h-5 w-5" />
                  </div>
                  <div>
                    <span className="font-bold text-slate-800 block text-xs">
                      Matching Active Workforce
                    </span>
                    <span className="text-slate-500 text-[11px]">
                      Designated for {data.staff_grade_description}
                      {data.planned_grade_code ? ` (${data.planned_grade_code})` : ""}
                    </span>
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-xl font-bold text-slate-900">
                    {data.eligible_workers_count}
                  </span>
                  <span className="text-slate-500 block text-[10px]">
                    {data.eligible_workers_count >= data.required_staff_count
                      ? "Adequate headcount"
                      : "Staff shortage"}
                  </span>
                </div>
              </div>
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-xs font-medium"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
