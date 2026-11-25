import React from "react";
import { Link } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";

export interface ActionRow {
  id: string;
  primary: React.ReactNode;
  secondary?: React.ReactNode;
  /** Right-hand badge, e.g. "3d left". */
  meta?: React.ReactNode;
}

interface ActionSectionProps {
  title: string;
  icon: React.ReactNode;
  count: number;
  rows: ActionRow[];
  viewAll: { to: string; search?: Record<string, string>; hash?: string };
  emptyText: string;
  /** Amber for things to act on, rose for urgent ones. */
  tone?: "amber" | "rose" | "indigo";
}

const TONES = {
  amber: "bg-amber-100 text-amber-900",
  rose: "bg-rose-100 text-rose-800",
  indigo: "bg-indigo-100 text-indigo-800",
};

/** One dashboard section: title with count, up to 5 rows, "View all" (Batch 10 B). */
export const ActionSection: React.FC<ActionSectionProps> = ({
  title,
  icon,
  count,
  rows,
  viewAll,
  emptyText,
  tone = "amber",
}) => (
  <section
    aria-label={title}
    className="flex flex-col rounded-lg border border-slate-200 bg-white p-4 shadow-2xs"
  >
    <header className="flex items-center justify-between gap-2">
      <h4 className="flex items-center gap-1.5 text-xs font-bold text-slate-800">
        {icon}
        {title}
      </h4>
      <span
        className={`rounded-full px-2 py-0.5 text-2xs font-extrabold ${
          count > 0 ? TONES[tone] : "bg-slate-100 text-slate-500"
        }`}
        aria-label={`${count} ${title}`}
      >
        {count}
      </span>
    </header>
    {rows.length === 0 ? (
      <p className="mt-3 text-2xs italic text-slate-400">{emptyText}</p>
    ) : (
      <ul className="mt-3 divide-y divide-slate-100">
        {rows.map((r) => (
          <li key={r.id} className="flex items-start justify-between gap-3 py-1.5 text-xs">
            <div className="min-w-0">
              <div className="truncate font-medium text-slate-900">{r.primary}</div>
              {r.secondary && <div className="truncate text-2xs text-slate-500">{r.secondary}</div>}
            </div>
            {r.meta && <div className="shrink-0 text-2xs text-slate-500">{r.meta}</div>}
          </li>
        ))}
      </ul>
    )}
    <div className="mt-auto pt-3">
      <Link
        to={viewAll.to}
        search={viewAll.search as never}
        hash={viewAll.hash}
        className="inline-flex items-center gap-1 text-2xs font-semibold text-indigo-600 hover:text-indigo-800"
      >
        View all <ArrowRight className="h-3 w-3" />
      </Link>
    </div>
  </section>
);
