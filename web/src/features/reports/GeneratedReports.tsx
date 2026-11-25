import React, { useState, useEffect, useCallback } from "react";
import {
  FileSpreadsheet,
  Download,
  RefreshCw,
  Search,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { EmptyState, useToast } from "../../ui";
import {
  GeneratedReportItem,
  GeneratedReportFilters,
  fetchGeneratedReports,
  downloadFile,
} from "./api";

export const GeneratedReports: React.FC = () => {
  const { token } = useAuth();
  const toast = useToast();
  const [reports, setReports] = useState<GeneratedReportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Filters
  const [countryFilter, setCountryFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [kindFilter, setKindFilter] = useState<string>("");
  const [periodFilter, setPeriodFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Download state per item
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const loadReports = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const filters: GeneratedReportFilters = {};
      if (countryFilter) filters.country = countryFilter;
      if (statusFilter) filters.status = statusFilter;
      if (kindFilter) filters.kind = kindFilter;
      if (periodFilter) filters.period = periodFilter;

      const data = await fetchGeneratedReports(filters, token);
      setReports(data);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to load generated reports history");
    } finally {
      setLoading(false);
    }
  }, [countryFilter, statusFilter, kindFilter, periodFilter, token]);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  const handleDownload = async (item: GeneratedReportItem) => {
    setDownloadingId(item.id);
    try {
      await downloadFile(item.download_url, item.file_name, token);
    } catch (err: unknown) {
      toast.error(err, "Download failed.");
    } finally {
      setDownloadingId(null);
    }
  };

  const filteredItems = reports.filter((item) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      item.file_name.toLowerCase().includes(q) ||
      item.report_key.toLowerCase().includes(q) ||
      item.generated_by.toLowerCase().includes(q)
    );
  });

  const formatFileSize = (bytes?: number | null) => {
    if (!bytes) return "0 KB";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Header and Summary Bar */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-5 flex flex-col gap-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Generated Reports Section</h2>
            <p className="text-xs text-slate-500 mt-1">
              Historical archive of automated month-end packages and on-demand exports (DEC-46).
            </p>
          </div>
          <button
            onClick={loadReports}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 transition self-start sm:self-auto"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh Archive</span>
          </button>
        </div>

        {/* Filter Controls */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3 items-end pt-2 border-t border-slate-100">
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Search File</label>
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search filename..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full text-xs pl-8 pr-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Country</label>
            <select
              value={countryFilter}
              onChange={(e) => setCountryFilter(e.target.value)}
              className="w-full text-xs px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Countries</option>
              <option value="AE">United Arab Emirates (AE)</option>
              <option value="SA">Saudi Arabia (SA)</option>
              <option value="QA">Qatar (QA)</option>
              <option value="OM">Oman (OM)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Status</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full text-xs px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Statuses</option>
              <option value="DRAFT">Draft</option>
              <option value="APPROVED">Approved</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Type</label>
            <select
              value={kindFilter}
              onChange={(e) => setKindFilter(e.target.value)}
              className="w-full text-xs px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Types</option>
              <option value="MONTH_END">Month-End Auto Package</option>
              <option value="ON_DEMAND">On-Demand Export</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Period (YYYY-MM)</label>
            <input
              type="text"
              placeholder="e.g. 2026-10"
              value={periodFilter}
              onChange={(e) => setPeriodFilter(e.target.value)}
              className="w-full text-xs px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {errorMsg && (
          <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}
      </div>

      {/* Generated Reports Table */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col">
        <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <span className="text-xs font-semibold text-slate-700">
            Archive History ({filteredItems.length} files)
          </span>
          <span className="text-[11px] text-slate-400">
            Files are retained immutably with SHA-256 integrity verification
          </span>
        </div>

        <div className={filteredItems.length > 0 && !loading ? "overflow-x-auto fw-scroll" : undefined}>
          {loading ? (
            <div className="py-20 flex flex-col items-center justify-center gap-2 text-slate-400">
              <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
              <span className="text-xs">Loading generated report records...</span>
            </div>
          ) : filteredItems.length === 0 ? (
            <EmptyState
              icon={<FileSpreadsheet className="h-5 w-5" />}
              title="No generated reports yet"
              description="Month-end packages appear here when a payroll draft is created and approved."
            />
          ) : (
            <table className="w-full text-left text-xs text-slate-700 border-collapse">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold">
                <tr>
                  <th className="px-4 py-3">File Name</th>
                  <th className="px-3 py-3">Report</th>
                  <th className="px-3 py-3">Country</th>
                  <th className="px-3 py-3">Period</th>
                  <th className="px-3 py-3">Version</th>
                  <th className="px-3 py-3">Status</th>
                  <th className="px-3 py-3">Role Visibility</th>
                  <th className="px-3 py-3">Generated At</th>
                  <th className="px-3 py-3">Size</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredItems.map((item) => {
                  const isDownloading = downloadingId === item.id;
                  const isDraft = item.status === "DRAFT";
                  return (
                    <tr key={item.id} className="hover:bg-slate-50/70 transition">
                      <td className="px-4 py-3 font-mono text-[11px] text-blue-600 font-medium">
                        <div className="flex items-center gap-2">
                          <FileSpreadsheet className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                          <span className="truncate max-w-xs" title={item.file_name}>
                            {item.file_name}
                          </span>
                        </div>
                      </td>
                      <td className="px-3 py-3 font-medium text-slate-800">
                        {item.report_key}
                      </td>
                      <td className="px-3 py-3 font-semibold text-slate-600">
                        {item.country}
                      </td>
                      <td className="px-3 py-3 text-slate-600 whitespace-nowrap">
                        {item.period_start} to {item.period_end}
                      </td>
                      <td className="px-3 py-3 font-bold text-slate-700">
                        v{item.version_no}
                      </td>
                      <td className="px-3 py-3">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wide uppercase ${
                            isDraft
                              ? "bg-amber-50 text-amber-700 border border-amber-200"
                              : "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          }`}
                        >
                          {isDraft ? "DRAFT" : "APPROVED"}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex flex-wrap gap-1 max-w-xs">
                          {item.visible_roles.map((r) => (
                            <span
                              key={r}
                              className="px-1.5 py-0.5 text-[9px] font-medium bg-slate-100 text-slate-600 rounded"
                            >
                              {r}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-3 py-3 text-slate-500 whitespace-nowrap">
                        {new Date(item.generated_at).toLocaleString()}
                      </td>
                      <td className="px-3 py-3 font-mono text-slate-500">
                        {formatFileSize(item.file_size_bytes)}
                      </td>
                      <td className="px-4 py-3 text-right whitespace-nowrap">
                        <button
                          onClick={() => handleDownload(item)}
                          disabled={isDownloading}
                          className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-lg bg-blue-50 text-blue-700 hover:bg-blue-100 transition disabled:opacity-50"
                        >
                          {isDownloading ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Download className="w-3.5 h-3.5" />
                          )}
                          <span>Download</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};
