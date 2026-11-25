// Settings > System (Admin): our own count of Google Maps usage per month for this environment
// (Batch 8, ADR-033), with the soft limits from the company settings. Google's own quotas
// (runbook 08) are the hard stop; this warns before them.

import React from "react";
import { Map as MapIcon } from "lucide-react";
import { useApi } from "../../api/apiCache";
import { AlertBanner, Skeleton } from "../../ui";

interface MapUsageSummary {
  environment: string;
  months: { month: string; map_loads: number; geocodes: number }[];
  soft_limits: { MAP_LOAD: number; GEOCODE: number };
  warnings: string[];
}

function monthLabel(ym: string): string {
  const [y, m] = ym.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString("en-GB", { month: "short", year: "numeric", timeZone: "UTC" });
}

const Bar: React.FC<{ value: number; limit: number }> = ({ value, limit }) => {
  const pct = limit > 0 ? Math.min(100, Math.round((value / limit) * 100)) : 0;
  const tone = pct >= 100 ? "bg-red-500" : pct >= 80 ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 rounded bg-slate-100" aria-hidden>
        <div className={`h-1.5 rounded ${tone}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="tabular-nums text-xs text-slate-500">{pct}%</span>
    </div>
  );
};

export const MapUsagePanel: React.FC = () => {
  const { data, isLoading, error } = useApi<MapUsageSummary>("/api/v1/map-usage?months=6");

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4">
      <div className="flex items-start gap-3">
        <MapIcon className="h-5 w-5 text-indigo-600 mt-0.5" />
        <div>
          <h2 className="text-base font-semibold text-slate-900">Google Maps usage</h2>
          <p className="text-xs text-slate-500">
            Map loads (a Google map created in a browser) and place searches, counted by this app for the{" "}
            <strong>{data?.environment ?? "…"}</strong> environment. Google's daily quotas are the hard stop
            (runbook 08); the soft limits are company settings (<code>map_loads_soft_limit_month</code>,{" "}
            <code>geocodes_soft_limit_month</code>).
          </p>
        </div>
      </div>

      {error && <AlertBanner tone="error">Could not load map usage.</AlertBanner>}
      {data?.warnings.map((w) => (
        <AlertBanner key={w} tone="warning">
          {w}
        </AlertBanner>
      ))}

      {isLoading || !data ? (
        <Skeleton className="h-32 w-full" />
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-slate-500 border-b border-slate-200">
              <th className="py-2 pr-4 font-medium">Month</th>
              <th className="py-2 pr-4 font-medium">Map loads</th>
              <th className="py-2 pr-4 font-medium">of soft limit</th>
              <th className="py-2 pr-4 font-medium">Place searches</th>
              <th className="py-2 font-medium">of soft limit</th>
            </tr>
          </thead>
          <tbody>
            {data.months.map((m) => (
              <tr key={m.month} className="border-b border-slate-100 last:border-b-0">
                <td className="py-2 pr-4 text-slate-700">{monthLabel(m.month)}</td>
                <td className="py-2 pr-4 tabular-nums font-medium text-slate-900">{m.map_loads.toLocaleString()}</td>
                <td className="py-2 pr-4">
                  <Bar value={m.map_loads} limit={data.soft_limits.MAP_LOAD} />
                </td>
                <td className="py-2 pr-4 tabular-nums font-medium text-slate-900">{m.geocodes.toLocaleString()}</td>
                <td className="py-2">
                  <Bar value={m.geocodes} limit={data.soft_limits.GEOCODE} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {data && (
        <p className="text-xs text-slate-500">
          Soft limits per month: {data.soft_limits.MAP_LOAD.toLocaleString()} map loads,{" "}
          {data.soft_limits.GEOCODE.toLocaleString()} place searches.
        </p>
      )}
    </div>
  );
};
