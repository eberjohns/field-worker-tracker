# Performance baseline (Batch 9 step 1), November 2026

Measured 24 Nov 2026 on the code of `perf/batch9-measure`. That is v1.17.0, which includes #32, #33 and #34, plus the step 1 tooling. There are no speed fixes in this step.

**Where the numbers come from:**
- `docs/reviews/perf-2026-11/pages-localhost.json`: page loads in Chromium.
- `docs/reviews/perf-2026-11/api-localhost.json`: endpoint replay and the report survey.
- the API's `request_timing` log, for slow SQL and repeats.

`docs/runbooks/06-performance-measurement.md` describes how to measure and how to re-run.

**Render:** pending, owner run. The Render columns below stay empty until the owner runs both scripts with `--read-only` (runbook 06).

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

| Page | Cold: usable | Warm: usable | API requests (cold / warm) | Chain depth (cold / warm) | API bytes, cold | Static bytes, cold | Slowest call (cold): server time, queries |
|---|---:|---:|---:|---:|---:|---:|---|
| Dashboard | 12.2 s | 6.5 s | 5 / 4 | 3 / 3 | 19.7 MB | 607 KB | `/approvals`: 11.5 s, 64 queries |
| Worksites | 9.9 s | 3.6 s | 6 / 5 | 1 / 1 | 9.9 MB | 607 KB | `/approvals`: 9.6 s, 64 queries |
| Worksite detail | 7.4 s | 172 ms | 8 / 7 | 2 / 3 | 10.1 MB | 607 KB | `/approvals`: 7.1 s, 64 queries |
| Base Planner | 18.7 s | 18.8 s | 3 / 3 | 1 / 2 | 11.6 MB | 607 KB | `/base-planner/worksites`: 18.5 s, 411 queries |
| Operational Planner (week) | 80.8 s | 70.3 s | 9 / 8 | 2 / 2 | 34.3 MB | 607 KB | `/operational-planner/coverage`: 77.7 s, 416 queries |
| Employees | 10.3 s | 235 ms | 5 / 4 | 1 / 1 | 10.4 MB | 607 KB | `/approvals`: 9.8 s, 64 queries |
| Attendance (last 7 days) | 10.0 s | 172 ms | 3 / 2 | 2 / 2 | 10.0 MB | 607 KB | `/approvals`: 9.5 s, 64 queries |
| Live Map | 6.2 s | 94 ms | 4 / 2 | 2 / 1 | 10.4 MB | 1.1 MB | `/approvals`: 5.9 s, 64 queries |
| Reports | 5.9 s | 31 ms | 2 / 1 | 1 / 1 | 9.9 MB | 607 KB | `/approvals`: 5.7 s, 64 queries |

**Report run** (Reports page, `job-costing`, 2026-10): usable 21.3 s after "Run Preview", 1 request, 13 KB.

| Page | Render: cold | Render: warm |
|---|---:|---:|
| all 9 pages | pending: owner run | pending: owner run |

**Static files** are the same on every page: one 2.4 MB JavaScript bundle (597 KB gzipped) and 130 KB of CSS. The Live Map adds the map worker (519 KB) and map tiles.

## Endpoints

**Local:** replayed one at a time. Each one's target is from docs/14: lists p95 < 300 ms; week view or roster p95 < 1.5 s. A path appears more than once when pages call it with different query strings.

