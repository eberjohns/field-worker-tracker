import { useEffect, useState } from "react";
import { X, Users, AlertCircle } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { formatApiError } from "./jobItemUtils";

interface SupervisorProposal {
  supervisor_id: string;
  supervisor_name: string;
  supervisor_tally_id: string;
  crew_members_on_site: number;
}

interface WorksiteProposal {
  worksite_id: string;
  job_number: string;
  job_name: string;
  assigned_supervisor_ids: string[];
  proposals: SupervisorProposal[];
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onAssigned: () => void;
}

const pairKey = (worksiteId: string, supervisorId: string) => `${worksiteId}:${supervisorId}`;

/**
 * DEC-57 "Assign supervisors from current crews": the server proposes, Admin reviews and
 * ticks the pairs to assign, and nothing is assigned until Admin confirms.
 */
export default function SupervisorProposalsModal({ isOpen, onClose, onAssigned }: Props) {
  const { token } = useAuth();
  const [rows, setRows] = useState<WorksiteProposal[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

  useEffect(() => {
    if (!isOpen) return;
    setSelected(new Set());
    setResult(null);
    setError(null);
    setLoading(true);
    fetch("/api/v1/worksites/supervisor-proposals", { headers })
      .then(async (res) => {
        if (!res.ok) throw new Error(formatApiError(await res.json().catch(() => null)));
        setRows(await res.json());
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  if (!isOpen) return null;

  const withProposals = rows.filter((r) => r.proposals.length > 0);
  const withoutProposals = rows.filter((r) => r.proposals.length === 0);

  const toggle = (key: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const selectTopSuggestions = () => {
    const next = new Set<string>();
    for (const r of withProposals) next.add(pairKey(r.worksite_id, r.proposals[0].supervisor_id));
    setSelected(next);
  };

  const confirm = async () => {
    setSaving(true);
    setError(null);
    try {
      const assignments = Array.from(selected).map((k) => {
        const [worksite_id, supervisor_id] = k.split(":");
        return { worksite_id, supervisor_id };
      });
      const res = await fetch("/api/v1/worksites/supervisors/bulk-assign", {
        method: "POST",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({ assignments }),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok) throw new Error(formatApiError(body));
      setResult(
        `Assigned ${body.assigned} pair(s)` +
          (body.already_assigned ? `; ${body.already_assigned} were already assigned.` : "."),
      );
      setSelected(new Set());
      onAssigned();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-3xl bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden max-h-[90vh] flex flex-col">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div>
            <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
              <Users className="h-5 w-5 text-indigo-600" /> Assign supervisors from current crews
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Suggested from today's standing assignments. Nothing is assigned until you confirm.
            </p>
          </div>
          <button onClick={onClose} className="p-1 rounded hover:bg-slate-200" title="Close">
            <X className="h-5 w-5 text-slate-500" />
          </button>
        </div>

        <div className="px-6 py-4 overflow-y-auto flex-1 space-y-4">
          {error && (
            <div className="flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-md p-3">
              <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" /> {error}
            </div>
          )}
          {result && (
            <div className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-md p-3">
              {result}
            </div>
          )}
          {loading && <p className="text-sm text-slate-500">Loading suggestions…</p>}

          {!loading && withProposals.length === 0 && !error && (
            <p className="text-sm text-slate-500">No new suggestions from current crews.</p>
          )}

          {withProposals.length > 0 && (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-slate-500 border-b">
                  <th className="py-2">Worksite</th>
                  <th className="py-2">Suggested supervisor (crew members on site)</th>
                </tr>
              </thead>
              <tbody>
                {withProposals.map((r) => (
                  <tr key={r.worksite_id} className="border-b last:border-0 align-top">
                    <td className="py-2 pr-4">
                      <div className="font-medium text-slate-800">{r.job_number}</div>
                      <div className="text-xs text-slate-500">{r.job_name}</div>
                      {r.assigned_supervisor_ids.length === 0 && (
                        <span className="text-[10px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded px-1">
                          UNASSIGNED
                        </span>
                      )}
                    </td>
                    <td className="py-2 space-y-1">
                      {r.proposals.map((p) => {
                        const key = pairKey(r.worksite_id, p.supervisor_id);
                        return (
                          <label key={key} className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={selected.has(key)}
                              onChange={() => toggle(key)}
                            />
                            <span>
                              {p.supervisor_name}{" "}
                              <span className="text-slate-500">({p.supervisor_tally_id})</span>
                            </span>
                            <span className="text-xs text-slate-500">
                              {p.crew_members_on_site} on site
                            </span>
                          </label>
                        );
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {withoutProposals.length > 0 && (
            <div className="text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-md p-3">
              <div className="font-semibold mb-1">
                {withoutProposals.length} unassigned worksite(s) with no crew on site today
              </div>
              Assign these from the worksite page or the Worksite_Supervisors import sheet:{" "}
              {withoutProposals
                .slice(0, 20)
                .map((r) => r.job_number)
                .join(", ")}
              {withoutProposals.length > 20 ? ", …" : ""}
            </div>
          )}
        </div>

        <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
          <button
            onClick={selectTopSuggestions}
            disabled={withProposals.length === 0}
            className="text-sm text-indigo-700 hover:underline disabled:opacity-50"
          >
            Tick the top suggestion for each worksite
          </button>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm border border-slate-300 rounded-md bg-white hover:bg-slate-50"
            >
              Close
            </button>
            <button
              onClick={confirm}
              disabled={selected.size === 0 || saving}
              className="px-4 py-2 text-sm rounded-md bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {saving ? "Assigning…" : `Assign ${selected.size} selected`}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
