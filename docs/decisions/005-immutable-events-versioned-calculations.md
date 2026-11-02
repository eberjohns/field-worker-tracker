# 005 - Immutable events and versioned calculations
Status: Accepted
Date: 2026-10-28

## Context
Attendance and payroll must be explainable and defensible. Phones can be offline, clocks can be wrong, rules and settings change, and people correct data.

## Options considered
1. Update attendance rows in place.
2. Store raw events immutably and derive attendance as immutable calculation versions; snapshot payroll.

## Decision
Option 2. `mobile_event_logs` is append-only (server-side enrichment columns aside). Each recalculation creates a new `attendance_calculations` version holding its inputs snapshot and `input_hash`; comments and approvals are separate append-only records pointing to the version. Finalized payroll stores a complete snapshot. Inferred data is labelled INFERRED. Device clocks are never rewritten, only flagged.

## Why
Full traceability, safe corrections, no history rewriting, and reproducible results.

## Consequences
More storage (small relative to events). Recalculation must be idempotent (input hash). Approval resets when a new version materially changes results. Dates in finalized payroll periods are locked. See `docs/05-attendance-engine.md` and `docs/06-payroll-and-cost.md`.