| Endpoint | Pages | Samples | Server p50 | Server p95 | Target | DB p50 | Queries | Max repeats | Size | Gzip would send |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `/reports/job-costing` | Report run | 3 | 20.6 s | 20.8 s **over** | 300 ms | 5.5 s | 19 | 5 | 13 KB | 1 KB |
| `/job-items/destinations` | Ops Planner | 3 | 19.2 s | 19.5 s **over** | 300 ms | 8.4 s | 10 | 6 | 396 KB | 53 KB |
| `/operational-planner/coverage` | Ops Planner | 4 | 13.7 s | 14.3 s **over** | 1.5 s | 5.0 s | 416 | 400 | 4.2 MB | 127 KB |
| `/base-planner/worksites` | Base Planner | 5 | 11.0 s | 12.2 s **over** | 1.5 s | 3.2 s | 411 | 400 | 1.8 MB | 206 KB |
| `/approvals` | all 9 | 10 | 5.4 s | 5.8 s **over** | 300 ms | 2.4 s | 64 | 58 | 9.8 MB | 1.6 MB |
| `/worksites` | Worksites | 20 | 2.7 s | 3.1 s **over** | 300 ms | 613 ms | 5 | 1 | 64 KB | 7 KB |
| `/worksites/{id}` | Worksite detail | 20 | 43 ms | 182 ms | 300 ms | 19 ms | 13 | 2 | 10 KB | 1 KB |
| `/live/positions` | Live Map | 20 | 44 ms | 70 ms | 300 ms | 12 ms | 6 | 1 | 546 KB | 50 KB |
| `/dashboard/summary` | Dashboard | 20 | 50 ms | 52 ms | 300 ms | 22 ms | 16 | 2 | 449 B | 260 B |
| `/occurrences` | Worksite detail | 20 | 22 ms | 31 ms | 300 ms | 8 ms | 2 | 1 | 219 KB | 16 KB |
| `/employees/hierarchy` | Employees | 20 | 22 ms | 31 ms | 300 ms | 5 ms | 3 | 1 | 321 KB | 20 KB |
| `/employees` | Employees | 20 | 20 ms | 26 ms | 300 ms | 6 ms | 2 | 1 | 291 KB | 20 KB |
| `/employees` | Ops Planner | 20 | 18 ms | 24 ms | 300 ms | 6 ms | 2 | 1 | 243 KB | 17 KB |
| `/attendance` | Attendance | 20 | 19 ms | 23 ms | 300 ms | 9 ms | 6 | 1 | 107 KB | 12 KB |
| `/attendance/exceptions` | Attendance | 20 | 14 ms | 16 ms | 300 ms | 7 ms | 6 | 1 | 2 KB | 1 KB |
| `/settings/staff-grades` | Employees | 20 | 7 ms | 10 ms | 300 ms | 3 ms | 4 | 1 | 298 B | 187 B |
| `/boundary-queue` | Dashboard | 20 | 9 ms | 9 ms | 300 ms | 4 ms | 7 | 1 | 236 B | 108 B |
| `/staffing-gaps` | Ops Planner | 20 | 6 ms | 8 ms | 300 ms | 2 ms | 3 | 1 | 59 B | 63 B |
| `/salary-revisions` | Worksites, Worksite detail | 20 | 6 ms | 7 ms | 300 ms | 2 ms | 3 | 1 | 627 B | 271 B |
| `/reassignment-requests` | Ops Planner | 20 | 6 ms | 7 ms | 300 ms | 1 ms | 2 | 1 | 2 B | 22 B |
| `/alerts` | Dashboard | 20 | 5 ms | 6 ms | 300 ms | 2 ms | 2 | 1 | 511 B | 365 B |
| `/employees` | Worksite detail, Base Planner, Ops Planner | 20 | 5 ms | 5 ms | 300 ms | 2 ms | 2 | 1 | 12 KB | 1 KB |
| `/zones` | Worksites, Worksite detail | 20 | 4 ms | 5 ms | 300 ms | 1 ms | 2 | 1 | 3 KB | 957 B |
| `/accommodations` | Worksites | 20 | 4 ms | 5 ms | 300 ms | 1 ms | 2 | 1 | 2 B | 22 B |
| `/worksites/{id}/supervisors` | Worksite detail | 20 | 5 ms | 5 ms | 300 ms | 1 ms | 2 | 1 | 571 B | 279 B |
| `/groups` | Worksites, Worksite detail | 20 | 4 ms | 5 ms | 300 ms | 1 ms | 2 | 1 | 2 KB | 678 B |
| `/accommodations` | Employees | 20 | 4 ms | 5 ms | 300 ms | 1 ms | 2 | 1 | 2 B | 22 B |
| `/reports` | Reports | 20 | 4 ms | 5 ms | 300 ms | 1 ms | 1 | 1 | 21 KB | 3 KB |

