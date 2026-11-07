export interface RosterSiteChip {
  scheduled_work_id: string;
  worksite_id: string;
  job_number: string;
  job_name: string;
  job_item_id: string;
  sub_item_code: string;
  deployment_type: string;
  assigned_hours: number | string;
  sequence: number;
  has_boundary: boolean;
}

export interface RosterDayCell {
  work_date: string;
  weekday: string;
  chips: RosterSiteChip[];
  marker: string | null; // SKIPPED, WEEKLY_OFF, ON_LEAVE, TO_BE_COVERED, FREE
  day_total_hours: number | string;
  is_over_standard: boolean;
  is_under_standard: boolean;
}

export interface RosterWorkerRow {
  employee_id: string;
  name: string;
  tally_id: string;
  grade_code: string | null;
  staff_grade_description: string | null;
  weekly_off_day?: string | null;
  standard_hours: number | string;
  effective_daily_standard_hours: number | string;
  days: RosterDayCell[];
  week_allocated_hours: number | string;
  week_standard_hours: number | string;
  week_is_over: boolean;
  week_is_under: boolean;
  supervisor_id?: string | null;
  supervisor_name?: string | null;
  remarks: string | null;
}

export interface RosterResponse {
  week_start: string;
  week_end: string;
  total_workers: number;
  workers: RosterWorkerRow[];
}

export interface AssignedWorkerSummary {
  employee_id: string;
  name: string;
  tally_id: string;
  scheduled_work_id: string;
  source?: string;
  standing_assignment_id?: string | null;
  standing_assignment_version?: number | null;
}

export interface CoverageDayCell {
  work_date: string;
  weekday: string;
  required_staff_count: number;
  assigned_staff_count: number;
  is_to_be_covered: boolean;
  is_excess?: boolean;
  is_quota_met?: boolean;
  is_holiday?: boolean;
  holiday_name?: string | null;
  assigned_workers: string[];
  assigned_details?: AssignedWorkerSummary[];
}

export interface CoverageItemRow {
  job_item_id: string;
  sub_item_code: string;
  staff_grade_description: string;
  planned_grade_code: string;
  deployment_type: string;
  required_staff_count: number;
  hours_per_occurrence: number;
  frequency_unit?: string;
  occurrences_per_period?: number | string;
  days: CoverageDayCell[];
}

export interface CoverageWorksiteRow {
  worksite_id: string;
  job_number: string;
  job_name: string;
  customer_type?: string | null;
  is_outdoor?: boolean;
  items: CoverageItemRow[];
}

export interface CoverageResponse {
  week_start: string;
  week_end: string;
  worksites: CoverageWorksiteRow[];
}

export interface StandingAssignmentRead {
  id: string;
  employee_id: string;
  employee_name: string | null;
  job_item_id: string;
  job_number: string | null;
  sub_item_code: string | null;
  start_date: string;
  end_date: string | null;
  weekday_pattern: string[] | null;
  hours_per_day: number | null;
  is_active: boolean;
  version: number;
  created_at: string;
}

export interface WorkerAllocationResponse {
  employee_id: string;
  employee_name: string;
  base_standard_hours: number | string;
  effective_daily_standard_hours: number | string;
  today_allocated_hours: number | string;
  today_standard_hours: number | string;
  today_diff: number | string;
  today_is_over: boolean;
  today_is_under: boolean;
  week_allocated_hours: number | string;
  week_standard_hours: number | string;
  week_diff: number | string;
  week_is_over: boolean;
  week_is_under: boolean;
  month_allocated_hours: number | string;
  month_standard_hours: number | string;
  month_diff: number | string;
  month_is_over: boolean;
  month_is_under: boolean;
}

export interface CandidateRecommendation {
  employee_id: string;
  name: string;
  tally_id: string;
  grade_code: string | null;
  staff_grade_description: string | null;
  weekly_off_day?: string | null;
  standard_hours: number | string;
  exact_staff_type_match: boolean;
  ranking_score: number;
  reasons: string[];
  warnings: string[];
  today_allocated_hours: number | string;
  weekly_allocated_hours: number | string;
  monthly_allocated_hours: number | string;
  supervisor_id?: string | null;
  supervisor_name?: string | null;
  shares_site_group?: boolean;
  is_blocked?: boolean;
  blocked_reason?: string | null;
}

export interface ValidationIssue {
  code: string;
  severity: "ERROR" | "WARNING" | "INFO";
  message: string;
}

export interface ValidationReport {
  is_valid: boolean;
  issues: ValidationIssue[];
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
  infos: ValidationIssue[];
}

// -------------------------------------------------------------------------
// Base Planner (Recurring Blueprint) Types
// -------------------------------------------------------------------------

