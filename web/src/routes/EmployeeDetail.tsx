import React, { useState, useEffect } from "react";
import { useParams, Link } from "@tanstack/react-router";
import { useAuth } from "../context/AuthContext";
import {
  User as UserIcon,
  GitFork,
  FileText,
  Smartphone,
  History,
  ArrowLeft,
  KeyRound,
  Trash2,
  Plus,
  AlertCircle,
  CheckCircle,
  DollarSign,
  TrendingUp,
  TrendingDown,
} from "lucide-react";

export const EmployeeDetail: React.FC = () => {
  const { employeeId } = useParams({ strict: false }) as { employeeId: string };
  const { token, user } = useAuth();

  const [employee, setEmployee] = useState<any>(null);
  const [accommodations, setAccommodations] = useState<any[]>([]);
  const [reportingLines, setReportingLines] = useState<any[]>([]);
  const [documents, setDocuments] = useState<any[]>([]);
  const [devices, setDevices] = useState<any[]>([]);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [salaryHistory, setSalaryHistory] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<"profile" | "salary" | "hierarchy" | "documents" | "device" | "history">("profile");
  const [loading, setLoading] = useState(true);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Profile edit state
  const [editWeeklyOff, setEditWeeklyOff] = useState("");
  const [editBreakOverride, setEditBreakOverride] = useState<number | "">("");
  const [editPhone, setEditPhone] = useState("");
  const [editAccommodationId, setEditAccommodationId] = useState("");

  // Add document state
  const [newDocType, setNewDocType] = useState("VISA");
  const [newDocExpiry, setNewDocExpiry] = useState("");

  const fetchData = async () => {
    if (!employeeId) return;
    setLoading(true);
    try {
      const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

      // 1. Employee
      const empRes = await fetch(`/api/v1/employees/${employeeId}`, { headers });
      if (empRes.ok) {
        const empData = await empRes.json();
        setEmployee(empData);
        setEditWeeklyOff(empData.weekly_off_day || "");
        setEditBreakOverride(empData.break_override_minutes ?? "");
        setEditPhone(empData.phone || "");
        setEditAccommodationId(empData.accommodation_id || "");
      }

      // Accommodations list
      const accRes = await fetch(`/api/v1/accommodations`, { headers });
      if (accRes.ok) {
        setAccommodations(await accRes.json());
      }

      // 2. Reporting lines
      const repRes = await fetch(`/api/v1/employees/${employeeId}/reporting-lines`, { headers });
      if (repRes.ok) setReportingLines(await repRes.json());

      // 3. Documents
      const docRes = await fetch(`/api/v1/employees/${employeeId}/documents`, { headers });
      if (docRes.ok) setDocuments(await docRes.json());

      // 4. Salary history
      const salRes = await fetch(`/api/v1/employees/${employeeId}/salary`, { headers });
      if (salRes.ok) setSalaryHistory(await salRes.json());

      // 5. Devices (Admin only)
      if (user?.role === "ADMIN") {
        const devRes = await fetch(`/api/v1/employees/${employeeId}/devices`, { headers });
        if (devRes.ok) setDevices(await devRes.json());

        const auditRes = await fetch(`/api/v1/audit-logs?entity_type=employee&entity_id=${employeeId}`, { headers });
        if (auditRes.ok) setAuditLogs(await auditRes.json());
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [employeeId, user]);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatusMessage(null);
    setErrorMessage(null);

    try {
      const payload: any = {
        version: employee.version,
        weekly_off_day: editWeeklyOff || null,
        break_override_minutes: editBreakOverride !== "" ? Number(editBreakOverride) : null,
        accommodation_id: editAccommodationId || null,
      };
      if (user?.role === "ADMIN") {
        payload.phone = editPhone || null;
      }

      const res = await fetch(`/api/v1/employees/${employeeId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || err.message || "Save failed");
      }

      const updated = await res.json();
      setEmployee(updated);
      setStatusMessage("Profile updated successfully!");
    } catch (err: any) {
      setErrorMessage(err.message);
    }
  };

  const handleResetPassword = async () => {
    if (!window.confirm("Reset this user's password to company default?")) return;
    setStatusMessage(null);
    setErrorMessage(null);

    try {
      // Find user id by employee
      const usersRes = await fetch("/api/v1/users", {
        headers: { Authorization: `Bearer ${token}` },
      });
      const users = await usersRes.json();
      const targetUser = users.find((u: any) => u.employee_id === employee.id);

      if (!targetUser) throw new Error("Linked user account not found");

      const res = await fetch(`/api/v1/users/${targetUser.id}/reset-password`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to reset password");

      setStatusMessage("Password reset to company default successfully.");
    } catch (err: any) {
      setErrorMessage(err.message);
    }
  };

  const handleRevokeDevice = async (deviceId: string) => {
    if (!window.confirm("Revoke this device binding?")) return;
    try {
      const res = await fetch(`/api/v1/devices/${deviceId}/revoke`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        fetchData();
        setStatusMessage("Device binding revoked.");
      }
    } catch (err: any) {
      setErrorMessage(err.message);
    }
  };

  const handleAddDocument = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDocExpiry) return;
    try {
      const res = await fetch(`/api/v1/employees/${employeeId}/documents`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          document_type: newDocType,
          expiry_date: newDocExpiry,
        }),
      });
      if (res.ok) {
        setNewDocExpiry("");
        fetchData();
        setStatusMessage("Document added/updated.");
      }
    } catch (err: any) {
      setErrorMessage(err.message);
    }
  };

  if (loading || !employee) {
    return <div className="p-12 text-center text-slate-500">Loading employee details...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Back button and header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            to="/employees"
            className="p-2 border border-slate-200 rounded-lg hover:bg-white text-slate-600 transition"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-bold tracking-tight text-slate-900">{employee.name}</h2>
              <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-100 font-semibold text-slate-700">
                {employee.tally_id}
              </span>
              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-indigo-50 text-indigo-700">
                {employee.role}
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              {employee.staff_grade_description || "Field Worker"} • {employee.country} Operations
            </p>
          </div>
        </div>
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

      {/* Tabs */}
      <div className="border-b border-slate-200 flex gap-6">
        <button
          onClick={() => setActiveTab("profile")}
          className={`pb-3 text-sm font-medium flex items-center gap-2 border-b-2 transition ${
            activeTab === "profile"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          <UserIcon className="h-4 w-4" /> Profile
        </button>

        <button
          onClick={() => setActiveTab("salary")}
          className={`pb-3 text-sm font-medium flex items-center gap-2 border-b-2 transition ${
            activeTab === "salary"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          <DollarSign className="h-4 w-4" /> Salary Structure
        </button>

        <button
          onClick={() => setActiveTab("hierarchy")}
          className={`pb-3 text-sm font-medium flex items-center gap-2 border-b-2 transition ${
            activeTab === "hierarchy"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          <GitFork className="h-4 w-4" /> Hierarchy
        </button>

        <button
          onClick={() => setActiveTab("documents")}
          className={`pb-3 text-sm font-medium flex items-center gap-2 border-b-2 transition ${
            activeTab === "documents"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          <FileText className="h-4 w-4" /> Documents ({documents.length})
        </button>

        {user?.role === "ADMIN" && (
          <>
            <button
              onClick={() => setActiveTab("device")}
              className={`pb-3 text-sm font-medium flex items-center gap-2 border-b-2 transition ${
                activeTab === "device"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              <Smartphone className="h-4 w-4" /> Devices & Security
            </button>

            <button
              onClick={() => setActiveTab("history")}
              className={`pb-3 text-sm font-medium flex items-center gap-2 border-b-2 transition ${
                activeTab === "history"
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              <History className="h-4 w-4" /> Audit History
            </button>
          </>
        )}
      </div>

      {/* Tab Panels */}
      {activeTab === "profile" && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm max-w-2xl">
          <form onSubmit={handleSaveProfile} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Tally ID</label>
                <input
                  type="text"
                  disabled
                  value={employee.tally_id}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 text-sm text-slate-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Full Name</label>
                <input
                  type="text"
                  disabled
                  value={employee.name}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg p-2 text-sm text-slate-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Weekly Off Day</label>
                <select
                  value={editWeeklyOff}
                  onChange={(e) => setEditWeeklyOff(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm"
                >
                  <option value="SUNDAY">Sunday</option>
                  <option value="MONDAY">Monday</option>
                  <option value="TUESDAY">Tuesday</option>
                  <option value="WEDNESDAY">Wednesday</option>
                  <option value="THURSDAY">Thursday</option>
                  <option value="FRIDAY">Friday</option>
                  <option value="SATURDAY">Saturday</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Break Override (Minutes)</label>
                <input
                  type="number"
                  value={editBreakOverride}
                  onChange={(e) => setEditBreakOverride(e.target.value ? Number(e.target.value) : "")}
                  placeholder="e.g. 60"
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Living Camp / Accommodation</label>
                <select
                  value={editAccommodationId}
                  onChange={(e) => setEditAccommodationId(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm text-slate-800"
                >
                  <option value="">-- No Camp Assigned --</option>
                  {accommodations.map((acc) => (
                    <option key={acc.id} value={acc.id}>
                      {acc.name} ({acc.accommodation_code})
                    </option>
                  ))}
                </select>
              </div>

              {user?.role === "ADMIN" && (
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Phone Number</label>
                  <input
                    type="text"
                    value={editPhone}
                    onChange={(e) => setEditPhone(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg p-2 text-sm"
                  />
                </div>
              )}
            </div>

            <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
              <span className="text-xs text-slate-400">Record Version: {employee.version}</span>
              <button
                type="submit"
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 transition"
              >
                Save Changes
              </button>
            </div>
          </form>
        </div>
      )}

      {activeTab === "salary" && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm max-w-3xl space-y-6">
          <div className="flex items-center justify-between border-b pb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900">Worker Salary Structure</h3>
              <p className="text-xs text-slate-500">
                Effective-dated salary portions and historical revisions.
              </p>
            </div>
            {salaryHistory?.last_change_difference !== null && salaryHistory?.last_change_difference !== undefined && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">Last change:</span>
                <span
                  className={`inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-full ${
                    salaryHistory.last_change_difference > 0
                      ? "bg-emerald-100 text-emerald-800"
                      : salaryHistory.last_change_difference < 0
                      ? "bg-red-100 text-red-800"
                      : "bg-slate-100 text-slate-700"
                  }`}
                >
                  {salaryHistory.last_change_difference > 0 && <TrendingUp className="h-3.5 w-3.5" />}
                  {salaryHistory.last_change_difference < 0 && <TrendingDown className="h-3.5 w-3.5" />}
                  {salaryHistory.last_change_difference > 0
                    ? `+${salaryHistory.last_change_difference}`
                    : salaryHistory.last_change_difference}
                </span>
              </div>
            )}
          </div>

          {/* Current Active Structure Card */}
          {salaryHistory?.current_salary ? (
            <div className="rounded-xl border border-indigo-100 bg-indigo-50/40 p-5 space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-indigo-900 uppercase tracking-wider">
                  Active Structure (as of {salaryHistory.current_salary.effective_from})
                </span>
                <span className="text-xs font-mono text-slate-500">
                  Standard Hours: {salaryHistory.current_salary.standard_hours} hrs/day
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-1">
                <div className="bg-white p-3 rounded-lg border border-indigo-100">
                  <span className="text-xs text-slate-400 block mb-1">Basic Salary</span>
                  <span className="text-base font-bold text-slate-900">
                    {Number(salaryHistory.current_salary.basic_salary).toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                    })}
                  </span>
                </div>
                <div className="bg-white p-3 rounded-lg border border-indigo-100">
                  <span className="text-xs text-slate-400 block mb-1">Special Allowance</span>
                  <span className="text-base font-bold text-slate-900">
                    {Number(salaryHistory.current_salary.special_allowance).toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                    })}
                  </span>
                </div>
                <div className="bg-white p-3 rounded-lg border border-indigo-100">
                  <span className="text-xs text-slate-400 block mb-1">Other Allowances</span>
                  <span className="text-base font-bold text-slate-900">
                    {(
                      Number(salaryHistory.current_salary.fixed_ot_amount) +
                      Number(salaryHistory.current_salary.bonus) +
                      Number(salaryHistory.current_salary.telephone_allowance) +
                      Number(salaryHistory.current_salary.housing_transport_allowance)
                    ).toFixed(2)}
                  </span>
                </div>
                <div className="bg-white p-3 rounded-lg border border-indigo-200">
                  <span className="text-xs text-indigo-700 block mb-1 font-semibold">Total Fixed Portion</span>
                  <span className="text-base font-extrabold text-indigo-600">
                    {Number(salaryHistory.current_salary.salary_portion).toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                    })}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-8 text-center text-slate-400 rounded-lg border border-dashed border-slate-200">
              No active salary structure found for this worker. Upload the template or record a salary revision.
            </div>
          )}

          {/* Revisions History */}
          <div className="space-y-3 pt-2">
            <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
              Revision History ({salaryHistory?.history?.length ?? 0})
            </h4>

            {salaryHistory?.history && salaryHistory.history.length > 0 ? (
              <div className="divide-y divide-slate-100 border border-slate-200 rounded-lg overflow-hidden text-xs">
                {salaryHistory.history.map((rev: any) => (
                  <div key={rev.id} className="p-3 flex items-center justify-between hover:bg-slate-50">
                    <div className="space-y-0.5">
                      <div className="font-semibold text-slate-900">
                        Effective {rev.effective_from}
                      </div>
                      <div className="text-slate-400 text-[11px]">
                        Basic: {rev.basic_salary} • Standard: {rev.standard_hours} hrs
                      </div>
                    </div>

                    <div className="flex items-center gap-4">
                      <span className="font-bold text-slate-800 text-sm">
                        {rev.salary_portion}
                      </span>
                      {rev.difference !== 0 ? (
                        <span
                          className={`px-2 py-0.5 rounded font-semibold ${
                            rev.difference > 0 ? "text-emerald-700 bg-emerald-50" : "text-red-700 bg-red-50"
                          }`}
                        >
                          {rev.difference > 0 ? `+${rev.difference}` : rev.difference}
                        </span>
                      ) : (
                        <span className="text-slate-400">-</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      )}

      {activeTab === "hierarchy" && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm max-w-2xl space-y-6">
          <div>
            <h3 className="text-sm font-semibold text-slate-900 mb-3">Management Reporting Chain</h3>
            {reportingLines.length === 0 ? (
              <p className="text-xs text-slate-500">No managers assigned.</p>
            ) : (
              <div className="space-y-2">
                {reportingLines.map((line) => (
                  <div
                    key={line.id}
                    className="flex items-center justify-between p-3 rounded-lg border border-slate-200 bg-slate-50 text-sm"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-900">
                        {line.manager_name || `Manager ID: ${line.manager_id}`}
                      </span>
                      {line.manager_tally_id && (
                        <span className="text-xs text-slate-500 font-mono bg-slate-200/60 px-1.5 py-0.5 rounded">
                          Tally: {line.manager_tally_id}
                        </span>
                      )}
                      <span className="px-2 py-0.5 rounded text-xs font-mono font-medium bg-indigo-100 text-indigo-700">
                        {line.relationship}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === "documents" && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm max-w-3xl space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900">Official Document Validity</h3>
          </div>

          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold uppercase text-slate-500">
              <tr>
                <th className="p-3">Document Type</th>
                <th className="p-3">Expiry Date</th>
                <th className="p-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {documents.map((doc) => {
                const daysLeft = Math.ceil(
                  (new Date(doc.expiry_date).getTime() - new Date().getTime()) / (1000 * 86400)
                );
                const isExpiring = daysLeft <= 30 && daysLeft > 0;
                const isExpired = daysLeft <= 0;

                return (
                  <tr key={doc.id}>
                    <td className="p-3 font-semibold text-slate-800">{doc.document_type}</td>
                    <td className="p-3 font-mono text-xs">{doc.expiry_date}</td>
                    <td className="p-3">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                          isExpired
                            ? "bg-red-50 text-red-700"
                            : isExpiring
                            ? "bg-amber-50 text-amber-700"
                            : "bg-emerald-50 text-emerald-700"
                        }`}
                      >
                        {isExpired
                          ? "Expired"
                          : isExpiring
                          ? `Expiring soon (${daysLeft}d)`
                          : `Valid (${daysLeft}d left)`}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {user?.role === "ADMIN" && (
            <form onSubmit={handleAddDocument} className="pt-4 border-t border-slate-100 flex gap-4 items-end">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Document Type</label>
                <select
                  value={newDocType}
                  onChange={(e) => setNewDocType(e.target.value)}
                  className="border border-slate-300 rounded-lg p-2 text-sm"
                >
                  <option value="VISA">Visa</option>
                  <option value="PASSPORT">Passport</option>
                  <option value="EMIRATES_ID">Emirates ID</option>
                  <option value="LABOUR_CARD">Labour Card</option>
                  <option value="DRIVING_LICENCE">Driving Licence</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Expiry Date</label>
                <input
                  type="date"
                  required
                  value={newDocExpiry}
                  onChange={(e) => setNewDocExpiry(e.target.value)}
                  className="border border-slate-300 rounded-lg p-2 text-sm"
                />
              </div>

              <button
                type="submit"
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 flex items-center gap-2"
              >
                <Plus className="h-4 w-4" /> Save Document
              </button>
            </form>
          )}
        </div>
      )}

      {activeTab === "device" && user?.role === "ADMIN" && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm max-w-2xl space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900">Security & Credentials</h3>
            <button
              onClick={handleResetPassword}
              className="px-3.5 py-2 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-700 flex items-center gap-2 transition"
            >
              <KeyRound className="h-4 w-4" /> Reset Password to Default
            </button>
          </div>

          <div className="pt-4 border-t border-slate-100">
            <h4 className="text-xs font-semibold text-slate-700 uppercase tracking-wider mb-3">
              Bound Registered Devices (1 device limit)
            </h4>

            {devices.length === 0 ? (
              <p className="text-xs text-slate-500">No active device bound to this worker.</p>
            ) : (
              <div className="space-y-3">
                {devices.map((dev) => (
                  <div
                    key={dev.id}
                    className="p-4 border border-slate-200 rounded-lg flex items-center justify-between"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-800 text-sm">
                          {dev.device_model || dev.platform}
                        </span>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            dev.is_active ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {dev.is_active ? "ACTIVE BINDING" : "REVOKED"}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 mt-1">
                        OS: {dev.os_version || "—"} • App Version: {dev.app_version || "—"}
                      </p>
                    </div>

                    {dev.is_active && (
                      <button
                        onClick={() => handleRevokeDevice(dev.id)}
                        className="px-3 py-1.5 text-xs text-red-600 hover:bg-red-50 border border-red-200 rounded-lg flex items-center gap-1.5 transition"
                      >
                        <Trash2 className="h-3.5 w-3.5" /> Revoke Binding
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === "history" && user?.role === "ADMIN" && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm max-w-3xl space-y-4">
          <h3 className="text-sm font-semibold text-slate-900">Audit Trail for Employee</h3>
          {auditLogs.length === 0 ? (
            <p className="text-xs text-slate-500">No audit records found.</p>
          ) : (
            <div className="space-y-3">
              {auditLogs.map((log) => (
                <div key={log.id} className="p-3 border border-slate-100 rounded-lg bg-slate-50 text-xs">
                  <div className="flex items-center justify-between text-slate-500 mb-1">
                    <span className="font-semibold text-slate-700">{log.action}</span>
                    <span>{new Date(log.created_at).toLocaleString()}</span>
                  </div>
                  <pre className="p-2 bg-white rounded border border-slate-200 font-mono text-[11px] overflow-x-auto text-slate-800">
                    {JSON.stringify(log.diff, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