**Render:** pending, owner run.

### Reports (local, one run each, October 2026, AE)

| Report | Server | DB | Queries | Max repeats | Total rows |
|---|---:|---:|---:|---:|---:|
| `job-costing` | 20.2 s | 5.7 s | 19 | 5 | 360 |
| `project-attendance-summary` | 11.2 s | 3.0 s | 12 | 2 | 360 |
| `employee-movement` | 10.3 s | 2.2 s | 10 | 3 | 14,182 |
| `site-visits` | 10.1 s | 2.0 s | 9 | 3 | 14,182 |
| `weekly-roster` | 8.6 s | 2.6 s | 9 | 2 | 580 |
| `daily-attendance` | 2.4 s | 747 ms | 90 | 28 | 14,272 |
| `late-early-departure` | 2.2 s | 792 ms | 61 | 28 | 14,272 |
| `transportation-time` | 1.9 s | 622 ms | 32 | 28 | 14,272 |
| `monthly-attendance` | 1.7 s | 614 ms | 32 | 28 | 550 |
| `employee-utilization` | 993 ms | 451 ms | 32 | 28 | 14,272 |
| `provisions-staff-cost` | 269 ms | 62 ms | 10 | 2 | 580 |
| `payroll` | 144 ms | 75 ms | 10 | 2 | 580 |
| `pending-visits` | 19 ms | 12 ms | 2 | 1 | 0 |
| `staffing-gaps` | 13 ms | 6 ms | 4 | 1 | 6 |
| `document-expiry` | 11 ms | 4 ms | 3 | 1 | 0 |

**Payroll draft:** generating the October AE draft (580 employees) took **81 s** in one call, including the 11 reports the `PayrollRunCreated` listener generates. This was measured while seeding, with the same code that `POST /api/v1/payroll/runs` runs.

## Targets

| Target (addendum, docs/14) | Now (local) |
|---|---|
| List endpoints: p95 server time < 300 ms | Over: `/approvals` 5.8 s, `/worksites` 3.1 s, `/job-items/destinations` 19.5 s. All other list endpoints are under 200 ms. |
| Week view / roster: p95 < 1.5 s | Over: `/operational-planner/coverage` 14.3 s, `/base-planner/worksites` 12.2 s |
| A repeat visit to a list page shows data in < 300 ms from cache | Nothing is cached. Repeat visits fetch everything again: Worksites 3.6 s, Base Planner 18.8 s, Operational Planner 70.3 s. Employees, Attendance and Live Map are under 300 ms only because their calls are fast. |
| No page with request chains deeper than 2 | Over: Dashboard 3 (cold and warm), Worksite detail 3 (warm) |

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

### Checked and not ranked
- **Staffing gaps:** `get_staffing_gaps`, which runs queries in loops (a known issue in the brief), took 6.5 ms here. The mock data has only 6 gaps, so step 1 does not confirm it as a cost at this data shape. Step 2 should still fix it, because it grows with the number of gaps.
- **Indexes:** none missing. The hot columns are all indexed: `job_item_id`, `review_status`, the setting key, and the date and employee columns of `scheduled_work`. The slow statements are slow because of the number of rows returned.
- **Live positions:** 546 KB per load and per 30 s poll. Gzip (cause 7) covers most of it.
- **Live Map polling badge:** it shows a spinner that never stops ("Refreshing every 30s"), which looks like the page is still loading. This is UI, not speed; Batch 10.
