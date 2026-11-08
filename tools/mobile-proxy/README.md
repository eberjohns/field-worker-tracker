# FWT Mobile Tester Proxy & GPS Simulator

A lightweight, standalone web simulator representing a worker's mobile phone for testing the **Field Worker Tracker Mobile Contract (Phase 07)**.

It allows developers and QA to:
1. **Authenticate as a field worker** using Employee ID (`tally_id`) and password.
2. **Handle first-login forced password change**.
3. **Inspect single-device binding** and device mismatch handling.
4. **Accept and record location tracking consent policies**.
5. **Pull full snapshot data** (`/sync/snapshot`), including:
   - Worker profile and supervisor hierarchy.
   - Company tracking and attendance settings.
   - 30-day day plan with resolved shift times, alarm time, and day markers.
   - Worksites with full GeoJSON polygon boundaries and server-calculated geofence circles.
   - Accommodation camps with polygon boundaries.
6. **Fetch delta changes** (`/sync/changes?cursor=...`) with server-side coalescing.
7. **Simulate GPS movement**:
   - Interactive Leaflet map displaying worksite and accommodation polygons and geofence circles.
   - Draggable worker marker.
   - Real-time client-side Point-in-Polygon containment calculation.
   - Auto-event generation (`ENTRY`, `PING`, `EXIT`) upon crossing boundaries.
8. **Batch dispatch events** (`POST /api/v1/mobile/events/batch`) and observe validation results.

---

## Quick Start

### 1. Seed Demo Data
Ensure the backend database has the demo worker, accommodation, worksite, and day plans:
```bash
uv run --directory backend python ../tools/seed_phase07_demo.py
```
This provisions:
- Worker ID: `1193` ("Shanto Miah")
- Default Password: `Welcome123!` (forced password change required on first login)
- Worksite: `12A14301` ("Dubai Marina Towers Landscape") with polygon boundary
- Accommodation: `WARSAN_01` ("Warsan Staff Accommodation Camp") with polygon boundary
- Scheduled Work: Active shifts for the next 7 days

### 2. Run the Backend API
Start the backend server on `http://localhost:8000`:
```bash
uv run --directory backend uvicorn fw.main:app --reload --port 8000
```

### 3. Launch the Mobile Tester Proxy
In a new terminal, serve the `tools/mobile-proxy` folder using Python's built-in HTTP server:
```bash
python -m http.server 8085 --directory tools/mobile-proxy
```
Now open your browser at **[http://localhost:8085](http://localhost:8085)**.

---

## Testing Workflow Walkthrough

1. **Sign In**:
   - Leave Employee ID as `1193`, Password as `Welcome123!`, Device ID as `DEV_SIM_1193_A`.
   - Click **Sign In**.
   - Notice the amber alert: *"First Login: Change Password Required"*.
   - Enter a new password (e.g. `Secret456!`) and submit.
2. **Review Synced Data**:
   - The snapshot is automatically loaded upon password change (or click **Full Snapshot**).
   - Check the **Synced Worksites** (1) and **Day Plans** (40+) counts.
   - Review Today's Plan (`07:00 - 16:00`, Alarm: `06:30`, Marker: `SCHEDULED`).
   - The map centers and renders the green accommodation polygon (Warsan) and blue worksite polygon (Dubai Marina).
3. **GPS Movement & Event Generation**:
   - Drag the worker pin (👷) from Warsan towards Dubai Marina.
   - Or click **📍 Worksite (Inside)** to instantly teleport inside the site boundary.
   - Notice that the zone badge changes to `WORKSITE_POLYGON` and an `ENTRY` event is queued!
   - Click **Send Batch to Server** to submit `POST /api/v1/mobile/events/batch`.
   - Check the Network & Audit log console at the bottom for server confirmation.
4. **Device Mismatch Test**:
   - In a private/incognito window or using another browser tab, log in with `1193` using a different Device ID (e.g. `DEV_SIM_1193_B`).
   - The server rejects the login with `409 Conflict: DEVICE_MISMATCH` because employee `1193` is already bound to `DEV_SIM_1193_A`.
   - In the web dashboard at `http://localhost:5173/devices`, an Admin can view the device and click **Reset Binding** to permit re-registration.
