import React, { useState, useEffect } from "react";
import { useAuth } from "../../context/AuthContext";
import { X, Calculator, AlertCircle, Info } from "lucide-react";

interface JobItem {
  id: string;
  worksite_id: string;
  sub_item_code: string;
  staff_grade_description: string;
  planned_grade_code: string | null;
  frequency_unit: "WEEK" | "MONTH" | "QUARTER" | "YEAR";
  occurrences_per_period: number;
  period_interval: number;
  weekday_pattern: number[] | null;
  required_staff_count: number;
  hours_per_occurrence_per_staff: number | string;
  deployment_type: "PERMANENT" | "REMOTE";
  break_override_minutes: number | null;
  is_active: boolean;
  version: number;
}

interface JobItemModalProps {
  isOpen: boolean;
  onClose: () => void;
  worksiteId: string;
  initialData?: JobItem | null;
  onSuccess: () => void;
}

const COMMON_SGDS = [
  "GARDENER",
  "TEAM LEADER",
  "DRIVER",
  "IRRIGATION TECHNICIAN",
  "FOREMAN",
  "SUPERVISOR",
  "CLEANER",
  "LANDSCAPE WORKER",
  "ARBORIST",
  "OPERATOR",
];

const WEEKDAYS = [
  { day: 0, label: "Mon" },
  { day: 1, label: "Tue" },
  { day: 2, label: "Wed" },
  { day: 3, label: "Thu" },
  { day: 4, label: "Fri" },
  { day: 5, label: "Sat" },
  { day: 6, label: "Sun" },
];

