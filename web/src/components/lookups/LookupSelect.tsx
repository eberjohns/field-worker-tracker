import React from "react";
import { useAuth } from "../../context/AuthContext";
import { lookupLoaded, useLookup } from "../../features/lookups/useLookup";
import { LIST_LABELS, selectOptions, type ListKey } from "../../features/lookups/lookupUtils";

interface Props {
  listKey: ListKey;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  disabled?: boolean;
  placeholder?: string;
  inputClassName?: string;
  id?: string;
}

/**
 * Plain dropdown over a managed list (DEC-60; owner decision 23 Nov 2026: no adding from here).
 * Staff types are added by Admin in Settings > Managed Lists; grade codes come from active salary
 * revisions. The record's current value always stays selectable, marked "(not in list)" when it
 * has left the list.
 */
export const LookupSelect: React.FC<Props> = ({
  listKey,
  value,
  onChange,
  required,
  disabled,
  placeholder,
  inputClassName = "w-full px-3 py-2 text-sm border border-slate-300 rounded-lg bg-white focus:ring-2 focus:ring-indigo-500 focus:outline-none",
  id,
}) => {
  const { token } = useAuth();
  const values = useLookup(listKey, token);
  const options = selectOptions(listKey, values, value, lookupLoaded(listKey));
  return (
    <select
      id={id}
      required={required}
      disabled={disabled}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`${inputClassName} ${disabled ? "bg-slate-100 text-slate-500 cursor-not-allowed" : ""}`}
    >
      <option value="">{placeholder ?? `Select ${LIST_LABELS[listKey]}`}</option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
};
