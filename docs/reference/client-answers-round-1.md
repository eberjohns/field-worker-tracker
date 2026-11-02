# Client answers - round 1 and what changed

| # | Question (short) | Answer | Effect |
|---|---|---|---|
| 1 | Engineers have no IDs | We assign IDs, normalise the list, link by ID | Template: IDs everywhere; `Employee_Reporting` links; legacy conversion done by us |
| 2 | Workers under two superintendents | Allow multiple superintendents | DEC-10: reporting links table (07, 02, 03) |
| 3 | Titles nobody holds | Ignore; only suggest if holders exist | DEC-22: neutral empty list, no alerts |
| 4 | "IP"/"TS" suffixes | Just labels | Dropped from the model |
| 5 | "D/L" | Drivers; add a driver column | `is_driver` on Employees (BR-EM-08) |
| 6 | Default weekly off day | Company setting; each worker can differ | DEC-21; settings are effective-dated |
| 7 | Combined job numbers | (no answer) | Re-asked in plain words; DEC-23 |
| 8 | Overhead job items | "Didn't get it" | Re-asked; DEC-09 |
| 9 | Which tab is current | "Which workbook?" | Re-asked: the Model_for_Scheduling file, tabs 2021-2026 |
| 10 | Large per-visit hours | Per worker per occurrence; days = hours / 9 | DEC-11 confirmed |
| 11 | Frequency mismatches | Frequency x periods is what counts (6x52, 1x12, 1x4, 3x1...) | BR-JB-06: calculated value used; declared figures informational |
| 12 | Permanent vs Remote; Tally numbers | Permanent = one job that day; Remote = several while hours remain. Staff are assigned in the system | DEC-36; default-staff sheet removed |
| 13 | Accommodation, documents, join dates | Accommodation sheet; ID on employee; expiry dates as optional employee columns | Template v0.3 |
| 14 | Saudi Arabia | Yes, add it | DEC-34, ADR-007: country on every record |
| 15 | Planned times | Settings with placeholder values | DEC-21 |
| 16 | Breaks, seasonal periods, history | Extended breaks for outdoor jobs; Ramadan changes hours and break; settings must be as they were at the time | DEC-03, DEC-35, ADR-008, work-period rules |
| 17 | Grace and minimum time | Changeable; must have minimum time at site | DEC-24; grace stays a setting |
| 18 | Location off | Flag only; show unaccounted hours; break time excluded | DEC-04 |
| 19 | Missing exit | Estimate and mark for review; named review types | DEC-05; review reasons table (05) |
| 20 | How to handle Ramadan/midday ban | "Reduce hours, increase break - is that the way?" | Yes: dated work-period rules (04 section 14, DEC-35) |
| 21 | Roles | Admin all; Engineer approves, creates sites and boundaries; Superintendent view-only + temporary reassignment; Supervisor reassignment | 02 permission matrix |
| 22 | Boundaries | Not imported; show "not set"; draw in the UI with place search; also for accommodations | Boundary setup queue (10, 08, 16) |
| 23 | Phones | Android and iPhone; app by others | Contract only |
| 24 | Live location | Last known from pings, with age; late uploads possible | DEC-31; two ages on the map card |
| 25 | OT trigger | Beyond the job's work time = 1.25x; non-assigned days (holidays, weekly off) = 1.5x | DEC-01 changed |
| 26 | Fixed OT | Fixed; show OT for all workers | OT eligibility/duty-hour columns removed |
| 27 | Salary revision lookup | A revision holds until changed; look up by grade | DEC-37: fall-through lookup suggested |
| 28 | OH | Sum of J to Q, per grade | DEC-39: per-grade provisions |
| 29 | Deductions | Not needed | DEC-30 changed: none in v1 |
| 30 | Pay period | Calendar month; changes apply next month | DEC-06, DEC-07 |
| 31 | Gratuity meanings / WPS | Just show reports | DEC-25 |
| 32 | Budget | Per contract, from the jobs / staff types / hours | DEC-29 changed: calculated from job items |
| 33 | Holidays | Admin interface | Already designed; optional import sheet |
| 34 | Checklists | Not needed | DEC-40 |
| 35 | Shift start/end | Automatic | DEC-40 |
| 36 | Worker login | PIN created at first entry; stop use on other devices | DEC-15; device binding in 09 |
| 37 | Documents | Type + validity date; Admin alerted before expiry (setting) | DEC-33; Documents screen |
| 38 | Retention, hosting, consent | Keep forever; yearly backup and clear; asks which hosting; consent notice created by client | DEC-38; hosting recommendation (14 section 11); consent policies |
