"""Load the web app's pages in Chromium and record what each costs (Batch 9 step 1).

Needs the ``perf`` dependency group and a one-time browser download:

    uv run --directory backend --group perf playwright install chromium
    FW_PERF_USER=PERFADMIN FW_PERF_PASSWORD=... \
      uv run --directory backend --group perf python ../tools/perf/measure_pages.py

Per page, each run loads it **cold** (a new browser context: empty cache, fresh app) and then
**warm** (leave to another page inside the app and come back, as a user does). Before the runs,
each page is loaded once unrecorded. Recorded per load:

- requests: API (fetch/xhr under /api/) and static, counted apart
- chain depth: 1 + the deepest chain of API requests where each starts after an earlier one ended
- bytes: transferred (encoded) and, for the API, decoded
- the slowest API request with its server time and query count (from Server-Timing, if enabled)
- time to usable: the page's API calls have been quiet for 500 ms, no loading spinner
  (``.animate-spin``) is visible and the page's own marker (if any) is visible. The time is when
  that state began, not including the 500 ms.

Read-only rules (see perf_common.py): a non-local URL needs ``--read-only``; then only GET requests
(plus the login) leave the browser and the rest are aborted and listed as skipped.
"""

from __future__ import annotations

import argparse
import calendar
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from perf_common import (  # noqa: E402
    ROOT,
    ReadOnlyClient,
    allowed,
    check_target,
    credentials,
    is_local,
    parse_server_timing,
    run_details,
    safe_path,
    wait_until_awake,
    write_json,
)

OUT_DIR = ROOT / "docs" / "reviews" / "perf-2026-11"
# Real URLs (with ids and query strings) for measure_api.py: git-ignored, never committed.
REPLAY_DIR = ROOT / "backend" / "storage" / "perf"
QUIET_MS = 500
TIMEOUT_MS = 120_000
# A visible loading spinner, except decorative ones whose label contains one of the given texts.
SPINNER_JS = (
    "ignore => Array.from(document.querySelectorAll('.animate-spin'))"
    ".some(e => (e.offsetParent !== null || e.getClientRects().length > 0)"
    " && !ignore.some(t => (e.parentElement?.textContent || '').includes(t)))"
)
SPA_NAVIGATE_JS = (
    "p => { window.history.pushState({}, '', p); window.dispatchEvent(new PopStateEvent('popstate', { state: {} })); }"
)


@dataclass
class PageSpec:
    key: str
    path: str
    marker: str | None = None  # a selector that must be visible
    away: str = "/"  # where the warm run leaves to before coming back
    # Spinners that are not loading: the Live Map's polling badge always spins (and on a read-only
    # run the page always polls, because the stream-ticket POST is blocked).
    ignore_spinners: tuple[str, ...] = ()


PAGES = [
    PageSpec("dashboard", "/", away="/worksites"),
    PageSpec("worksites", "/worksites", marker="table tbody tr"),
    PageSpec("worksite_detail", "/worksites/{worksite_id}"),
    # Batch 9 step 2: the Schedule tab loads the month in view only.
    PageSpec("worksite_schedule", "/worksites/{worksite_id}?tab=schedule"),
    PageSpec("base_planner", "/base-planner"),
    PageSpec("operational_planner", "/operational-planner"),
    PageSpec("employees", "/employees", marker="table tbody tr"),
    PageSpec("attendance", "/attendance"),
    PageSpec("live_map", "/live", ignore_spinners=("Refreshing every",)),
    PageSpec("reports", "/reports"),
    # Batch 9 step 2: the inbox page fetches one page of the active tab.
    PageSpec("approvals", "/approvals"),
]


@dataclass
class Tracker:
    """Network activity of one page load (handlers only count; details are read afterwards)."""

    t0_epoch_ms: float = 0.0
    t0: float = 0.0
    requests: list[Any] = field(default_factory=list)
    inflight_api: int = 0
    api_started: int = 0
    last_api_ms: float = 0.0
    skipped: list[dict[str, str]] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)  # where the run was, for error messages

    def step(self, name: str) -> None:
        self.steps.append(f"{name}@{self.now_ms():.0f}ms")

    def now_ms(self) -> float:
        return (time.monotonic() - self.t0) * 1000

    def reset(self) -> None:
        self.t0_epoch_ms = time.time() * 1000
        self.t0 = time.monotonic()
        self.requests = []
        self.inflight_api = 0
        self.api_started = 0
        self.last_api_ms = 0.0


