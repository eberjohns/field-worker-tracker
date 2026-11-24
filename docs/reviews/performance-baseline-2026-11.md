# Performance baseline (Batch 9 step 1) and after step 2, November 2026

Measured 24 Nov 2026 on the code of `perf/batch9-measure`. That is v1.17.0, which includes #32, #33 and #34, plus the step 1 tooling. There are no speed fixes in this step.

**Where the numbers come from:**
- `docs/reviews/perf-2026-11/pages-localhost.json`: page loads in Chromium.
- `docs/reviews/perf-2026-11/api-localhost.json`: endpoint replay and the report survey.
- the API's `request_timing` log, for slow SQL and repeats.

`docs/runbooks/06-performance-measurement.md` describes how to measure and how to re-run.

**Render:** pending, owner run. The Render columns below stay empty until the owner runs both scripts with `--read-only` (runbook 06).

**After step 2:** measured 24 Nov 2026 on `perf/batch9-quickwins` (v1.19.0), same machine, same `fw_perf` dataset and the same scripts, one page per process. The result files are in `docs/reviews/perf-2026-11/after-step2/`; their `app_version` says 1.18.0 because the version is bumped by the commit, after measuring. The "After step 2" columns and the section [After step 2](#after-step-2-local) hold the new numbers.

## Summary

- **Every page is slow on first load, even locally:** 5.9 s to 81 s. On 7 of the 9 pages, almost all of that time is one call: the app shell loads the full approvals inbox, 9.8 MB, just to show a badge count.
- **The two planners are slow on every visit:** Base Planner 19 s, Operational Planner 70–81 s.
  - Loading a worksite also loads all its job items and all their occurrences, 13 months ahead: 339,300 rows here.
  - The planners make one settings query per worksite: 400 queries.
- **One slow request holds up the others.** The API does heavy Python work on a single event loop, so requests that start together finish one after another. In the Operational Planner, three calls that take 5–19 s each on their own took 48–78 s together.
- **Missed targets** (docs/14 and the addendum):
  - 6 endpoints are over their target.
  - The week view and the roster take 14.3 s and 12.2 s at p95, against 1.5 s.
  - Two pages have request chains 3 deep, against a maximum of 2.
- **Nothing is cached in the browser, and nothing is compressed.** Responses are sent at full size: 9.8 MB where gzip would send 1.6 MB, and 4.2 MB where it would send 127 KB. The local numbers don't show the cost of the network; the Render run will.

## After step 2 (local)

**What step 2 changed:**
1. The badge and the Dashboard use `GET /approvals/counts` (count queries only). The inbox is fetched only on the Approvals page, one tab and one page (50) at a time.
2. Occurrences are no longer loaded with job items (`lazy="select"`); the worksite list loads neither items nor supervisors. The Schedule tab fetches only the month in view from `GET /worksites/{id}/occurrences`.
3. The planners read settings and holidays once per country; Base Planner, coverage and roster are limited to the user's worksites (DEC-57); coverage loads only the week's shifts of the items in view (the wide period only for monthly or quarterly items); `get_staffing_gaps` runs a fixed number of queries.
4. GZip for responses of 1 KB or more (not for the SSE stream, PDF or xlsx).
5. The Dashboard fires its calls together.

**Targets:**

| Target | Baseline | After step 2 | Met |
|---|---:|---:|---|
| Operational Planner week view < 3 s (owner) | 80.8 s cold / 70.3 s warm | 1.4 s / 1.4 s | yes |
| Base Planner < 2 s (owner) | 18.7 s / 18.8 s | 0.69 s / 0.48 s | yes |
| No page over 3 s cold (owner) | 9 of 9 over | slowest is the Operational Planner, 1.4 s | yes |
| List endpoints p95 < 300 ms (docs/14) | 6 over | every list except `/job-items/destinations` (391 ms) | all but one |
| Week view / roster p95 < 1.5 s (docs/14) | 14.3 s / 12.2 s | coverage 1.4 s, Base Planner 0.80 s, roster 0.65 s p50 | yes, coverage only just |
| Chain depth ≤ 2 (addendum) | Dashboard 3, Worksite detail 3 | 2 at most (every page) | yes |
| A repeat visit < 300 ms from cache (addendum) | nothing cached | nothing cached; warm visits are fast because calls are fast | step 3 |

`/job-items/destinations` (391 ms p95) returns 1,500 job items with their worksite names for the reassignment picker; it is unscoped by rule (DEC-57). It was 19.5 s. Step 3 caches it on the client.

**Cause 3 re-checked (owner item 6):** requests no longer queue. In the first Operational Planner load after step 2 all 7 calls started within 27 ms of each other and overlapped: the six small ones were done by 650 ms, coverage finished at 1.65 s (server log, `api-timing` lines). The page time is now the slowest call, not the sum. No asyncio-debug run was needed, and no workers were added.

What still holds the event loop is coverage's own Python work: about **0.9–1.0 s per call** (server time 1.1–1.5 s, of which the database is 0.24–0.49 s), building 1,500 items × 7 day cells and 4.4 MB of JSON for an Admin (the whole company). While it runs, other requests in that process wait. Base Planner holds the loop for about 0.37 s (1.9 MB). For a supervisor both are much smaller, because they are now scoped. Options, in order of effect, for the owner to choose (step 3/4 or a later batch):
- the planner opens on one group or zone by default (the endpoints already take `group_id`; the web does not send it);
- a smaller coverage payload (only the cells that have something; names once per worker instead of per cell);
- moving the cell building off the event loop (a thread or a process pool);
- more uvicorn workers on Render, which only spreads the cost.

**Other notes:**
- **Live Map warm** went from 94 ms to 0.56–0.80 s. The API is not the cause (slowest call 140 ms): the page asks for the boundary queue only after the map has started (`LiveMap.tsx`, effect on `mapInstance`), and the map's style and tiles come from the tile server. Unchanged code; cold is 0.95 s (was 6.2 s).
- **Reports:** the survey runs each report once, first, on a cold database. The five reports that were slow because of the occurrence load dropped 7–19 s each (job-costing 20.2 s → 1.5 s; the app's preview is usable after 1.4 s, was 21.3 s). The attendance family showed 0.2–1.3 s more than the baseline in that single cold run, with the same queries and sizes and a higher DB time; timed again warm they were back at the baseline (daily-attendance 2.3 s, late-early-departure 1.9 s). Reports move to SQL in step 4.
- **Approvals inbox, Attendance tab** (29,382 pending rows in this dataset): page 1 of 50 rows takes 22 ms p50 and 18 KB (the whole inbox was 5.4 s and 9.8 MB); the last page 132 ms. The badge count takes 12 ms and 62 bytes.
- **Payroll draft** (cause 8) and the bundle (cause 9) are unchanged; they are steps 4 and 3.

## Method and environment

**Machine:** Windows 11, 12 CPUs, 16 GB RAM. Postgres 16 / PostGIS ran in the local docker-compose container. The API ran on uvicorn with 1 worker, no reload, `PERF_TIMING_ENABLED=true` (`tools/perf/run_api.py`). The web app was the production build served by `vite preview`, with `/api` proxied to the API. Browser and server were on the same machine, so the network time is close to zero.

**Dataset:** mock data only, in a separate local database `fw_perf` (`tools/perf/seed_perf_dataset.py --seed 42`, built in 316 s). Names are "Perf Worker 0001" and Tally IDs `PF00001…`.

| Table | Rows |
|---|---:|
| groups / zones | 20 / 30 |
| worksites (10% SA) | 400 |
| job items | 1,500 |
| job occurrences (the app's generator, from 2026-09-01, 13-month horizon) | 339,300 |
| employees (570 workers, 25 supervisors, 5 engineers) / salaries | 600 / 600 |
| standing assignments / base roster templates / entries | 912 / 912 / 3,420 |
| scheduled work (2026-09-01 to 13 months ahead) | 238,260 |
| leave requests | 17 |
| attendance records / calculations (2026-09-01 to 2026-11-23) | 40,938 / 40,938 |
| site visits | 39,312 |
| phone events (`mobile_event_logs`) | 426,179 |
| pending visits / last positions | 400 / 570 |
| payroll draft (Oct 2026, AE) / its generated reports | 1 run, 580 records / 11 |

**What went through the app:**
- through the app's own code: occurrences, the attendance values (the pure engine) and the payroll draft;
- bulk-inserted: master data, scheduled work, attendance rows, site visits and events. They are realistic in shape and count, but they are not the event pipeline's output.

**Page runs** (`tools/perf/measure_pages.py`):
- Each page was loaded once unrecorded, then 3 times **cold** (a new browser context: empty cache, fresh login state) and 3 times **warm** (leave to another page inside the app, then come back). The tables show the median.
- **Usable** means the page's API calls have been quiet for 500 ms, no loading spinner is visible, and the page's marker is visible (a table row on list pages).
- **Chain depth** is 1 + the longest chain of API calls where each starts only after an earlier one finished.

**Endpoint replay** (`tools/perf/measure_api.py`):
- Every GET URL the pages made was replayed one at a time: a warm-up, then 20 samples.
- Very slow endpoints got fewer samples (at least 3, about 60 s each).
- Server time comes from the `Server-Timing` header.

**Things to keep in mind when reading the numbers:**
- **Local only.** There is no network latency, and static files are served compressed by `vite preview`.
- **One worker.** The DB times in the page runs include time spent waiting for the event loop. The replay, one request at a time, gives the clean numbers.
- **The mock data has a very high pending-review rate.** 29,382 of 40,938 attendance days (72%) are PENDING_REVIEW, because the synthetic events often give short hours or overtime. Real data will probably have fewer, and the approvals payload scales with that number. `fw_db` has no attendance yet to compare with.
- **The occurrence volume is realistic.** `fw_db` has 186 occurrences per job item (58 items, 10,771 occurrences), and `fw_perf` has 226.
- **Runs were split.** The machine ran low on memory twice: the browser, Docker and the API, plus a Live Map measuring bug that kept the live stream buffering (fixed). After that, each page was measured in its own process. The three runs of each page are within ±10% of each other.

**Deviations from the step 1 brief:**
- **Attendance** is measured on the page's default range, the last 7 days, not a single day.
- **Scheduled work** runs 13 months ahead, as the app's standing assignments make it, not just 3 months.
- **Worksite detail** uses the site with the most job items (77P00001, 4 items).
- **Reports:** the heaviest report was picked locally: `job-costing`, October 2026, AE. The Render run reuses it.
- **Read-only checked locally.** A local `--read-only` run of both scripts behaved as required:
  - the Live Map's stream-ticket POST was blocked and listed as skipped, and the page fell back to polling;
  - no report was run, and no survey was written;
  - the host, region, network and zoned start time were recorded;
  - no credential appeared in the output.
- **Server-Timing in a browser:** Chromium (through Playwright) received and read the header via the preview proxy on every API call. A visual check in a browser's DevTools was not done.
  - The middleware's skip rule for the live stream also skipped `/live/stream-ticket`. It was fixed after the Live Map was measured, so that page has one 70 ms POST with no server time.

## Pages

**Local:** median of 3 runs.

| Page | Cold: usable | Warm: usable | **After step 2: cold / warm** | API requests (cold / warm) | Chain depth (cold / warm) | API bytes, cold | Static bytes, cold | Slowest call (cold): server time, queries |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Dashboard | 12.2 s | 6.5 s | **250 ms / 109 ms** | 5 / 4 | 3 / 3 | 19.7 MB | 607 KB | `/approvals`: 11.5 s, 64 queries |
| Worksites | 9.9 s | 3.6 s | **281 ms / 47 ms** | 6 / 5 | 1 / 1 | 9.9 MB | 607 KB | `/approvals`: 9.6 s, 64 queries |
| Worksite detail | 7.4 s | 172 ms | **203 ms / 62 ms** | 8 / 7 | 2 / 3 | 10.1 MB | 607 KB | `/approvals`: 7.1 s, 64 queries |
| Base Planner | 18.7 s | 18.8 s | **688 ms / 484 ms** | 3 / 3 | 1 / 2 | 11.6 MB | 607 KB | `/base-planner/worksites`: 18.5 s, 411 queries |
| Operational Planner (week) | 80.8 s | 70.3 s | **1.4 s / 1.4 s** | 9 / 8 | 2 / 2 | 34.3 MB | 607 KB | `/operational-planner/coverage`: 77.7 s, 416 queries |
| Employees | 10.3 s | 235 ms | **343 ms / 203 ms** | 5 / 4 | 1 / 1 | 10.4 MB | 607 KB | `/approvals`: 9.8 s, 64 queries |
| Attendance (last 7 days) | 10.0 s | 172 ms | **235 ms / 63 ms** | 3 / 2 | 2 / 2 | 10.0 MB | 607 KB | `/approvals`: 9.5 s, 64 queries |
| Live Map | 6.2 s | 94 ms | **954 ms / 750 ms** | 4 / 2 | 2 / 1 | 10.4 MB | 1.1 MB | `/approvals`: 5.9 s, 64 queries |
| Reports | 5.9 s | 31 ms | **187 ms / 32 ms** | 2 / 1 | 1 / 1 | 9.9 MB | 607 KB | `/approvals`: 5.7 s, 64 queries |
| Worksite detail, Schedule tab (new in step 2) | | | **250 ms / 94 ms** | | | | | |
| Approvals inbox (new in step 2) | | | **172 ms / 31 ms** | | | | | |

**Report run** (Reports page, `job-costing`, 2026-10): usable 21.3 s after "Run Preview", 1 request, 13 KB. **After step 2: 1.4 s.**

**After step 2, the other columns** (cold): every page makes its calls at chain depth 1 or 2. The largest API transfers are now the Operational Planner (205 KB on the wire, 5.0 MB unpacked) and Base Planner (213 KB, 1.9 MB unpacked); every other page transfers under 60 KB. The slowest call is `/operational-planner/coverage` (1.2 s, 13 queries) on the Operational Planner, `/base-planner/worksites` (0.54 s, 10 queries) on Base Planner, and under 100 ms with at most 16 queries on every other page. Details per page and run: `after-step2/pages-localhost.json`.

| Page | Render: cold | Render: warm |
|---|---:|---:|
| all 9 pages | pending: owner run | pending: owner run |

**Static files** are the same on every page: one 2.4 MB JavaScript bundle (597 KB gzipped) and 130 KB of CSS. The Live Map adds the map worker (519 KB) and map tiles.

## Endpoints

**Local:** replayed one at a time. Each one's target is from docs/14: lists p95 < 300 ms; week view or roster p95 < 1.5 s. A path appears more than once when pages call it with different query strings.

| Endpoint | Pages | Samples | Server p50 | Server p95 | Target | DB p50 | Queries | Max repeats | Size | Gzip would send | **After step 2: server p50 / p95, queries** |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `/reports/job-costing` | Report run | 3 | 20.6 s | 20.8 s **over** | 300 ms | 5.5 s | 19 | 5 | 13 KB | 1 KB | 959 ms / 1.0 s, 13 q |
| `/job-items/destinations` | Ops Planner | 3 | 19.2 s | 19.5 s **over** | 300 ms | 8.4 s | 10 | 6 | 396 KB | 53 KB | 321 / 391 ms, 4 q |
| `/operational-planner/coverage` | Ops Planner | 4 | 13.7 s | 14.3 s **over** | 1.5 s | 5.0 s | 416 | 400 | 4.2 MB | 127 KB | 1.2 s / 1.4 s, 13 q |
| `/base-planner/worksites` | Base Planner | 5 | 11.0 s | 12.2 s **over** | 1.5 s | 3.2 s | 411 | 400 | 1.8 MB | 206 KB | 594 / 800 ms, 10 q |
| `/approvals` | all 9 | 10 | 5.4 s | 5.8 s **over** | 300 ms | 2.4 s | 64 | 58 | 9.8 MB | 1.6 MB | replaced by `/approvals/counts`: 13 / 14 ms, 4 q, 62 B |
| `/worksites` | Worksites | 20 | 2.7 s | 3.1 s **over** | 300 ms | 613 ms | 5 | 1 | 64 KB | 7 KB | 15 / 16 ms, 2 q |
| `/worksites/{id}` | Worksite detail | 20 | 43 ms | 182 ms | 300 ms | 19 ms | 13 | 2 | 10 KB | 1 KB | 20 / 26 ms, 11 q |
| `/live/positions` | Live Map | 20 | 44 ms | 70 ms | 300 ms | 12 ms | 6 | 1 | 546 KB | 50 KB | 74 / 254 ms, 6 q |
| `/dashboard/summary` | Dashboard | 20 | 50 ms | 52 ms | 300 ms | 22 ms | 16 | 2 | 449 B | 260 B | 72 / 259 ms, 16 q |
| `/occurrences` | Worksite detail | 20 | 22 ms | 31 ms | 300 ms | 8 ms | 2 | 1 | 219 KB | 16 KB | replaced by `/worksites/{id}/occurrences` (Schedule tab, one month): 17 / 18 ms, 3 q |
| `/employees/hierarchy` | Employees | 20 | 22 ms | 31 ms | 300 ms | 5 ms | 3 | 1 | 321 KB | 20 KB | 34 / 48 ms, 3 q |
| `/employees` | Employees | 20 | 20 ms | 26 ms | 300 ms | 6 ms | 2 | 1 | 291 KB | 20 KB | 34 / 44 ms, 2 q |
| `/employees` | Ops Planner | 20 | 18 ms | 24 ms | 300 ms | 6 ms | 2 | 1 | 243 KB | 17 KB | 29 / 30 ms, 2 q |
| `/attendance` | Attendance | 20 | 19 ms | 23 ms | 300 ms | 9 ms | 6 | 1 | 107 KB | 12 KB | 27 / 31 ms, 6 q |
| `/attendance/exceptions` | Attendance | 20 | 14 ms | 16 ms | 300 ms | 7 ms | 6 | 1 | 2 KB | 1 KB | 15 / 18 ms, 6 q |
| `/settings/staff-grades` | Employees | 20 | 7 ms | 10 ms | 300 ms | 3 ms | 4 | 1 | 298 B | 187 B | 9 / 9 ms, 4 q |
| `/boundary-queue` | Dashboard | 20 | 9 ms | 9 ms | 300 ms | 4 ms | 7 | 1 | 236 B | 108 B | 13 / 15 ms, 7 q |
| `/staffing-gaps` | Ops Planner | 20 | 6 ms | 8 ms | 300 ms | 2 ms | 3 | 1 | 59 B | 63 B | 8 / 9 ms, 3 q |
| `/salary-revisions` | Worksites, Worksite detail | 20 | 6 ms | 7 ms | 300 ms | 2 ms | 3 | 1 | 627 B | 271 B | 8 / 9 ms, 3 q |
| `/reassignment-requests` | Ops Planner | 20 | 6 ms | 7 ms | 300 ms | 1 ms | 2 | 1 | 2 B | 22 B | 7 / 8 ms, 2 q |
| `/alerts` | Dashboard | 20 | 5 ms | 6 ms | 300 ms | 2 ms | 2 | 1 | 511 B | 365 B | 7 / 7 ms, 2 q |
| `/employees` | Worksite detail, Base Planner, Ops Planner | 20 | 5 ms | 5 ms | 300 ms | 2 ms | 2 | 1 | 12 KB | 1 KB | 7 / 8 ms, 2 q |
| `/zones` | Worksites, Worksite detail | 20 | 4 ms | 5 ms | 300 ms | 1 ms | 2 | 1 | 3 KB | 957 B | 8 / 9 ms, 2 q |
| `/accommodations` | Worksites | 20 | 4 ms | 5 ms | 300 ms | 1 ms | 2 | 1 | 2 B | 22 B | 7 / 7 ms, 2 q |
| `/worksites/{id}/supervisors` | Worksite detail | 20 | 5 ms | 5 ms | 300 ms | 1 ms | 2 | 1 | 571 B | 279 B | 6 / 6 ms, 2 q |
| `/groups` | Worksites, Worksite detail | 20 | 4 ms | 5 ms | 300 ms | 1 ms | 2 | 1 | 2 KB | 678 B | 7 / 7 ms, 2 q |
| `/accommodations` | Employees | 20 | 4 ms | 5 ms | 300 ms | 1 ms | 2 | 1 | 2 B | 22 B | 6 / 6 ms, 2 q |
| `/reports` | Reports | 20 | 4 ms | 5 ms | 300 ms | 1 ms | 1 | 1 | 21 KB | 3 KB | 6 / 6 ms, 1 q |

**Render:** pending, owner run.

### Reports (local, one run each, October 2026, AE)

| Report | Server | DB | Queries | Max repeats | Total rows | **After step 2: server, DB, queries** |
|---|---:|---:|---:|---:|---:|---|
| `job-costing` | 20.2 s | 5.7 s | 19 | 5 | 360 | 1.5 s, 234 ms, 13 |
| `project-attendance-summary` | 11.2 s | 3.0 s | 12 | 2 | 360 | 1.6 s, 709 ms, 9 |
| `employee-movement` | 10.3 s | 2.2 s | 10 | 3 | 14,182 | 1.1 s, 185 ms, 7 |
| `site-visits` | 10.1 s | 2.0 s | 9 | 3 | 14,182 | 1.1 s, 375 ms, 6 |
| `weekly-roster` | 8.6 s | 2.6 s | 9 | 2 | 580 | 216 ms, 75 ms, 6 |
| `daily-attendance` | 2.4 s | 747 ms | 90 | 28 | 14,272 | 3.5 s, 1.4 s, 90 (warm re-run: 2.3 s) |
| `late-early-departure` | 2.2 s | 792 ms | 61 | 28 | 14,272 | 2.9 s, 1.1 s, 61 (warm re-run: 1.9 s) |
| `transportation-time` | 1.9 s | 622 ms | 32 | 28 | 14,272 | 2.2 s, 1.0 s, 32 |
| `monthly-attendance` | 1.7 s | 614 ms | 32 | 28 | 550 | 1.9 s, 743 ms, 32 |
| `employee-utilization` | 993 ms | 451 ms | 32 | 28 | 14,272 | 2.3 s, 754 ms, 32 (warm re-run: 1.6 s) |
| `provisions-staff-cost` | 269 ms | 62 ms | 10 | 2 | 580 | 189 ms, 101 ms, 10 |
| `payroll` | 144 ms | 75 ms | 10 | 2 | 580 | 205 ms, 96 ms, 10 |
| `pending-visits` | 19 ms | 12 ms | 2 | 1 | 0 | 10 ms, 3 ms, 2 |
| `staffing-gaps` | 13 ms | 6 ms | 4 | 1 | 6 | 14 ms, 5 ms, 4 |
| `document-expiry` | 11 ms | 4 ms | 3 | 1 | 0 | 14 ms, 4 ms, 3 |

The after-step-2 survey is one cold run per report; see [After step 2](#after-step-2-local) for why the attendance family reads higher there.

**Payroll draft:** generating the October AE draft (580 employees) took **81 s** in one call, including the 11 reports the `PayrollRunCreated` listener generates. This was measured while seeding, with the same code that `POST /api/v1/payroll/runs` runs.

## Targets

| Target (addendum, docs/14) | Baseline (local) | **After step 2 (local)** |
|---|---|---|
| List endpoints: p95 server time < 300 ms | Over: `/approvals` 5.8 s, `/worksites` 3.1 s, `/job-items/destinations` 19.5 s. All other list endpoints are under 200 ms. | Met except `/job-items/destinations` 391 ms. The badge count is 14 ms, an inbox page 23 ms, `/worksites` 16 ms. |
| Week view / roster: p95 < 1.5 s | Over: `/operational-planner/coverage` 14.3 s, `/base-planner/worksites` 12.2 s | Met: coverage 1.4 s, Base Planner 800 ms, roster 0.65 s p50 (Admin, all 600 employees). |
| A repeat visit to a list page shows data in < 300 ms from cache | Nothing is cached. Repeat visits fetch everything again: Worksites 3.6 s, Base Planner 18.8 s, Operational Planner 70.3 s. Employees, Attendance and Live Map are under 300 ms only because their calls are fast. | Still nothing cached (step 3). Warm visits: Worksites 47 ms, Base Planner 484 ms, Operational Planner 1.4 s. |
| No page with request chains deeper than 2 | Over: Dashboard 3 (cold and warm), Worksite detail 3 (warm) | Met: 2 at most on every page. |

## Top 10 causes, ranked by impact

**Ranking:** time each cause adds locally, summed over the 9 pages, with how many pages it touches as the tiebreak. Network effects are noted, not counted; the Render run will add them. Causes 1 and 2 are close. Cause 1 touches every page. Cause 2 is the largest server-side cost and grows with every job item.

### 1. The app shell fetches the whole approvals inbox to show a badge
**Pages:** all 9, cold. The badge also refreshes every 30 s per open tab.

**Where:** `web/src/components/layout/Shell.tsx:101` fetches `GET /approvals?status=PENDING` on load and every 30 s, and reads only `counts.total`. `web/src/routes/Dashboard.tsx:65` fetches it again. On the server, `AttendanceService.get_attendance_approvals` (`modules/attendance/service.py:880`) returns every pending attendance row, with no paging.

**Evidence:**
- Each call returns 9.8 MB and 29,382 rows: 64 queries, 5.4 s p50 on its own.
- Inside pages, while other calls run, it takes 5.7–11.5 s.
- It accounts for nearly all of the cold load of 7 pages (cold vs warm):

  | Page | Cold | Warm |
  |---|---:|---:|
  | Worksite detail | 7.4 s | 0.17 s |
  | Employees | 10.3 s | 0.24 s |
  | Attendance | 10.0 s | 0.17 s |
  | Live Map | 6.2 s | 0.09 s |
  | Reports | 5.9 s | 0.03 s |
- The Dashboard loads 19.7 MB because it makes the call twice.
- The 58 repeated statements come from `selectinload(AttendanceRecord.current_calculation)`, in chunks of 500. It loads the calculation rows a second time, although the query already joins them.

**Scale:** with the mock data's 72% pending, this is the high end. Even 2,000 pending rows would mean about 0.7 MB per page load and per 30 s.

**Steps:**
- Step 2: a count-only call for the badge, paging for the inbox, removing the duplicate load and the second Dashboard call.
- Step 3: one shared query for the badge.

**After step 2:** done. The badge is `GET /approvals/counts` (12 ms, 62 bytes); the inbox page fetches one tab, 50 rows at a time (22 ms on the Attendance tab); the duplicate calculation load is gone; the Dashboard previews ask for 4 rows each.

### 2. Loading worksites also loads every job item and every occurrence
**Pages:** Worksites, Base Planner, Operational Planner, Reports.

**Where:** `Worksite.items` and `JobItem.occurrences` are both `lazy="selectin"` (`modules/jobs/models.py:72` and `:131`). Any query that loads worksites therefore also loads all their items and all their occurrences, up to 13 months ahead. That is 339,300 rows here.

**Evidence:**
- `GET /worksites` takes 2.7 s p50 for a 64 KB list, with 5 queries. The occurrence load is about 0.7 s; most of the rest is building those Python objects. This is the whole 3.6 s of a warm Worksites visit.
- `GET /job-items/destinations` takes 19.2 s p50. The occurrence statement runs 6 times per request.
- The occurrence statement is also the top slow statement in `base-planner/worksites`, `operational-planner/coverage` and the reports.
- `job-costing` takes 20.2 s to return 360 rows, and its top slow statement is the occurrence load.

**Growth:** `fw_db` has the same ratio per item, so this cost grows with every job item added.

**Step:** step 2: no nested items or occurrences unless asked; load explicitly per query.

**After step 2:** done. `/worksites` 16 ms p95 (was 3.1 s), destinations 391 ms (was 19.5 s), job-costing 1.0 s (was 20.8 s).

### 3. Heavy Python work on one event loop makes concurrent requests queue
**Pages:** all, worst on the planners.

**Where:** the request handlers are async, but most of their time is CPU work: building ORM objects and assembling payloads. While one request computes, every other request in that process waits.

**Evidence:**

| Operational Planner call | Alone (p50) | Inside the page |
|---|---:|---:|
| coverage | 13.7 s | 77.7 s |
| destinations | 19.2 s | 66 s |
| approvals | 5.4 s | 48.6 s |

- The Operational Planner page took 80.8 s: the sum of its calls, not the slowest one.
- The Base Planner endpoint takes 11.0 s alone and 18.5 s next to `/approvals`.
- The same waiting inflates the DB times in the page runs. For example, one settings lookup was logged at 2.8 s during a page run.

**Steps:**
- Step 2: less work per request (causes 1, 2, 4 and 5).
- Step 5: the hosting note should state the number of workers or processes on Render. One worker serialises all users.

**After step 2:** calls no longer queue; see [After step 2](#after-step-2-local) for the timeline and what still holds the loop (coverage's Python work, about 0.9 s per Admin call).

### 4. The planners build the whole network in Python, with a settings query per worksite
**Pages:** Base Planner, Operational Planner.

**Where:** `get_budget_only_staff_types` is called once per worksite (`modules/scheduling/service.py:2312` and `:2649`), although there are only two countries. Both endpoints return every worksite, item and template or coverage cell for the week.

**Evidence:**

| Endpoint | Queries (repeated) | Size | p50 / p95 | Target |
|---|---|---:|---|---|
| `operational-planner/coverage` | 416 (400) | 4.2 MB | 13.7 / 14.3 s | 1.5 s |
| `base-planner/worksites` | 411 (400) | 1.8 MB | 11.0 / 12.2 s | 1.5 s |

**Steps:**
- Step 2: settings once per country; a default filter (group or zone) or paging; only the fields the grid shows.
- Step 4: cache the settings.

**After step 2:** settings (and, in `/schedule/coverage`, holidays) are read once per country; coverage 13 queries, Base Planner 10, `/schedule/coverage` 14 (was 412). Scoping to the user's worksites (DEC-57) shrinks both for non-Admins. A default group/zone filter and a smaller payload are still open.

### 5. No browser caching: every visit fetches everything again
**Pages:** all.

**Where:** `@tanstack/react-query` is installed but unused. Pages use raw `fetch` in effects.

**Evidence:**
- Warm visits are as slow as cold ones whenever the page's own calls are slow:

  | Page | Warm | Cold |
  |---|---:|---:|
  | Base Planner | 18.8 s | 18.7 s |
  | Operational Planner | 70.3 s | 80.8 s |
  | Worksites | 3.6 s | 9.9 s, of which `/worksites` 3.5 s |
- Groups, zones, salary revisions and employee lists are fetched again on every page that uses them.
- The Operational Planner fetches `/employees` twice, with different filters.

**Step:** step 3.

### 6. Reports are computed in Python over full ORM rows
**Pages:** Reports, and the payroll draft (cause 8).

**Evidence:** for one month, 5 of the 15 reports take over 8 s:

| Report | Server time | Of which Python | Rows |
|---|---:|---:|---:|
| `job-costing` | 20.2 s | about 14 s | 360 |
| `project-attendance-summary` | 11.2 s | | |
| `employee-movement` | 10.3 s | | |
| `site-visits` | 10.1 s | | |
| `weekly-roster` | 8.6 s | | |

- The attendance family takes 1–2.4 s each, with 28 repeated statements: `selectinload` in chunks of 500 over 14,272 rows.
- In the app, the job-costing preview is usable after 21.3 s.

**Step:** step 2: aggregate in SQL, drop the occurrence load (cause 2), and load only the columns a report shows.

### 7. No response compression
**Pages:** all. Hidden locally; it will matter most on Render over home broadband.

**Evidence:** API bytes on the wire equal the decoded size (no `Content-Encoding`). What gzip would send instead:

| Response | Sent now | Gzip would send |
|---|---:|---:|
| approvals | 9.8 MB | 1.6 MB |
| coverage | 4.2 MB | 127 KB |
| base planner | 1.8 MB | 206 KB |
| live positions | 546 KB | 50 KB |
| employee lists | about 290 KB | about 20 KB |

At 20 Mbit/s, 9.8 MB takes about 4 s to transfer, and 1.6 MB under 1 s.

**Step:** step 2 (`GZipMiddleware`).

**After step 2:** done (1 KB minimum, level 6). Coverage sends 130 KB instead of 4.4 MB, Base Planner 211 KB instead of 1.9 MB, live positions 51 KB instead of 559 KB.

### 8. The payroll draft runs inside one request
**Pages:** Payroll, plus every other user while it runs (cause 3).

**Evidence:** 81 s for 580 employees, including generating 11 reports in the same request. Long synchronous requests risk proxy or host timeouts, and they block the worker for everyone.

**Step:** step 2 ("anything else step 1 finds"): generate the reports in the background (the job queue exists), and check the time without them.

### 9. One 2.4 MB JavaScript bundle, no code splitting
**Pages:** every first visit.

**Evidence:**
- `index.js` is 2.4 MB (597 KB gzipped). It includes the 3,700-line Operational Planner, the map and the charts.
- There is no `React.lazy` anywhere, and Vite warns about the chunk size.
- It costs little locally. On a slow link it is 1–3 s before anything shows.

**Step:** step 2 ("anything else"): route-level splitting.

### 10. Request waterfalls
**Pages:** Dashboard, Worksite detail.

**Evidence:**
- The Dashboard awaits its calls one after another: alerts, summary, boundary queue, then approvals (`web/src/routes/Dashboard.tsx:47-65`). The measured chain depth is 3, cold and warm.
- Worksite detail has a chain depth of 3 on warm visits.
- Locally this adds about 0.4 s before the large call starts. With a 200–300 ms round trip from Kerala, every extra link adds at least one round trip.

**Step:** step 2 (run independent calls in parallel).

**After step 2:** done. The Dashboard is at depth 1; Worksite detail at 2.

### Checked and not ranked
- **Staffing gaps:** `get_staffing_gaps`, which runs queries in loops (a known issue in the brief), took 6.5 ms here. The mock data has only 6 gaps, so step 1 does not confirm it as a cost at this data shape. Step 2 should still fix it, because it grows with the number of gaps. **After step 2:** fixed; the number of queries no longer depends on the number of leave days or gaps (test `test_staffing_gaps_query_count_does_not_grow_with_leave_length`).
- **Indexes:** none missing. The hot columns are all indexed: `job_item_id`, `review_status`, the setting key, and the date and employee columns of `scheduled_work`. The slow statements are slow because of the number of rows returned.
- **Live positions:** 546 KB per load and per 30 s poll. Gzip (cause 7) covers most of it.
- **Live Map polling badge:** it shows a spinner that never stops ("Refreshing every 30s"), which looks like the page is still loading. This is UI, not speed; Batch 10.
