# D3 - Time rules (planned times, break, seasons) and the daily attendance table

Users: Admin (all), Engineer (their scope), others read. Rules: BR-AT-06/13, `05-attendance-engine.md`.

## The five-point planned schedule
| Point | Meaning | Example |
|---|---|---|
| Accommodation start | leaves the accommodation | 05:00 |
| First-site start | planned start at the first site | 06:00 |
| Break | minutes | 00:30 |
| Last-site end | planned end at the last site | 15:30 |
| Accommodation end | back at the accommodation | 17:00 |
Planned **total time** = accommodation end - accommodation start (12:00). Planned **worked time** = last-site end - first-site start - break (09:00). Standard hours (8/10/12) come from the salary structure and can be changed by a rule (Ramadan -120 min).

## Levels and precedence
COMPANY (default) -> **DRIVERS** -> **TEAM** (everyone linked to a chosen supervisor, superintendent or engineer, e.g. Mr. Dawood's labourers) -> **EMPLOYEE** (one person, e.g. an indoor technician). The most specific rule in force on the date wins; blank fields inherit from the next rule. A rule may apply to ALL jobs, OUTDOOR_ONLY or INDOOR_ONLY (seasonal summer break for outdoor jobs). A job item can also carry its own longer break. Rules have a date range (a **season**) and are never edited in place once attendance exists: add a new rule from a date.
Starting presets (editable): Winter first site 06:00-06:30, last site 16:00-16:30, break 1 h; Summer first site 05:00-05:30, last site 16:30-17:00, break 2.5 h (outdoor); Ramadan 05:30-12:30, break 0, standard hours -2 h; drivers and indoor teams are exceptions.

## Screen: Time rules
```
Time rules   Scope [Company|Team|Drivers|Employee]  Season [All]  Country [AE]   [+ New rule]
Name            Scope            Applies  From        To          Acc.start First site Break Last site Acc.end Std hrs
Company std     Company          All      01 Jan 26   -           05:00     06:00      0:30  15:30     17:00    -
Summer          Company          Outdoor  15 Jun 27   15 Sep 27   04:30     05:00      2:30  16:30     17:30    -
Ramadan         Company          All      08 Feb 27   09 Mar 27   05:00     05:30      0:00  12:30     13:30    -2 h
Dawood team     Team: Dawood     All      01 Jan 26   -           05:30     06:30      1:00  16:00     17:30    -
```
- **New rule**: choose scope (pick the team/person), applies-to, dates, the five times, standard-hours change; preview "affects N workers"; save.
- **Check tool**: pick a person and a date -> shows the effective plan and **which rule won** (explainability).
- Engineers see and edit only rules for their teams/people; Admin edits company/driver rules.

## Daily attendance table (report 1)
```
              |                    PLANNED                          |                    ACTUAL                           | Var.total | Var.worked | Comments        | Approval
Worker  Date  | Acc.st First Break Last  Acc.end Total  Worked | Acc.st First Break Last  Acc.end Total  Worked |           |            |                 |
Ali K.  3 Nov | 5:00   6:00  0:30  15:30  17:00   12:00  09:00 | 5:20   6:20  0:30  15:20  16:50   11:30  08:30 | -00:30    | -00:30     | Supervisor      | Engineer
```
- Variation = actual - planned (signed). The **break shown is the break applied by the rule** (actual break timing is not measured).
- Comments: Supervisor, mainly where planned and actual differ. Approval: Engineer, **only rows with variation, a flag or overtime**; clean rows show AUTO. Bulk approve; filter "needs review".
- Workers without accommodation show n/a in the accommodation columns and total time = first to last site. Drivers use accommodation times only.
- Row click opens the timeline and map with the review reason chips (Estimated exit, Tracking off, Short hours...).

## Alarm
Phone alarm = planned accommodation start (that day's DAY_PLAN) minus `alarm_lead_minutes`; seasons and team rules therefore move the alarm automatically.

## Acceptance
The client's example reproduces exactly (12:00 / 09:00 planned; 11:30 / 08:30 actual; -00:30 and -00:30); a team rule and an employee rule override the company rule for their dates only; resolver explains the winner; past dates keep their old rule.