def is_api(request: Any) -> bool:
    return "/api/" in request.url and request.resource_type in ("fetch", "xhr")


def attach(page: Any, tracker: Tracker) -> None:
    def on_request(request: Any) -> None:
        tracker.requests.append(request)
        if is_api(request):
            tracker.inflight_api += 1
            tracker.api_started += 1
            tracker.last_api_ms = tracker.now_ms()

    def on_done(request: Any) -> None:
        if is_api(request):
            tracker.inflight_api = max(0, tracker.inflight_api - 1)
            tracker.last_api_ms = tracker.now_ms()

    page.on("request", on_request)
    page.on("requestfinished", on_done)
    page.on("requestfailed", on_done)
    page.on("crash", lambda _p: tracker.step("RENDERER CRASHED"))


def install_guard(context: Any, read_only: bool, tracker: Tracker) -> None:
    """Abort anything but reads in read-only mode, before it is sent (always installed, so local
    and read-only runs behave the same)."""

    def handle(route: Any) -> None:
        req = route.request
        if allowed(req.method, urlparse(req.url).path, read_only):
            route.continue_()
        else:
            tracker.skipped.append({"method": req.method, "path": safe_path(req.url), "reason": "read-only"})
            route.abort()

    context.route("**/*", handle)


def wait_usable(page: Any, tracker: Tracker, marker: str | None, ignore_spinners: tuple[str, ...] = ()) -> float:
    """Wait for the usable state; return when it began (ms after navigation start)."""
    deadline = time.monotonic() + TIMEOUT_MS / 1000
    marker_ms = 0.0
    if marker:
        page.wait_for_selector(marker, state="visible", timeout=TIMEOUT_MS)
        marker_ms = tracker.now_ms()
    last_busy = 0.0
    while time.monotonic() < deadline:
        busy = tracker.inflight_api > 0 or bool(page.evaluate(SPINNER_JS, list(ignore_spinners)))
        now = tracker.now_ms()
        if busy:
            last_busy = now
        quiet_since = max(tracker.last_api_ms, last_busy)
        if not busy and now - quiet_since >= QUIET_MS and now >= 1000:
            return max(marker_ms, quiet_since)
        page.wait_for_timeout(50)
    raise TimeoutError("page did not become usable in time")


def summarize(tracker: Tracker, usable_ms: float) -> dict[str, Any]:
    """Read sizes, timings and Server-Timing from the finished requests."""
    api: list[dict[str, Any]] = []
    static_count, static_bytes, api_bytes, api_decoded = 0, 0, 0, 0
    for req in tracker.requests:
        if req.resource_type in ("eventsource", "websocket"):
            # Never finishes: sizes() would wait for its end while the stream keeps buffering.
            continue
        timing = req.timing or {}
        start = (timing.get("startTime", 0) or 0) - tracker.t0_epoch_ms
        end_rel = timing.get("responseEnd", -1)
        end = start + end_rel if end_rel and end_rel > 0 else None
        try:
            sizes = req.sizes()
            encoded = int(sizes.get("responseBodySize", 0)) + int(sizes.get("responseHeadersSize", 0))
        except Exception:  # aborted or cached without sizes
            encoded = 0
        if is_api(req):
            resp = req.response()
            entry: dict[str, Any] = {
                "method": req.method,
                "path": safe_path(req.url),
                "status": resp.status if resp else None,
                "start_ms": round(start, 1),
                "end_ms": round(end, 1) if end is not None else None,
                "duration_ms": round(end_rel, 1) if end_rel and end_rel > 0 else None,
                "transfer_bytes": encoded,
            }
            if resp:
                try:
                    entry["decoded_bytes"] = len(resp.body())
                except Exception:
                    entry["decoded_bytes"] = None
                entry.update(parse_server_timing(resp.headers.get("server-timing")))
            api.append(entry)
            api_bytes += encoded
            api_decoded += entry.get("decoded_bytes") or 0
        else:
            static_count += 1
            static_bytes += encoded

    depth: dict[int, int] = {}
    ordered = sorted(range(len(api)), key=lambda i: api[i]["start_ms"])
    for i in ordered:
        before = [
            depth[j]
            for j in ordered
            if j in depth and api[j]["end_ms"] is not None and api[j]["end_ms"] <= api[i]["start_ms"]
        ]
        depth[i] = 1 + max(before, default=0)
    slowest = max(api, key=lambda e: e.get("duration_ms") or 0, default=None)
    return {
        "usable_ms": round(usable_ms, 1),
        "api_requests": len(api),
        "static_requests": static_count,
        "chain_depth": max(depth.values(), default=0),
        "api_transfer_bytes": api_bytes,
        "api_decoded_bytes": api_decoded,
        "static_transfer_bytes": static_bytes,
        "slowest": slowest,
        "api": api,
    }


