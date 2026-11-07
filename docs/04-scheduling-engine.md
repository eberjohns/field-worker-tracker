# 04 - Planning and Scheduling Engine

Chain: **Worksite -> Job Item -> Occurrence -> Assignment -> Scheduled Work (one worker, one day)**. Pure logic: `backend/src/fw/rules/scheduling/`; persistence/orchestration: `modules/jobs`, `modules/scheduling`. UX: `design/D1-planner.md` and `design/D2-leave-and-reassignment.md`.

## 1. How planning works at the client (from their weekly schedule sheet)
- Planning is done for the **whole year across all contracts** by Admin/Engineers, then viewed and adjusted **weekly** as a roster: workers down, days across, each day listing the sites (job numbers) with hours, or a status: Free, Weekly-OFF, holiday-skipped.
- A worker's day can hold several sites with fractional hours (remote jobs) or one full-day site (permanent jobs).
- Weekly off is usually Sunday; a few workers have another day. Working week Mon-Sat.
- Daily totals must reach the worker's **standard hours** (8, 10 or 12 from the salary structure). Their old sheet double-counted hours; the system checks.

## 2. Frequency model (unchanged)
`frequency_unit` (WEEK/MONTH/QUARTER/YEAR) x `occurrences_per_period` x `period_interval`; `periods_per_year`: WEEK 52, MONTH 12, QUARTER 4, YEAR 1.
```
expected_activities_per_year = occurrences_per_period * periods_per_year / period_interval
expected_annual_hours        = activities * required_staff_count * hours_per_occurrence_per_staff
```
Client's declared figures are optional/informational; the calculated value is used (info only if they differ).

| Client text | Structured |
|---|---|
| Daily (6 days a week) | WEEK, 6, 1 -> 312/yr |
| One time / week | WEEK, 1, 1 -> 52 |
| One time / 2 weeks | WEEK, 1, 2 -> 26 |
| Three time / week | WEEK, 3, 1 -> 156 |
| Two time / month | MONTH, 2, 1 -> 24 |
| Monthly | MONTH, 1, 1 -> 12 |
| Quarterly | QUARTER, 1, 1 -> 4 |
| Three time / year | YEAR, 3, 1 -> 3 |

## 3. Occurrences
Generated on a rolling horizon (`occurrence_horizon_months`, 13) and on demand; idempotent by `(job_item_id, window_start, slot_index)`.
- WEEK: ISO-week windows; with `weekday_pattern` (length = count) -> dated occurrences, else undated with suggested dates.
- MONTH / QUARTER: calendar windows, undated with suggestions. YEAR: the calendar year split into `k` equal windows.
- Suggested date for the i-th of `k` occurrences over `n` working days: working day `floor((i + 0.5) * n / k)`.
- Snapshot `required_staff_count` and `required_hours_per_staff` at generation. Past/completed occurrences are never altered; future ones without assignments are rebuilt when the job item changes; ones with assignments are kept and flagged `NEEDS_REVIEW`.
- **Budget-only staff types** (company setting; e.g. HSE Engineer, Project Manager, Irrigation Engineer) never generate occurrences: they exist only for the budget. The list is pre-filled from the distinct staff types found in job items; Admin ticks which are budget-only. Those people are not tracked.

## 4. Hours
- **Job unit day** `planned_workday_hours` (9): a job's `hours_per_occurrence_per_staff` (H) over this gives days per occurrence (`ceil(H/9)`; e.g. 42.688 h = 4 x 9 + 6.688). Hours are never divided among workers.
- **Worker capacity** = the worker's **standard hours** (salary structure; default `standard_hours_default` 8), reduced by time rules in force (Ramadan: -2 h). The planner shows allocated hours against it. Allocating more than standard hours is allowed and shows as **planned overtime** (warning); less shows **free hours**.
- A worker should be assigned to fulfil their standard hours each working day.

## 5. Assignments
**Standing assignment** (the year plan): worker <-> job item for a date range, optional weekday pattern and hours per day (default from the job item). The system generates daily Scheduled Work from it on the job's working days. Used for PERMANENT jobs and any recurring daily/weekly team.
**Direct assignment**: worker <-> one occurrence/date(s). Used for REMOTE periodic jobs (monthly, quarterly, yearly) and one-offs.
**Scheduled Work**: employee + work_date + occurrence + hours + sequence + status + origin (STANDING / DIRECT / EXCEPTION). One ACTIVE row per (employee, date, occurrence); `sequence` unique per (employee, date).
- **PERMANENT** job item: a worker's day with a PERMANENT assignment holds no other assignment. **REMOTE**: several per day while hours remain (sum shown against standard hours).
- Changing a standing assignment from a date forward (worker leaves, new joiner) is a permanent change, not a temporary reassignment.

## 6. Day markers (explainability)
Every roster cell shows why a day has no work. Markers are computed, not stored:
| Marker | Meaning |
|---|---|
| SKIPPED (public holiday) | Jobs are skipped on public holidays; shown as skipped |
| WEEKLY_OFF | The worker's weekly off day (own, else the country default, else none) |
| ON_LEAVE | Approved leave |
| TO_BE_COVERED | A job slot with no available worker (leave, weekly off) - needs cover |
| FREE | The worker has no assignment and is available |
| NO_BOUNDARY | The site has no boundary yet |
Weekly off and leave apply **only where they exist** (no weekly off defined and no company default means no skipping).

