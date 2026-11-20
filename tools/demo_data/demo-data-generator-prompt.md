# Demo data generator prompt (for Claude Code)

All people in the demo import are MOCK (invented names, Tally numbers and salaries); this file can be committed.

Give everything below the line to Claude Code. Put these files in the repo first, under `tools/demo_data/`:
`FieldWorkerTracker_Demo_Import.xlsx`, `demo_assignments.json`, `routes/` (the 5 route JSON files).

---

Build a demo activity generator: `tools/seed_demo_activity.py`. Follow AGENTS.md and .agents/rules/*.
Plan first and wait for my approval. Branch `feat/demo-activity-generator`; open a PR; do not merge.

## Goal
After a clean reset (`tools/reset_database.py`) and a committed import of
`tools/demo_data/FieldWorkerTracker_Demo_Import.xlsx`, the generator fills the system with realistic activity
from 2026-10-01 to yesterday (site-local date, Asia/Dubai), so that the live map, attendance, pending visits,
payroll and all 15 reports have content. It must use the REAL pipeline: phone events in → enrichment →
site visits / gaps → attendance engine → pending visits → payroll draft. It must not write attendance,
site visit, pending visit or payroll rows directly. (tools/seed_2month_reports_demo.py does that and still
treats every Sunday as a rest day; leave it alone, but don't reuse its approach.)

## Inputs
- `tools/demo_data/demo_assignments.json`: 43 standing assignments (tally_id, job_number, sub_item_code,
  weekdays, deployment_type), derived from the client's Week 39 roster. They were checked: every worker has
  7-8 h planned on every working day, never works on their own weekly off, and a PERMANENT item never
  shares a day with another job.
- Import data: 23 worksites with boundary polygons, 2 accommodations with polygons, 32 employees,
  3 leave records, Worksite_Supervisors (23 rows), public holidays, time rules (Standard Company Day 07:00-15:30, 30 min break).

## CLI
`uv run --directory backend python ../tools/seed_demo_activity.py [--from 2026-10-01] [--to YYYY-MM-DD]
[--seed 42] [--dry-run] [--reset-generated]`
- Default `--to` = yesterday in site time (fw.core.clock.site_today() - 1 day). Never generate today:
  today is played live from the mobile simulator.
- Refuse to run when APP_ENV is production.
- Exit with a clear message if the demo employees or worksites are missing (import not done).
- `--reset-generated` removes only what the generator created (tag devices, e.g. device id prefix `DEMO-`,
  and delete in dependency order), so it can be re-run the day before the demo.
- Deterministic with `--seed`.

## Steps
1. **Plan.** Create the standing assignments from demo_assignments.json through the same service the Base
   Planner uses, with all validations on. Then generate operational scheduled work from `--from` to
   `--to` + 30 days through the same service the Operational Planner uses (public holidays skipped as the
   planner does). Any validation refusal = stop and report it; don't bypass.
2. **Devices and consent.** For each WORKER (including the mock driver 2024, who is measured camp to camp): register one device and accept the current consent version
   through the mobile services. Do not create devices or events for supervisors, superintendents or
   engineers (supervisors are not tracked).
3. **Events.** For each worker and each planned day (not weekly off, not on leave, not a holiday), build the
   day: leave camp about 06:20, transit pings, ENTRY/EXIT for each planned site in order, a ping every
   8-12 minutes inside a site, the break taken on site, back at camp about 16:00. Jitter ±10 min, GPS
   accuracy 5-25 m, points inside the polygons from the import. Submit through the same service as
   `POST /api/v1/mobile/events/batch`. Ingestion refuses events older than 7 days by design: set the clock
   with `fw.core.clock.set_system_clock(FrozenClock(...))` to that day's evening (site time) while
   submitting, so each day is ingested as if live. Never relax validation.
4. **Day close.** For each day, run the attendance calculation through AttendanceService (the same entry
   point the day close uses), then `PendingVisitsService.detect_pending_visits(target_date=day)` as the
   worker does.
5. **Reviews.** As engineer 2901, approve every PENDING_REVIEW day older than 7 days through the attendance
   approval service, so October has no open reviews. Leave the last 7 days unreviewed for the demo.
6. **Payroll.** Create the October 2026 draft run through PayrollService (treat_leaves_as_paid = false).
   Do NOT approve it.

## Planted scenarios (D = the last generated day)
| # | Worker | When | What | What it shows |
|---|---|---|---|---|
| P1 | 2001 Ravi Varghese | latest Mon/Wed/Fri ≤ D | arrives at the first site 45 min late (same pattern as routes/route_2001_ravi_MWF_late.json) | late arrival, review |
| P2 | 2007 Junaid Akhtar | D | 7 min late | inside the 10 min grace, not flagged |
| P3 | 2012 Prakash Rao | D-2 | leaves 70 min early | early departure, shortfall |
| P4 | 2013 Waqas Anjum | D-3 and D-10 | stays 75 min after the planned end | OT1 |
| P5 | 2010 Abdi Hassan | latest Tuesday ≤ D (his weekly off) | works at Le Pont. Plan it first with an approved temporary reassignment created through the service | OT2 on own weekly off |
| P6 | 2019 Harpreet Gill | D-1 and D-9 | skips 22A14107 | open pending visit, and one past 7 days (escalation) |
| P7 | 2011 Suresh Nair | D-4 | no events at all, no leave | absent, missed-hours deduction |
| P8 | 2008 Faisal Mahmood | D-2 | location disabled 11:00-12:30 (send the location OFF/ON events) | tracking gap, alert |
| P9 | 2020 Mohamed Abdullahi | D-3 | that day's events uploaded at D-1 evening | late upload, new calculation version |
| P11 | 2024 Imtiaz Hussain (driver) | every working day | leaves camp ~05:45, foreman visits at Le Soleil and ENOC HO, back ~17:30 | driver measured camp to camp |
| P12 | 2008 Faisal Mahmood | weekdays | works at 22A15201 (Bilal's site) while in Kamran's crew | cross-crew read-only view (DEC-57) |
| P10 | 2023, 2017, 2003 | their imported leave days | no events | leave exempts pending visits; 2017 unpaid leave deduction |

All other days are normal, with jitter. If a scenario date falls on the worker's weekly off or a holiday,
move it to the nearest earlier working day and say so in the summary.

## Output
Print a summary: rows created per table, events accepted and refused (refusals must be 0 apart from
anything deliberate), and each planted scenario with its date, employee and attendance record id, so the
demo team can find them.

## Tests and docs
- A test that runs the generator for 3 days on the test database and checks that attendance records
  exist, that P1 is PENDING_REVIEW with a late flag, and that P7 is ABSENT.
- `docs/runbooks/demo-data.md`: reset → import → generate → set passwords → mobile simulator routes.
- CHANGELOG entry and version bump. Done when backend tests, ruff, pyright, lint-imports pass.
