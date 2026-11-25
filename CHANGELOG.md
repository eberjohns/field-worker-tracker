# Changelog
All notable changes. Format: Keep a Changelog. Mobile-contract changes are also logged in `docs/09-mobile-sync-contract.md`.

## [1.29.0] - 2026-11-25
### Added (chore: Render Blueprint)
- **`render.yaml`** describes the current Render setup. The owner applies it; nothing calls Render.
  - **Web static site** `field-worker-tracker-1`:
    - the CI build (pnpm, frozen lockfile), published from `web/dist`;
    - rewrites in order: `/api/*` to the backend, then `/*` to `/index.html`;
    - `VITE_GOOGLE_MAPS_API_KEY` and `VITE_GOOGLE_MAPS_MAP_ID` listed with `sync: false`;
    - no `VITE_API_URL`, since the rewrite makes it unnecessary.
  - **Backend** (Docker, `backend/Dockerfile`):
    - migrations on every deploy (`preDeployCommand: uv run alembic upgrade head`), with the free-plan alternative in a comment;
    - a health check;
    - every variable `sync: false`, with no values.
  - Nothing for push, email, MapTiler or Nominatim.
- **Runbook 09:**
  - checking names, the URL and the build against Render first;
  - applying the Blueprint and deleting leftover variables;
  - why the rewrite order matters;
  - `VITE_` values need a rebuild;
  - migrations on deploy, paid and free;
  - what to do when a deploy fails (`alembic current` / `heads`).
- **Runbooks 01 and 08** point to it. Runbook 01 no longer lists a push key.
- **`web/vercel.json`** is unchanged: it already has the same two rules in the same order.

## [1.28.0] - 2026-11-25
### Added (docs: mobile handover)
- **`docs/mobile-handover-v1.md`:** one standalone document for the mobile team. It covers:
  - every contract change since revision 1.1.1, with before/after bodies and what the app must do: lockout `403 ACCOUNT_LOCKED`, the error `detail` key, no push, no scorecard, gzip, template schedule items, the device-mismatch alert, value-only changes;
  - worksite and camp boundaries as the app receives them: GeoJSON `Polygon`, `[lng, lat]`, closed rings, holes, `geofence_circle` with named keys, and a worked example;
  - drawing a boundary with `PolygonOptions` / `LatLng` in the Google Maps SDK for Android;
  - setting up the Maps SDK key: its own Android key restricted by package name and SHA-1 to the Maps SDK for Android, no Map ID, and the key passed in from a build variable, never committed.
- **Runbook 08 §6:** the same Maps SDK for Android key setup.
- The 19 Nov mobile notes and the integration guide point to the new document.

## [1.27.0] - 2026-11-25
### Added (Batch 7: login lockout, push and email removal, decision records)
- **Login lockout (DEC-66), web and mobile:**
  - 5 wrong passwords in a row lock the account for 15 minutes (company settings `login_max_failed_attempts`, `login_lockout_minutes`).
  - While locked, every login, even with the right password, gets `403 ACCOUNT_LOCKED` with `reason`, `locked_until` and the unlock time in site time.
  - A successful login resets the count; once a lock has expired the count starts again.
  - An unknown user name gets the same reply and the same password-hashing work as a wrong password.
  - The count and the lock are committed even though the login fails.
  - Migration 0029 adds `users.last_failed_login_at` (the count reuses `users.failed_attempts`) and the two settings.
- **Admin "Unlock account"** on the Users page (`POST /users/{id}/unlock`), with a **Locked** badge. Every lock (`LOCK_ACCOUNT`, including the default-password-expiry lock), unlock (`UNLOCK_ACCOUNT`) and reset is audited. `GET /users` shows `locked_until` and `failed_attempts`.
- **Device mismatch alert:** a mobile login refused with `DEVICE_MISMATCH` raises the Admin alert `DEVICE_MISMATCH_ATTEMPT`. There is one open alert per worker per site-local day; later attempts add to its count. It appears with the device alerts on the dashboard.
- **Decision register:** DEC-62 (no email notifications), DEC-63 (no weekly scorecard), DEC-64 (no push in v1), DEC-65 (fixed import template only), DEC-66 (login lockout). "Superseded" notes were added in the requirements at §11, §16, §18 step 2 and §20; the client text is unchanged.
### Changed
- **Push is not used in v1:** `FcmPushProvider`, `PUSH_BACKEND` and `FCM_CREDENTIALS` are removed, and the null provider sends nothing and says so. The empty email adapter, `EMAIL_BACKEND`, `SMTP_*` and the Mailpit service in docker-compose are removed too. Existing `.env` files with these keys still load.
- **Mobile contract rev 1.2.0** (`docs/09`):
  - lockout is `403 ACCOUNT_LOCKED` (`429 RATE_LIMITED` and `Retry-After` are removed);
  - §7.4 push is "not used in v1";
  - the scorecard endpoint and the `SCORECARD` entity are removed;
  - gzip is documented;
  - the error example now shows `detail`, which the server has always sent, instead of `message`.
