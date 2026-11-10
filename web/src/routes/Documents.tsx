import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import {
  Search,
  RefreshCw,
  Bell,
  Download,
  FileText,
} from "lucide-react";

interface DocumentItem {
  document_id: string;
  employee_id: string;
  employee_name: string;
  tally_id: string;
  role: string;
  supervisor_name?: string | null;
  document_type: string;
  expiry_date: string;
  days_remaining: number;
  status: "OK" | "EXPIRING" | "EXPIRED";
}

export const Documents: React.FC = () => {
  const { token } = useAuth();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [totalCount, setTotalCount] = useState(0);

  // Filters
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("ALL");
  const [withinDays, setWithinDays] = useState<number>(30);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  // Alert check action state
  const [checkingAlerts, setCheckingAlerts] = useState(false);
  const [alertResult, setAlertResult] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
      const params = new URLSearchParams({
        within_days: String(withinDays),
      });
      if (typeFilter !== "ALL") params.set("document_type", typeFilter);

      const res = await fetch(`/api/v1/documents/expiring?${params.toString()}`, { headers });
      if (res.ok) {
        const data = await res.json();
        setDocuments(data.items || []);
        setTotalCount(data.total_count || 0);
      } else {
        const err = await res.json().catch(() => ({}));
        setErrorMsg(err.detail || "Failed to load employee documents.");
      }
    } catch (err) {
      console.error(err);
      setErrorMsg("Network error loading employee documents.");
    } finally {
      setLoading(false);
    }
  }, [withinDays, typeFilter, token]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  // Check and raise alerts
  const handleCheckAlerts = async () => {
    setCheckingAlerts(true);
    setAlertResult(null);
    setErrorMsg(null);
    try {
      const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await fetch("/api/v1/documents/check-alerts", {
        method: "POST",
        headers,
      });
      if (res.ok) {
        const data = await res.json();
        setAlertResult(`Checked expiry dates: ${data.created_alerts_count} new alert(s) raised.`);
        fetchDocuments();
      } else {
        const err = await res.json().catch(() => ({}));
        setErrorMsg(err.detail || "Failed to check document alerts.");
      }
    } catch (err) {
      console.error(err);
      setErrorMsg("Network error checking document alerts.");
    } finally {
      setCheckingAlerts(false);
    }
  };

  // Filter in memory by search & status
  const filteredDocuments = documents.filter((doc) => {
    if (statusFilter !== "ALL" && doc.status !== statusFilter) return false;
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      doc.employee_name.toLowerCase().includes(q) ||
      doc.tally_id.toLowerCase().includes(q) ||
      doc.document_type.toLowerCase().includes(q) ||
      (doc.supervisor_name && doc.supervisor_name.toLowerCase().includes(q))
    );
  });

  // Export to CSV
  const exportCSV = () => {
    const headers = ["Worker Name", "Tally ID", "Role", "Document Type", "Expiry Date", "Days Remaining", "Status"];
    const rows = filteredDocuments.map((d) => [
      `"${d.employee_name}"`,
      `"${d.tally_id}"`,
      d.role,
      d.document_type,
      d.expiry_date,
      d.days_remaining,
      d.status,
    ]);
    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map((e) => e.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `expiring_documents_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900">Employee Documents & Expiries</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">
              {totalCount} Expiring / Expired
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-1">
            Monitor Visa, Emirates ID, Passport, and Labour Card validity with configurable lead-time alerts.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleCheckAlerts}
            disabled={checkingAlerts}
            className="flex items-center gap-2 px-3.5 py-2 text-sm font-medium bg-amber-600 text-white rounded-lg hover:bg-amber-700 shadow-sm disabled:opacity-50"
          >
            <Bell className={`h-4 w-4 ${checkingAlerts ? "animate-spin" : ""}`} />
            {checkingAlerts ? "Checking..." : "Check & Raise Alerts"}
          </button>
          <button
            onClick={exportCSV}
            disabled={filteredDocuments.length === 0}
            className="flex items-center gap-2 px-3.5 py-2 text-sm font-medium bg-white text-slate-700 border border-slate-300 rounded-lg hover:bg-slate-50 shadow-sm disabled:opacity-50"
          >
            <Download className="h-4 w-4 text-slate-500" />
            Export CSV
          </button>
          <button
            onClick={() => fetchDocuments()}
            className="flex items-center gap-2 px-3.5 py-2 text-sm font-medium bg-white text-slate-700 border border-slate-300 rounded-lg hover:bg-slate-50 shadow-sm"
          >
            <RefreshCw className={`h-4 w-4 text-slate-500 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Alerts / Feedback */}
      {errorMsg && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center justify-between">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg(null)} className="text-red-500 hover:text-red-800 font-bold">×</button>
        </div>
      )}
      {alertResult && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700 flex items-center justify-between">
          <span>{alertResult}</span>
          <button onClick={() => setAlertResult(null)} className="text-emerald-500 hover:text-emerald-800 font-bold">×</button>
        </div>
      )}

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-wrap items-center gap-4">
        <div className="flex-1 min-w-[240px] relative">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search worker name, tally ID, or document..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div className="flex items-center gap-3">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="ALL">All Document Types</option>
            <option value="EMIRATES_ID">Emirates ID</option>
            <option value="VISA">Visa</option>
            <option value="PASSPORT">Passport</option>
            <option value="LABOUR_CARD">Labour Card</option>
            <option value="DRIVING_LICENCE">Driving Licence</option>
            <option value="IQAMA">Iqama</option>
          </select>

          <select
            value={withinDays}
            onChange={(e) => setWithinDays(Number(e.target.value))}
            className="text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value={15}>Expiring in 15 days</option>
            <option value={30}>Expiring in 30 days</option>
            <option value={60}>Expiring in 60 days</option>
            <option value={90}>Expiring in 90 days</option>
            <option value={365}>All Upcoming (1 Year)</option>
          </select>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-sm border border-slate-200 rounded-lg px-3 py-2 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="ALL">All Statuses</option>
            <option value="EXPIRING">Expiring Soon</option>
            <option value="EXPIRED">Already Expired</option>
            <option value="OK">Valid / OK</option>
          </select>
        </div>
      </div>

      {/* Documents Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-700">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-600 uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3.5">Employee</th>
                <th className="px-6 py-3.5">Role</th>
                <th className="px-6 py-3.5">Document Type</th>
                <th className="px-6 py-3.5">Expiry Date</th>
                <th className="px-6 py-3.5">Remaining</th>
                <th className="px-6 py-3.5">Status</th>
                <th className="px-6 py-3.5">Supervisor</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-slate-400">
                    Loading employee documents...
                  </td>
                </tr>
              ) : filteredDocuments.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-slate-400">
                    No documents found matching the filter criteria.
                  </td>
                </tr>
              ) : (
                filteredDocuments.map((doc) => (
                  <tr key={doc.document_id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="font-semibold text-slate-900">{doc.employee_name}</div>
                      <div className="text-xs text-slate-400 font-mono">Tally: {doc.tally_id}</div>
                    </td>
                    <td className="px-6 py-4 text-slate-600 text-xs font-medium">
                      {doc.role}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <FileText className="h-4 w-4 text-slate-400" />
                        <span className="font-medium text-slate-800">{doc.document_type.replace(/_/g, " ")}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-slate-600 font-mono text-xs">
                      {doc.expiry_date}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`font-semibold text-xs ${
                          doc.days_remaining < 0
                            ? "text-red-600"
                            : doc.days_remaining <= 30
                            ? "text-amber-600"
                            : "text-emerald-600"
                        }`}
                      >
                        {doc.days_remaining < 0
                          ? `${Math.abs(doc.days_remaining)} days overdue`
                          : `${doc.days_remaining} days left`}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${
                          doc.status === "EXPIRED"
                            ? "bg-red-100 text-red-800"
                            : doc.status === "EXPIRING"
                            ? "bg-amber-100 text-amber-800"
                            : "bg-emerald-100 text-emerald-800"
                        }`}
                      >
                        {doc.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-500 text-xs">
                      {doc.supervisor_name || "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

