/** Job budget display helpers (DEC-59). Money fields are null for non-Admin roles. */

import { formatAmount, formatMoney } from "../format/money.ts";

export interface BudgetWarning {
  code: string;
  job_item_id?: string | null;
  sub_item_code?: string | null;
  grade_code?: string | null;
  annual_hours?: number | string;
  message: string;
  plan_provisions?: number | string | null;
  payroll_provisions?: number | string | null;
}

export interface JobItemBudget {
  period_from: string;
  period_to: string;
  activities_per_year: number | string;
  full_year_hours: number | string;
  active_days: number;
  annual_hours: number | string;
  hourly_rate: number | string | null;
  annual_cost: number | string | null;
  is_budget_only: boolean;
  revision_code: string | null;
  warnings: BudgetWarning[];
}

export interface WorksiteBudgetTotals {
  period_from: string;
  period_to: string;
  revision_code: string | null;
  total_hours: number | string;
  missing_rate_hours: number | string;
  total_cost: number | string | null;
  warnings: BudgetWarning[];
}

export interface PlannedActualFigures {
  planned_hours: number | string;
  actual_hours: number | string;
  hours_diff: number | string;
  hours_diff_pct: number | string | null;
  planned_cost: number | string | null;
  actual_cost: number | string | null;
  cost_diff: number | string | null;
  cost_diff_pct: number | string | null;
}

export interface PlannedActualMonth extends PlannedActualFigures {
  month_from: string;
  month_to: string;
}

export interface PlannedActualItem extends PlannedActualFigures {
  job_item_id: string;
  sub_item_code: string;
  staff_grade_description: string;
  grade_code: string;
  is_budget_only: boolean;
  is_active: boolean;
  excluded_from_totals: boolean;
  hourly_rate: number | string | null;
  months: PlannedActualMonth[];
}

export interface WorksitePlannedVsActual extends PlannedActualFigures {
  worksite_id: string;
  job_number: string;
  job_name: string;
  country: string;
  period_from: string;
  period_to: string;
  revision_code: string | null;
  unplanned_hours: number | string;
  unallocated_actual_cost: number | string | null;
  items: PlannedActualItem[];
  months: PlannedActualMonth[];
  warnings: BudgetWarning[];
  missing_rate_hours: number | string;
}

const num = (v: number | string | null | undefined): number | null =>
  v === null || v === undefined || v === "" ? null : Number(v);

/** "1,234.5 h" or "–". */
export function fmtHours(v: number | string | null | undefined): string {
  const n = num(v);
  return n === null || Number.isNaN(n)
    ? "–"
    : `${n.toLocaleString(undefined, { maximumFractionDigits: 1 })} h`;
}

/** "AED 12,345.67" with a currency, "12,345.67" without one, or "–" (shared formatter). */
export function fmtMoney(v: number | string | null | undefined, currency?: string | null): string {
  return currency ? formatMoney(v, currency) : formatAmount(v);
}

/** "+12.5%" / "-3.0%" or "–" when nothing was planned. */
export function fmtPct(v: number | string | null | undefined): string {
  const n = num(v);
  if (n === null || Number.isNaN(n)) return "–";
  return `${n > 0 ? "+" : ""}${n.toFixed(1)}%`;
}

/** Signed difference with a unit-specific formatter. */
export function fmtDiff(
  v: number | string | null | undefined,
  fmt: (x: number) => string,
): string {
  const n = num(v);
  if (n === null || Number.isNaN(n)) return "–";
  return `${n > 0 ? "+" : ""}${fmt(n)}`;
}

/** Tailwind text colour for a variance: over plan red, under plan green. */
export function diffClass(v: number | string | null | undefined): string {
  const n = num(v);
  if (n === null || n === 0 || Number.isNaN(n)) return "text-slate-600";
  return n > 0 ? "text-rose-600" : "text-emerald-600";
}

/** "Jan 2026" from an ISO date. */
export function monthLabel(iso: string): string {
  const [y, m] = iso.split("-").map(Number);
  const names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${names[(m || 1) - 1]} ${y}`;
}

/** Sum a numeric field over rows, ignoring nulls; null if every value is null. */
export function sumField<T>(rows: T[], pick: (r: T) => number | string | null | undefined): number | null {
  let any = false;
  let total = 0;
  for (const r of rows) {
    const n = num(pick(r));
    if (n !== null && !Number.isNaN(n)) {
      any = true;
      total += n;
    }
  }
  return any ? total : null;
}
