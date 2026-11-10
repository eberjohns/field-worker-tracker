import React, { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import {
  Server,
  Activity,
  Database,
  CheckCircle2,
  AlertTriangle,
  Hexagon,
  ArrowRight,
  ShieldAlert,
  Users,
  CheckSquare,
  Clock,
  Calendar,
  TrendingUp,
  Radio,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import type { components } from "../api/schema";

type HealthResponse = components["schemas"]["HealthResponse"];

interface AlertItem {
  id: string;
  alert_type: string;
  title: string;
  message: string;
  ref_type: string;
  ref_id: string | null;
  employee_id: string | null;
  status: string;
  created_at: string;
  details: Record<string, any>;
}

export const Dashboard: React.FC = () => {
  const { token, user } = useAuth();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [dashboardSummary, setDashboardSummary] = useState<any | null>(null);
  const [pendingBoundaryCount, setPendingBoundaryCount] = useState<number>(0);
  const [pendingLeaves, setPendingLeaves] = useState<any[]>([]);
  const [pendingReassigns, setPendingReassigns] = useState<any[]>([]);
  const [myRequests, setMyRequests] = useState<any[]>([]);

  useEffect(() => {
    fetch("/health")
      .then((res) => res.json())
      .then((data) => {
        setHealth(data);
        setLoading(false);
      })
      .catch(() => {
        // Fallback for standalone web development
        setHealth({
          status: "connected",
          country: "AE",
          environment: "local",
        });
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!token) return;
    const fetchAlertsAndBoundaries = async () => {
      try {
        const headers = { Authorization: `Bearer ${token}` };
        const alertsRes = await fetch("/api/v1/alerts", { headers });
        if (alertsRes.ok) {
          const alertData = await alertsRes.json();
          setAlerts(alertData || []);
        }

        const summaryRes = await fetch("/api/v1/dashboard/summary", { headers });
        if (summaryRes.ok) {
          const sumData = await summaryRes.json();
          setDashboardSummary(sumData);
        }

        if (user?.role === "ADMIN" || user?.role === "ENGINEER") {
          const bRes = await fetch("/api/v1/boundary-queue?status=UNSET", { headers });
          if (bRes.ok) {
            const bData = await bRes.json();
            setPendingBoundaryCount(bData.unset_count ?? bData.total_count ?? 0);
          }
          const appRes = await fetch("/api/v1/approvals?status=PENDING", { headers });
          if (appRes.ok) {
            const appData = await appRes.json();
            setPendingLeaves(appData.leave_requests || []);
            setPendingReassigns(appData.reassignment_requests || []);
          }
        } else if (user?.role === "SUPERVISOR") {
          const [reassignRes, leaveRes] = await Promise.all([
            fetch("/api/v1/reassignment-requests", { headers }),
            fetch("/api/v1/leave-requests", { headers }),
          ]);
          const combined: any[] = [];
          if (reassignRes.ok) {
            const rData = await reassignRes.json();
            combined.push(...(rData || []).map((item: any) => ({ ...item, category_kind: "REASSIGNMENT" })));
          }
          if (leaveRes.ok) {
            const lData = await leaveRes.json();
            combined.push(...(lData || []).map((item: any) => ({ ...item, category_kind: "LEAVE" })));
          }
          combined.sort(
            (a, b) =>
              new Date(b.created_at || b.recorded_at || 0).getTime() -
              new Date(a.created_at || a.recorded_at || 0).getTime()
          );
          setMyRequests(combined.slice(0, 10));
        }
      } catch (err) {
        console.error("Failed to load dashboard alerts", err);
      }
    };
    fetchAlertsAndBoundaries();
  }, [token, user]);

  const coverAlerts = alerts.filter((a) => a.alert_type === "COVER_NEEDED");

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">Operations & Health Overview</h2>
        <p className="text-sm text-slate-500 mt-1">
          Real-time field operations status, pending coverage alerts, and system telemetry.
        </p>
      </div>

      {/* Real-time Field Operations Overview */}
      {dashboardSummary && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* 1. Today's Attendance Breakdown */}
          <Link
            to="/attendance"
            className="p-5 bg-white rounded-xl border border-slate-200 shadow-sm hover:border-blue-300 hover:shadow-md transition group space-y-2"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Attendance Today</span>
              <Clock className="h-4 w-4 text-blue-500 group-hover:scale-110 transition-transform" />
            </div>
            <div className="text-2xl font-bold text-slate-900">
              {dashboardSummary.attendance?.present ?? 0}
              <span className="text-xs font-normal text-slate-400 ml-1.5">
                / {dashboardSummary.attendance?.total_scheduled ?? 0} scheduled
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-slate-500 pt-1 border-t border-slate-100">
              <span className="text-emerald-600 font-semibold">{dashboardSummary.attendance?.present ?? 0} Pres</span>
              <span>•</span>
              <span className="text-amber-600 font-semibold">{dashboardSummary.attendance?.partial ?? 0} Part</span>
              <span>•</span>
              <span className="text-rose-600 font-semibold">{dashboardSummary.attendance?.absent ?? 0} Abs</span>
            </div>
          </Link>

          {/* 2. Live Workforce */}
          <Link
            to="/live"
            className="p-5 bg-white rounded-xl border border-slate-200 shadow-sm hover:border-emerald-300 hover:shadow-md transition group space-y-2"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Live Workforce</span>
              <Radio className="h-4 w-4 text-emerald-500 group-hover:scale-110 transition-transform animate-pulse" />
            </div>
            <div className="text-2xl font-bold text-emerald-600">
              {dashboardSummary.live?.active ?? 0}
              <span className="text-xs font-normal text-slate-400 ml-1.5">
                Active now
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-slate-500 pt-1 border-t border-slate-100">
              <span className="text-amber-600 font-medium">{dashboardSummary.live?.no_recent_signal ?? 0} No Signal</span>
              <span>•</span>
              <span className="text-orange-600 font-medium">{dashboardSummary.live?.location_disabled ?? 0} Disabled</span>
            </div>
          </Link>

          {/* 3. Pending Visits */}
          <Link
            to="/pending-visits"
            className="p-5 bg-white rounded-xl border border-slate-200 shadow-sm hover:border-amber-300 hover:shadow-md transition group space-y-2"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Pending Visits</span>
              <AlertTriangle className="h-4 w-4 text-amber-500 group-hover:scale-110 transition-transform" />
            </div>
            <div className="text-2xl font-bold text-slate-900 flex items-center justify-between">
              <span>{dashboardSummary.pending_visits?.total_open ?? 0}</span>
              {(dashboardSummary.pending_visits?.escalated_count ?? 0) > 0 && (
                <span className="px-2 py-0.5 rounded text-xs font-extrabold bg-red-100 text-red-700 border border-red-200">
                  {dashboardSummary.pending_visits.escalated_count} Escalated
                </span>
              )}
            </div>
            <div className="text-xs text-slate-400 pt-1 border-t border-slate-100">
              Unvisited scheduled work occurrences
            </div>
          </Link>

          {/* 4. Late Arrivals & Overtime */}
          <Link
            to="/attendance"
            className="p-5 bg-white rounded-xl border border-slate-200 shadow-sm hover:border-purple-300 hover:shadow-md transition group space-y-2"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Late Arrivals & OT</span>
              <TrendingUp className="h-4 w-4 text-purple-500 group-hover:scale-110 transition-transform" />
            </div>
            <div className="text-2xl font-bold text-purple-700">
              {dashboardSummary.late_arrivals?.count ?? 0}
              <span className="text-xs font-normal text-slate-400 ml-1.5">
                late arrivals
              </span>
            </div>
            <div className="text-xs text-slate-500 pt-1 border-t border-slate-100">
              Overtime today: <span className="font-semibold text-slate-800">{dashboardSummary.overtime?.total_ot_hours ?? 0} hrs</span>
            </div>
          </Link>
        </div>
      )}

      {/* System Health Tiles */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="p-6 bg-white rounded-xl border border-slate-200 shadow-2xs space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">API Liveness</span>
            <Activity className="h-4 w-4 text-emerald-500" />
          </div>
          <div className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-emerald-500" />
            {loading ? "Checking..." : health?.status?.toUpperCase()}
          </div>
          <p className="text-xs text-slate-500">FastAPI backend responding via /health</p>
        </div>

        <div className="p-6 bg-white rounded-xl border border-slate-200 shadow-2xs space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Deployment Country</span>
            <Server className="h-4 w-4 text-indigo-500" />
          </div>
          <div className="text-2xl font-bold text-indigo-600">
            {loading ? "..." : health?.country}
          </div>
          <p className="text-xs text-slate-500">Country Rule Pack: UAE (Asia/Dubai, AED, Sunday OT2)</p>
        </div>

        <div className="p-6 bg-white rounded-xl border border-slate-200 shadow-2xs space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Database Environment</span>
            <Database className="h-4 w-4 text-purple-500" />
          </div>
          <div className="text-2xl font-bold text-purple-600">
            {loading ? "..." : health?.environment?.toUpperCase()}
          </div>
          <p className="text-xs text-slate-500">PostgreSQL 16 + PostGIS 3.4 active container</p>
        </div>
      </div>

      {/* Active Operational Alerts Section */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-2xs p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-amber-500" />
            <h3 className="text-base font-bold text-slate-900">Active Operational Alerts & Pending Actions</h3>
          </div>
          <span className="text-xs font-medium text-slate-400">
            {coverAlerts.length + (pendingBoundaryCount > 0 ? 1 : 0)} items requiring attention
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Pending Boundaries Alert (Admin / Engineer) */}
          {(user?.role === "ADMIN" || user?.role === "ENGINEER") && pendingBoundaryCount > 0 && (
            <div className="p-4 rounded-lg border border-amber-200 bg-amber-50/70 space-y-2">
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-1.5 text-xs font-bold text-amber-800">
                  <Hexagon className="h-4 w-4 text-amber-600" />
                  Worksite Boundaries Queue
                </span>
                <span className="bg-amber-200 text-amber-900 text-2xs font-extrabold px-2 py-0.5 rounded-full">
                  {pendingBoundaryCount} Pending
                </span>
              </div>
              <p className="text-xs text-amber-900">
                Worksites imported or modified without drawn geofence boundaries. Attendance cannot be verified without geofences.
              </p>
              <Link
                to="/boundaries"
                className="inline-flex items-center gap-1 text-xs font-bold text-amber-900 hover:text-amber-700 pt-1"
              >
                Draw / Review Boundaries <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          )}

          {/* Cover Needed Alerts (Supervisor / Engineer / Admin) */}
          {coverAlerts.map((alert) => (
            <div key={alert.id} className="p-4 rounded-lg border border-rose-200 bg-rose-50/70 space-y-2">
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-1.5 text-xs font-bold text-rose-800">
                  <AlertTriangle className="h-4 w-4 text-rose-600" />
                  {alert.title}
                </span>
                <span className="text-2xs text-rose-700">
                  {new Date(alert.created_at).toLocaleDateString()}
                </span>
              </div>
              <p className="text-xs text-rose-900">{alert.message}</p>
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <Link
                  to="/operational-planner"
                  search={{
                    date: alert.details?.date_from || undefined,
                    employee_id: alert.employee_id || alert.details?.employee_id || undefined,
                  }}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-md text-xs font-semibold shadow-2xs transition"
                >
                  <Users className="h-3.5 w-3.5" />
                  Assign Cover in Planner <ArrowRight className="h-3 w-3" />
                </Link>
                {(user?.role === "ADMIN" || user?.role === "ENGINEER") && (
                  <Link
                    to="/approvals"
                    className="inline-flex items-center gap-1 text-xs font-semibold text-slate-700 hover:text-slate-900 px-2.5 py-1.5"
                  >
                    Approvals Inbox <ArrowRight className="h-3 w-3" />
                  </Link>
                )}
              </div>
            </div>
          ))}

          {coverAlerts.length === 0 && pendingBoundaryCount === 0 && (
            <div className="col-span-2 p-8 text-center text-slate-400 space-y-1 bg-slate-50/60 rounded-lg border border-dashed border-slate-200">
              <CheckCircle2 className="h-8 w-8 text-emerald-500 mx-auto" />
              <div className="text-sm font-semibold text-slate-700">All Operations Clear</div>
              <p className="text-xs text-slate-400">No active leave cover shortages or pending geofence boundaries.</p>
            </div>
          )}
        </div>
      </div>

      {/* Admin & Engineer: Pending Approvals Queue */}
      {(user?.role === "ADMIN" || user?.role === "ENGINEER") && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-2xs p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckSquare className="h-5 w-5 text-indigo-600" />
              <div>
                <h3 className="text-base font-bold text-slate-900">Pending Approvals Queue</h3>
                <p className="text-xs text-slate-500">
                  Requests submitted by supervisors and workers awaiting your review and authorization.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="bg-indigo-50 text-indigo-700 text-xs font-bold px-2.5 py-1 rounded-full border border-indigo-200">
                {pendingLeaves.length + pendingReassigns.length} Decisions Pending
              </span>
              <Link
                to="/approvals"
                className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800 px-3 py-1.5 rounded-lg hover:bg-indigo-50 transition"
              >
                Open Full Inbox <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          </div>

          {pendingLeaves.length === 0 && pendingReassigns.length === 0 ? (
            <div className="p-8 text-center text-slate-400 space-y-1 bg-slate-50/60 rounded-lg border border-dashed border-slate-200">
              <CheckCircle2 className="h-7 w-7 text-emerald-500 mx-auto" />
              <div className="text-xs font-semibold text-slate-700">Inbox Clean</div>
              <p className="text-2xs text-slate-400">All submitted leaves and temporary reassignments have been decided.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Pending Leaves List */}
              <div className="border border-slate-200 rounded-lg p-4 bg-slate-50/50 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                    <Calendar className="h-4 w-4 text-blue-600" />
                    Leave Requests ({pendingLeaves.length})
                  </span>
                  <Link to="/approvals" className="text-2xs text-indigo-600 font-semibold hover:underline">
                    Manage
                  </Link>
                </div>
                {pendingLeaves.length === 0 ? (
                  <p className="text-2xs text-slate-400 italic">No pending leave requests.</p>
                ) : (
                  <div className="space-y-2">
                    {pendingLeaves.slice(0, 4).map((l: any) => (
                      <div key={l.id} className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs flex items-center justify-between text-xs">
                        <div className="space-y-0.5">
                          <div className="font-semibold text-slate-900">{l.employee_name || l.employee_id}</div>
                          <div className="text-2xs text-slate-500">
                            {l.from_date} to {l.to_date} · <span className="font-medium text-blue-700">{l.leave_type}</span>
                          </div>
                          <div className="text-2xs text-slate-400 truncate max-w-xs">{l.reason}</div>
                        </div>
                        <Link
                          to="/approvals"
                          className="px-2.5 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded text-2xs font-bold border border-indigo-200 transition shrink-0"
                        >
                          Review
                        </Link>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Pending Reassignments List */}
              <div className="border border-slate-200 rounded-lg p-4 bg-slate-50/50 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                    <Clock className="h-4 w-4 text-purple-600" />
                    Reassignment Requests ({pendingReassigns.length})
                  </span>
                  <Link to="/approvals" className="text-2xs text-indigo-600 font-semibold hover:underline">
                    Manage
                  </Link>
                </div>
                {pendingReassigns.length === 0 ? (
                  <p className="text-2xs text-slate-400 italic">No pending temporary reassignments.</p>
                ) : (
                  <div className="space-y-2">
                    {pendingReassigns.slice(0, 4).map((r: any) => (
                      <div key={r.id} className="p-3 bg-white rounded-lg border border-slate-200 shadow-2xs flex items-center justify-between text-xs">
                        <div className="space-y-0.5">
                          <div className="font-semibold text-slate-900 flex items-center gap-1.5">
                            <span className="px-1.5 py-0.5 bg-purple-50 text-purple-700 border border-purple-200 rounded text-2xs font-bold">
                              {r.reassignment_type}
                            </span>
                            {r.reassignment_type === "REPLACE" ? (
                              <span>
                                {r.original_employee_name} → <span className="text-emerald-700 font-bold">{r.new_employee_name}</span>
                              </span>
                            ) : (
                              <span>{r.new_employee_name || r.original_employee_name}</span>
                            )}
                          </div>
                          <div className="text-2xs text-slate-500">
                            {r.date_from === r.date_to ? r.date_from : `${r.date_from} to ${r.date_to}`} · {r.target_job_name || r.target_job_number || "Job"}
                          </div>
                          <div className="text-2xs text-slate-400 truncate max-w-xs">{r.reason}</div>
                        </div>
                        <Link
                          to="/approvals"
                          className="px-2.5 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded text-2xs font-bold border border-indigo-200 transition shrink-0"
                        >
                          Review
                        </Link>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Supervisor: My Submitted Requests & Decision Status */}
      {user?.role === "SUPERVISOR" && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-2xs p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Clock className="h-5 w-5 text-indigo-600" />
              <div>
                <h3 className="text-base font-bold text-slate-900">My Requests & Decision Status</h3>
                <p className="text-xs text-slate-500">
                  Track operational reassignments and team absences submitted for authorization.
                </p>
              </div>
            </div>
            <Link
              to="/operational-planner"
              className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-800 px-3 py-1.5 rounded-lg hover:bg-indigo-50 transition"
            >
              Open Planner <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          {myRequests.length === 0 ? (
            <div className="p-8 text-center text-slate-400 space-y-1 bg-slate-50/60 rounded-lg border border-dashed border-slate-200">
              <CheckCircle2 className="h-7 w-7 text-slate-300 mx-auto" />
              <div className="text-xs font-semibold text-slate-700">No Active Requests</div>
              <p className="text-2xs text-slate-400">You haven't submitted any leave or reassignment requests recently.</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100 border border-slate-200 rounded-lg overflow-hidden">
              {myRequests.map((req: any) => {
                const isReassign = req.category_kind === "REASSIGNMENT";
                const isApproved = req.status === "APPROVED";
                const isRejected = req.status === "REJECTED";
                const isPending = req.status === "PENDING" || req.status === "REQUESTED";

                return (
                  <div key={req.id} className="p-3.5 bg-white hover:bg-slate-50/60 flex items-center justify-between text-xs transition">
                    <div className="space-y-1 max-w-xl">
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 rounded text-2xs font-bold ${
                          isReassign ? "bg-purple-50 text-purple-700 border border-purple-200" : "bg-blue-50 text-blue-700 border border-blue-200"
                        }`}>
                          {isReassign ? `REASSIGN: ${req.reassignment_type}` : `LEAVE: ${req.leave_type}`}
                        </span>
                        <span className="font-semibold text-slate-900">
                          {isReassign
                            ? req.reassignment_type === "REPLACE"
                              ? `${req.original_employee_name} → ${req.new_employee_name}`
                              : req.new_employee_name || req.original_employee_name
                            : req.employee_name || req.employee_id}
                        </span>
                      </div>
                      <div className="text-2xs text-slate-500">
                        Dates: {req.date_from || req.from_date} to {req.date_to || req.to_date}
                        {req.target_job_name && ` · Target: ${req.target_job_name}`}
                      </div>
                      {req.reason && <div className="text-2xs text-slate-400 truncate">Reason: {req.reason}</div>}
                      {/* Decision Details */}
                      {(isApproved || isRejected) && (
                        <div className="text-2xs font-medium text-slate-600 flex items-center gap-1.5 pt-0.5">
                          {isApproved ? (
                            <span className="text-emerald-700">✓ Authorized by {req.decided_by_name || req.approved_by_name || "Engineer"}</span>
                          ) : (
                            <span className="text-rose-700">✕ Rejected by {req.decided_by_name || req.approved_by_name || "Engineer"}</span>
                          )}
                          {(req.decision_note || req.decision_reason) && (
                            <span className="text-slate-400">— Note: "{req.decision_note || req.decision_reason}"</span>
                          )}
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-2.5 shrink-0">
                      <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${
                        isPending ? "bg-amber-100 text-amber-800" :
                        isApproved ? "bg-emerald-100 text-emerald-800" :
                        isRejected ? "bg-rose-100 text-rose-800" :
                        "bg-slate-100 text-slate-600"
                      }`}>
                        {isPending ? "PENDING REVIEW" : req.status}
                      </span>
                      {isApproved && isReassign && (
                        <Link
                          to="/operational-planner"
                          search={{ date: req.date_from, job_item_id: req.target_job_item_id, lens: "COVERAGE" }}
                          className="px-2.5 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded text-xs font-semibold border border-indigo-200 transition shadow-2xs"
                        >
                          View in Planner
                        </Link>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