- **Import template:** Company_Settings rows are the real current defaults (from `DEFAULT_COMPANY_SETTINGS`), not EXAMPLE rows, so a fresh import sets them. `ot2_weekdays` is removed from the template, the defaults and the country rules (unused since OT2 became holidays plus the worker's own weekly off day).
### Fixed
- **Effective-dated settings:**
  - A back-dated value (for example the 2026-01-01 defaults imported after a later change) now ends the day before the next value instead of staying open beside it.
  - A value on a date that already has a closed row replaces it instead of failing on the unique key.
### For the mobile team
- See `docs/09` §14 (1.2.0) and the mobile handover document. The app should show the `ACCOUNT_LOCKED` `detail`, must not register for push, and must not call the scorecard.

## [1.26.0] - 2026-11-25
### Changed (Batch 8: Google Maps is the dashboard's only map provider)
- **ADR-033 (revised 25 Nov, owner):** Google Maps only. MapLibre, MapTiler, Nominatim, `maplibre-gl`, `react-map-gl`, `terra-draw-maplibre-gl-adapter` and `VITE_MAP_PROVIDER` are removed. ADR-006's renderer, basemap and geocoding parts are superseded.
  - New dependencies (owner-approved): `@googlemaps/js-api-loader` 2.1.3, `terra-draw-google-maps-adapter` 1.7.0, `@types/google.maps` 3.67.0 (dev).
  - Keys only from `VITE_GOOGLE_MAPS_API_KEY` and `VITE_GOOGLE_MAPS_MAP_ID` (read at build time). Without them: "Map not configured".
  - Runbook 08: billing, Maps JavaScript API plus Geocoding API, referrer restrictions (`localhost:5173`, the Render web URL), daily quotas of 300 map loads and 100 geocodes, a quota alert at 80 %, a budget alert, and a rebuild on Render after changing `VITE_` values.
- **One map interface** (`web/src/features/map/port.ts`), with the Google implementation in `features/map/google/`.
  - The script loads once, lazily, only on pages with a map.
  - One map per page, pooled and reused across tabs, dialogs and in-app navigation. Markers (`AdvancedMarkerElement`) and polygons are updated in place. The Live Map doesn't reload the map on refresh or stream reconnect.
  - Every map opens on the road map; satellite and hybrid come from Google's own control.
  - Worker clusters use a small grid clusterer (`gridCluster.ts`); clicking a cluster zooms into it.
- **Boundary editor:** Terra Draw with its Google adapter. The instant checks are in `geo.ts` (WKT to and from GeoJSON, holes, ring closing and orientation, 7 decimals, too few points, out of range, swapped longitude/latitude, self-crossing). The paste box also accepts `SRID=`, Z and single-polygon `MULTIPOLYGON` WKT.
- **Boundary thumbnails:** lists and previews (Boundaries queue, accommodations, the worksite header) show a small SVG outline. The worksite header's **Show on map** opens the Boundary tab.
- **Place search:** Google Geocoding, only when Search is pressed (or Enter). No autocomplete, no reverse geocoding, nothing stored. A refused search says so in the search box; the map stays.
- **Failure panel:** if Google refuses the key or a quota is used up, the map area shows "Map unavailable today (usage limit reached)" and the rest of the page works.
- **Usage counter:** the browser reports each map created and each search to `POST /api/v1/map-usage`. Settings > **System** (Admin) shows map loads and searches per month for this environment against soft limits (company settings, 7,200 and 2,400 a month), with a warning when one is reached. Migration 0028 adds `map_usage_counters` and the two settings.
- **Backend:** the unused `MAP_STYLE_STREETS_URL`, `MAP_STYLE_SATELLITE_URL` and `MAP_API_KEY` settings are removed. Existing `.env` files with them still load.
### Measured
- A normal session on the demo data (Dashboard, Live Map with a refresh, Worksites, a worksite's Boundary tab with a map type switch, drawing and editing a boundary, one search, Live Map again, Settings > System) costs **1 Google script load, 1 map load and 1 geocode**.

## [1.25.0] - 2026-11-25
### Changed (Batch 9 step 4: reports in SQL, payroll draft in the background)
- **Reports read only the columns they show.**
  - The five attendance reports (daily, monthly, utilization, transportation, late/early departure) use one shared query instead of ORM rows, calculations in chunks and every employee again.
  - Movement, site visits, project summary and job costing select columns. They no longer load each worksite's job items.
  - For October (AE, 580 employees): Daily Attendance 3.5 → 1.2 s, Late/Early 2.9 → 0.65 s, Monthly 1.9 → 0.65 s, Utilization 2.3 → 0.58 s, Project Summary 1.6 → 0.55 s; every report under 2 s.
  - Output is unchanged: all 15 reports were compared row for row before and after.
- **Payroll draft:**
  - Salaries and worksite minutes are loaded in two queries instead of two per employee (1,206 → 48 queries); the records are byte-identical.
  - Draft plus month-end reports: 28–30 s → 17–20 s, 1,501 → 98 queries.
- **Payroll draft as a background job:** `POST /api/v1/payroll/runs/jobs` returns 202 with the job; `GET /api/v1/background-jobs/{id}` gives its status and progress.
  - The Payroll page shows a progress bar, survives a reload, and disables Generate and Re-run while a draft runs.
  - One draft per country and month at a time (409 with the running job's id).
  - A job whose server stopped is marked INTERRUPTED within 2 minutes and can be started again.
  - `POST /payroll/runs` still works as before, for compatibility.
- **The API keeps answering during a draft:**
  - large results are read in parts of 1,000 rows;
  - long loops give other requests a turn;
  - the month-end Excel files are written in a thread;
  - the API freezes its start-up objects for the garbage collector (`gc.freeze()`).
  - Other requests now wait at most about 200 ms; before these changes, 1.25 s.
- **New module `tasks`** (`background_jobs` table, migration 0027, additive). It sits just above `fw.core` in the layers contract. See `docs/modules/tasks.md`.
- **Cold page check (owner):** measured twice. The step 3 increase is real and has two causes:
  - each page's own code file is one more round trip (+30–45 ms);
  - Batch 10 B's three extra Dashboard calls (+~70 ms).
  - The step 2 backend, run next to the current one on the same data, is not faster.
  - Details: `docs/reviews/performance-baseline-2026-11.md`, "After step 4".

### Fixed
- **`.gitignore`:** the Python packaging patterns (`lib/`, `build/`, `dist/`, `var/`, `parts/`, `eggs/`, `env/`…) matched folders of any name anywhere. `web/src/lib` or `web/src/data` would have been silently left out of commits. They are now anchored to the repo root and `backend/`. `data/` is anchored to `/data/`, the client spreadsheets folder, which stays ignored.
  - Checked with `git status --ignored`: nothing that should be tracked was hidden.
  - The ignored set is local secrets (`.env`, `web/.env.local`), caches, runtime storage (`storage/`, `backend/storage/`, `backend/src/storage/`), `web/dist/`, the client files (`data/`, `docs/reference/client-files/`) and an empty `transport` folder of `__pycache__` left by a parked branch.

## [1.24.0] - 2026-11-25
### Changed (Batch 9 step 3: client cache and code splitting)
- **Client cache:** page reads go through one React Query cache (`web/src/api/apiCache.ts`), keyed by URL.
  - Data younger than 30 s is used without a request; for groups, zones, salary revisions, the supervisor list and the reassignment destinations, 5 min.
  - Older data shows at once and refreshes in the background.
  - Any successful write marks every cached read stale, so a page never shows data older than its own last change. Signing in, signing out and a 401 clear the cache.
  - Pages: Dashboard, Worksites, Worksite detail and its Schedule tab, Base Planner, Operational Planner, Employees, Attendance and Approvals. Refresh buttons skip the cache.
  - The approvals badge is one shared, cached query, polled every 30 s.
- **Code splitting:** every page except the Dashboard and Login is its own chunk, preloaded when its menu link is hovered or focused. The first load is 366 KB of JavaScript (115 KB gzipped), was 2.4 MB (597 KB). The map library (about 1 MB) loads only when a map is shown, including on Worksites and Worksite detail.
- **Measured** (`fw_perf`, local): repeat visits draw from the cache in 0–125 ms, so the "repeat visit < 300 ms" target is met. Static files on first load are 126–169 KB on the pages without a map, were 607 KB. See `docs/reviews/performance-baseline-2026-11.md`, "After step 3".
- **Tools:** `tools/perf/run_api.py` takes `FW_PERF_API_PORT` when port 8000 is busy.

### Fixed
- A planner visit served from the cache stayed on "Loading…": the page's first loading state was only cleared on a non-silent load. Found while measuring, before release.

## [1.23.0] - 2026-11-25
### Changed (Batch 10 B: the UI uses the component layer everywhere)
- **No browser dialogs, native date inputs or hand-made overlays are left.** The ui-rules baseline is empty, so `pnpm run lint` now refuses every new one.
  - **Dialogs:** `alert/confirm/prompt` became toasts and `useDialogs()` confirmations. Each confirmation has a title and a clear button ("Delete holiday?", "Roll back"); destructive ones are red and focus Cancel.
  - **Errors:** they show the server's message. A 422 lists each field, through `ensureOk`/`toast.error(err)`, instead of a generic "failed".
  - **Modals:** all 44 hand-made overlays became `Modal`: one header, a footer for the buttons, only the body scrolls, and Escape and focus behave the same everywhere. That includes the job item, copy boundary, assign and approvals dialogs.
  - **Dates:** every date field is the DatePicker.
- **Menu grouped by area:** Overview · Planning · Workforce · Sites · Time & Pay · Reports · Admin.
  - Items and groups a role can't use are hidden.
  - New entries: Staffing Gaps (the Operational Planner's gap list) and Accommodations (the Worksites tab).
- **Sidebar:** the collapse button moved to the sidebar footer, so it no longer covers the logo, and the collapsed state is remembered.
- **Favicon and titles:** a favicon from the app logo (SVG, 32 px PNG, apple-touch-icon), and a page title per route in the browser tab.
- **Dashboard: pending actions and alerts grouped by type.** Each section has a count, the 5 most recent items and "View all". The sections are: document expiry, cover needed, leave, reassignment and attendance approvals, pending visits, boundary queue, unassigned worksites (Admin) and device/tracking alerts, each shown only to the roles that can act on it. "View all" opens the right Approvals tab (`?tab=`).
- **Scrolling:**
  - one thin, hover-only scrollbar style for every scroll area;
  - the Operational Planner roster scrolls once, inside the table, with a sticky header;
  - the job page boundary map no longer captures the page's scroll (cooperative gestures) and fits the window;
  - the Reports pages show an EmptyState instead of an empty scroll box.
- **API:** `GET /pending-visits` takes an optional `limit`, used by the dashboard preview. Without it, the response is unchanged.
### Fixed (screenshot review on the demo data, 1440×900 and 390×844)
- **Phones:**
  - the sidebar covered most of the screen; below 768 px it is now a drawer opened from a menu button in the top bar, and it closes when you pick a page;
  - page padding is smaller on small screens.
- **Operational Planner:**
  - on phones the controls squeezed the roster to nothing; below 1024 px the page now flows normally and the roster scrolls sideways;
  - on desktop the title no longer wraps into four lines.
- **Date fields:**
  - in forms they were shorter than the inputs beside them; they now match, using the new DatePicker size `lg` (36 px);
  - clicking in a date field now opens the calendar; before, only the small calendar icon did.
- **Worksite page:** the header no longer squeezes the job name and badges.
- **Worksites:** the header buttons and filters wrap instead of running off the screen, and the search box keeps a usable width.
- **Settings:** the "As of" date no longer overflows on phones.
- **Padding:** Documents, Pending Visits, System and Worksites no longer add their own padding on top of the page's.
- **Dashboard:** sections no longer stretch to the tallest one in their row.
- **Dialog descriptions** are now a `div`. A `p` could not hold the Add Worksite step list, which was invalid HTML and logged a React warning.
- **Small fixes:**
  - the attendance detail's input hash wraps;
  - the payroll breakdown shows "AED 0.00", not "AED -0.00".

## [1.22.0] - 2026-11-25
### Added (owner decisions of 25 Nov 2026)
- **Base Planner templates become scheduled work** (ADR-032). From tomorrow to `roster_materialise_weeks` ahead (new company setting, default 4), each template produces real `scheduled_work` rows with `source = TEMPLATE`.
  - **When:** a daily worker job, saving a template, and approving leave (including leave imported as approved).
  - **Idempotent:** one row per employee, job item and date. Running twice in a day changes nothing, and runs never interleave (advisory lock).
  - **Manual work is never overwritten.** Only untouched rows (`TEMPLATE`, `ACTIVE`, version 1) follow a template change; anything changed in the Operational Planner, a cover or a reassignment is kept.
  - **Same rules as the Operational Planner:** weekly off and approved leave skipped (leave keeps its cover), template, item and worksite dates, inactive employees and items, budget-only staff types, PERMANENT/REMOTE rules; over the standard day is logged, not blocked; public holidays are scheduled (worked hours become OT2).
  - **Operational Planner on template rows:** removing a base worker cancels the TEMPLATE row in place, a cover marks it REASSIGNED, and restore/undo put it back. Planner edits now reach the phones (they did not before).
- **ABSENT at day close.** A new daily job (before pending visits) calculates every employee with scheduled work and no attendance events: **ABSENT**, the planned hours as missed hours, flag `NO_ATTENDANCE_EVENTS`, **pending review**. It shows in the attendance review, the dashboard and the approvals count. Not for approved leave, the weekly off, or no scheduled work.
- **Manual attendance times** (`POST /attendance/manual-times`; Admin, and Engineers for their crew chain), from the attendance drawer ("Enter times"). For a dead phone: first site entry and last site exit, optional accommodation departure and return, and a required reason. The day gets a new calculation version (flag `MANUAL_TIMES`, back to review); earlier versions are kept; audited. Refused for a future day or a payroll-locked day.
- **Payroll:** approved ABSENT days are deducted at basic / 208 (DEC-30). Absences still pending review are not deducted and appear as `PENDING_ABSENCE` issues ("n absences pending review" on the payroll page).
- **The master import reads the Leave sheet.** New optional `status` column (APPROVED by default, or PENDING). Validated like the Admin leave import (worker, leave type, dates), plus to ≥ from and no overlap with open leave or another row; re-importing the same leave is UNCHANGED. Approved leave takes the worker off the materialised roster and raises the usual cover alert.
### Fixed
- **Payroll deducted approved leave days twice.** The engine records an approved leave day's planned hours as shortfall, and payroll counted that shortfall as well as the leave itself: unpaid leave was deducted twice, and paid leave once, unless the run treated leave as paid. Found by the demo re-run, where October's draft for worker 2023 had 24 h of unpaid leave plus 26.1 h of shortfall. Payroll now never counts shortfall on an approved leave day; the leave lines decide (DEC-30).
- **Restoring a removed base worker** left the cancellation in place; it now restores the worker.
- **Coverage and roster** skipped public holidays for template workers and did not skip their weekly off; they now match the materialised rows.
- **Reset database** (Settings) clears the new manual-times table.
- **A planner scenario test had a fixed week** (23–29 Nov 2026) that turned into the past; it now uses a week after next.

## [1.21.0] - 2026-11-25
### Added (Batch 10 A: UI component layer, ADR-031)
- **`web/src/ui`, the app's building blocks** with stable props, built only on what is already installed (no new dependency):
  - Button and IconButton, Modal, ConfirmDialog (default and destructive);
  - toasts (success, info, warning, error) and AlertBanner;
  - DatePicker, DateRangePicker (with presets), Calendar (holiday and leave markers);
  - ScrollArea, TextField and TextArea, NumberField, Select, LookupSelect;
  - Tabs, Menu, Tooltip, Badge and CountBadge, EmptyState, Skeleton, PageHeader.
  
  Keyboard behaviour throughout: focus stays inside dialogs and returns to the opener, and the destructive confirm focuses Cancel. Calendar arrows, Page Up/Down and Home/End work, Tabs and Menu use arrow keys, and Escape closes popovers.
- **Dialogs and toasts as hooks:** `useDialogs().confirm/prompt` returns a promise, so `window.confirm` becomes one `await`. `useToast().error(err)` shows the server's message, and for a 422 lists each field (`ui/errors.ts` reads every error body shape the API sends).
- **Tokens in one file** (`ui/tokens.css`): colour, spacing, radius, type, shadow and layer variables, mapped to `fw-*` Tailwind names. The light theme is defined now; dark can follow by redefining the variables. The thin `.fw-scroll` scrollbar shows on hover or keyboard focus.
- **Dates:** ISO values and UTC arithmetic (no time-zone day shifts), "25 Nov 2026" display, day-first typing ("25/11/2026", "25 Nov 2026" or ISO), with min/max and a readable error.
- **`/dev/ui` gallery** (development builds only, not in the production bundle): every component and state.
- **UI rules check** (`pnpm run check:ui`, also part of `pnpm run lint`). It fails on a new `window.alert/confirm/prompt`, `<input type="date">`, hand-made `fixed inset-0` overlay, or import of a library the ui layer wraps (`clsx` and `tailwind-merge` outside `ui/cn.ts`; `react-dom` portals outside `ui/overlay.tsx`). The 157 existing violations in 34 files are listed in `web/scripts/ui-rules-baseline.json` for Batch 10 B to remove.
- **Web tests in CI:** `pnpm run test` now runs in the frontend job. A small TypeScript loader (`web/scripts/register-ts.mjs`, using the installed `typescript`) lets `node --test` run `.tsx` component tests. 93 new tests: components, dates, errors, toasts, keyboard, popover placement, the rules and the gallery. The 33 existing web tests now run in CI too.
### Fixed
- **Reassignment notice tests failed after local midnight.** The tests built their dates from the machine's day, while the 3-day notice rule counts from the site's day (`site_today()`). Between local and Dubai midnight, a "2 days' notice" request was really 3 days and was accepted. The tests now use the site clock.

## [1.20.0] - 2026-11-25
### Added (demo activity generator)
- **`tools/seed_demo_activity.py`** fills the demo import with activity from 1 Oct 2026 to yesterday, through the real pipeline. It never writes attendance, site visit, pending visit or payroll rows itself. In order:
  - Base Planner templates, then Operational Planner shifts (each validated first, 30 days ahead);
  - one `DEMO-<tally>` phone per worker through the mobile login, and consent;
  - each worker-day's phone events uploaded through the batch upload service, with the app clock at that evening;
  - the day close (attendance for every planned worker, then pending visits and reminders);
  - engineer 2901's approvals for days older than 7 days;
  - the October payroll draft, not approved.
  
  The planted scenarios P1–P12 come from `tools/demo_data/demo-data-generator-prompt.md`. Options: `--from`, `--to`, `--seed` (deterministic), `--dry-run`, `--reset-generated`. Refused for production and for a database not on this machine. The demo's three leave rows go through the Admin leave import, because the master import doesn't read the Leave sheet yet.
- **Runbook** `docs/runbooks/07-demo-data.md`: reset → import → generate → passwords → simulator.
### Fixed
- **Late arrival / early departure report:** it compared the UTC clock time of the first entry and last exit with the planned site times. In Dubai that meant nobody was ever late and everyone left about four hours early. It now converts to the employee's country time zone first.
- **Pending visits closed by a late upload (DEC-32):** day-close detection only runs for the day just closed, so a phone batch uploaded later recalculated the day but left its pending visits OPEN (and escalating). After recalculating, the event listener now closes the worker's OPEN pending visits for that day whose site has a counted visit (`VISIT_CONFIRMED_LATE`) and resolves their reminder alerts. It never opens new ones.
- **`tools/reset_database.py`** failed on the current schema: since 0017 the Admin has no employee row. It now runs the same reset as Settings > Reset database (shared `reset_to_bootstrap_state`) and refuses production.
- **Phone event upload uses the app clock** (`get_system_clock()`) for the 5-minute and 7-day checks and for `server_received_at`, like the rest of the backend. In production that is the system clock, so nothing changes there; a frozen clock can now replay a past day.

## [1.19.0] - 2026-11-24
### Changed (Batch 9 step 2: quick wins)
Measured locally on the `fw_perf` dataset with the step 1 scripts: Operational Planner 80.8 s → 1.4 s, Base Planner 18.7 s → 0.69 s, Dashboard 12.2 s → 0.25 s, and no page over 1 s cold apart from the Operational Planner. The "After step 2" columns in `docs/reviews/performance-baseline-2026-11.md` have the details; the raw results are in `docs/reviews/perf-2026-11/after-step2/`.
- **Approvals badge from a count.** New `GET /approvals/counts` (Admin, Engineer, Superintendent): pending leave, reassignments and attendance rows from count queries, with the inbox's scope rules, and nothing written. The top-bar badge (still polled every 30 s) and the Dashboard use it; before, they loaded the whole inbox (9.8 MB in the measuring data) to read one number.
- **Approvals inbox paged.** `GET /approvals` takes `type` (`leave`, `reassignments`, `attendance`), `limit` (1–200, default 50) and `offset`, and returns `totals` per type for the selected status. Without `type` it returns the first page of each list (the old shape). The Approvals page fetches only the open tab, 50 rows at a time, with Prev/Next. The "All history" status now really asks for all statuses (it fell back to pending before). Attendance rows no longer load their calculation twice.
- **Pending reassignments whose start date has passed** are left out of the pending list, its total and the badge, so the three agree. They were already shown as expired when the list was read.
- **Occurrences are no longer loaded with job items** (`JobItem.occurrences` is loaded only where it's asked for). Every query that touched a worksite or job item used to load all their occurrences, 13 months ahead: the worksite list, destinations, both planners, the reports and the reassignment list. The worksite list also no longer loads items and supervisors it doesn't return.
- **New `GET /worksites/{id}/occurrences` and `GET /job-items/{id}/occurrences`** with a required `from_date`/`to_date` (at most 366 days). Each returns the occurrences whose window overlaps the range, plus a `summary` of the whole schedule (count, planned hours, first and last window, months, roles); 404 outside the user's scope. The worksite Schedule tab loads one month at a time, only when it's opened, and its month picker drives the calendar and the table. Its totals now cover the whole schedule; before, they counted only the first 500 occurrences.
- **`GET /occurrences` checks scope (DEC-57):** a worksite or job item outside the caller's scope is a 404, and without either filter only worksites in scope are listed. It had no scope check before.
- **Planners follow DEC-57.** Base Planner, Operational Planner coverage and `/schedule/coverage` show only the worksites in the user's scope; the Operational Planner roster shows the user's directory (own crew plus workers on their worksites). Admin sees everything, as before. Reassignment destinations still list all active worksites.
- **Planners read settings once per country** (budget-only roles and, in `/schedule/coverage`, public holidays) instead of once per worksite: 400 queries fewer per load. Coverage loads only the week's shifts of the items in view, and the month or quarter only for items that need it.
- **Staffing gaps run a fixed number of queries**, whatever the number of leave days or gaps (one query for existing covers instead of one per day and item).
- **Compressed responses:** gzip for responses of 1 KB or more when the client sends `Accept-Encoding: gzip` (level 6). Not for the live SSE stream, PDF or xlsx. The coverage response goes from 4.4 MB to 130 KB on the wire. Note for the mobile team in `docs/mobile-team-notes-2026-11-19.md` (no contract change).
- **The Dashboard makes its calls in parallel**; its previews ask for 4 pending leave and 4 pending reassignment requests, with the real counts in the headers.
- `tools/perf/measure_pages.py` also measures the worksite Schedule tab and the Approvals page.
### Removed
- `payroll/repository.get_worksites_and_items` (no callers).

## [1.18.0] - 2026-11-24
### Added (Batch 9 step 1: measuring, no speed fixes)
- **Request timing** (`fw/core/perf.py`, settings `PERF_TIMING_ENABLED`, `PERF_SLOW_QUERY_MS`): a `Server-Timing` header (app time, DB time and query count, most repeated statement) and a `request_timing` log line per request with the route template, status, duration, queries, DB time, repeats and slow statements (SQL text only, never values, never ids). Off by default; dev and staging only, ignored when `APP_ENV=production`. The live stream is not timed.
- **Scaled mock dataset** (`tools/perf/seed_perf_dataset.py`) in a separate local database `fw_perf`: 600 employees, 400 worksites, 1,500 job items, 339k occurrences, 238k scheduled work rows, about 41k attendance days, 426k phone events and an October payroll draft. Mock names and Tally IDs only; refuses any database not named `*_perf`, any non-local host and production.
- **Measuring scripts** (`tools/perf/measure_pages.py`, `measure_api.py`, `run_api.py`): Chromium page loads (cold and warm) with request counts, chain depth, bytes, slowest endpoint and time to usable; an endpoint replay with p50/p95 against docs/14. `--read-only` for deployed sites (only GETs and the login leave the client; refused without it for a non-local URL); host, region, network and start time recorded; credentials only from `FW_PERF_USER` / `FW_PERF_PASSWORD` and never written.
- **Baseline report** `docs/reviews/performance-baseline-2026-11.md` with the raw results in `docs/reviews/perf-2026-11/`, and runbook `docs/runbooks/06-performance-measurement.md`.
- Dev-only dependency: Python `playwright` 1.65.2 in a separate uv group `perf` (not installed by CI or the app).

## [1.17.0] - 2026-11-24
### Fixed
- **A payroll draft failed with a 500 when any employee had scheduled work in the month.** `generate_draft_run` built each record's job cost allocations while the record had no id yet, so `job_cost_allocations.payroll_record_id` was null. Every ACTIVE scheduled work row linked to an occurrence (all standing assignments) triggers it, so the demo's October payroll would have failed. The record gets its id up front. Present since phase 11; found while seeding the Batch 9 measuring dataset. Test: two worksites, 3 and 1 days of scheduled work, the cost is split 3:1 and adds up to the record's final staff cost.

## [1.16.0] - 2026-11-24
### Fixed
- **Payroll record breakdown showed Basic, Special Allowance, Fixed OT and Bonus as 0.00.** A run stored only `basic_salary` (nested under `snapshot.salary`) while the record read top-level keys, and the other components were not stored. A run now stores all six components (basic, special allowance, fixed OT, bonus, telephone, housing/transport) that add up to `salary_portion`, and the record returns them. Older runs fall back to the nested basic and then to the salary row the run used (`salary_id`), else the employee's row in effect at the end of the period. The record view shows all six (telephone and housing/transport are new) and no longer reads the snapshot itself.
- The payroll report read the same snapshot with wrong keys (`bonus_amount`, `housing_allowance`, basic falling back to `salary_portion`), and the provisions report read `provisions_breakdown` while runs store `settings.provisions`, so each provision was 0. Both now use the same reader.
- **Viewing a payroll run regenerated its 11 month-end reports** (files and DRAFT rows, even for an approved run): the run detail read published `PayrollRunCreated`. The event is now published once when a draft is created or re-run.
- The payroll run cards (Gross, Net, Employer Cost) read fields the API never returned and showed 0; they read the run's totals now.
- **Money shows the currency, never "$".** Payroll runs have `currency` (the country's `currency` setting, stored with the run; AED for AE, SAR for SA). One web formatter (`features/format/money.ts`) shows "AED 1,234.56" on the payroll screens (runs, records, record breakdown, revision lines, budget vs actual), salary structures, the employee salary cards and create form, worksite budgets (list, detail, planners) and the budget panels (job item checks, Add Worksite review, planned vs actual). The planner worksite rows carry `country` for this.
### Changed
- The worksite renewal reference is labelled **"Contract renewal no. (label only)"** with a tooltip that it does not select the salary revision (BR-JB-08), in the Add Worksite wizard, its review, the worksite page and the Worksites list.
- **Settings > Budget-Only Roles** takes its options from the staff type list (active values, `GET /lookups/staff_grade_description`) instead of the deprecated `/settings/staff-grades`, which mixed in values not in the list. A saved value not in the list (e.g. "QA/QC Engineer" from a settings import) is flagged "Not in the staff type list" with **Add to list** (Admin; near matches ask first) and **Remove**. Matching ignores case and spaces, like the list.
- `test_mobile_sync`'s base-planner test creates its own worksite and job item; it used the first active worksite left by other tests and failed when that one had no job item scheduled today.

## [1.15.0] - 2026-11-23
### Added
- **Batch 5.1 B: Add Worksite wizard** (handover 6.1 B; regression 5). Three steps: worksite, job items, review. Nothing is saved until "Create worksite", which sends one `POST /worksites` with `job_items[]` (0-50) and `supervisor_ids[]`; the worksite, its supervisors and its items (with occurrences and audit entries) are saved in one transaction or not at all.
  - Step 1: job number checked live (`GET /worksites/job-number-check`: format, duplicate, Outdoor/Indoor/Water feature), name, group and zone, customer type, country, contract dates, renewal reference, salary revision of that country, manual budget and an optional pick of active supervisors.
  - Step 2: one row per item with Add, Duplicate and Remove (codes A, B, … Z, AA), the same fields as the job item form and a checks panel per row: activities and hours per year, expected occurrences and eligible employees (red at 0) from `POST /job-items/validation-preview`, and man-hours and cost (Admin) from the budget preview. The break is shown as "from time rules".
  - Step 3: review with the contract labour budget (sum of the rows) next to the manual budget, and warnings (no boundary, no supervisor, 0 eligible employees, budget warnings).
  - A failed create returns to the step and row at fault: row errors carry `field: "job_items[N].<field>"` and `row`, schema errors `body.job_items.N.<field>`, a bad supervisor `field: "supervisor_ids"`.
  - After create the worksite page shows "Worksite created" with **Draw boundary now**.
- `JobItemFields` and `JobItemChecksPanel` are shared by the wizard rows and the job item modal, which now shows the server checks (eligible employees, expected occurrences) and suggests the next free sub-item code.
### Changed
- **Admin-only actions (DEC-61, owner decision 23 Nov 2026).** Only Admin creates worksites and employees, runs the Master Data Import (every `/imports` route, template included) and the boundary file import (`POST /boundaries/import`), adds groups and zones, and deactivates or reactivates anything: `is_active` on `PATCH /job-items/{id}` and `PATCH /accommodations/{id}` is now refused for other roles (403). The web hides the menu item, Import links (Worksites, Employees, Planner, Operational Planner), Add Worksite, Add Employee, the accommodation Activate/Deactivate button, the boundary file import button and group/zone "Other – add new…" from Engineers; the Imports page says "Admin only".
- Engineers edit and add job items, generate occurrences and assign or remove supervisors only on worksites in their DEC-57 scope (404 outside it); the role alone was checked before.
- `POST /worksites` with a malformed job number returns 422 `INVALID_JOB_NUMBER` instead of a 500.
### Removed
- The Engineer import paths: skipped salary sheets and money settings (`SHEET_ADMIN_ONLY`, `SETTING_ADMIN_ONLY`), the Engineer template, the preview filter and the commit/rollback role checks; `fw/rules/imports/access.py` is deleted. A test keeps the salary sheets Admin only by role.
- The Add Worksite form's inline job items, which were posted one by one after the worksite and whose failures were ignored.

## [1.14.0] - 2026-11-23
### Changed
- **Tests use their own database.** Tests ran against `fw_db`, the working database, which is how test rows got into local data and how the reset-database test wiped settings. `tests/conftest.py` now points the app and every test session at `fw_test` (or `FW_TEST_DATABASE`, which must end in `_test`), drops, recreates and migrates it at the start of every run, and refuses to run against any other database. CI's backend job now has a PostGIS service and runs the database tests it used to skip.
- **Managed lists, owner decision (DEC-60 and ADR-030 amended).**
  - Staff type and grade dropdowns are plain dropdowns: no "Other – add new…", no search. The record's current value stays selectable, marked "(not in list)" when it has left the list.
  - Staff types: only Admin adds, deactivates and reactivates them, in Settings > Managed Lists (`POST /lookups/staff_grade_description` is Admin-only).
  - Grade codes come only from salary revisions: the grade list is the base codes with a line in an active revision and follows the revisions (migration 0025, source `REVISION`). `POST`/`PATCH /lookups/grade_code` return `GRADE_FROM_REVISION_ONLY`. Screens refuse a grade with no line in an active revision (`UNKNOWN_GRADE_CODE`).
  - Imports: a grade on Employees or Job_Items with no line in an active revision, in the database or the same file, is an error with a hint. Grades are never added to a list by import (`GRADE_ADDED_TO_LIST` removed).
### Added
- **Groups and zones: "Other – add new…"** in the Add Worksite form and the worksite edit (Admin, Engineer). A group needs only its name and gets the next free 3-digit code; a zone needs code and name. Duplicate names and codes are refused, near names ask "Did you mean …?". New group codes in imports and the API must be 3 digits. The worksite edit can now change the group and zone.
### Removed
- The `NO_REVISION_LINE` warning, `GRADE_ADDED_TO_LIST`, and the Add Worksite group/zone fields that created the group or zone only when the worksite was saved.

## [1.13.0] - 2026-11-23
### Added
- **Batch 5.1 C: managed lists for staff types and grade codes (DEC-60, ADR-030).** Client meeting 19 Nov, item 2.
  - Table `lookup_values` (migration 0024), seeded from the former controlled list and the values already on employees, job items and revision lines.
  - `GET/POST /lookups/{list_key}` and `PATCH /lookups/{list_key}/{id}`: Admin and Engineer add values (duplicates refused ignoring case and spaces; near matches and aliases ask "Did you mean …?" and need "Add anyway"; grades must be base codes, with a warning when no active revision has a line); Admin deactivates; nothing is deleted; all audited.
  - `<LookupSelect>`: a searchable dropdown with "Other – add new…", used for staff type and grade in the job item form, Add Worksite rows, employee create and the employee profile edit. Settings has a Managed Lists tab; the budget-only checklist reads the staff type list.
### Changed
- Job items, employee create/update, grade change and profile details validate staff type and grade against the active lists (`INVALID_STAFF_GRADE_DESCRIPTION`, `UNKNOWN_GRADE_CODE`, `LOOKUP_VALUE_INACTIVE`, with hints). Employee create used to accept any staff type.
- Imports: an unknown staff type is now an **error** with a hint (Job_Items used to warn and save it); aliases now also resolve on the Employees sheet (they failed as `INVALID_ENUM`); a new valid grade code is a warning (`GRADE_ADDED_TO_LIST`) and joins the list on commit. The downloaded template's Lists sheet carries the current lists.
- "Reset database" clears the lists and re-seeds the staff types.
- `GET /grades` and `GET /settings/staff-grades` return the managed lists (deprecated).
- The employee page shows an Engineer's staff type read-only, like Supervisor and Superintendent (the server already refused the change).
### Removed
- The hard-coded staff type list (`CONTROLLED_SGDS`, `CONTROLLED_STAFF_GRADE_DESCRIPTIONS`); it is only the seed now (`SEED_STAFF_TYPES`).

## [1.12.0] - 2026-11-23
### Added
- **Batch 5.4: job budget and man-hours (DEC-59, ADR-029).** One pure rule (`fw.rules.jobs.budget`) gives activities/year, man-hours and cost per job item; the new `budget` module loads everything in bulk.
  - Job item responses carry `budget` (activities/year, hours and, for Admin, rate and cost in the current contract year); worksite detail carries `budget_totals`.
  - `POST /worksites/{id}/job-items/budget-preview` and `POST /job-items/budget-preview`: live figures for an unsaved item (nothing saved). The job item form and the Add Worksite rows show them while typing.
  - `GET /worksites/{id}/planned-vs-actual`: per item and per month, hours for every role that can see the worksite, money for Admin. The worksite page has a Planned vs actual section with a date range; the job items table has activities/year, annual hours, annual cost (Admin) and a totals row.
  - `salary_revision_lines.telephone_allowance` and `housing_transport_allowance` (migration 0023, default 0), with optional import columns after `notes`.
### Changed
- **Planned figures change.** Fortnightly items were counted twice (the budget ignored `period_interval`); items now count only inside their own dates and the worksite contract dates; hours are pro-rated by day instead of "days since start / 365, capped at 1".
- **Hourly rate** = (salary portion + the revision line's own provisions + gratuity + leave salary) x (1 + `hr_overhead_rate`) / `standard_ot_divisor_hours`, built with payroll's formulas; no hard-coded 1.05 or 208 (`SETTING_MISSING`). Revision detail `planned_hourly_cost` uses the same rule. Where a grade's revision provisions differ from the payroll settings, planned vs actual says so (`PROVISIONS_DIFFER_FROM_PAYROLL`).
- `GET /payroll/budget-vs-actual` moved to the budget module (same path, Admin only); it takes `from`/`to` (default: each worksite's contract year), returns items and months, and `prorated_budget` is now the planned cost for the period. Actual hours: site visits on approved days; actual cost: approved payroll allocations split over items by approved hours; budget-only staff: actual = planned. The Payroll Budget tab and the Job Costing report use it.
### Fixed
- Project Attendance Summary counts actual man-hours only on approved days, and no longer assumes 8 hours for a scheduled entry.
### Removed
- `calculate_revision_planned_hourly_cost` (with its 1.05/208 defaults) and the old budget loop in `PayrollService`.

## [1.11.0] - 2026-11-23
### Changed
- **Batch 5.3b: grade codes are stored as the base code everywhere (DEC-58, ADR-028).** Revision lines, job items and employees hold `G3C`; revisions show `G3C-2026` through the new `salary_revisions.suffix_label` (default: year). Input accepts `-YYYY`, `-R<n>` and `G5-C`; anything else (e.g. `G3C26`) is rejected with `INVALID_GRADE_CODE` instead of being guessed. Migration 0022 strips existing suffixes (stops on duplicates).
- **Payroll provisions now follow settings.** Payroll runs and salary structures read the seeded setting names (`provision_*`, `standard_ot_divisor_hours`) instead of names that never existed, so provisions are 842 (132+65+30+550+65) instead of the hard-coded 550. **Existing draft runs will change when recalculated.** Approved runs are unchanged. No money setting has a fallback any more: a missing one stops with 422 `SETTING_MISSING`.
- **Admin only (DEC-47):** payroll runs, run detail, issues and records, salary revision detail and its template export. The worker's own payslip (`/mobile/me/payroll`, `/payroll/my-records`) is unchanged.
- Engineers' imports skip the salary sheets (`SHEET_ADMIN_ONLY`) and money/rate settings and `default_password` in Company_Settings (`SETTING_ADMIN_ONLY`) without storing their values; their template leaves them out; they cannot commit or roll back a batch that writes such data.
- Site-local dates for the budget, salary structures and salary/revision defaults.
- "Reset database" now re-seeds the default company settings (the migration 0003 values), so payroll works straight after a reset without reimporting Company_Settings.
### Fixed
- Budget no longer prices unknown grades at 10.00/hour: such job items are left out of the totals and listed as `MISSING_GRADE_RATE` warnings (shown on the Budget tab).
- Editing or deleting a future salary row re-copies the amounts of later CREW_BREAK rows; CREW_BREAK rows cannot be edited or deleted directly (`CREW_BREAK_ROW_LOCKED`); the audit keeps the full row. Past and current rows stay locked.
- profile-details: grade validated; Staff Grade Description must be on the controlled list and is locked for Supervisors, Superintendents and Engineers (meeting 19 Nov); a future `effective_from` is rejected (`FUTURE_PROFILE_CHANGE_NOT_SUPPORTED`); `actor_role` is stored.
- Grade dropdowns (job items, employees, employee detail, Add Worksite) now list every grade in use (G8–G25 included) from `GET /grades`; the Add Worksite form no longer pre-fills "Gardener Helper"/`G3C`.
### Added
- `GET /grades`, `employee_attribute_history.actor_role`, budget `warnings[]`/`missing_rate_hours`, revision `display_grade_code`.
- Tests: grade parsing, budget warnings, CREW_BREAK resync and locks, Admin-only salary data and payroll, Engineer import skipping, profile-details, `SETTING_MISSING`, worker mobile payslip still available.
### Removed
- `tools/demo_data/antigravity-demo-data-generator-prompt.md` (replaced by `demo-data-generator-prompt.md`).

## [1.10.0] - 2026-11-20
### Fixed
- **Batch 5.3a: dashboard cards always showed 0.** The web read field names `/dashboard/summary` does not return. A typed mapper (`web/src/features/dashboard/summary.ts`, with tests) now reads the API's fields; no API field was renamed.
### Added
- `/dashboard/summary` returns `pending_visits_escalated_count` (open visits at least `pending_visit_escalation_days` past due; additive, web only). The pending-visits card shows it as the escalated badge.
- Backend tests: non-zero dashboard counts (`test_dashboard_summary.py`) and the demo workbook previewing with 0 errors (`test_demo_import_preview.py`).
- Mock demo data committed in `tools/demo_data/` (workbook, assignments, 5 route files, generator prompt). `.gitignore` keeps `docs/reference/client-files/` ignored.
### Security
- Personal-data scrub: real client names and Tally IDs in tests, seeds, demo scripts, docs, the mobile proxy and the import template examples replaced with the demo's mock people (2001-2024, 2701-2704, 2801-2802, 2901-2902). Git history is not rewritten.
### Removed
- `tools/demo_data/handover-2026-11-19.md` (an outdated copy of the handover).

## [1.9.1] - 2026-11-20
### Documentation
- Rebased on main after PR #25; handover status and queue updated (Batch 5.3 split into 5.3a and 5.3b; Batch 9 note on caching `AccessScope`).
- Added `docs/handover-addendum-batches-8-10.md` (Batches 8, 9 and 10).
- Handover updated with section 0 (changes since 19 Nov, owner decisions of 20 Nov, DEC-57 rule, PR #23 regressions, new work queue); the handover's Batch 6 is renamed Batch 7.
- Added the post-merge review of PR #22/#23 (`docs/reviews/review-pr22-23-2026-11-20.md`), the 19 Nov audit, the mobile-team notes, the client meeting notes of 19 Nov and `CLAUDE.md`.
- Demo data built from client files (`tools/demo_data/` workbook, assignments, routes) is git-ignored (golden rule 8).

## [1.9.0] - 2026-11-20
### Fixed
- **Batch 5.2: DEC-57 worksite scope applied everywhere (ADR-027).** Non-admins no longer see an empty Worksites page once supervisors are assigned. Worksites, the planner job-item picker, Employees, Attendance, Live Map, Pending Visits, the dashboard and all 15 reports now use one scope service (`AccessScope`) and the same rule.
- Worksite detail and the worksite supervisor list had no scope check (any user could read any worksite by ID); they now return 404 outside scope.
- `/live/trail/{id}` and the employee DSAR export let a user with an empty scope through; both now refuse.
- Pending-visit explain/reschedule/close now check scope.
- Dashboard pending-approvals counts were not scoped and counted reassignments with a status that does not exist; both fixed.
### Added
- `Worksite_Supervisors` import sheet (`job_number`, `supervisor_tally_id`, `notes`; role must be SUPERVISOR; commits after Worksites and Employees; idempotent). Template regenerated.
- Admin "Assign supervisors from crews" review (`GET /worksites/supervisor-proposals`, `POST /worksites/supervisors/bulk-assign`), "Unassigned only" Worksites filter, and an unassigned-worksites dashboard warning.
- `GET /job-items/destinations`: reassignment destinations list every active worksite (no costs).
- `read_only` flag on employee, attendance, leave and reassignment responses; the web hides edit and approve controls for cross-crew workers, and the server refuses attendance decisions on them (`READ_ONLY_SCOPE`).
- Company setting `scope_site_worker_window_days` (default 31, PROPOSED_DEFAULT).
- Deactivating a supervisor or changing their role ends their worksite assignments (audited, automatic).

## [1.8.0] - 2026-11-20
### Added
- Operational Enhancements & Access Control Hardening (Batch 6):
  - Access Control & Financial Privacy (DEC-47, DEC-51):
    - Excel workbook imports and exports (`/worksites/export`, `/employees/export`, `/imports/*`) strictly restricted to `ADMIN` and `ENGINEER`.
    - Worksite budget amounts, planned labor costs, and pricing figures strictly restricted to `ADMIN`; masked as `null` for all other roles.
    - Salary structures table and salary history APIs restricted to `ADMIN` only (403 for non-admins).
  - Multi-Supervisor Worksite Scoping (DEC-57, ADR-026):
    - Migration `0020_worksite_supervisors.py`: Created `worksite_supervisors` table enabling multiple field supervisor assignments per worksite.
    - Added supervisor assignment management endpoints: `GET`, `POST /api/v1/worksites/{id}/supervisors`, and `DELETE /api/v1/worksites/{id}/supervisors/{supervisor_id}`.
    - Operational scoping: Field supervisors now see only their assigned worksites and workers assigned to their worksite's job items.
    - Web UI: Added "Assigned Field Supervisors" management card in `WorksiteDetail.tsx`.
  - Employee Profile Governance & Attribute History:
    - Migration `0021_employee_attribute_history.py`: Created `employee_attribute_history` table for immutable change auditing of designation, grade code, and driver status.
    - Added `PATCH /api/v1/employees/{id}/profile-details` and `GET /api/v1/employees/{id}/attribute-history`.
    - Controlled dropdowns for `staff_grade_description` and `grade_code` across employee creation and edit modals.
    - Role-locked designations for `SUPERVISOR`, `SUPERINTENDENT`, and `ENGINEER`.
    - Added confirmation prompt before modifying employee hierarchy reporting lines.
    - Added optional initial salary structure configuration inline during employee creation.
  - Salary Structures DEC-39 Cost Breakdown & Future Revision Governance:
    - Added column sorting across all headers in `SalaryStructures.tsx`.
    - Added full on-screen DEC-39 cost breakdown: Basic Salary, Allowances, Total Salary Portion, Gratuity `((Basic/365)*30)`, Leave Salary `(Basic/12)`, Monthly Provisions (sum of company settings provisions + Gratuity + Leave Salary), Total Staff Cost, HR Overhead (5%), and Final Cost.
    - Implemented `PATCH` and `DELETE /api/v1/employees/{id}/salary/{salary_id}` for editing and deleting future-dated salary revisions prior to activation (strictly guarded by `effective_from > site_today(country)` per DEC-06).
    - Revision grade line suffixing: revision lines append `"-{rev_code}"` with fallback base grade code matching in side-by-side diffs and template exports.
  - Worksite & Accommodation UX:
    - Worksite Excel export includes secondary `Job_Items` sheet tab.
    - Dynamic Group & Zone creation (`+ Add New...` / "__NEW__").
    - GPS "My Location" centering button on Polygon map editor.
    - PlaceSearch autocomplete integration on Accommodation boundary drawing.
    - Inline job items creation within the Add Worksite modal.
    - Accommodation Edit and Activate/Deactivate actions.
  - Documentation & ADRs:
    - Created `ADR-026` (`docs/decisions/026-worksite-scoping-salary-cost-transparency.md`).
    - Updated `docs/decisions/decision-register.md` (DEC-47, DEC-51, DEC-57) and `docs/07-data-model.md`.

## [1.7.3] - 2026-11-19
### Fixed
- Hotfix: Worksite Page Errors & Job Item Creation Validation:
  - Web UI:
    - Fixed 404 error on `Worksites.tsx` by updating endpoint `/api/v1/payroll/salary-revisions` to `/api/v1/salary-revisions`.
    - `JobItemModal`: Added required `start_date` input (defaulted to worksite start date or current date) and optional `end_date` input, sent on create and edit.
    - `JobItemModal`: Replaced planned grade text input with required `<select>` populated from active salary revision lines (with `G1A`..`G7C` fallback).
    - `JobItemModal`: Replaced staff grade description text input with required `<select>` strictly constrained to the 16 controlled items from the master import list without uncontrolled default values.
    - `JobItemModal`: Formatted 422 error details into readable `<field>: <message>` lines under the form instead of `[object Object]`.
    - Added unit test suite `JobItemModal.test.ts` verifying error parsing, payload generation, and controlled lists.
  - Backend:
    - Added `@field_validator("staff_grade_description")` on `JobItemBase` and `JobItemUpdate` enforcing membership in the controlled staff grade description list with descriptive error messages.
    - Added test coverage in `test_jobs_api.py` verifying 422 rejection for uncontrolled descriptions, missing start dates, and missing planned grade codes, along with successful creation.


## [1.7.0] - 2026-11-19
### Added
- Client Alignment & Audit Fixes (Batch 5):
  - OT2 Overtime Rule Alignment (DEC-01):
    - OT2 = all worked hours on a public holiday or on the worker's own weekly off day (`is_ot2_day = inputs.is_public_holiday or inputs.is_weekly_off`).
    - Unassigned non-off day = OT1 for all worked hours (`day_type = "UNASSIGNED"`).
    - Normal assigned day = OT1 for hours beyond standard hours.
    - Removed hardcoded Sunday check (`is_ot2_weekday`); if worker's `weekly_off_day` is not configured, does not default to Sunday and raises `NO_WEEKLY_OFF_DAY` flag instead.
  - Background Jobs Scheduler (`fw/worker.py`):
    - Production async scheduler executing periodic watchdogs (`check_no_activity` & `check_stale_devices` every 15 minutes), daily pending visit detection & reminders (per site local date), daily document expiry checks, retention purge (>60d sync changes, >6mo notifications), and yearly archiving per DEC-38.
    - Removed lazy document expiry check and global variable from `notifications/service.py`.
    - Idempotent execution, structured start/complete logging, and admin `JOB_FAILURE` alert creation on error.
  - Multi-Process Safety & Scaling:
    - Database Migration `0019_stream_tickets.py`: Created `stream_tickets` table with 30s TTL and single-use atomic consumption for SSE authentication across multiple web worker processes.
    - `LivePositionBroadcaster`: Added PostgreSQL `LISTEN live_positions` channel consumer that fans out live position updates to local SSE subscribers across processes with duplicate suppression.
  - Site-Local Date & Clock:
    - Added `site_today(country)` and `site_now(country)` in `fw/core/clock.py` resolving country timezone from settings.
    - Replaced all raw `date.today()` calls and hardcoded `ZoneInfo("Asia/Dubai")` usages.
  - Attendance & Payroll Resilience:
    - Removed blanket exception swallows in attendance calculation; missing salary structures now explicitly flag `NO_SALARY_STRUCTURE`.
    - Month-end report generation executes in a separate transaction post-commit, creating `MONTH_END_REPORTS_FAILED` alerts without rolling back approved payroll runs.
  - Web UI & API Route Consolidation:
    - Fixed salary revisions API endpoint URL in `WorksiteDetail.tsx` (`/api/v1/salary-revisions`).
    - Handled silent/empty catch blocks across `WorksiteDetail.tsx`, `Attendance.tsx`, `AuthContext.tsx`, `Shell.tsx`, `BasePlanner.tsx`, `OperationalPlanner.tsx`, and `SalaryStructures.tsx` with error states and logging.
    - Consolidated duplicate device revocation routes onto `POST /api/v1/devices/{device_id}/revoke` and `/reset` with `REVOKE_DEVICE` audit logging; removed orphaned `api/devices.py`.
  - Documentation & ADRs:
    - Created `ADR-025` (`docs/decisions/025-batch5-audit-fixes.md`).
    - Updated `docs/03-business-rules.md`, `docs/05-attendance-engine.md`, `docs/06-payroll-and-cost.md`, `docs/12-reports.md`, `docs/decisions/decision-register.md`, and added clarification notes in `docs/reference/field_workforce_system_requirements.md`.

## [1.6.0] - 2026-11-19
### Added
- Client Alignment (Batch 4): Breaks, Fixed Crew Structure, Payroll Formula Text, and Governance:
  - Database Migration `0018_reporting_lines_active.py`:
    - Added `is_active` (boolean, default True, indexed), `deactivated_at`, and `deactivated_by` to `employee_reporting_lines`.
    - Converted unique constraint `uq_employee_manager_relationship` to partial index `uq_employee_manager_relationship_active` filtering `WHERE is_active = true`.
    - Replaced index `ix_unique_single_supervisor` with partial unique index filtering `WHERE relationship = 'SUPERVISOR' AND is_active = true`.
    - Added `change_source` column to `employee_salary` (nullable varchar(50)) to distinguish crew break propagation updates from formal salary revisions.
  - Break Time: One Source of Truth (DEC-03, DEC-41):
    - Attendance Engine break priority: Worker salary structure (`employee_salary.break_minutes` if > 0) -> Seasonal/Effective `TimeRule.break_minutes` -> Company Default (`default_break_minutes`).
    - Removed hardcoded "or 30" fallback; company default setting is now the definitive calculation fallback.
    - Job-item `break_override_minutes` is strictly display reference and never affects calculation (`DailyCalculationInputs.first_site_break_override` remains unused).
    - Daily calculation result and explanations reflect definitive `break_source`: `SALARY_STRUCTURE` / `TIME_RULE` / `COMPANY_DEFAULT`.
    - Setting or updating `break_override_minutes` on a supervisor propagates to all linked active crew members in `employee_salary` with effective dating (`change_source = 'CREW_BREAK'`).
    - Propagation is strictly idempotent, updates future-dated salary rows, updates same-effective-date rows in-place (preserving non-crew change sources), never invents baseline salary rows for workers without prior salary history, and rejects locked payroll periods with `HTTP 422 PAYROLL_PERIOD_LOCKED`; retroactively recalculates unlocked attendance for dates prior to today; newly linked workers inherit supervisor's crew break upon assignment.
    - Master Data Import pipeline commits `Employee_Salary` before applying idempotent crew-break propagation, defaulting new salary structures to the supervisor's crew break when omitted. Re-importing workers with a changed supervisor issues an `UPDATED` preview action and automatically soft-deactivates the former active supervisor link upon commit.
    - Web UI salary history (Employee Detail & Payroll Salary Structures drawer) labels `CREW_BREAK` updates with a dedicated "Break change" badge with no false monetary difference.
  - Fixed Crew Structure & Governance (DEC-10, ADR-024):
    - Enforced fixed crew topology: Workers have exactly 1 supervisor (manager must have role `SUPERVISOR`); Superintendents and Engineers attach ONLY to Supervisors; direct `WORKER -> SUPERINTENDENT/ENGINEER` links are forbidden.
    - Added pure validation rules in `fw.rules.hierarchy`: `WORKER_DIRECT_LINK_NOT_ALLOWED`, `SUPERVISOR_LINK_ROLE_MISMATCH`, `INVALID_LINK_SUBJECT` (rejects supervisor linking to a supervisor, or superintendent/engineer link to a non-supervisor), `HIERARCHY_ROLE_MISMATCH`, and `HIERARCHY_CYCLE`.
    - Enforced validations in `OrgService.add_reporting_line` and Master Data Import pipeline preview (surfaced as blocking preview ERRORs, not crashes).
    - Transitive scope & approval inheritance: Workers inherit supervisor's superintendents and engineers for transitive scope (`compute_transitive_scope`), approval routing (leaves, reassignments, attendance reviews), live map, and reporting.
    - Soft deactivation & auditability: `OrgService.remove_reporting_line` and hierarchy editor soft-deactivate links (`is_active = False`) preserving complete history. All operational queries across attendance, scheduling, sync, live map, and reports filter `is_active = true`.
    - Hierarchy Violations Audit & Remediation Tooling: Admin endpoint `GET /api/v1/employees/hierarchy-violations` lists non-conforming legacy links with `can_move_to_supervisor` indicators, `GET /api/v1/employees/hierarchy-violations/export` exports violation roster to Excel, `POST /api/v1/employees/hierarchy-violations/{id}/move-to-supervisor` safely attaches the manager to the worker's supervisor before deactivating the direct link, and `POST /api/v1/employees/hierarchy-violations/{id}/deactivate` soft-deactivates the link.
    - Frontend Web UI: Employee Detail Hierarchy editor restricts worker manager candidates strictly to `SUPERVISOR`, hides direct supt/eng inputs on worker profiles, displays inherited leadership read-only with an `(inherited via supervisor)` badge, restricts supt/eng linking only to supervisor profiles, and provides an interactive "Hierarchy Audit & Violations" modal with live resolution actions and Excel download.
  - Payroll Formula Text Alignment:
    - Corrected formula descriptions across Web UI labels/guides (`web/src/routes/Payroll.tsx`), documentation (`docs/06-payroll-and-cost.md`, `docs/modules/payroll.md`, `docs/decisions/020-month-end-payroll-and-dynamic-budget.md`), and historical changelog entries:
      - Gratuity formula: `basic / 365 * 30` (or 21 days for < 5 years service).
      - Leave salary formula: `basic / 12` (or pro-rated basic / 30 * days).
    - Pinned exact calculation test in `backend/tests/test_payroll_rules.py` (Basic 1,100 -> Gratuity 90.41, Leave Salary 91.67). `fw.rules.payroll.formulas.py` logic remained untouched.
  - Decision Register & Documentation Updates:
    - Updated `docs/decisions/decision-register.md` with client confirmations (dated 19 Nov 2026): DEC-01 (OT1/OT2 definitions), DEC-03/DEC-41 (break precedence), DEC-10 (fixed crew hierarchy), DEC-30 (missed-hours deductions remain), DEC-47 (salary reports restricted to Admin), DEC-49 (drivers measured camp-to-camp minus break).
    - Status updates: DEC-38 & DEC-56 set to `HUMAN` ("implemented; awaiting client/counsel review"); DEC-44 set to `DROPPED` ("omitted by client in later meetings").
    - Phase 10 status updated to `dropped (client omitted transport)` in `docs/phases/README.md`.
    - Report inventory aligned from 16 to 15 reports across `docs/12-reports.md` and `docs/README.md` (`driver-run-sheet` dropped with transport).
    - Regenerated master bulk import template `FieldWorkerTracker_Import_Template_v1.0.xlsx` with updated reporting instructions and validations.

- System Refinements & Lifecycle Controls (Batch 3):
  - Database Migration `0016_leave_cover_and_batches.py`: Added `leave_requests.cover_employee_id` (indexed), `reassignment_requests.batch_id` (indexed), `reassignment_requests.batch_note`, and `scheduled_work.is_weekly_off_cover`.
  - Single Standalone System Admin (`0017_single_standalone_admin.py`, ADR-023): Decoupled the single `ADMIN001` system administrator from the `employees` table (`users.employee_id` nullable strictly when `role = 'ADMIN'`), added PostgreSQL partial unique index `uq_users_single_admin` guaranteeing at most one Admin account, restricted `employees.role` strictly to operational roles (`WORKER`, `SUPERVISOR`, `SUPERINTENDENT`, `ENGINEER`), blocked `ADMIN` creation/promotion in APIs & Excel imports (`ADMIN_ROLE_RESERVED`), updated database reset/seeding and all tests to reuse `ADMIN001` via `UserService.get_or_create_system_admin`, and removed `Admin` from Employees UI filters.
  - Company Settings & Budget-Only Roles Alignment: Unified mobile & web default password resolution onto the single `default_password` setting (`SyncService.get_default_password`), fixed `alarm_lead_minutes` resolution in mobile day-plan sync, added `company_name` and `pending_visit_escalation_days` to the import registry, master template, and `docs/18-company-settings.md`. Resolved `GET /api/v1/settings/staff-grades` from the union of active `employees` and active `job_items`, intersected imported `budget_only_staff_types` against resolved workforce/job grades on import, and surfaced any orphaned saved budget-only roles as removable active chips on the Settings tab.
  - Role Permission Split (`SUPERINTENDENT` vs. `SUPERVISOR`): Granted `SUPERINTENDENT` direct edit permissions across Base Planner & Operational Planner and approval permissions for Leave Requests, Reassignments, Reassignment Batches, and Attendance Decisions; restricted `SUPERVISOR` strictly to view-only on Base Planner and request/draft-batch mode on Operational Planner.
  - Leave Auto-Cover & Bulk Cover: Added optional `cover_employee_id` to Leave Requests with weekly-off mismatch indicators; approving a leave auto-assigns the cover worker across all working days of the leave (never skipping their own weekly off day, instead tagging `is_weekly_off_cover = true` and rendering **`Weekly Off (Covering)`** badges in Operational Planner Coverage & Roster views). Added `POST /api/v1/leave-requests/{leave_id}/bulk-cover` and a **"Cover All Slots"** button on Leave Management to cover every remaining uncovered slot of an approved leave with one worker.
  - Supervisor Draft Reassignment Batches: Supervisors stage multiple operational shifts into a `localStorage`-persisted Draft Batch (`POST /api/v1/reassignment-requests/batch`); approvers (`ADMIN`, `ENGINEER`, `SUPERINTENDENT`) see grouped batch cards in Approvals Inbox with **Approve All** (`POST /api/v1/reassignment-batches/{batch_id}/approve`), **Reject All** (`POST /api/v1/reassignment-batches/{batch_id}/reject`), and individual per-line decisions.
  - `localStorage`-Backed Undo & Redo in Planning: Created reusable `web/src/hooks/usePlannerHistory.ts` (25-step cap, 24h TTL, `Ctrl+Z` / `Ctrl+Y` / `Ctrl+Shift+Z`) and wired Undo/Redo into both `BasePlanner` (saved template snapshots) and `OperationalPlanner` (inverse shift API mutations for editors; instant draft stack undo/redo for Supervisors).
  - Tally ID Change & Previously-Used Guardrail: Added Admin-only `GET /api/v1/employees/check-tally-id` and `POST /api/v1/employees/{id}/change-tally-id` atomically updating `employees.tally_id` and linked `users.username` while preserving all UUID-linked history and logging `CHANGE_TALLY_ID` in `audit_logs`. Enforced a previously-used `tally_id` guardrail (`409 TALLY_ID_PREVIOUSLY_USED` unless `confirm_reuse=true`) on both Change Tally ID and Create Employee.
  - Admin-Only Deactivation & Option A Clean Reactivation: Added impact preview, password-verified (`verify_password`) + typed-confirmation (`DEACTIVATE`/`REACTIVATE`) endpoints with optional `effective_date` for Employees (`/employees/{id}/deactivation-impact|deactivate|reactivate`), Worksites (`/worksites/{id}/...`), and Job Items (`/job-items/{id}/...`). Deactivating an employee immediately disables web/mobile logins (`User.is_active = False` + revokes `UserSession`s), removes active roster entries, cancels future shifts (`WORKER_DEACTIVATED`), and surfaces **`Needs Cover (Worker Deactivated)`** gaps; deactivating a worksite/job item cancels future shifts & occurrences to immediately free assigned workers; Option A Clean Reactivation restores active visibility/login without restoring old schedules. Restricted visibility of deactivated Employees, Worksites, Job Items, and Accommodations strictly to `ADMIN` (`Active` / `Deactivated` / `All` filters).
  - Documentation: Authored `docs/19-tally-id-and-lifecycle-guide.md` and updated `docs/07-data-model.md` and `docs/README.md`.

- System Refinements & Patches (Batch 2):
  - Editable Employee Hierarchy (Admin-Only): Added interactive reporting-line editor to Employee Detail Hierarchy tab allowing Admin to add/replace a single direct Supervisor and add/remove multiple Superintendents and Engineers; non-admins remain read-only and Admin accounts (`ADMIN`/`ADMIN001`) are strictly excluded from hierarchy links.
  - Master Excel `boundary_polygon` Column: Added optional `boundary_polygon` column (GeoJSON Polygon or WKT `POLYGON((...))`) to both `Worksites` and `Accommodations` sheets in the master template, preview validator (`INVALID_POLYGON`), and atomic PostGIS commit pipeline (publishing boundary-changed sync events).
  - Selective Sheet Import: Added optional `sheets` filter parameter to `POST /api/v1/imports` and an Import Scope selector (*All Sheets in File* vs. *Specific Sheet(s)*) on the Master Data Import screen.
  - Database Reset Admin Password Verification: Updated `POST /api/v1/settings/reset-database` and the Settings Danger Zone modal to require both `RESET` confirmation text and verified current Admin password before clearing tables.
  - Paid Leave Payroll Run Option: Added `treat_leaves_as_paid` toggle when generating a Draft Payroll Run (`POST /api/v1/payroll/runs` and Payroll modal) so all approved leave hours can be paid without deduction when required, recorded in run/record snapshots for auditability.
  - Urgent Leave 3-Day Notice Exemption: Exempted `EMERGENCY` and `SICK` leave types from the 3-day advance notice requirement for all roles (`fw.rules.scheduling.leave.validate_leave_dates` and Leave Management UI).
  - Login Password Visibility Toggle: Added `Eye` / `EyeOff` password visibility toggle buttons to the Login page and Forced Password Change inputs.

### Changed
- Mobile Contract Documentation (`docs/09-mobile-sync-contract.md`, v1.1.1): Full alignment audit against implemented mobile APIs — documented `POST /api/v1/mobile/consent/withdraw`, corrected `GET /api/v1/mobile/me/payroll` (`WorkerMobilePayrollSlip`) response schema, added complete request/response JSON examples for every endpoint, documented server-side PostGIS verification verdicts and flags, clarified password strength rules and planned `/mobile/me/scorecard` status, added a complete HTTP error code matrix, and added 9 end-to-end operational scenarios.

### Added
- System-Wide Refinements and Patches:
  - Base Planner Sunday Quota Overflow & Target Styling Reset: When using "Fill Active Working Days", if a worker's weekly rest day falls within target days (e.g. Friday), automatically schedules Sunday to satisfy the required 6-day quota. Automatically disables cyan target styling on slot cells once planned quota has been reached.
  - Base Planner Monthly Week Selection Capping: Capped selectable weeks of the month in recurring monthly cadences to `occurrences_per_period` (e.g. 1 week for 1x/month, 2 weeks for 2x/month), disabling extra checkboxes and allowing 1-click week switching for single-visit cadences.
  - Approved Leave Cancellation Lockdown: Restricted leave cancellation strictly to `REQUESTED` leaves; attempts to cancel an `APPROVED` leave now return `HTTP 400 VALIDATION_ERROR` ("Approved leave cannot be cancelled once approved"), preserving coverage integrity and preventing orphaned shift gaps.
  - Multi-Tier Break Duration Hierarchy (One Source of Truth): Configured break minutes priority: worker salary structure (`employee_salary.break_minutes`) > seasonal/effective time rule > company default (`default_break_minutes`). Setting crew break on a supervisor propagates directly to linked crew members' salary structures (`employee_salary`). Job-item break override is strictly display reference and never affects calculation.
  - Operational Planner Public Holiday Skipping: Configured operational planner template slot expansion to skip statutory public holidays by default when generating daily shifts from master base blueprints.
  - Daily Dashboard Document Expiry Alerts: Added automatic daily document expiry scanning during alert retrieval (`check_document_expiry_alerts`) and integrated a dedicated Document Expiry Alert card with lead time and expiration countdown badges into the Operations Dashboard linking to `/documents`.
  - Multi-Page Interactive Sorting Controls: Added interactive sorting toggles across Employees (Name vs Tally ID), Worksites (Job Number vs Name), Base Planner (Job Number Asc/Desc), and Operational & Master Planner (Worksite Job Number Asc/Desc).
  - Mobile Payslips API: Added `GET /api/v1/mobile/me/payroll` with optional `period=YYYY-MM` filter, returning formatted payslips with earnings, deductions, currency, and period. Exported to `openapi-mobile.json`.
  - Voluntary Worker Password Change: Added `POST /api/v1/mobile/auth/change-password` allowing workers to update their passwords directly from the mobile app after validating their old password.
  - Mobile Proxy Enhancements: Added Payslips card on Worker Profile tab, added Change Password interactive modal on Profile tab, and fixed CAMP geofence event emission to cleanly report `ENTRY` and `EXIT` for accommodation camps.
  - Dedicated Employee Password Reset: Added `POST /api/v1/employees/{employee_id}/reset-password` endpoint that auto-provisions a `User` record if one does not already exist, resets to company default password, and clears lockouts.
  - Employee Phone & Email Persistence: Fixed bulk import pipeline to persist `phone` and `email` to database, and updated Employee Detail view to render both contact fields with editing permissions for Admin and Engineer roles.
  - Human-Readable Audit Trail: Enriched audit trail diffs on Employee Detail page with human-readable labels for UUIDs (`actor_name`, `entity_label`, friendly field key formatting).
  - Planned Attendance Schedule Fallback: In attendance daily calculation, populated baseline 5-point schedule fallbacks from company settings (`default_accommodation_start`, `default_first_site_start`, `default_break_minutes`, `default_last_site_end`, `default_accommodation_end`) when no matching `TimeRule` specifies hours.
  - Budget-Only Staff Types Handling: Excluded budget-only positions (`budget_only_staff_types`) from `BasePlanner` and `OperationalPlanner` views. In `get_budget_vs_actual` and Job Costing reports, credited actual cost as equal to pro-rated planned cost so contract budgets account for budgeted roles without false variance skew.
  - Leave Request 3-Day Notice & Admin Bypass: Enforced 3-day advance notice rule across all user roles, with an explicit `bypass_notice` confirmation checkbox for administrators.
  - Salary Revision Precedence & Worksites Filter: Implemented resolution precedence (Worksite `salary_revision_code` > Company Setting `default_salary_revision_code` > latest active revision). Exposed `salary_revision_code` in worksite CRUD APIs, added salary revision filter toolbar to Worksites view, and enabled editing in Worksite Detail.
  - Company Settings Pre-fill & Documentation: Pre-filled all company settings catalog defaults in the bulk import template (`Company_Settings` sheet) and authored comprehensive reference documentation `docs/18-company-settings.md`.
  - Budget-Only Roles Config & Persistence: Fixed `get_unique_staff_grades` to retrieve only real active employee staff grades from workforce records, eliminating phantom roles from appearing when no matching workforce exists. Fixed array/JSON-string parsing and case-insensitive matching in Settings tab, and granted Engineers role permission to update settings.
  - Staff Grade Filter on Employees Page: Enriched the Employees view filter dropdown to include all unique workforce staff grade descriptions alongside system roles, with seamless support across both server-side query params and client-side hierarchy tree filtering.
  - Cross-Role Planner Candidate Recommendations & Budget-Only Worker Exclusion: Strictly excluded budget-only workers from candidate recommendations across Base Planner, Operational Planner, and AssignModal. Added `all_roles` query parameter to recommendation endpoints and interactive `[ ] Show all workforce roles` checkbox toggles across `AssignModal`, `OperationalPlanner`, and `BasePlanner` to allow cross-grade candidate visibility when needed.

### Added
- PHASE-13 (Hardening, Archive, Backup, Privacy and Go-Live):
  - Database Migration `0014_archive_and_retention.py`:
    - Created `archive_records` table (`id`, `year`, `file_name`, `file_path`, `file_size_bytes`, `sha256_checksum`, `encryption_algo`, `record_count`, `status`, `archived_at`, `verified_at`, `purged_at`, `purged_record_count`, `details`).
    - Added `consent_status`, `consent_withdrawn_at`, `anonymised_at` to `employees`.
    - Added `status`, `withdrawn_at`, `withdrawal_reason` to `consent_records`, altered `device_id` to nullable.
  - Yearly Archive Engine (`fw.modules.archive`):
    - Export, AES-256-GCM encryption with 96-bit nonce and 16-byte authentication tag (PyCA `cryptography`), SHA-256 checksum computation, downloadable `.enc` package, verified sample decryption, and transactional purge using `SET LOCAL fwt.bypass_immutability = 'on'`.
    - Purges historical raw `mobile_event_logs`, `site_visits`, and `tracking_gaps` for the archived calendar year while preserving daily attendance records and payroll snapshots for 7 years.
    - Endpoints: `GET /api/v1/admin/archives`, `POST /api/v1/admin/archives`, `GET /api/v1/admin/archives/{year}/download`, `POST /api/v1/admin/archives/{year}/verify`, `POST /api/v1/admin/archives/{year}/purge`.
  - Statutory Data Retention & Privacy Controls:
    - Purge endpoint `POST /api/v1/admin/retention/purge`: purges transient `sync_changes` older than 60 days and resolved notifications older than 6 months.
    - Terminated worker anonymisation endpoint `POST /api/v1/admin/retention/anonymise`: anonymises inactive employees terminated > 2 years per UAE labour law while retaining hours and payroll history for audit.
    - Worker Tracking Consent Withdrawal: mobile endpoint `POST /api/v1/mobile/consent/withdraw` and admin endpoint `POST /api/v1/employees/{id}/withdraw-consent`. Immediate rejection (`HTTP 403 CONSENT_WITHDRAWN`) of subsequent location batches; emits `WorkerConsentWithdrawn` domain event creating Admin alert.
    - Employee Data Subject Access Request (DSAR): `GET /api/v1/employees/{id}/export-dsar` generates a multi-sheet Excel package (Profile, Consent History, Documents, Attendance Summary, Payroll Slips).
  - Web UI Features:
    - Archive Viewer & Retention Management in Admin Settings (`web/src/features/admin/ArchiveSettings.tsx`, integrated into `web/src/routes/Settings.tsx`).
    - Export & Import action buttons on Employees page (`/api/v1/employees/export`, Link to `/imports`), Worksites page (`/api/v1/worksites/export`, Link to `/imports`), and Planner pages (Roster export, Link to `/imports`).
    - Employee Detail DSAR Export button, Consent Status badge, and administrative Consent Withdrawal button.
  - Disaster Recovery & Performance Benchmarks:
    - Automated restore drill tool `tools/backup_restore_drill.py`: creates backup dump, restores to scratch database, validates data parity across 9 tables, checks PostGIS geometry validity (`ST_IsValid`), and measures RTO against the 4-hour SLA (achieved 4.49s). Full record saved in `docs/runbooks/restore_drill_record.json`.
    - 300-worker performance load test `tools/load_test.py`: verified all non-functional requirements in `docs/14-nonfunctional.md` (Sync changes pull: 94.8ms < 300ms p95; List endpoints: 227.9ms < 300ms p95; Week view roster: 1104.1ms < 1500ms p95; Event batch ingest: 455.1ms < 500ms p95).
    - Spatial point-in-polygon batch optimization in `EventEnrichmentService` using in-memory Shapely geometries.
    - Standalone air-gapped archive decryptor `tools/decrypt_archive.py` supporting CLI verification, key generation, and decryption of AES-256-GCM packages without a database connection.
    - Automated semver versioning engine `tools/version.py`: manages synchronized versions across `version.json`, `web/src/version.ts`, `web/package.json`, and `backend/pyproject.toml`, logged in `docs/system-versioning.md`, with an automatic git `pre-commit` hook.
  - Production Deployment & Reverse Proxy:
    - Dual reverse proxy support for sovereign deployments:
      - Default: Caddy (`infra/caddy/Caddyfile`) with automatic Let's Encrypt TLS.
      - Alternative: Nginx (`infra/nginx/nginx.conf`) with TLS 1.3, HSTS, CSP, SSE streaming optimizations (`proxy_buffering off;`), 12MB client upload limit for Excel workbooks, and Docker Compose `--profile nginx`.
    - Production compose manifests at repository root `docker-compose.prod.yml` and `infra/docker-compose.prod.yml`.
  - Operational Runbooks (`docs/runbooks/`):
    - `01-production-deployment.md`: Azure UAE North topology, secrets management, rolling zero-downtime deployment, health probes, and rollback procedures.
    - `02-backup-and-restore-drill.md`: Point-in-time recovery policy, quarterly drill procedure, and recorded pre-go-live drill result.
    - `03-incident-breach-response.md`: 72-hour SDAIA and UAE Data Office breach notification protocols, severity classification, containment steps.
    - `04-sync-failure-recovery.md`: Mobile sync gap recovery, cursor drift diagnostics, and forced snapshot resync.
    - `05-admin-operations-guide.md`: Operating guide for yearly archive, retention purge, DSAR exports, and consent withdrawal.
  - Legal & Architectural Documentation:
    - Assigned operational role owners and statuses for all 10 human actions in `docs/legal/01-human-actions.md`.
    - Updated Decision Register (`DEC-38`, `DEC-55`, `DEC-56`).
    - Architecture Decision Record `docs/decisions/022-archive-retention-and-hardening.md` (ADR-022).

- PHASE-12 (Reports and the Generated Reports section):
  - Database Migration `0013_reports_history.py`:
    - Created `generated_reports` table (`report_key`, `country`, `period_start`, `period_end`, `kind`, `params`, `file_name`, `file_ref`, `version_no`, `status`, `sha256`, `file_size_bytes`, `visible_roles`, `generated_by`, `generated_at`).
    - Created `report_exports` table (`report_key`, `format`, `status`, `filters`, `requested_by_user_id`, `file_ref`, `file_name`, `file_size_bytes`, `sha256`, `error_message`, `created_at`, `completed_at`).
  - Storage Adapter (`fw.adapters.storage`):
    - Pluggable `FileStoragePort` protocol and `LocalStorageAdapter` implementing secure relative path validation, parent directory auto-creation, SHA-256 digest computation, and local streaming.
  - Reports Core & Registry (`fw.modules.reports`):
    - Comprehensive `REPORTS_REGISTRY` managing 15 active reports (`daily-attendance`, `monthly-attendance`, `employee-movement`, `site-visits`, `employee-utilization`, `transportation-time`, `late-early-departure`, `project-attendance-summary`, `pending-visits`, `staffing-gaps`, `document-expiry`, `weekly-roster`, `payroll`, `provisions-staff-cost`, `job-costing`; `driver-run-sheet` omitted as transport is inactive).
    - Formatters:
      - Excel (`fw.modules.reports.formatters.excel`): Single header row, formatted ISO dates, typed numerics/currencies, no merged data cells, column width auto-fit, and a secondary `Filters` sheet capturing execution parameters.
      - CSV (`fw.modules.reports.formatters.csv_formatter`): RFC 4180 compliant CSV stream.
      - PDF (`fw.modules.reports.formatters.pdf_formatter`): Pure-Python landscape tabular PDF 1.4 formatter for daily attendance and payroll sheets.
    - Handlers for all 15 reports implementing business rules, time calculations, planned vs actual comparisons, variations, and transitive scope filtering.
    - Role Scoping & Confidentiality: `payroll`, `provisions-staff-cost`, and `job-costing` strictly ADMIN only (403 Forbidden for Engineers, Superintendents, and Supervisors).
    - Asynchronous export job runner: `POST /api/v1/reports/{key}/export` dispatches background jobs; status polled via `GET /api/v1/exports/{id}`; files downloaded via `GET /api/v1/exports/{id}/download`.
    - Month-end automatic report generation: Automatically generates 11 reports for each active country upon draft payroll run creation (`PayrollRunCreated`) and final approval (`PayrollRunApproved`).
    - File naming convention (DEC-46): `<Company>_<Report>_<Country>_<Period>_generated-<datetime>.xlsx`, suffixed with `_APPROVED` for approved runs.
    - Immutable archive: Generated reports cannot be mutated; re-downloading (`GET /api/v1/generated-reports/{id}/download`) returns the exact file with identical byte length and SHA-256 checksum.
    - Notifications: Emits in-app notifications to Admins and Engineers upon month-end draft and approved package readiness.
  - Web UI Features:
    - Reports API client (`web/src/features/reports/api.ts`).
    - Reports Hub (`web/src/features/reports/ReportsHub.tsx`): Interactive catalog browser, category filtering, typed dynamic filter toolbar (dates, year, month, country, worksite, supervisor), results preview table, and export action buttons with real-time job status polling.
    - Generated Reports archive (`web/src/features/reports/GeneratedReports.tsx`): Filterable archive table (country, status, kind, period, search), status chips (`DRAFT` / `APPROVED`), version badges, visible role pills, file sizes, and one-click direct re-download.
    - Top tab navigation in `web/src/routes/Reports.tsx` seamlessly switching between Reports Hub and Archive, with `/reports/generated` route in `router.tsx` and sidebar link in `Shell.tsx`.
  - Architecture & Verification:
    - ADR-021 (`docs/decisions/021-reports-registry-history-and-visibility.md`).
    - Comprehensive integration tests in `backend/tests/test_reports_api.py` covering catalog role isolation, 403 enforcement, daily calculations, openpyxl inspection of generated Excel files, PDF headers, month-end automatic generation lifecycle, and re-download byte identity.
    - All 173 backend tests passing; import-linter and pyright passing with 0 errors; frontend build verified.

- PHASE-11 (Month-end Payroll, Salary Revisions, and Job Budget):
  - Pure Payroll Rules (`fw.rules.payroll`):
    - Overtime formulas complying with 208-hour standard monthly divisor (26 days × 8 hours): OT1 rate = `(basic / 208) * 1.25` (only hours beyond standard hours on normal working days); OT2 rate = `(basic / 208) * 1.50` (all hours worked on public holidays and worker's weekly off day). Benchmark: Basic $1,100 -> OT1 $6.61, OT2 $7.93.
    - Missed hours deduction: `missed_hours * (basic / 208)` deducted from monthly salary portion. Paid leaves (annual, sick) incur zero deduction.
    - Statutory employer provisions: Gratuity accrual = basic / 365 * 30; Leave salary provision = basic / 12.
    - 5 company provisions (Visa, Air Ticket, Uniform, Medical, Accommodation) from company settings.
    - HR overhead: 5% added to Total Staff Cost for Final Staff Cost.
    - Planned hourly cost calculation for job budgeting from grade revision lines.
  - Database Migration `0012_payroll_and_budget.py`:
    - Tables: `salary_revisions`, `salary_revision_lines`, `payroll_runs`, `payroll_records`, and `job_cost_allocations`.
    - Added `salary_revision_code` column to `worksites` for dynamic contract budget binding.
  - Backend Module (`fw.modules.payroll`):
    - Automated draft creation via background check (`POST /api/v1/payroll/auto-run-check`) running `payroll_auto_run_delay_days` (default 5) after month-end.
    - Draft re-runs with automatic `run_no` increment.
    - Issues endpoint (`GET /api/v1/payroll/runs/{id}/issues`) identifying unapproved overtime and missing employee salary structures.
    - Approval endpoint (`POST /api/v1/payroll/runs/{id}/approve`) freezing immutable snapshots in `payroll_records` and setting `locked = True` on attendance records for that period and country.
    - Role-based scoping: Admin manages and approves; Engineers inspect scoped records read-only; Supervisors receive 403.
    - Worker-facing approved payroll slips endpoints: `GET /api/v1/payroll/my-records` and `GET /api/v1/mobile/me/payroll` returning employee-side pay components with employer provisions withheld.
    - Salary revisions management: listing, creation, and side-by-side diff comparison (`POST /api/v1/salary-revisions/diff`).
    - Dynamic job budget vs actual cost allocation (`GET /api/v1/payroll/budget-vs-actual`) and worksite revision binding (`PUT /api/v1/payroll/worksites/{id}/revision`).
  - Web UI Features (`web/src/routes/Payroll.tsx`):
    - 3-tab layout: Payroll Runs & Approvals, Salary Revisions, and Job Budget vs Actual.
    - Payroll Runs tab: Run status badges (`DRAFT` / `APPROVED`), run numbers, summary KPI cards, Draft Inspector with collapsible Issues Panel, Re-run Draft button, Approve Payroll confirmation modal, and worker records table with search.
    - Worker Detail Drawer: Comprehensive employee pay breakdown and employer staff cost breakdown (with 5% HR OH).
    - Explanatory Formula Guide ("i" icon modal): Detailed documentation of legal/contractual math (208 divisor, OT1 vs OT2 classification, basic / 365 * 30 gratuity, basic / 12 leave salary, 5% HR OH).
    - Salary Revisions tab: Revision selector dropdown, grade pricing lines table, "Export Template" button generating pre-filled sheet, and "Import Revision & Diff" modal with side-by-side red/green diff preview.
    - Excel Template Import & Diff: Real `.xlsx` template export (`GET /api/v1/salary-revisions/{code}/export-template`), drag-and-drop Excel file upload, automated side-by-side diff (`POST /api/v1/salary-revisions/preview-file`), inline editable preview grid, and single-click revision commit.
    - Worker Records Table enhancements: Clear Role pills with color-coding, Role filtering dropdown (Workers, Supervisors, Engineers, Admins), employee Tally ID rendering, and explicit standard target vs worked hours display (`8h/d (208h) / XX.Xh`).
    - Job Budget vs Actual stability: Safe variance calculation ensuring robust rendering without undefined property exceptions.
    - Job Budget vs Actual tab: Worksite cards/table with dynamic revision binding dropdown, annual planned hours, annual labor budget, pro-rated budget, actual allocated cost from attendance minutes, variance indicators, and prominent information banner detailing the provision basis distinction between planned budgets and actual costs.
  - Mobile Simulator & Proxy:
    - Added Monthly Payslips card in worker Profile tab calling `/api/v1/payroll/my-records` and showing approved payslips with period, worked hours, OT amounts, and net pay.
  - Architecture & Verification:
    - ADR-020 (`docs/decisions/020-month-end-payroll-and-dynamic-budget.md`).
    - Bulk Master Data Import & Template Integration: Enabled `Salary_Revisions` and `Salary_Revision_Lines` sheets in master import registry (`SHEET_REGISTRY`) and commit pipeline, allowing master workbook (`FieldWorkerTracker_Import_Template_v1.0.xlsx`) and standalone revision sheets to be previewed, diffed, and committed directly.
    - Unit tests (`tests/test_payroll_rules.py`) and integration tests (`tests/test_payroll_api.py`) verifying all 8 checklist requirements.

- PHASE-09 (Live Map, Pending Visits, Alerts, and Documents):
  - Database Migration `0011_live_map_and_alerts.py`:
    - Created dedicated `live_location_access_logs` table (`id`, `user_id`, `access_type`, `filters`, `client_ip`, `user_agent`, `created_at`) with performance indexes (`ix_live_location_access_logs_user`, `ix_live_location_access_logs_created_at`) for surveillance auditing without polluting business mutation logs.
  - Live Streaming & Positions:
    - SSE stream endpoint (`GET /api/v1/live/stream`) with 20s heartbeat and single-use 30s tokens via `POST /api/v1/live/stream-ticket` (`StreamTicketManager`).
    - Position query endpoint (`GET /api/v1/live/positions`) computing dynamic live states (`ACTIVE`, `NO_RECENT_SIGNAL`, `LOCATION_DISABLED`, `NOT_SCHEDULED`) against `live_active_window_minutes`.
    - Route trail playback endpoint (`GET /api/v1/live/trail/{employee_id}`) returning chronological GPS breadcrumbs.
    - Newest-wins update policy for `employee_last_position` ensuring late batch uploads from offline devices never overwrite newer position records.
    - Privacy audit logging: every view of live locations (polling or SSE streaming) is automatically recorded in `live_location_access_logs`.
  - Alerts & Incident Management:
    - Automated `TRACKING_INTERRUPTED` alert creation on `LOCATION_DISABLED` events and resolution on `LOCATION_ENABLED`.
    - Automated document expiry alert evaluation (`check_document_expiry_alerts`) against configured lead days (e.g. 30 days) raising `DOC_EXPIRY` alerts.
    - Alert scope resolution: alerts link to `employee_id` and are visible throughout the worker's management hierarchy (Supervisor, Superintendent, Engineer) and Admin.
  - Pending Visits Workflow:
    - Day-close detection (`detect_pending_visits`) identifying unvisited scheduled work occurrences (`OPEN`).
    - Automatic exemption for workers on approved leave.
    - Follow-up lifecycle: Supervisor explanation modal (`EXPLAINED`), Engineer/Admin reschedule (`RESCHEDULED` with source `FOLLOW_UP`), and closure (`CLOSED`).
    - Daily reminders runner (`check_pending_visit_reminders`) and escalation badges for visits open 3+ days.
    - Automatic reconciliation and closure when late batch uploads confirm a visit.
  - Web UI Features:
    - Interactive Live Map (`/live`) with MapLibre GL GeoJSON clustering (`cluster: true`), worksite polygons, accommodation polygons, state-colored markers, and selected worker route breadcrumb line.
    - Live Map side panel with search, state and supervisor filters, worker cards showing two distinct ages: position fix age and device last-contact age.
    - Interactive **Journey Replay Player** in Live Map worker slide-out panel featuring date selection, animated path replay, Play/Pause control, timeline scrubber, and speed multipliers (1x–30x) styled to match the light theme.
    - Connection indicator showing real-time SSE streaming or 30s polling fallback.
    - System Page (`/system`) enhancements: Moved application health and telemetry from Dashboard to System page; added dedicated password change section for users and administrators.
    - Authentication improvements: First sign-in password change fallback allowing default temporary password verification and dedicated temporary password input in `Login.tsx`.
    - Dynamic Budget-Only Roles: Endpoint `GET /api/v1/settings/staff-grades` resolving unique staff grades from employees, excel import support, and dynamic checkboxes in Settings.
    - Mobile Proxy Simulator: Added Live Auto-Upload toggle (`⚡ Live Upload: ON`) transmitting events in real time to the server as the route plays, Clock Mode toggle (`🕒 Clock: Live/Simulated`), and verified transit inference without unnecessary transit pings.
    - Pending Visits screen (`/pending-visits`) with search, status filters, 3+ days escalation badges, Explain modal, Reschedule modal with worker assignment, Close modal, and CSV export.
    - Documents Expiry screen (`/documents`) for Admin with lead days filters, status badges (`OK`, `EXPIRING`, `EXPIRED`), alert engine check trigger, and CSV export.
    - Boundary Tools & Setup Queue (`/boundaries`):
      - Bulk Boundary Export (`GET /api/v1/boundaries/export`) supporting CSV and GeoJSON downloads.
      - Bulk Boundary Import (`POST /api/v1/boundaries/import`) supporting CSV and JSON with primary keys (`job_number` for worksites, `accommodation_code` for camps), automatic WKT/GeoJSON format resolution, and graceful skip reporting for unknown keys.
      - 1-click **Copy GeoJSON** and **Copy WKT** buttons in Worksite detail header and Copy Boundary modal.
      - **Paste Polygon** tool in Mobile Simulator (`http://localhost:8085`) supporting WKT and GeoJSON string rendering with centroid alignment and zoom-to-fit.
    - Dashboard Overview tiles (`/`) showing Today's Attendance breakdown, Live Workforce status, Pending Visits with escalation alerts, Late Arrivals, and Overtime Hours Today.
  - Architecture & Testing:
    - ADR-019 (`docs/decisions/019-live-location-access-logging-and-streaming.md`).
    - Complete test suite `test_phase09_live_map_pending_alerts.py` covering all 7 checklist requirements. All 151 backend tests passing; modular monolith import contracts strictly kept (0 violations).

- PHASE-08 (Events Ingestion, Enrichment, and Attendance Engine):
  - Database migration `0010_events_and_attendance.py`:
    - Enrichment columns on `mobile_event_logs`: `server_verdict`, `server_site_id`, `server_accommodation_id`, `distance_to_polygon_m`, `flags`, `processing_status`, `error_reason`, `device_clock_skew_s`, and `batch_id`.
    - PostgreSQL append-only trigger `trg_mobile_event_logs_append_only` with `trg_mobile_event_logs_immutability()` function blocking DELETE operations and modifications to device-reported columns (`event_timestamp_utc`, latitude, longitude, accuracy, mock location, sequence number, device clock), with session-local bypass (`fwt.bypass_immutability`) for admin reset operations.
    - Tables: `employee_last_position` (live map positions with latest timestamp upsert guarantee), `site_visits` (reconstructed polygon visits with entry/exit times, durations, and observed/inferred tags), `tracking_gaps` (interrupted location tracking intervals with distance and unaccounted minutes), `attendance_records` (per-worker/date tracking state and current calculation pointer), `attendance_calculations` (immutable calculation versions with SHA-256 `input_hash`), `attendance_comments` (operational comment threads), `attendance_approvals` (audited decisions), and `pending_visits` (day-close unvisited assignment tracking).
  - Pure Python Business Rules (`fw.rules.attendance`):
    - `verdicts.py`: Spatial containment evaluation (`INSIDE`, `BORDERLINE`, `OUTSIDE`, `NO_POLYGON`), distance to assigned polygon, clock skew detection, and accuracy threshold checks.
    - `visits.py`: Deterministic state machine for time-ordered events; visit opening, confirmation polling, duplicate entry suppression, inferred exit on departure/day close, and minimum duration thresholding.
    - `gaps.py`: Reconstruction of location interruptions (`LOCATION_DISABLED` to `LOCATION_ENABLED`), tracking unaccounted minutes (`gap_minutes - break_used`), and `TRACKING_GAP` flag evaluation.
    - `engine.py`: 5-point planned schedule resolution from effective-dated time rules, job-item break override priority, signed variations (`worked_minutes - required_minutes`), grace period application, business status classification (`PRESENT`, `PARTIAL`, `ABSENT`), overtime engine (OT1 beyond standard hours / rest days; 100% OT2 for public holidays and Sundays per DEC-01), movement split (productive, transit, offsite, idle), review routing, and deterministic `input_hash`.
  - Backend Services & Architecture:
    - Decoupled `EventsIngested` domain event bus publishing in `EventsService.ingest_batch`.
    - Synchronous attendance listener in `fw.modules.attendance.listeners` running PostGIS spatial enrichment and daily attendance calculation within the transaction.
    - `EventEnrichmentService` PostGIS spatial enrichment (`ST_Covers`, `ST_Distance`).
    - `AttendanceWatchdogs`: Scheduled alert runners for `NO_ACTIVITY` (assigned workers with no events past alarm time) and `STALE_DEVICE` (inactive devices past threshold).
    - FastAPI endpoints under `/api/v1/attendance`: `/attendance` list with role/scope filtering and pagination, `/attendance/exceptions` review queue, `/attendance/{id}` details with current calculation and comment threads, `/attendance/{id}/calculations` version history, `/attendance/{id}/timeline` derived event timeline, `/attendance/{id}/comments` supervisor explanations, `/attendance/{id}/decisions` engineer approval/rejection with mandatory comment on rejection, `/attendance/recalculate` manual recompute with audit reasons, and `/attendance/events` raw event audit table.
    - Approvals inbox integration: Connected `AttendanceService.get_attendance_approvals` to `/api/v1/approvals` endpoint, providing unified badge counts and action rows across leave, reassignments, and attendance.
    - Employee API & Org service: Added accommodation filtering (`has_accommodation`, `accommodation_id`) to `GET /api/v1/employees`.
    - Audit Trail enrichment: Added human-readable entity descriptions, actor names, and readable diff mappings resolving raw UUIDs into employee names, job items, and accommodation names.
  - Web UI Features:
    - Client-specified Attendance table layout matching contract: Planned (7 columns), Actual (7 columns), Variations, Review chips, and Approval status. Non-accommodation workers render `n/a` for camp commute columns.
    - Slide-over Attendance Detail Drawer: KPI summary cards, Overtime & Day Classification, Movement breakdown, Chronological timeline with Observed / Inferred badges, Version history with diff inspection, Supervisor comment thread, and Engineer Approve/Reject action form with required rejection justification.
    - Recalculate Modal: Admin dialog to re-trigger calculations across date ranges with audit reason tracking.
    - Approvals Inbox: Added Attendance tab with live badge count, exception summary cards, and one-click review drawer.
    - Employee Creation Modal: Dialog for adding operational staff with immediate multi-tier leadership assignment (Supervisor, Superintendent, Project Engineer) and accommodation assignment.
    - Employee Directory Accommodation Filter: Quick filters for "With Camp", "Without Camp / Self", and specific camp selections.
    - Mobile Tester Proxy Simulator: Added simulation date picker with 1-7 day backdated testing support.
  - Testing & Verification:
    - Test suites: `test_attendance_scenarios.py` (covering all worked examples A through H), `test_attendance_verdicts.py` (spatial verdict classification and flags), `test_attendance_immutability.py` (database trigger immutability), `test_attendance_api.py` (end-to-end API lifecycle), and `test_attendance_watchdogs.py` (alert generation). 144 passing tests across backend.
    - Demo script `tools/seed_phase08_demo.py` demonstrating end-to-end event ingestion, enrichment, attendance calculation, supervisor explanation, and engineer approval.
    - Architecture Decision Record `docs/decisions/018-attendance-engine-and-review-workflow.md`.

  - Database migration `0009_mobile_sync.py`:
    - `sync_changes`: Per-worker append-only change log with monotonic cursor (`id BIGINT IDENTITY`), `employee_id`, `entity_type`, `entity_id`, `op`, `payload` JSONB, `priority`, and `created_at`.
    - `consent_records`: Workers' accepted privacy and location tracking consent history.
    - `mobile_event_logs`: PostGIS-enabled immutable raw location event logs (`Geometry(POINT, 4326)`), device timestamp, capture timestamp, coordinates, accuracy, battery, and server processing flags.
  - Domain Events & Synchronous Listeners:
    - Domain events (`ScheduledWorkChanged`, `HolidayChanged`, `TimeRuleChanged`, `EmployeeProfileChanged`, `WorksiteBoundaryChanged`, `AccommodationBoundaryChanged`) registered on `fw.core.event_bus`.
    - Synchronous listeners in `fw.modules.sync.listeners` materialize changes into `sync_changes` in the same database transaction.
  - Mobile Auth & Security:
    - Worker authentication (`POST /mobile/auth/login`) by Employee ID (`tally_id`) and default password (`Welcome123!`).
    - Forced first-login password change (`POST /mobile/auth/change-password`).
    - Single-device binding (`registered_devices`): rejects subsequent logins from mismatching devices with HTTP 409 `DEVICE_MISMATCH`.
    - Admin-only device reset action (`POST /devices/{device_id}/reset-binding`).
    - Location consent verification (`GET /mobile/auth/consent`, `POST /mobile/auth/consent`).
    - Mobile heartbeat (`POST /mobile/auth/heartbeat`) and token revocation (`POST /mobile/auth/logout`).
  - Change Log Synchronization Engine:
    - Full baseline snapshot (`GET /mobile/sync/snapshot`) returning `PROFILE`, `SETTINGS`, `DAY_PLAN` (30-day sliding window), `SCHEDULE_ITEM`, `JOB` (with boundary polygon and geofence circle helper), and `ACCOMMODATION`.
    - Delta sync (`GET /mobile/sync/changes?cursor=N`) with server-side entity coalescing, returning only the latest state per entity.
    - Compaction floor check signaling `resync_required = true` when cursor falls below retention floor.
    - Client sync acknowledgment (`POST /mobile/sync/ack`).
  - Location Event Batch Ingestion:
    - Batch ingestion endpoint `POST /mobile/events/batch` accepting up to 200 raw events per request.
    - Validates timestamps (rejects >30 days old or >5 min future clock skew) and WGS84 coordinate bounds.
    - Idempotent deduplication returning `DUPLICATE` without double-inserting.
    - Persists raw events immutably in `mobile_event_logs`.
  - Push Adapter:
    - `PushProvider` port with `NullPushProvider` and `FcmPushProvider`.
  - Web Dashboard Devices View:
    - `Devices.tsx` (`/devices`): Device status KPIs, search/filter, platform badges, sync lag calculation, and Admin-only device binding reset.
    - Wired into React router and `Shell.tsx` navigation bar with `Smartphone` icon.
  - Developer & Integration Tooling:
    - Standalone Mobile Tester Proxy & GPS Simulator (`tools/mobile-proxy/`) with interactive Leaflet map, worksite/camp polygon rendering, geofence circle visualization, draggable worker pin, Point-in-Polygon detection, auto-event queueing, and batch dispatch.
    - Demo seed script `tools/seed_phase07_demo.py` provisioning worker 2001 ("Ravi Varghese"), company settings, consent policy, accommodation, and worksite.
    - OpenAPI export script `tools/export_openapi.py --tag mobile` and exported `openapi-mobile.json`.
    - CI check in `.github/workflows/ci.yml` verifying OpenAPI schema synchronization.
    - Mobile developer onboarding guide in `docs/18-mobile-integration-guide.md`.
    - Architecture Decision Record `docs/decisions/017-mobile-sync-and-events-architecture.md`.
    - Phase 07 to Phase 08 & 09 Handoff and Architecture Documentation in `docs/phases/PHASE-07-HANDOFF.md`.
  - Base Planner Blueprint Integration:
    - Integrated `base_roster_templates` and `base_roster_entries` into `SyncService.build_snapshot` and delta change listeners, ensuring recurring blueprint schedules sync shifts, worksites, and polygon boundaries to mobile workers without requiring single-day operational records.
    - Updated `save_base_template` to publish `ScheduledWorkChanged` domain events to invalidate and update mobile sync logs.
  - Mobile Tester Proxy & Web Dashboard Enhancements:
    - Dynamic Auto-Route generation connecting accommodation camp and assigned worksite with realistic shift timing.
    - Automatic map viewport bounding box auto-fit for accommodation and worksite polygons.
    - Interactive custom polygon drawing tool with real-time area calculation and WKT / GeoJSON clipboard export.
    - Dashboard polygon editor bridge: "Paste Polygon" modal in `PolygonEditor.tsx` accepting GeoJSON and WKT.
    - Audio shift alarm synthesizer and Network Inspector with exportable JSON traffic logs.
    - "Clear Map" reset button for scratch layers.
    - Full upstream reporting chain traversal in employee detail view.
    - Explicit PostGIS `ST_AsGeoJSON` loading in event listeners to eliminate `MissingGreenlet` errors.
- PHASE-06 (Leave Management, Temporary Reassignment & Approvals Inbox):
  - Pure domain rules in `backend/src/fw/rules/scheduling/`:
    - `leave.py`: Date order validation, overlapping leave checks against requested/approved leaves, notice period checking (3+ days ahead for non-admin, past leaves allowed for Admin), and leave taken counting (working days excluding worker's weekly off day and public holidays vs calendar days).
    - `reassignment.py`: 3-day notice validation strictly enforced for all roles (`date_from - today >= 3`), late approval detection (`LATE_APPROVAL` flag if decided within 3 days of shift), expired request detection, and live hours preview calculation with overtime and grade group mismatch warnings.
  - Database migration `0008_leave_reassignment_approvals.py`:
    - `leave_requests`: Stores employee leave records (`ANNUAL`, `SICK`, `UNPAID`, `EMERGENCY`, `OTHER`), date bounds, status (`REQUESTED`, `APPROVED`, `REJECTED`, `CANCELLED`), reason, and audit user references.
    - `reassignment_requests`: Stores operational change requests (`REPLACE`, `MOVE`, `ADD`, `CANCEL`), dates, original and cover workers, target job item, reason category, notice flags, and decision audit metadata.
    - `alerts`: Stores operational alerts (`COVER_NEEDED`, `PENDING_BOUNDARY`, `DOC_EXPIRY`) for supervisors, superintendents, engineers, and administrators.
    - `scheduled_work`: Extended with `reassignment_request_id` and `is_late_approval` boolean flag.
  - Event-driven notifications and alerts:
    - Domain events (`LeaveApprovedEvent`, `LeaveCancelledEvent`, `ReassignmentApprovedEvent`) published on the core event bus by `SchedulingService`.
    - `NotificationService` subscribes synchronously: creates `COVER_NEEDED` alert on leave approval and resolves it on leave cancellation or cover reassignment approval, preserving strict modular monolith layer boundaries.
  - Web API endpoints mounted under `/api/v1`:
    - Leave endpoints: `POST /leave-requests`, `GET /leave-requests`, `GET /leave-requests/{id}`, `POST /leave-requests/{id}/approve`, `POST /leave-requests/{id}/reject` (mandatory reason), `POST /leave-requests/{id}/cancel`, `GET /leave-requests/summary` (working days vs calendar days per worker/type), `GET /leave-requests/template` (downloadable Excel template), `POST /leave-requests/import` (bulk Excel import with error reporting).
    - Reassignment endpoints: `POST /reassignment-requests` (refused if <3 days notice for any role), `POST /reassignment-requests/preview` (live preview of worker hours impact), `GET /reassignment-requests`, `GET /reassignment-requests/{id}`, `POST /reassignment-requests/{id}/approve`, `POST /reassignment-requests/{id}/reject` (mandatory reason), `POST /reassignment-requests/{id}/cancel`.
    - Approvals inbox: `GET /approvals` (scoped to engineer's reporting lines, Admin sees all, counts badge).
    - Staffing gaps: `GET /staffing-gaps` (surfaces uncovered approved leave slots).
    - Alerts: `GET /alerts`, `POST /alerts/{id}/resolve`.
  - Frontend views:
    - `Approvals.tsx` (`/approvals`): Tabs for Leave Requests, Reassignments, and Attendance placeholder; status filtering; approve/reject actions with mandatory rejection reason dialog.
    - `LeaveManagement.tsx` (`/leave`): Year selector; working days vs calendar days summary cards; record leave modal with 3-day notice client validation; cancel leave action; admin-only standalone leave Excel import modal with template downloader.
    - `OperationalPlanner.tsx`: `TO_BE_COVERED` cells rendered with amber dashed border, alert icons, and one-click "Select Cover" candidate modal; coverage badges rendered on roster and operational grid cells.
    - `Shell.tsx`: Navigation updated with Approvals Inbox and Leave Management links; dynamic red pill badge showing real-time pending approvals count.
    - `Dashboard.tsx`: Active operational alerts widget displaying `COVER_NEEDED` and `PENDING_BOUNDARY` action items.
  - Architecture Decision Record `docs/decisions/016-leave-and-temporary-reassignment.md`.
- PHASE-05 (Rebuilt Planner: Base Planner & Operational Planner):
  - Clean architectural separation into two dedicated workspaces:
    - **Base Planner (`/base-planner`)**: Blueprint recurring master schedule engine. High-density 7-weekday matrix grid (`MON` to `SUN`) grouped by Worksite. Explicit day-by-day storage (`MON`..`SUN`) and in-modal cadence selection for monthly (`W1_MON`..`W4_SUN`) and quarterly (`M1_W1_MON`..`M3_W4_SUN`) line items without fragile mask overwrites. Contract quota enforcement prevents planning excess visits in the base blueprint. Fully enables all 7 days with candidate warnings for rest days.
    - **Operational Planner (`/operational-planner`)**: Live daily operations calendar with 7-weekday calendar date grid. Displays base blueprint shifts as low-opacity muted chips (45%), surfaces approved leave gaps as `TO_BE_COVERED` alert slots (amber dashed border), and supports single-day operational covers (`OVERRIDE`) and compensatory shifts (`DIRECT`) rendered in solid opacity (100%). Visual target recommendations belong solely to Base Planner.
  - Database migration `0007_base_op_planner.py`:
    - `base_roster_templates`: Stores recurring blueprint definition (`allocation_mode` in `UNIFORM`, `DAY_OF_WEEK`, `start_date`, `end_date`, `is_active`, `version`).
    - `base_roster_entries`: Stores assigned workers per template with explicit `weekday_mask` (`MON`..`SUN`, or periodic cadence `W1_MON`, `M1_W2_WED`), `assigned_hours`, and `sequence`.
    - `scheduled_works`: Enhanced with `original_employee_id`, `override_reason`, and expanded source enum (`TEMPLATE`, `STANDING`, `DIRECT`, `OVERRIDE`, `EXCEPTION`, `FOLLOW_UP`).
  - Pure domain rules in `backend/src/fw/rules/scheduling/`:
    - `blueprint.py`: Resolves Base Roster Templates into daily slots across dates, evaluating periodic cadence matching (`W1_MON`..`W4_SUN`, `M1_W1_MON`..`M3_W4_SUN`), rest-day warnings, and public holiday overtime flags without artificial weekday dropping.
    - `quotas.py`: Equal window pacing calculations for periodic visits (e.g. 2 visits/month) as visual guidance only. Deterministic, zero-swapping visit evaluation based on creation timestamp and date.
    - `operational.py`: Resolves cell state hierarchy (`OPERATIONAL OVERRIDE > APPROVED LEAVE GAP (TO_BE_COVERED) > BASE BLUEPRINT`).
  - Worksite contract overview:
    - Added Contract Validity Period (`start_date` – `end_date` or `Ongoing`) and Annual Operating Budget (`budget_amount AED / year`) to `/worksites` and `/worksites/:id`.
  - Frontend components and routes:
    - `BasePlanner.tsx`: Worksite line items list in 7-weekday matrix, click-to-assign slot modal with in-modal multi-week cadence checkboxes, convenience Mon–Sat fill action (skipping worker's weekly rest days), in-modal Supervisor's Crew filter toggle, 3-tier candidate ranking with rest-day warnings and remote capacity tracking, slot headcount capping (`required_staff_count`), silent background refresh with scroll retention, and base template saving with quota enforcement.
    - `OperationalPlanner.tsx`: Coverage view (Job-centric) and Worker Roster view (Worker-centric), sticky freeze headers, visual distinction between blueprint (muted) and operational (solid) shifts, shift labeling accurately distinguishing "Cover" (replacement) from "Additional" (within quota) and "Excess" (extra visits), candidate exclusion of covered worker and current slot workers, silent background refresh with scroll retention, staging workspace modal with multi-worker selection, staged removals with undo, editable hours/reason inputs, atomic save/cancel, shift reason visibility via note icon and tooltips, pure light-theme enterprise styling.
    - Fixed monthly and quarterly period quota aggregation in `get_operational_coverage` to evaluate occurrences across the complete calendar month or quarter instead of isolating 7-day week views.
    - Fixed weekly off day normalization across backend rules (`blueprint.py`, `operational.py`) and frontend planners (`BasePlanner.tsx`, `OperationalPlanner.tsx`) using `is_same_weekday` helper, correctly skipping rest days and displaying warnings when database stores full uppercase strings (e.g. `FRIDAY`).
    - Base planned worker operational removal: Planners can operationally remove base recurring blueprint workers for a specific date with a mandatory reason. Renders in the operational grid in red (`bg-rose-50 border-dashed border-rose-300 text-rose-800`, line-through worker name, `REMOVED` badge, note tooltip), and provides `[Remove Base Shift]` and `[Restore Base Worker]` actions in the modal.
    - Worker Roster tab enhancements: Persistent sticky freeze header (`sticky top-0 z-10 bg-slate-100 shadow-sm border-b`), hours heatmap shading on weekly totals (amber for under, emerald for met, purple for overtime `+X.Xh OT`) and daily cells (sky for partial shift, solid indigo for 8h met, purple for >8h overtime, neutral slate for weekly off, red line-through for removed), exclusion of system administrators (`Employee.role != 'ADMIN'`), real-time search by worker name, tally ID, grade, or assigned job number, filter by job / worksite dropdown, and supervisor crew grouping toggle.
    - Entity pinning and week navigation scroll retention: Pin icon buttons for worksites in Coverage View and Base Planner, and for workers in Worker Roster View, persisted in `localStorage` and sorted to the top. Week navigation maintains vertical scroll position seamlessly without jumping to the top.
- PHASE-05 (Planner: yearly plan and weekly roster):
  - Pure domain rules for scheduling (`fw.rules.scheduling`):
    - `assignment.py`: Date generator for standing assignments across repeating weekday patterns and holiday skips.
    - `markers.py`: Day marker evaluator producing `SKIPPED` (public holiday), `WEEKLY_OFF`, `ON_LEAVE`, `TO_BE_COVERED`, and `FREE`.
    - `validation.py`: Assignment validation engine checking `PERMANENT_EXCLUSIVE`, duplicate assignment, `OVER_STANDARD_HOURS`, `UNDER_STANDARD_HOURS`, `GRADE_GROUP_MISMATCH`, and `PAST_DATE` (Admin allowed, non-admin blocked).
    - `suggestions.py`: Candidate recommendation and ranking engine implementing DEC-52 (same grade-group first-class eligibility, exact staff type match first with asterisk `*`, site familiarity in past 14 days, supervisor affinity, and available free capacity).
    - `allocation.py`: Capacity calculation per day/week/month against standard hours from salary structure (default 8 h), including Ramadan -120 min reduction.
    - `excel.py`: Pure openpyxl roster export matching the client's weekly schedule layout with worker rows, day cells, and hours summaries.
  - Database migration `0006_planner_and_scheduling.py` introducing `standing_assignments` and `scheduled_work` tables with partial unique indexes, check constraints (`ck_scheduled_work_sequence_positive`), and optimistic locking.
  - Scheduling module (`fw.modules.scheduling`):
    - 13-month rolling horizon generation of daily scheduled work from standing assignments linked to occurrences.
    - Assignment ending lifecycle (`POST /standing-assignments/{id}/end`) with future unstarted row cancellation and audit logging.
    - Occurrence-linked scheduled work CRUD, dry-run validation, and two-step collision-free sequence reordering.
    - Weekly roster aggregation with site chips, day markers, and row totals vs standard hours.
    - Job coverage matrix with assigned vs required staffing and under-staffed slot tracking.
    - Binary Excel streaming (`/roster?format=xlsx`).
  - Web API endpoints mounted under `/api/v1`:
    - `GET /roster`: Weekly roster JSON or streaming Excel export (`?format=xlsx`).
    - `GET /schedule/coverage`: Job coverage matrix for a week.
    - `GET /workers/{id}/allocation`: Worker allocated hours per day/week/month vs standard hours.
    - `GET /occurrences/{id}/recommendations` & `GET /job-items/{id}/recommendations`: Ranked candidate suggestions.
    - `GET /standing-assignments`, `POST /standing-assignments`, `POST /standing-assignments/{id}/end`: Year plan standing assignments.
    - `POST /scheduled-work`, `PATCH /scheduled-work/{id}`, `POST /scheduled-work/reorder`, `POST /scheduled-work/validate`: Scheduled work operations.
  - React Web Dashboard Planner (`web/src/routes/Planner.tsx` and `web/src/features/planner`):
    - Weekly Roster view with human-readable week selector (`Week 1 - NOV 2026 (02 - 08 Nov)`), compact/expanded chip modes, problems-only filter, and worker capacity inspection.
    - Job Coverage view with persistent sticky day header (`sticky top-0 z-20` on table headers), site-by-site staffing gaps, normalized weekday pattern resolution (fixing Monday vs Thursday target resolution), chronological assignment priority (preventing new slots from stealing requirement from fulfilled visits), weekly quota-based excess evaluation (allowing Sunday compensatory shifts without false excess badges), 6-state visual legend (Fully Staffed, Under-Staffed, Quota Met, Excess Assigned, Public Holiday, and No Requirement), soft-teal Quota Met indicators, sky-blue Public Holiday badges, and purple excess badges/chips (`+X Excess`).
    - Fixed 1x/week periodic items without explicit pattern defaulting to Thursday by strictly resolving target day to Monday (`week_start`) and updating `_suggest_date` in `fw.rules.jobs.occurrences` for `total_slots == 1`.
    - Fixed periodic assignment priority in `get_coverage_view` to sort assigned dates strictly by `earliest_created` timestamp, guaranteeing that earlier assigned slots retain requirement fulfillment and subsequent slots are recorded as excess without slot swapping.
    - Added weekly rest day detection and warning notices in `AssignModal`, displaying candidate rest day badges (`⚠️ Rest Day Today`) and informing planners that standing schedules skip rest days and non-scheduled days (Sundays) on future weeks, recommending "Save Current Date" for one-off compensatory shifts.
    - Added comprehensive live end-to-end regression test suite `backend/tests/test_planner_scenarios.py` verifying target day resolution, sequential slot assignment, and rest day warnings.
    - Relative weekday alignment for monthly recurring standing assignments (e.g. preserving 1st Wednesday of the month across rolling 13-month horizon), planning week Monday anchoring, and guaranteed explicit date materialization for off-day/holiday compensatory shifts.
    - Assign Modal with staged crew editing, clean `✕` remove chips, no automatic server calls, explicit "Save Current Date" vs "Save Recursively (Standing Team)" alongside "Cancel", candidate search, multi-tier ranking, automatic PERMANENT conflict blocking, supervisor crew filter toggle, accurate Quota Met warning notice, compensatory shift tips, and clean recursive standing series cancellation.
    - Collapsible left navigation sidebar (`w-64` to `w-16`) with persisted toggle state, maximizing planner workspace view.
    - Global 401 Unauthorized response interceptor in `AuthContext` auto-clearing credentials and redirecting to `/login`.
    - Authenticated download streaming for Master Data template and error workbooks in `Imports.tsx`.
    - Top navigation Crew / Supervisor filter dropdown displaying supervisor names, filtering the Workers Capacity Side Panel and defaulting Assign Modal recommendations to that supervisor's crew.
    - Worker Capacity Side Panel displaying compact, space-efficient worker list grouped by supervisor crew with hours allocated vs standard hours, progress indicators, and capacity filters (All, Available, Overtime), populated immediately on initial mount.
    - Job Item modal clarity: re-labeled occurrence duration to "Work Shift Duration / Visit" and prevented default Mon-Sat selection for weekly-1x and periodic job items.
    - Employees & People view: primary grouping by Supervisor crew, Superintendent and Engineer chips with click-to-focus smooth scrolling, leadership oversight executive cards with click-to-filter, and organizational headcount metrics.
    - Excel export button downloading `.xlsx` roster formatted to the client's specification.
  - ADR-014: Planner standing assignments, scheduled work, and roster markers.
  - Integration tests and 300-worker roster performance benchmark (< 2s) in `backend/tests/test_scheduling_api.py`.
- PHASE-04 (Sites, boundaries and job items):
  - Map-stack compatibility gate (ADR-006): installed and verified `maplibre-gl@6.16.0`, `react-map-gl@8.1.3`, `terra-draw@1.39.0`, `terra-draw-maplibre-gl-adapter@1.5.0`, and modular Turf packages (`@turf/area`, `@turf/boolean-valid`, `@turf/kinks`, `@turf/centroid`). Interactive polygon drawing, vertex editing, area computation, and self-intersection checks verified.
  - Pure domain rules for jobs (`fw.rules.jobs`):
    - `format.py`: Job number validation (`^\d{2}[ABC]\d{5}$`), strict letter extraction (`A` = outdoor, `B`/`C` = indoor/water feature).
    - `frequency.py`: Structured frequency normalization and expected annual activities / hours calculation across WEEK, MONTH, QUARTER, YEAR.
    - `day_split.py`: 9-hour day chunk split (e.g. 42.688 h = 4 x 9.0h + 6.688h) and multi-day occurrence duration calculation.
    - `occurrences.py`: 13-month rolling horizon occurrence slot generation, budget-only staff types exclusion (seeded default `["HSE Engineer", "Project Manager", "Irrigation Engineer"]`).
  - Database migration `0005_sites_boundaries_jobs.py` introducing `worksites`, `job_items`, and `job_occurrences` tables with PostGIS Polygon geometry, GiST spatial indexing, optimistic locking, and check constraints.
  - Jobs module (`fw.modules.jobs`): Worksites CRUD, polygon boundary validation via PostGIS (`ST_IsValid`, `ST_Area > 0`, `ST_PointOnSurface`), boundary setup queue aggregation, copy boundary (pull and push), job items CRUD with automatic occurrence generation, validation panel calculations, occurrences listing/updating.
  - Import pipeline integration (`Worksites` and `Job_Items` sheets): Excel phrase frequency normalizer (e.g. "Daily", "Monthly", "6x / week"), hyphenated / combined job number rejection, atomic commit with automatic occurrence generation.
  - Web API endpoints mounted under `/api/v1`:
    - Worksites: `GET /worksites`, `POST /worksites`, `GET /worksites/{id}`, `PATCH /worksites/{id}`.
    - Boundaries: `PUT /worksites/{id}/boundary`, `POST /worksites/{id}/copy-boundary`, `POST /worksites/{id}/copy-boundary-to`, `PUT /accommodations/{id}/boundary`, `GET /boundary-queue`.
    - Job Items: `POST /worksites/{id}/job-items`, `PATCH /job-items/{id}`, `POST /job-items/{id}/generate-occurrences`, `GET /job-items/{id}/validation`.
    - Occurrences: `GET /occurrences`, `PATCH /occurrences/{id}`.
  - React Web Dashboard views:
    - `/worksites` (`web/src/routes/Worksites.tsx`): Filterable worksites list, outdoor/indoor indicators, boundary status chips, create worksite modal.
    - `/worksites/$worksiteId` (`web/src/routes/WorksiteDetail.tsx`): Overview tab with metadata & inline editing; Job Items tab with create/edit modal; Boundary tab with interactive MapLibre + Terra Draw editor, area calculation, copy boundary modals; Occurrences tab with 13-month slot schedule table.
    - `/boundaries` (`web/src/routes/Boundaries.tsx`): Boundary setup queue with overall completion bar, metric cards for worksites and accommodations, filterable queue table, direct draw actions, and camp boundary drawing modal.
    - Map components (`web/src/features/map`): `MapContainer` with satellite/streets switcher, API key setup prompt banner, OSM fallback; `PolygonEditor` with Terra Draw and Turf validity checks; `PlaceSearch` for Dubai / KSA geocoding.
- PHASE-03 (Import framework, master data import and salary structures):
  - Pure domain rules for payroll salary arithmetic (`fw.rules.payroll.salary`): fixed salary portion calculation, standard round-to-cents money rounding, upcoming 1st-of-month effective date computation, and salary delta computation.
  - Pure domain rules for workbook normalization and validation (`fw.rules.imports.normalizer`, `fw.rules.imports.validator`): text normalization, grade code year suffix stripping, controlled Staff Grade Description (SGD) aliases with unknown flag, cell semantics (`_` clears optional, blank preserves, error on clearing required), date range checks, intra-file natural key clash detection, and reporting line hierarchy issue detection (cycles, self-reference, multi-supervisor).
  - Database migration `0004_import_and_salary.py` adding `import_batches`, `import_rows`, and `employee_salary` tables with foreign keys and check constraints.
  - Imports module (`fw.modules.imports`): Code-driven single source of truth `SHEET_REGISTRY` covering 14 sheets, dynamic Excel template generator (`tools/generate_import_template.py` and `generator.py`), multipart/raw workbook parser with composite same-file foreign key resolution, preview engine with field-level diffs (`old -> new`), atomic multi-sheet commit in dependency order, user provisioning for web roles, and guarded safe rollback (`POST /imports/{id}/rollback`).
  - Payroll module (`fw.modules.payroll`): Effective-dated worker salary structure management, revision history, and query services.
  - Web API endpoints mounted under `/api/v1`:
    - Imports: `GET /imports/template`, `POST /imports`, `GET /imports/{id}/preview`, `POST /imports/{id}/commit`, `POST /imports/{id}/rollback`, `GET /imports/{id}/errors.xlsx`, `GET /imports`.
    - Salary: `GET /employees/{id}/salary`, `POST /employees/{id}/salary`, `GET /salary-structures`.
  - React Web Dashboard views:
    - `/imports` view (`web/src/routes/Imports.tsx`): Excel upload zone, cell rule guide, preview summary metrics, filterable rows with status badges and visual diffs, error report generator, batch history with safe rollback.
    - `/salary-structures` view (`web/src/routes/SalaryStructures.tsx`): List of workers with current salary structure, standard hours, active fixed salary portion, last change date and difference delta, revision history drawer, and salary revision modal.
    - Employee Detail (`web/src/routes/EmployeeDetail.tsx`): New Salary tab displaying active structure, last change badge, and revision history.
  - ADR-013: Import pipeline framework, registry single-source, and salary structures.
  - Automated demo script for Phase 03 (`backend/tools/demo_phase03.py`).
- PHASE-02 (Settings, time rules and calendars):
  - Pure domain rules resolver for time rules (`fw.rules.time_rules`): scope hierarchy (`EMPLOYEE > TEAM > DRIVERS > COMPANY`), manager relationship weighting (`SUPERVISOR > SUPERINTENDENT > ENGINEER`), specificity (`OUTDOOR_ONLY` / `INDOOR_ONLY` > `ALL`), and field-level inheritance with full explainability.
  - Verification of the client 5-point planned schedule calculation: 05:00 / 06:00 / 0:30 / 15:30 / 17:00 => 12:00 total (720 min), 09:00 worked (540 min).
  - Database migration `0003_settings_and_time_rules.py` adding `time_rules`, `public_holidays`, and `consent_policies` tables with foreign keys and check constraints; seeded catalog settings, default company time rule, statutory public holidays (AE & SA), and consent policy v1.
  - Settings service & schemas supporting effective-dated updates (closing prior active records at `new_effective_from - 1 day`), setting history tracking, and time rule CRUD with scope protection for Engineers.
  - Explainer API endpoint `GET /time-rules/resolve` returning effective schedule, planned total/worked minutes, standard hours adjustments, winning primary rule, and field-level source traces.
  - Public holidays endpoints (`GET /public-holidays`, `POST /public-holidays`, `DELETE /public-holidays/{id}`) and consent policy endpoints (`GET /consent-policies`, `POST /consent-policies`).
  - Web Dashboard Settings view (`web/src/routes/Settings.tsx`): 7 tabs (Company Settings with effective-dated edit modal & history drawer, Time Rules table with create modal, Resolver Check Tool with visual 5-point schedule & candidate trace, Public Holidays, Budget-Only Staff Types checklist, Default Password policy, and Consent Notice publisher).
  - ADR-012: Time rules resolver hierarchy, field inheritance, and scope.
  - Automated demo script for Phase 02 (`backend/tools/demo_phase02.py`).
- PHASE-01 (Access and people):
  - Pure domain rules for hierarchy validation: cycle prevention in directed management graph, single supervisor constraint, and transitive descendant scope resolution (`fw.rules.hierarchy`).
  - Pure password policy rules: default password detection, strength validation, and expiration/locking after `default_password_max_days` (`fw.rules.password`).
  - Database migration `0002_access_and_people.py` introducing `audit_logs`, `users`, `user_sessions`, `employees`, `employee_reporting_lines`, `employee_grade_history`, `groups`, `zones`, `accommodations`, `employee_documents`, `registered_devices`, and `company_setting_values`.
  - Identity module with Argon2id password hashing, rotating refresh token sessions in httpOnly cookies, forced password change on default password, and Admin reset-to-default capability.
  - Org module providing Employees CRUD with optimistic locking (`version`), bulk update of operational settings, Grade Code change tracking, reporting lines management, groups/zones/accommodations, and documents/devices tracking.
  - Audit module recording append-only audit entries on all state-changing actions with actor, diff, entity_id, and timestamp.
  - Full Web API routers mounted under `/api/v1` for Auth, Employees, Users, Org Entities, Devices, and Audit Logs.
  - React Web Dashboard additions: Login view with forced password change flow, role-filtered Shell navigation, Employees table with supervisor grouping and bulk update modal, Employee Detail view with Profile/Hierarchy/Documents/Device/History tabs, Users Admin view, and Audit Log viewer.
  - ADR-011: Transitive reporting scope resolution and session token rotation.
  - Fictional seed script (`tools/seed_phase01.py`) and automated demo script (`tools/demo_phase01.py`).
- PHASE-00 (Foundation):
  - Monorepo structure (`backend/`, `web/`, `infra/`, `tools/`).
  - Docker Compose environment with PostGIS 16-3.4, FastAPI API container, Procrastinate worker, Vite/React web container, and Mailpit mail catcher.
  - Root `.env.example` and developer onboarding `README.md`.
  - Backend FastAPI app factory with `/health` (liveness) and `/health/ready` (database readiness).
  - Pydantic v2 settings with `DEPLOYMENT_COUNTRY` validation (`AE` or `SA`).
  - Async SQLAlchemy 2.0 session factory and Alembic migration baseline with PostGIS extension.
  - `core` shared libraries: RFC 7807 problem details error handling, UTC `Clock` port/adapters, JSON `structlog` logging, and domain event bus.
  - Country rule packs Protocol and implementations for UAE (`AE`) and Saudi Arabia (`SA`).
  - Architecture layers contract enforcement via `import-linter` (9 modular monolith layers + pure rules contract).
  - React 18 + Vite + TypeScript frontend shell with TanStack Router, Tailwind CSS, and OpenAPI code generator (`openapi-typescript`).
  - CI workflow (`.github/workflows/ci.yml`) covering linting, type-checking, architecture contract verification, database migration rollback, and web build.
  - PR template (`.github/pull_request_template.md`).
  - Full dependency verification audit in `docs/17-dependencies.md` and ADR 010.
- Documentation pack for Field Worker Tracker: requirements reference, 15 numbered docs, 6 design docs, 14 phase plans with context packs and checklists, decision register, ADRs 001-009, legal/compliance drafts, import template v1.0.
- Agent rules and skills (architecture, conventions, time and money, documentation, safety, dependencies, phase workflow; add-module, add-endpoint, add-synced-entity, db-migration, write-adr, import-column, add-dependency, start-phase, finish-phase).
### Decisions captured
- See `docs/decisions/decision-register.md` and the answers logs in `docs/reference/`.
