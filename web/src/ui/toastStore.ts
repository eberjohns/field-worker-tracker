/** Toast queue as a pure reducer, so it can be tested without a browser (Batch 10 A). */
import type { FieldError } from "./errors";

export type ToastTone = "success" | "info" | "warning" | "error";

export interface ToastInput {
  tone: ToastTone;
  title: string;
  message?: string;
  fields?: FieldError[];
  /** Milliseconds; null keeps it until closed. Default by tone (see defaultDuration). */
  durationMs?: number | null;
}

export interface ToastItem extends Required<Omit<ToastInput, "message" | "fields">> {
  id: number;
  message?: string;
  fields: FieldError[];
}

export type ToastAction = { type: "add"; toast: ToastItem } | { type: "dismiss"; id: number };

/** At most this many toasts are on screen; the oldest goes first. */
export const MAX_TOASTS = 4;

/**
 * Success and info leave after 4 s, warnings after 6 s, errors after 8 s. Errors with a list of
 * field problems stay until closed, so there is time to read them.
 */
export function defaultDuration(tone: ToastTone, hasFields = false): number | null {
  if (tone === "error") return hasFields ? null : 8000;
  if (tone === "warning") return 6000;
  return 4000;
}

export function makeToast(id: number, input: ToastInput): ToastItem {
  const fields = input.fields ?? [];
  return {
    id,
    tone: input.tone,
    title: input.title,
    message: input.message,
    fields,
    durationMs:
      input.durationMs === undefined ? defaultDuration(input.tone, fields.length > 0) : input.durationMs,
  };
}

export function toastReducer(state: ToastItem[], action: ToastAction): ToastItem[] {
  switch (action.type) {
    case "add": {
      // The same message twice in a row (a double click) shows once.
      const last = state[state.length - 1];
      if (
        last &&
        last.tone === action.toast.tone &&
        last.title === action.toast.title &&
        last.message === action.toast.message
      ) {
        return state;
      }
      const next = [...state, action.toast];
      return next.length > MAX_TOASTS ? next.slice(next.length - MAX_TOASTS) : next;
    }
    case "dismiss":
      return state.filter((t) => t.id !== action.id);
    default:
      return state;
  }
}
