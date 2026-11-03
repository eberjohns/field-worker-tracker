import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { KeyRound, CheckCircle, AlertCircle, RefreshCw } from "lucide-react";

interface UserItem {
  id: string;
  employee_id: string;
  username: string;
  role: string;
  is_active: boolean;
  must_change_password: boolean;
  last_login_at: string | null;
  version: number;
}

export const UsersAdmin: React.FC = () => {
  const { token, user } = useAuth();
  const [users, setUsers] = useState<UserItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/users", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setUsers(await res.json());
      }
    } catch (err: any) {
      setErrorMessage("Failed to load users");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user?.role === "ADMIN") {
      fetchUsers();
    }
  }, [user]);

  const handleResetPassword = async (userId: string, username: string) => {
    if (!window.confirm(`Reset password for user '${username}' to company default?`)) return;
    setStatusMessage(null);
    setErrorMessage(null);

    try {
      const res = await fetch(`/api/v1/users/${userId}/reset-password`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Reset failed");
      setStatusMessage(`Password for user '${username}' has been reset to company default.`);
      fetchUsers();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to reset password");
    }
  };

  if (user?.role !== "ADMIN") {
    return <div className="p-8 text-center text-red-600">Access Restricted to Administrators.</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">User Accounts Administration</h2>
          <p className="text-sm text-slate-500 mt-1">Manage system logins, roles, and password resets</p>
        </div>
        <button
          onClick={fetchUsers}
          className="p-2 border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-600"
          title="Refresh"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {statusMessage && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700 flex items-center gap-2">
          <CheckCircle className="h-4 w-4" />
          {statusMessage}
        </div>
      )}
      {errorMessage && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center gap-2">
          <AlertCircle className="h-4 w-4" />
          {errorMessage}
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
        {loading ? (
          <div className="p-12 text-center text-slate-500 text-sm">Loading users...</div>
        ) : (
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold uppercase text-slate-500">
              <tr>
                <th className="p-4">Username (Tally ID)</th>
                <th className="p-4">Role</th>
                <th className="p-4">Default Password Flag</th>
                <th className="p-4">Last Login</th>
                <th className="p-4">Account Status</th>
                <th className="p-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-slate-50 transition">
                  <td className="p-4 font-mono font-medium text-slate-900">{u.username}</td>
                  <td className="p-4">
                    <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
                      {u.role}
                    </span>
                  </td>
                  <td className="p-4">
                    {u.must_change_password ? (
                      <span className="px-2 py-0.5 rounded text-xs bg-amber-100 text-amber-800 font-medium">
                        Must Change (Default)
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded text-xs bg-emerald-100 text-emerald-800 font-medium">
                        Changed
                      </span>
                    )}
                  </td>
                  <td className="p-4 text-xs text-slate-500">
                    {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "Never"}
                  </td>
                  <td className="p-4">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                        u.is_active ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"
                      }`}
                    >
                      {u.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="p-4 text-right">
                    <button
                      onClick={() => handleResetPassword(u.id, u.username)}
                      className="px-3 py-1.5 bg-slate-100 hover:bg-amber-50 text-slate-700 hover:text-amber-800 border border-slate-200 rounded-lg text-xs font-medium inline-flex items-center gap-1.5 transition"
                    >
                      <KeyRound className="h-3.5 w-3.5" /> Reset to Default
                    </button>
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
