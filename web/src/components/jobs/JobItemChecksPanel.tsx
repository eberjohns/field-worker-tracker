import React, { useEffect } from "react";
import { AlertCircle, Calculator, Info } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import {
  useBudgetPreview,
  useJobItemChecks,
  useNewWorksiteBudgetPreview,
  type JobItemChecks,
  type NewWorksiteContext,
} from "../../features/budget/useBudgetPreview";
import { fmtHours, fmtMoney, type JobItemBudget } from "../../features/budget/budgetFormat";
import { draftHours, draftProblem, draftToPayload, type JobItemDraft } from "./jobItemUtils";

export interface JobItemCheckResult {
  checks: JobItemChecks | null;
  budget: JobItemBudget | null;
}

/**
 * The job item validation panel (BR-JB-06, BR-JB-12) and its budget (DEC-59), from the server,
 * for an item that is not saved yet. A saved worksite uses its own budget preview; the Add
 * Worksite wizard passes the unsaved worksite's country and contract instead.
 */
export const JobItemChecksPanel: React.FC<{
  draft: JobItemDraft;
  country: string;
  worksiteId?: string | null;
  context?: NewWorksiteContext;
  onResult?: (result: JobItemCheckResult) => void;
}> = ({ draft, country, worksiteId = null, context = {}, onResult }) => {
  const { token, user } = useAuth();
  const isAdmin = user?.role === "ADMIN";
  const problem = draftProblem(draft);
  const payload = problem ? null : draftToPayload(draft);

  const checksState = useJobItemChecks(token, country, payload);
  const saved = useBudgetPreview(token, worksiteId, worksiteId ? payload : null);
  const unsaved = useNewWorksiteBudgetPreview(token, country, worksiteId ? null : payload, context);
  const budgetState = worksiteId ? saved : unsaved;
  const checks = payload ? checksState.data : null;
  const budget = payload ? budgetState.budget : null;

  useEffect(() => {
    onResult?.({ checks, budget });
    // onResult is a fresh closure on every render of the parent; only new results matter.
  }, [checks, budget]);

  if (problem) {
    return (
      <p className="text-[11px] text-slate-500 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
        Add {problem} to see the checks for this item.
      </p>
    );
  }

  const hours = draftHours(draft);
  const zero = (n: number | undefined) => n === 0;
  const tile = "bg-white p-2.5 rounded border border-indigo-100";
  const redTile = "bg-rose-50 p-2.5 rounded border border-rose-300";
  const loading = (checksState.loading && !checks) || (budgetState.loading && !budget);

  return (
    <div
      className="bg-indigo-50/60 border border-indigo-200 rounded-lg p-3 space-y-2 text-xs"
      data-testid="job-item-checks"
    >
      <div className="flex items-center gap-2 font-semibold text-indigo-900">
        <Calculator className="h-4 w-4 text-indigo-600" />
        <span>Checks {loading ? "…" : ""}</span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        <div className={tile}>
          <span className="text-slate-500 block text-[10px]">Activities / year</span>
          <span className="font-bold text-slate-900 text-sm">
            {checks ? Number(checks.calculated_activities_per_year).toLocaleString() : "–"}
          </span>
        </div>
        <div className={tile}>
          <span className="text-slate-500 block text-[10px]">Hours / full year</span>
          <span className="font-bold text-indigo-700 text-sm">
            {fmtHours(checks?.calculated_annual_hours)}
          </span>
        </div>
        <div className={tile}>
          <span className="text-slate-500 block text-[10px]">Days per visit</span>
          <span className="font-bold text-slate-900 text-sm">
            {checks ? `${checks.days_per_occurrence} (${hours.toFixed(1)} h)` : "–"}
          </span>
        </div>
        <div className={zero(checks?.expected_occurrences_count) ? redTile : tile}>
          <span className="text-slate-500 block text-[10px]">Expected occurrences</span>
          <span className="font-bold text-slate-900 text-sm">
            {checks ? checks.expected_occurrences_count : "–"}
          </span>
        </div>
        <div className={zero(checks?.eligible_workers_count) ? redTile : tile}>
          <span className="text-slate-500 block text-[10px]">Eligible employees</span>
          <span
            className={`font-bold text-sm ${zero(checks?.eligible_workers_count) ? "text-rose-700" : "text-slate-900"}`}
          >
            {checks ? checks.eligible_workers_count : "–"}
          </span>
        </div>
        <div className={tile}>
          <span className="text-slate-500 block text-[10px]">
            Man-hours this contract year
            {budget ? ` (${budget.period_from} – ${budget.period_to})` : ""}
          </span>
          <span className="font-bold text-indigo-700 text-sm">{fmtHours(budget?.annual_hours)}</span>
        </div>
        {isAdmin && (
          <div className={tile}>
            <span className="text-slate-500 block text-[10px]">
              Annual cost{budget?.revision_code ? ` (${budget.revision_code})` : ""}
            </span>
            <span className="font-bold text-slate-900 text-sm">{fmtMoney(budget?.annual_cost)}</span>
          </div>
        )}
      </div>
      {[checksState.error, budgetState.error].filter(Boolean).map((msg) => (
        <div key={msg} className="flex items-start gap-1.5 text-[11px] text-rose-700">
          <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
          <span>{msg}</span>
        </div>
      ))}
      {budget?.warnings.map((w, i) => (
        <div key={`${w.code}-${i}`} className="flex items-start gap-1.5 text-[11px] text-amber-800">
          <AlertCircle className="h-3.5 w-3.5 text-amber-600 shrink-0 mt-0.5" />
          <span>{w.message}</span>
        </div>
      ))}
      {checks && checks.days_per_occurrence > 1 && (
        <div className="flex items-start gap-1.5 text-[11px] text-indigo-800">
          <Info className="h-3.5 w-3.5 text-indigo-600 shrink-0 mt-0.5" />
          <span>
            More than 9 h per visit: each visit is split over {checks.days_per_occurrence} days (
            {checks.daily_hours_split.map((h) => `${Number(h)} h`).join(" + ")}).
          </span>
        </div>
      )}
    </div>
  );
};
