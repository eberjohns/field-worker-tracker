import React, { useState, useEffect } from "react";
import { Link } from "@tanstack/react-router";
import { useAuth } from "../context/AuthContext";
import { Search, Filter, Layers, CheckSquare, Square, RefreshCw } from "lucide-react";

interface Employee {
  id: string;
  tally_id: string;
  name: string;
  role: string;
  staff_grade_description: string | null;
  grade_code: string | null;
  weekly_off_day: string | null;
  is_driver: boolean;
  country: string;
  is_active: boolean;
  version: number;
}

export const Employees: React.FC = () => {
  const { token, user } = useAuth();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<string>("");
  const [groupBySupervisor, setGroupBySupervisor] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // Bulk update dialog state
  const [bulkModalOpen, setBulkModalOpen] = useState(false);
  const [bulkWeeklyOff, setBulkWeeklyOff] = useState("");
  const [bulkBreak, setBulkBreak] = useState<number | "">("");
  const [bulkLoading, setBulkLoading] = useState(false);

  const fetchEmployees = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.set("q", search);
      if (roleFilter) params.set("role", roleFilter);

      const res = await fetch(`/api/v1/employees?${params.toString()}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data = await res.json();
        setEmployees(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEmployees();
  }, [search, roleFilter]);

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  const handleBulkUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setBulkLoading(true);
    try {
      const res = await fetch("/api/v1/employees/bulk-update", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          employee_ids: selectedIds,
          changes: {
            weekly_off_day: bulkWeeklyOff || null,
            break_override_minutes: bulkBreak !== "" ? Number(bulkBreak) : null,
          },
        }),
      });
      if (res.ok) {
        setBulkModalOpen(false);
        setSelectedIds([]);
        fetchEmployees();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setBulkLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">Employees & People</h2>
          <p className="text-sm text-slate-500 mt-1">
            Manage worker records, reporting scopes, and operational profiles
          </p>
        </div>

        <div className="flex items-center gap-3">
          {selectedIds.length > 0 && (user?.role === "ADMIN" || user?.role === "ENGINEER") && (
            <button
              onClick={() => setBulkModalOpen(true)}
              className="px-3.5 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition"
            >
              Bulk Update ({selectedIds.length})
            </button>
          )}

          <button
            onClick={() => setGroupBySupervisor(!groupBySupervisor)}
            className={`flex items-center gap-2 px-3 py-2 border rounded-lg text-sm font-medium transition ${
              groupBySupervisor ? "bg-slate-200 border-slate-300" : "bg-white border-slate-200 hover:bg-slate-50"
            }`}
          >
            <Layers className="h-4 w-4" />
            {groupBySupervisor ? "Grouped by Supervisor" : "Flat Table"}
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex items-center gap-4 bg-white p-4 rounded-xl border border-slate-200">
        <div className="relative flex-1">
          <Search className="h-4 w-4 absolute left-3 top-3 text-slate-400" />
          <input
            type="text"
            placeholder="Search by name or Tally ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-slate-400" />
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="border border-slate-200 rounded-lg text-sm px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            <option value="">All Roles</option>
            <option value="ADMIN">Admin</option>
            <option value="ENGINEER">Engineer</option>
            <option value="SUPERINTENDENT">Superintendent</option>
            <option value="SUPERVISOR">Supervisor</option>
            <option value="WORKER">Worker</option>
          </select>
        </div>

        <button
          onClick={fetchEmployees}
          className="p-2 border border-slate-200 rounded-lg hover:bg-slate-50 text-slate-600"
          title="Refresh"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-sm">
        {loading ? (
          <div className="p-12 text-center text-slate-500 text-sm">Loading employees...</div>
        ) : employees.length === 0 ? (
          <div className="p-12 text-center text-slate-500 text-sm">No employees found.</div>
        ) : (
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold uppercase text-slate-500">
              <tr>
                <th className="p-4 w-12">
                  <span className="sr-only">Select</span>
                </th>
                <th className="p-4">Tally ID</th>
                <th className="p-4">Name</th>
                <th className="p-4">Role</th>
                <th className="p-4">Staff Grade (SGD)</th>
                <th className="p-4">Grade Code</th>
                <th className="p-4">Weekly Off</th>
                <th className="p-4">Country</th>
                <th className="p-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {employees.map((emp) => {
                const isSelected = selectedIds.includes(emp.id);
                return (
                  <tr key={emp.id} className="hover:bg-slate-50 transition">
                    <td className="p-4">
                      <button
                        onClick={() => toggleSelect(emp.id)}
                        className="text-slate-400 hover:text-indigo-600"
                      >
                        {isSelected ? (
                          <CheckSquare className="h-4 w-4 text-indigo-600" />
                        ) : (
                          <Square className="h-4 w-4" />
                        )}
                      </button>
                    </td>
                    <td className="p-4 font-mono font-medium text-slate-900">
                      <Link
                        to="/employees/$employeeId"
                        params={{ employeeId: emp.id }}
                        className="text-indigo-600 hover:underline"
                      >
                        {emp.tally_id}
                      </Link>
                    </td>
                    <td className="p-4 font-medium text-slate-900">{emp.name}</td>
                    <td className="p-4">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-800">
                        {emp.role}
                      </span>
                    </td>
                    <td className="p-4">{emp.staff_grade_description || "—"}</td>
                    <td className="p-4 font-mono text-xs">{emp.grade_code || "—"}</td>
                    <td className="p-4">{emp.weekly_off_day || "SUNDAY"}</td>
                    <td className="p-4">
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-100">
                        {emp.country}
                      </span>
                    </td>
                    <td className="p-4">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                          emp.is_active ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"
                        }`}
                      >
                        {emp.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Bulk Update Modal */}
      {bulkModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-lg border border-slate-200 max-w-md w-full p-6 space-y-4">
            <h3 className="text-lg font-bold text-slate-900">
              Bulk Update {selectedIds.length} Employee(s)
            </h3>
            <p className="text-xs text-slate-500">
              Update accommodation, break override, or weekly off day for the selected workers.
            </p>

            <form onSubmit={handleBulkUpdate} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Weekly Off Day</label>
                <select
                  value={bulkWeeklyOff}
                  onChange={(e) => setBulkWeeklyOff(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm"
                >
                  <option value="">Leave Unchanged</option>
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
                  placeholder="e.g. 60"
                  value={bulkBreak}
                  onChange={(e) => setBulkBreak(e.target.value ? Number(e.target.value) : "")}
                  className="w-full border border-slate-300 rounded-lg p-2 text-sm"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setBulkModalOpen(false)}
                  className="px-4 py-2 border border-slate-200 rounded-lg text-sm text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={bulkLoading}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50"
                >
                  {bulkLoading ? "Saving..." : "Apply Updates"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
