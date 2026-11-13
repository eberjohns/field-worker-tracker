# 09 - Mobile Sync and Event Contract

**Audience: the mobile app team.** This document is the contract. The machine-readable version is `openapi-mobile.json`, exported from the backend (routes tagged `mobile`). Additive changes (new optional fields, new entity types) can appear at any time - **clients must ignore unknown fields and unknown entity types**. Breaking changes ship under a new version path with at least 60 days' notice.

Contract version: **1** (header `X-Contract-Version: 1`). Base path: `/api/v1/mobile`.

## 1. What the app does
The app is a **data collector and viewer**. It stores the worker's profile, the next ~30 days of schedule with job details and boundaries, and its own pending events. It records location events and uploads them. It never calculates attendance or pay; the server verifies locations against its own polygons.

## 2. General rules
- JSON over HTTPS (TLS only). Times are ISO-8601 UTC (`2026-11-02T05:31:07Z`). Coordinates are WGS84 decimal degrees; **GeoJSON order is `[longitude, latitude]`**.
- Auth: `Authorization: Bearer <access_token>`. Access token lifetime 15 minutes; refresh token 30 days, rotating, bound to the registered device.
- Every response includes `server_time_utc`. Use it to detect device clock drift.
- Errors use RFC 7807 (`application/problem+json`) with a stable `code`.
- Rate limits: login 5 failures then 15-minute lockout; otherwise generous. On `429` obey `Retry-After`.
- One active device per worker. The server stores the device identifier, platform, model, OS and app version. Login from any other device is refused (`DEVICE_MISMATCH`) and logged; an Admin resets the binding when a worker changes phone. A second device cannot register until the first is revoked.

## 3. Login
All users (workers included) log in with **username = worker ID** and a **password**. Everyone starts with the company **default password** and must change it at first login. Only Admin can reset a user to the default (workers ask their supervisor).
### POST `/mobile/auth/login`
```json
{ "tally_id": "1193", "password": "...", "device": { "device_identifier": "b6c1...", "platform": "ANDROID", "device_model": "Samsung A14", "app_version": "1.0.3", "os_version": "14", "push_token": "fcm-token-or-null" } }
```
200:
```json
{ "access_token": "...", "refresh_token": "...", "expires_in": 900, "server_time_utc": "...",
  "must_change_password": true, "employee": { "employee_id": "uuid", "tally_id": "1193", "name": "Shanto Miah", "role": "WORKER" } }
```
- While `must_change_password` is true the only allowed call is `POST /mobile/auth/change-password` `{ "old_password", "new_password" }`. Other calls return `403 PASSWORD_CHANGE_REQUIRED`.
- The **first successful login binds the account to that device**. Login from another device returns `403 DEVICE_MISMATCH` and is logged; Admin resets the binding.
- Errors: `INVALID_CREDENTIALS` (401), `DEVICE_MISMATCH` (403), `ACCOUNT_LOCKED` (403: default password not changed in time, or too many failures; ask Admin), `ACCOUNT_DISABLED` (403).
### POST `/mobile/auth/refresh` `{ "refresh_token" }`; POST `/mobile/auth/logout` (204). Reuse of an old refresh token revokes the session.
### POST `/mobile/consent`
`{ "policy_version": 1, "consented_at_utc": "..." }` after the worker accepts the location notice.

### GET `/mobile/policy/location?language=en`
Returns `{ "version": 3, "language": "en", "title": "...", "body": "...", "published_at": "..." }` - the location consent notice written by the company (purpose and legal basis). The app shows it on first use and the worker **must accept before tracking can start**. When `SETTINGS.location_policy_version` is higher than the version the worker accepted, the app shows the new notice and calls `POST /mobile/consent` again before tracking resumes.

### PUT `/mobile/device`
`{ "push_token", "app_version", "os_version", "location_permission_state": "ALWAYS|WHILE_IN_USE|DENIED|RESTRICTED" }`. Call when any value changes.

