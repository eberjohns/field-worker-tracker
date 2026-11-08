# 18 - Mobile Team Integration & Onboarding Guide

**Audience: Mobile Application Engineers and QA.**  
This document is the operational onboarding guide complementing the formal [Mobile Sync Contract](09-mobile-sync-contract.md) and the machine-readable OpenAPI schema [`openapi-mobile.json`](../openapi-mobile.json).

---

## 1. Quick Overview

The Field Worker Tracker (FWT) backend acts as the authoritative source of truth for workforce scheduling, worksite boundaries, attendance evaluation, and payroll calculation.
The mobile application:
- Stores the worker's identity, company tracking settings, and a 30-day forward sliding schedule window offline.
- Detects proximity to worksites and accommodations using GeoJSON polygons and geofence circles.
- Collects raw location events (`ENTRY`, `EXIT`, `PING`, `LOCATION_DISABLED`, `LOCATION_ENABLED`) during scheduled working hours.
- Batches and transmits location events reliably over intermittent network connections.
- **Never calculates attendance or overtime on the device** (the server calculates attendance independently from immutable events).

---

## 2. Authentication & Device Binding Lifecycle

### Step 1: Initial Login
- Workers authenticate with their Employee ID (`tally_id`) and temporary default password (default: `Welcome123!`).
- **Endpoint**: `POST /api/v1/mobile/auth/login`
- **Payload**:
  ```json
  {
    "tally_id": "1193",
    "password": "Welcome123!",
    "device_identifier": "b6c1482f-2d7c-473f-...",
    "platform": "ANDROID",
    "device_model": "Samsung Galaxy A14",
    "app_version": "1.0.0",
    "os_version": "Android 14",
    "push_token": "fcm-device-push-token"
  }
  ```

### Step 2: Forced Password Change
- If the response contains `"must_change_password": true`, all operational endpoints (`/sync/*`, `/events/*`) return `403 Forbidden` (`PASSWORD_CHANGE_REQUIRED`).
- The mobile app must prompt the worker to set a new personal password:
- **Endpoint**: `POST /api/v1/mobile/auth/change-password`
  ```json
  {
    "old_password": "Welcome123!",
    "new_password": "MyNewSecurePassword!"
  }
  ```

### Step 3: Single-Device Binding
- The first successful login binds the worker's account to `device_identifier`.
- If the worker attempts to log in from a different device, the backend returns:
  `409 Conflict` with code `DEVICE_MISMATCH`.
- To swap devices, an **Admin must reset the device binding** from the web dashboard at `/devices` (`POST /api/v1/devices/{device_id}/reset-binding`).

---

## 3. Location Tracking Consent & Privacy Policy

Under UAE Personal Data Protection Law (Federal Decree-Law No. 45 of 2021), location tracking requires active worker consent.
- Fetch current active policy: `GET /api/v1/mobile/auth/consent?language=en`
- Record worker acceptance: `POST /api/v1/mobile/auth/consent`
  ```json
  {
    "policy_version": "1.0.0",
    "accepted": true,
    "language": "en",
    "app_version": "1.0.0"
  }
  ```
- If the backend publishes a new policy version, subsequent heartbeats or sync snapshots signal a policy update, requiring re-consent before location tracking resumes.

---

## 4. Synchronization Protocol

The sync engine uses an append-only change log with monotonic global cursors.

```
       Mobile Device                             Backend Server
            |                                           |
            |--- 1. GET /mobile/sync/snapshot --------->| (On clean install or resync)
            |<-- Returns all entities & cursor 4812 ----|
            |                                           |
            |--- 2. POST /mobile/sync/ack {cursor:4812}->| (Ack applied cursor)
            |<-- 204 No Content ------------------------|
            |                                           |
            |--- 3. Heartbeat or Push nudge (latest=4820)
            |                                           |
            |--- 4. GET /mobile/sync/changes?cursor=4812>|
            |<-- Coalesced delta changes (next: 4820) --|
            |                                           |
            |--- 5. Apply transactionally in local DB --|
            |--- 6. POST /mobile/sync/ack {cursor:4820}->|
```

### 1. Full Snapshot (`GET /api/v1/mobile/sync/snapshot`)
Returns all active entities for the worker within the forward 30-day window:
- `PROFILE`: Worker name, designation, phone, supervisor contact details.
- `SETTINGS`: Tracking intervals, tolerances, grace periods.
- `DAY_PLAN`: Per-day schedule details (work date, resolved start/end times, alarm time, and day markers such as `WEEKLY_OFF`, `PUBLIC_HOLIDAY`, `LEAVE`).
- `SCHEDULE_ITEM`: Individual job assignments for each day.
- `JOB`: Worksite metadata, full GeoJSON `boundary` polygon, and computed `geofence_circle`.
- `ACCOMMODATION`: Assigned living quarters with GeoJSON `boundary` polygon.

