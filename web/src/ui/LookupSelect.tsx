import React from "react";
import { LIST_LABELS, selectOptions, type ListKey } from "../features/lookups/lookupUtils";
import { Select, type SelectProps } from "./Select";

export interface LookupSelectProps extends Omit<SelectProps, "options" | "placeholder"> {
  listKey: ListKey;
  /** The managed list's active values (from `useLookup`). */
  values: readonly string[];
  /** False until the list has loaded once (then a missing current value is "(not in list)"). */
  loaded: boolean;
  placeholder?: string;
}

/**
 * Dropdown over a managed list (DEC-60): sorted values, and the record's current value always
 * selectable, marked "(not in list)" once it has left the list. Presentational: the connected
 * version that loads the list is `components/lookups/LookupSelect`.
 */
export const LookupSelect: React.FC<LookupSelectProps> = ({ listKey, values, loaded, value, placeholder, ...rest }) => (
  <Select
    value={value}
    options={selectOptions(listKey, values, value, loaded)}
    placeholder={placeholder ?? `Select ${LIST_LABELS[listKey]}`}
    {...rest}
  />
);
