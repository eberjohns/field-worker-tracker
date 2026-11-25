import React, { useState, useEffect, useCallback } from "react";
import { Link } from "@tanstack/react-router";
import {
  Calendar,
  Plus,
  UploadCloud,
  Download,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  Users,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { DatePicker, Modal, problemFromBody, useDialogs, useToast } from "../ui";

interface LeaveRequestItem {
  id: string;
  read_only?: boolean; // DEC-57: visible through a worksite, managed by the crew chain
  employee_id: string;
  employee_name: string;
  tally_id: string;
  employee_weekly_off_day?: string | null;
  cover_employee_id?: string | null;
  cover_employee_name?: string | null;
  cover_employee_tally_id?: string | null;
  cover_weekly_off_day?: string | null;
  weekly_off_mismatch?: boolean;
  leave_type: string;
  from_date: string;
  to_date: string;
  working_days: number;
  calendar_days: number;
  reason: string;
  status: string;
  recorded_by_name: string | null;
  recorded_at?: string;
  created_at?: string;
  approved_by_name: string | null;
  approved_at: string | null;
  decision_note: string | null;
}

interface LeaveTakenTypeSummary {
  leave_type: string;
  working_days: number;
  calendar_days: number;
}

interface LeaveTakenWorkerSummary {
  employee_id: string;
  employee_name: string;
  tally_id: string;
  total_working_days: number;
  total_calendar_days: number;
  by_type: Record<string, LeaveTakenTypeSummary>;
}

interface EmployeeOption {
  id: string;
  name: string;
  tally_id: string;
  weekly_off_day?: string | null;
  role?: string;
}

const DOW = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];

/** True when the cover's weekly off falls on a leave day the original worker works; the
 * off-day warning shows only then (19 Nov meeting item 5). Same rule as the server. */
function coverOffAffected(
  from: string,
  to: string,
  empOff: string | null | undefined,
  coverOff: string | null | undefined,
): boolean {
  const cover = (coverOff || "").trim().toUpperCase().slice(0, 3);
  const emp = (empOff || "").trim().toUpperCase().slice(0, 3);
  if (!cover || cover === emp) return false;
  if (!from || !to || to < from) return true;
  const start = new Date(`${from}T00:00:00Z`);
  const days = Math.min(Math.round((Date.parse(`${to}T00:00:00Z`) - start.getTime()) / 86400000) + 1, 7);
  for (let i = 0; i < days; i++) {
    if (DOW[(start.getUTCDay() + i) % 7] === cover) return true;
  }
  return false;
}

