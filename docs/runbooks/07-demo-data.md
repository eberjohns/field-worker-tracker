# Runbook 07: Demo data (reset → import → generate → passwords → simulator)

Fills a **local** database with the mock demo crews and about eight weeks of activity: phone events, site visits, attendance, pending visits, approvals and an October payroll draft. Everything goes through the real services, so the screens show what the pipeline really produces.

Everyone in the demo is a mock person (`tools/demo_data/`). Never point any of this at a database with real people in it.

| Step | What | Tool |
|---|---|---|
| 1 | Start the local database | `docker compose up -d db` (repo root) |
| 2 | Reset to the bootstrap state | `tools/reset_database.py` or Settings > Reset database |
| 3 | Import the demo workbook | Imports page, `tools/demo_data/FieldWorkerTracker_Demo_Import.xlsx` |
| 4 | Generate the activity | `tools/seed_demo_activity.py` |
| 5 | Set passwords for the people you'll sign in as | sign in and change, or Admin reset |
| 6 | Play today live | `tools/mobile-proxy` with a route from `tools/demo_data/routes/` |

## 1. Database

Use the local docker database only: `docker compose up -d db` from the repo root (container `field-worker-tracker-db-1`). The tools use `DATABASE_URL` from `backend/.env`, like the app, and print the database they work on.

To keep your own data, point `DATABASE_URL` and `DATABASE_MIGRATOR_URL` at a separate local database (for example `fw_demo`) and run `uv run --directory backend alembic upgrade head` once.

**Both tools refuse** `APP_ENV=production`. The generator also refuses a database that is not on this machine.

## 2. Reset

```bash
uv run --directory backend python ../tools/reset_database.py
```

This does the same as Settings > Reset database (Admin). It clears every master and transactional table, then creates the standalone Admin `ADMIN001` (password `ChangeMe123!`), the default company settings and the managed lists.

## 3. Import the demo workbook

1. Sign in as `ADMIN001`.
2. On the Imports page, upload `tools/demo_data/FieldWorkerTracker_Demo_Import.xlsx`.
3. Check the preview (0 errors), then commit.

**What the import creates:**
- 4 crews (32 people), 23 sites, 57 job items, worksite supervisors, time rules, AE/SA public holidays, salaries and the company settings, including the default password;
- a user account for each supervisor, superintendent and engineer, with username = Tally ID.

**Workers get their user on their first phone login.** Since v1.22.0 the master import also reads the **Leave** sheet (approved unless its `status` says PENDING), so step 1 of the generator finds the leave already there and skips it.

## 4. Generate the activity

```bash
uv run --directory backend python ../tools/seed_demo_activity.py
```