def measure_load(page: Any, tracker: Tracker, base: str, spec: PageSpec, path: str, warm: bool) -> dict[str, Any]:
    if warm:
        tracker.reset()
        page.evaluate(SPA_NAVIGATE_JS, path)
    else:
        tracker.reset()
        page.goto(base + path, wait_until="commit", timeout=TIMEOUT_MS)
    tracker.step("warm-nav" if warm else "goto")
    usable = wait_usable(page, tracker, spec.marker, spec.ignore_spinners)
    tracker.step("usable")
    result = summarize(tracker, usable)
    tracker.step("summarized")
    return result


def captured_gets(tracker: Tracker) -> list[str]:
    """The GET API URLs of this load, as path + query, for measure_api.py to replay."""
    out: list[str] = []
    for req in tracker.requests:
        if is_api(req) and req.method == "GET":
            u = urlparse(req.url)
            out.append(u.path + (f"?{u.query}" if u.query else ""))
    return out


def run_report(page: Any, tracker: Tracker, report_name: str, month: tuple[date, date]) -> dict[str, Any]:
    """In the Reports hub: pick the report, set the date range, Run Preview, wait for the table."""
    page.get_by_role("button", name=report_name).first.click()
    # Date-range reports show two date inputs; monthly ones (job-costing, payroll, ...) show
    # Year and Month dropdowns instead.
    dates = page.locator("input[type=date]")
    if dates.count() >= 2:
        dates.nth(0).fill(month[0].isoformat())
        dates.nth(1).fill(month[1].isoformat())
    for label, value in (("Year", month[0].year), ("Month", month[0].month)):
        select = page.locator(f"div:has(> label:text-is('{label}')) > select")
        if select.count():
            select.first.select_option(str(value))
    tracker.reset()
    page.get_by_role("button", name="Run Preview").click()
    usable = wait_usable(page, tracker, "table tbody tr")
    return summarize(tracker, usable)


