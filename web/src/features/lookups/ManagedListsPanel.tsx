import React, { useCallback, useEffect, useState } from "react";
import { ListChecks } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { AddLookupValueForm } from "../../components/lookups/AddLookupValueForm";
import { refreshLookup } from "./useLookup";
import { LIST_LABELS, canManageLists, type ListKey, type LookupValue } from "./lookupUtils";

const SOURCE_LABEL: Record<string, string> = {
  SEED: "Seed / existing data",
  SCREEN: "Added in Settings",
  IMPORT: "Added by import (before 23 Nov 2026)",
  REVISION: "Active salary revision",
  IN_USE: "In use, not in list",
};

/**
 * Settings → Managed lists (DEC-60, owner decision 23 Nov 2026). Staff types: Admin adds,
 * deactivates and reactivates; others read. Grade codes: read-only, they follow the active salary
 * revisions.
 */
export const ManagedListsPanel: React.FC = () => {
  const { token, user } = useAuth();
  const [listKey, setListKey] = useState<ListKey>("staff_grade_description");
  const [rows, setRows] = useState<LookupValue[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`/api/v1/lookups/${listKey}?include_inactive=true`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error();
      setRows(await res.json());
      setError(null);
    } catch {
      setError("Could not load the list.");
    }
  }, [listKey, token]);

  const canEdit = canManageLists(user?.role) && listKey === "staff_grade_description";

  useEffect(() => {
    void load();
  }, [load]);

  const toggle = async (row: LookupValue) => {
    if (!row.id || row.version === null) return;
    setBusyId(row.id);
    try {
      const res = await fetch(`/api/v1/lookups/${listKey}/${row.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ is_active: !row.is_active, version: row.version }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof body?.detail === "string" ? body.detail : "Update failed.");
      await load();
      await refreshLookup(listKey, token);
    } catch (e: any) {
      setError(e.message || "Update failed.");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-slate-900 flex items-center gap-2">
            <ListChecks className="w-4 h-4 text-indigo-600" /> Managed lists
          </h3>
          <p className="text-xs text-slate-500 max-w-2xl">
            Values offered in every Staff Grade Description and Grade Code dropdown (DEC-60).
            {listKey === "staff_grade_description"
              ? " Only an Admin adds staff types, here. Deactivating one takes it out of the dropdowns; records that already use it keep it. Values are never deleted, and imports never add one."
              : " Grade codes come from salary revisions: the list is every grade with a line in an active revision. To add a grade, add a line for it to a revision."}
          </p>
        </div>
        <div className="flex rounded-lg border border-slate-200 overflow-hidden text-xs font-medium">
          {(Object.keys(LIST_LABELS) as ListKey[]).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => {
                setListKey(k);
                setNotice(null);
              }}
              className={`px-3 py-1.5 ${listKey === k ? "bg-indigo-600 text-white" : "bg-white text-slate-600 hover:bg-slate-50"}`}
            >
              {LIST_LABELS[k]}
            </button>
          ))}
        </div>
      </div>

      {canEdit && (
        <div className="max-w-md">
          <AddLookupValueForm
            key={listKey}
            listKey={listKey}
            onAdded={(value, existed) => {
              setNotice(existed ? `'${value}' is already in the list.` : `Added ${value}.`);
              void load();
            }}
          />
        </div>
      )}
      {notice && <div className="text-xs text-emerald-700">{notice}</div>}
      {error && <div className="text-xs text-rose-700">{error}</div>}

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="bg-slate-50 text-slate-500 uppercase text-[10px] tracking-wider">
            <tr>
              <th className="px-3 py-2 text-left">Value</th>
              <th className="px-3 py-2 text-left">Source</th>
              <th className="px-3 py-2 text-left">Status</th>
              {canEdit && <th className="px-3 py-2 text-right">Action</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((r) => (
              <tr key={`${r.id ?? "in-use"}-${r.value}`} className={r.is_active ? "" : "text-slate-400"}>
                <td className={`px-3 py-2 ${listKey === "grade_code" ? "font-mono" : ""}`}>{r.value}</td>
                <td className="px-3 py-2">{SOURCE_LABEL[r.source] ?? r.source}</td>
                <td className="px-3 py-2">{r.is_active ? "Active" : "Deactivated"}</td>
                {canEdit && (
                  <td className="px-3 py-2 text-right">
                    {r.id && (
                      <button
                        type="button"
                        disabled={busyId === r.id}
                        onClick={() => void toggle(r)}
                        className="px-2 py-1 border border-slate-300 rounded hover:bg-slate-50 disabled:opacity-50"
                      >
                        {r.is_active ? "Deactivate" : "Reactivate"}
                      </button>
                    )}
                  </td>
                )}
              </tr>
            ))}
            {rows.length === 0 && !error && (
              <tr>
                <td colSpan={canEdit ? 4 : 3} className="px-3 py-6 text-center text-slate-400">
                  No values yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
