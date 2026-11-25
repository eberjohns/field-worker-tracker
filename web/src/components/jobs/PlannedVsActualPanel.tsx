import React, { useEffect, useState } from "react";
import { formatMoney } from "../../features/format/money";
import { AlertCircle, BarChart3 } from "lucide-react";
import {
  diffClass,
  fmtDiff,
  fmtHours,
  fmtMoney,
  fmtPct,
  monthLabel,
} from "../../features/budget/budgetFormat";
import type { PlannedActualFigures, WorksitePlannedVsActual } from "../../features/budget/budgetFormat";
import { DatePicker } from "../../ui";

interface Props {
  worksiteId: string;
  /** The worksite's currency (AED / SAR). */
  currency?: string | null;
  isAdmin: boolean;
  token: string | null | undefined;
}

const hoursFmt = (n: number) => n.toLocaleString(undefined, { maximumFractionDigits: 1 });

/** Planned vs actual for one worksite (DEC-59). Hours for every role; money for Admin only. */
export const PlannedVsActualPanel: React.FC<Props> = ({ worksiteId, isAdmin, token, currency }) => {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [data, setData] = useState<WorksitePlannedVsActual | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if ((from && !to) || (!from && to)) return; // wait for both dates
    let cancelled = false;
    setLoading(true);
    const qs = from && to ? `?from=${from}&to=${to}` : "";
    fetch(`/api/v1/worksites/${worksiteId}/planned-vs-actual${qs}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (cancelled) return;
        if (res.ok) {
          setData(body as WorksitePlannedVsActual);
          setError(null);
          if (!from && !to) {
            setFrom(body.period_from);
            setTo(body.period_to);
          }
        } else {
          setError(typeof body?.detail === "string" ? body.detail : "Could not load planned vs actual.");
        }
      })
      .catch(() => !cancelled && setError("Could not load planned vs actual."))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [worksiteId, token, from, to]);

  const figures = (f: PlannedActualFigures) => (
    <>
      <td className="px-3 py-2 text-right font-mono">{fmtHours(f.planned_hours)}</td>
      <td className="px-3 py-2 text-right font-mono">{fmtHours(f.actual_hours)}</td>
      <td className={`px-3 py-2 text-right font-mono ${diffClass(f.hours_diff)}`}>
        {fmtDiff(f.hours_diff, hoursFmt)} <span className="text-[10px]">{fmtPct(f.hours_diff_pct)}</span>
      </td>
      {isAdmin && (
        <>
          <td className="px-3 py-2 text-right font-mono">{fmtMoney(f.planned_cost, currency)}</td>
          <td className="px-3 py-2 text-right font-mono">{fmtMoney(f.actual_cost, currency)}</td>
          <td className={`px-3 py-2 text-right font-mono ${diffClass(f.cost_diff)}`}>
            {fmtDiff(f.cost_diff, (n) => formatMoney(n, currency))} <span className="text-[10px]">{fmtPct(f.cost_diff_pct)}</span>
          </td>
        </>
      )}
    </>
  );

  const head = (first: string) => (
    <tr>
      <th className="px-3 py-2 text-left">{first}</th>
      <th className="px-3 py-2 text-right">Planned h</th>
      <th className="px-3 py-2 text-right">Actual h</th>
      <th className="px-3 py-2 text-right">Diff h</th>
      {isAdmin && (
        <>
          <th className="px-3 py-2 text-right">Planned cost</th>
          <th className="px-3 py-2 text-right">Actual cost</th>
          <th className="px-3 py-2 text-right">Diff cost</th>
        </>
      )}
    </tr>
  );

  return (
    <div className="bg-white border border-slate-200 rounded-xl shadow-xs p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 font-semibold text-slate-900 text-sm">
          <BarChart3 className="h-4 w-4 text-indigo-600" />
          Planned vs actual
          {data?.revision_code && (
            <span className="text-[11px] font-normal text-slate-500">revision {data.revision_code}</span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <label className="flex items-center gap-1">
            From
            <DatePicker
              value={from}
              onChange={(iso) => setFrom(iso)}
              size="sm"
            />
          </label>
          <label className="flex items-center gap-1">
            To
            <DatePicker
              value={to}
              onChange={(iso) => setTo(iso)}
              size="sm"
            />
          </label>
          <button
            type="button"
            onClick={() => {
              setFrom("");
              setTo("");
            }}
            className="px-2 py-1 border border-slate-300 rounded hover:bg-slate-50"
            title="Back to the current contract year"
          >
            Contract year
          </button>
        </div>
      </div>

      <p className="text-[11px] text-slate-500">
        Planned: job items pro-rated by day inside the item and contract dates. Actual hours: site
        visits on approved attendance days, split over the day's scheduled items.
        {isAdmin && " Actual cost: approved payroll allocations, split by those hours."} Budget-only
        staff count as actual = planned.
      </p>

      {error && (
        <div className="flex items-start gap-1.5 text-xs text-rose-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}
      {loading && !data && <div className="text-xs text-slate-400">Loading…</div>}

      {data && (
        <>
          {data.warnings.map((w, i) => (
            <div key={`${w.code}-${i}`} className="flex items-start gap-1.5 text-[11px] text-amber-800">
              <AlertCircle className="h-3.5 w-3.5 text-amber-600 shrink-0 mt-0.5" />
              {w.message}
            </div>
          ))}

          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase text-[10px] tracking-wider">
                {head("Job item")}
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((it) => (
                  <tr key={it.job_item_id} className={it.excluded_from_totals ? "opacity-60" : ""}>
                    <td className="px-3 py-2">
                      <span className="font-mono font-bold">{it.sub_item_code}</span>{" "}
                      {it.staff_grade_description}
                      <span className="block text-[10px] text-slate-400">
                        {it.grade_code}
                        {it.is_budget_only && " · budget-only (actual = planned)"}
                        {it.excluded_from_totals && " · no grade rate, not in totals"}
                      </span>
                    </td>
                    {figures(it)}
                  </tr>
                ))}
                {Number(data.unplanned_hours) > 0 && (
                  <tr>
                    <td className="px-3 py-2 text-slate-500 italic">Unscheduled hours on site</td>
                    <td className="px-3 py-2" />
                    <td className="px-3 py-2 text-right font-mono">{fmtHours(data.unplanned_hours)}</td>
                    <td colSpan={isAdmin ? 4 : 1} />
                  </tr>
                )}
              </tbody>
              <tfoot className="bg-slate-50 font-semibold border-t-2 border-slate-200">
                <tr>
                  <td className="px-3 py-2">
                    Worksite ({data.period_from} – {data.period_to})
                  </td>
                  {figures(data)}
                </tr>
              </tfoot>
            </table>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-slate-50 text-slate-600 uppercase text-[10px] tracking-wider">
                {head("Month")}
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.months.map((m) => (
                  <tr key={m.month_from}>
                    <td className="px-3 py-2">{monthLabel(m.month_from)}</td>
                    {figures(m)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
};
