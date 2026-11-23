# ADR-029: Job budget, man-hours and planned vs actual

- **Status:** Accepted
- **Date:** 2026-11-23
- **Batch:** 5.4 (`fix/batch5.4`), migration `0023_revision_line_allowances`
- **Register:** DEC-59 (new); builds on DEC-58 / ADR-028, DEC-47, DEC-09/48 (budget-only staff)

## Context
The budget-vs-actual code counted activities with its own copy of the frequency rule, which ignored
`period_interval`, so fortnightly items counted twice. It ignored the item's start and end dates and the
worksite's end date, and pro-rated the annual budget with "days since start / 365, capped at 1". The
hourly rate used salary plus provisions × 1.05 / 208, without gratuity or leave salary, so a plan never
matched payroll's actual cost. Man-hours and cost were not shown on job items or while editing them. The
Project Attendance Summary counted every visit's minutes, approved or not.

## Options considered
1. Patch the existing loop in `PayrollService.get_budget_vs_actual`.
2. **One pure rule in `fw.rules.jobs.budget`, a `budget` module that loads everything in bulk,
   period-based planned vs actual.**
3. Count planned hours from the generated occurrences (exact by weekday, but tied to the occurrence
   horizon and much slower).

## Decision
- **Rule** (`fw.rules.jobs.budget`, pure):
  - activities/year from `calculate_expected_activities_per_year` (with `period_interval`);
  - hours = activities/year × staff × hours per activity, **pro-rated by day**: only days inside the
    period, the item's dates and the worksite contract dates count; each day is worth 1 / (length of its
    contract year), so a full contract year gives exactly the annual figure;
  - monthly cost of a grade = salary portion (basic + special + fixed OT + bonus + telephone +
    housing/transport) + **the revision line's own provisions** (visa, air ticket, uniform, medical,
    accommodation, transportation) + gratuity (basic/365×30) + leave salary (basic/12), then
    `hr_overhead_rate`, built with payroll's own formula functions;
  - hourly rate = monthly cost / `standard_ot_divisor_hours`. No hard-coded 1.05 or 208:
    `SETTING_MISSING` (422) for Admin money views.
- **Provisions (owner, 23 Nov):** the plan uses the revision's provisions (the client's R2-2026 budget
  basis, 1,720/month for most grades); payroll keeps the settings (842). Where they differ for a grade,
  planned-vs-actual shows `PROVISIONS_DIFFER_FROM_PAYROLL` ("plan uses revision provisions X, payroll uses
  settings Y").
- **Missing grade:** `MISSING_GRADE_RATE` (from ADR-028); the item is left out of the totals.
- **Contract year:** anniversary to anniversary from the worksite `start_date` (calendar year when
  blank); default period everywhere, using the site-local today.
- **Actual hours:** site-visit minutes on approved days (payroll's rule: APPROVED, or not REJECTED with no
  review reasons), split over that worker's scheduled job items at that worksite that day by
  `assigned_hours`; minutes with nothing scheduled are "unscheduled hours" at worksite level. Never a
  default of 8.
- **Actual cost:** approved `job_cost_allocations`, pro-rated by day into the period's months; each
  worksite-month is split over its items by approved actual hours (scheduled hours when the month has
  none). Payroll allocation itself is unchanged (still by scheduled hours).
- **Budget-only staff types:** actual = planned (hours and cost).
- **Manual `budget_amount`:** stays an annual worksite figure, pro-rated by day.
- **Telephone and housing/transport** on revision lines: new columns (0023), default 0, optional import
  columns after `notes`.
- **Module:** `fw.modules.budget` (layer between reports/imports/archive and payroll; owns no tables).
  A fixed number of queries whatever the number of worksites.
- **Roles (DEC-47):** hours for everyone who can see the worksite; rates, costs and provision notes for
  Admin only.

## Why
One rule for every screen means the form, the worksite page, the Payroll tab and the Job Costing report
agree. Building the grade cost with payroll's functions means plan and actual are costed the same way,
so the only systematic difference left is the provision basis, and that is now shown. Day pro-rating is
simple, exact over a contract year and cheap.

## Consequences
- Planned figures change: fortnightly items halve; partial-year items and ended contracts shrink; rates
  rise (gratuity, leave salary and revision provisions now included).
- `GET /payroll/budget-vs-actual` keeps its old fields, but `prorated_budget` is the planned cost for the
  period, not "annual × elapsed/365".
- Revision detail `planned_hourly_cost` uses the same rule and needs the rate settings.
- Open (handover): confirm with the client which provision values are current (payroll may need a
  transportation provision and updated settings); payroll allocation by attended hours.
- Docs: `docs/07`, `docs/08`, `docs/11`, `docs/modules/budget.md`, `docs/13`.