## 4. Heartbeat (how the server knows the app is alive)
### POST `/mobile/heartbeat`
```json
{ "app_version": "1.0.3", "cursor": 4812, "location_permission_state": "ALWAYS" }
```
200:
```json
{ "server_time_utc": "...", "latest_cursor": 4815, "min_app_version": "1.0.0", "has_pending_changes": true }
```
Call: on app open, when connectivity returns, every 15 minutes while in the foreground, and **just before the morning alarm** (so today's data is fresh). If `has_pending_changes` is true, pull changes (section 5). Any authenticated call also updates the server's `last_seen_at`. The server never assumes the phone is online; it only records when it last heard from it.

## 5. Sync
The server keeps a per-worker **change log**. Each change has a global, increasing `cursor`. The app stores the last cursor it **successfully applied**.

### GET `/mobile/sync/snapshot`  (handshake and resync)
Returns everything needed offline plus the cursor to continue from.
```json
{
  "cursor": 4812, "generated_at": "...", "server_time_utc": "...",
  "window": { "from": "2026-11-02", "to": "2026-12-02" },
  "entities": [
    { "entity_type": "PROFILE",       "entity_id": "uuid", "entity_version": 3, "payload": { } },
    { "entity_type": "SETTINGS",      "entity_id": "self", "entity_version": 9, "payload": { } },
    { "entity_type": "ACCOMMODATION", "entity_id": "uuid", "entity_version": 1, "payload": { } },
    { "entity_type": "JOB",           "entity_id": "uuid", "entity_version": 5, "payload": { } },
    { "entity_type": "SCHEDULE_ITEM", "entity_id": "uuid", "entity_version": 2, "payload": { } },
    { "entity_type": "TRANSPORT_RUN", "entity_id": "uuid", "entity_version": 1, "payload": { } }
  ]
}
```
The server reads the cursor **before** building the snapshot, so nothing is missed; applying a change already included is harmless (idempotent).

### GET `/mobile/sync/changes?cursor=4812&limit=200`
```json
{
  "from_cursor": 4812, "next_cursor": 4815, "has_more": false, "resync_required": false,
  "server_time_utc": "...",
  "changes": [
    { "cursor": 4813, "entity_type": "SCHEDULE_ITEM", "entity_id": "uuid", "entity_version": 3, "op": "UPSERT", "priority": 1, "payload": { } },
    { "cursor": 4815, "entity_type": "SCHEDULE_ITEM", "entity_id": "uuid2", "entity_version": 4, "op": "DELETE", "priority": 1, "payload": null }
  ]
}
```
- `payload` is the **full current snapshot** of that entity (not a diff).
- `op = DELETE` is a tombstone: remove the entity locally.
- The server may coalesce, returning only the latest change per entity in a page. Do not rely on seeing intermediate versions.
- `priority = 1` means the change affects today or tomorrow: apply first, and if tracking is active re-register geofences immediately.
- If `resync_required` is true (cursor older than the server's retention), call the snapshot endpoint and replace local data.
- Loop while `has_more` is true.

### Applying changes (client rules)
1. Apply all changes of a page **in one local transaction**: upsert by `(entity_type, entity_id)` only if `entity_version >=` the stored version; delete on `DELETE`.
2. Store `next_cursor` only after the transaction commits. If it fails, do not advance.
3. Then `POST /mobile/sync/ack` `{ "cursor": 4815 }` (idempotent; the server records `last_acked_cursor` for dashboard status).
4. Purge local schedule items older than 7 days. Keep the 30-day forward window.

### Push nudge (optional trigger)
A silent data push `{ "type": "SYNC", "latest_cursor": 4815, "priority": 1 }`. It carries **no schedule data**. On receipt, pull changes. Pushes can be delayed or lost; the heartbeat and app-open pulls are the safety net. Expected operating rule: the app reaches the internet at least once a day.

### Entity payloads
**PROFILE**
```json
{ "employee_id": "uuid", "tally_id": "1193", "name": "Shanto Miah", "role": "WORKER",
  "staff_grade_description": "Gardener Expert", "weekly_off_day": "FRIDAY", "is_driver": false,
  "supervisor": { "name": "Shakir Khisham", "phone": "+971..." }, "accommodation_id": "uuid-or-null" }
```
**SETTINGS** (static tracking settings for this worker, effective-dated; the `upcoming` array lists changes inside the sync window)
```json
{ "geofence_circle_radius_m": 300, "approach_polling_interval_s": 60, "confirmation_polling_interval_s": 300,
  "schedule_sync_window_days": 30, "location_policy_version": 1, "alarm_lead_minutes": 30,
  "timezone": "Asia/Dubai", "upcoming": [] }
```
Planned times, break, standard hours and the alarm time are **not** here: they vary by season and rule, so they come per date in DAY_PLAN.
**DAY_PLAN** (one per date in the window; resolved for this worker from the time rules, holidays, weekly off and leave)
```json
{ "work_date": "2026-11-03", "status": "WORKING", "marker": null,
  "planned": { "accommodation_start": "05:00", "first_site_start": "06:00", "break_minutes": 30, "last_site_end": "15:30", "accommodation_end": "17:00" },
  "standard_hours": 8, "alarm_time": "04:30" }
```
`status`: `WORKING`, `OFF` (marker `WEEKLY_OFF`), `SKIPPED` (marker `PUBLIC_HOLIDAY`), `LEAVE`, `FREE`. `alarm_time` = planned accommodation start minus `alarm_lead_minutes`; the app rings the alarm at that time on working days. The planned times and standard hours change by season, so always read them from DAY_PLAN, not SETTINGS.
**TRANSPORT_RUN** (sent to the driver and to each passenger)
```json
{ "run_id": "uuid", "run_date": "2026-11-03", "direction": "MORNING", "vehicle_label": "Hiace",
  "driver": { "name": "Shakir Khisham", "phone": "+971..." },
  "stops": [ { "sequence": 1, "stop_type": "SITE", "job_id": "uuid", "name": "...", "planned_time": null,
               "passengers": [ { "name": "Shanto Miah", "tally_id": "1193" } ] } ] }
```
Workers see their driver, vehicle and their stop; the driver sees all stops in order with the passengers for each (workers receive only their own name). Entity removed with a `DELETE` tombstone when a run is cancelled.
**ACCOMMODATION**
```json
{ "accommodation_id": "uuid", "name": "...", "address": "...", "boundary": { "type": "Polygon", "coordinates": [[[55.38,25.29],[55.381,25.29],[55.381,25.291],[55.38,25.29]]] },
  "geofence_circle": { "center": { "lat": 25.2905, "lng": 55.3805 }, "radius_m": 420 } }
```
**JOB** (a worksite)
```json
{ "job_id": "uuid", "job_number": "12A14301", "job_name": "BKA - Wasl - R1068 Staff Accomodation, Warsan - Outdoor AMC",
  "boundary": { "type": "Polygon", "coordinates": [[[...]]] },
  "geofence_circle": { "center": { "lat": 25.1, "lng": 55.2 }, "radius_m": 480 }, "boundary_missing": false }
```
`geofence_circle` is computed by the server: centre of the polygon, radius = distance to the farthest vertex + `geofence_circle_radius_m`. If `boundary_missing` is true the site cannot be geofenced; show it in the schedule but do not track.
**SCHEDULE_ITEM**
```json
{ "scheduled_work_id": "uuid", "work_date": "2026-11-03", "sequence": 1, "assigned_hours": 3.0, "status": "ACTIVE",
  "job_id": "uuid", "job_item_id": "uuid", "sub_item_code": "A", "occurrence_id": "uuid",
  "job_item_summary": { "staff_grade_description": "Gardener Expert", "deployment_type": "PERMANENT", "required_staff_count": 3, "hours_per_occurrence_per_staff": 9.0 },
  "source": "PLANNED", "is_reassignment": false }
```
Status values: `ACTIVE`, `CANCELLED`, `REASSIGNED`, `COMPLETED`. Show ACTIVE items; keep others only for history display. `source` may be `PLANNED`, `REASSIGNMENT`, `COVER` or `FOLLOW_UP`; treat unknown values as `PLANNED`.
**Reserved for later** (ignore until announced): `SCORECARD`, `PAYROLL_SUMMARY`.

## 6. Daily tracking behaviour (what we need from the app)
1. At the company alarm time the app rings. When the worker stops the alarm, tracking turns on (permissions per the policy accepted at first launch).
2. Create geofence circles for **today's** worksites and the worker's accommodation from the `geofence_circle` data.
3. On entering a circle: start **approach polling** every `approach_polling_interval_s`. Poll until a fix is **inside the polygon** (do the point-in-polygon check on the device).
4. Inside the polygon: log `ENTRY`. Then poll every `confirmation_polling_interval_s`; each fix is a `PING`.
5. When the circle reports the worker left (or a ping is outside the polygon), poll to confirm they are outside, then log `EXIT`.
6. If location services are switched off: log `LOCATION_DISABLED` with the **last polled location** and `location_captured_at_utc` of that fix. When switched on: log `LOCATION_ENABLED` with the **new location**. Keep trying to deliver these.
7. Never invent events. If permission is denied or no fix is available, do not create `ENTRY/EXIT/PING`.
The server re-verifies every location against its stored polygon and can disagree with the device. The device's decision is recorded, but the server's verdict drives attendance.

**App-side notifications (no server involvement):** the shift-start reminder is the morning alarm; arrival/departure confirmations are local notifications the app raises on its own ENTRY/EXIT. Server-generated alerts (tracking interrupted, pending visits, document expiry) go to web users and to Engineer/Supervisor/Superintendent accounts only.

## 7. Events
### POST `/mobile/events/batch`
```json
{
  "batch_id": "uuid", "device_clock_utc": "2026-11-03T06:40:05Z",
  "events": [
    { "event_id": "uuid", "event_type": "ENTRY", "event_timestamp_utc": "2026-11-03T06:20:12Z",
      "location_captured_at_utc": "2026-11-03T06:20:12Z", "latitude": 25.1003, "longitude": 55.2002,
      "accuracy_meters": 12.5, "is_mock_location": false, "sequence_number": 211,
      "job_id": "uuid", "job_item_id": null, "accommodation_id": null }
  ]
}
```
- `event_type`: `ENTRY | EXIT | PING | LOCATION_DISABLED | LOCATION_ENABLED`. There is no `source` field.
- `event_id`: UUID generated on the device **when the event is created** and stored before any upload attempt. This makes retries safe.
- `event_timestamp_utc`: when the event happened on the device. `location_captured_at_utc`: when the location fix was read (for `LOCATION_DISABLED` this is earlier than the event time).
- `sequence_number`: increasing per app install (optional but recommended).
- `job_id` / `accommodation_id`: hints when known. The employee identity comes from the token, never the body.
- `latitude`/`longitude` may be null only for `LOCATION_DISABLED` when no fix has been taken yet.
- `device_clock_utc`: the device's current clock when the batch is sent. Large drift is flagged on the server; times are never rewritten.
- Max 200 events per batch; send in timestamp order; send oldest first.
- Upload `LOCATION_DISABLED` and `LOCATION_ENABLED` **immediately** (as a single-event batch) whenever the network is available, without waiting for the usual batch interval: supervisors and engineers are alerted from these events.

200:
```json
{ "batch_id": "uuid", "server_time_utc": "...", "latest_cursor": 4815,
  "results": [ { "event_id": "uuid", "status": "ACCEPTED" } , { "event_id": "uuid2", "status": "DUPLICATE" }, { "event_id": "uuid3", "status": "REJECTED", "reason": "TIMESTAMP_TOO_OLD" } ] }
```
Per-event `status`: `ACCEPTED`, `DUPLICATE` (already stored: treat as success), `REJECTED`. Reject reasons: `INVALID_SCHEMA`, `INVALID_COORDINATES`, `TIMESTAMP_IN_FUTURE`, `TIMESTAMP_TOO_OLD` (older than 7 days).
Client rules: delete an event from the local queue on `ACCEPTED` or `DUPLICATE`; on `REJECTED` log locally and delete (do not retry); on network/5xx failure retry the **same** batch with exponential backoff (5 s up to 1 h, with jitter). Whole-batch errors: `DEVICE_NOT_ACTIVE` (403, device was revoked: stop and show re-registration), `401` (refresh the token, then retry).
`latest_cursor` is piggybacked so the app can pull changes immediately if it is ahead.

## 8. On-demand data (not synced)
- `GET /mobile/me/scorecard?week_start=2026-11-02` -> assigned hours, completed work count, worked minutes, status per day (supplied by the backend).
- `GET /mobile/me/payroll?period=2026-10` -> the worker's own finalized payroll: salary components, OT hours and amounts, employee-side totals only (no provisions, overhead or cost). 404 until the period is finalized.
These shapes will be added to the OpenAPI file when the web side reaches payroll; the app should hide the screens until the endpoints are available.

## 9. Error codes
`INVALID_CREDENTIALS`, `INVALID_ACTIVATION`, `ACTIVATION_EXPIRED`, `DEVICE_ALREADY_REGISTERED`, `DEVICE_MISMATCH`, `DEVICE_NOT_ACTIVE`, `ACCOUNT_DISABLED`, `RESYNC_REQUIRED` (informational), `VALIDATION_ERROR`, `RATE_LIMITED`, `APP_VERSION_UNSUPPORTED` (426).

## 10. Security expectations for the app
Store tokens in the OS secure store. Do not log tokens or coordinates in plain logs. Request only the permissions the agreed features need and show the consent notice before enabling tracking. Do not send location when tracking is off.

## 11. What the app team sends us / receives
- We provide: this document, `openapi-mobile.json`, a sandbox base URL, test accounts (default password), sample sites with polygons, and a GPS event simulator.
- We need from you: the minimum OS versions supported, push provider choice (FCM/APNs), and the app's expected polling battery profile so we can tune the default intervals.

## 12. Contract changelog
| Date | Version | Change |
|---|---|---|
| - | 1 | Initial contract |
| draft | 1 | Login by employee ID + password with forced first change and device binding (activation code removed); new entities `DAY_PLAN` and `TRANSPORT_RUN`; planned times moved from SETTINGS to DAY_PLAN |
| draft | 1 | PROFILE `is_driver` replaces `work_time_rule`; `device_model` on registration; `GET /mobile/policy/location`; SETTINGS `upcoming` array; `deployment_type` on schedule item summary |
| draft | 1 | LOCATION_DISABLED/ENABLED uploaded immediately; `source` gains `FOLLOW_UP` (unknown values treated as PLANNED) |
| 2026-11-08 | 1.0.0 | Phase 07 baseline release: Auth (`/mobile/auth/login`, forced password change, single-device binding, mismatch handling), consent (`/mobile/auth/consent`), heartbeat (`/mobile/auth/heartbeat`), change log synchronization (`/mobile/sync/snapshot`, `/mobile/sync/changes` with delta coalescing, `/mobile/sync/ack`), location events batch ingestion (`/mobile/events/batch`), openapi-mobile.json, and standalone Mobile Tester Proxy (`tools/mobile-proxy/`). |
