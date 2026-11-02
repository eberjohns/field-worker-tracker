---
name: add-synced-entity
description: Use when a new kind of data must reach the worker's phone, or when an existing synced entity changes shape or fan-out. Handles change-log writes for affected workers.
---
Read `docs/09-mobile-sync-contract.md` and `docs/decisions/003-sync-change-log.md` first.
1. Add the entity type to the `SyncEntityType` enum and define its payload schema (the full current snapshot of that entity, small).
2. In the `sync` module, add or extend the function that finds the **affected workers** for a change (for example: workers scheduled in the next 30 days at that site) and writes one `sync_changes` row per worker (`UPSERT`, or `DELETE` as a tombstone).
3. Include the entity in the full-snapshot builder used by the handshake and the resync.
4. Make the source module publish a domain event (for example `ScheduledWorkChanged`) on the `core` event bus **inside the same database transaction** as the change. The `sync` module's handler (registered at startup) writes the rows. Lower modules never import `sync`.
5. Update the entity table in `docs/09-mobile-sync-contract.md` (payload, fan-out rule, priority).
Never send one worker's data to another worker. Never write sync rows outside the transaction, and never import `sync` from a lower module.
