import { useEffect, useReducer } from "react";
import { addOutcome, type AddOutcome, type ListKey, type LookupValue } from "./lookupUtils";

// One shared copy of each list for the whole app, so a staff type added in Settings shows up in
// every open form at once (DEC-60).
const cache = new Map<ListKey, LookupValue[]>();
const pending = new Map<ListKey, Promise<void>>();
const listeners = new Map<ListKey, Set<() => void>>();

function notify(listKey: ListKey) {
  listeners.get(listKey)?.forEach((fn) => fn());
}

function authHeaders(token: string | null | undefined): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Reload one list (its active values). */
export function refreshLookup(listKey: ListKey, token: string | null | undefined): Promise<void> {
  const running = pending.get(listKey);
  if (running) return running;
  const p = fetch(`/api/v1/lookups/${listKey}`, { headers: authHeaders(token) })
    .then((res) => (res.ok ? res.json() : []))
    .then((data: unknown) => {
      cache.set(listKey, Array.isArray(data) ? (data as LookupValue[]) : []);
      notify(listKey);
    })
    .catch((err) => console.error(`Failed to load list ${listKey}`, err))
    .finally(() => pending.delete(listKey));
  pending.set(listKey, p);
  return p;
}

/** True once the list has been loaded at least once. */
export function lookupLoaded(listKey: ListKey): boolean {
  return cache.has(listKey);
}

/** Active values of a managed list, for dropdowns. */
export function useLookup(listKey: ListKey, token: string | null | undefined): string[] {
  const [, rerender] = useReducer((x: number) => x + 1, 0);
  useEffect(() => {
    let set = listeners.get(listKey);
    if (!set) {
      set = new Set();
      listeners.set(listKey, set);
    }
    set.add(rerender);
    if (!cache.has(listKey)) void refreshLookup(listKey, token);
    return () => {
      set?.delete(rerender);
    };
  }, [listKey, token]);
  return (cache.get(listKey) ?? []).filter((v) => v.is_active).map((v) => v.value);
}

/** POST a new staff type (Admin, Settings); on success every open dropdown reloads. */
export async function addLookupValue(
  listKey: ListKey,
  token: string | null | undefined,
  value: string,
  confirmNearMatch: boolean,
): Promise<AddOutcome> {
  try {
    const res = await fetch(`/api/v1/lookups/${listKey}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders(token) },
      body: JSON.stringify({ value, confirm_near_match: confirmNearMatch }),
    });
    const body = await res.json().catch(() => ({}));
    const outcome = addOutcome(res.status, body);
    if (outcome.kind === "added") await refreshLookup(listKey, token);
    return outcome;
  } catch {
    return { kind: "error", message: "Could not add the value." };
  }
}
