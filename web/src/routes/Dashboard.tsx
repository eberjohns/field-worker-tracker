import React, { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import {
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
  FileText,
  Smartphone,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { mapDashboardSummary, type DashboardSummaryApi } from "../features/dashboard/summary";
import { ActionSection, type ActionRow } from "../features/dashboard/ActionSection";
import {
  ACTION_SECTIONS,
  DEVICE_ALERT_TYPES,
  PREVIEW_SIZE,
  newest,
  sectionsForRole,
  type ActionSectionKey,
} from "../features/dashboard/actionSections";

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
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [dashboardSummary, setDashboardSummary] = useState<DashboardSummaryApi | null>(null);
  const [boundaryQueue, setBoundaryQueue] = useState<{ count: number; items: any[] }>({ count: 0, items: [] });
  const [approvalCounts, setApprovalCounts] = useState<{ leave: number; reassignments: number; attendance: number }>({
    leave: 0,
    reassignments: 0,
    attendance: 0,
  });
  const [pendingLeaves, setPendingLeaves] = useState<any[]>([]);
  const [pendingReassigns, setPendingReassigns] = useState<any[]>([]);
  const [attendanceRows, setAttendanceRows] = useState<any[]>([]);
  const [visits, setVisits] = useState<{ count: number; items: any[] }>({ count: 0, items: [] });
  const [unassignedList, setUnassignedList] = useState<any[]>([]);
  const [myRequests, setMyRequests] = useState<any[]>([]);

  const sections = new Set(sectionsForRole(user?.role));

  useEffect(() => {
    if (!token) return;
    const load = async () => {
      const headers = { Authorization: `Bearer ${token}` };
      const getJson = async (url: string) => {
        try {
          const res = await fetch(url, { headers });
          return res.ok ? await res.json() : null;
        } catch (err) {
          console.error(`Failed to load ${url}`, err);
          return null;
        }
      };
      const has = (k: Parameters<typeof sections.has>[0]) => sections.has(k);
      const isSupervisor = user?.role === "SUPERVISOR";
      const n = PREVIEW_SIZE;
      // All dashboard calls start together (Batch 9 step 2); none depends on another.
      const [alertData, sumData, bData, leavePage, reassignPage, attPage, visitPage, unassigned, reassignList, leaveList] =
        await Promise.all([
          getJson("/api/v1/alerts"),
          getJson("/api/v1/dashboard/summary"),
          has("boundary") ? getJson(`/api/v1/boundary-queue?status=UNSET&limit=${n}`) : null,
          // Previews: 5 items each; the counts come with the first page.
          has("leave") ? getJson(`/api/v1/approvals?status=PENDING&type=leave&limit=${n}`) : null,
          has("reassignment") ? getJson(`/api/v1/approvals?status=PENDING&type=reassignments&limit=${n}`) : null,
          has("attendance") ? getJson(`/api/v1/approvals?status=PENDING&type=attendance&limit=${n}`) : null,
          has("pendingVisits") ? getJson(`/api/v1/pending-visits?status=OPEN&limit=${n}`) : null,
          has("unassigned") ? getJson(`/api/v1/worksites?unassigned=true&limit=${n}`) : null,
          isSupervisor ? getJson("/api/v1/reassignment-requests") : null,
          isSupervisor ? getJson("/api/v1/leave-requests") : null,
        ]);

      setAlerts(alertData || []);
      if (sumData) setDashboardSummary(sumData);
      if (bData) setBoundaryQueue({ count: bData.unset_count ?? bData.total_count ?? 0, items: bData.items || [] });
      const counts = leavePage?.counts ?? reassignPage?.counts ?? attPage?.counts;
      if (counts) setApprovalCounts({ leave: counts.leave, reassignments: counts.reassignments, attendance: counts.attendance });
      if (leavePage) setPendingLeaves(leavePage.leave_requests || []);
      if (reassignPage) setPendingReassigns(reassignPage.reassignment_requests || []);
      if (attPage) setAttendanceRows(attPage.attendance_rows || []);
      if (visitPage) setVisits({ count: visitPage.open_count ?? 0, items: visitPage.items || [] });
      if (unassigned) setUnassignedList(unassigned);
      if (isSupervisor) {
        const combined: any[] = [
          ...(reassignList || []).map((item: any) => ({ ...item, category_kind: "REASSIGNMENT" })),
          ...(leaveList || []).map((item: any) => ({ ...item, category_kind: "LEAVE" })),
        ];
        combined.sort(
          (a, b) =>
            new Date(b.created_at || b.recorded_at || 0).getTime() -
            new Date(a.created_at || a.recorded_at || 0).getTime()
        );
        setMyRequests(combined.slice(0, 10));
      }
    };
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, user]);

  const coverAlerts = alerts.filter((a) => a.alert_type === "COVER_NEEDED");
  const docExpiryAlerts = alerts.filter((a) => a.alert_type === "DOC_EXPIRY");
  const deviceAlerts = alerts.filter((a) => DEVICE_ALERT_TYPES.has(a.alert_type));
  // DEC-57: Admin-only count of worksites nobody but Admin can see.
  const cards = mapDashboardSummary(dashboardSummary);
  const unassignedWorksites = cards.unassignedWorksites;

  const alertRows = (list: AlertItem[]): ActionRow[] =>
    newest(list).map((a) => ({
      id: a.id,
      primary: a.title,
      secondary: a.message,
      meta: new Date(a.created_at).toLocaleDateString(),
    }));

  const icon = (I: React.ComponentType<{ className?: string }>, cls: string) => <I className={`h-4 w-4 ${cls}`} />;

  const sectionNodes: Record<ActionSectionKey, React.ReactNode> = {
    docExpiry: (
      <ActionSection
        title="Document expiry"
        icon={icon(FileText, "text-amber-600")}
        count={docExpiryAlerts.length}
        rows={newest(docExpiryAlerts).map((a) => {
          const daysLeft = Number(a.details?.days_left ?? 0);
          return {
            id: a.id,
            primary: a.title,
            secondary: `Expiry: ${a.details?.expiry_date || "N/A"}`,
            meta: (
              <span className={daysLeft < 0 ? "font-bold text-rose-700" : "font-semibold text-amber-700"}>
                {daysLeft < 0 ? `Expired ${Math.abs(daysLeft)}d ago` : `${daysLeft}d left`}
              </span>
            ),
          };
        })}
        viewAll={{ to: "/documents" }}
        emptyText="No documents expiring soon."
      />
    ),
    cover: (
      <ActionSection
        title="Cover needed"
        tone="rose"
        icon={icon(Users, "text-rose-600")}
        count={coverAlerts.length}
        rows={alertRows(coverAlerts)}
        viewAll={{ to: "/operational-planner", hash: "staffing-gaps" }}
        emptyText="No leave shifts need cover."
      />
    ),
    leave: (
      <ActionSection
        title="Leave approval"
        tone="indigo"
        icon={icon(Calendar, "text-blue-600")}
        count={approvalCounts.leave}
        rows={pendingLeaves.map((l: any) => ({
          id: l.id,
          primary: l.employee_name || l.employee_id,
          secondary: `${l.from_date} to ${l.to_date} · ${l.leave_type}`,
        }))}
        viewAll={{ to: "/approvals", search: { tab: "leave" } }}
        emptyText="No leave requests waiting."
      />
    ),
    reassignment: (
      <ActionSection
        title="Reassignment approval"
        tone="indigo"
        icon={icon(Clock, "text-purple-600")}
        count={approvalCounts.reassignments}
        rows={pendingReassigns.map((r: any) => ({
          id: r.id,
          primary:
            r.reassignment_type === "REPLACE"
              ? `${r.original_employee_name} → ${r.new_employee_name}`
              : r.new_employee_name || r.original_employee_name,
          secondary: `${r.date_from === r.date_to ? r.date_from : `${r.date_from} to ${r.date_to}`} · ${
            r.target_job_name || r.target_job_number || "Job"
          }`,
          meta: r.reassignment_type,
        }))}
        viewAll={{ to: "/approvals", search: { tab: "reassignments" } }}
        emptyText="No reassignments waiting."
      />
    ),
    attendance: (
      <ActionSection
        title="Attendance review"
        tone="indigo"
        icon={icon(CheckSquare, "text-indigo-600")}
        count={approvalCounts.attendance}
        rows={attendanceRows.map((r: any) => ({
          id: r.id,
          primary: r.employee_name || r.employee_id,
          secondary: `${r.work_date} · ${(r.review_reasons || []).join(", ") || r.business_status}`,
        }))}
        viewAll={{ to: "/approvals", search: { tab: "attendance" } }}
        emptyText="No attendance waiting for review."
      />
    ),
    pendingVisits: (
      <ActionSection
        title="Pending visits"
        icon={icon(AlertTriangle, "text-amber-600")}
        count={visits.count}
        rows={visits.items.map((v: any) => ({
          id: v.id,
          primary: `${v.job_number || ""} ${v.worksite_name}`.trim(),
          secondary: `${v.due_date} · ${v.employee_name}`,
          meta: v.is_escalated ? <span className="font-bold text-rose-700">Escalated</span> : `${v.age_days}d`,
        }))}
        viewAll={{ to: "/pending-visits" }}
        emptyText="No open pending visits."
      />
    ),
    boundary: (
      <ActionSection
        title="Boundary queue"
        icon={icon(Hexagon, "text-amber-600")}
        count={boundaryQueue.count}
        rows={boundaryQueue.items.map((b: any) => ({
          id: b.id,
          primary: `${b.code} ${b.name}`,
          secondary: b.entity_type === "ACCOMMODATION" ? "Accommodation" : b.zone_name || "Worksite",
        }))}
        viewAll={{ to: "/boundaries" }}
        emptyText="Every worksite and accommodation has a boundary."
      />
    ),
    unassigned: (
      <ActionSection
        title="Unassigned worksites"
        icon={icon(ShieldAlert, "text-amber-600")}
        count={unassignedWorksites}
        rows={unassignedList.map((w: any) => ({ id: w.id, primary: `${w.job_number} ${w.job_name}` }))}
        viewAll={{ to: "/worksites" }}
        emptyText="Every worksite has a supervisor."
      />
    ),
    device: (
      <ActionSection
        title="Device & tracking alerts"
        tone="rose"
        icon={icon(Smartphone, "text-rose-600")}
        count={deviceAlerts.length}
        rows={alertRows(deviceAlerts)}
        viewAll={{ to: "/devices" }}
        emptyText="No device or tracking alerts."
      />
    ),
  };
  const visible = ACTION_SECTIONS.filter((x) => sections.has(x.key));

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">Operations & Health Overview</h2>
        <p className="text-sm text-slate-500 mt-1">
          Real-time field operations status, pending coverage alerts, and workforce requests.
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
              {cards.attendance.present}
              <span className="text-xs font-normal text-slate-400 ml-1.5">
                / {cards.attendance.totalScheduled} scheduled
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-slate-500 pt-1 border-t border-slate-100">
              <span className="text-emerald-600 font-semibold">{cards.attendance.present} Pres</span>
              <span>•</span>
              <span className="text-amber-600 font-semibold">{cards.attendance.partial} Part</span>
              <span>•</span>
              <span className="text-rose-600 font-semibold">{cards.attendance.absent} Abs</span>
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
              {cards.live.active}
              <span className="text-xs font-normal text-slate-400 ml-1.5">
                Active now
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-slate-500 pt-1 border-t border-slate-100">
              <span className="text-amber-600 font-medium">{cards.live.noRecentSignal} No Signal</span>
              <span>•</span>
              <span className="text-orange-600 font-medium">{cards.live.locationDisabled} Disabled</span>
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
              <span>{cards.pendingVisits.open}</span>
              {cards.pendingVisits.escalated > 0 && (
                <span className="px-2 py-0.5 rounded text-xs font-extrabold bg-red-100 text-red-700 border border-red-200">
                  {cards.pendingVisits.escalated} Escalated
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
              {cards.lateArrivals}
              <span className="text-xs font-normal text-slate-400 ml-1.5">
                late arrivals
              </span>
            </div>
            <div className="text-xs text-slate-500 pt-1 border-t border-slate-100">
              Overtime today: <span className="font-semibold text-slate-800">{cards.overtimeHours} hrs</span>
            </div>
          </Link>
        </div>
      )}

      {/* Pending actions & alerts, grouped by type (Batch 10 B) */}
      {visible.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-amber-500" />
            <h3 className="text-base font-bold text-slate-900">Pending Actions & Alerts</h3>
          </div>
          <div className="grid grid-cols-1 items-start gap-4 md:grid-cols-2 xl:grid-cols-3">
            {visible.map((x) => (
              <React.Fragment key={x.key}>{sectionNodes[x.key]}</React.Fragment>
            ))}
          </div>
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
