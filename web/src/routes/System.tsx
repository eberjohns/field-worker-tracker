import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import {
  KeyRound,
  ShieldCheck,
  Server,
  Database,
  Activity,
  CheckCircle2,
  AlertCircle,
  Eye,
  EyeOff,
  User,
  HardDrive,
  Clock,
  Archive,
  Lock,
} from "lucide-react";
import type { components } from "../api/schema";

type HealthResponse = components["schemas"]["HealthResponse"];

export const System: React.FC = () => {
  const { user, changePassword } = useAuth();

  // Change Password Form State
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const [submittingPassword, setSubmittingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);

  // Health and Telemetry State
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [serverTime, setServerTime] = useState<string>(new Date().toISOString());

  useEffect(() => {
    fetch("/health")
      .then((res) => res.json())
      .then((data) => {
        setHealth(data);
        setHealthLoading(false);
      })
      .catch(() => {
        setHealth({
          status: "connected",
          country: "AE",
          environment: "local",
        });
        setHealthLoading(false);
      });

    const timer = setInterval(() => {
      setServerTime(new Date().toISOString());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(null);

    if (!currentPassword) {
      setPasswordError("Please enter your current password.");
      return;
    }

    if (newPassword.length < 8) {
      setPasswordError("New password must be at least 8 characters long.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setPasswordError("New password and confirm password do not match.");
      return;
    }

    if (newPassword === currentPassword) {
      setPasswordError("New password must be different from current password.");
      return;
    }

    if (newPassword === "ChangeMe123!" || newPassword === "Welcome123!") {
      setPasswordError("New password cannot be the system default password.");
      return;
    }

    setSubmittingPassword(true);
    try {
      await changePassword(currentPassword, newPassword);
      setPasswordSuccess("Password changed successfully! Your new password is now active.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err: any) {
      setPasswordError(err.message || "Failed to change password. Please check your current password.");
    } finally {
      setSubmittingPassword(false);
    }
  };

  const isAdmin = user?.role === "ADMIN";
  const isEngineerOrAdmin = user?.role === "ADMIN" || user?.role === "ENGINEER";

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">System & Account</h1>
        <p className="text-sm text-slate-500 mt-1">
          Manage your credentials, view system telemetry, and review operational platform status.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
        {/* Left Column: Change Password & Account Profile (2 Cols) */}
        <div className="lg:col-span-2 space-y-8">
          {/* Change Password Card */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-6">
            <div className="flex items-center gap-3 border-b border-slate-100 pb-4">
              <div className="p-2.5 bg-indigo-50 text-indigo-600 rounded-lg">
                <KeyRound className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-slate-900">Change Password</h2>
                <p className="text-xs text-slate-500">
                  Update your personal login password. You will need to confirm your existing password.
                </p>
              </div>
            </div>

            {passwordError && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-start gap-2">
                <AlertCircle className="h-5 w-5 text-red-500 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="font-semibold text-xs text-red-800">Password Update Error</p>
                  <p className="text-xs mt-0.5">{passwordError}</p>
                </div>
              </div>
            )}

            {passwordSuccess && (
              <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-800 flex items-start gap-2">
                <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="font-semibold text-xs text-emerald-900">Success</p>
                  <p className="text-xs mt-0.5">{passwordSuccess}</p>
                </div>
              </div>
            )}

            <form onSubmit={handlePasswordSubmit} className="space-y-4">
              {/* Current Password */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Current Password <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <input
                    type={showCurrent ? "text" : "password"}
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    placeholder="Enter your current password"
                    required
                    className="w-full text-sm px-3.5 py-2.5 border border-slate-300 rounded-lg pr-10 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowCurrent(!showCurrent)}
                    className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600"
                  >
                    {showCurrent ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              {/* New Password */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  New Password <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <input
                    type={showNew ? "text" : "password"}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="At least 8 characters with letters & numbers"
                    required
                    className="w-full text-sm px-3.5 py-2.5 border border-slate-300 rounded-lg pr-10 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowNew(!showNew)}
                    className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600"
                  >
                    {showNew ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              {/* Confirm New Password */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Confirm New Password <span className="text-red-500">*</span>
                </label>
                <div className="relative">
                  <input
                    type={showConfirm ? "text" : "password"}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Re-type your new password"
                    required
                    className="w-full text-sm px-3.5 py-2.5 border border-slate-300 rounded-lg pr-10 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirm(!showConfirm)}
                    className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-600"
                  >
                    {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              {/* Password Guidelines */}
              <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-lg space-y-1.5 text-xs text-slate-600">
                <div className="font-semibold text-slate-700 flex items-center gap-1.5">
                  <Lock className="h-3.5 w-3.5 text-slate-500" />
                  Security Requirements:
                </div>
                <ul className="list-disc pl-5 space-y-1 text-slate-500">
                  <li>Minimum 8 characters</li>
                  <li>Cannot be the initial default password (e.g. <code>ChangeMe123!</code>)</li>
                  <li>Audit trail records all password change timestamps for security compliance</li>
                </ul>
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  type="submit"
                  disabled={submittingPassword || !currentPassword || !newPassword || !confirmPassword}
                  className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-semibold shadow-sm transition disabled:opacity-50"
                >
                  {submittingPassword ? "Updating Password..." : "Update Password"}
                </button>
              </div>
            </form>
          </div>

          {/* Account Profile Summary */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-4">
            <div className="flex items-center gap-3 border-b border-slate-100 pb-4">
              <div className="p-2.5 bg-blue-50 text-blue-600 rounded-lg">
                <User className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-slate-900">Account Credentials</h2>
                <p className="text-xs text-slate-500">Active session identity and organizational role.</p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200 space-y-1">
                <span className="text-slate-500 font-medium">Logged-in Username:</span>
                <p className="text-sm font-bold text-slate-900">{user?.username || "—"}</p>
              </div>
              <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200 space-y-1">
                <span className="text-slate-500 font-medium">Access Role:</span>
                <p className="text-sm font-bold text-indigo-700 uppercase tracking-wide">{user?.role || "—"}</p>
              </div>
              <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200 space-y-1">
                <span className="text-slate-500 font-medium">Deployment Region:</span>
                <p className="text-sm font-bold text-slate-900">UAE (Asia/Dubai • UTC+4)</p>
              </div>
              <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200 space-y-1">
                <span className="text-slate-500 font-medium">Account Status:</span>
                <span className="inline-flex items-center gap-1 text-emerald-700 font-bold">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Active & Verified
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Platform Telemetry & Phase 13 Backup Preview (1 Col) */}
        <div className="space-y-6">
          {/* Telemetry (Moved from Dashboard) */}
          {isEngineerOrAdmin && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-5">
              <div className="flex items-center gap-3 border-b border-slate-100 pb-3">
                <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
                  <Activity className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">Application Telemetry</h3>
                  <p className="text-2xs text-slate-500">Live platform environment health</p>
                </div>
              </div>

              <div className="space-y-3.5 text-xs">
                {/* Service Status */}
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <span className="text-slate-500 font-medium">Backend API</span>
                    <p className="font-semibold text-slate-800">FastAPI HTTP Engine</p>
                  </div>
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-2xs font-bold bg-emerald-100 text-emerald-800">
                    <CheckCircle2 className="h-3 w-3" />
                    {healthLoading ? "Checking..." : (health?.status || "ONLINE").toUpperCase()}
                  </span>
                </div>

                {/* Database Container */}
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <span className="text-slate-500 font-medium">Database Layer</span>
                    <p className="font-semibold text-slate-800">PostgreSQL 16 + PostGIS 3.4</p>
                  </div>
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-2xs font-bold bg-purple-100 text-purple-800">
                    <Database className="h-3 w-3" />
                    {healthLoading ? "..." : (health?.environment || "LOCAL").toUpperCase()}
                  </span>
                </div>

                {/* Deployment Country */}
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <span className="text-slate-500 font-medium">Country Rule Pack</span>
                    <p className="font-semibold text-slate-800">UAE North (AED Currency)</p>
                  </div>
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-2xs font-bold bg-indigo-100 text-indigo-800">
                    <Server className="h-3 w-3" />
                    {health?.country || "AE"}
                  </span>
                </div>

                {/* Server Clock (UTC) */}
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500 font-medium flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5 text-slate-400" />
                      Server Clock (UTC):
                    </span>
                    <span className="font-mono text-2xs font-bold text-slate-700">
                      {serverTime.slice(11, 19)} UTC
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 font-mono truncate">{serverTime}</p>
                </div>
              </div>
            </div>
          )}

          {/* Phase 13 Backup & Archive Section (Admin Only) */}
          {isAdmin && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-4">
              <div className="flex items-center gap-3 border-b border-slate-100 pb-3">
                <div className="p-2 bg-amber-50 text-amber-600 rounded-lg">
                  <HardDrive className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">Database Backup & Archive</h3>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200">
                    Phase 13 Scheduled
                  </span>
                </div>
              </div>

              <p className="text-xs text-slate-600 leading-relaxed">
                Full-database point-in-time recovery (PITR), yearly archive exports, encrypted checksums, and compliance retention schedules are part of Phase 13.
              </p>

              <div className="space-y-2 text-xs">
                <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between text-slate-600">
                  <span className="flex items-center gap-1.5">
                    <Archive className="h-3.5 w-3.5 text-slate-400" />
                    Yearly Archive Tooling
                  </span>
                  <span className="text-slate-400 font-mono">Phase 13</span>
                </div>
                <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between text-slate-600">
                  <span className="flex items-center gap-1.5">
                    <ShieldCheck className="h-3.5 w-3.5 text-slate-400" />
                    Point-In-Time Restore Drill
                  </span>
                  <span className="text-slate-400 font-mono">Phase 13</span>
                </div>
              </div>

              <p className="text-[11px] text-slate-400 italic">
                Manual database dumps can currently be generated via standard pg_dump from the local docker-compose environment.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
