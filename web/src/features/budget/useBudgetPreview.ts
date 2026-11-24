import { useEffect, useState } from "react";
import type { JobItemBudget } from "./budgetFormat";

type PreviewState = { budget: JobItemBudget | null; error: string | null; loading: boolean };

type PostState<T> = { data: T | null; error: string | null; loading: boolean };

/** Debounced POST to a preview endpoint. Saves nothing; body null skips the call. */
function usePost<T>(
  token: string | null | undefined,
  url: string | null,
  body: Record<string, unknown> | null,
  delayMs: number,
  fallbackError: string,
): PostState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const key = url && body ? JSON.stringify(body) : "";

  useEffect(() => {
    if (!key || !url) {
      setData(null);
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
          const json = await res.json().catch(() => ({}));
          if (cancelled) return;
          if (res.ok) {
            setData(json as T);
            setError(null);
          } else {
            setData(null);
            setError(typeof json?.detail === "string" ? json.detail : fallbackError);
          }
        })
        .catch(() => {
          if (!cancelled) setError(fallbackError);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, delayMs);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [key, url, token, delayMs, fallbackError]);

  return { data, error, loading };
}

function usePreview(
  token: string | null | undefined,
  url: string | null,
  body: Record<string, unknown> | null,
  delayMs: number,
): PreviewState {
  const { data, error, loading } = usePost<JobItemBudget>(
    token,
    url,
    body,
    delayMs,
    "Could not calculate the budget.",
  );
  return { budget: data, error, loading };
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

/** The contract fields of a worksite that is not saved yet, for its item budgets. */
export interface NewWorksiteContext {
  salary_revision_code?: string | null;
  contract_start?: string | null;
  contract_end?: string | null;
}

/** Same for a job item of a worksite that is not saved yet (Add Worksite wizard). */
export function useNewWorksiteBudgetPreview(
  token: string | null | undefined,
  country: string,
  item: Record<string, unknown> | null,
  context: NewWorksiteContext = {},
  delayMs = 400,
): PreviewState {
  return usePreview(
    token,
    "/api/v1/job-items/budget-preview",
    item
      ? {
          country,
          item,
          salary_revision_code: context.salary_revision_code || null,
          contract_start: context.contract_start || null,
          contract_end: context.contract_end || null,
        }
      : null,
    delayMs,
  );
}

/** The job item validation panel for an unsaved item (POST /job-items/validation-preview). */
export interface JobItemChecks {
  calculated_activities_per_year: number | string;
  calculated_annual_hours: number | string;
  expected_occurrences_count: number;
  days_per_occurrence: number;
  daily_hours_split: (number | string)[];
  eligible_workers_count: number;
}

export function useJobItemChecks(
  token: string | null | undefined,
  country: string,
  item: Record<string, unknown> | null,
  delayMs = 400,
): PostState<JobItemChecks> {
  return usePost<JobItemChecks>(
    token,
    "/api/v1/job-items/validation-preview",
    item && country ? { country, item } : null,
    delayMs,
    "Could not check the job item.",
  );
}
