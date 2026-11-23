// Grade dropdown options (DEC-58). The list comes from GET /api/v1/grades (base codes in use);
// there is no hard-coded fallback list. A record's current value always stays selectable.

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

export function gradeOptions(apiGrades: readonly string[], current?: string | null): string[] {
  const set = new Set(apiGrades.filter((g) => typeof g === "string" && g.trim() !== ""));
  if (current && current.trim() !== "") set.add(current.trim());
  return [...set].sort(compareGrades);
}

/** "G3C" + "2026" -> "G3C-2026"; the stored value stays the base code. */
export function displayGrade(base: string, suffixLabel?: string | null): string {
  return suffixLabel ? `${base}-${suffixLabel}` : base;
}
