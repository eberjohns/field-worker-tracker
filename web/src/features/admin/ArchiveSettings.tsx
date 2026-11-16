import React, { useEffect, useState } from "react";
import {
  Archive,
  Download,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  ShieldCheck,
  FileKey,
  Users,
} from "lucide-react";

interface ArchiveRecord {
  id: string;
  year: number;
  file_name: string;
  file_size_bytes: number;
  sha256_checksum: string;
  encryption_algo: string;
  record_count: number;
  status: string;
  archived_at: string;
  verified_at: string | null;
  purged_at: string | null;
  purged_record_count: number | null;
  details: Record<string, any>;
}

export const ArchiveSettings: React.FC = () => {
  const [archives, setArchives] = useState<ArchiveRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Modal for new archive
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [targetYear, setTargetYear] = useState<number>(new Date().getFullYear() - 1);
  const [purgeLiveEvents, setPurgeLiveEvents] = useState<boolean>(true);

  const token = localStorage.getItem("fwt_token");

  const fetchArchives = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/admin/archives", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to load archive history.");
      const data = await res.json();
      setArchives(data);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to load archives.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchArchives();
  }, []);

  const handleGenerateArchive = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading("generate");
    setStatusMessage(null);
    setErrorMessage(null);

    try {
      const res = await fetch("/api/v1/admin/archives/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          year: targetYear,
          purge_live_events: purgeLiveEvents,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.message || "Failed to generate yearly archive.");
      }

      const record: ArchiveRecord = await res.json();
      setStatusMessage(
        `Archive for ${record.year} generated successfully (${record.record_count} events encrypted with AES-256-GCM).`
      );
      setShowGenerateModal(false);
      fetchArchives();
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to generate archive.");
    } finally {
      setActionLoading(null);
    }
  };

  const handleVerifyArchive = async (archiveId: string, year: number) => {
    setActionLoading(`verify-${archiveId}`);
    setStatusMessage(null);
    setErrorMessage(null);

    try {
      const res = await fetch(`/api/v1/admin/archives/${archiveId}/verify`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.message || "Archive integrity check failed.");
      }

      await res.json();
      setStatusMessage(`Integrity verified for ${year} archive. SHA-256 checksum matched and sample decrypted.`);
      fetchArchives();
    } catch (err: any) {
      setErrorMessage(err.message || "Integrity verification failed.");
    } finally {
      setActionLoading(null);
    }
  };

  const handleDownloadArchive = async (archiveId: string, fileName: string) => {
    try {
      const res = await fetch(`/api/v1/admin/archives/${archiveId}/download`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to download encrypted archive file.");

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      setErrorMessage(err.message || "Download failed.");
    }
  };

  const handleRunRetentionPurge = async () => {
    if (!window.confirm("Run retention cleanup now? This will permanently purge sync changes older than 60 days and resolved alerts older than 6 months.")) {
      return;
    }

    setActionLoading("retention");
    setStatusMessage(null);
    setErrorMessage(null);

    try {
      const res = await fetch("/api/v1/admin/retention/run", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          purge_sync_older_than_days: 60,
          purge_notifications_older_than_months: 6,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.message || "Retention purge failed.");
      }

      const data = await res.json();
      setStatusMessage(
        `Retention purge complete: purged ${data.sync_changes_purged} sync changes and ${data.notification_logs_purged} notification logs.`
      );
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to run retention purge.");
    } finally {
      setActionLoading(null);
    }
  };

  const handleRunAnonymisation = async () => {
    if (!window.confirm("Run employee anonymisation? This will permanently anonymise personal details for terminated employees whose employment ended over 2 years ago.")) {
      return;
    }

    setActionLoading("anonymise");
    setStatusMessage(null);
    setErrorMessage(null);

    try {
      const res = await fetch("/api/v1/admin/retention/anonymise", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ older_than_years: 2 }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.message || "Anonymisation failed.");
      }

      const data = await res.json();
      setStatusMessage(
        `Anonymisation complete: ${data.anonymised_employees_count} terminated employee(s) anonymised.`
      );
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to anonymise employees.");
    } finally {
      setActionLoading(null);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  return (
    <div className="space-y-6">
      {statusMessage && (
        <div className="flex items-center gap-2 p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm rounded-lg">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{statusMessage}</span>
        </div>
      )}

      {errorMessage && (
        <div className="flex items-center gap-2 p-3 bg-rose-50 border border-rose-200 text-rose-800 text-sm rounded-lg">
          <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Top Banner: Retention & Archiving Policy Summary */}
      <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-3">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-indigo-600" />
              Statutory Retention & Yearly Archive Policy (DEC-38)
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed max-w-3xl">
              Per UAE & Saudi PDPL requirements, raw GPS event logs are retained live for 13 months. An annual administrative archive exports, encrypts (AES-256-GCM), verifies, and purges raw events to minimize live database footprint while retaining audited attendance and payroll summaries for 7 years.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowGenerateModal(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-medium shadow-sm transition"
            >
              <Archive className="w-3.5 h-3.5" />
              Run Yearly Archive
            </button>
          </div>
        </div>

        {/* Action pills for scheduled maintenance */}
        <div className="pt-2 border-t border-slate-200 flex flex-wrap items-center gap-3 text-xs">
          <span className="font-medium text-slate-500">Routine Maintenance:</span>
          <button
            onClick={handleRunRetentionPurge}
            disabled={actionLoading === "retention"}
            className="inline-flex items-center gap-1 px-2.5 py-1 bg-white hover:bg-slate-100 border border-slate-200 rounded text-slate-700 font-medium transition"
          >
            <RefreshCw className={`w-3 h-3 ${actionLoading === "retention" ? "animate-spin" : ""}`} />
            Purge Sync Changes (&gt;60d) &amp; Alerts (&gt;6mo)
          </button>

          <button
            onClick={handleRunAnonymisation}
            disabled={actionLoading === "anonymise"}
            className="inline-flex items-center gap-1 px-2.5 py-1 bg-white hover:bg-slate-100 border border-slate-200 rounded text-slate-700 font-medium transition"
          >
            <Users className={`w-3 h-3 ${actionLoading === "anonymise" ? "animate-spin" : ""}`} />
            Anonymise Departed Workers (&gt;2yr)
          </button>
        </div>
      </div>

      {/* Archives Table */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h4 className="text-sm font-semibold text-slate-800">Archived Year Packages</h4>
            <p className="text-xs text-slate-500">
              Download encrypted packages locally or trigger cryptographic SHA-256 integrity verification.
            </p>
          </div>
          <button
            onClick={fetchArchives}
            disabled={loading}
            className="p-1.5 text-slate-500 hover:text-slate-800 rounded transition"
            title="Refresh archives list"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-600">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-medium">
              <tr>
                <th className="px-4 py-3">Year</th>
                <th className="px-4 py-3">Archive File</th>
                <th className="px-4 py-3">Size</th>
                <th className="px-4 py-3">Events Archived</th>
                <th className="px-4 py-3">Encryption</th>
                <th className="px-4 py-3">SHA-256 Checksum</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Archived At</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {archives.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-slate-400">
                    No yearly archives generated yet. Click "Run Yearly Archive" to create the first package.
                  </td>
                </tr>
              ) : (
                archives.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-50 transition">
                    <td className="px-4 py-3 font-semibold text-slate-800">{a.year}</td>
                    <td className="px-4 py-3 font-mono text-[11px] text-slate-700">{a.file_name}</td>
                    <td className="px-4 py-3">{formatBytes(a.file_size_bytes)}</td>
                    <td className="px-4 py-3 font-medium text-slate-700">{a.record_count.toLocaleString()}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-indigo-50 text-indigo-700 border border-indigo-200">
                        <FileKey className="w-3 h-3" />
                        {a.encryption_algo}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-[10px] text-slate-500" title={a.sha256_checksum}>
                      {a.sha256_checksum.slice(0, 12)}...{a.sha256_checksum.slice(-8)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium ${
                          a.status === "VERIFIED"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : "bg-slate-100 text-slate-700 border border-slate-200"
                        }`}
                      >
                        {a.status === "VERIFIED" && <CheckCircle2 className="w-3 h-3 text-emerald-600" />}
                        {a.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-500">
                      {new Date(a.archived_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right space-x-2">
                      <button
                        onClick={() => handleVerifyArchive(a.id, a.year)}
                        disabled={actionLoading === `verify-${a.id}`}
                        className="inline-flex items-center gap-1 px-2 py-1 bg-white hover:bg-slate-100 border border-slate-200 rounded text-slate-700 font-medium transition text-[11px]"
                        title="Decrypt sample and test SHA-256 checksum"
                      >
                        <RefreshCw
                          className={`w-3 h-3 ${actionLoading === `verify-${a.id}` ? "animate-spin" : ""}`}
                        />
                        Verify
                      </button>

                      <button
                        onClick={() => handleDownloadArchive(a.id, a.file_name)}
                        className="inline-flex items-center gap-1 px-2 py-1 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded text-indigo-700 font-medium transition text-[11px]"
                        title="Download encrypted archive package to local drive"
                      >
                        <Download className="w-3 h-3" />
                        Download
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Generate Yearly Archive Modal */}
      {showGenerateModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-base font-semibold text-slate-900">Run Yearly Archive</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Package raw location events and visits into an encrypted archive.
                </p>
              </div>
              <button
                onClick={() => setShowGenerateModal(false)}
                className="text-slate-400 hover:text-slate-600 text-sm"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleGenerateArchive} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">
                  Calendar Year to Archive
                </label>
                <input
                  type="number"
                  min={2020}
                  max={new Date().getFullYear()}
                  value={targetYear}
                  onChange={(e) => setTargetYear(parseInt(e.target.value, 10))}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  required
                />
              </div>

              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg space-y-2">
                <label className="flex items-start gap-2 text-xs text-amber-900 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={purgeLiveEvents}
                    onChange={(e) => setPurgeLiveEvents(e.target.checked)}
                    className="mt-0.5 rounded border-amber-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  <span>
                    <strong>Purge live database records:</strong> Automatically purge archived raw events and granular visits from the active database after successful package encryption and verification.
                  </span>
                </label>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowGenerateModal(false)}
                  className="px-3 py-1.5 border border-slate-200 rounded-lg text-xs font-medium text-slate-700 hover:bg-slate-50 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading === "generate"}
                  className="inline-flex items-center gap-1.5 px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-medium transition shadow-sm disabled:opacity-50"
                >
                  <Archive className="w-3.5 h-3.5" />
                  {actionLoading === "generate" ? "Archiving..." : "Create Archive"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