def median_of(loads: list[dict[str, Any]]) -> dict[str, Any]:
    keys = (
        "usable_ms",
        "api_requests",
        "static_requests",
        "chain_depth",
        "api_transfer_bytes",
        "api_decoded_bytes",
        "static_transfer_bytes",
    )
    out: dict[str, Any] = {k: statistics.median(load[k] for load in loads) for k in keys}
    mid = sorted(loads, key=lambda load: load["usable_ms"])[len(loads) // 2]
    out["slowest"] = mid["slowest"]
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base-url", default="http://localhost:4173", help="the web app (vite preview locally)")
    p.add_argument("--api-url", default=None, help="the API, if on another host (default: --base-url)")
    p.add_argument("--read-only", action="store_true", help="send only GET requests (and the login)")
    p.add_argument("--region", default="local", help="hosting region of --base-url")
    p.add_argument("--network", default="local (same machine)", help="the client's network")
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--pages", default=",".join(s.key for s in PAGES))
    p.add_argument("--worksite", default=None, help="job number for the worksite page (default: first)")
    p.add_argument("--report", default=None, help="report key for the Reports page (default: from the local API run)")
    p.add_argument("--report-month", default="2026-10", help="YYYY-MM for the report's date range")
    p.add_argument("--out", default=None)
    p.add_argument("--merge", action="store_true", help="add these pages to the existing output file")
    p.add_argument("--headed", action="store_true")
    args = p.parse_args()

    base = args.base_url.rstrip("/")
    api_url = (args.api_url or args.base_url).rstrip("/")
    check_target([base, api_url], args.read_only)
    user, password = credentials()
    details = run_details(base, api_url, args.region, args.network, args.read_only)
    if not is_local(api_url):
        details["health_wait_s"] = round(wait_until_awake(api_url), 1)

    client = ReadOnlyClient(api_url, args.read_only)
    login = client.login(user, password)
    token = login["access_token"]
    sites = client.request("GET", "/api/v1/worksites")
    site_list = sorted(
        sites.json() if sites is not None and sites.status_code == 200 else [], key=lambda s: s["job_number"]
    )
    site = next((s for s in site_list if s["job_number"] == args.worksite), site_list[0] if site_list else None)
    report_key = args.report or _local_heaviest_report()
    reports = client.request("GET", "/api/v1/reports")
    names = {
        r["key"]: r["name"] for r in (reports.json() if reports is not None and reports.status_code == 200 else [])
    }
    year, month = (int(x) for x in args.report_month.split("-"))
    first = date(year, month, 1)
    last = date(year, month, calendar.monthrange(year, month)[1])
    client.close()

    init_script = (
        "localStorage.setItem('fwt_token', " + json.dumps(token) + ");"
        "localStorage.setItem('fwt_user', " + json.dumps(json.dumps(login["user"], default=str)) + ");"
    )
    wanted = [s for s in PAGES if s.key in set(args.pages.split(","))]
    out = (ROOT / args.out) if args.out else OUT_DIR / f"pages-{details['host']}.json"
    replay_out = REPLAY_DIR / f"replay-{details['api_host']}.json"
    results: dict[str, Any] = {"run": details, "pages": {}, "skipped": []}
    replay: dict[str, list[str]] = {}
    if args.merge:
        # Add these pages to an earlier run's file (e.g. pages measured in smaller batches).
        results = _load_json(out) or results
        results.setdefault("batches", []).append(details)
        replay = _load_json(replay_out) or replay

    def save() -> None:
        # After every page, so a stopped run keeps the pages it finished.
        seen: set[tuple[str, str]] = set()
        results["skipped"] = [
            s
            for s in results["skipped"]
            if (s["method"], s["path"]) not in seen and not seen.add((s["method"], s["path"]))
        ]
        write_json(out, results, [password, token])
        write_json(replay_out, replay, [password, token])

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        for spec in wanted:
            path = spec.path.replace("{worksite_id}", str(site["id"]) if site else "")
            if "{" in spec.path and not site:
                results["pages"][spec.key] = {"error": "no worksite"}
                continue
            loads: dict[str, list[dict[str, Any]]] = {"cold": [], "warm": []}
            report_runs: list[dict[str, Any]] = []
            for n in range(args.runs + 1):  # run 0 is the unrecorded warm-up
                tracker = Tracker()
                context = browser.new_context(viewport={"width": 1440, "height": 900})
                context.add_init_script(init_script)
                install_guard(context, args.read_only, tracker)
                page = context.new_page()
                attach(page, tracker)
                try:
                    cold = measure_load(page, tracker, base, spec, path, warm=False)
                    if n == 1:
                        replay[spec.key] = captured_gets(tracker)
                    if spec.key == "reports" and report_key and report_key in names:
                        report = run_report(page, tracker, names[report_key], (first, last))
                        if n:
                            report_runs.append(report)
                        if n == 1:
                            replay["reports_run"] = captured_gets(tracker)
                    away = spec.away if spec.away != path else "/worksites"
                    tracker.reset()
                    tracker.step("away")
                    page.evaluate(SPA_NAVIGATE_JS, away)
                    wait_usable(page, tracker, None)
                    tracker.step("away-usable")
                    warm = measure_load(page, tracker, base, spec, path, warm=True)
                    if n:
                        loads["cold"].append(cold)
                        loads["warm"].append(warm)
                except Exception as exc:
                    results["pages"].setdefault(spec.key, {}).setdefault("errors", []).append(
                        f"run {n}: {type(exc).__name__}: {str(exc).splitlines()[0][:200]}"
                        f" (steps: {', '.join(tracker.steps[-6:])})"
                    )
                finally:
                    results["skipped"].extend(tracker.skipped)
                    context.close()
            entry = results["pages"].setdefault(spec.key, {})
            entry["path"] = safe_path(spec.path.replace("{worksite_id}", "{id}"))
            for kind, runs in loads.items():
                if runs:
                    entry[kind] = median_of(runs)
                    entry[f"{kind}_runs"] = runs
            if report_runs:
                entry["report"] = {"key": report_key, "month": args.report_month, **median_of(report_runs)}
            print(
                f"{spec.key:22} cold {entry.get('cold', {}).get('usable_ms', '-'):>8} ms   "
                f"warm {entry.get('warm', {}).get('usable_ms', '-'):>8} ms",
                flush=True,
            )
            save()
        browser.close()

    save()
    print(f"Wrote {out} (and the replay list under {REPLAY_DIR})")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _local_heaviest_report() -> str | None:
    """The report measure_api.py picked locally (the Render run reuses it)."""
    path = OUT_DIR / "api-localhost.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("heaviest_report", {}).get("key")
    except (OSError, ValueError):
        return None


if __name__ == "__main__":
    main()
