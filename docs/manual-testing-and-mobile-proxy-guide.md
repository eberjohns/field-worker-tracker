# Manual Testing & Mobile Simulator Guide

This guide describes how QA testers, developers, and field team leads can test the **Field Worker Tracker (FWT)** platform end-to-end without hardcoded database seed scripts.

By using the standardized **Master Data Import Template** (`docs/import-templates/FieldWorkerTracker_Import_Template_v1.0.xlsx`) and the interactive **Mobile Proxy Simulator** (`tools/mobile-proxy/`), you can test all platform features—from data import, geofencing, and scheduling to real-time mobile GPS tracking, live monitoring, attendance calculation, and password management.

---

## 1. Quick Environment Setup

### 1.1 Start the PostgreSQL/PostGIS Container
Ensure Docker is running, then start the database container:
```bash
docker-compose up -d db
```

### 1.2 Start the Backend API
In a terminal:
```bash
cd backend
uv run uvicorn fw.main:app --port 8000 --reload
```
*Verify API liveness at:* `http://localhost:8000/health`

### 1.3 Start the Web Dashboard
In a second terminal:
```bash
cd web
npm run dev
```
*Access Web Dashboard at:* `http://localhost:5173`

### 1.4 Start the Mobile Proxy Simulator
In a third terminal:
```bash
python -m http.server 8085 --directory tools/mobile-proxy
```
*Access Mobile Simulator at:* `http://localhost:8085`

---

## 2. Authentication & Test Accounts

| Role | Username (Tally ID) | Default Password | What They Can Access |
|---|---|---|---|
| **Admin** | `ADMIN001` | `ChangeMe123!` | Full access: Imports, Users, Settings, System, Live Map, Boundaries, Approvals, Documents |
| **Engineer** | `1001` | `ChangeMe123!` | Technical and engineering oversight: Planner, Live Map, Approvals, Attendance, Boundaries |
| **Superintendent** | `1002` / `1003` | `ChangeMe123!` | Operational oversight: Planner, Employees, Attendance, Pending Visits |
| **Supervisor** | `1004` / `1005` / `1006` | `ChangeMe123!` | Direct team management: Planner, Leave recording, Attendance, Pending Visits |
| **Field Worker** | `1007` – `1025` | `Welcome123!` | Mobile App login (`http://localhost:8085`): Day plans, sync, GPS location transmission |

> **Development Blank Login Shortcut**: On `http://localhost:5173/login`, in `local` environment you can simply click **"Sign In"** with blank credentials to log in instantly as `ADMIN001`.

---

## 3. End-to-End Testing Workflow

### Step 1: Master Data Import
1. Log in to the Web Dashboard as **Admin** (`http://localhost:5173`).
2. Go to **Master Data Import** (`/imports`) in the sidebar.
3. Click **Choose File** and select `docs/import-templates/FieldWorkerTracker_Import_Template_v1.0.xlsx`.
4. Click **Validate Workbook**:
   - The system checks all 14 sheets, foreign keys, weekly patterns, salary math, and country rule constraints.
5. Click **Commit Import**:
   - Automatically populates:
     - **25 Employees** across roles (Engineer, Superintendents, Supervisors, Drivers, Gardeners, Technicians).
     - **34 Worksites** with UAE project codes, customer types, and contract budgets.
     - **146 Job Items** with required staff counts, hours per occurrence, and break windows.
     - **4 Accommodations** (Sonapur, Al Quoz, Jebel Ali, DIP camps).
     - **5 Client Groups** and **4 Geographic Zones**.
     - **Employee Salary structures & Public Holidays**.
     - **Operational Settings** (geofence radius, polling frequencies, attendance grace periods, document lead days).

---

