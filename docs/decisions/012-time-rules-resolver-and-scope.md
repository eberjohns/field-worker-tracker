# 012 - Time Rules Resolver Hierarchy, Field Inheritance, and Scope

Status: Accepted  
Date: 2026-11-03  

## Context
In Phase 02, system settings, planned-time rules, public holidays, and consent policy versions are established.
Client decisions DEC-03, DEC-21, DEC-35, and DEC-41 define how planned work hours and breaks are scheduled:
1. Schedules have five points: accommodation start, first-site start, break minutes, last-site end, and accommodation end.
2. Rules exist at multiple scopes: COMPANY, DRIVERS, TEAM (workers linked to a manager), and EMPLOYEE (individual worker).
3. Work-period rules (Ramadan, Summer outdoor midday break) apply over date ranges and may restrict by worksite environment (outdoor vs indoor).
4. Rules are effective-dated and must explain which rule won for any past, present, or future work date.

## Options considered
- **Scope vs Environment Specificity**:
  - *Option A (Environment trumps scope)*: A COMPANY rule with `OUTDOOR_ONLY` overrides a TEAM rule with `ALL`.
  - *Option B (Scope trumps environment)*: Scope precedence is primary (`EMPLOYEE > TEAM > DRIVERS > COMPANY`); within the same scope, `OUTDOOR_ONLY` / `INDOOR_ONLY` wins over `ALL`.
- **Field Inheritance**:
  - *Option A (All-or-nothing rule win)*: The highest-priority rule supplies all five times; if any field is empty, it remains null.
  - *Option B (Field-level inheritance)*: The highest-priority matching rule sets the primary identity, but any null/unspecified fields inherit independently down the candidate chain until resolved.
- **Multi-Manager Tie-Breaking**:
  - *Option A (Arbitrary or first created)*: Take the first matching team rule in the database.
  - *Option B (Relationship-weighted)*: Direct `SUPERVISOR` team rule takes precedence over `SUPERINTENDENT`, which takes precedence over `ENGINEER`. If the same relationship level, the rule with the most recent `start_date` wins.
- **Effective-Date Boundaries**:
  - *Option A (Half-open intervals)*: Set `prev.effective_to = new_from` and evaluate using strictly `<`.
  - *Option B (Inclusive non-overlapping days)*: Set `prev.effective_to = new_from - 1 day`, keeping date filters `effective_from <= date <= effective_to` clear and consistent across SQL and UI calendars.

## Decision
- Adopt **Option B (Scope is primary)**: `EMPLOYEE > TEAM > DRIVERS > COMPANY`. Within the same scope, narrower `applies_to` (`OUTDOOR_ONLY` / `INDOOR_ONLY`) wins over `ALL`.
- Adopt **Option B (Field-level inheritance)**: Missing times and breaks inherit from the next applicable rule down the chain, with full explainability recorded in `winning_sources`.
- Adopt **Option B (Relationship-weighted tie-breaking)**: `SUPERVISOR > SUPERINTENDENT > ENGINEER`, followed by `start_date` descending.
- Adopt **Option B (Inclusive non-overlapping dates)**: Updating a setting row closes the previous row on `new_effective_from - 1 day`.
- **Accommodation handling**: For workers without company accommodation (`employee.accommodation_id IS NULL`), nominal accommodation times are recorded with `has_accommodation = False`, and `planned_total_minutes` equals `last_site_end - first_site_start` (BR-AT-16).
- **Engineer Scope**: Engineers can only view and manage time rules for employees and managers within their reporting scope. They cannot create or modify company-wide or driver rules.

## Why
- Scope-primary precedence ensures that direct manager instructions (or individual technician agreements) take priority over organization-wide policies, while field inheritance prevents managers from needing to re-enter unchanged commute times when adjusting a break.
- Relationship weighting reflects practical site authority: the immediate field supervisor knows the daily site timing best.
- Non-overlapping inclusive calendar dates avoid timezone edge cases when resolving by work date.

## Consequences
- Pure business rule in `backend/src/fw/rules/time_rules.py` implements the resolver with zero external dependencies.
- `GET /time-rules/resolve` provides full explainability (`winning_sources` and candidate trace) for auditability.
- Migration `0003_settings_and_time_rules.py` adds `time_rules`, `public_holidays`, and `consent_policies` with foreign keys to users and employees.
