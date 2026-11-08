import React, { useState, useEffect } from "react";
import {
  Smartphone,
  RotateCcw,
  Search,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  ShieldAlert,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

interface DeviceStatus {
  device_id: string;
  employee_id: string;
  tally_id: string;
  employee_name: string;
  platform: string;
  device_model: string | null;
  app_version: string | null;
  os_version: string | null;
  last_seen_at: string | null;
  last_acked_cursor: number;
  current_cursor: number;
  sync_lag: number;
  location_permission_state: string | null;
  is_active: boolean;
  revoked_at: string | null;
}

export const Devices: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === "ADMIN";

  const [devices, setDevices] = useState<DeviceStatus[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [resettingId, setResettingId] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const fetchDevices = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem("fwt_token");
      const res = await fetch("/api/v1/devices", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        throw new Error("Failed to fetch devices");
      }
      const data: DeviceStatus[] = await res.json();
      setDevices(data);
    } catch (err: any) {
      setMessage({ type: "error", text: err.message || "Failed to load devices" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDevices();
  }, []);

  const handleResetBinding = async (deviceId: string, employeeName: string) => {
    if (
      !window.confirm(
        `Are you sure you want to reset the device binding for ${employeeName}? They will be able to bind a new device on their next login.`
      )
    ) {
      return;
    }

    try {
      setResettingId(deviceId);
      const token = localStorage.getItem("fwt_token");
      const res = await fetch(`/api/v1/devices/${deviceId}/reset`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to reset device binding");
      }

      setMessage({
        type: "success",
        text: `Device binding for ${employeeName} has been successfully reset.`,
      });
      await fetchDevices();
    } catch (err: any) {
      setMessage({ type: "error", text: err.message || "Could not reset device" });
    } finally {
      setResettingId(null);
    }
  };

  const filteredDevices = devices.filter((d) => {
    const q = searchTerm.toLowerCase();
    return (
      d.tally_id.toLowerCase().includes(q) ||
      d.employee_name.toLowerCase().includes(q) ||
      (d.device_model && d.device_model.toLowerCase().includes(q)) ||
      d.platform.toLowerCase().includes(q)
    );
  });

  const activeCount = devices.filter((d) => d.is_active).length;
  const laggingCount = devices.filter((d) => d.is_active && d.sync_lag > 0).length;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Smartphone className="w-7 h-7 text-emerald-600" />
            Registered Devices & Sync Lag
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Monitor mobile client synchronization, sync lag, client versions, and reset device
            bindings.
          </p>
        </div>
        <button
          onClick={fetchDevices}
          className="inline-flex items-center gap-2 px-3.5 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition"
        >
          <RotateCcw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {message && (
        <div
          className={`p-4 rounded-lg flex items-center justify-between ${
            message.type === "success"
              ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
              : "bg-rose-50 text-rose-800 border border-rose-200"
          }`}
        >
          <div className="flex items-center gap-2">
            {message.type === "success" ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            ) : (
              <AlertTriangle className="w-5 h-5 text-rose-600" />
            )}
            <span className="text-sm font-medium">{message.text}</span>
          </div>
          <button
            onClick={() => setMessage(null)}
            className="text-slate-400 hover:text-slate-600 text-sm"
          >
            ✕
          </button>
        </div>
      )}

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-center gap-4">
          <div className="p-3 bg-emerald-50 rounded-lg text-emerald-600">
            <Smartphone className="w-6 h-6" />
          </div>
          <div>
            <div className="text-sm text-slate-500 font-medium">Active Devices</div>
            <div className="text-2xl font-bold text-slate-900">{activeCount}</div>
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-center gap-4">
          <div className="p-3 bg-amber-50 rounded-lg text-amber-600">
            <Clock className="w-6 h-6" />
          </div>
          <div>
            <div className="text-sm text-slate-500 font-medium">Pending Sync Lag</div>
            <div className="text-2xl font-bold text-amber-600">{laggingCount}</div>
          </div>
        </div>

        <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm flex items-center gap-4">
          <div className="p-3 bg-slate-50 rounded-lg text-slate-600">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <div className="text-sm text-slate-500 font-medium">Total Registered Records</div>
            <div className="text-2xl font-bold text-slate-900">{devices.length}</div>
          </div>
        </div>
      </div>

      {/* Filter & Table */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-200 bg-slate-50/50 flex flex-col sm:flex-row gap-3 items-center justify-between">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by worker, ID, model..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-sm bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            />
          </div>
          <div className="text-xs text-slate-500">
            Showing {filteredDevices.length} of {devices.length} devices
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-slate-600 font-semibold text-xs uppercase tracking-wider">
                <th className="py-3 px-4">Worker</th>
                <th className="py-3 px-4">Platform & Model</th>
                <th className="py-3 px-4">App / OS</th>
                <th className="py-3 px-4">Location Permission</th>
                <th className="py-3 px-4">Last Seen</th>
                <th className="py-3 px-4">Cursor (Acked / Max)</th>
                <th className="py-3 px-4">Sync Lag</th>
                <th className="py-3 px-4">Status</th>
                {isAdmin && <th className="py-3 px-4 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={isAdmin ? 9 : 8} className="py-10 text-center text-slate-400">
                    Loading registered devices...
                  </td>
                </tr>
              ) : filteredDevices.length === 0 ? (
                <tr>
                  <td colSpan={isAdmin ? 9 : 8} className="py-10 text-center text-slate-400">
                    No devices found matching your criteria.
                  </td>
                </tr>
              ) : (
                filteredDevices.map((d) => (
                  <tr key={d.device_id} className="hover:bg-slate-50/80 transition">
                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-900">{d.employee_name}</div>
                      <div className="text-xs text-slate-500 font-mono">ID: {d.tally_id}</div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`text-xs px-2 py-0.5 rounded font-medium ${
                            d.platform === "ANDROID"
                              ? "bg-emerald-100 text-emerald-800"
                              : "bg-sky-100 text-sky-800"
                          }`}
                        >
                          {d.platform}
                        </span>
                        <span className="text-slate-700">{d.device_model || "Generic"}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-600">
                      <div>v{d.app_version || "1.0.0"}</div>
                      <div className="text-slate-400">OS: {d.os_version || "N/A"}</div>
                    </td>
                    <td className="py-3 px-4 text-xs">
                      <span
                        className={`inline-block px-2 py-0.5 rounded font-medium ${
                          d.location_permission_state === "ALWAYS"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : d.location_permission_state === "WHILE_IN_USE"
                              ? "bg-amber-50 text-amber-700 border border-amber-200"
                              : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {d.location_permission_state || "UNKNOWN"}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-500">
                      {d.last_seen_at ? new Date(d.last_seen_at).toLocaleString() : "Never"}
                    </td>
                    <td className="py-3 px-4 text-xs font-mono">
                      <span className="text-slate-900 font-semibold">{d.last_acked_cursor}</span>
                      <span className="text-slate-400"> / {d.current_cursor}</span>
                    </td>
                    <td className="py-3 px-4">
                      {d.sync_lag === 0 ? (
                        <span className="inline-flex items-center gap-1 text-xs text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded font-medium">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                          In Sync
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs text-amber-700 bg-amber-50 px-2 py-0.5 rounded font-medium border border-amber-200">
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
                          {d.sync_lag} pending
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      {d.is_active ? (
                        <span className="inline-flex items-center gap-1 text-xs text-emerald-700 font-medium">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                          Active Binding
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs text-rose-600 font-medium">
                          <XCircle className="w-3.5 h-3.5 text-rose-500" />
                          Revoked
                        </span>
                      )}
                    </td>
                    {isAdmin && (
                      <td className="py-3 px-4 text-right">
                        {d.is_active ? (
                          <button
                            onClick={() => handleResetBinding(d.device_id, d.employee_name)}
                            disabled={resettingId === d.device_id}
                            className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-rose-700 bg-rose-50 border border-rose-200 rounded hover:bg-rose-100 transition disabled:opacity-50"
                          >
                            <RotateCcw className="w-3 h-3" />
                            {resettingId === d.device_id ? "Resetting..." : "Reset Binding"}
                          </button>
                        ) : (
                          <span className="text-xs text-slate-400 italic">Unbound</span>
                        )}
                      </td>
                    )}
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
