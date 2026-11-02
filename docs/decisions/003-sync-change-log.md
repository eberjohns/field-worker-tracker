# 003 - Per-worker sync change log
Status: Accepted
Date: 2026-10-28

## Context
Phones store the worker's profile, the next 30 days of schedule, job info and boundaries, work offline, and must be updated when something changes. The server cannot reliably know whether a phone is online.

## Options considered
1. Phone re-downloads everything periodically.
2. WebSockets/long-lived connections for live updates.
3. Per-worker change log with an increasing cursor, delta pulls, and a push "nudge".

## Decision
Option 3. Each relevant change writes one `sync_changes` row per affected worker (full entity snapshot, `UPSERT` or `DELETE` tombstone) in the **same transaction** as the change. The phone pulls `changes?cursor=N` and acks. Triggers: silent push (nudge only), the cursor piggybacked on every response, heartbeat, app open and the pre-alarm check. If the cursor is older than the compaction floor the phone does a full snapshot resync.

## Why
Cheap and battery-friendly; resilient to lost pushes; idempotent apply; the server can measure sync lag per device (`last_acked_cursor`) without assuming "online". WebSockets drain battery and are killed by the OS in the background.

## Consequences
Fan-out on shared data (a boundary change writes rows for every worker scheduled there). Compaction needed (60 days, cursor floor). Changes may be coalesced to the latest version per entity. Writers publish domain events; the `sync` module subscribes (see 001 and `docs/13-architecture.md`). Contract in `docs/09-mobile-sync-contract.md`.
