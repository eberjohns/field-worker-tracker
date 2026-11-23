export const CONTROLLED_STAFF_GRADE_DESCRIPTIONS = [
  "Admin",
  "Commercial - QS",
  "Foreman With DL",
  "Foreman Without DL",
  "Gardener - Hand Watering",
  "Gardener Expert",
  "Gardener Helper",
  "HSE Engineer",
  "Irrigation Engineer",
  "Irrigation Technician",
  "Landscaping Engineer",
  "Palm Tree Technician",
  "Project Manager",
  "Superintendent",
  "Supervisor",
  "Team Leader",
];

// Grade dropdowns read GET /api/v1/grades (features/grades); no hard-coded list (DEC-58).

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