### 2. Delta Changes (`GET /api/v1/mobile/sync/changes?cursor=N`)
- The server performs **delta coalescing**: if an entity had multiple revisions between cursor $N$ and the latest cursor, only the latest final state is delivered.
- If `resync_required: true` is returned (e.g., worker phone was offline longer than the 30-day change log retention window), the app must discard local schedule data and pull a fresh snapshot.

### 3. Acknowledging Cursor (`POST /api/v1/mobile/sync/ack`)
- After committing the sync transaction to the phone's local SQLite database, send the new cursor to update the server's sync tracking and web dashboard lag indicators.

---

## 5. Worksite Boundaries vs. Geofence Circles

To balance mobile battery efficiency with precise attendance tracking:
1. **Hardware Geofence Circle** (`JOB.geofence_circle`):
   - `{ center: { lat, lng }, radius_m }`
   - Register this circle with the mobile operating system's native geofencing API (e.g. Android GeofencingClient or iOS CLCircularRegion).
   - Serves as the wake-up trigger when approaching the worksite.
2. **GeoJSON Boundary Polygon** (`JOB.boundary`):
   - Exact boundary coordinates in WGS84 GeoJSON format (`[longitude, latitude]`).
   - When inside the geofence circle, the mobile app switches to high-frequency polling and executes a **client-side Point-in-Polygon check** (e.g. standard ray-casting algorithm).
   - Only when the GPS coordinate is confirmed inside the polygon does the app create an `ENTRY` event.

---

## 6. Location Events Batch Ingestion

- **Endpoint**: `POST /api/v1/mobile/events/batch`
- **Request Format**:
  ```json
  {
    "events": [
      {
        "event_id": "c1f7b134-8b83-4a12-9c17-f58c70d42183",
        "event_type": "ENTRY",
        "recorded_at": "2026-11-08T07:02:15Z",
        "latitude": 25.080250,
        "longitude": 55.145250,
        "accuracy_m": 4.8,
        "speed_mps": 0.0,
        "battery_pct": 82,
        "worksite_id": "9da30c7f-a667-4feb-b958-c12c1695de2d",
        "is_mock": false
      }
    ]
  }
  ```
- **Validation Rules**:
  - `recorded_at` must not be older than 30 days (`TIMESTAMP_TOO_OLD`).
  - `recorded_at` must not be more than 5 minutes in the future (`TIMESTAMP_IN_FUTURE`).
  - `latitude` must be in range $[-90, 90]$, `longitude` in $[-180, 180]$ (`INVALID_COORDINATES`).
  - `event_id` must be a unique UUID generated when the event is recorded on the phone. Re-sending an already ingested `event_id` returns status `DUPLICATE` without creating a duplicate record or erroring out.
- **Immediate Dispatches**:
  - `LOCATION_DISABLED` and `LOCATION_ENABLED` events should be uploaded immediately to inform supervisors of tracking disruptions.

---

## 7. Machine-Readable OpenAPI Schema

Export the official schema anytime using:
```bash
python tools/export_openapi.py --tag mobile
```
This produces `openapi-mobile.json` at the root of the repository, containing schemas and endpoint specifications for all `/mobile/*` routes.
You can import this JSON directly into Postman, Insomnia, or Swagger Codegen / OpenAPI Generator to generate TypeScript, Kotlin, or Swift API models.

---

## 8. Mobile Tester Proxy & GPS Simulator

To test the integration end-to-end without a physical device, use the included standalone proxy:
```bash
# 1. Seed demo worker and worksite
uv run --directory backend python ../tools/seed_phase07_demo.py

# 2. Run backend
uv run --directory backend uvicorn fw.main:app --port 8000

# 3. Serve the proxy
python -m http.server 8085 --directory tools/mobile-proxy
```
Visit **[http://localhost:8085](http://localhost:8085)** to test logins, forced password resets, live map coordinate tracking, boundary transitions, and batch uploads.

---

## 9. Seeded Reference Worker Account

| Attribute | Value |
|---|---|
| Employee ID (`tally_id`) | `1193` |
| Worker Name | Shanto Miah |
| Initial Password | `Welcome123!` |
| Must Change Password | `True` (enforced at first login) |
| Worksite Assigned | `12A14301` ("Dubai Marina Towers Landscape") |
| Accommodation | `WARSAN_01` ("Warsan Staff Accommodation Camp") |
| Shift Schedule | Active shifts 07:00 - 16:00 for the next 7 days |

