import React, { useEffect, useMemo, useState } from "react";
import { currencyForCountry } from "../../features/format/money";
import { RENEWAL_HINT, RENEWAL_LABEL, RenewalLabel } from "./RenewalLabel";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Copy,
  Loader2,
  Plus,
  Trash2,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { GroupZoneSelect } from "../org/GroupZoneSelect";
import type { OrgUnit } from "../../features/org/groupZoneUtils";
import { JobItemFields } from "../jobs/JobItemFields";
import { JobItemChecksPanel, type JobItemCheckResult } from "../jobs/JobItemChecksPanel";
import {
  draftProblem,
  draftToPayload,
  duplicateCodes,
  duplicateDraft,
  emptyDraft,
  nextSubItemCode,
  rowError,
  type JobItemDraft,
  type RowError,
} from "../jobs/jobItemUtils";
import { fmtHours, fmtMoney } from "../../features/budget/budgetFormat";
import { DatePicker, Modal } from "../../ui";

/**
 * Add Worksite (Batch 5.1 B, Admin only, DEC-61): worksite, job items, review. Nothing is saved
 * until "Create", which sends one POST /worksites with the items and supervisors (one
 * transaction). A new group or zone added from its dropdown is saved at once (DEC-60).
 */

interface Revision {
  code: string;
  name: string;
  country: string;
  status?: string;
}

interface Supervisor {
  id: string;
  name: string;
  tally_id?: string;
  is_active?: boolean;
}

interface JobNumberCheck {
  job_number: string;
  valid: boolean;
  exists: boolean;
  message: string | null;
  is_outdoor: boolean | null;
  kind: string | null;
}

interface Row {
  key: string;
  draft: JobItemDraft;
}

export interface AddWorksiteWizardProps {
  open: boolean;
  onClose: () => void;
  groups: OrgUnit[];
  zones: OrgUnit[];
  onGroupCreated: (unit: OrgUnit) => void;
  onZoneCreated: (unit: OrgUnit) => void;
  revisions: Revision[];
  onCreated: (worksiteId: string) => void;
}

const STEPS = ["Worksite", "Job items", "Review"] as const;
const input =
  "w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none bg-white";
const label = "block text-xs font-semibold text-slate-700 mb-1";

let rowSeq = 0;
const newKey = () => `row-${++rowSeq}`;

function sumOrNull(values: (number | string | null | undefined)[]): number | null {
  let total = 0;
  for (const v of values) {
    if (v === null || v === undefined || v === "") return null;
    const n = Number(v);
    if (Number.isNaN(n)) return null;
    total += n;
  }
  return total;
}

