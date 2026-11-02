# D5 - Drivers section and daily transport runs

Users: Admin, Engineer (all in scope), Supervisor (create and edit in scope), Superintendent (read), Drivers and workers (see their own run in the app). Data: `07-data-model.md` (Transport). Mobile entity: TRANSPORT_RUN.

## Purpose
Record who is driven by whom, in which order, to which job sites each day, so that workers know their driver and the driver knows the stops and passengers. No routing or maps navigation; just the ordered list.

## Concepts
- **Driver**: an employee with `is_driver = Y`. Drivers use accommodation-to-accommodation time.
- **Vehicle**: a label (Hiace, Ertiga, Deira Bus). Optional on a run.
- **Run**: driver + date + direction (MORNING from accommodation to sites, EVENING back) + ordered **stops** + **passengers** per stop. A worker is on at most one run per direction per day. Different days can use different drivers ("3 days with one driver, 3 with another").

## Screens
```
Drivers and Transport   Date [Mon 2 Nov]  Direction [Morning]  [Suggest from schedule] [Copy last week] [+ New run]
Driver / Vehicle         Stops (in order)                                              Passengers  Status
Shakir K. - Hiace        1 Al Nahda 1 (12A10604)  2 Mirdif (12A10611)  3 Ajman (...)    9           DRAFT  [Publish]
Afra S.  - Sunny         1 Deira ...                                                   4           PUBLISHED
Unassigned workers (6): Ali K, Bashir M ...   [drag onto a run]
```
- **Drivers list**: driver, default vehicle, runs this week.
- **Run editor**: reorder stops by drag or up/down; add a stop from today's sites; assign passengers per stop from the **unassigned workers** list (workers scheduled that day, grouped by site); remove/move passengers; capacity note optional.
- **Suggest**: groups the day's scheduled workers by their first site and accommodation and proposes runs; the user edits.
- **Copy**: copy a day or week of runs forward.
- **Publish**: syncs the run to the driver (full list with passengers) and to each passenger (driver, vehicle, own stop). Changing a published run re-syncs and notifies affected workers.
- Roster remarks column shows each worker's driver/vehicle for the day.

## Rules
Runs are validated against the schedule: passengers must be scheduled that day; a stop must be a site on someone's schedule (or the accommodation); a driver cannot have two runs overlapping in the same direction. Warnings for workers scheduled but not on any run. If a reassignment changes a worker's site, the affected run is flagged "needs update".
Driver attendance is measured accommodation-to-accommodation (05). The transportation-time report uses the same stops.

## Acceptance
A day of runs can be suggested, edited and published; driver and passenger phones receive their parts; a worker sees driver and vehicle; run sheet report prints stops with passengers; unassigned-worker warning works.