### Step 2: Draw Geofence Boundaries
Attendance and live GPS containment require geofence polygons:
1. Navigate to **Boundary Queue** (`/boundaries`).
2. Review worksites and accommodations listed under `Unset Boundaries`.
3. Click **Draw Boundary** on a worksite (e.g. *Dr. Moopen's Business Bay* or *AFM Al Dhiyafa*).
4. Use the polygon drawing tool on the interactive map to draw the site perimeter, then click **Save Boundary**.
5. Do the same for at least one staff accommodation camp (e.g. *ACC-01 Sonapur* or *ACC-02 Al Quoz*).

---

### Step 3: Base Planner & Weekly Operational Roster
1. Navigate to **Base Planner** (`/base-planner`):
   - Review annual job item occurrence matrices and base recurring team assignments.
2. Navigate to **Operational Planner** (`/operational-planner`):
   - Review the weekly operational grid (Job Items x 7 Days).
   - Inspect daily required vs. assigned staff counts.
   - Click on any slot to add an operational shift override or replacement cover.

---

### Step 4: Leave Requests & Cover Auto-Resolution
1. Navigate to **Leave Management** (`/leave`).
2. Record a leave request:
   - Worker: Select `1010 - Manoj Patel` (Irrigation Technician)
   - Dates: Select next Monday to Wednesday
   - Type: `ANNUAL` or `SICK`
   - Reason: `Medical appointment`
3. Switch to **Approvals Inbox** (`/approvals`) and approve the leave request.
4. Check the **Dashboard** (`/`):
   - Under **Active Operational Alerts**, observe a new `COVER_NEEDED` alert for `Manoj Patel`.
5. Click **"Assign Cover in Planner"** on the alert:
   - You are taken to `/operational-planner` filtered to that date and worker.
   - Select the uncovered cell, assign a replacement worker (e.g. `1011 - Deepak Sharma`), and click **Save Roster**.
6. Return to **Dashboard** (`/`):
   - Verify the `COVER_NEEDED` alert has automatically disappeared and resolved!

---

### Step 5: Expiring Documents & Alerts
1. Navigate to **Documents** (`/documents`):
   - Review the document status list populated from the import template:
     - `1013 - Rajesh Nair`: **EXPIRED** Emirates ID (badge in red).
     - `1007 - Ramesh Kumar`: **EXPIRING SOON** Visa (expires in < 15 days).
     - `1010 - Manoj Patel`: **EXPIRING SOON** Passport.
     - `1017 - Mohan Lal`: **EXPIRING SOON** Labour Card.
     - `1024 - Jitender Pal`: **EXPIRING SOON** Driving License.
2. Filter by document type (`Visa`, `Emirates ID`, `Passport`, `Labour Card`, `Driving License`) or status (`Expiring Soon`, `Expired`, `Valid`).
3. Click **"Check & Raise Alerts"** to test background compliance alert evaluation.
4. Click **"Export CSV"** to verify audit compliance export.

---

### Step 6: Mobile Proxy Simulator (Simulating Worker GPS)
1. Open the Mobile Simulator in your browser: **`http://localhost:8085`**.
2. **Login as a Field Worker**:
   - Tally ID: `1010` (or `1007`, `1013`, `1017`)
   - Password: `Welcome123!`
   - Click **Login to Device**.
3. **Explore the Phone Interface**:
   - **Today's Shift**: View planned departure time, alarm lead time, worksite name, required hours, break duration, and supervisor contact.
   - **30-Day Forward Roster**: Tap the calendar tab to inspect synced upcoming shifts, off days, and holidays.
   - **Sync Tab**: Run a **Full Sync** or **Delta Sync** to pull the latest schedule from the backend.
4. **Simulate GPS Route & Events**:
   - **Manual Event Buttons**:
     - Click **"Site Entry"** to emit an entry event inside the worksite perimeter.
     - Click **"Ping"** to emit location pings during work hours.
     - Click **"Location OFF"** to simulate the worker disabling GPS (raises `TRACKING_INTERRUPTED` alert on dashboard).
     - Click **"Location ON"** to re-enable GPS (clears the alert).
     - Click **"Site Exit"** when the shift ends.
   - **Or use the Route Player**:
     - Select a route preset (*Standard Workday*, *Late Arrival*, or *Midday Gap*).
     - Select the Work Date (today or within the past 7 days).
     - Click **Play ▶** with speed `60x` or `300x` to simulate the full day's commute and shift.
   - Tap **"Transmit Batch"** in the Network tab to upload the location event batch to the backend (`POST /api/v1/mobile/events`).

---

### Step 7: Live Map & Attendance Verification
1. In the Web Dashboard, navigate to **Live Map** (`/live`):
   - Notice the worker pin on the map.
   - State indicators:
     - **Green (`ACTIVE`)**: Contact within the 15-minute active window.
     - **Amber (`NO RECENT SIGNAL / CAN'T TRACK`)**: Device has not uploaded a ping in >15 minutes.
     - **Red (`LOCATION DISABLED`)**: Worker explicitly toggled location tracking off.
   - Click the worker pin in the side panel or map:
     - Inspect **Position Age** (when the GPS fix was taken) vs. **Contact Age** (when the phone last synced with server).
     - View the worker's **Route Trail** (breadcrumb line showing movement between camp and site).
2. Navigate to **Attendance** (`/attendance`):
   - Select today's work date.
   - Inspect the attendance calculation:
     - Actual accommodation departure vs. planned departure.
     - First site entry and last site exit times.
     - Productive minutes, transit minutes, and break minutes used.
     - Overtime calculation (OT1 for standard workday extensions, OT2 for holidays/rest days).
3. Navigate to **Pending Visits** (`/pending-visits`):
   - Any scheduled work occurrence where the worker did not arrive at site appears in the list.
   - Test clicking **"Explain"** to submit a supervisor explanation.
   - Test clicking **"Reschedule"** to assign a follow-up shift to another worker.
   - Test clicking **"Close"** with a documented reason.

---

### Step 8: System & Account Settings (Change Password)
1. In the Web Dashboard, click **System** in the sidebar (`/system`).
2. **Change Password**:
   - Enter your current password (e.g. `ChangeMe123!`).
   - Enter a new secure password (e.g. `MyNewSecurePassword2026!`).
   - Confirm the new password.
   - Click **Update Password**.
   - Verify the success message and test logging out and logging back in with your new password.
3. **Application Telemetry**:
   - Review live backend API health, PostgreSQL container status, and server clock (UTC).
4. **Phase 13 Backup & Archive Section**:
   - Review the compliance preview for upcoming Phase 13 backup, restore drills, and archive tooling.

---

## 4. Key Verification Checklist for QA Testers

- [ ] Master data import parses and commits all 14 sheets without validation errors.
- [ ] Worksites imported without geofences appear in `/boundaries` and trigger dashboard boundary alerts.
- [ ] Approved leave creates a `TO_BE_COVERED` gap and a `COVER_NEEDED` alert on the Dashboard.
- [ ] Assigning a cover shift in `/operational-planner` automatically resolves the `COVER_NEEDED` alert.
- [ ] Documents expiring within 30 days display an `EXPIRING SOON` badge and raise document alerts.
- [ ] Expired documents display an `EXPIRED` badge in red.
- [ ] Mobile simulator successfully authenticates worker accounts and syncs 30-day forward rosters.
- [ ] Simulated GPS batches upload successfully and display on `/live` with real-time breadcrumb trails.
- [ ] Attendance calculations accurately compute site entry, exit, worked minutes, and overtime.
- [ ] Every user role (Admin, Engineer, Superintendent, Supervisor) can change their own password in `/system`.
- [ ] Dashboard is clean, displaying only operational statistics, action alerts, and pending requests.