export interface BaseRosterEntryRead {
  id: string;
  template_id: string;
  employee_id: string;
  employee_name?: string | null;
  tally_id?: string | null;
  weekly_off_day?: string | null;
  weekday_mask: string; // "ALL" | "MON" .. "SUN"
  assigned_hours: number | string;
  sequence: number;
}

export interface BaseRosterEntryCreate {
  employee_id: string;
  weekday_mask: string;
  assigned_hours: number | string;
  sequence?: number;
}

export interface BaseRosterTemplateRead {
  id: string;
  job_item_id: string;
  allocation_mode: "UNIFORM" | "DAY_OF_WEEK";
  start_date: string;
  end_date?: string | null;
  is_active: boolean;
  version: number;
  entries: BaseRosterEntryRead[];
}

export interface BaseRosterTemplateCreate {
  job_item_id: string;
  allocation_mode: "UNIFORM" | "DAY_OF_WEEK";
  start_date: string;
  end_date?: string | null;
  entries: BaseRosterEntryCreate[];
}

export interface BasePlannerItemRow {
  job_item_id: string;
  sub_item_code: string;
  staff_grade_description: string;
  planned_grade_code: string;
  deployment_type: string;
  required_staff_count: number;
  hours_per_occurrence: number | string;
  frequency_unit: string;
  occurrences_per_period: number | string;
  weekday_pattern?: string[] | null;
  start_date?: string | null;
  end_date?: string | null;
  template?: BaseRosterTemplateRead | null;
}

export interface BasePlannerWorksiteRow {
  worksite_id: string;
  job_number: string;
  job_name: string;
  customer_type?: string | null;
  is_outdoor?: boolean;
  start_date?: string | null;
  end_date?: string | null;
  budget_amount?: number | string | null;
  items: BasePlannerItemRow[];
}

export interface BasePlannerResponse {
  worksites: BasePlannerWorksiteRow[];
}

// -------------------------------------------------------------------------
// Operational Planner Types
// -------------------------------------------------------------------------

export interface OperationalCellWorker {
  employee_id: string;
  employee_name: string;
  tally_id?: string | null;
  assigned_hours: number | string;
  display_type: "BLUEPRINT" | "OVERRIDE" | "DIRECT" | "TO_BE_COVERED";
  opacity_class: "muted" | "solid" | "warning";
  original_employee_id?: string | null;
  original_employee_name?: string | null;
  shift_id?: string | null;
  reason?: string | null;
  is_public_holiday?: boolean;
  is_rest_day?: boolean;
  tags: string[];
}

export interface OperationalDayCell {
  work_date: string;
  weekday: string;
  required_staff_count: number;
  assigned_staff_count: number;
  is_public_holiday: boolean;
  holiday_name?: string | null;
  is_recommended_target: boolean;
  is_quota_met: boolean;
  is_excess: boolean;
  is_to_be_covered: boolean;
  workers: OperationalCellWorker[];
}

export interface OperationalJobItemRow {
  job_item_id: string;
  sub_item_code: string;
  staff_grade_description: string;
  planned_grade_code: string;
  deployment_type: string;
  required_staff_count: number;
  hours_per_occurrence: number | string;
  frequency_unit: string;
  occurrences_per_period: number | string;
  quota_target: number;
  quota_assigned: number;
  quota_satisfied: boolean;
  days: OperationalDayCell[];
}

export interface OperationalWorksiteRow {
  worksite_id: string;
  job_number: string;
  job_name: string;
  customer_type?: string | null;
  is_outdoor?: boolean;
  start_date?: string | null;
  end_date?: string | null;
  budget_amount?: number | string | null;
  items: OperationalJobItemRow[];
}

export interface OperationalCoverageResponse {
  week_start: string;
  week_end: string;
  worksites: OperationalWorksiteRow[];
}

export interface OperationalRosterDayCell {
  work_date: string;
  weekday: string;
  is_working_day: boolean;
  is_weekly_off: boolean;
  is_public_holiday: boolean;
  holiday_name?: string | null;
  leave_type?: string | null;
  allocated_hours: number | string;
  shifts: OperationalCellWorker[];
}

export interface OperationalRosterWorkerRow {
  employee_id: string;
  tally_id: string;
  name: string;
  staff_grade_description?: string | null;
  weekly_off_day?: string | null;
  total_week_hours: number | string;
  standard_week_hours: number | string;
  days: OperationalRosterDayCell[];
}

export interface OperationalRosterResponse {
  week_start: string;
  week_end: string;
  workers: OperationalRosterWorkerRow[];
}

export interface OperationalShiftCreate {
  job_item_id: string;
  work_date: string;
  employee_id: string;
  original_employee_id?: string | null;
  assigned_hours?: number | string | null;
  override_reason?: string | null;
  source?: "DIRECT" | "OVERRIDE";
  acknowledge_warnings?: boolean;
}


