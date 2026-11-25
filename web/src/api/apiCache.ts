/**
 * Client cache for API reads (Batch 9 step 3), on React Query.
 *
 * Every GET goes through one QueryClient, keyed by its path, so a repeat visit to a page shows
 * the last data at once:
 * - fresh data (younger than its stale time) is used without a request;
 * - stale data is shown at once and refreshed in the background (`loadApi`, `useApi`).
 *
 * Correctness rules:
 * - Any successful write (POST, PUT, PATCH, DELETE under /api/) marks every cached read stale
 *   (`markAllStale`, called by the fetch interceptor in AuthContext). The next read refetches.
 *   This is coarse on purpose: no page can show data older than its own last write.
 * - Signing in, signing out and a 401 clear the cache, so one user never sees another's data.
 * - Data changed by other people shows up after the stale time (30 s for pages, 5 min for
 *   reference lists), or at once on a reload.
 */
import { QueryClient, useQuery, type UseQueryOptions } from "@tanstack/react-query";
import { ApiError, ensureOk } from "../ui/errors";

/** Page data: lists, planners, details. */
export const PAGE_STALE_MS = 30_000;
/** Reference lists that change rarely: groups, zones, revisions, lookups, destinations. */
export const REFERENCE_STALE_MS = 5 * 60_000;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: PAGE_STALE_MS,
      gcTime: 15 * 60_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

export type ApiKey = readonly ["api", string];

export function apiKey(path: string): ApiKey {
  return ["api", path] as const;
}

function token(): string | null {
  try {
    return localStorage.getItem("fwt_token");
  } catch {
    return null;
  }
}

/** One uncached GET: JSON body, or an ApiError for a non-2xx response. */
export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const t = token();
  const res = await fetch(path, { headers: t ? { Authorization: `Bearer ${t}` } : {}, signal });
  await ensureOk(res);
  return (await res.json()) as T;
}

export interface CacheOptions {
  /** How long the data counts as fresh. Default PAGE_STALE_MS. */
  staleTime?: number;
  /** Ignore the cache and fetch (for example a Refresh button). */
  force?: boolean;
}

/** A cache-aware GET: the cached value while fresh, otherwise a request (one per path at a time). */
export async function fetchApi<T>(path: string, opts: CacheOptions = {}): Promise<T> {
  const staleTime = opts.force ? 0 : opts.staleTime ?? PAGE_STALE_MS;
  return queryClient.fetchQuery<T, Error, T, ApiKey>({
    queryKey: apiKey(path),
    queryFn: ({ signal }) => getJson<T>(path, signal),
    staleTime,
  });
}

/** The cached value for a path, fresh or not, without a request. */
export function peekApi<T>(path: string): T | undefined {
  return queryClient.getQueryData<T>(apiKey(path));
}

/** True when the path has cached data that is still fresh. */
export function isFresh(path: string, staleTime: number = PAGE_STALE_MS): boolean {
  const state = queryClient.getQueryState(apiKey(path));
  if (!state || state.data === undefined || state.isInvalidated) return false;
  return Date.now() - state.dataUpdatedAt < staleTime;
}

/**
 * Stale-while-revalidate for imperative loaders:
 * - with cached data, `onData` runs at once with it (`fromCache` true);
 * - unless that data is fresh, the path is then fetched and `onData` runs again with the result.
 * Returns whether cached data was shown, so the caller can skip its loading spinner.
 * Errors of the refresh are thrown, as from a plain fetch.
 */
export async function loadApi<T>(
  path: string,
  onData: (data: T, fromCache: boolean) => void,
  opts: CacheOptions = {}
): Promise<boolean> {
  const staleTime = opts.staleTime ?? PAGE_STALE_MS;
  const cached = opts.force ? undefined : peekApi<T>(path);
  if (cached !== undefined) {
    onData(cached, true);
    if (isFresh(path, staleTime)) return true;
  }
  const data = await fetchApi<T>(path, { staleTime: 0 });
  onData(data, false);
  return cached !== undefined;
}

