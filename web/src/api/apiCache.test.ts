import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";
import {
  cachedResponse,
  clearApiCache,
  fetchApi,
  isCacheBustingWrite,
  loadAll,
  loadApi,
  markAllStale,
  peekApi,
  queryClient,
  apiKey,
} from "./apiCache";

// A fake server: counts requests per path and answers with { path, n }.
let calls: Record<string, number> = {};
let failing = new Set<string>();

function installFetch() {
  calls = {};
  failing = new Set();
  (globalThis as any).localStorage = { getItem: () => "t0k", setItem() {}, removeItem() {} };
  (globalThis as any).fetch = async (path: string) => {
    calls[path] = (calls[path] ?? 0) + 1;
    if (failing.has(path)) {
      return new Response(JSON.stringify({ detail: "Boom" }), { status: 500 });
    }
    return new Response(JSON.stringify({ path, n: calls[path] }), { status: 200 });
  };
}

/** Make a cached entry old enough to be stale. */
function age(path: string, ms: number) {
  const q = queryClient.getQueryCache().find({ queryKey: apiKey(path) });
  assert.ok(q, `no cache entry for ${path}`);
  q.setState({ dataUpdatedAt: Date.now() - ms });
}

describe("apiCache", () => {
  beforeEach(() => {
    clearApiCache();
    installFetch();
  });

  it("fetchApi serves fresh data from the cache, one request per path", async () => {
    const a = await fetchApi<any>("/api/v1/x");
    const b = await fetchApi<any>("/api/v1/x");
    assert.equal(a.n, 1);
    assert.deepEqual(b, a);
    assert.equal(calls["/api/v1/x"], 1);
    const c = await fetchApi<any>("/api/v1/x", { force: true });
    assert.equal(c.n, 2);
  });

  it("loadApi shows cached data at once and refreshes it when stale", async () => {
    await fetchApi("/api/v1/y");
    age("/api/v1/y", 60_000);
    const seen: [number, boolean][] = [];
    const shown = await loadApi<any>("/api/v1/y", (d, fromCache) => seen.push([d.n, fromCache]));
    assert.equal(shown, true);
    assert.deepEqual(seen, [
      [1, true],
      [2, false],
    ]);
  });

  it("loadApi does not refetch fresh data", async () => {
    await fetchApi("/api/v1/z");
    const seen: number[] = [];
    await loadApi<any>("/api/v1/z", (d) => seen.push(d.n));
    assert.deepEqual(seen, [1]);
    assert.equal(calls["/api/v1/z"], 1);
  });

  it("a write marks everything stale; the next read refetches", async () => {
    await fetchApi("/api/v1/a");
    markAllStale();
    const seen: number[] = [];
    await loadApi<any>("/api/v1/a", (d) => seen.push(d.n));
    assert.deepEqual(seen, [1, 2]);
  });

  it("clearApiCache forgets everything (sign-in, sign-out, 401)", async () => {
    await fetchApi("/api/v1/b");
    clearApiCache();
    assert.equal(peekApi("/api/v1/b"), undefined);
  });

  it("loadAll applies the cache only when every path is cached, and skips null paths", async () => {
    await fetchApi("/api/v1/p1");
    const runs: [any[], boolean][] = [];
    await loadAll(["/api/v1/p1", null, "/api/v1/p2"], (r, c) => runs.push([r, c]));
    // p2 was not cached: no cached pass, one network pass (p1 still fresh, served from cache).
    assert.equal(runs.length, 1);
    assert.equal(runs[0][1], false);
    assert.equal(runs[0][0][1], null);
    assert.equal(calls["/api/v1/p1"], 1);
    assert.equal(calls["/api/v1/p2"], 1);
    // Both cached and fresh now: one cached pass, no requests.
    runs.length = 0;
    await loadAll(["/api/v1/p1", "/api/v1/p2"], (r, c) => runs.push([r, c]));
    assert.equal(runs.length, 1);
    assert.equal(runs[0][1], true);
    assert.equal(calls["/api/v1/p1"], 1);
  });

  it("loadAll gives null (or the cached value) for a failed path and keeps the others", async () => {
    failing.add("/api/v1/bad");
    let result: any[] = [];
    await loadAll(["/api/v1/ok", "/api/v1/bad"], (r) => (result = r));
    assert.equal(result[0].n, 1);
    assert.equal(result[1], null);
  });

  it("cachedResponse looks like fetch: ok + json, or a non-ok Response on errors", async () => {
    const ok = await cachedResponse("/api/v1/r");
    assert.equal(ok.ok, true);
    assert.equal((await ok.json()).n, 1);
    failing.add("/api/v1/e");
    const bad = await cachedResponse("/api/v1/e");
    assert.equal(bad.ok, false);
    assert.equal(bad.status, 500);
  });

  it("isCacheBustingWrite: successful API writes only, not auth, stream tickets or previews", () => {
    assert.equal(isCacheBustingWrite("POST", "/api/v1/leave-requests", true), true);
    assert.equal(isCacheBustingWrite("delete", "/api/v1/holidays/1", true), true);
    assert.equal(isCacheBustingWrite("POST", "/api/v1/leave-requests", false), false);
    assert.equal(isCacheBustingWrite("GET", "/api/v1/worksites", true), false);
    assert.equal(isCacheBustingWrite(undefined, "/api/v1/worksites", true), false);
    assert.equal(isCacheBustingWrite("POST", "/api/v1/auth/login", true), false);
    assert.equal(isCacheBustingWrite("POST", "/api/v1/live/stream-ticket", true), false);
    assert.equal(isCacheBustingWrite("POST", "/api/v1/map-usage", true), false);
    assert.equal(isCacheBustingWrite("POST", "/api/v1/reassignment-requests/preview", true), false);
    assert.equal(isCacheBustingWrite("POST", "/api/v1/imports/1/preview?x=1", true), false);
    assert.equal(isCacheBustingWrite("POST", "https://tiles.example/x", true), false);
  });
});
