export interface AttendanceCalculationSnapshot {
  id: string;
  version_no: number;
  input_hash: string;
  calculated_at: string;
  engine_version: string;
  reason: string;

  planned_accommodation_departure: string | null;
  planned_first_site_start: string | null;
  planned_break_minutes: number;
  planned_last_site_end: string | null;
  planned_accommodation_return: string | null;
  planned_total_minutes: number;
  planned_worked_minutes: number;
  standard_hours_minutes: number;

  accommodation_departure_at: string | null;
  first_site_entry_at: string | null;
  break_minutes_used: number;
  break_source: string;
  last_site_exit_at: string | null;
  accommodation_return_at: string | null;
  elapsed_site_minutes: number;
  shift_span_minutes: number;
  unaccounted_minutes: number;
  worked_minutes: number;
  required_minutes: number;
  variation_minutes: number;
  shortfall_minutes: number;
  grace_minutes: number;
  grace_applied: boolean;
  satisfied: boolean;

  productive_minutes: number;
  transit_minutes: number;
  offsite_minutes: number;
  idle_minutes: number;

  ot1_minutes: number;
  ot2_minutes: number;
  ot_threshold_minutes: number;
  day_type: string;
  assigned_count: number;
  completed_count: number;
  business_status: string;

  flags: string[];
  review_reasons: string[];
  visits_snapshot: any[];
  gaps_snapshot: any[];
  inputs_snapshot: Record<string, any>;
  source_event_ids: string[];
}

export interface AttendanceComment {
  id: string;
  attendance_id: string;
  author_user_id: string;
  author_name: string;
  comment_type: string;
  comment_text: string;
  scheduled_work_id: string | null;
  created_at: string;
}

export interface AttendanceApproval {
  id: string;
  attendance_id: string;
  reviewer_user_id: string;
  reviewer_name: string;
  decision: "APPROVED" | "REJECTED";
  comment: string;
  calculation_id: string;
  created_at: string;
}

export interface AttendanceRecord {
  id: string;
  employee_id: string;
  employee_name: string;
  tally_id: string;
  supervisor_name: string | null;
  work_date: string;
  business_status: "PRESENT" | "PARTIAL" | "ABSENT" | "REST" | "ON_LEAVE" | "FREE";
  review_status: "AUTO" | "PENDING_REVIEW" | "APPROVED" | "REJECTED";
  locked: boolean;
  created_at: string;
  updated_at: string;
  current_calculation: AttendanceCalculationSnapshot | null;
  comments: AttendanceComment[];
  approvals: AttendanceApproval[];
}

export interface AttendanceListResponse {
  items: AttendanceRecord[];
  total: number;
}

export interface TimelineItem {
  item_id: string;
  item_type: string;
  label: string;
  place_name: string | null;
  started_at: string;
  ended_at: string | null;
  duration_minutes: number;
  is_inferred: boolean;
  flags: string[];
  details?: {
    counts_as_completed?: boolean;
    entry_event_id?: string;
    exit_event_id?: string | null;
    distance_between_m?: number;
    latitude?: number | null;
    longitude?: number | null;
    accuracy?: number | null;
    verdict?: string | null;
    [key: string]: any;
  };
  id?: string;
  title?: string;
  timestamp?: string;
  description?: string;
  latitude?: number | null;
  longitude?: number | null;
}

