# 008 - Effective-dated configuration and time rules
Status: Accepted
Date: 2026-10-29

## Context
Working hours and breaks change by season (Ramadan, summer midday break) and by job (extended breaks for outdoor work). The client requires that the system account for what the setting was **when the work took place**, not only the current configuration. Late events and corrections cause old dates to be recalculated.

## Options considered
1. Mutable current settings plus a snapshot on each calculation.
2. Effective-dated values (and dated time rules) resolved by work date, plus a snapshot on each calculation.

## Decision
Option 2. Settings are stored as effective-dated rows (`company_setting_values`: key, country, value, effective_from, effective_to) and never edited in place. Seasonal rules are `time_rules` (country, date range, all/outdoor-only, daily-hours change, break, blocked window). Scheduling capacity and attendance always resolve configuration **as of the work date**, including recalculation of old dates. Each calculation still snapshots the values it used.

## Why
Recalculating a past day gives the same result it would have had at the time unless the events changed, which keeps approvals and payroll defensible. A snapshot alone cannot reproduce a result when events arrive late.

## Consequences
Settings screens add a new value with a start date and show history. Resolution adds a small lookup (cacheable). The mobile SETTINGS payload carries upcoming changes inside the sync window. Rules inside a range that has attendance are closed or superseded, never deleted. See `docs/03-business-rules.md` (BR-ST-04, BR-ST-05), `docs/04-scheduling-engine.md` section 14 and `docs/05-attendance-engine.md`.
