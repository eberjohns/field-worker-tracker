// Staff type and grade dropdowns read the managed lists (components/lookups/LookupSelect, DEC-60).

export function formatApiError(errData: any): string {
  if (Array.isArray(errData?.invalid_params) && errData.invalid_params.length > 0) {
    return errData.invalid_params
      .map((p: any) => {
        const field = p.field ? String(p.field).replace(/^body\./, "") : "error";
        const reason = p.reason ? String(p.reason).replace(/^Value error,\s*/i, "") : "Invalid value";
        return `${field}: ${reason}`;
      })
      .join("\n");
  }
  if (Array.isArray(errData?.detail)) {
    return errData.detail
      .map((d: any) => {
        const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : d.loc || "error";
        const msg = d.msg ? String(d.msg).replace(/^Value error,\s*/i, "") : "Invalid value";
        return `${field}: ${msg}`;
      })
      .join("\n");
  }
  if (typeof errData?.detail === "string" && errData.detail !== "Request validation failed.") {
    return errData.detail;
  }
  return errData?.message || errData?.detail || "Failed to save job item.";
}

export interface JobItemPayloadParams {
  subItemCode: string;
  sgd: string;
  plannedGrade: string;
  startDate: string;
  endDate?: string | null;
  frequencyUnit: "WEEK" | "MONTH" | "QUARTER" | "YEAR";
  occurrencesPerPeriod: number;
  periodInterval: number;
  selectedWeekdays?: string[] | null;
  requiredStaff: number;
  hoursPerOccurrence: number | string;
  deploymentType: "PERMANENT" | "REMOTE";
  breakOverride?: number | string | null;
}

export function buildJobItemPayload(params: JobItemPayloadParams): Record<string, any> {
  const parsedHours = parseFloat(String(params.hoursPerOccurrence)) || 0;
  const staffCount = params.requiredStaff || 1;
  const interval = params.periodInterval > 0 ? params.periodInterval : 1;

  return {
    sub_item_code: params.subItemCode.trim(),
    staff_grade_description: params.sgd.trim(),
    planned_grade_code: params.plannedGrade.trim(),
    start_date: params.startDate.trim(),
    end_date: params.endDate?.trim() || null,
    frequency_unit: params.frequencyUnit,
    occurrences_per_period: params.occurrencesPerPeriod,
    period_interval: interval,
    weekday_pattern:
      params.selectedWeekdays && params.selectedWeekdays.length > 0
        ? params.selectedWeekdays
        : null,
    required_staff_count: staffCount,
    hours_per_occurrence_per_staff: parsedHours,
    deployment_type: params.deploymentType,
    break_override_minutes:
      params.breakOverride === "" || params.breakOverride == null
        ? null
        : Number(params.breakOverride),
  };
}

// --- Job item drafts: one shape for the job item modal and the Add Worksite wizard rows ---

export type FrequencyUnit = "WEEK" | "MONTH" | "QUARTER" | "YEAR";
export type DeploymentType = "PERMANENT" | "REMOTE";

export const WEEKDAY_CODES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"] as const;
export const WORKING_WEEK = ["MON", "TUE", "WED", "THU", "FRI", "SAT"];

export interface JobItemDraft {
  sub_item_code: string;
  staff_grade_description: string;
  planned_grade_code: string;
  start_date: string;
  end_date: string;
  frequency_unit: FrequencyUnit;
  occurrences_per_period: number;
  period_interval: number;
  weekday_pattern: string[];
  required_staff_count: number;
  hours_per_occurrence_per_staff: number | string;
  deployment_type: DeploymentType;
  break_override_minutes: number | "";
}

/** A new item: no staff type or grade preselected (handover 6.1 A), dates from the contract. */
export function emptyDraft(code: string, startDate: string, endDate = ""): JobItemDraft {
  return {
    sub_item_code: code,
    staff_grade_description: "",
    planned_grade_code: "",
    start_date: startDate,
    end_date: endDate,
    frequency_unit: "WEEK",
    occurrences_per_period: 6,
    period_interval: 1,
    weekday_pattern: [...WORKING_WEEK],
    required_staff_count: 1,
    hours_per_occurrence_per_staff: 9,
    deployment_type: "PERMANENT",
    break_override_minutes: "",
  };
}

/** Copy of a row under a new sub-item code. */
export function duplicateDraft(draft: JobItemDraft, code: string): JobItemDraft {
  return { ...draft, sub_item_code: code, weekday_pattern: [...draft.weekday_pattern] };
}

