# Background Jobs Module (`fw.modules.tasks`)

## Purpose
Run a long operation that a user starts and waits for outside the request that started it,
with its status and progress, so the page can show "Calculating employees 120 / 580" instead of
a request that hangs for half a minute. The first job is the payroll draft (Batch 9 step 4).
Architecture: `docs/13-architecture.md`, section 7.

## Owned tables
- `background_jobs` (`docs/07-data-model.md`).

## Public interface (`fw.modules.tasks`)
- `BackgroundJobService.start(kind, params, fn, dedupe_key, user_id)`: records the job and runs
  `fn(session)` as an asyncio task in this process. The session commits only when `fn` returns;
  `fn` returns the job's `result` (a JSON-able dict). `409 JOB_ALREADY_RUNNING` while a job with
  the same `dedupe_key` is QUEUED or RUNNING.
- `BackgroundJobService.get`, `list_recent`: read jobs (stale active jobs become INTERRUPTED first).
- `BackgroundJobService.wait(job_id)`: wait for a job of this process (tests).
- `shutdown_background_jobs()`: called at app shutdown; running jobs store INTERRUPTED.
- `BackgroundJob`, `BackgroundJobRead`, the `JOB_*` statuses.

Code that runs inside a job reports progress with `fw.core.progress.report_progress(phase, done,
total)` and gives other requests a turn with `yield_to_loop()`. Both live in `fw.core`, so a
module reports progress without depending on this one; outside a job they do nothing.

The HTTP routes are in `fw/api/background_jobs.py` (`GET /background-jobs`, `GET
/background-jobs/{id}`). The routes that start a job belong to the module that owns the work
(for example `POST /payroll/runs/jobs`).

## Dependencies
`fw.core` only. It sits in its own layer just above `fw.core` in the import-linter contract, so
every business module may start a job.

## Why a separate module
Job bookkeeping (status, progress, heartbeat, one-at-a-time per key, interruption) is the same
for every long operation. Keeping it out of payroll means imports, exports and the approved-run
reports can use it later without copying it.