export const JobItemModal: React.FC<JobItemModalProps> = ({
  isOpen,
  onClose,
  worksiteId,
  initialData,
  onSuccess,
}) => {
  const { token } = useAuth();
  const [subItemCode, setSubItemCode] = useState("");
  const [sgd, setSgd] = useState("GARDENER");
  const [plannedGrade, setPlannedGrade] = useState("");
  const [frequencyUnit, setFrequencyUnit] = useState<"WEEK" | "MONTH" | "QUARTER" | "YEAR">("WEEK");
  const [occurrencesPerPeriod, setOccurrencesPerPeriod] = useState<number>(6);
  const [periodInterval, setPeriodInterval] = useState<number>(1);
  const [selectedWeekdays, setSelectedWeekdays] = useState<number[]>([0, 1, 2, 3, 4, 5]); // Mon-Sat
  const [requiredStaff, setRequiredStaff] = useState<number>(1);
  const [hoursPerOccurrence, setHoursPerOccurrence] = useState<number | string>(9.0);
  const [deploymentType, setDeploymentType] = useState<"PERMANENT" | "REMOTE">("PERMANENT");
  const [breakOverride, setBreakOverride] = useState<number | "">("");

  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (initialData) {
      setSubItemCode(initialData.sub_item_code);
      setSgd(initialData.staff_grade_description);
      setPlannedGrade(initialData.planned_grade_code || "");
      setFrequencyUnit(initialData.frequency_unit);
      setOccurrencesPerPeriod(initialData.occurrences_per_period);
      setPeriodInterval(initialData.period_interval);
      setSelectedWeekdays(initialData.weekday_pattern || []);
      setRequiredStaff(initialData.required_staff_count);
      setHoursPerOccurrence(initialData.hours_per_occurrence_per_staff);
      setDeploymentType(initialData.deployment_type);
      setBreakOverride(initialData.break_override_minutes ?? "");
    } else {
      setSubItemCode("");
      setSgd("GARDENER");
      setPlannedGrade("");
      setFrequencyUnit("WEEK");
      setOccurrencesPerPeriod(6);
      setPeriodInterval(1);
      setSelectedWeekdays([0, 1, 2, 3, 4, 5]);
      setRequiredStaff(1);
      setHoursPerOccurrence(9.0);
      setDeploymentType("PERMANENT");
      setBreakOverride("");
    }
    setErrorMsg("");
  }, [initialData, isOpen]);

  if (!isOpen) return null;

  // Real-time calculations
  const parsedHours = parseFloat(String(hoursPerOccurrence)) || 0;
  const staffCount = requiredStaff || 1;
  let multiplier = 52;
  if (frequencyUnit === "MONTH") multiplier = 12;
  else if (frequencyUnit === "QUARTER") multiplier = 4;
  else if (frequencyUnit === "YEAR") multiplier = 1;

  const interval = periodInterval > 0 ? periodInterval : 1;
  const calculatedActivities = occurrencesPerPeriod * (multiplier / interval);
  const calculatedAnnualHours = calculatedActivities * parsedHours * staffCount;

  // Day split
  const daysPerOccurrence = parsedHours > 0 ? Math.ceil(parsedHours / 9.0) : 1;
  const isMultiDay = parsedHours > 9.0;

  const toggleWeekday = (day: number) => {
    if (selectedWeekdays.includes(day)) {
      setSelectedWeekdays(selectedWeekdays.filter((d) => d !== day));
    } else {
      setSelectedWeekdays([...selectedWeekdays, day].sort());
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");

    if (!subItemCode.trim()) {
      setErrorMsg("Sub-item code is required.");
      return;
    }
    if (!sgd.trim()) {
      setErrorMsg("Staff grade description is required.");
      return;
    }
    if (parsedHours <= 0) {
      setErrorMsg("Hours per occurrence must be greater than 0.");
      return;
    }

    setLoading(true);
    try {
      const payload: Record<string, any> = {
        sub_item_code: subItemCode.trim(),
        staff_grade_description: sgd.trim(),
        planned_grade_code: plannedGrade.trim() || null,
        frequency_unit: frequencyUnit,
        occurrences_per_period: occurrencesPerPeriod,
        period_interval: interval,
        weekday_pattern: selectedWeekdays.length > 0 ? selectedWeekdays : null,
        required_staff_count: staffCount,
        hours_per_occurrence_per_staff: parsedHours,
        deployment_type: deploymentType,
        break_override_minutes: breakOverride === "" ? null : Number(breakOverride),
      };

      const url = initialData
        ? `/api/v1/job-items/${initialData.id}`
        : `/api/v1/worksites/${worksiteId}/job-items`;
      const method = initialData ? "PATCH" : "POST";

      if (initialData) {
        payload.version = initialData.version;
      }

      const res = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to save job item.");
      }

      onSuccess();
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || "An error occurred.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-2xl bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden max-h-[90vh] flex flex-col">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div>
            <h2 className="text-lg font-bold text-slate-900">
              {initialData ? "Edit Job Item" : "Add Job Item"}
            </h2>
            <p className="text-xs text-slate-500">
              Define frequency, required staffing, and hours. Occurrences are automatically generated.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200/60"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Modal Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5 overflow-y-auto flex-1">
          {errorMsg && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-xs text-red-700">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Row 1: Sub-Item Code & SGD */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Sub-Item Code *
              </label>
              <input
                type="text"
                required
                value={subItemCode}
                onChange={(e) => setSubItemCode(e.target.value)}
                placeholder="e.g. 01, A1, M01"
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Staff Grade Description (SGD) *
              </label>
              <input
                type="text"
                list="sgd-options"
                required
                value={sgd}
                onChange={(e) => setSgd(e.target.value)}
                placeholder="Select or enter SGD"
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
              />
              <datalist id="sgd-options">
                {COMMON_SGDS.map((opt) => (
                  <option key={opt} value={opt} />
                ))}
              </datalist>
            </div>
          </div>

          {/* Row 2: Planned Grade & Deployment Type */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Planned Grade Code (Optional)
              </label>
              <input
                type="text"
                value={plannedGrade}
                onChange={(e) => setPlannedGrade(e.target.value)}
                placeholder="e.g. GARDENER_L1"
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Deployment Type *
              </label>
              <select
                value={deploymentType}
                onChange={(e) => setDeploymentType(e.target.value as "PERMANENT" | "REMOTE")}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none bg-white"
              >
                <option value="PERMANENT">PERMANENT (Dedicated on-site roster)</option>
                <option value="REMOTE">REMOTE (Dispatched / mobile team)</option>
              </select>
            </div>
          </div>

          {/* Row 3: Frequency Configuration */}
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 space-y-3">
            <span className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
              Frequency & Schedule
            </span>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">
                  Unit
                </label>
                <select
                  value={frequencyUnit}
                  onChange={(e) => setFrequencyUnit(e.target.value as any)}
                  className="w-full px-2.5 py-1.5 text-xs border border-slate-300 rounded-md bg-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
                >
                  <option value="WEEK">Week(s)</option>
                  <option value="MONTH">Month(s)</option>
                  <option value="QUARTER">Quarter(s)</option>
                  <option value="YEAR">Year(s)</option>
                </select>
              </div>
              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">
                  Times per Period
                </label>
                <input
                  type="number"
                  min="1"
                  max="365"
                  value={occurrencesPerPeriod}
                  onChange={(e) => setOccurrencesPerPeriod(parseInt(e.target.value) || 1)}
                  className="w-full px-2.5 py-1.5 text-xs border border-slate-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-slate-600 mb-1">
                  Every (Interval)
                </label>
                <input
                  type="number"
                  min="1"
                  max="52"
                  value={periodInterval}
                  onChange={(e) => setPeriodInterval(parseInt(e.target.value) || 1)}
                  className="w-full px-2.5 py-1.5 text-xs border border-slate-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                />
              </div>
            </div>

            {/* Weekdays picker if Week unit */}
            {frequencyUnit === "WEEK" && (
              <div className="pt-2">
                <label className="block text-[11px] font-medium text-slate-600 mb-1.5">
                  Scheduled Days of Week
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {WEEKDAYS.map((w) => {
                    const isSelected = selectedWeekdays.includes(w.day);
                    return (
                      <button
                        type="button"
                        key={w.day}
                        onClick={() => toggleWeekday(w.day)}
                        className={`px-3 py-1 text-xs font-semibold rounded-md border transition-colors ${
                          isSelected
                            ? "bg-indigo-600 border-indigo-600 text-white shadow-xs"
                            : "bg-white border-slate-300 text-slate-700 hover:bg-slate-100"
                        }`}
                      >
                        {w.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Row 4: Staffing & Hours */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Required Staff Count *
              </label>
              <input
                type="number"
                min="1"
                max="50"
                value={requiredStaff}
                onChange={(e) => setRequiredStaff(parseInt(e.target.value) || 1)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Hours / Occ / Staff *
              </label>
              <input
                type="number"
                step="0.001"
                min="0.25"
                max="300"
                value={hoursPerOccurrence}
                onChange={(e) => setHoursPerOccurrence(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Break Override (Minutes)
              </label>
              <input
                type="number"
                min="0"
                max="180"
                placeholder="Default (from zone)"
                value={breakOverride}
                onChange={(e) =>
                  setBreakOverride(e.target.value === "" ? "" : parseInt(e.target.value))
                }
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none"
              />
            </div>
          </div>

          {/* Live Preview Panel */}
          <div className="bg-indigo-50/60 border border-indigo-200 rounded-lg p-3.5 space-y-2 text-xs">
            <div className="flex items-center gap-2 font-semibold text-indigo-900">
              <Calculator className="h-4 w-4 text-indigo-600" />
              <span>Calculated Planning Metrics</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-1">
              <div className="bg-white p-2.5 rounded border border-indigo-100">
                <span className="text-slate-500 block text-[10px]">Expected Activities / Yr</span>
                <span className="font-bold text-slate-900 text-sm">
                  {calculatedActivities.toLocaleString()}
                </span>
              </div>
              <div className="bg-white p-2.5 rounded border border-indigo-100">
                <span className="text-slate-500 block text-[10px]">Expected Annual Hours</span>
                <span className="font-bold text-indigo-700 text-sm">
                  {calculatedAnnualHours.toLocaleString(undefined, { maximumFractionDigits: 1 })} h
                </span>
              </div>
              <div className="bg-white p-2.5 rounded border border-indigo-100 col-span-2 sm:col-span-1">
                <span className="text-slate-500 block text-[10px]">Occurrence Duration</span>
                <span className="font-bold text-slate-900 text-sm">
                  {daysPerOccurrence} day{daysPerOccurrence > 1 ? "s" : ""}
                </span>
              </div>
            </div>

            {isMultiDay && (
              <div className="flex items-start gap-1.5 text-[11px] text-indigo-800 pt-1">
                <Info className="h-3.5 w-3.5 text-indigo-600 shrink-0 mt-0.5" />
                <span>
                  Hours exceed 9.0h standard shift. Occurrence will be chunked into{" "}
                  <strong>{daysPerOccurrence} days</strong> ({Math.floor(parsedHours / 9)} x 9.0h +{" "}
                  {(parsedHours % 9).toFixed(3)}h).
                </span>
              </div>
            )}
          </div>

          {/* Footer Actions */}
          <div className="pt-2 flex justify-end gap-3 border-t border-slate-200">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
            >
              {loading ? "Saving..." : initialData ? "Save Changes" : "Create Job Item"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
