import React, { useState, useEffect } from "react";
import { Link } from "@tanstack/react-router";
import {
  CheckSquare,
  Clock,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  RefreshCw,
  ArrowRight,
  AlertCircle,
  Calendar,
  Users,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

interface LeaveRequestItem {
  id: string;
  employee_id: string;
  employee_name: string;
  tally_id: string;
  leave_type: string;
  from_date: string;
  to_date: string;
  working_days: number;
  calendar_days: number;
  reason: string;
  status: string;
  recorded_by_name: string | null;
  recorded_at: string;
  approved_by_name: string | null;
  approved_at: string | null;
  decision_note: string | null;
}

interface ReassignmentItem {
  id: string;
  reassignment_type: string;
  date_from: string;
  date_to: string;
  original_employee_id: string | null;
  original_employee_name: string | null;
  new_employee_id: string | null;
  new_employee_name: string | null;
  target_job_item_id: string | null;
  target_job_number: string | null;
  target_job_name: string | null;
  hours_per_day: number | null;
  reason_category: string;
  reason: string;
  status: string;
  is_late_approval: boolean;
  is_orphaned: boolean;
  requested_by_name: string | null;
  requested_at?: string;
  created_at?: string;
  decided_by_name: string | null;
  decided_at: string | null;
  decision_note: string | null;
}

interface ApprovalsCounts {
  leaves: number;
  reassignments: number;
  attendance: number;
  total: number;
}

export const Approvals: React.FC = () => {
  const { token, user } = useAuth();
  const [activeTab, setActiveTab] = useState<"leave" | "reassignments" | "attendance">("leave");
  const [counts, setCounts] = useState<ApprovalsCounts>({ leaves: 0, reassignments: 0, attendance: 0, total: 0 });
  const [leaves, setLeaves] = useState<LeaveRequestItem[]>([]);
  const [reassignments, setReassignments] = useState<ReassignmentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("PENDING");

  // Decision Modal State
  const [decisionModal, setDecisionModal] = useState<{
    open: boolean;
    type: "LEAVE" | "REASSIGNMENT";
    action: "APPROVE" | "REJECT";
    item: any | null;
    note: string;
    submitting: boolean;
    error: string | null;
  }>({
    open: false,
    type: "LEAVE",
    action: "APPROVE",
    item: null,
    note: "",
    submitting: false,
    error: null,
  });

  const fetchInbox = async () => {
    setLoading(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const statusParam = statusFilter === "ALL" ? "" : `?status=${statusFilter}`;
      const res = await fetch(`/api/v1/approvals${statusParam}`, { headers });
      if (res.ok) {
        const data = await res.json();
        setCounts(data.counts || { leaves: 0, reassignments: 0, attendance: 0, total: 0 });
        setLeaves(data.leave_requests || []);
        setReassignments(data.reassignment_requests || []);
      }
    } catch (err) {
      console.error("Failed to load approvals inbox", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInbox();
  }, [token, statusFilter]);

  const handleOpenDecision = (type: "LEAVE" | "REASSIGNMENT", action: "APPROVE" | "REJECT", item: any) => {
    setDecisionModal({
      open: true,
      type,
      action,
      item,
      note: "",
      submitting: false,
      error: null,
    });
  };

  const handleConfirmDecision = async () => {
    if (decisionModal.action === "REJECT" && !decisionModal.note.trim()) {
      setDecisionModal((prev) => ({ ...prev, error: "A rejection reason is mandatory." }));
      return;
    }

    setDecisionModal((prev) => ({ ...prev, submitting: true, error: null }));
    try {
      const headers = {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      };

      let url = "";
      let body: any = {};

      if (decisionModal.type === "LEAVE") {
        const actionPath = decisionModal.action === "APPROVE" ? "approve" : "reject";
        url = `/api/v1/leave-requests/${decisionModal.item.id}/${actionPath}`;
        body = { reason: decisionModal.note.trim() };
      } else {
        const actionPath = decisionModal.action === "APPROVE" ? "approve" : "reject";
        url = `/api/v1/reassignment-requests/${decisionModal.item.id}/${actionPath}`;
        body = { decision_note: decisionModal.note.trim() };
      }

      const res = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const errData = await res.json();
        const msg = errData?.detail?.message || errData?.detail || "Action failed";
        setDecisionModal((prev) => ({ ...prev, submitting: false, error: String(msg) }));
        return;
      }

      setDecisionModal((prev) => ({ ...prev, open: false, submitting: false }));
      await fetchInbox();
    } catch (err: any) {
      setDecisionModal((prev) => ({ ...prev, submitting: false, error: err.message || "Network error" }));
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <CheckSquare className="h-6 w-6 text-indigo-600" />
            Approvals Inbox
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Review and decide leave requests and temporary operational reassignments for your reporting scope.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-lg">
            <button
              onClick={() => setStatusFilter("PENDING")}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition cursor-pointer ${
                statusFilter === "PENDING"
                  ? "bg-white text-indigo-700 shadow-2xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Pending ({counts.total})
            </button>
            <button
              onClick={() => setStatusFilter("APPROVED")}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition cursor-pointer ${
                statusFilter === "APPROVED"
                  ? "bg-white text-emerald-700 shadow-2xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              Approved History
            </button>
            <button
              onClick={() => setStatusFilter("ALL")}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition cursor-pointer ${
                statusFilter === "ALL"
                  ? "bg-white text-slate-900 shadow-2xs"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              All History
            </button>
          </div>
          <button
            onClick={fetchInbox}
            disabled={loading}
            className="p-2 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg border border-slate-200 transition"
            title="Refresh"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-200 flex gap-6">
        <button
          onClick={() => setActiveTab("leave")}
          className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition ${
            activeTab === "leave"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Calendar className="h-4 w-4" />
          Leave Requests
          {counts.leaves > 0 && (
            <span className="bg-amber-100 text-amber-800 text-xs font-bold px-2 py-0.5 rounded-full">
              {counts.leaves}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab("reassignments")}
          className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition ${
            activeTab === "reassignments"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Clock className="h-4 w-4" />
          Reassignment Requests
          {counts.reassignments > 0 && (
            <span className="bg-amber-100 text-amber-800 text-xs font-bold px-2 py-0.5 rounded-full">
              {counts.reassignments}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab("attendance")}
          className={`pb-3 text-sm font-semibold flex items-center gap-2 border-b-2 transition ${
            activeTab === "attendance"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <AlertCircle className="h-4 w-4" />
          Attendance Exceptions
          <span className="bg-slate-100 text-slate-500 text-xs px-2 py-0.5 rounded-full">
            Phase 08
          </span>
        </button>
      </div>

      {/* Tab Content: Leave Requests */}
      {activeTab === "leave" && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-slate-500 flex items-center justify-center gap-2">
              <RefreshCw className="h-5 w-5 animate-spin" />
              Loading leave requests...
            </div>
          ) : leaves.length === 0 ? (
            <div className="p-12 text-center text-slate-400 space-y-2">
              <CheckCircle2 className="h-10 w-10 text-emerald-500 mx-auto" />
              <div className="text-base font-semibold text-slate-700">No leave requests to review</div>
              <p className="text-xs text-slate-400">All scoped leave requests have been decided.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                <thead className="bg-slate-50 text-xs font-semibold text-slate-600 uppercase">
                  <tr>
                    <th className="py-3 px-4">Worker</th>
                    <th className="py-3 px-4">Leave Type</th>
                    <th className="py-3 px-4">Dates & Duration</th>
                    <th className="py-3 px-4">Reason</th>
                    <th className="py-3 px-4">Recorded By</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {leaves.map((l) => {
                    const isPending = l.status === "REQUESTED";
                    return (
                      <tr key={l.id} className="hover:bg-slate-50/80 transition">
                        <td className="py-3.5 px-4">
                          <div className="font-medium text-slate-900">{l.employee_name}</div>
                          <div className="text-xs text-slate-400">Tally ID: {l.tally_id}</div>
                        </td>
                        <td className="py-3.5 px-4">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                            l.leave_type === "ANNUAL" ? "bg-blue-50 text-blue-700 border border-blue-200" :
                            l.leave_type === "SICK" ? "bg-rose-50 text-rose-700 border border-rose-200" :
                            l.leave_type === "EMERGENCY" ? "bg-amber-50 text-amber-700 border border-amber-200" :
                            "bg-slate-100 text-slate-700"
                          }`}>
                            {l.leave_type}
                          </span>
                        </td>
                        <td className="py-3.5 px-4">
                          <div className="text-slate-800 font-medium">{l.from_date} to {l.to_date}</div>
                          <div className="text-xs text-slate-500">
                            {l.working_days} working {l.working_days === 1 ? "day" : "days"} ({l.calendar_days} cal)
                          </div>
                        </td>
                        <td className="py-3.5 px-4 text-slate-600 max-w-xs truncate" title={l.reason}>
                          {l.reason}
                        </td>
                        <td className="py-3.5 px-4 text-xs text-slate-500">
                          <div>{l.recorded_by_name || "Unknown"}</div>
                          <div className="text-slate-400">{new Date(l.recorded_at).toLocaleDateString()}</div>
                        </td>
                        <td className="py-3.5 px-4">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${
                            l.status === "REQUESTED" ? "bg-amber-100 text-amber-800" :
                            l.status === "APPROVED" ? "bg-emerald-100 text-emerald-800" :
                            l.status === "REJECTED" ? "bg-rose-100 text-rose-800" :
                            "bg-slate-100 text-slate-600"
                          }`}>
                            {l.status}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          {isPending && (user?.role === "ADMIN" || user?.role === "ENGINEER") ? (
                            <div className="flex items-center justify-end gap-2">
                              <button
                                onClick={() => handleOpenDecision("LEAVE", "APPROVE", l)}
                                className="px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-md text-xs font-medium transition shadow-2xs"
                              >
                                Approve
                              </button>
                              <button
                                onClick={() => handleOpenDecision("LEAVE", "REJECT", l)}
                                className="px-3 py-1 bg-white hover:bg-rose-50 text-rose-700 border border-rose-300 rounded-md text-xs font-medium transition"
                              >
                                Reject
                              </button>
                            </div>
                          ) : l.status === "APPROVED" ? (
                            <div className="flex items-center justify-end gap-2">
                              <Link
                                to="/operational-planner"
                                search={{ date: l.from_date, employee_id: l.employee_id }}
                                className="px-2.5 py-1 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-md transition flex items-center gap-1 shadow-2xs"
                                title="Open Operational Planner to arrange a cover replacement"
                              >
                                <Users className="h-3 w-3" />
                                Arrange Cover
                              </Link>
                            </div>
                          ) : (
                            <span className="text-xs text-slate-400">
                              {l.approved_by_name ? `Decided by ${l.approved_by_name}` : "—"}
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab Content: Reassignment Requests */}
      {activeTab === "reassignments" && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-slate-500 flex items-center justify-center gap-2">
              <RefreshCw className="h-5 w-5 animate-spin" />
              Loading reassignment requests...
            </div>
          ) : reassignments.length === 0 ? (
            <div className="p-12 text-center text-slate-400 space-y-2">
              <CheckCircle2 className="h-10 w-10 text-emerald-500 mx-auto" />
              <div className="text-base font-semibold text-slate-700">No reassignments to review</div>
              <p className="text-xs text-slate-400">All temporary coverage requests have been decided.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                <thead className="bg-slate-50 text-xs font-semibold text-slate-600 uppercase">
                  <tr>
                    <th className="py-3 px-4">Type</th>
                    <th className="py-3 px-4">Workers</th>
                    <th className="py-3 px-4">Target Job / Site</th>
                    <th className="py-3 px-4">Dates</th>
                    <th className="py-3 px-4">Requested By</th>
                    <th className="py-3 px-4">Reason</th>
                    <th className="py-3 px-4">Notice Status</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {reassignments.map((r) => {
                    const isPending = r.status === "PENDING";
                    return (
                      <tr key={r.id} className="hover:bg-slate-50/80 transition">
                        <td className="py-3.5 px-4">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-bold ${
                            r.reassignment_type === "REPLACE" ? "bg-indigo-50 text-indigo-700 border border-indigo-200" :
                            r.reassignment_type === "ADD" ? "bg-emerald-50 text-emerald-700 border border-emerald-200" :
                            r.reassignment_type === "MOVE" ? "bg-purple-50 text-purple-700 border border-purple-200" :
                            "bg-rose-50 text-rose-700 border border-rose-200"
                          }`}>
                            {r.reassignment_type}
                          </span>
                        </td>
                        <td className="py-3.5 px-4">
                          {r.reassignment_type === "REPLACE" && (
                            <div className="flex items-center gap-1.5 text-xs">
                              <span className="font-medium text-slate-800">{r.original_employee_name}</span>
                              <ArrowRight className="h-3 w-3 text-slate-400" />
                              <span className="font-bold text-emerald-700">{r.new_employee_name}</span>
                            </div>
                          )}
                          {r.reassignment_type === "ADD" && (
                            <div className="font-bold text-emerald-700 text-xs">{r.new_employee_name}</div>
                          )}
                          {r.reassignment_type === "MOVE" && (
                            <div className="font-medium text-slate-800 text-xs">{r.original_employee_name}</div>
                          )}
                          {r.reassignment_type === "CANCEL" && (
                            <div className="font-medium text-rose-800 text-xs">{r.original_employee_name}</div>
                          )}
                        </td>
                        <td className="py-3.5 px-4">
                          <div className="font-medium text-slate-800 text-xs">{r.target_job_name || "—"}</div>
                          <div className="text-2xs text-slate-400">{r.target_job_number}</div>
                        </td>
                        <td className="py-3.5 px-4 text-xs font-medium text-slate-800">
                          {r.date_from === r.date_to ? r.date_from : `${r.date_from} to ${r.date_to}`}
                        </td>
                        <td className="py-3.5 px-4 text-xs text-slate-500">
                          <div className="font-medium text-slate-800">{r.requested_by_name || "Supervisor"}</div>
                          <div className="text-2xs text-slate-400">
                            {new Date(r.created_at || r.requested_at || Date.now()).toLocaleDateString()}
                          </div>
                        </td>
                        <td className="py-3.5 px-4 text-xs text-slate-600 max-w-xs truncate" title={r.reason}>
                          <span className="font-medium text-slate-700">[{r.reason_category}]</span> {r.reason}
                        </td>
                        <td className="py-3.5 px-4">
                          {r.is_late_approval ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-2xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">
                              <AlertTriangle className="h-3 w-3 text-amber-600" />
                              LATE_APPROVAL
                            </span>
                          ) : (
                            <span className="text-2xs text-emerald-600 font-medium">Standard Notice</span>
                          )}
                        </td>
                        <td className="py-3.5 px-4">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${
                            r.status === "PENDING" ? "bg-amber-100 text-amber-800" :
                            r.status === "APPROVED" ? "bg-emerald-100 text-emerald-800" :
                            r.status === "REJECTED" ? "bg-rose-100 text-rose-800" :
                            r.status === "EXPIRED" ? "bg-slate-200 text-slate-700" :
                            "bg-slate-100 text-slate-600"
                          }`}>
                            {r.status}
                          </span>
                          {r.decided_by_name && (
                            <div className="text-2xs text-slate-500 pt-0.5">
                              by {r.decided_by_name}
                              {r.decision_note && <div className="text-slate-400 italic">"{r.decision_note}"</div>}
                            </div>
                          )}
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          {isPending && (user?.role === "ADMIN" || user?.role === "ENGINEER") ? (
                            <div className="flex items-center justify-end gap-2">
                              <button
                                onClick={() => handleOpenDecision("REASSIGNMENT", "APPROVE", r)}
                                className="px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-md text-xs font-medium transition shadow-2xs cursor-pointer"
                              >
                                Approve
                              </button>
                              <button
                                onClick={() => handleOpenDecision("REASSIGNMENT", "REJECT", r)}
                                className="px-3 py-1 bg-white hover:bg-rose-50 text-rose-700 border border-rose-300 rounded-md text-xs font-medium transition cursor-pointer"
                              >
                                Reject
                              </button>
                            </div>
                          ) : r.status === "APPROVED" ? (
                            <div className="flex items-center justify-end">
                              <Link
                                to="/operational-planner"
                                search={{
                                  date: r.date_from,
                                  job_item_id: r.target_job_item_id || undefined,
                                  lens: "COVERAGE",
                                }}
                                className="px-2.5 py-1 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-md transition flex items-center gap-1 shadow-2xs"
                                title="Open Operational Planner to view this reassignment"
                              >
                                <Users className="h-3 w-3" />
                                View in Planner
                              </Link>
                            </div>
                          ) : (
                            <span className="text-xs text-slate-400">
                              {r.decided_by_name ? `Decided by ${r.decided_by_name}` : "—"}
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab Content: Attendance Placeholder */}
      {activeTab === "attendance" && (
        <div className="p-12 text-center bg-white rounded-xl border border-slate-200 shadow-xs space-y-3">
          <Clock className="h-10 w-10 text-indigo-400 mx-auto" />
          <h3 className="text-base font-semibold text-slate-800">Attendance Review & Dispute Approvals</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Reviewing manual punches, site exit disputes, and attendance approvals will be delivered in Phase 08 (Daily Attendance Calculation & Review).
          </p>
        </div>
      )}

      {/* Decision Modal */}
      {decisionModal.open && decisionModal.item && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4 border border-slate-100">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                {decisionModal.action === "APPROVE" ? (
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                ) : (
                  <XCircle className="h-5 w-5 text-rose-600" />
                )}
                {decisionModal.action === "APPROVE" ? "Confirm Approval" : "Reject Request"}
              </h3>
              <button
                onClick={() => setDecisionModal((prev) => ({ ...prev, open: false }))}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>

            <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs space-y-1">
              <div>
                <span className="font-semibold text-slate-700">Request:</span>{" "}
                {decisionModal.type === "LEAVE"
                  ? `${decisionModal.item.employee_name} (${decisionModal.item.leave_type} Leave)`
                  : `${decisionModal.item.reassignment_type} Cover for ${decisionModal.item.target_job_name || "Shift"}`}
              </div>
              <div>
                <span className="font-semibold text-slate-700">Dates:</span>{" "}
                {decisionModal.type === "LEAVE"
                  ? `${decisionModal.item.from_date} to ${decisionModal.item.to_date}`
                  : `${decisionModal.item.date_from} to ${decisionModal.item.date_to}`}
              </div>
              <div>
                <span className="font-semibold text-slate-700">Reason:</span>{" "}
                {decisionModal.item.reason}
              </div>
            </div>

            {decisionModal.action === "REJECT" && (
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-800">
                  Rejection Reason <span className="text-rose-500">* (Mandatory)</span>
                </label>
                <textarea
                  rows={3}
                  value={decisionModal.note}
                  onChange={(e) => setDecisionModal((prev) => ({ ...prev, note: e.target.value, error: null }))}
                  placeholder="State the operational reason for rejecting this request..."
                  className="w-full text-xs p-2.5 rounded-lg border border-slate-300 focus:outline-hidden focus:ring-2 focus:ring-rose-500"
                />
              </div>
            )}

            {decisionModal.action === "APPROVE" && (
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-800">
                  Decision Note <span className="text-slate-400 font-normal">(Optional)</span>
                </label>
                <textarea
                  rows={2}
                  value={decisionModal.note}
                  onChange={(e) => setDecisionModal((prev) => ({ ...prev, note: e.target.value }))}
                  placeholder="Optional approval comments..."
                  className="w-full text-xs p-2.5 rounded-lg border border-slate-300 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            )}

            {decisionModal.error && (
              <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg text-xs flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
                {decisionModal.error}
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setDecisionModal((prev) => ({ ...prev, open: false }))}
                className="px-4 py-2 border border-slate-300 text-slate-700 hover:bg-slate-100 rounded-lg text-xs font-medium transition"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={decisionModal.submitting}
                onClick={handleConfirmDecision}
                className={`px-4 py-2 text-white rounded-lg text-xs font-semibold transition flex items-center gap-1.5 ${
                  decisionModal.action === "APPROVE"
                    ? "bg-emerald-600 hover:bg-emerald-700"
                    : "bg-rose-600 hover:bg-rose-700"
                }`}
              >
                {decisionModal.submitting ? "Processing..." : decisionModal.action === "APPROVE" ? "Confirm Approval" : "Confirm Rejection"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
