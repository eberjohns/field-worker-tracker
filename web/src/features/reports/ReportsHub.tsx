import React, { useState, useEffect, useCallback } from "react";
import {
  FileSpreadsheet,
  FileText,
  FileDown,
  Search,
  RefreshCw,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import {
  ReportMetadata,
  ReportDataResponse,
  ReportFilterParams,
  fetchReportsRegistry,
  fetchReportData,
  triggerExportJob,
  getExportStatus,
  downloadFile,
} from "./api";
import { DatePicker, EmptyState } from "../../ui";

export const ReportsHub: React.FC = () => {
  const { token, user } = useAuth();
  const [reports, setReports] = useState<ReportMetadata[]>([]);
  const [selectedReport, setSelectedReport] = useState<ReportMetadata | null>(null);
  const [loadingCatalog, setLoadingCatalog] = useState(true);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  // Search for catalog
  const [searchQuery, setSearchQuery] = useState("");

  // Report execution state
  const [filterParams, setFilterParams] = useState<ReportFilterParams>({
    date_from: new Date().toISOString().slice(0, 10),
    date_to: new Date().toISOString().slice(0, 10),
    year: new Date().getFullYear(),
    month: new Date().getMonth() + 1,
    country: "AE",
  });
  const [reportData, setReportData] = useState<ReportDataResponse | null>(null);
  const [runningReport, setRunningReport] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

  // Export job state
  const [exportingFormat, setExportingFormat] = useState<string | null>(null);
  const [exportMessage, setExportMessage] = useState<string | null>(null);

  // Load available reports on mount
  const loadCatalog = useCallback(async () => {
    setLoadingCatalog(true);
    setCatalogError(null);
    try {
      const list = await fetchReportsRegistry(token);
      setReports(list);
      if (list.length > 0 && !selectedReport) {
        setSelectedReport(list[0]);
      }
    } catch (err: any) {
      setCatalogError(err.message || "Failed to load reports catalog");
    } finally {
      setLoadingCatalog(false);
    }
  }, [token]);

  useEffect(() => {
    loadCatalog();
  }, [loadCatalog]);

  // Run report preview
  const handleRunReport = async () => {
    if (!selectedReport) return;
    setRunningReport(true);
    setReportError(null);
    try {
      const data = await fetchReportData(selectedReport.key, filterParams, token);
      setReportData(data);
    } catch (err: any) {
      setReportError(err.message || "Failed to generate report data preview");
      setReportData(null);
    } finally {
      setRunningReport(false);
    }
  };

  // Trigger file export and poll
  const handleExport = async (format: "xlsx" | "csv" | "pdf") => {
    if (!selectedReport) return;
    setExportingFormat(format);
    setExportMessage(`Initiating ${format.toUpperCase()} export job...`);
    try {
      const job = await triggerExportJob(selectedReport.key, filterParams, format, token);
      let currentJob = job;

      // Poll until COMPLETED or FAILED (or timeout after 60s)
      let attempts = 0;
      while (
        (currentJob.status === "PENDING" || currentJob.status === "PROCESSING") &&
        attempts < 30
      ) {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        attempts += 1;
        setExportMessage(
          `Generating ${format.toUpperCase()} file (${currentJob.status.toLowerCase()})...`
        );
        currentJob = await getExportStatus(currentJob.id, token);
      }

      if (currentJob.status === "COMPLETED" && currentJob.download_url) {
        setExportMessage("Downloading file...");
        await downloadFile(
          currentJob.download_url,
          currentJob.file_name || `${selectedReport.key}.${format}`,
          token
        );
        setExportMessage(null);
      } else if (currentJob.status === "FAILED") {
        setReportError(currentJob.error_message || "Export processing failed");
      } else {
        setReportError("Export took too long. Check the background jobs queue.");
      }
    } catch (err: any) {
      setReportError(err.message || "Export failed");
    } finally {
      setExportingFormat(null);
      setExportMessage(null);
    }
  };

  // Filter catalog list by search query
  const filteredReports = reports.filter((r) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return r.name.toLowerCase().includes(q) || r.description.toLowerCase().includes(q);
  });

  return (
    <div className="flex flex-col lg:flex-row gap-6">
      {/* Left Sidebar: Reports Catalog */}
      <div className="w-full lg:w-80 flex-shrink-0 bg-white border border-slate-200 rounded-xl shadow-sm p-4 flex flex-col gap-4">
        <div>
          <h2 className="text-base font-semibold text-slate-900">Reports Catalog</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Select a report configured for role {user?.role || "USER"}
          </p>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
          <input
            type="text"
            placeholder="Search reports..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-sm bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition"
          />
        </div>

        {/* List of Reports */}
        <div className="flex-1 overflow-y-auto fw-scroll space-y-1 pr-1 max-h-[500px] lg:max-h-[calc(100vh-320px)]">
          {loadingCatalog ? (
            <div className="py-8 text-center text-slate-400 flex flex-col items-center gap-2">
              <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
              <span className="text-xs">Loading report definitions...</span>
            </div>
          ) : catalogError ? (
            <div className="p-3 bg-red-50 text-red-700 rounded-lg text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{catalogError}</span>
            </div>
          ) : filteredReports.length === 0 ? (
            <div className="py-8 text-center text-slate-400 text-xs">
              No matching reports found.
            </div>
          ) : (
            filteredReports.map((r) => {
              const isSelected = selectedReport?.key === r.key;
              return (
                <button
                  key={r.key}
                  onClick={() => {
                    setSelectedReport(r);
                    setReportData(null);
                    setReportError(null);
                  }}
                  className={`w-full text-left p-3 rounded-lg border transition flex flex-col gap-1 ${
                    isSelected
                      ? "bg-blue-50/70 border-blue-200 text-blue-900 shadow-sm"
                      : "border-transparent hover:bg-slate-50 text-slate-700"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold leading-tight">{r.name}</span>
                    <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                      {r.category}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-500 line-clamp-2 leading-relaxed">
                    {r.description}
                  </p>
                  <div className="flex items-center gap-1.5 mt-1">
                    {r.supported_formats.map((fmt) => (
                      <span
                        key={fmt}
                        className={`text-[9px] font-semibold px-1 py-0.2 rounded uppercase ${
                          fmt === "xlsx"
                            ? "bg-emerald-50 text-emerald-700"
                            : fmt === "pdf"
                            ? "bg-rose-50 text-rose-700"
                            : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {fmt}
                      </span>
                    ))}
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>

      {/* Right Area: Selected Report Runner & Results */}
      <div className="flex-1 flex flex-col gap-4">
        {selectedReport ? (
          <>
            {/* Header and Filter Toolbar */}
            <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-5 flex flex-col gap-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h1 className="text-lg font-bold text-slate-900">{selectedReport.name}</h1>
                    <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-slate-100 text-slate-600">
                      {selectedReport.key}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">{selectedReport.description}</p>
                </div>

                {/* Export Buttons */}
                <div className="flex items-center gap-2 flex-wrap">
                  {selectedReport.supported_formats.includes("xlsx") && (
                    <button
                      onClick={() => handleExport("xlsx")}
                      disabled={exportingFormat !== null}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition disabled:opacity-50 shadow-sm"
                    >
                      {exportingFormat === "xlsx" ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <FileSpreadsheet className="w-3.5 h-3.5" />
                      )}
                      <span>Export Excel</span>
                    </button>
                  )}
                  {selectedReport.supported_formats.includes("csv") && (
                    <button
                      onClick={() => handleExport("csv")}
                      disabled={exportingFormat !== null}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-700 text-white hover:bg-slate-800 transition disabled:opacity-50 shadow-sm"
                    >
                      {exportingFormat === "csv" ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <FileText className="w-3.5 h-3.5" />
                      )}
                      <span>Export CSV</span>
                    </button>
                  )}
                  {selectedReport.supported_formats.includes("pdf") && (
                    <button
                      onClick={() => handleExport("pdf")}
                      disabled={exportingFormat !== null}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-rose-600 text-white hover:bg-rose-700 transition disabled:opacity-50 shadow-sm"
                    >
                      {exportingFormat === "pdf" ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <FileDown className="w-3.5 h-3.5" />
                      )}
                      <span>Export PDF</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Dynamic Filter Controls */}
              {(() => {
                const schema = selectedReport.filter_schema || {};
                const isMonthly = Boolean(
                  schema["year"] ||
                    schema["month"] ||
                    ["monthly-attendance", "payroll", "provisions-staff-cost", "job-costing", "employee-utilization"].includes(
                      selectedReport.key
                    )
                );
                const isExpiry = Boolean(
                  schema["days_ahead"] || selectedReport.key === "document-expiry"
                );
                const isDateRange = !isMonthly && !isExpiry;

                return (
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 items-end">
                    {/* Date range for daily/movements/visits */}
                    {isDateRange && (
                      <>
                        <div>
                          <DatePicker
                            label="From Date"
                            value={filterParams.date_from || ""}
                            onChange={(iso) => setFilterParams((prev) => ({ ...prev, date_from: iso }))}
                            size="lg"
                          />
                        </div>
                        <div>
                          <DatePicker
                            label="To Date"
                            value={filterParams.date_to || ""}
                            onChange={(iso) => setFilterParams((prev) => ({ ...prev, date_to: iso }))}
                            size="lg"
                          />
                        </div>
                      </>
                    )}

                    {/* Year & Month for monthly/payroll */}
                    {isMonthly && (
                      <>
                        <div>
                          <label className="block text-xs font-medium text-slate-700 mb-1">Year</label>
                          <select
                            value={filterParams.year || 2026}
                            onChange={(e) =>
                              setFilterParams((prev) => ({ ...prev, year: Number(e.target.value) }))
                            }
                            className="w-full text-xs px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                          >
                            <option value={2026}>2026</option>
                            <option value={2025}>2025</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-700 mb-1">Month</label>
                          <select
                            value={filterParams.month || 11}
                            onChange={(e) =>
                              setFilterParams((prev) => ({ ...prev, month: Number(e.target.value) }))
                            }
                            className="w-full text-xs px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                          >
                            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                              <option key={m} value={m}>
                                {new Date(2026, m - 1).toLocaleString("default", { month: "long" })}
                              </option>
                            ))}
                          </select>
                        </div>
                      </>
                    )}

                    {/* Lead Days for Document Expiry */}
                    {isExpiry && (
                      <div>
                        <label className="block text-xs font-medium text-slate-700 mb-1">
                          Expiry Horizon
                        </label>
                        <select
                          value={filterParams.days_ahead || 30}
                          onChange={(e) =>
                            setFilterParams((prev) => ({ ...prev, days_ahead: Number(e.target.value) }))
                          }
                          className="w-full text-xs px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                          <option value={30}>Next 30 Days</option>
                          <option value={60}>Next 60 Days</option>
                          <option value={90}>Next 90 Days</option>
                          <option value={180}>Next 180 Days</option>
                        </select>
                      </div>
                    )}

                    {/* Country */}
                    <div>
                      <label className="block text-xs font-medium text-slate-700 mb-1">Country</label>
                      <select
                        value={filterParams.country || "AE"}
                        onChange={(e) =>
                          setFilterParams((prev) => ({ ...prev, country: e.target.value }))
                        }
                        className="w-full text-xs px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="AE">United Arab Emirates (AE)</option>
                        <option value="SA">Saudi Arabia (SA)</option>
                        <option value="QA">Qatar (QA)</option>
                        <option value="OM">Oman (OM)</option>
                      </select>
                    </div>

                    {/* Run Button */}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={handleRunReport}
                        disabled={runningReport}
                        className="flex-1 inline-flex items-center justify-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-lg bg-blue-600 text-white hover:bg-blue-700 transition disabled:opacity-50 shadow-sm"
                      >
                        {runningReport ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <RefreshCw className="w-3.5 h-3.5" />
                        )}
                        <span>Run Preview</span>
                      </button>
                    </div>
                  </div>
                );
              })()}

              {/* Export Status Notification Banner */}
              {exportMessage && (
                <div className="p-2.5 bg-blue-50 border border-blue-200 text-blue-800 rounded-lg text-xs flex items-center gap-2 animate-pulse">
                  <Loader2 className="w-4 h-4 animate-spin flex-shrink-0" />
                  <span>{exportMessage}</span>
                </div>
              )}

              {/* Error Message */}
              {reportError && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{reportError}</span>
                </div>
              )}
            </div>

            {/* Results Table */}
            <div className="flex-1 bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col">
              <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                <span className="text-xs font-semibold text-slate-700">
                  Data Preview ({reportData ? `${reportData.total_rows} rows` : "No data loaded"})
                </span>
                {reportData && (
                  <span className="text-[11px] text-slate-400">
                    Generated at {new Date(reportData.generated_at).toLocaleTimeString()}
                  </span>
                )}
              </div>

              {/* Scrolls only when there is a table: an empty preview shows no scrollbar (Batch 10 B). */}
              <div className={reportData && reportData.data.length > 0 && !runningReport ? "flex-1 overflow-auto fw-scroll max-h-[600px]" : "flex-1"}>
                {runningReport ? (
                  <div className="py-20 flex flex-col items-center justify-center gap-2 text-slate-400">
                    <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
                    <span className="text-xs">Computing report rows...</span>
                  </div>
                ) : !reportData ? (
                  <EmptyState
                    icon={<FileSpreadsheet className="h-5 w-5" />}
                    title={`Ready to generate ${selectedReport.name}`}
                    description='Set your filters above and click "Run Preview", or "Export Excel" to download directly.'
                  />
                ) : reportData.data.length === 0 ? (
                  <EmptyState title="No matching records" description="Nothing matches the selected period and criteria." />
                ) : (
                  <table className="w-full text-left text-xs text-slate-700 border-collapse">
                    <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold sticky top-0 z-10 shadow-sm">
                      <tr>
                        {reportData.columns.map((col) => (
                          <th
                            key={col.key}
                            className="px-3 py-2.5 whitespace-nowrap border-r border-slate-100 last:border-0"
                          >
                            {col.label}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {reportData.data.map((row, idx) => (
                        <tr key={idx} className="hover:bg-slate-50/70 transition">
                          {reportData.columns.map((col) => {
                            const val = row[col.key];
                            return (
                              <td
                                key={col.key}
                                className="px-3 py-2 whitespace-nowrap border-r border-slate-50 last:border-0 font-mono text-[11px]"
                              >
                                {val !== null && val !== undefined ? String(val) : "-"}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="bg-white border border-slate-200 rounded-xl">
            <EmptyState title="No report selected" description="Select a report from the catalog." />
          </div>
        )}
      </div>
    </div>
  );
};
