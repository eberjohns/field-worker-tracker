"""Replay the API calls the pages made and record server time per endpoint (Batch 9 step 1).

    FW_PERF_USER=PERFADMIN FW_PERF_PASSWORD=... \
      uv run --directory backend --group perf python ../tools/perf/measure_api.py

Input: the GET URLs ``measure_pages.py`` captured (``backend/storage/perf/replay-<host>.json``).
Each URL is called once to warm up, then ``--samples`` times in a row. Recorded per endpoint:
client time, server time, DB time, query count and most repeated statement (Server-Timing, when
PERF_TIMING_ENABLED is on), response bytes and the bytes gzip would send. p50/p95 are compared
with docs/14 (lists p95 < 300 ms, week view / roster p95 < 1.5 s).

Locally (not read-only) it also runs each report once for one month and records the heaviest;
the Reports page measurement uses that report, and so does the Render run. With ``--read-only``
no report is run: only the captured GET URLs are replayed.
"""

from __future__ import annotations

import argparse
import calendar
import gzip
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from perf_common import (  # noqa: E402
    ROOT,
    ReadOnlyClient,
    check_target,
    credentials,
    is_local,
    parse_server_timing,
    percentile,
    run_details,
    safe_path,
    wait_until_awake,
    write_json,
)

OUT_DIR = ROOT / "docs" / "reviews" / "perf-2026-11"
REPLAY_DIR = ROOT / "backend" / "storage" / "perf"
LIST_TARGET_MS = 300
WEEK_TARGET_MS = 1500


def target_ms(path: str) -> int:
    """docs/14: week view / roster p95 < 1.5 s, list endpoints p95 < 300 ms."""
    return WEEK_TARGET_MS if any(k in path for k in ("planner", "roster", "week", "coverage")) else LIST_TARGET_MS


def sample(client: ReadOnlyClient, url: str, samples: int, budget_s: float = 60.0) -> dict[str, Any] | None:
    t0 = time.perf_counter()
    first = client.request("GET", url)  # warm-up, not recorded
    if first is None:
        return None
    # A very slow endpoint gets fewer samples (at least 3): 20 x 77 s would take 25 minutes.
    warm_s = time.perf_counter() - t0
    samples = min(samples, max(3, int(budget_s / max(warm_s, 0.001))))
    rows: list[dict[str, Any]] = []
    for _ in range(samples):
        t0 = time.perf_counter()
        r = client.request("GET", url)
        if r is None:
            return None
        rows.append(
            {
                "client_ms": (time.perf_counter() - t0) * 1000,
                "status": r.status_code,
                "bytes": len(r.content),
                **parse_server_timing(r.headers.get("server-timing")),
            }
        )
    body = first.content

    def col(key: str) -> list[float]:
        return [float(x[key]) for x in rows if key in x]

    server = col("server_ms")
    path = safe_path(url)
    p95_basis = server or col("client_ms")
    return {
        "path": path,
        "query": "?" in url,
        "status": rows[-1]["status"],
        "samples": len(rows),
        "client_p50_ms": round(percentile(col("client_ms"), 0.5), 1),
        "client_p95_ms": round(percentile(col("client_ms"), 0.95), 1),
        "server_p50_ms": round(percentile(server, 0.5), 1) if server else None,
        "server_p95_ms": round(percentile(server, 0.95), 1) if server else None,
        "db_p50_ms": round(percentile(col("db_ms"), 0.5), 1) if col("db_ms") else None,
        "db_queries": int(statistics.median(col("db_queries"))) if col("db_queries") else None,
        "repeated_max": int(max(col("repeated_max"))) if col("repeated_max") else None,
        "bytes": len(body),
        "gzip_bytes": len(gzip.compress(body, 6)) if len(body) > 0 else 0,
        "target_ms": target_ms(path),
        "over_target": percentile(p95_basis, 0.95) > target_ms(path),
    }


