# FWT Mobile Simulator & GPS Route Player (Phase 07 & 08)

An interactive, standalone Android Studio-inspired mobile phone simulator and route player for the **Field Worker Tracker (FWT) Mobile Contract**.

It provides:
1. **Realistic Smartphone Interface**:
   - Modern phone chassis with status bar clock, battery indicator, and dynamic island.
   - **Authentication Gate**: Device login screen requesting Tally ID and Password. Only authenticated devices can access shifts, GPS tracking, and synced data.
   - **Today's Shift View**: Local shift alarm preview with chime test (`04:30 AM`), planned departure (`05:00 AM`), site hours (`06:00 – 15:30`), break window (`30 min midday`), camp details, and supervisor contact.
   - **GPS & Zone View**: Real-time Point-in-Polygon containment detection (`CAMP`, `TRANSIT`, `PERIMETER`, `INSIDE_WORKSITE`), live coordinates, accuracy, speed, and manual event buttons (`ENTRY`, `PING`, `EXIT`, `LOCATION OFF/ON`).
   - **30-Day Forward Roster**: Dynamic forward view of synced day plans with shift times, alarm times, working days, and rest days.
   - **Dedicated Profile View**: Shows worker name, tally ID, grade, contact phone, weekly off day, living camp, and direct supervisor contact with a 1-click call button.
   - **Sync & Settings View**: Sync engine controls (Full Snapshot, Delta Sync, Ack), cursor tracking, dynamic company settings breakdown, and privacy consent management.
2. **Interactive Waypoint Route Player**:
   - Play/Pause/Reset timeline playback with speed multiplier (`1x`, `10x`, `60x`, `300x`).
   - Scrub through the simulated day using the timeline slider.
   - Realistic geographic placement: Warsan Staff Accommodation Camp and Dubai Silicon Oasis Landscape Maintenance worksite are ~4.1 km apart, providing an authentic 10-15 minute commute.
   - Preset route templates:
     - **Standard Workday**: 05:00 Camp -> 05:35 Leave Camp -> 05:48 Transit -> 05:58 Geofence Buffer -> 06:02 Site Entry -> 06:07 Confirmation Ping -> 09:00/12:00/14:00 Work -> 15:31 Site Exit -> 16:00 Back at Camp.
     - **Late Arrival**: Arrives at site at 08:30 instead of 06:00.
     - **Midday Gap**: Leaves site from 11:30 to 13:00, then returns.
3. **Route Import & Export (JSON)**:
   - Import custom route JSON files generated externally or by UI tools.
   - Export currently loaded route waypoints to a `.json` file.
4. **Ground-Truth Attendance Analytics (Phase 08 Preparation)**:
   - Live analytics card showing exact calculated worked minutes inside the worksite polygon (e.g. 569m / 9h 29m), time in transit, and time at accommodation.
   - Cross-check and verify these ground truth figures against attendance engine calculations in Phase 08.
5. **REST Network & Audit Inspector**:
   - Live log of every HTTP request sent to the backend.
   - Displays method, endpoint, status code (`200 OK`, `401`, `409`, `422`), and latency in milliseconds.
   - Click any entry to inspect the full JSON Request and Response payloads.
   - **Export Network Log (JSON)**: One-click export of the complete HTTP exchange history (`fwt_network_traffic.json`) for debugging, audits, and automated validation.

---

## Quick Start

### 1. Seed Demo Data & Company Settings
```bash
uv run --directory backend python ../tools/seed_phase07_demo.py
```
This seeds:
- Worker ID: `1193` ("Shanto Miah", Landscape Gardener)
- Password: `Welcome123!`
- Supervisor: `SUP001` ("Shakir Khisham", `+971 50 123 4567`)
- Worksite: `12A14301` ("Dubai Silicon Oasis Landscape Maintenance") with GeoJSON polygon boundary (~4.1 km from camp)
- Accommodation: `WARSAN_01` ("Warsan Staff Accommodation Camp") with polygon boundary
- Forward Schedule: 30 days of active shifts seeded for worker 1193 with Fridays off.
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

By default, the backend allows local development origins on common localhost ports (`http://localhost:8085`, `http://127.0.0.1:8085`, `http://localhost:5173`, etc.) via an origin regex in `fw.main`.

If you host the simulator on a remote server, external domain, or different port, configure `CORS_ORIGINS` in your `.env` file:

```env
# backend/.env or root .env
CORS_ORIGINS=["http://localhost:8085", "http://127.0.0.1:8085", "https://your-mobile-proxy-host.domain"]
```

---

## Route JSON Format

You can import any custom route using the **📂 Import Route JSON** button. The file must follow this JSON schema:

```json
{
  "name": "Custom Dubai Route",
  "waypoints": [
    {
      "time": "05:00:00",
      "lat": 25.15825,
      "lng": 55.41225,
      "label": "Warsan Camp Departure"
    },
    {
      "time": "05:48:00",
      "lat": 25.14200,
      "lng": 55.39500,
      "label": "Manama St Transit"
    },
    {
      "time": "06:02:00",
      "lat": 25.13100,
      "lng": 55.38400,
      "label": "Worksite Entry"
    },
    {
      "time": "12:00:00",
      "lat": 25.13050,
      "lng": 55.38350,
      "label": "Midday Break"
    },
    {
      "time": "15:31:00",
      "lat": 25.12650,
      "lng": 55.37800,
      "label": "Worksite Exit"
    },
    {
      "time": "16:00:00",
      "lat": 25.15825,
      "lng": 55.41225,
      "label": "Back at Camp"
    }
  ]
}
```
