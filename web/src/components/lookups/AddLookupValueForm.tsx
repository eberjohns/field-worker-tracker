import React, { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { addLookupValue } from "../../features/lookups/useLookup";
import { LIST_LABELS, type ListKey } from "../../features/lookups/lookupUtils";

interface Props {
  listKey: ListKey;
  /** ``existed`` is true when the value was already in the list. */
  onAdded: (value: string, existed: boolean) => void;
}

/** Settings > Managed Lists: Admin adds a staff type. Duplicates and near spellings are checked. */
export const AddLookupValueForm: React.FC<Props> = ({ listKey, onAdded }) => {
  const { token } = useAuth();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestion, setSuggestion] = useState<string | null>(null);

  const submit = async (confirmNearMatch: boolean) => {
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    const out = await addLookupValue(listKey, token, text, confirmNearMatch);
    setBusy(false);
    if (out.kind === "added") {
      setSuggestion(null);
      setText("");
      onAdded(out.value, false);
    } else if (out.kind === "exists") {
      if (out.isActive) onAdded(out.value, true);
      else setError(out.message);
    } else if (out.kind === "near") {
      setSuggestion(out.suggestions[0] ?? null);
    } else {
      setError(out.message);
    }
  };

  return (
    <div className="p-2 border border-indigo-200 bg-indigo-50/60 rounded-lg space-y-1.5 text-xs">
      <div className="flex gap-1.5">
        <input
          type="text"
          value={text}
          maxLength={100}
          onChange={(e) => {
            setText(e.target.value);
            setSuggestion(null);
            setError(null);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void submit(false);
            }
          }}
          placeholder={`New ${LIST_LABELS[listKey]}`}
          className="flex-1 min-w-0 px-2 py-1 border border-slate-300 rounded bg-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
        <button
          type="button"
          disabled={busy || !text.trim()}
          onClick={() => void submit(false)}
          className="px-2 py-1 bg-indigo-600 text-white rounded font-semibold disabled:opacity-50"
        >
          {busy ? "Adding…" : "Add"}
        </button>
      </div>
      {suggestion && (
        <div className="flex flex-wrap items-center gap-1.5 text-amber-800">
          <span>
            Did you mean <b>{suggestion}</b>? It is already in the list.
          </span>
          <button
            type="button"
            onClick={() => {
              setSuggestion(null);
              setText("");
            }}
            className="px-1.5 py-0.5 border border-amber-300 bg-white rounded font-semibold"
          >
            Keep {suggestion}
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
    </div>
  );
};
