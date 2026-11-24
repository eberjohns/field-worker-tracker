import React, { useState, useEffect } from "react";
import { currencyForCountry, formatAmount, formatMoney } from "../features/format/money";
import { useAuth } from "../context/AuthContext";
import {
  Search,
  Filter,
  History,
  Calendar,
  Plus,
  X,
  ArrowUpDown,
  Pencil,
  Trash2,
  Banknote,
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
  special_allowance: number;
  fixed_ot_amount: number;
  bonus: number;
  telephone_allowance: number;
  housing_transport_allowance: number;
  gratuity: number;
  leave_salary: number;
  per_month_provision: number;
  total_staff_cost: number;
  hr_oh: number;
  final_cost: number;
  break_minutes?: number | null;
  effective_from: string;
  last_change_date: string | null;
  difference: number;
}

interface SalaryHistoryRecord {
  id: string;
  effective_from: string;
  standard_hours: number;
  basic_salary: number;
  break_minutes?: number | null;
  change_source?: string | null;
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
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Sorting state
  const [sortBy, setSortBy] = useState<keyof SalaryItem>("tally_id");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");

  // History modal state
  const [selectedWorkerId, setSelectedWorkerId] = useState<string | null>(null);
  const [selectedWorkerName, setSelectedWorkerName] = useState("");
  const [selectedWorkerTally, setSelectedWorkerTally] = useState("");
  const [historyList, setHistoryList] = useState<SalaryHistoryRecord[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Edit future revision state
  const [editingRevision, setEditingRevision] = useState<SalaryHistoryRecord | null>(null);
  const [editRevForm, setEditRevForm] = useState({
    basic_salary: 0,
    special_allowance: 0,
    fixed_ot_amount: 0,
    bonus: 0,
    telephone_allowance: 0,
    housing_transport_allowance: 0,
    standard_hours: 8,
    break_minutes: 60 as number | null,
    effective_from: "",
  });
  const [savingRev, setSavingRev] = useState(false);

  // New salary change modal
  const [changeModalOpen, setChangeModalOpen] = useState(false);
  const [changeWorkerId, setChangeWorkerId] = useState<string | null>(null);
  const [changeWorkerName, setChangeWorkerName] = useState("");
  const [formData, setFormData] = useState({
    effective_from: "",
    standard_hours: 8,
    break_minutes: 60 as number | null,
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
    setFetchError(null);
    try {
      const params = new URLSearchParams();
      if (countryFilter) params.set("country", countryFilter);
      const res = await fetch(`/api/v1/salary-structures?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setSalaries(data.filter((s: any) => s.tally_id !== "ADMIN001"));
      } else {
        setFetchError("Failed to fetch salary structures from server.");
      }
    } catch (err) {
      console.error("Failed to fetch salary structures", err);
      setFetchError("Network error while loading salary structures. Please retry.");
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
    } catch (err) {
      console.error("Failed to load salary history", err);
      setHistoryList([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleEditRevision = (rec: SalaryHistoryRecord) => {
    setEditingRevision(rec);
    setEditRevForm({
      basic_salary: rec.basic_salary,
      special_allowance: rec.special_allowance || 0,
      fixed_ot_amount: rec.fixed_ot_amount || 0,
      bonus: rec.bonus || 0,
      telephone_allowance: rec.telephone_allowance || 0,
      housing_transport_allowance: rec.housing_transport_allowance || 0,
      standard_hours: rec.standard_hours,
      break_minutes: rec.break_minutes ?? 60,
      effective_from: rec.effective_from,
    });
  };

  const handleSaveRevision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingRevision || !selectedWorkerId) return;
    setSavingRev(true);
    try {
      const res = await fetch(`/api/v1/employees/${selectedWorkerId}/salary/${editingRevision.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(editRevForm),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail?.message || err.detail || "Failed to update salary revision.");
      }
      setEditingRevision(null);
      await openHistory(selectedWorkerId, selectedWorkerName, selectedWorkerTally);
      fetchSalaries();
    } catch (err: any) {
      alert(err.message || "Failed to update salary revision");
    } finally {
      setSavingRev(false);
    }
  };

  const handleDeleteRevision = async (rec: SalaryHistoryRecord) => {
    if (!selectedWorkerId) return;
    if (
      !window.confirm(
        `Are you sure you want to delete the future salary revision effective ${rec.effective_from}?`
      )
    )
      return;
    try {
      const res = await fetch(`/api/v1/employees/${selectedWorkerId}/salary/${rec.id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail?.message || err.detail || "Failed to delete salary revision.");
      }
      await openHistory(selectedWorkerId, selectedWorkerName, selectedWorkerTally);
      fetchSalaries();
    } catch (err: any) {
      alert(err.message || "Failed to delete salary revision");
    }
  };

  const openChangeModal = (emp: SalaryItem) => {
    setChangeWorkerId(emp.employee_id);
    setChangeWorkerName(emp.name);
    setFormData({
      effective_from: "",
      standard_hours: emp.standard_hours || 8,
      break_minutes: emp.break_minutes ?? 60,
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
        delete payload.effective_from;
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

  const handleSort = (field: keyof SalaryItem) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortBy(field);
      setSortOrder("asc");
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

  // The salary history modal shows the worker's country currency.
  const historyCurrency = currencyForCountry(
    salaries.find((x) => x.employee_id === selectedWorkerId)?.country,
  );

  const sortedAndFiltered = [...filtered].sort((a, b) => {
    const valA = a[sortBy];
    const valB = b[sortBy];
    if (valA == null && valB == null) return 0;
    if (valA == null) return 1;
    if (valB == null) return -1;

    let res = 0;
    if (typeof valA === "number" && typeof valB === "number") {
      res = valA - valB;
    } else {
      res = String(valA).localeCompare(String(valB), undefined, { numeric: true });
    }
    return sortOrder === "asc" ? res : -res;
  });

  const todayStr = new Date().toISOString().slice(0, 10);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 flex items-center gap-2">
            <Banknote className="h-6 w-6 text-indigo-600" />
            Worker Salary Structures & Cost Analysis
          </h1>
          <p className="text-sm text-slate-500">
            Effective-dated monthly fixed pay components, statutory provisions, and total employer staff cost breakdown (DEC-39).
          </p>
        </div>
      </div>

      {fetchError && (
        <div className="p-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl">
          {fetchError}
        </div>
      )}

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
        ) : sortedAndFiltered.length === 0 ? (
          <div className="p-12 text-center text-slate-400">
            No salary records found. Upload the master data template to import salary structures.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs border-collapse">
              <thead className="bg-slate-50 text-slate-600 font-semibold uppercase tracking-wider text-[11px]">
                <tr>
                  <th
                    onClick={() => handleSort("tally_id")}
                    className="py-3 px-3 cursor-pointer hover:bg-slate-100 whitespace-nowrap"
                  >
                    <div className="flex items-center gap-1">
                      <span>Tally ID</span>
                      <ArrowUpDown className="h-3 w-3 text-slate-400" />
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort("name")}
                    className="py-3 px-3 cursor-pointer hover:bg-slate-100 whitespace-nowrap"
                  >
                    <div className="flex items-center gap-1">
                      <span>Worker Name</span>
                      <ArrowUpDown className="h-3 w-3 text-slate-400" />
                    </div>
                  </th>
                  <th className="py-3 px-2 whitespace-nowrap" title="Amounts in this row are in this currency">
                    Currency
                  </th>
                  <th
                    onClick={() => handleSort("basic_salary")}
                    className="py-3 px-2 text-right cursor-pointer hover:bg-slate-100 whitespace-nowrap"
                  >
                    <div className="flex items-center justify-end gap-1">
                      <span>Basic</span>
                      <ArrowUpDown className="h-3 w-3 text-slate-400" />
                    </div>
                  </th>
                  <th className="py-3 px-2 text-right whitespace-nowrap">Sp. Allow</th>
                  <th className="py-3 px-2 text-right whitespace-nowrap">Fixed OT</th>
                  <th className="py-3 px-2 text-right whitespace-nowrap">Bonus</th>
                  <th className="py-3 px-2 text-right whitespace-nowrap">Tel</th>
                  <th className="py-3 px-2 text-right whitespace-nowrap">HRA/Trans</th>
                  <th
                    onClick={() => handleSort("salary_portion")}
                    className="py-3 px-2.5 text-right font-bold text-indigo-700 bg-indigo-50/50 cursor-pointer hover:bg-indigo-100/50 whitespace-nowrap"
                  >
                    <div className="flex items-center justify-end gap-1">
                      <span>Salary Portion</span>
                      <ArrowUpDown className="h-3 w-3 text-indigo-400" />
                    </div>
                  </th>
                  <th className="py-3 px-2 text-right whitespace-nowrap text-slate-600">
                    Gratuity (30d)
                  </th>
                  <th className="py-3 px-2 text-right whitespace-nowrap text-slate-600">
                    Leave Sal
                  </th>
                  <th
                    onClick={() => handleSort("per_month_provision")}
                    className="py-3 px-2 text-right cursor-pointer hover:bg-slate-100 whitespace-nowrap"
                  >
                    <div className="flex items-center justify-end gap-1">
                      <span>Mo. Prov</span>
                      <ArrowUpDown className="h-3 w-3 text-slate-400" />
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort("total_staff_cost")}
                    className="py-3 px-2 text-right cursor-pointer hover:bg-slate-100 whitespace-nowrap font-semibold"
                  >
                    <div className="flex items-center justify-end gap-1">
                      <span>Staff Cost</span>
                      <ArrowUpDown className="h-3 w-3 text-slate-400" />
                    </div>
                  </th>
                  <th className="py-3 px-2 text-right whitespace-nowrap text-slate-600">HR OH (5%)</th>
                  <th
                    onClick={() => handleSort("final_cost")}
                    className="py-3 px-2.5 text-right font-bold text-emerald-800 bg-emerald-50/50 cursor-pointer hover:bg-emerald-100/50 whitespace-nowrap"
                  >
                    <div className="flex items-center justify-end gap-1">
                      <span>Final Cost</span>
                      <ArrowUpDown className="h-3 w-3 text-emerald-600" />
                    </div>
                  </th>
                  <th className="py-3 px-2.5 text-center whitespace-nowrap">Hours / Break</th>
                  <th
                    onClick={() => handleSort("effective_from")}
                    className="py-3 px-2.5 cursor-pointer hover:bg-slate-100 whitespace-nowrap"
                  >
                    <div className="flex items-center gap-1">
                      <span>Effective</span>
                      <ArrowUpDown className="h-3 w-3 text-slate-400" />
                    </div>
                  </th>
                  <th className="py-3 px-3 text-right whitespace-nowrap">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700 font-mono text-[11px]">
                {sortedAndFiltered.map((s) => (
                  <tr key={s.employee_id} className="hover:bg-slate-50 transition-colors">
                    <td className="py-2.5 px-3 font-semibold text-slate-900 whitespace-nowrap">
                      {s.tally_id}
                    </td>
                    <td className="py-2.5 px-3 font-sans font-medium text-slate-900 whitespace-nowrap">
                      {s.name}
                    </td>
                    <td className="py-2.5 px-2 text-slate-500">{currencyForCountry(s.country)}</td>
                    <td className="py-2.5 px-2 text-right text-slate-800">
                      {formatAmount(s.basic_salary)}
                    </td>
                    <td className="py-2.5 px-2 text-right text-slate-500">
                      {formatAmount(s.special_allowance)}
                    </td>
                    <td className="py-2.5 px-2 text-right text-slate-500">
                      {formatAmount(s.fixed_ot_amount)}
                    </td>
                    <td className="py-2.5 px-2 text-right text-slate-500">
                      {formatAmount(s.bonus)}
                    </td>
                    <td className="py-2.5 px-2 text-right text-slate-500">
                      {formatAmount(s.telephone_allowance)}
                    </td>
                    <td className="py-2.5 px-2 text-right text-slate-500">
                      {formatAmount(s.housing_transport_allowance)}
                    </td>
                    <td className="py-2.5 px-2.5 text-right font-bold text-indigo-700 bg-indigo-50/30">
                      {formatAmount(s.salary_portion)}
                    </td>
                    <td className="py-2.5 px-2 text-right text-slate-600">
                      {formatAmount(s.gratuity)}
                    </td>
                    <td className="py-2.5 px-2 text-right text-slate-600">
                      {formatAmount(s.leave_salary)}
                    </td>
                    <td className="py-2.5 px-2 text-right text-slate-700 font-medium">
                      {formatAmount(s.per_month_provision)}
                    </td>
                    <td className="py-2.5 px-2 text-right font-semibold text-slate-900">
                      {formatAmount(s.total_staff_cost)}
                    </td>
                    <td className="py-2.5 px-2 text-right text-slate-600">
                      {formatAmount(s.hr_oh)}
                    </td>
                    <td className="py-2.5 px-2.5 text-right font-bold text-emerald-700 bg-emerald-50/30">
                      {formatAmount(s.final_cost)}
                    </td>
                    <td className="py-2.5 px-2.5 text-center text-slate-600 font-sans whitespace-nowrap text-[10px]">
                      {s.standard_hours}h / {s.break_minutes ?? 60}m
                    </td>
                    <td className="py-2.5 px-2.5 text-slate-500 whitespace-nowrap text-[10px]">
                      {s.effective_from}
                    </td>
                    <td className="py-2.5 px-3 text-right space-x-1 whitespace-nowrap font-sans">
                      <button
                        onClick={() => openHistory(s.employee_id, s.name, s.tally_id)}
                        className="inline-flex items-center gap-1 text-[11px] font-semibold text-indigo-600 hover:text-indigo-800 px-2 py-0.5 rounded hover:bg-indigo-50"
                      >
                        <History className="h-3 w-3" />
                        History
                      </button>
                      {user?.role === "ADMIN" && (
                        <button
                          onClick={() => openChangeModal(s)}
                          className="inline-flex items-center gap-1 text-[11px] font-semibold text-slate-700 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 px-2 py-0.5 rounded"
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
          </div>
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
                  {historyList.map((rec) => {
                    const isFuture = rec.effective_from > todayStr;
                    return (
                      <div
                        key={rec.id}
                        className={`border rounded-lg p-4 transition-colors ${
                          isFuture
                            ? "border-purple-200 bg-purple-50/30"
                            : "border-slate-200 bg-slate-50/50 hover:border-indigo-300"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <Calendar className="h-4 w-4 text-indigo-600" />
                            <span className="text-sm font-bold text-slate-900">
                              Effective from {rec.effective_from}
                            </span>
                            {isFuture && (
                              <span className="px-1.5 py-0.5 rounded bg-purple-100 text-purple-800 text-[10px] font-bold border border-purple-200">
                                Upcoming (Editable)
                              </span>
                            )}
                            {rec.change_source === "CREW_BREAK" && (
                              <span className="px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 text-[10px] font-bold">
                                Break change
                              </span>
                            )}
                          </div>

                          <div className="flex items-center gap-2">
                            {rec.change_source === "CREW_BREAK" ? (
                              <span className="text-xs text-slate-400 font-medium">
                                No salary diff
                              </span>
                            ) : rec.difference !== 0 ? (
                              <span
                                className={`text-xs font-bold px-2 py-0.5 rounded ${
                                  rec.difference > 0
                                    ? "bg-emerald-100 text-emerald-800"
                                    : "bg-red-100 text-red-800"
                                }`}
                              >
                                {rec.difference > 0 ? `+${rec.difference}` : rec.difference}
                              </span>
                            ) : null}

                            {/* CREW_BREAK rows follow the row before them; change the crew break instead. */}
                            {isFuture && user?.role === "ADMIN" && rec.change_source !== "CREW_BREAK" && (
                              <div className="flex items-center gap-1.5 ml-2 border-l border-slate-200 pl-2">
                                <button
                                  type="button"
                                  onClick={() => handleEditRevision(rec)}
                                  className="p-1 text-slate-500 hover:text-indigo-600 rounded hover:bg-slate-100 transition"
                                  title="Edit future revision"
                                >
                                  <Pencil className="h-3.5 w-3.5" />
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleDeleteRevision(rec)}
                                  className="p-1 text-slate-500 hover:text-rose-600 rounded hover:bg-slate-100 transition"
                                  title="Delete future revision"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </button>
                              </div>
                            )}
                          </div>
                        </div>

                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs text-slate-600">
                          <div>
                            <span className="text-slate-400 block">Standard Hours:</span>
                            <span className="font-semibold">{rec.standard_hours} hrs</span>
                          </div>
                          <div>
                            <span className="text-slate-400 block">Basic Salary:</span>
                            <span className="font-semibold">{formatMoney(rec.basic_salary, historyCurrency)}</span>
                          </div>
                          <div>
                            <span className="text-slate-400 block">Allowances:</span>
                            <span className="font-semibold">
                              {formatMoney(
                                Number(rec.special_allowance) +
                                  Number(rec.fixed_ot_amount) +
                                  Number(rec.bonus) +
                                  Number(rec.telephone_allowance) +
                                  Number(rec.housing_transport_allowance),
                                historyCurrency,
                              )}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-400 block">Total Fixed Pay:</span>
                            <span className="font-bold text-indigo-700">{formatMoney(rec.salary_portion, historyCurrency)}</span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
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

      {/* Edit Future Salary Revision Modal */}
      {editingRevision && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <form
            onSubmit={handleSaveRevision}
            className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4"
          >
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-1.5">
                <Pencil className="h-4 w-4 text-indigo-600" />
                Edit Future Salary Revision
              </h3>
              <button
                type="button"
                onClick={() => setEditingRevision(null)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <p className="text-xs text-slate-500">
              Modifying upcoming revision for <span className="font-semibold">{selectedWorkerName}</span>.
            </p>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Effective From Date (Must be future)
                </label>
                <input
                  type="date"
                  required
                  min={new Date(Date.now() + 86400000).toISOString().slice(0, 10)}
                  value={editRevForm.effective_from}
                  onChange={(e) =>
                    setEditRevForm({ ...editRevForm, effective_from: e.target.value })
                  }
                  className="w-full border rounded-lg px-3 py-1.5 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-0.5">Basic Salary</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={editRevForm.basic_salary}
                    onChange={(e) =>
                      setEditRevForm({ ...editRevForm, basic_salary: parseFloat(e.target.value) || 0 })
                    }
                    className="w-full border rounded p-1.5 font-mono"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-0.5">Special Allow</label>
                  <input
                    type="number"
                    step="0.01"
                    value={editRevForm.special_allowance}
                    onChange={(e) =>
                      setEditRevForm({
                        ...editRevForm,
                        special_allowance: parseFloat(e.target.value) || 0,
                      })
                    }
                    className="w-full border rounded p-1.5 font-mono"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-0.5">Fixed OT</label>
                  <input
                    type="number"
                    step="0.01"
                    value={editRevForm.fixed_ot_amount}
                    onChange={(e) =>
                      setEditRevForm({
                        ...editRevForm,
                        fixed_ot_amount: parseFloat(e.target.value) || 0,
                      })
                    }
                    className="w-full border rounded p-1.5 font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-0.5">Bonus</label>
                  <input
                    type="number"
                    step="0.01"
                    value={editRevForm.bonus}
                    onChange={(e) =>
                      setEditRevForm({ ...editRevForm, bonus: parseFloat(e.target.value) || 0 })
                    }
                    className="w-full border rounded p-1.5 font-mono"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-0.5">Telephone</label>
                  <input
                    type="number"
                    step="0.01"
                    value={editRevForm.telephone_allowance}
                    onChange={(e) =>
                      setEditRevForm({
                        ...editRevForm,
                        telephone_allowance: parseFloat(e.target.value) || 0,
                      })
                    }
                    className="w-full border rounded p-1.5 font-mono"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-0.5">Housing/Trans</label>
                  <input
                    type="number"
                    step="0.01"
                    value={editRevForm.housing_transport_allowance}
                    onChange={(e) =>
                      setEditRevForm({
                        ...editRevForm,
                        housing_transport_allowance: parseFloat(e.target.value) || 0,
                      })
                    }
                    className="w-full border rounded p-1.5 font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-0.5">Standard Hours</label>
                  <input
                    type="number"
                    step="0.5"
                    value={editRevForm.standard_hours}
                    onChange={(e) =>
                      setEditRevForm({
                        ...editRevForm,
                        standard_hours: parseFloat(e.target.value) || 8,
                      })
                    }
                    className="w-full border rounded p-1.5 font-mono"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-0.5">Break Minutes</label>
                  <input
                    type="number"
                    value={editRevForm.break_minutes ?? ""}
                    onChange={(e) =>
                      setEditRevForm({
                        ...editRevForm,
                        break_minutes: e.target.value ? parseInt(e.target.value) : null,
                      })
                    }
                    className="w-full border rounded p-1.5 font-mono"
                  />
                </div>
              </div>
            </div>

            <div className="border-t pt-3 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setEditingRevision(null)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium rounded-lg"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={savingRev}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-sm disabled:opacity-50"
              >
                {savingRev ? "Updating..." : "Update Revision"}
              </button>
            </div>
          </form>
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

              <div className="grid grid-cols-3 gap-3">
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
                  <label className="block text-xs font-medium text-slate-700 mb-1">Break Duration (Min)</label>
                  <input
                    type="number"
                    min="0"
                    max="240"
                    value={formData.break_minutes ?? ""}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        break_minutes: e.target.value ? parseInt(e.target.value) : null,
                      })
                    }
                    placeholder="e.g. 60"
                    className="w-full border rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-indigo-500"
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
