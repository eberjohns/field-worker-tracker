import React, { useMemo, useRef, useState } from "react";
import { ChevronDown, Plus } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { addLookupValue, useLookup } from "../../features/lookups/useLookup";
import {
  LIST_LABELS,
  canAddLookup,
  filterOptions,
  optionsWithCurrent,
  type ListKey,
} from "../../features/lookups/lookupUtils";

const ADD_LABEL = "Other – add new…";

interface AddFormProps {
  listKey: ListKey;
  initial?: string;
  country?: string | null;
  /** ``existed`` is true when the value was already in the list (it is selected instead). */
  onAdded: (value: string, warnings: string[], existed?: boolean) => void;
  onCancel?: () => void;
}

/** The "add new value" form, shared by LookupSelect and the Settings "Managed lists" tab. */
export const AddLookupValueForm: React.FC<AddFormProps> = ({ listKey, initial = "", country, onAdded, onCancel }) => {
  const { token } = useAuth();
  const [text, setText] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [suggestion, setSuggestion] = useState<string | null>(null);

  const submit = async (confirmNearMatch: boolean) => {
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    const out = await addLookupValue(listKey, token, text, confirmNearMatch, country);
    setBusy(false);
    if (out.kind === "added") {
      setSuggestion(null);
      setText("");
      onAdded(out.value, out.warnings);
    } else if (out.kind === "exists") {
      if (out.isActive) {
        onAdded(out.value, [`'${out.value}' is already in the list.`], true);
      } else {
        setError(out.message);
      }
    } else if (out.kind === "near") {
      setSuggestion(out.suggestions[0] ?? null);
      setError(null);
    } else {
      setError(out.message);
    }
  };

  return (
    <div className="mt-1 p-2 border border-indigo-200 bg-indigo-50/60 rounded-lg space-y-1.5 text-xs">
      <div className="flex gap-1.5">
        <input
          autoFocus
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
              e.preventDefault(); // never submit the surrounding form
              void submit(false);
            } else if (e.key === "Escape" && onCancel) {
              onCancel();
            }
          }}
          placeholder={listKey === "grade_code" ? "e.g. G16A" : `New ${LIST_LABELS[listKey]}`}
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
        {onCancel && (
          <button type="button" onClick={onCancel} className="px-2 py-1 border border-slate-300 rounded bg-white">
            Cancel
          </button>
        )}
      </div>
      {suggestion && (
        <div className="flex flex-wrap items-center gap-1.5 text-amber-800">
          <span>
            Did you mean <b>{suggestion}</b>?
          </span>
          <button
            type="button"
            onClick={() => onAdded(suggestion, [])}
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
      {listKey === "grade_code" && !suggestion && !error && (
        <div className="text-slate-500">Base code only (G3C); a year suffix like -2026 is removed.</div>
      )}
    </div>
  );
};

interface Props {
  listKey: ListKey;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  disabled?: boolean;
  placeholder?: string;
  /** Grade codes: the country whose active revision is checked when a new grade is added. */
  country?: string | null;
  className?: string;
  inputClassName?: string;
  id?: string;
}

/**
 * Searchable dropdown over a managed list (DEC-60). The last option, "Other – add new…", lets
 * Admin and Engineer add a value, which is then available to everyone. The record's current value
 * always stays selectable, even if it has been deactivated since.
 */
export const LookupSelect: React.FC<Props> = ({
  listKey,
  value,
  onChange,
  required,
  disabled,
  placeholder,
  country,
  className = "",
  inputClassName = "w-full px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white focus:ring-2 focus:ring-indigo-500 focus:outline-none",
  id,
}) => {
  const { token, user } = useAuth();
  const values = useLookup(listKey, token, !disabled);
  const options = useMemo(() => optionsWithCurrent(listKey, values, value), [listKey, values, value]);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [adding, setAdding] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const filtered = filterOptions(options, query);
  const allowAdd = canAddLookup(user?.role);

  const choose = (v: string) => {
    onChange(v);
    setOpen(false);
    setQuery("");
  };

  return (
    <div className={`relative ${className}`}>
      <input
        id={id}
        ref={inputRef}
        type="text"
        role="combobox"
        aria-expanded={open}
        autoComplete="off"
        required={required}
        disabled={disabled}
        value={open ? query : value}
        placeholder={open && value ? value : placeholder ?? `Select ${LIST_LABELS[listKey]}`}
        onFocus={() => {
          setOpen(true);
          setQuery("");
        }}
        onBlur={() => setOpen(false)}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && open) {
            e.preventDefault();
            if (filtered.length > 0) choose(filtered[0]);
          } else if (e.key === "Escape") {
            setOpen(false);
            setQuery("");
          }
        }}
        className={`${inputClassName} pr-8 ${disabled ? "bg-slate-100 text-slate-500 cursor-not-allowed" : ""}`}
      />
      <ChevronDown className="pointer-events-none absolute right-2.5 top-2.5 h-4 w-4 text-slate-400" />
      {open && !disabled && (
        <ul className="absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-slate-200 bg-white shadow-lg text-sm">
          {filtered.map((opt) => (
            <li key={opt}>
              <button
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault(); // keep focus until the click is handled
                  choose(opt);
                }}
                className={`block w-full text-left px-3 py-1.5 hover:bg-indigo-50 ${
                  opt === value ? "font-semibold text-indigo-700" : "text-slate-800"
                }`}
              >
                {opt}
              </button>
            </li>
          ))}
          {filtered.length === 0 && <li className="px-3 py-1.5 text-slate-400">No match</li>}
          {allowAdd && (
            <li className="border-t border-slate-100">
              <button
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault();
                  setAdding(query);
                  setOpen(false);
                  setQuery("");
                  setNotice(null);
                }}
                className="flex w-full items-center gap-1.5 px-3 py-1.5 text-left text-indigo-700 hover:bg-indigo-50"
              >
                <Plus className="h-3.5 w-3.5" />
                {ADD_LABEL}
              </button>
            </li>
          )}
        </ul>
      )}
      {adding !== null && (
        <AddLookupValueForm
          listKey={listKey}
          initial={adding}
          country={country}
          onAdded={(v, warnings) => {
            onChange(v);
            setAdding(null);
            setNotice(warnings.length ? warnings.join(" ") : null);
          }}
          onCancel={() => setAdding(null)}
        />
      )}
      {notice && <div className="mt-1 text-[11px] text-amber-700">{notice}</div>}
    </div>
  );
};
