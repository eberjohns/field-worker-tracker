# 019 - Live Location Access Logging, SSE Streaming, and Follow-Up Workflows

Status: Accepted  
Date: 2026-11-10  

## Context
Phase 09 introduces live workforce monitoring (`/live`), real-time Server-Sent Events (SSE) streaming of mobile device locations, and day-close pending visit tracking. Because real-time location monitoring constitutes surveillance data under privacy regulations, every view of live positions (both polling and streaming connections) must be auditable. In addition, mobile devices upload batched events asynchronously after offline periods, meaning late uploads must never overwrite newer positions.

## Options considered
1. **Log location reads into general `audit_logs`**:
   - *Pros*: Single audit table.
   - *Cons*: High-frequency polling (e.g. every 15-30s from multiple supervisors) would flood the business audit log, diluting administrative and financial audit trails and degrading query performance.
2. **Dedicated `live_location_access_logs` table**:
   - *Pros*: Separates high-volume location surveillance audit records from business entity audit trails; indexed by user and timestamp; allows independent retention policies and high-speed logging.
   - *Cons*: An extra table to maintain.
3. **SSE authentication via query-param JWT vs. single-use tickets**:
   - EventSource browser APIs do not support setting custom `Authorization` headers. Passing long-lived JWTs in URLs leaks tokens in web server access logs and browser history.
   - Short-lived (30s) single-use stream tickets (`POST /api/v1/live/stream-ticket`) eliminate token leakage.

## Decision
1. **Dedicated Surveillance Access Table**:
   - Created `live_location_access_logs` (`id`, `user_id`, `access_type` ['POLL', 'STREAM'], `filters`, `client_ip`, `user_agent`, `created_at`).
   - Every execution of `GET /api/v1/live/positions` and `GET /api/v1/live/stream` writes an entry.
2. **Stream Ticket Authentication**:
   - Front-end requests a 30s ticket via authenticated `POST /api/v1/live/stream-ticket`.
   - The ticket is consumed on `GET /api/v1/live/stream?ticket=...` and immediately invalidated (single-use).
3. **Newest-Wins Position Cache**:
   - `employee_last_position` is updated only if `event_timestamp_utc >= existing.event_timestamp_utc`. Late uploads from previously offline phones enrich `mobile_event_logs` but do not revert the live map marker.
4. **Pending Visit Follow-Up**:
   - Detects unvisited scheduled work at day close (`OPEN`). Approved leave strictly exempts workers.
   - Supervisors record explanations (`EXPLAINED`). Engineers/Admins can reschedule (`RESCHEDULED` with source `FOLLOW_UP`) or close (`CLOSED`). Late uploads automatically reconcile and close open pending visits.

## Why
This architecture guarantees worker privacy auditability without polluting financial audit logs, secures streaming endpoints against token leakage, and prevents out-of-order mobile sync events from disrupting real-time operations.

## Consequences
- Live location access is fully accountable and compliant.
- `audit_logs` remains clean and performant.
- `GET /api/v1/live/stream` automatically falls back to 30s polling if SSE is interrupted.

