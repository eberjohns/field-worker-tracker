import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import {
  Download,
  RefreshCw,
  Search,
  X,
} from "lucide-react";

interface PendingVisitItem {
  id: string;
  scheduled_work_id: string;
  worksite_id: string;
  worksite_name: string;
  job_number: string;
  job_item_id: string;
  sub_item_code: string;
  item_description: string;
  employee_id: string;
  employee_name: string;
  tally_id: string;
  supervisor_name?: string | null;
  work_date: string;
  age_days: number;
  status: "OPEN" | "EXPLAINED" | "RESCHEDULED" | "CLOSED";
  latest_explanation?: string | null;
  rescheduled_to_work_date?: string | null;
  closed_reason?: string | null;
  is_escalated: boolean;
  created_at: string;
}

interface EmployeeOption {
  id: string;
  name: string;
  tally_id: string;
  role: string;
}

export const PendingVisits: React.FC = () => {
  const { token, user } = useAuth();
  const [items, setItems] = useState<PendingVisitItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [totalCount, setTotalCount] = useState(0);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [search, setSearch] = useState("");
  const [escalatedOnly, setEscalatedOnly] = useState(false);

  // Modals state
  const [explainingItem, setExplainingItem] = useState<PendingVisitItem | null>(null);
  const [explanationText, setExplanationText] = useState("");
  const [submittingExplain, setSubmittingExplain] = useState(false);

  const [reschedulingItem, setReschedulingItem] = useState<PendingVisitItem | null>(null);
  const [rescheduleDate, setRescheduleDate] = useState("");
  const [selectedWorkerIds, setSelectedWorkerIds] = useState<string[]>([]);
  const [submittingReschedule, setSubmittingReschedule] = useState(false);

  const [closingItem, setClosingItem] = useState<PendingVisitItem | null>(null);
  const [closeReason, setCloseReason] = useState("");
  const [submittingClose, setSubmittingClose] = useState(false);

  // Available workers for reschedule multi-select
  const [availableWorkers, setAvailableWorkers] = useState<EmployeeOption[]>([]);

  // Feedback messages
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const fetchPendingVisits = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
      const params = new URLSearchParams();
      if (statusFilter !== "ALL") params.set("status", statusFilter);
      if (escalatedOnly) params.set("escalated_only", "true");

      const res = await fetch(`/api/v1/pending-visits?${params.toString()}`, { headers });
      if (res.ok) {
        const data = await res.json();
        setItems(data.items || []);
        setTotalCount(data.total_count || 0);
      } else {
        const err = await res.json().catch(() => ({}));
        setErrorMsg(err.detail || "Failed to load pending visits.");
      }
    } catch (err) {
      console.error(err);
      setErrorMsg("Network error loading pending visits.");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, escalatedOnly, token]);

  useEffect(() => {
    fetchPendingVisits();
  }, [fetchPendingVisits]);

  // Fetch active workers for the reschedule modal dropdown
  useEffect(() => {
    const fetchWorkers = async () => {
      try {
        const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
        const res = await fetch("/api/v1/employees?is_active=true&limit=300", { headers });
        if (res.ok) {
          const data = await res.json();
          setAvailableWorkers(data.items || []);
        }
      } catch (err) {
        console.error(err);
      }
    };
    fetchWorkers();
  }, [token]);

  // Handle Explain Submission
  const handleExplain = async () => {
    if (!explainingItem || !explanationText.trim()) return;
    setSubmittingExplain(true);
    setErrorMsg(null);
    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      };
      const res = await fetch(`/api/v1/pending-visits/${explainingItem.id}/explain`, {
        method: "POST",
        headers,
        body: JSON.stringify({ explanation: explanationText.trim() }),
      });
      if (res.ok) {
        setSuccessMsg("Explanation recorded successfully.");
        setExplainingItem(null);
        setExplanationText("");
        fetchPendingVisits();
      } else {
        const err = await res.json().catch(() => ({}));
        setErrorMsg(err.detail || "Failed to submit explanation.");
      }
    } catch (err) {
      console.error(err);
      setErrorMsg("Network error submitting explanation.");
    } finally {
      setSubmittingExplain(false);
    }
  };

  // Handle Reschedule Submission
  const handleReschedule = async () => {
    if (!reschedulingItem || !rescheduleDate || selectedWorkerIds.length === 0) return;
    setSubmittingReschedule(true);
    setErrorMsg(null);
    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      };
      const res = await fetch(`/api/v1/pending-visits/${reschedulingItem.id}/reschedule`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          work_date: rescheduleDate,
          employee_ids: selectedWorkerIds,
        }),
      });
      if (res.ok) {
        setSuccessMsg("Visit rescheduled successfully.");
        setReschedulingItem(null);
        setRescheduleDate("");
        setSelectedWorkerIds([]);
        fetchPendingVisits();
      } else {
        const err = await res.json().catch(() => ({}));
        setErrorMsg(err.detail || "Failed to reschedule visit.");
      }
    } catch (err) {
      console.error(err);
      setErrorMsg("Network error rescheduling visit.");
    } finally {
      setSubmittingReschedule(false);
    }
  };

  // Handle Close Submission
  const handleClose = async () => {
    if (!closingItem || !closeReason.trim()) return;
    setSubmittingClose(true);
    setErrorMsg(null);
    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      };
      const res = await fetch(`/api/v1/pending-visits/${closingItem.id}/close`, {
        method: "POST",
        headers,
        body: JSON.stringify({ reason: closeReason.trim() }),
      });
      if (res.ok) {
        setSuccessMsg("Pending visit closed.");
        setClosingItem(null);
        setCloseReason("");
        fetchPendingVisits();
      } else {
        const err = await res.json().catch(() => ({}));
        setErrorMsg(err.detail || "Failed to close pending visit.");
      }
    } catch (err) {
      console.error(err);
      setErrorMsg("Network error closing pending visit.");
    } finally {
      setSubmittingClose(false);
    }
  };

  // Filter items in memory by search
  const filteredItems = items.filter((item) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      item.worksite_name.toLowerCase().includes(q) ||
      item.job_number.toLowerCase().includes(q) ||
      item.employee_name.toLowerCase().includes(q) ||
      item.tally_id.toLowerCase().includes(q) ||
      (item.item_description && item.item_description.toLowerCase().includes(q))
    );
  });

  // Export to CSV
  const exportCSV = () => {
    const headers = [
      "Job Number",
      "Worksite Name",
      "Sub Item Code",
      "Worker Name",
      "Tally ID",
      "Work Date",
      "Age (Days)",
      "Status",
      "Escalated",
      "Latest Explanation",
    ];
    const rows = filteredItems.map((i) => [
      `"${i.job_number}"`,
      `"${i.worksite_name}"`,
      `"${i.sub_item_code}"`,
      `"${i.employee_name}"`,
      `"${i.tally_id}"`,
      i.work_date,
      i.age_days,
      i.status,
      i.is_escalated ? "YES" : "NO",
      `"${(i.latest_explanation || "").replace(/"/g, '""')}"`,
    ]);
    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map((e) => e.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `pending_visits_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const isEngineerOrAdmin = user?.role === "ADMIN" || user?.role === "ENGINEER";

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900">Pending Visits</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">
              {totalCount} Total
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Track unvisited scheduled work occurrences, record supervisor explanations, or reschedule follow-up visits.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={exportCSV}
            disabled={filteredItems.length === 0}
            className="flex items-center gap-2 px-3.5 py-2 text-sm font-medium bg-white text-slate-700 border border-slate-300 rounded-lg hover:bg-slate-50 shadow-sm disabled:opacity-50"
          >
            <Download className="h-4 w-4 text-slate-500" />
            Export CSV
          </button>
          <button
            onClick={() => fetchPendingVisits()}
            className="flex items-center gap-2 px-3.5 py-2 text-sm font-medium bg-white text-slate-700 border border-slate-300 rounded-lg hover:bg-slate-50 shadow-sm"
          >
            <RefreshCw className={`h-4 w-4 text-slate-500 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Notifications */}
      {errorMsg && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center justify-between">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-red-500 hover:text-red-800 font-bold">×</button>
        </div>
      )}
      {successMsg && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700 flex items-center justify-between">
          <span>{successMsg}</span>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-500 hover:text-emerald-800 font-bold">×</button>
        </div>
      )}

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-wrap items-center gap-4">
        <div className="flex-1 min-w-[240px] relative">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search by worksite, job #, worker, or tally ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="flex items-center gap-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="ALL">All Statuses</option>
            <option value="OPEN">Open Only</option>
            <option value="EXPLAINED">Explained</option>
            <option value="RESCHEDULED">Rescheduled</option>
            <option value="CLOSED">Closed</option>
          </select>

          <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
            <input
              type="checkbox"
              checked={escalatedOnly}
              onChange={(e) => setEscalatedOnly(e.target.checked)}
              className="rounded border-slate-300 text-amber-600 focus:ring-amber-500"
            />
            <span>3+ Days Escalated Only</span>
          </label>
        </div>
      </div>

      {/* Table Card */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-700">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-600 uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3.5">Worksite</th>
                <th className="px-6 py-3.5">Job Item</th>
                <th className="px-6 py-3.5">Scheduled Worker</th>
                <th className="px-6 py-3.5">Work Date</th>
                <th className="px-6 py-3.5">Age</th>
                <th className="px-6 py-3.5">Status</th>
                <th className="px-6 py-3.5">Latest Explanation</th>
                <th className="px-6 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={8} className="px-6 py-12 text-center text-slate-400">
                    Loading pending visits...
                  </td>
                </tr>
              ) : filteredItems.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-6 py-12 text-center text-slate-400">
                    No pending visits found matching criteria.
                  </td>
                </tr>
              ) : (
                filteredItems.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-semibold text-slate-900">{item.worksite_name}</div>
                      <div className="text-xs text-slate-400 font-mono">{item.job_number}</div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-slate-800 font-medium">{item.sub_item_code}</div>
                      <div className="text-xs text-slate-500">{item.item_description}</div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="font-medium text-slate-900">{item.employee_name}</div>
                      <div className="text-xs text-slate-400">Tally: {item.tally_id}</div>
                    </td>
                    <td className="px-6 py-4 text-slate-600 font-mono text-xs">
                      {item.work_date}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-1.5">
                        <span className="font-semibold text-slate-800">{item.age_days}d</span>
                        {item.is_escalated && (
                          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-100 text-amber-800 border border-amber-300">
                            Escalated
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${
                          item.status === "OPEN"
                            ? item.is_escalated
                              ? "bg-red-100 text-red-800"
                              : "bg-amber-100 text-amber-800"
                            : item.status === "EXPLAINED"
                            ? "bg-blue-100 text-blue-800"
                            : item.status === "RESCHEDULED"
                            ? "bg-purple-100 text-purple-800"
                            : "bg-slate-100 text-slate-700"
                        }`}
                      >
                        {item.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 max-w-xs">
                      {item.latest_explanation ? (
                        <p className="text-xs text-slate-700 italic truncate" title={item.latest_explanation}>
                          "{item.latest_explanation}"
                        </p>
                      ) : (
                        <span className="text-xs text-slate-400">None</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right space-x-2 whitespace-nowrap">
                      {item.status === "OPEN" && (
                        <button
                          onClick={() => {
                            setExplainingItem(item);
                            setExplanationText(item.latest_explanation || "");
                          }}
                          className="px-2.5 py-1 text-xs font-medium bg-blue-50 text-blue-700 rounded hover:bg-blue-100 border border-blue-200"
                        >
                          Explain
                        </button>
                      )}

                      {isEngineerOrAdmin && item.status !== "CLOSED" && (
                        <>
                          <button
                            onClick={() => {
                              setReschedulingItem(item);
                              setRescheduleDate("");
                              setSelectedWorkerIds([item.employee_id]);
                            }}
                            className="px-2.5 py-1 text-xs font-medium bg-purple-50 text-purple-700 rounded hover:bg-purple-100 border border-purple-200"
                          >
                            Reschedule
                          </button>
                          <button
                            onClick={() => {
                              setClosingItem(item);
                              setCloseReason("");
                            }}
                            className="px-2.5 py-1 text-xs font-medium bg-slate-50 text-slate-700 rounded hover:bg-slate-100 border border-slate-200"
                          >
                            Close
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal: Explain Pending Visit */}
      {explainingItem && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="font-bold text-slate-900 text-base">Explain Missed Visit</h3>
              <button onClick={() => setExplainingItem(null)} className="text-slate-400 hover:text-slate-600">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="text-xs text-slate-600 space-y-1 bg-slate-50 p-3 rounded-lg border border-slate-200">
              <div><strong>Worksite:</strong> {explainingItem.worksite_name} ({explainingItem.job_number})</div>
              <div><strong>Worker:</strong> {explainingItem.employee_name} ({explainingItem.tally_id})</div>
              <div><strong>Work Date:</strong> {explainingItem.work_date}</div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Explanation / Reason for missed visit:
              </label>
              <textarea
                rows={4}
                value={explanationText}
                onChange={(e) => setExplanationText(e.target.value)}
                placeholder="e.g. Work cancelled by client, vehicle breakdown, site access delayed..."
                className="w-full text-sm p-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t">
              <button
                onClick={() => setExplainingItem(null)}
                className="px-4 py-2 text-sm text-slate-700 hover:bg-slate-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleExplain}
                disabled={submittingExplain || !explanationText.trim()}
                className="px-4 py-2 text-sm font-semibold bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {submittingExplain ? "Submitting..." : "Save Explanation"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Reschedule Pending Visit */}
      {reschedulingItem && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="font-bold text-slate-900 text-base">Reschedule Follow-up Visit</h3>
              <button onClick={() => setReschedulingItem(null)} className="text-slate-400 hover:text-slate-600">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="text-xs text-slate-600 space-y-1 bg-slate-50 p-3 rounded-lg border border-slate-200">
              <div><strong>Worksite:</strong> {reschedulingItem.worksite_name}</div>
              <div><strong>Original Date:</strong> {reschedulingItem.work_date}</div>
              <div><strong>Item:</strong> {reschedulingItem.sub_item_code} - {reschedulingItem.item_description}</div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                New Work Date:
              </label>
              <input
                type="date"
                value={rescheduleDate}
                onChange={(e) => setRescheduleDate(e.target.value)}
                className="w-full text-sm p-2.5 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Assign Worker(s):
              </label>
              <div className="max-h-48 overflow-y-auto border border-slate-200 rounded-lg p-2 space-y-1">
                {availableWorkers.map((worker) => {
                  const isChecked = selectedWorkerIds.includes(worker.id);
                  return (
                    <label
                      key={worker.id}
                      className="flex items-center gap-2 p-1.5 hover:bg-slate-50 rounded cursor-pointer text-xs text-slate-800"
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedWorkerIds([...selectedWorkerIds, worker.id]);
                          } else {
                            setSelectedWorkerIds(selectedWorkerIds.filter((id) => id !== worker.id));
                          }
                        }}
                        className="rounded border-slate-300 text-purple-600 focus:ring-purple-500"
                      />
                      <span className="font-medium">{worker.name}</span>
                      <span className="text-slate-400">({worker.tally_id} • {worker.role})</span>
                    </label>
                  );
                })}
              </div>
              <p className="text-[11px] text-slate-400 mt-1">
                {selectedWorkerIds.length} worker(s) selected for follow-up shift.
              </p>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t">
              <button
                onClick={() => setReschedulingItem(null)}
                className="px-4 py-2 text-sm text-slate-700 hover:bg-slate-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleReschedule}
                disabled={submittingReschedule || !rescheduleDate || selectedWorkerIds.length === 0}
                className="px-4 py-2 text-sm font-semibold bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
              >
                {submittingReschedule ? "Rescheduling..." : "Confirm Reschedule"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Close Pending Visit */}
      {closingItem && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="font-bold text-slate-900 text-base">Close Pending Visit</h3>
              <button onClick={() => setClosingItem(null)} className="text-slate-400 hover:text-slate-600">
                <X className="h-5 w-5" />
              </button>
            </div>

            <p className="text-xs text-slate-600">
              Closing a pending visit marks it as resolved without creating a rescheduled assignment.
            </p>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Reason for closure (required):
              </label>
              <textarea
                rows={3}
                value={closeReason}
                onChange={(e) => setCloseReason(e.target.value)}
                placeholder="e.g. Work confirmed complete under alternative job order, customer waived inspection..."
                className="w-full text-sm p-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-500"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t">
              <button
                onClick={() => setClosingItem(null)}
                className="px-4 py-2 text-sm text-slate-700 hover:bg-slate-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleClose}
                disabled={submittingClose || !closeReason.trim()}
                className="px-4 py-2 text-sm font-semibold bg-slate-800 text-white rounded-lg hover:bg-slate-900 disabled:opacity-50"
              >
                {submittingClose ? "Closing..." : "Close Visit"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

