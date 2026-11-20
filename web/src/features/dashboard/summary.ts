/**
 * Maps GET /api/v1/dashboard/summary (backend `DashboardSummaryResponse`) to the values the
 * Dashboard cards show. The cards used to read field names the API never returned
 * (`pending_visits.total_open`, `live.*`, `late_arrivals.count`, `overtime.total_ot_hours`),
 * so they always showed 0. Keep this the only place that knows the API field names.
 */

export interface DashboardSummaryApi {
  today_date?: string;
  attendance?: {
    present?: number;
    partial?: number;
    absent?: number;
    not_started?: number;
    total_scheduled?: number;
  };
  live_workers?: {
    active?: number;
    no_recent_signal?: number;
    location_disabled?: number;
    not_scheduled?: number;
    total?: number;
  };
  pending_visits_count?: number;
  pending_visits_escalated_count?: number;
  late_arrivals_count?: number;
  overtime_hours_today?: number;
  open_alerts_count?: number;
  expiring_documents_count?: number;
  pending_approvals_count?: number;
  unassigned_worksites_count?: number | null;
}

export interface DashboardCards {
  attendance: { present: number; partial: number; absent: number; notStarted: number; totalScheduled: number };
  live: { active: number; noRecentSignal: number; locationDisabled: number; notScheduled: number; total: number };
  pendingVisits: { open: number; escalated: number };
  lateArrivals: number;
  overtimeHours: number;
  openAlerts: number;
  expiringDocuments: number;
  pendingApprovals: number;
  unassignedWorksites: number;
}

const n = (v: unknown): number => (typeof v === "number" && Number.isFinite(v) ? v : 0);

export function mapDashboardSummary(api: DashboardSummaryApi | null | undefined): DashboardCards {
  const a = api ?? {};
  return {
    attendance: {
      present: n(a.attendance?.present),
      partial: n(a.attendance?.partial),
      absent: n(a.attendance?.absent),
      notStarted: n(a.attendance?.not_started),
      totalScheduled: n(a.attendance?.total_scheduled),
    },
    live: {
      active: n(a.live_workers?.active),
      noRecentSignal: n(a.live_workers?.no_recent_signal),
      locationDisabled: n(a.live_workers?.location_disabled),
      notScheduled: n(a.live_workers?.not_scheduled),
      total: n(a.live_workers?.total),
    },
    pendingVisits: { open: n(a.pending_visits_count), escalated: n(a.pending_visits_escalated_count) },
    lateArrivals: n(a.late_arrivals_count),
    overtimeHours: n(a.overtime_hours_today),
    openAlerts: n(a.open_alerts_count),
    expiringDocuments: n(a.expiring_documents_count),
    pendingApprovals: n(a.pending_approvals_count),
    unassignedWorksites: n(a.unassigned_worksites_count),
  };
}
