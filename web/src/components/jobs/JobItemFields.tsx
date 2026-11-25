import React from "react";
import { LookupSelect } from "../lookups/LookupSelect";
import { DatePicker } from "../../ui";
import { WEEKDAY_CODES, type FrequencyUnit, type JobItemDraft } from "./jobItemUtils";

/**
 * The fields of one job item, shared by the job item modal and the Add Worksite wizard rows
 * (Batch 5.1 B). Controlled: the parent keeps the draft.
 */
export interface JobItemFieldsProps {
  draft: JobItemDraft;
  onChange: (patch: Partial<JobItemDraft>) => void;
  /** "edit" shows the break override input (modal); "display" shows a label only (wizard). */
  breakMode?: "edit" | "display";
  /** Field to highlight after a failed save, e.g. "planned_grade_code". */
  errorField?: string | null;
  idPrefix?: string;
}

const WEEKDAY_LABEL: Record<string, string> = {
  MON: "Mon",
  TUE: "Tue",
  WED: "Wed",
  THU: "Thu",
  FRI: "Fri",
  SAT: "Sat",
  SUN: "Sun",
};

const inputBase =
  "w-full px-3 py-2 text-sm border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none bg-white";

export const JobItemFields: React.FC<JobItemFieldsProps> = ({
  draft,
  onChange,
  breakMode = "edit",
  errorField = null,
  idPrefix = "ji",
}) => {
  const ring = (field: string) =>
    `${inputBase} ${errorField === field ? "border-rose-500 ring-1 ring-rose-400" : "border-slate-300"}`;
  const label = "block text-xs font-semibold text-slate-700 mb-1";
  const small = "block text-[11px] font-medium text-slate-600 mb-1";

  const toggleWeekday = (code: string) => {
    const has = draft.weekday_pattern.includes(code);
    onChange({
      weekday_pattern: has
        ? draft.weekday_pattern.filter((c) => c !== code)
        : WEEKDAY_CODES.filter((c) => c === code || draft.weekday_pattern.includes(c)),
    });
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label className={label} htmlFor={`${idPrefix}-code`}>
            Sub-Item Code *
          </label>
          <input
            id={`${idPrefix}-code`}
            type="text"
            required
            value={draft.sub_item_code}
            onChange={(e) => onChange({ sub_item_code: e.target.value })}
            placeholder="e.g. A, B, M01"
            className={ring("sub_item_code")}
          />
        </div>
        <div>
          <label className={label} htmlFor={`${idPrefix}-sgd`}>
            Staff Type *
          </label>
          <LookupSelect
            id={`${idPrefix}-sgd`}
            listKey="staff_grade_description"
            required
            value={draft.staff_grade_description}
            onChange={(v) => onChange({ staff_grade_description: v })}
            placeholder="Select staff type *"
            inputClassName={ring("staff_grade_description")}
          />
        </div>
        <div>
          <label className={label} htmlFor={`${idPrefix}-grade`}>
            Planned Grade *
          </label>
          <LookupSelect
            id={`${idPrefix}-grade`}
            listKey="grade_code"
            required
            value={draft.planned_grade_code}
            onChange={(v) => onChange({ planned_grade_code: v })}
            placeholder="Select grade *"
            inputClassName={ring("planned_grade_code")}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label className={label} htmlFor={`${idPrefix}-deploy`}>
            Deployment *
          </label>
          <select
            id={`${idPrefix}-deploy`}
            value={draft.deployment_type}
            onChange={(e) =>
              onChange({ deployment_type: e.target.value as JobItemDraft["deployment_type"] })
            }
            className={ring("deployment_type")}
          >
            <option value="PERMANENT">Permanent (on-site roster)</option>
            <option value="REMOTE">Remote (dispatched team)</option>
          </select>
        </div>
        <DatePicker
          id={`${idPrefix}-start`}
          label="Start Date"
          required
          size="sm"
          value={draft.start_date}
          onChange={(iso) => onChange({ start_date: iso })}
          error={errorField === "start_date" ? "Check the start date" : undefined}
        />
        <DatePicker
          id={`${idPrefix}-end`}
          label="End Date"
          size="sm"
          value={draft.end_date}
          min={draft.start_date || undefined}
          onChange={(iso) => onChange({ end_date: iso })}
          error={errorField === "end_date" ? "Check the end date" : undefined}
        />
      </div>

      <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-3">
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className={small} htmlFor={`${idPrefix}-unit`}>
              Frequency unit
            </label>
            <select
              id={`${idPrefix}-unit`}
              value={draft.frequency_unit}
              onChange={(e) => onChange({ frequency_unit: e.target.value as FrequencyUnit })}
              className={ring("frequency_unit")}
            >
              <option value="WEEK">Week(s)</option>
              <option value="MONTH">Month(s)</option>
              <option value="QUARTER">Quarter(s)</option>
              <option value="YEAR">Year(s)</option>
            </select>
          </div>
          <div>
            <label className={small} htmlFor={`${idPrefix}-occ`}>
              Times per period
            </label>
            <input
              id={`${idPrefix}-occ`}
              type="number"
              min="1"
              max="365"
              value={draft.occurrences_per_period}
              onChange={(e) => onChange({ occurrences_per_period: parseInt(e.target.value) || 0 })}
              className={ring("occurrences_per_period")}
            />
          </div>
          <div>
            <label className={small} htmlFor={`${idPrefix}-int`}>
              Every (interval)
            </label>
            <input
              id={`${idPrefix}-int`}
              type="number"
              min="1"
              max="52"
              value={draft.period_interval}
              onChange={(e) => onChange({ period_interval: parseInt(e.target.value) || 1 })}
              className={ring("period_interval")}
            />
          </div>
        </div>
        {draft.frequency_unit === "WEEK" && (
          <div>
            <span className={small}>Days of the week</span>
            <div className="flex flex-wrap gap-1.5">
              {WEEKDAY_CODES.map((code) => {
                const on = draft.weekday_pattern.includes(code);
                return (
                  <button
                    type="button"
                    key={code}
                    aria-pressed={on}
                    onClick={() => toggleWeekday(code)}
                    className={`px-3 py-1 text-xs font-semibold rounded-md border transition-colors ${
                      on
                        ? "bg-indigo-600 border-indigo-600 text-white"
                        : "bg-white border-slate-300 text-slate-700 hover:bg-slate-100"
                    }`}
                  >
                    {WEEKDAY_LABEL[code]}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label className={label} htmlFor={`${idPrefix}-staff`}>
            Staff count *
          </label>
          <input
            id={`${idPrefix}-staff`}
            type="number"
            min="1"
            max="50"
            value={draft.required_staff_count}
            onChange={(e) => onChange({ required_staff_count: parseInt(e.target.value) || 0 })}
            className={ring("required_staff_count")}
          />
        </div>
        <div>
          <label className={label} htmlFor={`${idPrefix}-hours`}>
            Hours per staff per visit *
          </label>
          <input
            id={`${idPrefix}-hours`}
            type="number"
            step="0.001"
            min="0.25"
            max="300"
            value={draft.hours_per_occurrence_per_staff}
            onChange={(e) => onChange({ hours_per_occurrence_per_staff: e.target.value })}
            className={ring("hours_per_occurrence_per_staff")}
          />
        </div>
        <div>
          {breakMode === "edit" ? (
            <>
              <label className={label} htmlFor={`${idPrefix}-break`}>
                Break override (minutes)
              </label>
              <input
                id={`${idPrefix}-break`}
                type="number"
                min="0"
                max="180"
                placeholder="Default (time rules)"
                value={draft.break_override_minutes}
                onChange={(e) =>
                  onChange({
                    break_override_minutes: e.target.value === "" ? "" : parseInt(e.target.value),
                  })
                }
                className={ring("break_override_minutes")}
              />
            </>
          ) : (
            <>
              <span className={label}>Break</span>
              <p className="px-3 py-2 text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-lg">
                From time rules (display only; an override can be set later on the item)
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
