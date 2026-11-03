import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { RefreshCw } from "lucide-react";

interface AuditLogEntry {
  id: number;
  actor_user_id: string | null;
  actor_role: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  diff: Record<string, any>;
  reason: string | null;
  ip: string | null;
  created_at: string;
}

export const AuditLogs: React.FC = () => {
  const { token, user } = useAuth();
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [entityTypeFilter, setEntityTypeFilter] = useState("");

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (entityTypeFilter) params.set("entity_type", entityTypeFilter);

      const res = await fetch(`/api/v1/audit-logs?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setLogs(await res.json());
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user?.role === "ADMIN") {
      fetchLogs();
    }
  }, [user, entityTypeFilter]);

  if (user?.role !== "ADMIN") {
    return <div className="p-8 text-center text-red-600">Access Restricted to Administrators.</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">System Audit Trail</h2>
          <p className="text-sm text-slate-500 mt-1">
            Immutable log of state-changing operations and security events (docs/07-data-model.md)
          </p>
        </div>
        <button
          onClick={fetchLogs}
          className="p-2 border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-600"
          title="Refresh"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {/* Filter Bar */}
      <div className="flex items-center gap-4 bg-white p-4 rounded-xl border border-slate-200">
        <select
          value={entityTypeFilter}
          onChange={(e) => setEntityTypeFilter(e.target.value)}
          className="border border-slate-200 rounded-lg text-sm px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
        >
          <option value="">All Entity Types</option>
          <option value="employee">Employee</option>
          <option value="user">User</option>
          <option value="employee_reporting_line">Reporting Line</option>
          <option value="employee_document">Document</option>
          <option value="registered_device">Registered Device</option>
          <option value="accommodation">Accommodation</option>
          <option value="group">Group</option>
          <option value="zone">Zone</option>
        </select>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
        {loading ? (
          <div className="p-12 text-center text-slate-500 text-sm">Loading audit logs...</div>
        ) : logs.length === 0 ? (
          <div className="p-12 text-center text-slate-500 text-sm">No audit logs recorded yet.</div>
        ) : (
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold uppercase text-slate-500">
              <tr>
                <th className="p-4">Time (UTC)</th>
                <th className="p-4">Action</th>
                <th className="p-4">Entity</th>
                <th className="p-4">Actor</th>
                <th className="p-4">Reason</th>
                <th className="p-4">Changes (Diff)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {logs.map((log) => (
                <tr key={log.id} className="hover:bg-slate-50 transition items-start">
                  <td className="p-4 text-xs font-mono text-slate-500 whitespace-nowrap">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td className="p-4 font-semibold text-slate-800 text-xs">{log.action}</td>
                  <td className="p-4 text-xs">
                    <span className="font-medium text-slate-900">{log.entity_type}</span>
                    <div className="font-mono text-[11px] text-slate-400 truncate max-w-[150px]">
                      {log.entity_id}
                    </div>
                  </td>
                  <td className="p-4 text-xs">
                    <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-700">
                      {log.actor_role || "SYSTEM"}
                    </span>
                  </td>
                  <td className="p-4 text-xs text-slate-500">{log.reason || "—"}</td>
                  <td className="p-4">
                    <pre className="p-2 bg-slate-50 border border-slate-200 rounded text-[11px] font-mono text-slate-700 max-h-24 overflow-y-auto">
                      {JSON.stringify(log.diff, null, 2)}
                    </pre>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
