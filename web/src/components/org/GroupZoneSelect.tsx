import React, { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { addOutcome } from "../../features/lookups/lookupUtils";
import {
  NEW_UNIT,
  UNIT_LABELS,
  canAddUnit,
  findUnitByName,
  unitOptions,
  unitPayload,
  type OrgUnit,
  type UnitKind,
} from "../../features/org/groupZoneUtils";

interface Props {
  kind: UnitKind;
  value: string;
  onChange: (id: string) => void;
  items: OrgUnit[];
  /** Called with the new group or zone so the parent can add it to its list. */
  onCreated: (unit: OrgUnit) => void;
  required?: boolean;
  selectClassName?: string;
}

/**
 * Group or zone dropdown with "Other – add new…" (Admin, Engineer). The small form saves the new
 * group or zone at once and selects it: a group needs only its name (the 3-digit code is
 * generated), a zone its code and name. Duplicates and near names are checked like the managed
 * lists (DEC-60 amendment, owner decision 23 Nov 2026).
 */
export const GroupZoneSelect: React.FC<Props> = ({
  kind,
  value,
  onChange,
  items,
  onCreated,
  required,
  selectClassName = "w-full px-3 py-1.5 border border-slate-300 rounded text-sm focus:ring-1 focus:ring-indigo-500 bg-white",
}) => {
  const { token, user } = useAuth();
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestion, setSuggestion] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const label = UNIT_LABELS[kind];

  const close = () => {
    setAdding(false);
    setName("");
    setCode("");
    setError(null);
    setSuggestion(null);
  };

  const submit = async (confirmNearMatch: boolean) => {
    if (!name.trim() || (kind === "zone" && !code.trim())) {
      setError(kind === "zone" ? "Enter the zone code and name." : "Enter the group name.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(kind === "group" ? "/api/v1/groups" : "/api/v1/zones", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify(unitPayload(kind, name, code, confirmNearMatch)),
      });
      const body = await res.json().catch(() => ({}));
      const out = addOutcome(res.status, body);
      if (out.kind === "added") {
        const unit = body as OrgUnit;
        onCreated(unit);
        onChange(unit.id);
        setNotice(kind === "group" ? `Added ${unit.name} with code ${unit.code}.` : `Added ${unit.name}.`);
        close();
      } else if (out.kind === "exists" && out.isActive && out.existingId) {
        onChange(out.existingId);
        setNotice(`${out.value} already exists; selected it.`);
        close();
      } else if (out.kind === "near") {
        setSuggestion(out.suggestions[0] ?? null);
      } else {
        setError(out.kind === "exists" || out.kind === "error" ? out.message : "Could not add.");
      }
    } catch {
      setError(`Could not add the ${label.toLowerCase()}.`);
    } finally {
      setBusy(false);
    }
  };

  const useSuggestion = () => {
    const hit = suggestion ? findUnitByName(items, suggestion) : undefined;
    if (hit) {
      onChange(hit.id);
      setNotice(`Selected ${hit.name}.`);
      close();
    } else {
      setError(`${suggestion} is not in the list here; reload the page.`);
    }
  };

  const enter = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault(); // never submit the surrounding form
      void submit(false);
    } else if (e.key === "Escape") {
      close();
    }
  };

  return (
    <div>
      <select
        required={required}
        value={adding ? NEW_UNIT : value}
        onChange={(e) => {
          setNotice(null);
          if (e.target.value === NEW_UNIT) {
            setAdding(true);
          } else {
            close();
            onChange(e.target.value);
          }
        }}
        className={selectClassName}
      >
        <option value="">Select {label}...</option>
        {unitOptions(items, value).map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
        {canAddUnit(user?.role) && <option value={NEW_UNIT}>Other – add new…</option>}
      </select>
      {adding && (
        <div className="mt-2 space-y-1.5 p-2.5 bg-slate-50 border border-slate-200 rounded text-xs">
          {kind === "zone" && (
            <input
              type="text"
              autoFocus
              placeholder="Zone code (e.g. 7)"
              maxLength={50}
              value={code}
              onChange={(e) => {
                setCode(e.target.value);
                setError(null);
              }}
              onKeyDown={enter}
              className="w-full px-2.5 py-1 font-mono border border-slate-300 rounded bg-white"
            />
          )}
          <input
            type="text"
            autoFocus={kind === "group"}
            placeholder={kind === "group" ? "New group name (e.g. Emaar)" : "Zone name (e.g. Jebel Ali)"}
            maxLength={100}
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              setSuggestion(null);
              setError(null);
            }}
            onKeyDown={enter}
            className="w-full px-2.5 py-1 border border-slate-300 rounded bg-white"
          />
          {kind === "group" && <div className="text-slate-500">The 3-digit group code is given automatically.</div>}
          {suggestion && (
            <div className="flex flex-wrap items-center gap-1.5 text-amber-800">
              <span>
                Did you mean <b>{suggestion}</b>?
              </span>
              <button
                type="button"
                onClick={useSuggestion}
                className="px-1.5 py-0.5 border border-amber-300 bg-white rounded font-semibold"
              >
                Use {suggestion}
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void submit(true)}
                className="px-1.5 py-0.5 border border-slate-300 bg-white rounded"
              >
                Add anyway
              </button>
            </div>
          )}
          {error && <div className="text-rose-700">{error}</div>}
          <div className="flex gap-1.5">
            <button
              type="button"
              disabled={busy}
              onClick={() => void submit(false)}
              className="px-2 py-1 bg-indigo-600 text-white rounded font-semibold disabled:opacity-50"
            >
              {busy ? "Adding…" : `Add ${label.toLowerCase()}`}
            </button>
            <button type="button" onClick={close} className="px-2 py-1 border border-slate-300 rounded bg-white">
              Cancel
            </button>
          </div>
        </div>
      )}
      {notice && <div className="mt-1 text-[11px] text-emerald-700">{notice}</div>}
    </div>
  );
};
