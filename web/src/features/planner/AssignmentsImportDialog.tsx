import React, { useState } from "react";
import { Button, Modal, problemFromBody } from "../../ui";

/** Import of job item assignments (19 Nov meeting item 6).
 *
 * The file uses the layout of "Export Assignments". The import only adds assignments that
 * don't exist yet; it never changes or removes existing ones. "Check file" runs a dry run;
 * "Import" is enabled after a check with no errors in the selected file. */

interface RowResult {
  row: number;
  status: "CREATED" | "WOULD_CREATE" | "EXISTS" | "ERROR";
  message: string;
  warnings: string[];
}

interface ImportResult {
  dry_run: boolean;
  created: number;
  would_create: number;
  existing: number;
  errors: number;
  rows: RowResult[];
}

interface Props {
  open: boolean;
  onClose: () => void;
  token: string | null;
  onImported: () => void;
}

export const AssignmentsImportDialog: React.FC<Props> = ({ open, onClose, token, onImported }) => {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setFile(null);
    setResult(null);
    setError(null);
  };

  const run = async (dryRun: boolean) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`/api/v1/operational-planner/assignments/import?dry_run=${dryRun}`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) {
        setResult(null);
        setError(problemFromBody(res.status, body, "The file could not be read.").message);
        return;
      }
      setResult(body as ImportResult);
      if (!dryRun) onImported();
    } catch {
      setError("The file could not be sent. Check your connection and try again.");
    } finally {
      setBusy(false);
    }
  };

  const checked = result?.dry_run === true;
  const canImport = checked && result.errors === 0 && result.would_create > 0;
  const problemRows = (result?.rows || []).filter((r) => r.status === "ERROR" || r.warnings.length > 0);

  return (
    <Modal
      open={open}
      onClose={() => {
        reset();
        onClose();
      }}
      dismissible={!busy}
      size="lg"
      title="Import assignments"
      description="Use a file from Export Assignments. New rows are added as planner shifts; existing assignments are left as they are, and nothing is removed."
      footer={
        <>
          <Button
            onClick={() => {
              reset();
              onClose();
            }}
            disabled={busy}
          >
            Close
          </Button>
          <Button onClick={() => run(true)} disabled={!file} loading={busy && !checked}>
            Check file
          </Button>
          <Button variant="primary" onClick={() => run(false)} disabled={!canImport} loading={busy && checked}>
            Import {canImport ? `${result.would_create} assignment${result.would_create === 1 ? "" : "s"}` : ""}
          </Button>
        </>
      }
    >
      <div className="space-y-3 text-sm">
        <input
          type="file"
          accept=".xlsx"
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            setResult(null);
            setError(null);
          }}
          className="block w-full text-xs"
        />
        {error && <div className="p-2.5 rounded-lg bg-red-50 border border-red-200 text-red-800 text-xs">{error}</div>}
        {result && (
          <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-700">
            {result.dry_run ? (
              <>
                Check: <b>{result.would_create}</b> to add, <b>{result.existing}</b> already assigned,{" "}
                <b>{result.errors}</b> with errors.
                {result.errors > 0 && " Fix the rows below and check again."}
              </>
            ) : (
              <>
                Imported: <b>{result.created}</b> added, <b>{result.existing}</b> already assigned,{" "}
                <b>{result.errors}</b> skipped with errors.
              </>
            )}
          </div>
        )}
        {problemRows.length > 0 && (
          <div className="max-h-60 overflow-y-auto border border-slate-200 rounded-lg">
            <table className="w-full text-xs">
              <thead className="bg-slate-50 text-slate-500 sticky top-0">
                <tr>
                  <th className="p-2 text-left">Row</th>
                  <th className="p-2 text-left">Result</th>
                  <th className="p-2 text-left">Details</th>
                </tr>
              </thead>
              <tbody>
                {problemRows.map((r) => (
                  <tr key={r.row} className="border-t border-slate-100">
                    <td className="p-2 font-mono">{r.row}</td>
                    <td className={`p-2 font-semibold ${r.status === "ERROR" ? "text-red-700" : "text-amber-700"}`}>
                      {r.status === "ERROR" ? "Error" : "Warning"}
                    </td>
                    <td className="p-2">{[r.message, ...r.warnings].filter(Boolean).join(" · ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Modal>
  );
};
