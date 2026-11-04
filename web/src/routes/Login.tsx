import React, { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { Lock, User as UserIcon, ShieldAlert, CheckCircle2 } from "lucide-react";

export const Login: React.FC = () => {
  const { login, changePassword, user, isAuthenticated, logout } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Forced password change state
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [changeError, setChangeError] = useState<string | null>(null);
  const [changeSuccess, setChangeSuccess] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username, password);
      window.location.href = "/";
    } catch (err: any) {
      setError(err.message || "Failed to log in");
    } finally {
      setLoading(false);
    }
  };

  const handleForceChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setChangeError(null);
    if (newPassword !== confirmPassword) {
      setChangeError("Passwords do not match.");
      return;
    }
    if (newPassword.length < 8) {
      setChangeError("New password must be at least 8 characters long.");
      return;
    }

    setLoading(true);
    try {
      await changePassword(password, newPassword);
      setChangeSuccess(true);
      setTimeout(() => {
        window.location.href = "/";
      }, 1000);
    } catch (err: any) {
      setChangeError(err.message || "Failed to change password");
    } finally {
      setLoading(false);
    }
  };

  if (isAuthenticated && user?.must_change_password) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
        <div className="sm:mx-auto sm:w-full sm:max-w-md">
          <div className="bg-amber-500 h-12 w-12 rounded-xl flex items-center justify-center text-white mx-auto shadow-sm">
            <ShieldAlert className="h-6 w-6" />
          </div>
          <h2 className="mt-4 text-center text-2xl font-bold tracking-tight text-slate-900">
            Password Change Required
          </h2>
          <p className="mt-2 text-center text-sm text-slate-600">
            You are logged in with the temporary default password. Please choose a new secure password to proceed.
          </p>
        </div>

        <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
          <div className="bg-white py-8 px-6 shadow-sm rounded-xl border border-slate-200 sm:px-10">
            {changeError && (
              <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
                {changeError}
              </div>
            )}
            {changeSuccess && (
              <div className="mb-4 p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-sm text-emerald-700 flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4" />
                Password changed successfully! Redirecting...
              </div>
            )}

            <form onSubmit={handleForceChange} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">New Password</label>
                <input
                  type="password"
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="At least 8 characters"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Confirm New Password</label>
                <input
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="Repeat new password"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 transition disabled:opacity-50"
              >
                {loading ? "Updating..." : "Save Password & Continue"}
              </button>

              <button
                type="button"
                onClick={logout}
                className="w-full text-center text-xs text-slate-500 hover:text-slate-800 pt-2"
              >
                Cancel & Sign Out
              </button>
            </form>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-indigo-600 h-12 w-12 rounded-xl flex items-center justify-center text-white mx-auto font-bold text-xl shadow-sm">
          FW
        </div>
        <h2 className="mt-4 text-center text-2xl font-bold tracking-tight text-slate-900">
          Field Worker Tracker
        </h2>
        <p className="mt-1 text-center text-sm text-slate-500">Sign in with your Worker or Employee ID</p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-6 shadow-sm rounded-xl border border-slate-200 sm:px-10">
          {error && (
            <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
              {error}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Worker / Employee ID</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <UserIcon className="h-4 w-4" />
                </div>
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="pl-9 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="e.g. ADMIN001 or WRK001"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Password</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-9 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="••••••••"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 transition disabled:opacity-50"
            >
              {loading ? "Signing in..." : "Sign in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

