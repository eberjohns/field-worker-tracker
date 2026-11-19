# 025 - Batch 5 Audit Fixes: Overtime Alignment, Worker Scheduling, and Multi-Process Safety
Status: Accepted
Date: 2026-11-19

## Context
Following a client architecture audit, several operational gaps and edge cases were identified across business rules and infrastructure:
1. **OT2 Overtime Calculation**: The engine contained hard-coded Sunday checks (`is_ot2_weekday`). DEC-01 specifies that OT2 applies exclusively to all hours worked on a public holiday or on the worker's own weekly off day. Missing weekly off days were defaulting to Sunday rather than surfacing an explicit anomaly.
2. **Background Jobs Execution**: Scheduled tasks (watchdogs, pending visits detection, document expiry checks, retention purges, and yearly archives) required a reliable background scheduler rather than lazy web-request evaluations.
3. **Multi-Process SSE Scaling**: In-memory `StreamTicketManager` tickets prevented stream authentication across multiple instances, and `LivePositionBroadcaster` lacked a PostgreSQL `LISTEN/NOTIFY` fan-out loop across process boundaries.
4. **Site-Local Timezone Consistency**: Reassignments and shifts evaluated against system local `date.today()` or hardcoded `ZoneInfo("Asia/Dubai")` instead of the site's configured country timezone.
5. **Attendance and Payroll Resilience**: Silent `except Exception: pass` blocks in attendance calculation masked data corruption and missing salary structures. Additionally, post-payroll month-end report generation failures should not roll back finalized payroll approvals.

## Options considered
- **External job queues (Celery / Redis / Procrastinate)**: Required additional external services and dependencies that introduced deployment overhead on Windows/production.
- **Async scheduler on native asyncpg pool**: A dedicated async scheduler in `fw/worker.py` utilizing the application's existing PostgreSQL connection pool, periodic intervals, and site-local date tracking.
- **Database-backed stream tickets**: PostgreSQL table `stream_tickets` with short 30-second TTL and atomic `consumed_at IS NULL` single-use consumption.

## Decision
1. **OT2 Rule Alignment (DEC-01, DEC-21)**:
   - `is_ot2_day = inputs.is_public_holiday or inputs.is_weekly_off`.
   - On an OT2 day, all worked hours are OT2.
   - On an unassigned non-off day, all worked hours are OT1.
   - On a normal assigned day, OT1 applies only to hours worked beyond standard hours.
   - Removed hardcoded Sunday checks. If `weekly_off_day` is missing, `is_weekly_off` evaluates to `False` and flags `NO_WEEKLY_OFF_DAY`.
2. **Background Jobs Scheduler (`fw/worker.py`)**:
   - Implemented `WorkerScheduler` executing periodic watchdogs (every 15 min), site-local daily pending visits detection and reminders, daily document expiry checks, routine retention purge (>60d sync changes, >6mo notifications), and yearly archiving.
   - Yearly archiving in the scheduler runs with `purge_live_events=False`; raw events are never purged automatically. Live record purging remains strictly an explicit manual Admin action until DEC-38 is confirmed with counsel/client.
   - Removed lazy document expiry checks from `notifications/service.py`.
   - Each job runs idempotently, logs start/completion, and logs `JOB_FAILURE` admin alerts on unhandled errors.
3. **Multi-Process Live Map Architecture**:
   - Migration `0019_stream_tickets.py` stores single-use SSE tickets with 30s TTL. Atomic `UPDATE ... RETURNING` ensures single-use validation across processes.
   - `LivePositionBroadcaster` connects via `asyncpg` to PostgreSQL `LISTEN live_positions` channel, fanning out updates to local SSE subscribers and deduplicating recent events.
4. **Site-Local Clocks**:
   - Centralized `site_today(country)` and `site_now(country)` in `fw/core/clock.py` using country timezone settings.
   - Replaced all raw `date.today()` and hardcoded `ZoneInfo("Asia/Dubai")` usages.
5. **Attendance & Payroll Fault Isolation**:
   - Removed blanket exception swallowing in attendance calculation; missing salary structures flag `NO_SALARY_STRUCTURE`.
   - Month-end report generation executes in a separate transaction post-commit, creating `MONTH_END_REPORTS_FAILED` alerts without rolling back approved payroll runs.

## Why
Ensures strict compliance with client requirements, guarantees multi-process safety in containerized environments, and eliminates silent failures across background operations.

## Consequences
- Multi-instance deployments can safely authenticate SSE connections and distribute live position events.
- Background jobs run deterministically without relying on user dashboard activity.
- Client requirements and decision register accurately reflect OT2 and deduction business rules.
