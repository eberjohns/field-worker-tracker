import { useEffect, useState } from "react";
import type { JobItemBudget } from "./budgetFormat";

type PreviewState = { budget: JobItemBudget | null; error: string | null; loading: boolean };

/** Debounced POST to a budget-preview endpoint (DEC-59). Saves nothing. */
function usePreview(
  token: string | null | undefined,
  url: string | null,
  body: Record<string, unknown> | null,
  delayMs: number,
): PreviewState {
  const [budget, setBudget] = useState<JobItemBudget | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const key = url && body ? JSON.stringify(body) : "";

  useEffect(() => {
    if (!key || !url) {
      setBudget(null);
      setError(null);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      setLoading(true);
      fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: key,
      })
        .then(async (res) => {
          const data = await res.json().catch(() => ({}));
          if (cancelled) return;
          if (res.ok) {
            setBudget(data as JobItemBudget);
            setError(null);
          } else {
            setBudget(null);
            setError(typeof data?.detail === "string" ? data.detail : "Could not calculate the budget.");
          }
        })
        .catch(() => {
          if (!cancelled) setError("Could not calculate the budget.");
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, delayMs);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [key, url, token, delayMs]);

  return { budget, error, loading };
}

/**
 * Live planned man-hours (and, for Admin, cost) of an unsaved job item on a saved worksite.
 * Pass payload null to skip (e.g. while required fields are empty).
 */
export function useBudgetPreview(
  token: string | null | undefined,
  worksiteId: string | null | undefined,
  payload: Record<string, unknown> | null,
  delayMs = 400,
): PreviewState {
  return usePreview(
    token,
    worksiteId ? `/api/v1/worksites/${worksiteId}/job-items/budget-preview` : null,
    payload,
    delayMs,
  );
}

/** Same for a job item of a worksite that is not saved yet (Add Worksite form). */
export function useNewWorksiteBudgetPreview(
  token: string | null | undefined,
  country: string,
  item: Record<string, unknown> | null,
  delayMs = 400,
): PreviewState {
  return usePreview(
    token,
    "/api/v1/job-items/budget-preview",
    item ? { country, item } : null,
    delayMs,
  );
}
