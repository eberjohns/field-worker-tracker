// Managed lists (DEC-60): staff types and grade codes. Pure helpers, tested with node:test.
// Owner decision 23 Nov 2026: dropdowns are plain; Admin adds staff types in Settings; grade codes
// come only from active salary revisions.

export type ListKey = "staff_grade_description" | "grade_code";

export interface LookupValue {
  id: string | null;
  value: string;
  is_active: boolean;
  source: string;
  version: number | null;
  created_at?: string | null;
}

export const LIST_LABELS: Record<ListKey, string> = {
  staff_grade_description: "Staff Grade Description",
  grade_code: "Grade code",
};

/** Case- and space-insensitive key, the same rule as the server ("Gardener  helper" == "GardenerHelper"). */
export function valueKey(v: string): string {
  return (v || "").replace(/\s+/g, "").toLowerCase();
}

const GRADE_RE = /^G(\d+)([A-Z]?)$/;

export function gradeSortKey(code: string): [number, string] {
  const m = GRADE_RE.exec(code);
  return m ? [Number(m[1]), m[2]] : [10_000, code];
}

export function compareGrades(a: string, b: string): number {
  const [na, la] = gradeSortKey(a);
  const [nb, lb] = gradeSortKey(b);
  return na !== nb ? na - nb : la.localeCompare(lb);
}

/** Grades in natural order (G1A < G2A < G10A); staff types alphabetically. */
export function sortValues(listKey: ListKey, values: readonly string[]): string[] {
  const copy = [...values];
  return listKey === "grade_code"
    ? copy.sort(compareGrades)
    : copy.sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
}

/** Dropdown options: the list, de-duplicated, plus the record's current value (even if deactivated). */
export function optionsWithCurrent(
  listKey: ListKey,
  values: readonly string[],
  current?: string | null,
): string[] {
  const byKey = new Map<string, string>();
  for (const v of values) {
    if (typeof v === "string" && v.trim() !== "" && !byKey.has(valueKey(v))) byKey.set(valueKey(v), v.trim());
  }
  if (current && current.trim() !== "" && !byKey.has(valueKey(current))) {
    byKey.set(valueKey(current), current.trim());
  }
  return sortValues(listKey, [...byKey.values()]);
}

export interface SelectOption {
  value: string;
  label: string;
}

/**
 * Options for a plain dropdown: the active values, plus the record's current value when it is
 * not in the list any more, marked "(not in list)" once the list has loaded.
 */
export function selectOptions(
  listKey: ListKey,
  values: readonly string[],
  current: string | null | undefined,
  loaded: boolean,
): SelectOption[] {
  const listed = new Set(values.map(valueKey));
  return optionsWithCurrent(listKey, values, current).map((v) => ({
    value: v,
    label: loaded && !listed.has(valueKey(v)) ? `${v} (not in list)` : v,
  }));
}

/** Only Admin adds, deactivates and reactivates staff types (Settings > Managed Lists). */
export function canManageLists(role: string | null | undefined): boolean {
  return role === "ADMIN";
}

/** "G3C" + "2026" -> "G3C-2026"; the stored value stays the base code (DEC-58). */
export function displayGrade(base: string, suffixLabel?: string | null): string {
  return suffixLabel ? `${base}-${suffixLabel}` : base;
}

export type AddOutcome =
  | { kind: "added"; value: string; body: any }
  | { kind: "exists"; value: string; existingId: string | null; isActive: boolean; message: string }
  | { kind: "near"; value: string; suggestions: string[]; message: string }
  | { kind: "error"; message: string };

const DUPLICATE_CODES = new Set(["LOOKUP_DUPLICATE", "DUPLICATE_NAME"]);
const NEAR_CODES = new Set(["LOOKUP_NEAR_MATCH", "NEAR_MATCH"]);

/**
 * Turn an "add" response into what an add form shows. Shared by the staff type form
 * (POST /lookups) and the group and zone forms (POST /groups, /zones).
 */
export function addOutcome(status: number, body: any): AddOutcome {
  if (status === 201 || status === 200) {
    return { kind: "added", value: String(body?.value ?? body?.name ?? ""), body };
  }
  if (status === 409 && DUPLICATE_CODES.has(body?.code)) {
    return {
      kind: "exists",
      value: String(body.existing ?? ""),
      existingId: body.existing_id ? String(body.existing_id) : null,
      isActive: body.is_active !== false,
      message: String(body.detail ?? "Already in the list."),
    };
  }
  if (status === 422 && NEAR_CODES.has(body?.code)) {
    return {
      kind: "near",
      value: String(body.value ?? ""),
      suggestions: Array.isArray(body.suggestions) ? body.suggestions.map(String) : [],
      message: String(body.detail ?? ""),
    };
  }
  const msg = typeof body?.detail === "string" ? body.detail : "Could not add the value.";
  return { kind: "error", message: msg };
}
