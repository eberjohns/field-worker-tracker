# D1 - Planner (yearly plan, weekly roster, hours panel)

Users: Admin, Engineer (build and edit); Superintendent, Supervisor (view, request changes). Rules: `04-scheduling-engine.md`. API: `08-api-spec.md` (roster, standing-assignments, allocation).

## Purpose
Plan the whole year across all contracts, then see and adjust the plan week by week the way the client works today (their weekly sheet: workers down, days across, sites with hours).

## Three lenses on the same data
1. **Roster** (default): worker x day. Best for checking each person's day.
2. **Coverage**: job x day. Best for seeing gaps and over-staffing per site.
3. **Year plan**: job item x team over a date range. Best for building standing assignments.

## Roster screen
```
Week 45 (2 Nov - 8 Nov)  Supervisor [All]  Engineer [All]  Staff type [All]  [Compact|Expanded]  [Export Excel]
Worker              | Mon 2        | Tue 3        | Wed 4        | ... | Sun 8        | Hours  | Remarks
Shanto Miah  G2B 8h | 12A14301 A 9 | 12A14301 A 9 | 12A14301 A 9 |     | WEEKLY-OFF   | 54/48  | Deira Bus
Rebiyu Aboli G1C 8h | 12A10604 2   | SKIPPED      | 12A10606 2.5 |     | WEEKLY-OFF   | 38/48  | Shakir (Hiace)
                    | 12A10605 2   | (Public hol.)| 12A10607 1.5 |     |              |        |
Cletus G. G3C 8h    | FREE         | TO BE COVERED| ON LEAVE     |     | WEEKLY-OFF   | 9/48   |
```
- A cell = list of **site chips** (job number, short name, hours) or one marker. Day total shown under the chips; red when over standard hours (planned OT), amber when under.
- Row footer: week total vs standard hours x working days.
- Markers (always explain why): SKIPPED (public holiday), WEEKLY-OFF, ON LEAVE, TO BE COVERED, FREE, NO BOUNDARY (chip warning).
- Compact mode joins chips "A + B"; expanded shows one line per site.
- Filters: supervisor, engineer, group/zone, staff type, grade group, "show only problems" (over/under hours, uncovered).
- Click a cell: **assign panel** (below). Drag a chip to another cell/worker (a Move button does the same). Right-click: request temporary reassignment / record leave / mark free.
- Export reproduces the client's layout (one row per worker, site and time per day, remarks).

## Workers side panel (always visible while assigning)
```
Workers for: 12A14301 A  Gardener - Hand Watering  (G1)      Wed 4 Nov  9 h
Search [______]   [x] same grade group   [ ] show leave/off
Name           Grade  Staff type        Today    Week      Month   Status
Ali K.         G1C    Gardener Helper   0/8 h    32/48 h   130/208  free
Bashir M. *    G1B    Hand Watering     9/8 h !  45/48 h   ...      over by 1h
Chand S.       G1C    Gardener Helper   --       --        --       ON LEAVE
```
- Shows **allocated hours today / this week / this month against standard hours**, colour bars, and why a worker is unavailable (leave, weekly off, already on a PERMANENT job).
- Ranking: same grade group eligible; exact staff type first (*), then recent at this site, same team, most free hours.
- Choosing a worker previews the day: "adds 9 h -> total 9/8 (1 h planned overtime)".

## Assign panel (a cell or a job slot)
Choose job item (or it is preset), worker, hours (pre-filled; for large monthly/quarterly hours the system proposes the split over days), single day / range / **standing** (repeat on weekdays until an end date). Warnings in a dialog: over standard hours, weekly off, public holiday, grade-group mismatch; PERMANENT conflicts and leave are blocking.

## Year plan screen
Left: contracts > jobs > items with required staff and planned hours. Centre: a timeline per item showing standing assignments as bars (worker, dates, weekday pattern). Right: the same workers side panel. Actions: add team, end an assignment from a date (permanent change), replace a worker from a date, copy a team to another item.
Status chips per item: staffed / understaffed / over, with the number of TO BE COVERED days in the next 30 days.

## Flows
- **Build the year**: pick item -> assign workers as standing assignments -> check coverage view -> resolve warnings.
- **Weekly check**: open roster for next week -> filter "problems" -> fix by assigning/covering or request a reassignment (D2).
- **Monthly/quarterly jobs**: item shows its windows; pick dates (suggestions given) and workers per occurrence; hours split over days of 9 h.
- **Publishing**: nothing to publish; saved changes reach phones through sync (30-day window); changes inside the notice period go through D2.

## Interactions and states
Loading skeleton; empty week message; keyboard navigation across cells (arrows, Enter opens, Esc closes); every action has a button alternative to drag; undo within the session; conflicts return the API warnings list; optimistic locking shows "changed by someone else, reload".

## Acceptance (used by phase checklist)
Roster matches the client's sheet layout for a sample week; hours panel reconciles with the roster totals; markers appear for holiday, off, leave and uncovered; PERMANENT exclusivity enforced; export opens in Excel with the same rows.
