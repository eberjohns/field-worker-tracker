# Budget Module (`fw.modules.budget`)

## Purpose
Planned man-hours and cost per job item and per worksite, and planned vs actual (hours and money) for
any period, per job item and per month. Decision: DEC-59, ADR-029.

## Owned tables
None. It reads:
- `jobs`: worksites and job items;
- `payroll`: salary revisions and lines, approved payroll runs, records and job cost allocations;
- `attendance`: site visits, attendance records and their current calculation (approval);
- `scheduling`: scheduled work (to split a day's hours over job items);
- `settings`: `hr_overhead_rate`, `standard_ot_divisor_hours`, `provision_*`,
  `budget_only_staff_types`, `default_salary_revision_code`.

## Public interface (`fw.modules.budget`)
- `BudgetService.worksite_budget(_by_id)`: per-item `JobItemBudget` and `WorksiteBudgetTotals` for the
  current contract year (used by the worksite detail and job item create/update responses).
- `BudgetService.preview_item`: the same for an unsaved job item.
- `BudgetService.planned_vs_actual`: `WorksiteBudgetVsActualItem` per worksite (items, months, warnings).
- `budget_router`:
  - `GET /payroll/budget-vs-actual` (Admin);
  - `GET /worksites/{id}/planned-vs-actual` (worksite scope; money Admin only);
  - `POST /worksites/{id}/job-items/budget-preview` and `POST /job-items/budget-preview` (Admin, Engineer).

The arithmetic is in `fw.rules.jobs.budget` (pure).

## Dependencies and layer
Layer between `reports | imports | archive` and `payroll` (import-linter contract), because it reads
payroll, attendance, scheduling and jobs, and the Job Costing report reads it. It never writes.

## Why a separate module
`payroll` already depends on `jobs`, so the jobs API could not call payroll for budgets without a cycle,
and the budget combines five modules' data. Keeping it separate keeps payroll about pay, and gives one
place that loads everything in bulk (a fixed number of queries for any number of worksites).