/** React hook form: `useApi(path)`; a null path disables the query. */
export function useApi<T>(
  path: string | null,
  opts: { staleTime?: number; refetchInterval?: number; enabled?: boolean } & Pick<
    UseQueryOptions<T, Error, T, ApiKey>,
    "placeholderData"
  > = {}
) {
  return useQuery<T, Error, T, ApiKey>({
    queryKey: apiKey(path ?? ""),
    queryFn: ({ signal }) => getJson<T>(path as string, signal),
    enabled: path !== null && (opts.enabled ?? true),
    staleTime: opts.staleTime ?? PAGE_STALE_MS,
    refetchInterval: opts.refetchInterval,
    placeholderData: opts.placeholderData,
  });
}

/** After a write: every cached read is stale; pages on screen refetch what they show. */
export function markAllStale(): void {
  void queryClient.invalidateQueries({ queryKey: ["api"] });
}

/** Sign-in, sign-out, 401: forget everything. */
export function clearApiCache(): void {
  queryClient.cancelQueries();
  queryClient.clear();
}

const WRITE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/**
 * Whether a finished request should mark the cache stale: a successful write to the API,
 * except the auth calls (they clear the cache themselves), the live-stream ticket and previews.
 */
export function isCacheBustingWrite(method: string | undefined, url: string, ok: boolean): boolean {
  if (!ok || !WRITE_METHODS.has((method ?? "GET").toUpperCase())) return false;
  if (!url.includes("/api/")) return false;
  if (/\/api\/v1\/(auth\/|live\/stream-ticket)/.test(url)) return false;
  // Previews compute without saving (reassignment preview, import preview).
  return !/\/preview(\?|$)/.test(url);
}

export type LoadSpec = string | null | { path: string; staleTime?: number };

function specPath(spec: LoadSpec): string | null {
  return spec === null ? null : typeof spec === "string" ? spec : spec.path;
}

function specStale(spec: LoadSpec): number {
  return spec !== null && typeof spec === "object" && spec.staleTime !== undefined ? spec.staleTime : PAGE_STALE_MS;
}

/**
 * Stale-while-revalidate for a page's set of parallel GETs (null entries are skipped and give null).
 * - When every path has cached data, `apply(cached, true)` runs at once.
 * - Unless all of it is fresh, all paths are then read (fresh ones from the cache, stale ones from
 *   the server, in parallel) and `apply(results, false)` runs. A failed path gives its cached value,
 *   or null, and is logged.
 * - `force` skips the cache (a Refresh button). Returns whether cached data was applied first.
 */
export async function loadAll(
  specs: LoadSpec[],
  apply: (results: any[], fromCache: boolean) => void,
  opts: { force?: boolean } = {}
): Promise<boolean> {
  const paths = specs.map(specPath);
  let shown = false;
  if (!opts.force) {
    const cached = paths.map((p) => (p ? peekApi<any>(p) : null));
    if (cached.every((v) => v !== undefined)) {
      apply(cached, true);
      shown = true;
      if (specs.every((s, i) => !paths[i] || isFresh(paths[i] as string, specStale(s)))) return true;
    }
  }
  const results = await Promise.all(
    specs.map((s, i) => {
      const p = paths[i];
      if (!p) return null;
      const staleTime = opts.force ? 0 : isFresh(p, specStale(s)) ? specStale(s) : 0;
      return fetchApi<any>(p, { staleTime }).catch((err) => {
        console.error(`Failed to load ${p}`, err);
        return peekApi<any>(p) ?? null;
      });
    })
  );
  apply(results, false);
  return shown;
}

/**
 * A cached GET as a Response, for code written around `fetch` (`res.ok`, `res.json()`):
 * no request while the cached data is fresh. Errors come back as a non-ok Response.
 */
export async function cachedResponse(path: string, opts: CacheOptions = {}): Promise<Response> {
  try {
    const data = await fetchApi<unknown>(path, opts);
    return new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" } });
  } catch (err) {
    const status = err instanceof ApiError && err.status ? err.status : 500;
    const detail = err instanceof Error ? err.message : "Request failed";
    return new Response(JSON.stringify({ detail }), { status, headers: { "Content-Type": "application/json" } });
  }
}
