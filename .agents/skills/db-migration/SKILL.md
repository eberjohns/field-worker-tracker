---
name: db-migration
description: Use for any database schema change. Creates a safe, reversible Alembic migration and updates the data-model doc.
---
1. Change the SQLAlchemy models, then generate the migration with Alembic and **read the generated SQL**.
2. Write a working `downgrade`.
3. Prefer additive changes. To rename or remove, use expand/contract: add the new column/table, backfill, switch the code, and remove the old one in a later release.
4. Add indexes for new foreign keys and for columns used in filters or ordering. High-volume tables (`mobile_event_logs`, `sync_changes`, `audit_logs`) need an explicit index review.
5. Spatial columns use PostGIS `geometry(..., 4326)` with a GiST index.
6. Update `docs/07-data-model.md` (fields, constraints, reason).
Never edit an already-applied migration; add a new one.
