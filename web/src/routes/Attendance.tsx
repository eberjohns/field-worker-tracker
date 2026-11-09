import React, { useState, useEffect } from "react";
import {
  Calendar,
  RefreshCw,
  Search,
  AlertTriangle,
  Clock,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { AttendanceRecord, AttendanceListResponse } from "../features/attendance/types";
import { AttendanceTable } from "../features/attendance/AttendanceTable";
import { AttendanceDetailDrawer } from "../features/attendance/AttendanceDetailDrawer";
import { RecalculateModal } from "../features/attendance/RecalculateModal";

export const Attendance: React.FC = () => {
  const { token, user } = useAuth();

  // Date filters: default to last 7 days through today
  const todayStr = new Date().toISOString().split("T")[0];
  const lastWeekStr = new Date(Date.now() - 6 * 24 * 60 * 60 * 1000)
    .toISOString()
    .split("T")[0];

  const [fromDate, setFromDate] = useState<string>(lastWeekStr);
  const [toDate, setToDate] = useState<string>(todayStr);
  const [activeTab, setActiveTab] = useState<"ALL" | "PENDING_REVIEW">("ALL");
  const [businessStatus, setBusinessStatus] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Pagination
  const [page, setPage] = useState<number>(0);
  const pageSize = 50;

  // Data
  const [records, setRecords] = useState<AttendanceRecord[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [exceptionsCount, setExceptionsCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);

  // Selected Record & Modals
  const [selectedRecord, setSelectedRecord] = useState<AttendanceRecord | null>(null);
  const [showRecalculateModal, setShowRecalculateModal] = useState<boolean>(false);

  const fetchAttendance = async () => {
    setLoading(true);
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const params = new URLSearchParams({
        from_date: fromDate,
        to_date: toDate,
        limit: String(pageSize),
        offset: String(page * pageSize),
      });

      if (activeTab === "PENDING_REVIEW") {
        params.append("review_status", "PENDING_REVIEW");
      }
      if (businessStatus !== "ALL") {
        params.append("business_status", businessStatus);
      }

      const res = await fetch(`/api/v1/attendance?${params.toString()}`, { headers });
      if (res.ok) {
        const data: AttendanceListResponse = await res.json();
        setRecords(data.items || []);
        setTotal(data.total || 0);
      }

      // Query exceptions badge count
      const excRes = await fetch(
        `/api/v1/attendance/exceptions?from_date=${fromDate}&to_date=${toDate}&limit=1`,
        { headers }
      );
      if (excRes.ok) {
        const excData = await excRes.json();
        setExceptionsCount(excData.total || 0);
      }
    } catch (err) {
      console.error("Failed to load attendance", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAttendance();
  }, [token, fromDate, toDate, activeTab, businessStatus, page]);

  // Client-side search filtering by employee name or tally id
  const filteredRecords = records.filter((r) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      r.employee_name.toLowerCase().includes(q) ||
      r.tally_id.toLowerCase().includes(q)
    );
  });

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-4">
      {/* Top Banner / Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
        <div>
          <h1 className="text-lg font-bold text-slate-900 flex items-center gap-2">
            <Clock className="h-5 w-5 text-emerald-600" />
            Attendance & Work Verification
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Planned vs actual schedule, signed variations, overtime classification, and exception workflows.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {["ADMIN", "SUPERINTENDENT"].includes(user?.role || "") && (
            <button
              onClick={() => setShowRecalculateModal(true)}
              className="px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 flex items-center gap-1.5 transition-colors"
            >
              <RefreshCw className="h-3.5 w-3.5 text-slate-500" />
              Recalculate Day
            </button>
          )}

          <button
            onClick={() => fetchAttendance()}
            className="p-1.5 text-slate-500 hover:text-slate-800 rounded-lg hover:bg-slate-100 border border-slate-200"
            title="Refresh"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Tabs and Filter Bar */}
      <div className="bg-white p-3 rounded-xl border border-slate-200 shadow-sm space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-3">
          {/* Tabs */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => {
                setActiveTab("ALL");
                setPage(0);
              }}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                activeTab === "ALL"
                  ? "bg-slate-900 text-white"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              All Records
            </button>
            <button
              onClick={() => {
                setActiveTab("PENDING_REVIEW");
                setPage(0);
              }}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-colors ${
                activeTab === "PENDING_REVIEW"
                  ? "bg-amber-600 text-white"
                  : "text-amber-700 bg-amber-50 hover:bg-amber-100"
              }`}
            >
              <AlertTriangle className="h-3.5 w-3.5" />
              Needs Review
              {exceptionsCount > 0 && (
                <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-white/20 font-bold">
                  {exceptionsCount}
                </span>
              )}
            </button>
          </div>

          {/* Date range filters */}
          <div className="flex items-center gap-2 text-xs">
            <div className="flex items-center gap-1 bg-slate-50 px-2 py-1 rounded-lg border border-slate-200">
              <Calendar className="h-3.5 w-3.5 text-slate-400" />
              <input
                type="date"
                value={fromDate}
                onChange={(e) => {
                  setFromDate(e.target.value);
                  setPage(0);
                }}
                className="bg-transparent text-slate-700 focus:outline-none text-xs"
              />
              <span className="text-slate-400">to</span>
              <input
                type="date"
                value={toDate}
                onChange={(e) => {
                  setToDate(e.target.value);
                  setPage(0);
                }}
                className="bg-transparent text-slate-700 focus:outline-none text-xs"
              />
            </div>
          </div>
        </div>

        {/* Secondary filters & search */}
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-slate-500 font-medium">Status:</span>
            <select
              value={businessStatus}
              onChange={(e) => {
                setBusinessStatus(e.target.value);
                setPage(0);
              }}
              className="p-1.5 border border-slate-300 rounded-lg bg-white text-xs"
            >
              <option value="ALL">All Statuses</option>
              <option value="PRESENT">Present</option>
              <option value="PARTIAL">Partial</option>
              <option value="ABSENT">Absent</option>
              <option value="REST">Rest Day</option>
              <option value="ON_LEAVE">On Leave</option>
            </select>
          </div>

          <div className="relative w-64">
            <Search className="h-3.5 w-3.5 text-slate-400 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Search by worker or Tally ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-emerald-500"
            />
          </div>
        </div>
      </div>

      {/* Main Table */}
      <AttendanceTable
        records={filteredRecords}
        loading={loading}
        onSelectRecord={(rec) => setSelectedRecord(rec)}
      />

      {/* Pagination Footer */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between bg-white px-4 py-3 rounded-xl border border-slate-200 text-xs text-slate-600">
          <div>
            Showing <span className="font-semibold text-slate-900">{page * pageSize + 1}</span> to{" "}
            <span className="font-semibold text-slate-900">
              {Math.min((page + 1) * pageSize, total)}
            </span>{" "}
            of <span className="font-semibold text-slate-900">{total}</span> records
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="p-1.5 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-40"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="font-medium">
              Page {page + 1} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="p-1.5 border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-40"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Detail Drawer */}
      {selectedRecord && (
        <AttendanceDetailDrawer
          record={selectedRecord}
          onClose={() => setSelectedRecord(null)}
          onRecordUpdated={() => {
            fetchAttendance();
            // keep drawer updated
            fetch(`/api/v1/attendance/${selectedRecord.id}`, {
              headers: { Authorization: `Bearer ${token}` },
            })
              .then((res) => res.json())
              .then((updated) => setSelectedRecord(updated))
              .catch(() => {});
          }}
        />
      )}

      {/* Recalculate Modal */}
      <RecalculateModal
        open={showRecalculateModal}
        onClose={() => setShowRecalculateModal(false)}
        onRecalculated={() => fetchAttendance()}
      />
    </div>
  );
};