function codeToNumber(code: string): number | null {
  if (!/^[A-Z]+$/.test(code)) return null;
  let n = 0;
  for (const ch of code) n = n * 26 + (ch.charCodeAt(0) - 64);
  return n;
}

function numberToCode(n: number): string {
  let code = "";
  while (n > 0) {
    const rem = (n - 1) % 26;
    code = String.fromCharCode(65 + rem) + code;
    n = Math.floor((n - 1) / 26);
  }
  return code;
}

/** The first free code in A, B, … Z, AA, AB … (case-insensitive). */
export function nextSubItemCode(existing: string[]): string {
  const used = new Set(
    existing
      .map((c) => codeToNumber(c.trim().toUpperCase()))
      .filter((n): n is number => n !== null),
  );
  let n = 1;
  while (used.has(n)) n += 1;
  return numberToCode(n);
}

export function draftHours(draft: JobItemDraft): number {
  return parseFloat(String(draft.hours_per_occurrence_per_staff)) || 0;
}

/** What is missing before the item can be checked or saved ("" when ready). */
export function draftProblem(draft: JobItemDraft): string {
  if (!draft.sub_item_code.trim()) return "a sub-item code";
  if (!draft.staff_grade_description.trim()) return "a staff type";
  if (!draft.planned_grade_code.trim()) return "a planned grade";
  if (!draft.start_date.trim()) return "a start date";
  if (draftHours(draft) <= 0) return "hours per staff above 0";
  if (!(draft.occurrences_per_period > 0)) return "occurrences per period";
  if (!(draft.required_staff_count > 0)) return "a staff count";
  if (draft.end_date && draft.end_date < draft.start_date) return "an end date after the start";
  return "";
}

export function draftReady(draft: JobItemDraft): boolean {
  return draftProblem(draft) === "";
}

/** API body for POST/PATCH and the previews (same mapping as buildJobItemPayload). */
export function draftToPayload(draft: JobItemDraft): Record<string, any> {
  return buildJobItemPayload({
    subItemCode: draft.sub_item_code,
    sgd: draft.staff_grade_description,
    plannedGrade: draft.planned_grade_code,
    startDate: draft.start_date,
    endDate: draft.end_date,
    frequencyUnit: draft.frequency_unit,
    occurrencesPerPeriod: draft.occurrences_per_period,
    periodInterval: draft.period_interval,
    selectedWeekdays: draft.frequency_unit === "WEEK" ? draft.weekday_pattern : null,
    requiredStaff: draft.required_staff_count,
    hoursPerOccurrence: draft.hours_per_occurrence_per_staff,
    deploymentType: draft.deployment_type,
    breakOverride: draft.break_override_minutes,
  });
}

/** Sub-item codes used more than once (upper case). */
export function duplicateCodes(drafts: JobItemDraft[]): string[] {
  const seen = new Map<string, number>();
  for (const d of drafts) {
    const c = d.sub_item_code.trim().toUpperCase();
    if (c) seen.set(c, (seen.get(c) ?? 0) + 1);
  }
  return [...seen.entries()].filter(([, n]) => n > 1).map(([c]) => c);
}

export interface RowError {
  /** Wizard step that holds the field: 1 worksite, 2 job items. */
  step: 1 | 2;
  row: number | null;
  field: string | null;
  message: string;
}

/**
 * Where a create error belongs (Batch 5.1 B). Service errors carry `field` like
 * "job_items[2].planned_grade_code"; schema errors carry "body.job_items.2.required_staff_count".
 */
export function rowError(errData: any): RowError {
  const message = formatApiError(errData);
  const paths: string[] = [];
  if (typeof errData?.field === "string") paths.push(errData.field);
  if (Array.isArray(errData?.invalid_params)) {
    for (const p of errData.invalid_params) if (p?.field) paths.push(String(p.field));
  }
  for (const raw of paths) {
    const path = raw.replace(/^body\./, "");
    const m = /^job_items(?:\[(\d+)\]|\.(\d+))(?:\.(\w+))?/.exec(path);
    if (m) {
      return { step: 2, row: Number(m[1] ?? m[2]), field: m[3] ?? null, message };
    }
  }
  const first = paths[0]?.replace(/^body\./, "") ?? null;
  return { step: 1, row: null, field: first, message };
}