export const LeaveManagement: React.FC = () => {
  const toast = useToast();
  const dialogs = useDialogs();
  const { token, user } = useAuth();
  const [year, setYear] = useState<number>(new Date().getFullYear());
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [typeFilter, setTypeFilter] = useState<string>("ALL");
  const [leaves, setLeaves] = useState<LeaveRequestItem[]>([]);
  const [summaries, setSummaries] = useState<LeaveTakenWorkerSummary[]>([]);
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [loading, setLoading] = useState(true);

  // Record Modal State
  const [recordModalOpen, setRecordModalOpen] = useState(false);
  const [recordForm, setRecordForm] = useState({
    employee_id: "",
    cover_employee_id: "",
    leave_type: "ANNUAL",
    from_date: "",
    to_date: "",
    reason: "",
  });
  const [recordSubmitting, setRecordSubmitting] = useState(false);
  const [bypassNotice, setBypassNotice] = useState(false);
  const [recordError, setRecordError] = useState<string | null>(null);

  // Bulk Cover Modal State
  const [bulkCoverLeave, setBulkCoverLeave] = useState<LeaveRequestItem | null>(null);
  const [bulkCoverEmpId, setBulkCoverEmpId] = useState("");
  const [bulkCoverSubmitting, setBulkCoverSubmitting] = useState(false);
  const [bulkCoverResult, setBulkCoverResult] = useState<string | null>(null);
  const [bulkCoverError, setBulkCoverError] = useState<string | null>(null);

  // Workers who can't cover the selected dates (on leave, already covering, or on a
  // PERMANENT job): left out of both cover dropdowns (19 Nov meeting item 5).
  const [recordUnavailable, setRecordUnavailable] = useState<Record<string, string>>({});
  const [bulkUnavailable, setBulkUnavailable] = useState<Record<string, string>>({});
  const fetchCoverUnavailable = useCallback(
    async (from: string, to: string, excludeLeaveId?: string): Promise<Record<string, string>> => {
      if (!from || !to || to < from) return {};
      const params = new URLSearchParams({ from_date: from, to_date: to });
      if (excludeLeaveId) params.set("exclude_leave_id", excludeLeaveId);
      try {
        const res = await fetch(`/api/v1/leave-requests/cover-availability?${params}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) return {};
        const data = await res.json();
        return data.unavailable || {};
      } catch {
        return {};
      }
    },
    [token],
  );
  useEffect(() => {
    let cancelled = false;
    fetchCoverUnavailable(recordForm.from_date, recordForm.to_date).then((u) => {
      if (!cancelled) setRecordUnavailable(u);
    });
    return () => {
      cancelled = true;
    };
  }, [fetchCoverUnavailable, recordForm.from_date, recordForm.to_date]);
  useEffect(() => {
    if (!bulkCoverLeave) return;
    let cancelled = false;
    fetchCoverUnavailable(bulkCoverLeave.from_date, bulkCoverLeave.to_date, bulkCoverLeave.id).then((u) => {
      if (!cancelled) setBulkUnavailable(u);
    });
    return () => {
      cancelled = true;
    };
  }, [fetchCoverUnavailable, bulkCoverLeave]);

  const canManageCover =
    user?.role === "ADMIN" || user?.role === "ENGINEER" || user?.role === "SUPERINTENDENT";

  // Import Modal State
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importSubmitting, setImportSubmitting] = useState(false);
  const [importResult, setImportResult] = useState<any | null>(null);
  const [importError, setImportError] = useState<string | null>(null);

  const fetchLeavesAndSummaries = async () => {
    setLoading(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const statusParam = statusFilter === "ALL" ? "" : `&status=${statusFilter}`;
      const [leavesRes, sumRes] = await Promise.all([
        fetch(`/api/v1/leave-requests?year=${year}${statusParam}`, { headers }),
        fetch(`/api/v1/leave-requests/summary?year=${year}`, { headers }),
      ]);

      if (leavesRes.ok) {
        const data = await leavesRes.json();
        setLeaves(data);
      }
      if (sumRes.ok) {
        const sumData = await sumRes.json();
        setSummaries(sumData);
      }
    } catch (err) {
      console.error("Failed to fetch leaves", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchEmployees = async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const res = await fetch("/api/v1/employees?limit=300", { headers });
      if (res.ok) {
        const data = await res.json();
        setEmployees(data.items || data || []);
      }
    } catch (err) {
      console.error("Failed to load employees", err);
    }
  };

  useEffect(() => {
    fetchLeavesAndSummaries();
  }, [token, year, statusFilter]);

  useEffect(() => {
    fetchEmployees();
  }, [token]);

  const isUrgentLeaveType =
    recordForm.leave_type === "EMERGENCY" || recordForm.leave_type === "SICK";

  // Notice period warning check for record form
  const getNoticeWarning = () => {
    if (!recordForm.from_date || isUrgentLeaveType) return null;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const from = new Date(recordForm.from_date);
    const diffDays = Math.ceil((from.getTime() - today.getTime()) / (1000 * 3600 * 24));
    if (diffDays < 3) {
      return "Leave requests require at least 3 days notice in advance.";
    }
    return null;
  };

  const handleRecordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!recordForm.employee_id || !recordForm.from_date || !recordForm.to_date || !recordForm.reason.trim()) {
      setRecordError("Please fill in all required fields.");
      return;
    }

    const warning = getNoticeWarning();
    if (warning) {
      if (user?.role !== "ADMIN") {
        setRecordError(warning);
        return;
      }
      if (!bypassNotice) {
        setRecordError("Please check the confirmation box to bypass the 3-day notice rule for this short-notice leave.");
        return;
      }
    }

    setRecordSubmitting(true);
    setRecordError(null);
    try {
      const headers = {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      };
      const payload = {
        employee_id: recordForm.employee_id,
        cover_employee_id: recordForm.cover_employee_id || null,
        leave_type: recordForm.leave_type,
        from_date: recordForm.from_date,
        to_date: recordForm.to_date,
        reason: recordForm.reason,
        bypass_notice: user?.role === "ADMIN" && bypassNotice,
      };
      const res = await fetch("/api/v1/leave-requests", {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json();
        const msg = problemFromBody(null, err, "Failed to record leave").message;
        setRecordError(String(msg));
        return;
      }

      setRecordModalOpen(false);
      setBypassNotice(false);
      setRecordForm({
        employee_id: "",
        cover_employee_id: "",
        leave_type: "ANNUAL",
        from_date: "",
        to_date: "",
        reason: "",
      });
      await fetchLeavesAndSummaries();
    } catch (err: any) {
      setRecordError(err.message || "Network error");
    } finally {
      setRecordSubmitting(false);
    }
  };

  const handleBulkCoverSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!bulkCoverLeave || !bulkCoverEmpId) return;
    setBulkCoverSubmitting(true);
    setBulkCoverError(null);
    setBulkCoverResult(null);
    try {
      const res = await fetch(`/api/v1/leave-requests/${bulkCoverLeave.id}/bulk-cover`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ cover_employee_id: bulkCoverEmpId }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setBulkCoverError(String(problemFromBody(null, err, "Failed to bulk cover leave.").message));
        return;
      }
      const data = await res.json();
      const woMsg =
        data.weekly_off_cover_dates?.length > 0
          ? ` (${data.weekly_off_cover_dates.length} day(s) fall on cover worker's weekly off and are marked Weekly Off Covering)`
          : "";
      setBulkCoverResult(
        `Assigned ${data.cover_employee_name || "cover worker"} to ${data.covered_count} uncovered slot(s)${woMsg}.`
      );
      await fetchLeavesAndSummaries();
    } catch (err: any) {
      setBulkCoverError(err.message || "Network error");
    } finally {
      setBulkCoverSubmitting(false);
    }
  };

  const handleCancelLeave = async (leaveId: string) => {
    if (!(await dialogs.confirm({ title: "Cancel this leave?", message: "Are you sure you want to cancel this leave? This will restore schedule slots.", confirmLabel: "Cancel leave", variant: "destructive" }))) {
      return;
    }

    try {
      const headers = { Authorization: `Bearer ${token}` };
      const res = await fetch(`/api/v1/leave-requests/${leaveId}/cancel`, {
        method: "POST",
        headers,
      });
      if (res.ok) {
        await fetchLeavesAndSummaries();
      } else {
        const err = await res.json();
        toast.error(err, "Failed to cancel leave");
      }
    } catch (err: any) {
      toast.error(err);
    }
  };

  const handleDownloadTemplate = async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const res = await fetch("/api/v1/leave-requests/template", { headers });
      if (!res.ok) throw new Error("Template download failed");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "leave_import_template.xlsx";
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (err: any) {
      toast.error(err, "Failed to download template");
    }
  };

  const handleImportSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!importFile) {
      setImportError("Please select an Excel workbook to upload.");
      return;
    }

    setImportSubmitting(true);
    setImportError(null);
    setImportResult(null);

    try {
      const formData = new FormData();
      formData.append("file", importFile);

      const headers = { Authorization: `Bearer ${token}` };
      const res = await fetch("/api/v1/leave-requests/import", {
        method: "POST",
        headers,
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) {
        const msg = problemFromBody(null, data, "Import failed").message;
        setImportError(String(msg));
        return;
      }

      setImportResult(data);
      await fetchLeavesAndSummaries();
    } catch (err: any) {
      setImportError(err.message || "Network error");
    } finally {
      setImportSubmitting(false);
    }
  };

  const filteredLeaves = leaves.filter((l) => {
    if (typeFilter !== "ALL" && l.leave_type !== typeFilter) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <Calendar className="h-6 w-6 text-indigo-600" />
            Leave Management
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Record employee leaves, monitor working-day vs calendar-day leave taken, and manage bulk imports.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {user?.role === "ADMIN" && (
            <button
              onClick={() => {
                setImportModalOpen(true);
                setImportResult(null);
                setImportError(null);
                setImportFile(null);
              }}
              className="px-3.5 py-2 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition shadow-2xs"
            >
              <UploadCloud className="h-4 w-4 text-indigo-600" />
              Import Leaves
            </button>
          )}

          <button
            onClick={() => {
              setRecordModalOpen(true);
              setRecordError(null);
            }}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition shadow-2xs"
          >
            <Plus className="h-4 w-4" />
            Record Leave
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs space-y-1">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Leave Taken ({year})</div>
          <div className="text-2xl font-bold text-slate-900">
            {summaries.reduce((acc, s) => acc + s.total_working_days, 0)}{" "}
            <span
              className="text-xs font-normal text-slate-500 cursor-help inline-flex items-center gap-0.5"
              title="Working days exclude employee weekly rest days and public holidays. '(cal)' indicates total elapsed calendar days."
            >
              working days ({summaries.reduce((acc, s) => acc + s.total_calendar_days, 0)} cal)
              <HelpCircle className="h-3 w-3 text-slate-400" />
            </span>
          </div>
          <p className="text-2xs text-slate-400">Total approved leaves across your scope</p>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs space-y-1">
          <div className="text-xs font-semibold text-blue-600 uppercase tracking-wider">Annual Leaves</div>
          <div className="text-2xl font-bold text-blue-700">
            {summaries.reduce((acc, s) => acc + (s.by_type?.ANNUAL?.working_days || 0), 0)}{" "}
            <span
              className="text-xs font-normal text-slate-500 cursor-help inline-flex items-center gap-0.5"
              title="Working days exclude employee weekly rest days and public holidays. '(cal)' indicates total elapsed calendar days."
            >
              days ({summaries.reduce((acc, s) => acc + (s.by_type?.ANNUAL?.calendar_days || 0), 0)} cal)
              <HelpCircle className="h-3 w-3 text-slate-400" />
            </span>
          </div>
          <p className="text-2xs text-slate-400">Excludes rest days & holidays</p>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs space-y-1">
          <div className="text-xs font-semibold text-rose-600 uppercase tracking-wider">Sick Leaves</div>
          <div className="text-2xl font-bold text-rose-700">
            {summaries.reduce((acc, s) => acc + (s.by_type?.SICK?.working_days || 0), 0)}{" "}
            <span
              className="text-xs font-normal text-slate-500 cursor-help inline-flex items-center gap-0.5"
              title="Working days exclude employee weekly rest days and public holidays. '(cal)' indicates total elapsed calendar days."
            >
              days ({summaries.reduce((acc, s) => acc + (s.by_type?.SICK?.calendar_days || 0), 0)} cal)
              <HelpCircle className="h-3 w-3 text-slate-400" />
            </span>
          </div>
          <p className="text-2xs text-slate-400">Approved medical absences</p>
        </div>

        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs space-y-1">
          <div className="text-xs font-semibold text-amber-600 uppercase tracking-wider">Emergency / Unpaid</div>
          <div className="text-2xl font-bold text-amber-700">
            {summaries.reduce((acc, s) => acc + (s.by_type?.EMERGENCY?.working_days || 0) + (s.by_type?.UNPAID?.working_days || 0), 0)}{" "}
            <span className="text-xs font-normal text-slate-500">working days</span>
          </div>
          <p className="text-2xs text-slate-400">Special leave categories</p>
        </div>
      </div>

      {/* Filter and Control Bar */}
      <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-2xs flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-semibold text-slate-600">Year:</span>
            <select
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="text-xs font-medium text-slate-800 bg-slate-50 border border-slate-200 rounded-md px-2.5 py-1.5 focus:outline-hidden"
            >
              <option value={2025}>2025</option>
              <option value={2026}>2026</option>
              <option value={2027}>2027</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-xs font-semibold text-slate-600">Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-xs font-medium text-slate-800 bg-slate-50 border border-slate-200 rounded-md px-2.5 py-1.5 focus:outline-hidden"
            >
              <option value="ALL">All Statuses</option>
              <option value="REQUESTED">Requested (Pending)</option>
              <option value="APPROVED">Approved</option>
              <option value="REJECTED">Rejected</option>
              <option value="CANCELLED">Cancelled</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-xs font-semibold text-slate-600">Type:</span>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="text-xs font-medium text-slate-800 bg-slate-50 border border-slate-200 rounded-md px-2.5 py-1.5 focus:outline-hidden"
            >
              <option value="ALL">All Types</option>
              <option value="ANNUAL">Annual</option>
              <option value="SICK">Sick</option>
              <option value="UNPAID">Unpaid</option>
              <option value="EMERGENCY">Emergency</option>
              <option value="OTHER">Other</option>
            </select>
          </div>
        </div>

        <button
          onClick={fetchLeavesAndSummaries}
          disabled={loading}
          className="p-1.5 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg border border-slate-200 transition"
          title="Refresh"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* Leave Requests Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-slate-500 flex items-center justify-center gap-2">
            <RefreshCw className="h-5 w-5 animate-spin" />
            Loading leaves...
          </div>
        ) : filteredLeaves.length === 0 ? (
          <div className="p-12 text-center text-slate-400 space-y-2">
            <Calendar className="h-10 w-10 text-slate-300 mx-auto" />
            <div className="text-base font-semibold text-slate-700">No leave records found</div>
            <p className="text-xs text-slate-400">Click "Record Leave" to submit a leave request for a worker.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs font-semibold text-slate-600 uppercase">
                <tr>
                  <th className="py-3 px-4">Worker</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4">Dates</th>
                  <th className="py-3 px-4">Leave Taken</th>
                  <th className="py-3 px-4">Reason</th>
                  <th className="py-3 px-4">Recorded By</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredLeaves.map((l) => (
                  <tr key={l.id} className="hover:bg-slate-50/80 transition">
                    <td className="py-3.5 px-4">
                      <div className="font-semibold text-slate-900">{l.employee_name}</div>
                      <div className="text-xs text-slate-400">
                        Tally: {l.tally_id}
                        {l.employee_weekly_off_day ? ` · Off: ${l.employee_weekly_off_day}` : ""}
                      </div>
                      {l.cover_employee_name && (
                        <div className="mt-1 flex flex-wrap items-center gap-1">
                          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                            Cover: {l.cover_employee_name} ({l.cover_employee_tally_id})
                          </span>
                          {l.weekly_off_mismatch && (
                            <span
                              className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-50 text-amber-800 border border-amber-200"
                              title={`Original off: ${l.employee_weekly_off_day || "Unset"}, Cover off: ${l.cover_weekly_off_day || "Unset"}`}
                            >
                              Off-Day Mismatch
                            </span>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${
                        l.leave_type === "ANNUAL" ? "bg-blue-50 text-blue-700 border border-blue-200" :
                        l.leave_type === "SICK" ? "bg-rose-50 text-rose-700 border border-rose-200" :
                        l.leave_type === "EMERGENCY" ? "bg-amber-50 text-amber-700 border border-amber-200" :
                        "bg-slate-100 text-slate-700"
                      }`}>
                        {l.leave_type}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-slate-800 font-medium text-xs">
                      {l.from_date} to {l.to_date}
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="font-bold text-slate-900 text-xs">
                        {l.working_days} working {l.working_days === 1 ? "day" : "days"}
                      </div>
                      <div className="text-2xs text-slate-400">
                        {l.calendar_days} calendar days
                      </div>
                    </td>
                    <td className="py-3.5 px-4 text-xs text-slate-600 max-w-xs truncate" title={l.reason}>
                      {l.reason}
                    </td>
                    <td className="py-3.5 px-4 text-xs text-slate-500">
                      <div>{l.recorded_by_name || "Unknown"}</div>
                      <div className="text-2xs text-slate-400">
                        {new Date(l.recorded_at || l.created_at || Date.now()).toLocaleDateString()}
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold ${
                        l.status === "REQUESTED" ? "bg-amber-100 text-amber-800" :
                        l.status === "APPROVED" ? "bg-emerald-100 text-emerald-800" :
                        l.status === "REJECTED" ? "bg-rose-100 text-rose-800" :
                        "bg-slate-100 text-slate-600"
                      }`}>
                        {l.status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {l.status === "APPROVED" && canManageCover && !l.read_only && (
                          <button
                            type="button"
                            onClick={() => {
                              setBulkCoverLeave(l);
                              setBulkCoverEmpId(l.cover_employee_id || "");
                              setBulkCoverError(null);
                              setBulkCoverResult(null);
                            }}
                            className="px-2.5 py-1 text-xs font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-md transition flex items-center gap-1 shadow-2xs cursor-pointer"
                            title="Assign one cover worker to every remaining TO_BE_COVERED slot for this leave"
                          >
                            <Users className="h-3 w-3" />
                            Cover All Slots
                          </button>
                        )}
                        {l.status === "APPROVED" && (
                          <Link
                            to="/operational-planner"
                            search={{ date: l.from_date, employee_id: l.employee_id, lens: "COVERAGE" }}
                            className="px-2.5 py-1 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-md transition flex items-center gap-1 shadow-2xs"
                            title="Open Operational Planner to arrange a cover replacement for this approved leave"
                          >
                            <Users className="h-3 w-3" />
                            Arrange Cover
                          </Link>
                        )}
                        {l.status === "REQUESTED" && (
                          <button
                            onClick={() => handleCancelLeave(l.id)}
                            className="px-2.5 py-1 text-xs font-medium text-rose-700 hover:bg-rose-50 border border-rose-200 rounded-md transition"
                          >
                            Cancel
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Record Leave Modal */}
      {recordModalOpen && (
        <Modal
          open
          onClose={() => setRecordModalOpen(false)}
          size="md"
          title={<span className="inline-flex items-center gap-2"><Calendar className="h-5 w-5 text-indigo-600" /> Record Leave Request</span>}
        >
          <form onSubmit={handleRecordSubmit} className="space-y-4 text-xs">
            <div className="space-y-1">
              <label className="font-semibold text-slate-700">Worker *</label>
              <select
                required
                value={recordForm.employee_id}
                onChange={(e) => setRecordForm({ ...recordForm, employee_id: e.target.value })}
                className="w-full p-2.5 rounded-lg border border-slate-300 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">Select worker...</option>
                {employees.map((emp) => (
                  <option key={emp.id} value={emp.id}>
                    {emp.name} ({emp.tally_id})
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <label className="font-semibold text-slate-700">Leave Type *</label>
              <select
                required
                value={recordForm.leave_type}
                onChange={(e) => setRecordForm({ ...recordForm, leave_type: e.target.value })}
                className="w-full p-2.5 rounded-lg border border-slate-300 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
              >
                <option value="ANNUAL">Annual Leave</option>
                <option value="SICK">Sick Leave</option>
                <option value="UNPAID">Unpaid Leave</option>
                <option value="EMERGENCY">Emergency Leave</option>
                <option value="OTHER">Other Leave</option>
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <DatePicker
                  label="From Date"
                  required
                  value={recordForm.from_date}
                  onChange={(iso) => setRecordForm({ ...recordForm, from_date: iso })}
                  size="lg"
                />
              </div>
              <div className="space-y-1">
                <DatePicker
                  label="To Date"
                  required
                  value={recordForm.to_date}
                  onChange={(iso) => setRecordForm({ ...recordForm, to_date: iso })}
                  size="lg"
                />
              </div>
            </div>

            {isUrgentLeaveType && (
              <div className="p-2.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
                <span className="text-xs">
                  Emergency and Sick leaves are exempt from the 3-day advance notice requirement.
                </span>
              </div>
            )}

            {getNoticeWarning() && (
              <div className="space-y-2">
                <div className="p-2.5 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />
                  <span className="text-xs">{getNoticeWarning()}</span>
                </div>
                {user?.role === "ADMIN" && (
                  <label className="flex items-center gap-2 text-xs font-semibold text-amber-900 bg-amber-50/70 p-2.5 rounded-lg border border-amber-200 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={bypassNotice}
                      onChange={(e) => setBypassNotice(e.target.checked)}
                      className="rounded text-indigo-600 focus:ring-indigo-500 h-4 w-4"
                    />
                    <span>Emergency / Short-notice leave (Confirm Admin bypass)</span>
                  </label>
                )}
              </div>
            )}

            <div className="space-y-1">
              <label className="font-semibold text-slate-700">
                Cover Worker <span className="font-normal text-slate-400">(Optional — auto-covers all shifts on approval)</span>
              </label>
              <select
                value={recordForm.cover_employee_id}
                onChange={(e) => setRecordForm({ ...recordForm, cover_employee_id: e.target.value })}
                className="w-full p-2.5 rounded-lg border border-slate-300 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">No pre-assigned cover worker</option>
                {employees
                  .filter(
                    (emp) =>
                      emp.id !== recordForm.employee_id &&
                      emp.role !== "ADMIN" &&
                      (!recordUnavailable[emp.id] || emp.id === recordForm.cover_employee_id),
                  )
                  .map((emp) => (
                    <option key={emp.id} value={emp.id}>
                      {emp.name} ({emp.tally_id}){emp.weekly_off_day ? ` — Off: ${emp.weekly_off_day}` : ""}
                    </option>
                  ))}
              </select>
              {(() => {
                const origEmp = employees.find((e) => e.id === recordForm.employee_id);
                const covEmp = employees.find((e) => e.id === recordForm.cover_employee_id);
                if (
                  origEmp &&
                  covEmp &&
                  coverOffAffected(recordForm.from_date, recordForm.to_date, origEmp.weekly_off_day, covEmp.weekly_off_day)
                ) {
                  return (
                    <div className="mt-1.5 p-2.5 bg-amber-50 border border-amber-200 text-amber-900 rounded-lg flex items-start gap-2">
                      <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 mt-0.5" />
                      <span>
                        <strong>Weekly Off Day Mismatch:</strong> {origEmp.name}'s off day is{" "}
                        <strong>{origEmp.weekly_off_day || "Unset"}</strong>, while {covEmp.name}'s off day is{" "}
                        <strong>{covEmp.weekly_off_day || "Unset"}</strong>. On approval, {covEmp.name} will still
                        be assigned to cover all working days of {origEmp.name}, with a clear{" "}
                        <strong>Weekly Off (Covering)</strong> indicator on {covEmp.weekly_off_day || "their off day"}.
                      </span>
                    </div>
                  );
                }
                return null;
              })()}
            </div>

            <div className="space-y-1">
              <label className="font-semibold text-slate-700">Reason / Notes *</label>
              <textarea
                required
                rows={3}
                value={recordForm.reason}
                onChange={(e) => setRecordForm({ ...recordForm, reason: e.target.value })}
                placeholder="Enter reason for leave..."
                className="w-full p-2.5 rounded-lg border border-slate-300 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {recordError && (
              <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
                {recordError}
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setRecordModalOpen(false)}
                className="px-4 py-2 border border-slate-300 text-slate-700 hover:bg-slate-100 rounded-lg font-medium transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={recordSubmitting}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-semibold transition"
              >
                {recordSubmitting ? "Submitting..." : "Submit Leave Request"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* Bulk Cover Approved Leave Modal */}
      {bulkCoverLeave && (
        <Modal
          open
          onClose={() => setBulkCoverLeave(null)}
          size="md"
          title={<span className="inline-flex items-center gap-2"><Users className="h-5 w-5 text-emerald-600" /> Cover All Uncovered Slots</span>}
        >
          <div className="space-y-4">
            <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs space-y-1">
              <div>
                <span className="font-semibold text-slate-700">Worker on Leave:</span>{" "}
                {bulkCoverLeave.employee_name} ({bulkCoverLeave.tally_id})
                {bulkCoverLeave.employee_weekly_off_day
                  ? ` · Off: ${bulkCoverLeave.employee_weekly_off_day}`
                  : ""}
              </div>
              <div>
                <span className="font-semibold text-slate-700">Leave Period:</span>{" "}
                {bulkCoverLeave.from_date} to {bulkCoverLeave.to_date} ({bulkCoverLeave.leave_type})
              </div>
            </div>
  
            <form onSubmit={handleBulkCoverSubmit} className="space-y-3 text-xs">
              <div className="space-y-1">
                <label className="font-semibold text-slate-700">Select Cover Worker *</label>
                <select
                  required
                  value={bulkCoverEmpId}
                  onChange={(e) => setBulkCoverEmpId(e.target.value)}
                  className="w-full p-2.5 rounded-lg border border-slate-300 focus:outline-hidden focus:ring-2 focus:ring-emerald-500"
                >
                  <option value="">Choose cover worker...</option>
                  {employees
                    .filter(
                      (emp) =>
                        emp.id !== bulkCoverLeave.employee_id &&
                        emp.role !== "ADMIN" &&
                        (!bulkUnavailable[emp.id] || emp.id === bulkCoverEmpId),
                    )
                    .map((emp) => (
                      <option key={emp.id} value={emp.id}>
                        {emp.name} ({emp.tally_id}){emp.weekly_off_day ? ` — Off: ${emp.weekly_off_day}` : ""}
                      </option>
                    ))}
                </select>
              </div>
  
              {(() => {
                const covEmp = employees.find((e) => e.id === bulkCoverEmpId);
                if (
                  covEmp &&
                  coverOffAffected(
                    bulkCoverLeave.from_date,
                    bulkCoverLeave.to_date,
                    bulkCoverLeave.employee_weekly_off_day,
                    covEmp.weekly_off_day,
                  )
                ) {
                  return (
                    <div className="p-2.5 bg-amber-50 border border-amber-200 text-amber-900 rounded-lg flex items-start gap-2">
                      <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 mt-0.5" />
                      <span>
                        <strong>Weekly Off Mismatch:</strong> {covEmp.name}'s weekly off is{" "}
                        <strong>{covEmp.weekly_off_day || "Unset"}</strong>. All uncovered working days of{" "}
                        {bulkCoverLeave.employee_name} will be assigned with a clear{" "}
                        <strong>Weekly Off (Covering)</strong> indicator where overlapping.
                      </span>
                    </div>
                  );
                }
                return null;
              })()}
  
              {bulkCoverError && (
                <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  {bulkCoverError}
                </div>
              )}
  
              {bulkCoverResult && (
                <div className="p-2.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                  {bulkCoverResult}
                </div>
              )}
  
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setBulkCoverLeave(null)}
                  className="px-3.5 py-2 border border-slate-300 text-slate-700 hover:bg-slate-50 rounded-lg font-medium"
                >
                  Close
                </button>
                <button
                  type="submit"
                  disabled={bulkCoverSubmitting || !bulkCoverEmpId}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white rounded-lg font-semibold"
                >
                  {bulkCoverSubmitting ? "Assigning..." : "Cover All Uncovered Slots"}
                </button>
              </div>
            </form>
          </div>
        </Modal>
      )}

      {/* Standalone Leave Import Modal */}
      {importModalOpen && (
        <Modal
          open
          onClose={() => setImportModalOpen(false)}
          size="md"
          title={<span className="inline-flex items-center gap-2"><UploadCloud className="h-5 w-5 text-indigo-600" /> Import Leaves from Excel</span>}
        >
          <div className="space-y-4">
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg space-y-2 text-xs">
              <div className="font-semibold text-slate-800">Download Template First</div>
              <p className="text-slate-500">
                Download the standardized Excel workbook with headers: Tally ID, Leave Type, From Date, To Date, and Reason.
              </p>
              <button
                type="button"
                onClick={handleDownloadTemplate}
                className="px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-100 text-slate-700 rounded-md font-semibold flex items-center gap-1.5 shadow-2xs"
              >
                <Download className="h-4 w-4 text-indigo-600" />
                Download Template (.xlsx)
              </button>
            </div>
  
            <form onSubmit={handleImportSubmit} className="space-y-4 text-xs">
              <div className="space-y-1">
                <label className="font-semibold text-slate-700">Select Completed Excel File (.xlsx)</label>
                <input
                  type="file"
                  required
                  accept=".xlsx"
                  onChange={(e) => setImportFile(e.target.files?.[0] || null)}
                  className="w-full p-2.5 rounded-lg border border-slate-300 focus:outline-hidden"
                />
              </div>
  
              {importError && (
                <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
                  {importError}
                </div>
              )}
  
              {importResult && (
                <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg space-y-1">
                  <div className="font-bold flex items-center gap-1.5">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                    Import Succeeded!
                  </div>
                  <div>Committed: {importResult.committed_count} leave requests</div>
                </div>
              )}
  
              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setImportModalOpen(false)}
                  className="px-4 py-2 border border-slate-300 text-slate-700 hover:bg-slate-100 rounded-lg font-medium transition"
                >
                  Close
                </button>
                <button
                  type="submit"
                  disabled={importSubmitting || !importFile}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-semibold transition"
                >
                  {importSubmitting ? "Uploading..." : "Upload and Commit"}
                </button>
              </div>
            </form>
          </div>
        </Modal>
      )}
    </div>
  );
};