export const AddWorksiteWizard: React.FC<AddWorksiteWizardProps> = ({
  open,
  onClose,
  groups,
  zones,
  onGroupCreated,
  onZoneCreated,
  revisions,
  onCreated,
}) => {
  const { token } = useAuth();
  const headers = useMemo(
    () => (token ? { Authorization: `Bearer ${token}` } : ({} as Record<string, string>)),
    [token],
  );

  const [step, setStep] = useState(0);
  const [jobNumber, setJobNumber] = useState("");
  const [jobCheck, setJobCheck] = useState<JobNumberCheck | null>(null);
  const [checking, setChecking] = useState(false);
  const [name, setName] = useState("");
  const [groupId, setGroupId] = useState("");
  const [zoneId, setZoneId] = useState("");
  const [customerType, setCustomerType] = useState("Direct");
  const [country, setCountry] = useState("AE");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [renewalRef, setRenewalRef] = useState("");
  const [revisionCode, setRevisionCode] = useState("");
  const [budget, setBudget] = useState("");
  const [supervisors, setSupervisors] = useState<Supervisor[]>([]);
  const [supervisorIds, setSupervisorIds] = useState<string[]>([]);
  const [supervisorFilter, setSupervisorFilter] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [results, setResults] = useState<Record<string, JobItemCheckResult>>({});
  const [error, setError] = useState<RowError | null>(null);
  const [saving, setSaving] = useState(false);

  // Fresh form every time the wizard opens.
  useEffect(() => {
    if (!open) return;
    setStep(0);
    setJobNumber("");
    setJobCheck(null);
    setName("");
    setGroupId("");
    setZoneId("");
    setCustomerType("Direct");
    setCountry("AE");
    setStartDate("");
    setEndDate("");
    setRenewalRef("");
    setRevisionCode("");
    setBudget("");
    setSupervisorIds([]);
    setSupervisorFilter("");
    setRows([]);
    setResults({});
    setError(null);
    fetch("/api/v1/employees?role=SUPERVISOR&limit=200", { headers })
      .then((r) => (r.ok ? r.json() : []))
      .then((list: Supervisor[]) => setSupervisors(list.filter((s) => s.is_active !== false)))
      .catch(() => setSupervisors([]));
  }, [open, headers]);

  // Live job number check (format and uniqueness), debounced.
  useEffect(() => {
    const value = jobNumber.trim();
    if (!open || !value) {
      setJobCheck(null);
      return;
    }
    let cancelled = false;
    setChecking(true);
    const timer = setTimeout(() => {
      fetch(`/api/v1/worksites/job-number-check?job_number=${encodeURIComponent(value)}`, {
        headers,
      })
        .then((r) => (r.ok ? r.json() : null))
        .then((data: JobNumberCheck | null) => {
          if (!cancelled) setJobCheck(data);
        })
        .catch(() => {
          if (!cancelled) setJobCheck(null);
        })
        .finally(() => {
          if (!cancelled) setChecking(false);
        });
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [jobNumber, open, headers]);

  const countryRevisions = revisions.filter(
    (r) => r.country === country && (!r.status || r.status === "ACTIVE"),
  );
  // A revision of the other country no longer applies after the country changes.
  useEffect(() => {
    setRevisionCode((code) =>
      code && !revisions.some((r) => r.code === code && r.country === country) ? "" : code,
    );
  }, [country, revisions]);

  if (!open) return null;

  const drafts = rows.map((r) => r.draft);
  const dupes = duplicateCodes(drafts);
  const context = {
    salary_revision_code: revisionCode || null,
    contract_start: startDate || null,
    contract_end: endDate || null,
  };
  const todayStr = new Date().toISOString().slice(0, 10);

  const step1Problem = (): string => {
    if (!jobNumber.trim()) return "Enter the job number.";
    if (checking) return "Checking the job number…";
    if (!jobCheck) return "The job number could not be checked yet.";
    if (!jobCheck.valid) return jobCheck.message || "The job number is not valid.";
    if (!name.trim()) return "Enter the worksite name.";
    if (!groupId) return "Choose the customer group.";
    if (!zoneId) return "Choose the zone.";
    if (startDate && endDate && endDate < startDate) return "The contract end is before its start.";
    return "";
  };
  const step2Problem = (): string => {
    for (const [i, d] of drafts.entries()) {
      const p = draftProblem(d);
      if (p) return `Job item ${i + 1} (${d.sub_item_code || "?"}) needs ${p}.`;
    }
    if (dupes.length) return `Sub-item code used twice: ${dupes.join(", ")}.`;
    return "";
  };
  const blocker = step === 0 ? step1Problem() : step === 1 ? step2Problem() : "";

  const patchRow = (key: string, patch: Partial<JobItemDraft>) =>
    setRows((prev) => prev.map((r) => (r.key === key ? { ...r, draft: { ...r.draft, ...patch } } : r)));
  const addRow = () =>
    setRows((prev) => [
      ...prev,
      {
        key: newKey(),
        draft: emptyDraft(
          nextSubItemCode(prev.map((r) => r.draft.sub_item_code)),
          startDate || todayStr,
          endDate,
        ),
      },
    ]);
  const duplicateRow = (key: string) =>
    setRows((prev) => {
      const i = prev.findIndex((r) => r.key === key);
      const copy = {
        key: newKey(),
        draft: duplicateDraft(prev[i].draft, nextSubItemCode(prev.map((r) => r.draft.sub_item_code))),
      };
      return [...prev.slice(0, i + 1), copy, ...prev.slice(i + 1)];
    });
  const removeRow = (key: string) => {
    setRows((prev) => prev.filter((r) => r.key !== key));
    setResults((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const handleCreate = async () => {
    setError(null);
    setSaving(true);
    try {
      const res = await fetch("/api/v1/worksites", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify({
          job_number: jobCheck?.job_number || jobNumber.trim().toUpperCase(),
          job_name: name.trim(),
          group_id: groupId,
          zone_id: zoneId,
          customer_type: customerType || null,
          country,
          start_date: startDate || null,
          end_date: endDate || null,
          renewal_reference: renewalRef.trim() || null,
          salary_revision_code: revisionCode || null,
          budget_amount: budget ? parseFloat(budget) : null,
          supervisor_ids: supervisorIds,
          job_items: drafts.map(draftToPayload),
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const err = rowError(data);
        setError(err);
        setStep(err.step - 1);
        return;
      }
      onCreated(data.id);
    } catch {
      setError({ step: 1, row: null, field: null, message: "Could not reach the server." });
    } finally {
      setSaving(false);
    }
  };

  // --- review figures ---
  const rowResults = rows.map((r) => results[r.key]);
  const totalHours = sumOrNull(rowResults.map((r) => r?.budget?.annual_hours));
  const totalCost = sumOrNull(rowResults.map((r) => r?.budget?.annual_cost));
  const warnings: string[] = ["No boundary yet: draw it on the worksite page after creating."];
  if (supervisorIds.length === 0) {
    warnings.push("No supervisor picked: only Admin will see this worksite until one is assigned.");
  }
  rows.forEach((r, i) => {
    const res = results[r.key];
    const code = r.draft.sub_item_code || String(i + 1);
    if (res?.checks?.eligible_workers_count === 0) {
      warnings.push(`Job item ${code}: no eligible employees (${r.draft.staff_grade_description}, ${country}).`);
    }
    if (res?.checks?.expected_occurrences_count === 0) {
      warnings.push(`Job item ${code}: no occurrences in the planning horizon.`);
    }
    for (const w of res?.budget?.warnings ?? []) warnings.push(`Job item ${code}: ${w.message}`);
  });
  if (rows.length === 0) warnings.push("No job items: they can be added later on the worksite page.");

  const groupName = groups.find((g) => g.id === groupId);
  const zoneName = zones.find((z) => z.id === zoneId);
  const filteredSupervisors = supervisors.filter((s) =>
    `${s.name} ${s.tally_id ?? ""}`.toLowerCase().includes(supervisorFilter.trim().toLowerCase()),
  );

  return (
    <Modal
      open
      onClose={onClose}
      size="xl"
      title="Add Worksite"
      description={
        <ol className="mt-1 flex items-center gap-2 text-xs" aria-label="Steps">
          {STEPS.map((s, i) => (
            <li key={s} className="flex items-center gap-2">
              <span
                className={`h-5 w-5 rounded-full flex items-center justify-center font-bold ${
                  i < step
                    ? "bg-emerald-600 text-white"
                    : i === step
                      ? "bg-indigo-600 text-white"
                      : "bg-slate-200 text-slate-600"
                }`}
                aria-current={i === step ? "step" : undefined}
              >
                {i + 1}
              </span>
              <span className={i === step ? "font-semibold text-slate-900" : "text-slate-500"}>{s}</span>
              {i < STEPS.length - 1 && <span className="text-slate-300">›</span>}
            </li>
          ))}
        </ol>
      }
      footer={
        <div className="flex w-full flex-wrap items-center justify-between gap-2">
          <span className="text-[11px] text-slate-500 min-h-[1rem]">{blocker}</span>
            <div className="flex gap-2">
              {step > 0 && (
                <button
                  type="button"
                  onClick={() => setStep(step - 1)}
                  disabled={saving}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 hover:bg-white"
                >
                  Back
                </button>
              )}
              {step < 2 ? (
                <button
                  type="button"
                  onClick={() => {
                    setError(null);
                    if (step === 0 && rows.length === 0) addRow();
                    setStep(step + 1);
                  }}
                  disabled={Boolean(blocker)}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium disabled:opacity-50"
                >
                  Next
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleCreate}
                  disabled={saving}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium disabled:opacity-50 inline-flex items-center gap-1.5"
                >
                  {saving && <Loader2 className="h-4 w-4 animate-spin" />}
                  Create worksite
                </button>
              )}
            </div>
        </div>
      }
    >
      <div className="p-6 space-y-5">
        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2 text-xs text-red-700 whitespace-pre-line">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{error.message}</span>
          </div>
        )}

        {step === 0 && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className={label} htmlFor="wz-number">
                  Job number *
                </label>
                <input
                  id="wz-number"
                  value={jobNumber}
                  onChange={(e) => setJobNumber(e.target.value)}
                  placeholder="e.g. 12A14301"
                  className={`${input} ${error?.field === "job_number" ? "border-rose-500" : ""}`}
                />
                <p className="mt-1 text-[11px] min-h-[1rem]" aria-live="polite">
                  {checking ? (
                    <span className="text-slate-500">Checking…</span>
                  ) : jobCheck?.valid ? (
                    <span className="text-emerald-700 inline-flex items-center gap-1">
                      <CheckCircle2 className="h-3 w-3" />
                      {jobCheck.job_number} is free · {jobCheck.kind}
                      {jobCheck.is_outdoor ? " (outdoor rules apply)" : ""}
                    </span>
                  ) : jobCheck ? (
                    <span className="text-rose-700">{jobCheck.message}</span>
                  ) : (
                    <span className="text-slate-400">2 digits + A, B or C + 5 digits</span>
                  )}
                </p>
              </div>
              <div>
                <label className={label} htmlFor="wz-name">
                  Worksite name *
                </label>
                <input id="wz-name" value={name} onChange={(e) => setName(e.target.value)} className={input} />
              </div>
              <div>
                <span className={label}>Customer group *</span>
                <GroupZoneSelect
                  kind="group"
                  required
                  value={groupId}
                  onChange={setGroupId}
                  items={groups}
                  onCreated={onGroupCreated}
                  selectClassName={input}
                />
              </div>
              <div>
                <span className={label}>Zone *</span>
                <GroupZoneSelect
                  kind="zone"
                  required
                  value={zoneId}
                  onChange={setZoneId}
                  items={zones}
                  onCreated={onZoneCreated}
                  selectClassName={input}
                />
              </div>
              <div>
                <label className={label} htmlFor="wz-ctype">
                  Customer type
                </label>
                <select
                  id="wz-ctype"
                  value={customerType}
                  onChange={(e) => setCustomerType(e.target.value)}
                  className={input}
                >
                  <option value="Direct">Direct</option>
                  <option value="Indirect">Indirect</option>
                </select>
              </div>
              <div>
                <label className={label} htmlFor="wz-country">
                  Country *
                </label>
                <select id="wz-country" value={country} onChange={(e) => setCountry(e.target.value)} className={input}>
                  <option value="AE">UAE (AE)</option>
                  <option value="SA">Saudi Arabia (SA)</option>
                </select>
                <p className="mt-1 text-[11px] text-slate-500">Decides which country's time zone, public holidays, currency and pay rules apply. It doesn't limit who can see it.</p>
              </div>
              <div>
                <label className={label} htmlFor="wz-start">
                  Contract start
                </label>
                <DatePicker
                  id="wz-start"
                  value={startDate}
                  onChange={(iso) => setStartDate(iso)}
                  size="lg"
                />
              </div>
              <div>
                <label className={label} htmlFor="wz-end">
                  Contract end
                </label>
                <DatePicker
                  id="wz-end"
                  value={endDate}
                  onChange={(iso) => setEndDate(iso)}
                  size="lg"
                />
              </div>
              <div>
                <RenewalLabel className={label} htmlFor="wz-renewal" />
                <input id="wz-renewal" value={renewalRef} onChange={(e) => setRenewalRef(e.target.value)} className={input} />
              </div>
              <div>
                <label className={label} htmlFor="wz-revision">
                  Salary revision
                </label>
                <select
                  id="wz-revision"
                  value={revisionCode}
                  onChange={(e) => setRevisionCode(e.target.value)}
                  className={input}
                >
                  <option value="">Default for {country}</option>
                  {countryRevisions.map((r) => (
                    <option key={r.code} value={r.code}>
                      {r.code} – {r.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className={label} htmlFor="wz-budget">
                  Manual labour budget ({currencyForCountry(country)}, optional)
                </label>
                <input
                  id="wz-budget"
                  type="number"
                  min="0"
                  step="0.01"
                  value={budget}
                  onChange={(e) => setBudget(e.target.value)}
                  className={input}
                />
              </div>
            </div>

            <div>
              <span className={label}>Supervisors (optional)</span>
              <div className={`border rounded-lg ${error?.field === "supervisor_ids" ? "border-rose-500" : "border-slate-300"}`}>
                <input
                  value={supervisorFilter}
                  onChange={(e) => setSupervisorFilter(e.target.value)}
                  placeholder="Filter by name or Tally ID"
                  aria-label="Filter supervisors"
                  className="w-full px-3 py-1.5 text-xs border-b border-slate-200 rounded-t-lg focus:outline-none"
                />
                <div className="max-h-36 overflow-y-auto p-2 grid grid-cols-1 sm:grid-cols-2 gap-1">
                  {filteredSupervisors.length === 0 && (
                    <span className="text-xs text-slate-400 px-1">No active supervisors found.</span>
                  )}
                  {filteredSupervisors.map((s) => (
                    <label key={s.id} className="flex items-center gap-2 text-xs px-1 py-0.5 rounded hover:bg-slate-50">
                      <input
                        type="checkbox"
                        checked={supervisorIds.includes(s.id)}
                        onChange={(e) =>
                          setSupervisorIds((prev) =>
                            e.target.checked ? [...prev, s.id] : prev.filter((id) => id !== s.id),
                          )
                        }
                      />
                      <span>
                        {s.name}
                        {s.tally_id ? <span className="text-slate-400"> · {s.tally_id}</span> : null}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
              <p className="mt-1 text-[11px] text-slate-500">
                {supervisorIds.length} picked. Supervisors see the worksite and plan its work (DEC-57).
              </p>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-4">
            <p className="text-xs text-slate-500">
              One row per job item. Codes run A, B, C… and can be changed. Dates start from the contract.
              Zero items is fine: items can be added later.
            </p>
            {rows.map((r, i) => {
              const rowHasError = error?.row === i;
              return (
                <div
                  key={r.key}
                  className={`border rounded-xl p-4 space-y-3 ${rowHasError ? "border-rose-400 bg-rose-50/30" : "border-slate-200"}`}
                >
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-slate-900">
                      Job item {i + 1}
                      {r.draft.sub_item_code ? ` · ${r.draft.sub_item_code}` : ""}
                      {dupes.includes(r.draft.sub_item_code.trim().toUpperCase()) && (
                        <span className="ml-2 text-xs font-semibold text-rose-700">code used twice</span>
                      )}
                    </h3>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => duplicateRow(r.key)}
                        className="px-2 py-1 text-xs border border-slate-200 rounded hover:bg-slate-50 inline-flex items-center gap-1"
                      >
                        <Copy className="h-3 w-3" /> Duplicate
                      </button>
                      <button
                        type="button"
                        onClick={() => removeRow(r.key)}
                        className="px-2 py-1 text-xs border border-rose-200 text-rose-700 rounded hover:bg-rose-50 inline-flex items-center gap-1"
                      >
                        <Trash2 className="h-3 w-3" /> Remove
                      </button>
                    </div>
                  </div>
                  <JobItemFields
                    draft={r.draft}
                    onChange={(p) => patchRow(r.key, p)}
                    breakMode="display"
                    errorField={rowHasError ? error?.field : null}
                    idPrefix={r.key}
                  />
                  <JobItemChecksPanel
                    draft={r.draft}
                    country={country}
                    context={context}
                    onResult={(res) => setResults((prev) => ({ ...prev, [r.key]: res }))}
                  />
                </div>
              );
            })}
            <button
              type="button"
              onClick={addRow}
              className="px-3 py-2 text-xs font-semibold border border-dashed border-indigo-300 text-indigo-700 rounded-lg hover:bg-indigo-50 inline-flex items-center gap-1.5"
            >
              <Plus className="h-3.5 w-3.5" /> Add item
            </button>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4 text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 bg-slate-50 border border-slate-200 rounded-lg p-4">
              <div><span className="text-slate-500">Job number:</span> <b>{jobCheck?.job_number}</b> ({jobCheck?.kind})</div>
              <div><span className="text-slate-500">Name:</span> <b>{name}</b></div>
              <div><span className="text-slate-500">Group:</span> {groupName ? `${groupName.name} (${groupName.code})` : "–"}</div>
              <div><span className="text-slate-500">Zone:</span> {zoneName ? `${zoneName.name} (${zoneName.code})` : "–"}</div>
              <div><span className="text-slate-500">Country / customer type:</span> {country} · {customerType}</div>
              <div><span className="text-slate-500">Contract:</span> {startDate || "–"} to {endDate || "open"}</div>
              <div><span className="text-slate-500">Salary revision:</span> {revisionCode || `default for ${country}`}</div>
              <div><span className="text-slate-500" title={RENEWAL_HINT}>{RENEWAL_LABEL}:</span> {renewalRef || "–"}</div>
              <div className="sm:col-span-2">
                <span className="text-slate-500">Supervisors:</span>{" "}
                {supervisorIds.length
                  ? supervisors.filter((s) => supervisorIds.includes(s.id)).map((s) => s.name).join(", ")
                  : "none"}
              </div>
            </div>

            <table className="w-full text-left border border-slate-200 rounded-lg overflow-hidden">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-3 py-2">Item</th>
                  <th className="px-3 py-2">Staff type / grade</th>
                  <th className="px-3 py-2">Frequency</th>
                  <th className="px-3 py-2">Staff × hours</th>
                  <th className="px-3 py-2 text-right">Man-hours (contract year)</th>
                  <th className="px-3 py-2 text-right">Cost</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-3 py-3 text-slate-400">No job items.</td>
                  </tr>
                )}
                {rows.map((r) => {
                  const res = results[r.key];
                  return (
                    <tr key={r.key} className="border-t border-slate-100">
                      <td className="px-3 py-2 font-semibold">{r.draft.sub_item_code}</td>
                      <td className="px-3 py-2">{r.draft.staff_grade_description} · {r.draft.planned_grade_code}</td>
                      <td className="px-3 py-2">
                        {r.draft.occurrences_per_period} per {r.draft.period_interval > 1 ? `${r.draft.period_interval} ` : ""}
                        {r.draft.frequency_unit.toLowerCase()}
                      </td>
                      <td className="px-3 py-2">{r.draft.required_staff_count} × {r.draft.hours_per_occurrence_per_staff} h</td>
                      <td className="px-3 py-2 text-right">{fmtHours(res?.budget?.annual_hours)}</td>
                      <td className="px-3 py-2 text-right">{fmtMoney(res?.budget?.annual_cost, currencyForCountry(country))}</td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot className="bg-indigo-50/60 font-semibold">
                <tr>
                  <td className="px-3 py-2" colSpan={4}>
                    Contract labour budget (calculated)
                    {budget ? <span className="font-normal text-slate-600"> · manual budget {fmtMoney(budget, currencyForCountry(country))}</span> : null}
                  </td>
                  <td className="px-3 py-2 text-right">{fmtHours(totalHours)}</td>
                  <td className="px-3 py-2 text-right">{fmtMoney(totalCost, currencyForCountry(country))}</td>
                </tr>
              </tfoot>
            </table>

            <ul className="space-y-1">
              {warnings.map((w) => (
                <li key={w} className="flex items-start gap-1.5 text-amber-800">
                  <AlertTriangle className="h-3.5 w-3.5 text-amber-600 shrink-0 mt-0.5" />
                  <span>{w}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Modal>
  );
};
