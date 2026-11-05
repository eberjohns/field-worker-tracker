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
  standard_hours: number | string;
  effective_daily_standard_hours: number | string;
  days: RosterDayCell[];
  week_allocated_hours: number | string;
  week_standard_hours: number | string;
  week_is_over: boolean;
  week_is_under: boolean;
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
}

export interface CoverageDayCell {
  work_date: string;
  weekday: string;
  required_staff_count: number;
  assigned_staff_count: number;
  is_to_be_covered: boolean;
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

