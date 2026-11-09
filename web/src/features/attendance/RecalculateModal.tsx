import React, { useState } from "react";
import { X, RefreshCw, AlertCircle } from "lucide-react";
import { useAuth } from "../../context/AuthContext";

interface RecalculateModalProps {
  open: boolean;
  onClose: () => void;
  onRecalculated: () => void;
}

export const RecalculateModal: React.FC<RecalculateModalProps> = ({
  open,
  onClose,
  onRecalculated,
}) => {
  const { token } = useAuth();
  const [fromDate, setFromDate] = useState<string>(
    new Date().toISOString().split("T")[0]
  );
  const [toDate, setToDate] = useState<string>(
    new Date().toISOString().split("T")[0]
  );
  const [employeeId, setEmployeeId] = useState<string>("");
  const [reason, setReason] = useState<string>("MANUAL_TRIGGER");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successCount, setSuccessCount] = useState<number | null>(null);

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccessCount(null);

    try {
      const res = await fetch("/api/v1/attendance/recalculate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          from_date: fromDate,
          to_date: toDate,
          employee_id: employeeId.trim() || undefined,
          reason,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setSuccessCount(data.recalculated_count);
        setTimeout(() => {
          onRecalculated();
          onClose();
        }, 1200);
      } else {
        const err = await res.json();
        setError(err.detail || "Recalculation failed.");
      }
    } catch {
      setError("Network error triggering recalculation.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-md w-full overflow-hidden border border-slate-200">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-2">
            <RefreshCw className="h-4 w-4 text-emerald-600" />
            <h3 className="font-semibold text-slate-900 text-sm">Recalculate Attendance</h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4 text-xs">
          {error && (
            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {successCount !== null && (
            <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 font-medium">
              Successfully recalculated {successCount} attendance record(s).
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-700 font-medium mb-1">From Date</label>
              <input
                type="date"
                required
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                className="w-full p-2 border border-slate-300 rounded-lg focus:ring-1 focus:ring-emerald-500"
              />
            </div>
            <div>
              <label className="block text-slate-700 font-medium mb-1">To Date</label>
              <input
                type="date"
                required
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                className="w-full p-2 border border-slate-300 rounded-lg focus:ring-1 focus:ring-emerald-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-slate-700 font-medium mb-1">
              Employee ID (optional, blank for all)
            </label>
            <input
              type="text"
              placeholder="e.g. UUID or leave blank"
              value={employeeId}
              onChange={(e) => setEmployeeId(e.target.value)}
              className="w-full p-2 border border-slate-300 rounded-lg focus:ring-1 focus:ring-emerald-500 font-mono"
            />
          </div>

          <div>
            <label className="block text-slate-700 font-medium mb-1">Reason for Recalculation</label>
            <select
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full p-2 border border-slate-300 rounded-lg bg-white"
            >
              <option value="MANUAL_TRIGGER">Manual Admin Trigger</option>
              <option value="RULE_CHANGE">Rule / Policy Change</option>
              <option value="BOUNDARY_UPDATE">Worksite Polygon Boundary Update</option>
            </select>
          </div>

          <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-[11px] text-slate-500">
            Note: Records locked by approved payroll will be flagged as <span className="font-mono text-slate-700">POST_FINALIZATION</span> and will not overwrite finalized attendance snapshots.
          </div>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-2 text-slate-600 hover:text-slate-800 font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium transition-colors flex items-center gap-1.5 disabled:opacity-50"
            >
              {loading && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
              Start Recalculation
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

