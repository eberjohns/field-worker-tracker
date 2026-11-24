# ADR-032: Base Planner templates materialised into scheduled work

- **Status:** Accepted
- **Date:** 2026-11-25
- **Batch:** `fix/roster-materialise-absent` (v1.22.0), owner decision of 25 Nov 2026
- **Affects:** `docs/04-scheduling-engine.md` section 12, `docs/05-attendance-engine.md` section 6b-2,
  `docs/18-company-settings.md` (`roster_materialise_weeks`), `docs/09-mobile-sync-contract.md` (no shape change)

## Context
Base Planner templates (ADR-015) were only a blueprint. The Operational Planner drew them as muted
chips and the phones received "virtual" schedule items for them, but no `scheduled_work` row existed
unless someone created one by hand. Everything downstream that reads `scheduled_work` (attendance
expectations, the day close, pending visits, payroll's planned hours) therefore saw a worker on a
template as unscheduled. Without a row, an absent worker produced no attendance record at all, so
the day was never reviewed or deducted. The owner asked for the templates to become real
scheduled work, without losing anything planned by hand.

## Options considered
1. **Compute the blueprint on the fly everywhere** (attendance, day close, payroll): no new rows,
   but every reader repeats the template rules, and edits in the Operational Planner have nothing
   to attach to.
2. **Materialise the whole contract period**: simple to reason about, but months of rows to update
   on every template change, and far-future rows go stale as people join and leave.
3. **A rolling window of real rows** (from tomorrow to N weeks ahead), refreshed daily and when a
   template, base entry or leave changes, with a clear rule for which rows the system may change.

## Decision
Option 3.
- **Window:** from tomorrow (site date) to `roster_materialise_weeks` ahead (company setting,
  default 4, at most 26). Today and the past are never touched, so attendance already being
  recorded is never moved.
- **Rows:** `scheduled_work` with `source = TEMPLATE`, `status = ACTIVE`, `version = 1`. One row
  per employee, job item and date: if any row already exists for that key (any source or status),
  the materialiser creates nothing.
- **"Untouched" is the ownership rule:** a row is the system's only while it is `TEMPLATE`, `ACTIVE`
  and at version 1. Every Operational Planner edit, cover or reassignment changes the status or
  bumps the version, so those rows are never updated or deleted by a template change. Untouched
  rows follow the template (hours updated; deleted when the template no longer produces them).
- **Same rules as the Operational Planner:** the worker's weekly off and approved leave are
  skipped (leave keeps its cover flow); template, job item and worksite dates; inactive employees
  and items; budget-only staff types; the PERMANENT/REMOTE assignment rules (`validate_assignment`).
  More than the standard day is only logged. Public holidays are scheduled as normal (hours worked
  on them become OT2).
- **Triggers:** the daily worker job (after the day close), saving a template, approving leave
  (including leave imported as approved). Each run takes a transaction advisory lock, so two runs
  never interleave, and running twice changes nothing.
- **Operational Planner on template rows:** removing a base worker cancels their TEMPLATE row in
  place; a cover marks it REASSIGNED and links it (`original_scheduled_work_id`); restore and undo
  put it back to ACTIVE.
- **Phones:** targeted `SCHEDULE_ITEM` upserts for the rows that changed, a DELETE for rows removed,
  and a tombstone for the virtual blueprint item a real row replaces. No contract shape change:
  `source = TEMPLATE` is an unknown value, which the contract treats as PLANNED.

## Why
Real rows give attendance, the day close and payroll one source for "who was planned", and give
manual edits something to change. A short window keeps template changes cheap and current. The
version and status rule needs no new column and is already maintained by every edit path.

## Consequences
- An absent worker on a template now gets an ABSENT day at day close (owner decision, same batch).
- Lengthening `roster_materialise_weeks` fills the extra weeks on the next run; shortening it leaves
  rows already created (they are still valid plans).
- A row edited by hand keeps its old hours if the template changes later; the planner shows it as
  an override.
- The virtual blueprint items in the mobile snapshot remain for dates beyond the window.
