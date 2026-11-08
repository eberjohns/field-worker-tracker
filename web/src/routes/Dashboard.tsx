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
  const [pendingBoundaryCount, setPendingBoundaryCount] = useState<number>(0);

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

        if (user?.role === "ADMIN" || user?.role === "ENGINEER") {
          const bRes = await fetch("/api/v1/boundary-queue?status=UNSET", { headers });
          if (bRes.ok) {
            const bData = await bRes.json();
            setPendingBoundaryCount(bData.unset_count ?? bData.total_count ?? 0);
          }
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
              <div className="flex items-center gap-3 pt-1">
                <Link
                  to="/operational-planner"
                  className="inline-flex items-center gap-1 text-xs font-bold text-rose-800 hover:text-rose-950"
                >
                  Operational Planner <ArrowRight className="h-3 w-3" />
                </Link>
                {(user?.role === "ADMIN" || user?.role === "ENGINEER") && (
                  <Link
                    to="/approvals"
                    className="inline-flex items-center gap-1 text-xs font-bold text-indigo-700 hover:text-indigo-900"
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
    </div>
  );
};
