# 017 - Mobile Authentication, Change Log Synchronization, and Events Ingestion Architecture

Status: Accepted  
Date: 2026-11-08  

## Context
Phase 07 implements the backend synchronization contract, authentication, and location event ingestion for the field worker mobile application (`docs/09-mobile-sync-contract.md`). The mobile app is developed by an independent team.
Key architectural requirements and client decisions (DEC-13, DEC-14, DEC-15, DEC-53, ADR-003):
1. **Worker Authentication & Device Binding**: Workers log in using their Employee ID (`tally_id`) and a default password (`Welcome123!`). First login enforces mandatory password change before accessing data. Workers are bound to a single mobile device on first login; subsequent logins from another device return HTTP 409 `DEVICE_MISMATCH` until an Admin resets the binding via `/devices`.
2. **Synchronized Entities**: The mobile app requires offline access to:
   - `PROFILE` (name, staff grade, phone, supervisor reporting line)
   - `SETTINGS` (tracking intervals, grace periods, tolerances)
   - `DAY_PLAN` (30-day sliding window of resolved shift times, alarm time, and day markers)
   - `SCHEDULE_ITEM` (scheduled assignments for each day)
   - `JOB` (worksites with exact polygon boundary and precalculated geofence circle)
   - `ACCOMMODATION` (living quarters with polygon boundary)
3. **Change Synchronization**: Changes to master data, schedules, worksite boundaries, or time rules must be materialized into `sync_changes` per affected worker within the same database transaction. Delta sync requests must coalesce multiple updates to the same entity within a cursor window, returning only the latest state to conserve mobile bandwidth.
4. **Location Events Ingestion**: Mobile devices batch-upload raw location events (`ENTRY`, `EXIT`, `PING`, `LOCATION_OFF`, `TAMPER_SUSPECTED`) to `POST /api/v1/mobile/events/batch`. Raw events must be validated (timestamps, coordinates, duplicate IDs) and stored immutably in `mobile_event_logs`. Full attendance evaluation is deferred to Phase 08.
5. **Push Notifications**: Outside push service must be decoupled via a port adapter (`PushProvider`) with a configurable null backend for development and FCM backend for production.
6. **Mobile Integration Tooling**: A published OpenAPI schema (`openapi-mobile.json`) and an interactive testing tool are required to validate the contract without physical mobile devices.

## Options Considered

### 1. Worksite Boundaries & Geofences
- **Option A (Geofence Circles only)**: Server sends only center coordinates and radius.
  - *Drawback*: Fails to provide exact polygonal coverage. Workers on odd-shaped sites (e.g. narrow roads, golf courses) would be incorrectly flagged as absent or offsite.
- **Option B (Polygon Boundaries only)**: Server sends GeoJSON polygon coordinates, mobile computes bounding circles.
  - *Drawback*: Requires mobile app to perform complex geometric calculations on low-power devices.
- **Option C (Both GeoJSON Polygon and Pre-Calculated Geofence Circle)**:
  - Server sends full GeoJSON `boundary` (for point-in-polygon attendance verification) and a computed `geofence_circle` (`{center: {lat, lng}, radius_m}`).
  - *Decision*: Adopt **Option C**. Mobile OS hardware geofence triggers on the circle; mobile app Point-in-Polygon verifies presence inside the site polygon.

### 2. Sync Change Log & Delta Delivery
- **Option A (Full Resync on every poll)**: Mobile always downloads all 30 days of data.
  - *Drawback*: High cellular data usage for thousands of workers.
- **Option B (Cursor-based Change Log with Coalescing)**:
  - Database stores append-only `sync_changes` sequence. Delta query `GET /mobile/sync/changes?cursor=N` coalesces changes for the same `(entity_type, entity_id)` and returns only the final state.
  - If cursor is below retention compaction floor, server signals `resync_required = true` prompting a fresh snapshot.
  - *Decision*: Adopt **Option B**.

### 3. Layering & Events Endpoint
- **Option A (Events Module imports Sync Module for routes)**:
  - In `import-linter`, `fw.modules.sync` is in Layer 4 and `fw.modules.events` is in Layer 5 (`sync` is above `events`). Layer 5 importing Layer 4 violates acyclic layering.
- **Option B (Sync Module mounts Mobile Events Ingestion via EventsService)**:
  - Keep `fw.modules.events` focused on raw event logs and ingestion logic. `fw.modules.sync` (Layer 4) imports `EventsService` from `events` (Layer 5) to expose `/mobile/events/batch` under the `/mobile` tag.
  - *Decision*: Adopt **Option B**, ensuring 100% compliance with modular monolith layering.

### 4. Integration & Testing Tooling
- **Option A (Curl / Postman collection only)**: Hard for mobile engineers to test GPS boundary crossing and live coordinate streaming.
- **Option B (Standalone Mobile Tester Proxy & GPS Simulator)**:
  - Standalone web app in `tools/mobile-proxy/` running Leaflet maps with worksite/camp polygons, draggable worker pin, automated event batch queue, and live API console.
  - *Decision*: Adopt **Option B**.

## Decision
1. **Mobile Authentication & Binding**:
   - `POST /api/v1/mobile/auth/login` verifies credentials, binds `device_identifier` to `registered_devices`, and issues JWT with role `WORKER`.
   - `must_change_password` enforced via `POST /api/v1/mobile/auth/change-password`.
   - Admin-only endpoint `POST /api/v1/devices/{device_id}/reset-binding` revokes active device.
2. **Sync Change Materialization**:
   - Synchronous domain-event listeners on `fw.core.event_bus` (`ScheduledWorkChanged`, `HolidayChanged`, `TimeRuleChanged`, `EmployeeProfileChanged`, `WorksiteBoundaryChanged`) insert rows into `sync_changes` within the publisher's transaction.
   - `GET /api/v1/mobile/sync/snapshot` returns baseline state and primes cursor.
   - `GET /api/v1/mobile/sync/changes?cursor=N` delivers coalesced delta updates.
   - `POST /api/v1/mobile/sync/ack` records confirmed cursor on `registered_devices`.
3. **Location Events Ingestion**:
   - `POST /api/v1/mobile/events/batch` validates timestamps ($< 30$ days old, $\le 5$ min future skew), coordinate bounds ($[-90, 90], [-180, 180]$), and idempotency, persisting into `mobile_event_logs`.
4. **Push Adapter**:
   - `PushProvider` protocol with `NullPushProvider` (default) and `FcmPushProvider`.
5. **Contract Export & Verification**:
   - `tools/export_openapi.py --tag mobile` generates `openapi-mobile.json`.
   - CI step validates `openapi-mobile.json` is clean and up to date.
6. **Mobile Tester Proxy**:
   - Standalone application in `tools/mobile-proxy/` simulating worker GPS movements, boundary transitions, and sync requests.

## Consequences
- Database migration `0009_mobile_sync.py` adds `sync_changes`, `consent_records`, and `mobile_event_logs`.
- Web dashboard adds dedicated `/devices` route with Admin-restricted reset binding.
- Mobile team receives published contract (`docs/09-mobile-sync-contract.md`), onboarding guide (`docs/18-mobile-integration-guide.md`), `openapi-mobile.json`, and `tools/mobile-proxy/`.