def survey_reports(client: ReadOnlyClient, month: str) -> list[dict[str, Any]]:
    """Run every report once for the month (local only) and rank them by server time."""
    year, mon = (int(x) for x in month.split("-"))
    last = calendar.monthrange(year, mon)[1]
    params = f"date_from={year}-{mon:02d}-01&date_to={year}-{mon:02d}-{last:02d}&year={year}&month={mon}&country=AE"
    catalog = client.request("GET", "/api/v1/reports")
    out: list[dict[str, Any]] = []
    for rep in catalog.json() if catalog is not None and catalog.status_code == 200 else []:
        t0 = time.perf_counter()
        r = client.request("GET", f"/api/v1/reports/{rep['key']}?{params}")
        if r is None:
            continue
        timing = parse_server_timing(r.headers.get("server-timing"))
        total_rows = page_rows = None
        try:
            body = r.json()
            total_rows, page_rows = body.get("total_rows"), len(body.get("data", []))
        except (ValueError, AttributeError):
            pass
        out.append(
            {
                "key": rep["key"],
                "name": rep.get("name"),
                "status": r.status_code,
                "client_ms": round((time.perf_counter() - t0) * 1000, 1),
                "total_rows": total_rows,
                "page_rows": page_rows,
                "bytes": len(r.content),
                **timing,
            }
        )
    out.sort(key=lambda x: x.get("server_ms", x["client_ms"]), reverse=True)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--api-url", default="http://localhost:8000")
    p.add_argument("--read-only", action="store_true", help="replay GETs only; run no reports")
    p.add_argument("--region", default="local")
    p.add_argument("--network", default="local (same machine)")
    p.add_argument("--samples", type=int, default=20)
    p.add_argument("--budget-s", type=float, default=60.0, help="per endpoint; slow ones get fewer samples (min 3)")
    p.add_argument("--replay", default=None, help="replay file (default: from measure_pages.py)")
    p.add_argument("--report-month", default="2026-10")
    p.add_argument(
        "--reports-only",
        action="store_true",
        help="local only: just pick the heaviest report (run before measure_pages.py)",
    )
    p.add_argument("--pages", default=None, help="only replay these pages' URLs (comma list)")
    p.add_argument(
        "--merge",
        action="store_true",
        help="continue an earlier run: keep its endpoints and report survey, skip URLs already measured",
    )
    p.add_argument("--out", default=None)
    args = p.parse_args()

    api_url = args.api_url.rstrip("/")
    check_target([api_url], args.read_only)
    user, password = credentials()
    details = run_details(api_url, api_url, args.region, args.network, args.read_only)
    if not is_local(api_url):
        details["health_wait_s"] = round(wait_until_awake(api_url), 1)

    if args.reports_only and args.read_only:
        raise SystemExit("--reports-only runs reports, so it cannot be combined with --read-only.")
    replay_path = Path(args.replay) if args.replay else REPLAY_DIR / f"replay-{details['api_host']}.json"
    replay: dict[str, list[str]] = {} if args.reports_only else json.loads(replay_path.read_text(encoding="utf-8"))
    client = ReadOnlyClient(api_url, args.read_only)
    token = client.login(user, password)["access_token"]

    out = (ROOT / args.out) if args.out else OUT_DIR / f"api-{details['api_host']}.json"
    # Measured rows by real URL, so --merge can continue a stopped run. Local and git-ignored
    # (the URLs hold ids); the committed output has safe paths only.
    progress_path = REPLAY_DIR / f"api-progress-{details['api_host']}.json"
    previous: dict[str, Any] = (_load_json(out) or {}) if args.merge else {}
    seen: dict[str, dict[str, Any]] = (_load_json(progress_path) or {}) if args.merge else {}
    # Drop rows for URLs the latest page run no longer makes (e.g. a page measured again).
    current = {url for urls in replay.values() for url in urls}
    seen = {url: row for url, row in seen.items() if url in current}
    results: dict[str, Any] = {"run": previous.get("run", details), "endpoints": []}
    if previous:
        results["batches"] = [*previous.get("batches", []), details]
    secrets = [password, token]

    def save() -> None:
        results["endpoints"] = sorted(seen.values(), key=lambda r: -(r["server_p95_ms"] or r["client_p95_ms"]))
        results["skipped"] = [*previous.get("skipped", []), *client.skipped]
        write_json(out, results, secrets)
        write_json(progress_path, seen, secrets)

    if "reports_survey" in previous:
        results["reports_survey"] = previous["reports_survey"]
        results["heaviest_report"] = previous.get("heaviest_report")
    elif not args.read_only:
        survey = survey_reports(client, args.report_month)
        results["reports_survey"] = survey
        heaviest = next((r for r in survey if r["status"] == 200), None)
        results["heaviest_report"] = heaviest
        if heaviest:
            print(f"Heaviest report: {heaviest['key']} ({heaviest.get('server_ms', heaviest['client_ms'])} ms)")
        save()

    wanted = set(args.pages.split(",")) if args.pages else None
    for page, urls in replay.items():
        if wanted is not None and page.removesuffix("_run") not in wanted:  # "reports_run" goes with "reports"
            continue
        for url in dict.fromkeys(urls):
            if url in seen:
                if page not in seen[url]["pages"]:
                    seen[url]["pages"].append(page)
                continue
            row = sample(client, url, args.samples, args.budget_s)
            if row is None:
                continue
            row["pages"] = [page]
            seen[url] = row
            save()
            print(
                f"{row['server_p95_ms'] or row['client_p95_ms']:>9} ms p95  {row['db_queries'] or '-':>5} q  "
                f"{row['samples']:>2} x  {row['bytes']:>9,} B  {row['path']}",
                flush=True,
            )
    save()
    client.close()
    print(f"Wrote {out}")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


if __name__ == "__main__":
    main()
