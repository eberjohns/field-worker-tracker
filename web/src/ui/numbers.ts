/** NumberField parsing (Batch 10 A). */

export interface NumberRules {
  min?: number;
  max?: number;
  /** Whole numbers only. */
  integer?: boolean;
}

export interface ParsedNumber {
  value: number | null;
  error: string | null;
}

function shown(n: number): string {
  return Number.isInteger(n) ? String(n) : String(Number(n.toFixed(6)));
}

/** Typed text as a number with a readable error. Empty text is null (no value), not 0. */
export function parseNumberInput(input: string, rules: NumberRules = {}): ParsedNumber {
  const s = input.trim().replace(/,/g, "");
  if (!s) return { value: null, error: null };
  if (!/^[-+]?(\d+\.?\d*|\.\d+)$/.test(s)) return { value: null, error: "Enter a number" };
  const n = Number(s);
  if (!Number.isFinite(n)) return { value: null, error: "Enter a number" };
  if (rules.integer && !Number.isInteger(n)) return { value: n, error: "Enter a whole number" };
  if (rules.min !== undefined && n < rules.min) {
    return { value: n, error: `Must be at least ${shown(rules.min)}` };
  }
  if (rules.max !== undefined && n > rules.max) {
    return { value: n, error: `Must be at most ${shown(rules.max)}` };
  }
  return { value: n, error: null };
}

/** The text a NumberField shows for a value. */
export function formatNumberInput(value: number | null | undefined): string {
  return value === null || value === undefined || Number.isNaN(value) ? "" : shown(value);
}
