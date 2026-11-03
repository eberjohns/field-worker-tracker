import React, { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import {
  UploadCloud,
  FileSpreadsheet,
  Download,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RotateCcw,
  RefreshCw,
  Info,
  Filter,
} from "lucide-react";

interface ImportRow {
  id: string;
  batch_id: string;
  sheet: string;
  row_number: number;
  natural_key: string;
  action: "NEW" | "UPDATED" | "UNCHANGED" | "REACTIVATED" | "CLASH" | "ERROR" | "SKIPPED";
  status: "OK" | "WARNING" | "ERROR" | "INFO";
  codes: string[];
  messages: Array<{ field?: string; code: string; message: string }>;
  diff: Record<string, { old: any; new: any }>;
  normalized: Record<string, any>;
}

interface ImportBatch {
  id: string;
  kind: string;
  filename: string;
  template_version: string;
  status: string;
  summary: {
    total_rows?: number;
    counts?: Record<string, number>;
    sheet_counts?: Record<string, Record<string, number>>;
    can_commit?: boolean;
  };
  committed_at: string | null;
  created_at: string;
}

export const Imports: React.FC = () => {
  const { token, user } = useAuth();
  const [activeTab, setActiveTab] = useState<"upload" | "history">("upload");

  // Upload & preview state
  const [isUploading, setIsUploading] = useState(false);
  const [currentBatch, setCurrentBatch] = useState<ImportBatch | null>(null);
  const [previewRows, setPreviewRows] = useState<ImportRow[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [sheetFilter, setSheetFilter] = useState<string>("ALL");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Commit / rollback state
  const [isCommitting, setIsCommitting] = useState(false);
  const [batchesHistory, setBatchesHistory] = useState<ImportBatch[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Load history when tab changes
  useEffect(() => {
    if (activeTab === "history") {
      fetchHistory();
    }
  }, [activeTab]);

  const fetchHistory = async () => {
    setHistoryLoading(true);
    try {
      const res = await fetch("/api/v1/imports", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setBatchesHistory(await res.json());
      }
    } catch {
      // ignore
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/v1/imports", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail?.message || "Failed to parse import workbook.");
      }

      const previewData = await res.json();
      setCurrentBatch({
        id: previewData.batch_id,
        kind: "FULL_WORKBOOK",
        filename: previewData.filename,
        template_version: previewData.template_version,
        status: previewData.status,
        summary: previewData.summary,
        committed_at: null,
        created_at: new Date().toISOString(),
      });
      setPreviewRows(previewData.rows);
      setSuccessMessage(`Workbook '${previewData.filename}' parsed successfully. Review preview before committing.`);
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setIsUploading(false);
    }
  };

  const handleCommit = async () => {
    if (!currentBatch) return;
    if (!window.confirm("Are you sure you want to commit these changes to the database? This operation is atomic.")) {
      return;
    }

    setIsCommitting(true);
    setErrorMessage(null);
    try {
      const res = await fetch(`/api/v1/imports/${currentBatch.id}/commit`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail?.message || "Failed to commit import batch.");
      }

      const commitRes = await res.json();
      setCurrentBatch((prev) => (prev ? { ...prev, status: "COMMITTED", committed_at: commitRes.committed_at } : null));
      setSuccessMessage("Batch committed successfully! Master data and salary records have been saved.");
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setIsCommitting(false);
    }
  };

  const handleRollback = async (batchId: string) => {
    if (!window.confirm("Rollback this committed batch? Records created by this batch will be reverted.")) {
      return;
    }
    try {
      const res = await fetch(`/api/v1/imports/${batchId}/rollback`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setSuccessMessage("Batch rolled back successfully.");
        fetchHistory();
      } else {
        const err = await res.json();
        alert(err.detail?.message || "Rollback failed.");
      }
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleDownloadTemplate = () => {
    window.open("/api/v1/imports/template", "_blank");
  };

  const handleDownloadErrors = () => {
    if (!currentBatch) return;
    window.open(`/api/v1/imports/${currentBatch.id}/errors.xlsx`, "_blank");
  };

  // Filter rows
  const filteredRows = previewRows.filter((row) => {
    if (statusFilter !== "ALL") {
      if (statusFilter === "NEW" && row.action !== "NEW") return false;
      if (statusFilter === "UPDATED" && row.action !== "UPDATED") return false;
      if (statusFilter === "UNCHANGED" && row.action !== "UNCHANGED") return false;
      if (statusFilter === "WARNINGS" && row.status !== "WARNING") return false;
      if (statusFilter === "ERRORS" && row.status !== "ERROR") return false;
    }
    if (sheetFilter !== "ALL" && row.sheet !== sheetFilter) return false;
    return true;
  });

  const availableSheets = Array.from(new Set(previewRows.map((r) => r.sheet)));

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Master Data Import</h1>
          <p className="text-sm text-slate-500">
            Bulk load and preview master data, organization structures, and effective-dated salary records.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleDownloadTemplate}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 transition-colors"
          >
            <Download className="h-4 w-4 text-slate-500" />
            Download Template (.xlsx)
          </button>
        </div>
      </div>

      {/* Rules Notice */}
      <div className="rounded-xl border border-indigo-100 bg-indigo-50/60 p-4">
        <div className="flex items-start gap-3">
          <Info className="h-5 w-5 text-indigo-600 mt-0.5 shrink-0" />
          <div className="text-sm text-indigo-900">
            <span className="font-semibold">Import Cell Rules:</span> A{" "}
            <span className="font-mono bg-white px-1 py-0.5 rounded border border-indigo-200">blank</span> cell keeps the
            existing database value. A cell with{" "}
            <span className="font-mono bg-white px-1 py-0.5 rounded border border-indigo-200 font-bold">_</span> (single
            underscore) clears an optional field. Records are{" "}
            <span className="font-semibold underline">never deleted</span> by an import.
          </div>
        </div>
      </div>

      {/* Alerts */}
      {errorMessage && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <XCircle className="h-4 w-4 text-red-600" />
            {errorMessage}
          </div>
          <button onClick={() => setErrorMessage(null)} className="text-red-500 hover:text-red-700">
            Dismiss
          </button>
        </div>
      )}
      {successMessage && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            {successMessage}
          </div>
          <button onClick={() => setSuccessMessage(null)} className="text-emerald-500 hover:text-emerald-700">
            Dismiss
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-slate-200">
        <button
          onClick={() => setActiveTab("upload")}
          className={`pb-3 px-4 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "upload"
              ? "border-indigo-600 text-indigo-600 font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          Upload & Preview
        </button>
        <button
          onClick={() => setActiveTab("history")}
          className={`pb-3 px-4 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "history"
              ? "border-indigo-600 text-indigo-600 font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          Import History
        </button>
      </div>

      {/* Tab: Upload & Preview */}
      {activeTab === "upload" && (
        <div className="space-y-6">
          {/* Upload Zone */}
          {!currentBatch && (
            <div className="rounded-xl border-2 border-dashed border-slate-300 bg-white p-12 text-center hover:border-indigo-400 transition-colors">
              <UploadCloud className="mx-auto h-12 w-12 text-slate-400 mb-4" />
              <h3 className="text-base font-semibold text-slate-900">Upload Filled Template Workbook</h3>
              <p className="mt-1 text-sm text-slate-500 max-w-sm mx-auto">
                Drag and drop your <code className="font-mono text-slate-700">.xlsx</code> workbook or browse to inspect
                diffs before committing.
              </p>
              <div className="mt-6">
                <label className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 cursor-pointer transition-colors">
                  <FileSpreadsheet className="h-4 w-4" />
                  {isUploading ? "Uploading & Analyzing..." : "Select Template File"}
                  <input
                    type="file"
                    accept=".xlsx,.xlsm"
                    className="hidden"
                    onChange={handleFileUpload}
                    disabled={isUploading}
                  />
                </label>
              </div>
            </div>
          )}

          {/* Batch Summary & Preview Controls */}
          {currentBatch && (
            <div className="space-y-6">
              <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-900 text-lg">{currentBatch.filename}</span>
                    <span
                      className={`px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase ${
                        currentBatch.status === "COMMITTED"
                          ? "bg-emerald-100 text-emerald-800"
                          : currentBatch.status === "PREVIEWED"
                          ? "bg-blue-100 text-blue-800"
                          : "bg-slate-100 text-slate-800"
                      }`}
                    >
                      {currentBatch.status}
                    </span>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-4 text-sm text-slate-500">
                    <span>Total Rows: {currentBatch.summary.total_rows ?? 0}</span>
                    <span>•</span>
                    <span className="text-emerald-700 font-medium">New: {currentBatch.summary.counts?.NEW ?? 0}</span>
                    <span>•</span>
                    <span className="text-blue-700 font-medium">
                      Updated: {currentBatch.summary.counts?.UPDATED ?? 0}
                    </span>
                    <span>•</span>
                    <span className="text-slate-600">Unchanged: {currentBatch.summary.counts?.UNCHANGED ?? 0}</span>
                    <span>•</span>
                    <span className="text-amber-700 font-medium">
                      Warnings: {currentBatch.summary.counts?.WARNING ?? 0}
                    </span>
                    <span>•</span>
                    <span className="text-red-700 font-medium">
                      Errors: {currentBatch.summary.counts?.ERROR ?? 0}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  {(currentBatch.summary.counts?.ERROR ?? 0) > 0 && (
                    <button
                      onClick={handleDownloadErrors}
                      className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg border border-red-300 text-red-700 bg-red-50 hover:bg-red-100"
                    >
                      <Download className="h-4 w-4" />
                      Download Error Report
                    </button>
                  )}

                  {currentBatch.status !== "COMMITTED" && (
                    <button
                      onClick={handleCommit}
                      disabled={isCommitting || !currentBatch.summary.can_commit}
                      className={`inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold rounded-lg shadow-sm text-white transition-all ${
                        currentBatch.summary.can_commit
                          ? "bg-indigo-600 hover:bg-indigo-700 cursor-pointer"
                          : "bg-slate-300 cursor-not-allowed opacity-70"
                      }`}
                    >
                      <CheckCircle2 className="h-4 w-4" />
                      {isCommitting ? "Committing in 1 Transaction..." : "Confirm & Commit"}
                    </button>
                  )}

                  <label className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-lg border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 cursor-pointer">
                    <RefreshCw className="h-4 w-4 text-slate-500" />
                    Re-upload
                    <input type="file" accept=".xlsx,.xlsm" className="hidden" onChange={handleFileUpload} />
                  </label>
                </div>
              </div>

              {/* Filter Bar */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-4 rounded-xl border border-slate-200">
                {/* Status Pills */}
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider mr-1">Status:</span>
                  {["ALL", "NEW", "UPDATED", "UNCHANGED", "WARNINGS", "ERRORS"].map((filter) => (
                    <button
                      key={filter}
                      onClick={() => setStatusFilter(filter)}
                      className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                        statusFilter === filter
                          ? "bg-slate-900 text-white font-semibold"
                          : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                      }`}
                    >
                      {filter}
                    </button>
                  ))}
                </div>

                {/* Sheet Selector */}
                <div className="flex items-center gap-2">
                  <Filter className="h-4 w-4 text-slate-400" />
                  <select
                    value={sheetFilter}
                    onChange={(e) => setSheetFilter(e.target.value)}
                    className="rounded-lg border border-slate-300 bg-white py-1.5 px-3 text-xs font-medium text-slate-700 shadow-sm focus:border-indigo-500 focus:outline-none"
                  >
                    <option value="ALL">All Sheets ({previewRows.length})</option>
                    {availableSheets.map((s) => (
                      <option key={s} value={s}>
                        {s} ({previewRows.filter((r) => r.sheet === s).length})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Rows Diff Table */}
              <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                    <thead className="bg-slate-50 text-slate-600 font-medium text-xs">
                      <tr>
                        <th className="py-3 px-4">Sheet</th>
                        <th className="py-3 px-4">Row</th>
                        <th className="py-3 px-4">Natural Key</th>
                        <th className="py-3 px-4">Action</th>
                        <th className="py-3 px-4">Status</th>
                        <th className="py-3 px-4">Field Changes / Values</th>
                        <th className="py-3 px-4">Codes & Messages</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 text-slate-700">
                      {filteredRows.length === 0 ? (
                        <tr>
                          <td colSpan={7} className="py-8 text-center text-slate-400">
                            No rows matching selected filter.
                          </td>
                        </tr>
                      ) : (
                        filteredRows.map((r) => {
                          const hasDiff = Object.keys(r.diff).length > 0;
                          return (
                            <tr
                              key={r.id}
                              className={`hover:bg-slate-50/80 transition-colors ${
                                r.status === "ERROR" ? "bg-red-50/30" : ""
                              }`}
                            >
                              <td className="py-3 px-4 font-medium text-slate-900">{r.sheet}</td>
                              <td className="py-3 px-4 text-slate-500 font-mono text-xs">{r.row_number}</td>
                              <td className="py-3 px-4 font-mono text-xs font-medium text-slate-800">{r.natural_key}</td>
                              <td className="py-3 px-4">
                                <span
                                  className={`inline-flex px-2 py-0.5 rounded text-xs font-semibold ${
                                    r.action === "NEW"
                                      ? "bg-emerald-100 text-emerald-800"
                                      : r.action === "UPDATED"
                                      ? "bg-blue-100 text-blue-800"
                                      : r.action === "UNCHANGED"
                                      ? "bg-slate-100 text-slate-700"
                                      : r.action === "REACTIVATED"
                                      ? "bg-purple-100 text-purple-800"
                                      : r.action === "SKIPPED"
                                      ? "bg-amber-100 text-amber-800"
                                      : "bg-red-100 text-red-800"
                                  }`}
                                >
                                  {r.action}
                                </span>
                              </td>
                              <td className="py-3 px-4">
                                <span
                                  className={`inline-flex items-center gap-1 text-xs font-medium ${
                                    r.status === "OK"
                                      ? "text-emerald-700"
                                      : r.status === "WARNING"
                                      ? "text-amber-700"
                                      : r.status === "INFO"
                                      ? "text-slate-500"
                                      : "text-red-700 font-semibold"
                                  }`}
                                >
                                  {r.status === "OK" && <CheckCircle2 className="h-3.5 w-3.5" />}
                                  {r.status === "WARNING" && <AlertTriangle className="h-3.5 w-3.5" />}
                                  {r.status === "ERROR" && <XCircle className="h-3.5 w-3.5" />}
                                  {r.status}
                                </span>
                              </td>
                              <td className="py-3 px-4 max-w-md">
                                {hasDiff ? (
                                  <div className="space-y-1">
                                    {Object.entries(r.diff).map(([field, delta]) => (
                                      <div key={field} className="text-xs font-mono">
                                        <span className="font-semibold text-slate-600">{field}:</span>{" "}
                                        <span className="line-through text-red-600 bg-red-50 px-1 rounded">
                                          {String(delta.old ?? "(blank)")}
                                        </span>{" "}
                                        &rarr;{" "}
                                        <span className="text-emerald-700 font-semibold bg-emerald-50 px-1 rounded">
                                          {String(delta.new ?? "(blank)")}
                                        </span>
                                      </div>
                                    ))}
                                  </div>
                                ) : r.action === "NEW" ? (
                                  <span className="text-xs text-slate-500 italic">
                                    New entity ({Object.keys(r.normalized).length} fields)
                                  </span>
                                ) : (
                                  <span className="text-xs text-slate-400">Identical with database</span>
                                )}
                              </td>
                              <td className="py-3 px-4">
                                {r.messages.length > 0 ? (
                                  <div className="space-y-1">
                                    {r.messages.map((m, mIdx) => (
                                      <div
                                        key={mIdx}
                                        className={`text-xs ${
                                          r.status === "ERROR" ? "text-red-700 font-medium" : "text-amber-700"
                                        }`}
                                      >
                                        <span className="font-mono font-bold mr-1">[{m.code}]</span>
                                        {m.message}
                                      </div>
                                    ))}
                                  </div>
                                ) : (
                                  <span className="text-xs text-slate-400">-</span>
                                )}
                              </td>
                            </tr>
                          );
                        })
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab: Import History */}
      {activeTab === "history" && (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          {historyLoading ? (
            <div className="p-8 text-center text-slate-400">Loading batch history...</div>
          ) : batchesHistory.length === 0 ? (
            <div className="p-12 text-center text-slate-400">No import history found.</div>
          ) : (
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-slate-600 font-medium text-xs">
                <tr>
                  <th className="py-3 px-4">Filename</th>
                  <th className="py-3 px-4">Version</th>
                  <th className="py-3 px-4">Uploaded Date</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Total Rows</th>
                  <th className="py-3 px-4">Committed At</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 text-slate-700">
                {batchesHistory.map((b) => (
                  <tr key={b.id} className="hover:bg-slate-50">
                    <td className="py-3 px-4 font-semibold text-slate-900">{b.filename}</td>
                    <td className="py-3 px-4 text-xs font-mono text-slate-500">{b.template_version}</td>
                    <td className="py-3 px-4 text-xs text-slate-600">
                      {new Date(b.created_at).toLocaleString()}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded text-xs font-semibold ${
                          b.status === "COMMITTED"
                            ? "bg-emerald-100 text-emerald-800"
                            : b.status === "ROLLED_BACK"
                            ? "bg-slate-200 text-slate-700"
                            : "bg-blue-100 text-blue-800"
                        }`}
                      >
                        {b.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-medium">{b.summary?.total_rows ?? 0}</td>
                    <td className="py-3 px-4 text-xs text-slate-500">
                      {b.committed_at ? new Date(b.committed_at).toLocaleString() : "-"}
                    </td>
                    <td className="py-3 px-4 text-right">
                      {b.status === "COMMITTED" && user?.role === "ADMIN" && (
                        <button
                          onClick={() => handleRollback(b.id)}
                          className="inline-flex items-center gap-1 text-xs font-semibold text-red-600 hover:text-red-800 hover:underline"
                        >
                          <RotateCcw className="h-3 w-3" />
                          Rollback
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
};
