# FWT Mobile Simulator & GPS Route Player (Phase 07 & 08)

An interactive, standalone Android Studio-inspired mobile phone simulator and route player for the **Field Worker Tracker (FWT) Mobile Contract**.

It provides:
1. **Realistic Smartphone Interface**:
   - Modern phone frame with status bar clock, battery indicator, and dynamic island.
   - **Today's Shift View**: Local shift alarm preview with chime test (`04:30 AM`), planned departure (`05:00 AM`), site hours (`06:00 – 15:30`), break window, camp details, and supervisor contact.
   - **GPS & Zone View**: Real-time Point-in-Polygon containment detection (`CAMP`, `TRANSIT`, `PERIMETER`, `INSIDE_WORKSITE`), coordinates, accuracy, speed, and manual event buttons.
   - **Roster View**: Forward 30-day view of synced day plans with shift times, alarm times, and day markers.
   - **Sync & Settings View**: Sync engine controls (Snapshot, Delta, Ack), cursor tracking, dynamic company settings breakdown, and privacy consent management.
2. **Interactive Waypoint Route Player**:
   - Play/Pause/Reset timeline playback with speed multiplier (`1x`, `10x`, `60x`, `300x`).
   - Scrub through the simulated day using the timeline slider.
   - Preset route templates:
     - **Standard Workday**: 05:00 Camp -> 05:35 Transit -> 06:02 Site Entry -> 12:00 Midday Ping -> 15:31 Site Exit -> 16:30 Camp.
     - **Late Arrival**: Arrives at site at 08:30 instead of 06:00.
     - **Midday Gap**: Leaves site from 11:30 to 13:00, then returns.
3. **Route Import & Export (JSON)**:
   - Import custom route JSON files generated externally or by UI tools.
   - Export currently loaded route waypoints to a `.json` file.
4. **Ground-Truth Attendance Analytics (Phase 08 Preparation)**:
   - Live analytics card showing exact calculated worked minutes inside the worksite polygon, time in transit, and time at accommodation.
   - Use these exact metrics to cross-check and verify the attendance engine calculations in Phase 08.
5. **REST Network & Audit Inspector**:
   - Live log of every HTTP request sent to the backend.
   - Displays method, endpoint, status code (`200 OK`, `401`, `409`, `422`), and latency in milliseconds.
   - Click any entry to inspect the full JSON Request and Response payloads.

---

## Quick Start

### 1. Seed Demo Data & Company Settings
```bash
uv run --directory backend python ../tools/seed_phase07_demo.py
```
This seeds:
- Worker ID: `1193` ("Shanto Miah")
- Default Password: `Welcome123!`
- Worksite: `12A14301` ("Dubai Marina Towers Landscape") with GeoJSON polygon boundary
- Accommodation: `WARSAN_01` ("Warsan Staff Accommodation Camp") with polygon boundary
- Dynamic Company Settings: `day_plan_alarm_lead_minutes` (30 min), `geofence_circle_radius_m` (300 m), `approach_polling_interval_s` (60 s), `confirmation_polling_interval_s` (300 s).

### 2. Start the Backend API
```bash
uv run --directory backend uvicorn fw.main:app --port 8000
```

### 3. Launch the Mobile Simulator
```bash
python -m http.server 8085 --directory tools/mobile-proxy
```
Open **[http://localhost:8085](http://localhost:8085)** in your browser.

---

## CORS Configuration

By default, the backend allows local development origins on common ports (`http://localhost:8085`, `http://127.0.0.1:8085`, `http://localhost:5173`, etc.).

If you host the simulator on a remote server, external domain, or different port, configure `CORS_ORIGINS` in your environment or `.env` file:

```env
# backend/.env or root .env
CORS_ORIGINS=["http://localhost:8085", "http://127.0.0.1:8085", "https://your-mobile-proxy-host.domain"]
```

---

## Route JSON Format

You can import any custom route using the **📂 Import Route JSON** button. The file must follow this JSON schema:

```json
{
  "name": "Custom Dubai Marina Route",
  "waypoints": [
    {
      "time": "05:00:00",
      "lat": 25.15825,
      "lng": 55.41225,
      "label": "Warsan Camp Departure"
    },
    {
      "time": "05:35:00",
      "lat": 25.13000,
      "lng": 55.24000,
      "label": "Al Khail Road"
    },
    {
      "time": "06:02:00",
      "lat": 25.08025,
      "lng": 55.14525,
      "label": "Worksite Entry"
    },
    {
      "time": "12:00:00",
      "lat": 25.08010,
      "lng": 55.14480,
      "label": "Midday Check"
    },
    {
      "time": "15:31:00",
      "lat": 25.07750,
      "lng": 55.14200,
      "label": "Worksite Exit"
    },
    {
      "time": "16:30:00",
      "lat": 25.15825,
      "lng": 55.41225,
      "label": "Arrival Back at Camp"
    }
  ]
}
```

---

## Ground-Truth Verification Workflow for Phase 08

1. Click **Play Route** (at `60x` or `300x` speed).
2. The worker travels from Warsan Camp to Dubai Marina, works on site, and returns.
3. Observe the **Ground Truth Worked Time** card:
   - For the standard route: **`9h 29m (569m)`** inside the worksite polygon.
   - Deducting the standard 30 min midday break = **`539 worked minutes (8.98 hours)`**.
4. The simulator automatically records and flushes the `ENTRY`, `PING`, and `EXIT` events to `POST /api/v1/mobile/events/batch`.
5. In Phase 08, when the attendance calculation engine runs over the database `mobile_event_logs`, you can cross-check that the attendance table reports exactly 539 worked minutes with `ENTRY` at 06:02 and `EXIT` at 15:31!