## 7. Validation
Errors reject; warnings need acknowledgement.
| Code | Type | Condition |
|---|---|---|
| DUPLICATE_ASSIGNMENT | error | same employee/date/occurrence |
| EMPLOYEE_INACTIVE | error | inactive or outside employment dates |
| JOB_INACTIVE | error | inactive worksite/item or cancelled occurrence |
| OUTSIDE_JOB_DATES | error | date outside the item's period |
| BUDGET_ONLY_NOT_SCHEDULABLE | error | staff type listed as budget-only |
| ON_APPROVED_LEAVE | error | worker on approved leave (use a temporary reassignment for cover) |
| PERMANENT_EXCLUSIVE | error | PERMANENT job cannot share a day with another assignment |
| OUT_OF_SCOPE | error 403 | outside the user's scope |
| SEQUENCE_CONFLICT | error | duplicate sequence |
| PAST_DATE | error | before today for non-Admin |
| WEEKLY_OFF | warning | assigning on the worker's weekly off day |
| OVER_STANDARD_HOURS | warning | day total exceeds the worker's standard hours (planned OT) |
| UNDER_STANDARD_HOURS | info | day total below standard hours |
| GRADE_GROUP_MISMATCH | warning | worker's grade group differs from the job item's |
| PUBLIC_HOLIDAY | warning | assigning on a public holiday |
| NO_BOUNDARY | warning | site has no boundary |

## 8. Suggestions
Candidates: active, in the user's scope, employed on the date, not on leave, not budget-only. **Eligible = same grade group (G1..G7) as the item's planned grade** (a G2 worker can do gardener, irrigation or palm tree work); **exact staff type (SGD) match is listed first**. Then: worked at this site in the last 14 days, same supervisor as the team, fewer allocated hours that week (and most free hours against standard hours). If nobody qualifies the list is empty with a neutral message. Manual picks outside eligibility show `GRADE_GROUP_MISMATCH`.

## 9. Temporary reassignment and leave (summary; flows in D2)
- **Types**: REPLACE (A out, B in), MOVE (A moves to another site that day), ADD (extra worker), CANCEL (no work that day), over one date or a range.
- Requested **at least `reassignment_min_notice_days` (3) days ahead** by Supervisors, Superintendents, Engineers or Admin; **always approved by an Engineer** (an Engineer/Admin requester may approve their own). Status: PENDING -> APPROVED / REJECTED / CANCELLED / EXPIRED (not decided by the work date).
- Approval writes Scheduled Work with origin EXCEPTION, keeps the original, syncs to both workers' phones and alerts both and their supervisor.
- **Leave**: the worker asks the supervisor, the supervisor records it, an Engineer approves. Approval creates TO_BE_COVERED slots for affected standing assignments and an alert. Leave never changes pay; the system counts **leave taken** per worker, type and year (no balances). Only approved leave blocks assignment.
- Uncovered slots are just marked to be covered; no automatic relief logic.

## 10. Sync fan-out
Scheduled Work, assignment, job-item, boundary, time-rule and day-plan changes write `sync_changes` for the affected workers in the same transaction. A nightly job emits rows for days entering the 30-day window.

## 11. Worked example
Job `12A14301` item A "Gardener - Hand Watering": WEEK, 6, Mon-Sat, 3 staff, 9 h, PERMANENT. A standing assignment gives workers X, Y, Z the item for the contract year. Each Mon-Sat the system creates 3 rows of 9 h. On a public holiday the cell shows SKIPPED. If Y has leave on Wednesday, Y's slot shows TO_BE_COVERED; a supervisor requests a REPLACE (Y -> W) at least 3 days ahead; the Engineer approves; W's phone gets the day. W has an 8-hour standard day, so the planner shows W at 9/8 h (planned OT warning).

## 12. Base Planner & Operational Planner (Dual-Workspace Architecture)
See ADR-015 for design rationale:
- **Base Planner (`/base-planner`)**: 7-weekday recurring blueprint master schedule. Explicit weekday rows (`MON`..`SUN`, `W1_MON`..`W4_SUN`, `M1_W1_MON`..`M3_W4_SUN`). Quotas enforced (no excess allowed in blueprint). Candidate recommendations with rest-day warnings and remote capacity tracking. Mon–Sat fill convenience action skips worker's weekly rest day.
- **Operational Planner (`/operational-planner`)**: Live daily schedule. Renders base blueprint shifts as low-opacity muted chips (45%), leave gaps as `TO_BE_COVERED` (amber dashed), operational covers as solid indigo chips (`OVERRIDE`), compensatory shifts as solid emerald/purple chips (`DIRECT`), and base shift cancellations in bold red (`REMOVED`, `bg-rose-50 border-rose-300 text-rose-800 line-through`).
- **Base Worker Removal**: Stored in `scheduled_work` with `status = "CANCELLED"`, `source = "OVERRIDE"`, and mandatory `override_reason`. Restoring deletes the cancellation record via `DELETE /api/v1/operational-planner/shifts/{id}`. Active quota decrements if all workers on a date are cancelled.
- **Worker Roster Tab**: Sticky freeze header (`sticky top-0 z-10`), weekly total & daily hours heatmap shading, admin role exclusion (`role != 'ADMIN'`), worker search, site filter, and supervisor grouping toggle.
- **Period Quota Aggregation**: Monthly items aggregate across the full calendar month; quarterly items aggregate across the full 3-month calendar quarter.

