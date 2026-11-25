# Runbook 06: Performance measurement (Batch 9)

How to rebuild the measuring dataset and measure the web app's pages and API, locally and on a deployed site. Step 1 of Batch 9 used this to produce `docs/reviews/performance-baseline-2026-11.md`. Re-run it after steps 2–4 for the report's "after" column.

## What there is

| Piece | What it does |
|---|---|
| `PERF_TIMING_ENABLED` (backend setting) | Each response gets a `Server-Timing` header (`app`, `db` time with query count, `dbrepeat` = how often the most repeated statement ran), and each request writes one `request_timing` log line: the route template (no ids), status, duration, queries, DB time, repeats and statements slower than `PERF_SLOW_QUERY_MS` (SQL text only, never values). Off by default. Ignored when `APP_ENV=production`. |
| `tools/perf/seed_perf_dataset.py` | Builds the scaled **mock** dataset in a separate local database `fw_perf`. |
| `tools/perf/run_api.py` | Starts the API on `fw_perf` with timing on, on port 8000 (refuses if the port is taken). If 8000 is busy with another API, set `FW_PERF_API_PORT` (for example 8020) and point the preview's `/api` proxy at that port. |
| `tools/perf/measure_pages.py` | Loads the 9 pages in Chromium (Playwright), cold and warm, and records requests, chain depth, bytes, the slowest endpoint and time to usable. |
| `tools/perf/measure_api.py` | Replays the API calls the pages made (20 samples each) for p50/p95, and locally picks the heaviest report. |

Outputs go to `docs/reviews/perf-2026-11/` (`pages-<host>.json`, `api-<host>.json`). URLs there have no query strings and ids are `{id}`. The real URLs for replay go to `backend/storage/perf/` (git-ignored).

## The dataset (local only)

```sh
docker compose up -d db                       # the repo-root compose file
uv run --directory backend python ../tools/perf/seed_perf_dataset.py --recreate
```

**Safety:**
- The script refuses any database not named `*_perf`, any non-local host, and `APP_ENV=production`.
- `fw_db` and `fw_test` are never touched.
- Report files land in `backend/storage/perf/`.

**Contents:** 600 employees (570 workers, 25 supervisors, 5 engineers), 400 worksites (10% SA), 1,500 job items and their occurrences. All of it is mock: "Perf Worker 0001", Tally IDs `PF00001…`. Activity starts on 2026-09-01:
- standing assignments, base roster templates and scheduled work, to 13 months ahead like the app materialises;
- attendance, site visits and phone events, to yesterday;
- 5-minute pings for the last 7 days and today;
- one October payroll draft.

**What goes through the app:**
- through the app's own code: occurrences, the attendance values (the pure engine) and the payroll draft;
- bulk-inserted: master data, scheduled work, attendance rows, site visits and events. The event pipeline would take hours at this size, so these rows are realistic in shape and count but are not pipeline output.

Takes about 5 minutes (`--scale 0.05` for a quick small run).

**Login:**
- `PERFADMIN`, with the password in `FW_PERF_ADMIN_PASSWORD`, else the local default in the script;
- supervisors and engineers log in with their Tally ID and the same password.

## Measure locally

```sh
uv run --directory backend --group perf playwright install chromium   # once
uv run --directory backend python ../tools/perf/run_api.py > backend/storage/perf/api-timing.log &
(cd web && pnpm run build && pnpm exec vite preview --port 4173 --strictPort) &

export FW_PERF_USER=PERFADMIN FW_PERF_PASSWORD=...        # the login is read from these only
uv run --directory backend --group perf python ../tools/perf/measure_api.py --reports-only
uv run --directory backend --group perf python ../tools/perf/measure_pages.py
uv run --directory backend --group perf python ../tools/perf/measure_api.py
```

The order matters:
1. `--reports-only` picks the heaviest report.
2. The page run uses that report and captures the URLs.
3. The last run replays them.

`api-timing.log` holds a `request_timing` line per request.

## Measure a deployed site (Render)

Always use `--read-only`; both scripts refuse a non-local URL without it.

In read-only mode:
- only GET requests leave the client, plus the login POST;
- anything else is blocked before it is sent and listed under `skipped` (for example the live map's stream ticket);
- `measure_api.py` runs no reports: it replays only the GET URLs the page run captured.

The Reports page uses the report picked locally. The scripts read it from `docs/reviews/perf-2026-11/api-localhost.json`, or you pass it with `--report`.

1. If the deployment's `APP_ENV` is not production, set `PERF_TIMING_ENABLED=true` on the API service so the server-side columns are filled. With production, they stay empty and only the browser numbers are recorded.
2. Run with your own login, in your own terminal (with `!` from Claude Code):

```sh
export FW_PERF_USER=... FW_PERF_PASSWORD=...
uv run --directory backend --group perf python ../tools/perf/measure_pages.py \
  --base-url https://<web host> --api-url https://<api host> --read-only \
  --region "<hosting region>" --network "home broadband Kerala"
uv run --directory backend --group perf python ../tools/perf/measure_api.py \
  --api-url https://<api host> --read-only --region "<hosting region>" --network "home broadband Kerala"
```

**Before measuring:**
- Both scripts first wait until `/health` answers in under 2 s, because Render sleeps when idle.
- Each page is loaded once without recording.

**Recorded with the results:** the host, the region, the network and the start time with time zone. Credentials and tokens are never written; the scripts refuse to write output that contains them.

3. Send back `docs/reviews/perf-2026-11/pages-<host>.json` and `api-<host>.json`; they hold paths and timings only.

## Definitions

- **Cold:** a new browser context (empty cache, fresh login state), then a full page load.
- **Warm:** in the same tab, leave to another page inside the app and come back, as a user does. Today this refetches everything, because nothing is cached.
- **Time to usable:** the page's API calls have been quiet for 500 ms, no loading spinner (`.animate-spin`) is visible, and the page's marker is visible (a table row on list pages). The time is when that state began, not including the 500 ms.
- **Chain depth:** 1 + the deepest chain of API requests where each starts only after an earlier one finished (waterfalls).
- **Targets (docs/14):** list endpoints p95 < 300 ms; week view or roster p95 < 1.5 s.