| Option | Default | Meaning |
|---|---|---|
| `--from` | `2026-10-01` | first day played |
| `--to` | yesterday (site time) | last day played; today is refused, it's for the simulator |
| `--seed` | `42` | the same seed gives the same events, ids and jitter |
| `--dry-run` | | prints the plan, the scenario dates and the counts; writes nothing |
| `--reset-generated` | | removes what an earlier run created, then generates again |
| `--plan-ahead-days` | `30` | Operational Planner shifts after `--to` (the phones' forward roster) |
| `--no-payroll` | | skips the October payroll draft |

The full range (1 Oct to 23 Nov: about 1,100 worker-days and 71,000 events) takes about 4 minutes on a laptop. Each day is played and closed in order, and progress is printed per day.

**What it does, in order. It never writes attendance, site visit, pending visit or payroll rows itself:**

1. **Leave.** The demo's 3 leave rows go through the Admin leave import (`POST /leave-requests/import`), unless they're already there (the master import creates them since v1.22.0).
2. **Plan:**
   - Base Planner templates from `tools/demo_data/demo_assignments.json` (`save_base_template`, one entry per worker and weekday, in the file's visit order).
   - One Operational Planner shift per worker, day and item (`create_operational_shift`), from `--from` to `--to` + 30 days. Public holidays and weekly offs are skipped. Each shift first passes the scheduler's own validation, and any error stops the run.
   - The shifts carry the note "Demo plan (generated)". Running again adds only what's missing.
3. **Phones.** Each worker, the driver included, logs in once through the mobile login service on a device called `DEMO-<tally>`, then accepts the current consent version. Supervisors, superintendents and engineers get no device.
   - The login uses the default password. If a worker already changed it, set `FW_DEMO_WORKER_PASSWORD`.
   - A worker bound to another device (for example the simulator) stops the run. Reset that binding first (step 6).
4. **Events.** For each planned working day:
   - **Shape of the day:** camp pings; leave camp about 06:20; transit pings; ENTRY, pings every 8–12 minutes and EXIT at each site in plan order (the 30-minute break is taken on site); back at camp about 16:00.
   - **Points:** accuracy 5–25 m; points sit inside the boundaries, away from the edge.
   - **Upload:** through the same service as `POST /mobile/events/batch`, with the app clock set to that evening, so the 5-minute and 7-day checks apply as they would live.
   - **Normal days** stay inside the 10-minute grace.
5. **Day close.** As the next morning's jobs would: attendance for every planned worker (including those with no events), then pending-visit detection and reminders.
6. **Reviews.** Engineer 2901 approves every day waiting for review that is more than 7 days old. The DEC-10 check of the decision screen applies. The last 7 days stay open for the demo.
7. **Payroll.** The October 2026 draft (AE, leave unpaid), **not approved**. Approving it locks October.

**Planted scenarios** (D = the last day played; a date on a weekly off or holiday moves to the nearest earlier working day, and the summary says so):

| # | Worker | When | What you should see |
|---|---|---|---|
| P1 | 2001 | latest Mon/Wed/Fri ≤ D | 45 min late at the first site: waiting for review, shortfall beyond grace, in the late arrivals report |
| P2 | 2007 | D | 7 min late, inside the grace (no review) |
| P3 | 2012 | D-2 | leaves 70 min early: shortfall beyond grace |
| P4 | 2013 | D-3 and D-10 | stays 75 min after the planned end: OT1 |
| P5 | 2010 | latest Tuesday ≤ D (his weekly off) | works at Le Pont through an approved temporary reassignment (supervisor 2702 asks 4 days ahead, engineer 2901 approves): OT2 |
| P6 | 2019 | D-1 and D-9 | skips 22A14107: an open pending visit; the older one is escalated |
| P7 | 2011 | D-4 | no events and no leave: absent |
| P8 | 2008 | D-2 | location off 11:00–12:30 (LOCATION_DISABLED / ENABLED): tracking gap |
| P9 | 2020 | D-3 | that day's events reach the server on D-1 evening: a second calculation version, and the pending visits opened at day close are closed as `VISIT_CONFIRMED_LATE` |
| P10 | 2023, 2017, 2003 | their leave days | no events; 2017's leave is unpaid |
| P11 | 2024 (driver) | every working day | camp about 05:45 to about 17:30, measured camp to camp (no overtime: the driver's salary row sets a 12-hour standard day) |
| P12 | 2008 | weekdays | at 22A15201, another supervisor's site (DEC-57 cross-crew view) |

**The summary at the end** lists:
- rows created per table;
- events accepted, and refused by reason (0 refused is expected);
- each scenario with its date, worker, attendance record id and outcome.

**To start again:** run with `--reset-generated`. For a clean slate, repeat steps 2–4.

**What `--reset-generated` removes**, for the demo workers only:
- their attendance, pending visits, visits and gaps from `--from` on;
- the `DEMO-` devices with their events and consent;
- the generated shifts, the P5 reassignment and the generated templates.

Imported data, user accounts and anything made by hand stay. The payroll draft is replaced by the next run.

## 5. Passwords

| Who | Username | First sign-in |
|---|---|---|
| Admin | `ADMIN001` | `ChangeMe123!` from the reset; change it |
| Engineers 2901, 2902; superintendents 2801, 2802; supervisors 2701–2704 | Tally ID | the default password (Settings > Company settings, `default_password`); they must change it on first sign-in |
| Workers | Tally ID (phone only) | created by the generator's phone login with the default password, flagged to change it |

The default password expires after `default_password_max_days` (7). After that, or to put one person back, an Admin uses **Reset password** on the employee (`POST /employees/{id}/reset-password`).

## 6. Play today in the simulator

The generator never plays today, so you can play today live from the phone simulator (`tools/mobile-proxy`; see its README to start it).

1. **Free the worker's phone.** Each worker is bound to `DEMO-<tally>`, and the simulator is another device, so its login gives `DEVICE_MISMATCH`. As Admin, open **Devices**, find the worker's `DEMO-` device and **Reset** it.
2. **Sign in** in the simulator with the worker's Tally ID and password.
3. **Load a route** from `tools/demo_data/routes/`:
   - `route_2001_*_MWF_ministries.json`, `route_2001_*_MWF_late.json`, `route_2001_*_TTS_mirdif.json` for worker 2001 (Mon/Wed/Fri, late arrival, Tue/Thu/Sat);
   - `route_2010_*_lepont.json` for 2010 at Le Pont;
   - `route_2024_*_driver.json` for the driver.
4. **Pick today** as the work date and play.

A worker you've moved to the simulator stops the generator, so reset that binding again before the next generator run.
