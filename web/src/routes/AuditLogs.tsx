import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { RefreshCw } from "lucide-react";

interface AuditLogEntry {
  id: number;
  actor_user_id: string | null;
  actor_role: string | null;
  actor_name: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  entity_label: string | null;
  diff: Record<string, any>;
  diff_labels: Record<string, string>;
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

  const renderDiff = (diff: Record<string, any>, labels: Record<string, string> = {}) => {
    const entries = Object.entries(diff || {});
    if (entries.length === 0) return <span className="text-slate-400 text-xs">—</span>;

    return (
      <div className="space-y-1.5 text-xs max-w-md">
        <div className="space-y-1">
          {entries.map(([key, val]) => {
            const friendlyLabel = labels[key];
            const displayKey = key
              .replace(/_/g, " ")
              .replace(/\bid\b/i, "ID")
              .replace(/\b\w/g, (c) => c.toUpperCase());

            return (
              <div key={key} className="flex flex-col sm:flex-row sm:items-baseline gap-1.5 text-[11px] leading-tight">
                <span className="font-semibold text-slate-600 shrink-0">{displayKey}:</span>
                {friendlyLabel ? (
                  <span
                    className="font-medium text-indigo-800 bg-indigo-50/90 px-1.5 py-0.5 rounded border border-indigo-200/80 break-words"
                    title={String(val)}
                  >
                    {friendlyLabel}
                  </span>
                ) : (
                  <span className="font-mono text-slate-800 break-words">
                    {typeof val === "object" ? JSON.stringify(val) : String(val)}
                  </span>
                )}
              </div>
            );
          })}
        </div>
        <details className="text-[10px] text-slate-400 cursor-pointer pt-1 border-t border-slate-100">
          <summary className="hover:text-slate-600 font-mono select-none">Raw JSON</summary>
          <pre className="mt-1 p-2 bg-slate-900 text-slate-200 rounded text-[10px] font-mono overflow-x-auto max-h-36">
            {JSON.stringify(diff, null, 2)}
          </pre>
        </details>
      </div>
    );
  };

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
          <option value="StandingAssignment">Standing Assignment</option>
          <option value="ScheduledWork">Scheduled Work</option>
          <option value="employee_reporting_line">Reporting Line</option>
          <option value="employee_document">Document</option>
          <option value="registered_device">Registered Device</option>
          <option value="accommodation">Accommodation</option>
          <option value="worksite">Worksite</option>
          <option value="job_item">Job Item</option>
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
                  <td className="p-4">
                    <span className="font-bold text-xs uppercase px-2 py-0.5 rounded bg-slate-100 text-slate-800 border border-slate-200">
                      {log.action}
                    </span>
                  </td>
                  <td className="p-4 text-xs max-w-xs">
                    <span className="font-semibold text-slate-900 text-xs">
                      {log.entity_type}
                    </span>
                    {log.entity_label && (
                      <div className="font-medium text-indigo-700 text-xs mt-0.5 leading-snug" title={log.entity_label}>
                        {log.entity_label}
                      </div>
                    )}
                    <div className="font-mono text-[10px] text-slate-400 truncate max-w-[170px] mt-0.5" title={log.entity_id}>
                      {log.entity_id}
                    </div>
                  </td>
                  <td className="p-4 text-xs">
                    <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                      {log.actor_role || "SYSTEM"}
                    </span>
                    {log.actor_name && (
                      <div className="font-medium text-slate-800 text-xs mt-1" title={log.actor_name}>
                        {log.actor_name}
                      </div>
                    )}
                    {log.ip && (
                      <div className="font-mono text-[10px] text-slate-400 mt-0.5">
                        {log.ip}
                      </div>
                    )}
                  </td>
                  <td className="p-4 text-xs text-slate-500">{log.reason || "—"}</td>
                  <td className="p-4">
                    {renderDiff(log.diff, log.diff_labels)}
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
