import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import {
  Search,
  Filter,
  History,
  TrendingUp,
  TrendingDown,
  Calendar,
  Plus,
  X,
} from "lucide-react";

interface SalaryItem {
  employee_id: string;
  tally_id: string;
  name: string;
  role: string;
  country: string;
  standard_hours: number;
  salary_portion: number;
  basic_salary: number;
  effective_from: string;
  last_change_date: string | null;
  difference: number;
}

interface SalaryHistoryRecord {
  id: string;
  effective_from: string;
  standard_hours: number;
  basic_salary: number;
  special_allowance: number;
  fixed_ot_amount: number;
  bonus: number;
  telephone_allowance: number;
  housing_transport_allowance: number;
  salary_portion: number;
  difference: number;
  created_at: string;
}

export const SalaryStructures: React.FC = () => {
  const { token, user } = useAuth();
  const [salaries, setSalaries] = useState<SalaryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [countryFilter, setCountryFilter] = useState("");

  // History modal state
  const [selectedWorkerId, setSelectedWorkerId] = useState<string | null>(null);
  const [selectedWorkerName, setSelectedWorkerName] = useState("");
  const [selectedWorkerTally, setSelectedWorkerTally] = useState("");
  const [historyList, setHistoryList] = useState<SalaryHistoryRecord[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // New salary change modal
  const [changeModalOpen, setChangeModalOpen] = useState(false);
  const [changeWorkerId, setChangeWorkerId] = useState<string | null>(null);
  const [changeWorkerName, setChangeWorkerName] = useState("");
  const [formData, setFormData] = useState({
    effective_from: "",
    standard_hours: 8,
    basic_salary: 1200,
    special_allowance: 0,
    fixed_ot_amount: 0,
    bonus: 0,
    telephone_allowance: 0,
    housing_transport_allowance: 0,
  });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchSalaries();
  }, [countryFilter]);

  const fetchSalaries = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (countryFilter) params.set("country", countryFilter);
      const res = await fetch(`/api/v1/salary-structures?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setSalaries(data.filter((s: any) => s.tally_id !== "ADMIN001"));
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const openHistory = async (empId: string, name: string, tallyId: string) => {
    setSelectedWorkerId(empId);
    setSelectedWorkerName(name);
    setSelectedWorkerTally(tallyId);
    setHistoryLoading(true);
    try {
      const res = await fetch(`/api/v1/employees/${empId}/salary`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setHistoryList(data.history || []);
      }
    } catch {
      // ignore
    } finally {
      setHistoryLoading(false);
    }
  };

  const openChangeModal = (emp: SalaryItem) => {
    setChangeWorkerId(emp.employee_id);
    setChangeWorkerName(emp.name);
    setFormData({
      effective_from: "",
      standard_hours: emp.standard_hours || 8,
      basic_salary: emp.basic_salary || 1200,
      special_allowance: 0,
      fixed_ot_amount: 0,
      bonus: 0,
      telephone_allowance: 0,
      housing_transport_allowance: 0,
    });
    setChangeModalOpen(true);
  };

  const submitSalaryChange = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!changeWorkerId) return;
    setSubmitting(true);
    try {
      const payload: any = { ...formData };
      if (!payload.effective_from) {
        delete payload.effective_from; // server computes next month
      }
      const res = await fetch(`/api/v1/employees/${changeWorkerId}/salary`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        setChangeModalOpen(false);
        fetchSalaries();
      } else {
        const err = await res.json();
        alert(err.detail?.message || "Failed to update salary.");
      }
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const filtered = salaries.filter((s) => {
    if (search) {
      const q = search.toLowerCase();
      if (!s.name.toLowerCase().includes(q) && !s.tally_id.toLowerCase().includes(q)) {
        return false;
      }
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Worker Salary Structures</h1>
          <p className="text-sm text-slate-500">
            Effective-dated monthly fixed pay components, last change history, and standard hours.
          </p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row gap-4 justify-between bg-white p-4 rounded-xl border border-slate-200">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search by worker name or ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-slate-300 pl-9 pr-4 py-2 text-sm focus:border-indigo-500 focus:outline-none"
          />
        </div>

        <div className="flex items-center gap-3">
          <Filter className="h-4 w-4 text-slate-400" />
          <select
            value={countryFilter}
            onChange={(e) => setCountryFilter(e.target.value)}
            className="rounded-lg border border-slate-300 py-2 px-3 text-sm focus:border-indigo-500 focus:outline-none"
          >
            <option value="">All Countries</option>
            <option value="AE">United Arab Emirates (AED)</option>
            <option value="SA">Saudi Arabia (SAR)</option>
          </select>
        </div>
      </div>

      {/* Salary Structures Table */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-slate-400">Loading worker salary structures...</div>
        ) : filtered.length === 0 ? (
          <div className="p-12 text-center text-slate-400">
            No salary records found. Upload the master data template to import salary structures.
          </div>
        ) : (
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50 text-slate-600 font-medium text-xs">
              <tr>
                <th className="py-3 px-4">Tally ID</th>
                <th className="py-3 px-4">Worker Name</th>
                <th className="py-3 px-4">Role</th>
                <th className="py-3 px-4">Country</th>
                <th className="py-3 px-4">Standard Hours</th>
                <th className="py-3 px-4">Basic Salary</th>
                <th className="py-3 px-4">Total Fixed Portion</th>
                <th className="py-3 px-4">Effective From</th>
                <th className="py-3 px-4">Last Change Diff</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 text-slate-700">
              {filtered.map((s) => (
                <tr key={s.employee_id} className="hover:bg-slate-50 transition-colors">
                  <td className="py-3 px-4 font-mono font-medium text-slate-900">{s.tally_id}</td>
                  <td className="py-3 px-4 font-semibold text-slate-800">{s.name}</td>
                  <td className="py-3 px-4 text-xs">
                    <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-medium">
                      {s.role}
                    </span>
                  </td>
                  <td className="py-3 px-4 font-medium text-xs text-slate-600">{s.country}</td>
                  <td className="py-3 px-4 font-mono text-xs">{s.standard_hours} hrs/day</td>
                  <td className="py-3 px-4 font-mono">
                    {Number(s.basic_salary).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-3 px-4 font-mono font-semibold text-indigo-700">
                    {Number(s.salary_portion).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </td>
                  <td className="py-3 px-4 text-xs text-slate-500 font-mono">{s.effective_from}</td>
                  <td className="py-3 px-4">
                    {s.difference !== 0 ? (
                      <span
                        className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded ${
                          s.difference > 0
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-red-50 text-red-700"
                        }`}
                      >
                        {s.difference > 0 ? (
                          <TrendingUp className="h-3 w-3" />
                        ) : (
                          <TrendingDown className="h-3 w-3" />
                        )}
                        {s.difference > 0 ? `+${s.difference}` : s.difference}
                      </span>
                    ) : (
                      <span className="text-xs text-slate-400">-</span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-right space-x-2">
                    <button
                      onClick={() => openHistory(s.employee_id, s.name, s.tally_id)}
                      className="inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-800 hover:underline"
                    >
                      <History className="h-3.5 w-3.5" />
                      History
                    </button>
                    {user?.role === "ADMIN" && (
                      <button
                        onClick={() => openChangeModal(s)}
                        className="inline-flex items-center gap-1 text-xs font-medium text-slate-600 hover:text-slate-900 bg-slate-100 px-2 py-1 rounded"
                      >
                        <Plus className="h-3 w-3" />
                        Change
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* History Modal */}
      {selectedWorkerId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full p-6 space-y-4 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between border-b pb-3">
              <div>
                <h3 className="text-lg font-bold text-slate-900">Salary Structure History</h3>
                <p className="text-xs text-slate-500 font-mono">
                  {selectedWorkerName} ({selectedWorkerTally})
                </p>
              </div>
              <button
                onClick={() => setSelectedWorkerId(null)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3">
              {historyLoading ? (
                <div className="p-8 text-center text-slate-400">Loading history...</div>
              ) : historyList.length === 0 ? (
                <div className="p-8 text-center text-slate-400">No revisions recorded.</div>
              ) : (
                <div className="space-y-3">
                  {historyList.map((rec) => (
                    <div
                      key={rec.id}
                      className="border border-slate-200 rounded-lg p-4 hover:border-indigo-300 transition-colors bg-slate-50/50"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Calendar className="h-4 w-4 text-indigo-600" />
                          <span className="text-sm font-bold text-slate-900">
                            Effective from {rec.effective_from}
                          </span>
                        </div>
                        {rec.difference !== 0 && (
                          <span
                            className={`text-xs font-bold px-2 py-0.5 rounded ${
                              rec.difference > 0
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-red-100 text-red-800"
                            }`}
                          >
                            {rec.difference > 0 ? `+${rec.difference}` : rec.difference}
                          </span>
                        )}
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs text-slate-600">
                        <div>
                          <span className="text-slate-400 block">Standard Hours:</span>
                          <span className="font-semibold">{rec.standard_hours} hrs</span>
                        </div>
                        <div>
                          <span className="text-slate-400 block">Basic Salary:</span>
                          <span className="font-semibold">{rec.basic_salary}</span>
                        </div>
                        <div>
                          <span className="text-slate-400 block">Allowances:</span>
                          <span className="font-semibold">
                            {(
                              Number(rec.special_allowance) +
                              Number(rec.fixed_ot_amount) +
                              Number(rec.bonus) +
                              Number(rec.telephone_allowance) +
                              Number(rec.housing_transport_allowance)
                            ).toFixed(2)}
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-400 block">Total Fixed Pay:</span>
                          <span className="font-bold text-indigo-700">{rec.salary_portion}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="border-t pt-3 flex justify-end">
              <button
                onClick={() => setSelectedWorkerId(null)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium rounded-lg"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Record Salary Change Modal */}
      {changeModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <form
            onSubmit={submitSalaryChange}
            className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4"
          >
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="text-base font-bold text-slate-900">Record Salary Revision</h3>
              <button
                type="button"
                onClick={() => setChangeModalOpen(false)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <p className="text-xs text-slate-500">
              Applying change for <span className="font-semibold text-slate-700">{changeWorkerName}</span>.
              Salary changes take effect from the next payroll month.
            </p>

            <div className="space-y-3 text-sm">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Effective From (Blank = 1st of upcoming month)
                </label>
                <input
                  type="date"
                  value={formData.effective_from}
                  onChange={(e) => setFormData({ ...formData, effective_from: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Standard Hours</label>
                  <input
                    type="number"
                    step="0.5"
                    value={formData.standard_hours}
                    onChange={(e) => setFormData({ ...formData, standard_hours: parseFloat(e.target.value) || 8 })}
                    className="w-full border rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-indigo-500"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Basic Salary</label>
                  <input
                    type="number"
                    step="0.01"
                    value={formData.basic_salary}
                    onChange={(e) => setFormData({ ...formData, basic_salary: parseFloat(e.target.value) || 0 })}
                    className="w-full border rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-indigo-500"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Special Allowance</label>
                  <input
                    type="number"
                    step="0.01"
                    value={formData.special_allowance}
                    onChange={(e) => setFormData({ ...formData, special_allowance: parseFloat(e.target.value) || 0 })}
                    className="w-full border rounded-lg px-3 py-2 text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Fixed Overtime</label>
                  <input
                    type="number"
                    step="0.01"
                    value={formData.fixed_ot_amount}
                    onChange={(e) => setFormData({ ...formData, fixed_ot_amount: parseFloat(e.target.value) || 0 })}
                    className="w-full border rounded-lg px-3 py-2 text-xs"
                  />
                </div>
              </div>
            </div>

            <div className="border-t pt-3 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setChangeModalOpen(false)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium rounded-lg"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-sm"
              >
                {submitting ? "Saving..." : "Save Revision"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
