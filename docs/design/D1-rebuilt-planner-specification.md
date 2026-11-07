# Comprehensive Specification: Ground-Up Rebuild of the Planning & Scheduling System

---

## 1. Domain Context & Core Contract Model

### 1.1 Commercial Contract Reality
Field workforce tracking in the UAE and GCC is governed by **Annual Maintenance Contracts (AMCs)** for commercial facilities, residential communities, and infrastructure landscaping.
* **Clients pay for contractual staffing delivery (SLAs)**: e.g., 2 dedicated gardeners 6 days a week, 1 irrigation technician visit per month, 1 supervisor audit per week.
* **Under-staffing penalty risk**: Missed or uncovered visits result in contractual liquidated damages / invoice deductions.
* **Over-staffing / Excess cost**: Unscheduled extra shifts represent unbillable operational waste unless explicitly tracked as extra-contractual works.
* **Worker Welfare & Labor Law**: Every worker has a mandatory **Weekly Rest Day** (typically Friday or Sunday). Working on rest days is treated as planned overtime (OT1 or OT2) and must not be scheduled as an ongoing standard recurrence.

### 1.2 Contract Validity & Annual Operating Budget (UI Placement)
In the Worksites & Jobs section (`/worksites` and `/worksites/:id`):
1. **Contract Validity Period**: Prominently displays `start_date` to `end_date` (e.g., `01 Jan 2026 – 31 Dec 2026` or `Active • Ongoing`).
2. **Annual Operating Budget**: Prominently displays `budget_amount` as **AED / year** (the annual operating labor budget for the contract year per `DEC-29`).

---

## 2. Dedicated Workspaces & Navigation Structure

The system is cleanly split into **two dedicated top-level pages in the application navigation**:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ NAVIGATION SIDEBAR                                                                                     │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ [Dashboard]                                                                                            │
│ [Worksites & Jobs]                                                                                     │
│ [Employees & Org]                                                                                      │
│ ────────────────────────────────────────────────────────────────────────────────────────────────────── │
│ [Base Planner]          --> /base-planner         (Master Blueprint: Recurring Weekly Schedule)        │
│ [Operational Planner]   --> /operational-planner  (Live Calendar: Weekly Coverage, Roster, Leaves)     │
│ ────────────────────────────────────────────────────────────────────────────────────────────────────── │
│ [Attendance & Events]                                                                                  │
│ [Payroll & Overtime]                                                                                   │
│ [Master Imports]                                                                                       │
│ [Settings]                                                                                             │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Strict UI Design System & Styling Rules

> [!IMPORTANT]
> **Strict Light-Theme Enterprise UI**: The application does **NOT** use dark mode classes (`dark:*`) or dark/black background styling. It adheres strictly to the clean, high-contrast, professional enterprise design system established in `docs/10-ui-views.md` and the rest of the application (`Employees.tsx`, `Worksites.tsx`, `WorksiteDetail.tsx`).

### 3.1 Design Tokens & Color Palette
- **Canvas / Background**: Clean neutral background (`bg-slate-50`), white card containers (`bg-white`), borders in light slate (`border-slate-200` / `border-slate-300`).
- **Typography**: High-contrast slate typography (`text-slate-900` for primary headers, `text-slate-700` for body text, `text-slate-500` for secondary metadata).
- **Brand / Primary Accent**: Clean indigo (`bg-indigo-600`, `text-indigo-600`, `bg-indigo-50` for subtle active chips).
- **Status & Marker Badges**:
  - **Base Blueprint Shifts**: Muted rendering (40–50% opacity, `bg-indigo-50`, `border-indigo-300`, dashed border, `text-indigo-700`).
  - **Operational Overrides & Direct Shifts**: Solid rendering (100% opacity, `bg-indigo-600`, `text-white`, shadow-sm).
  - **Approved Leave Gap (`TO_BE_COVERED`)**: Amber dashed border (`border-dashed border-amber-400`), soft amber fill (`bg-amber-50`), alert icon, `text-amber-800`.
  - **Weekly Rest Day Marker**: Soft slate (`bg-slate-100`, `text-slate-600`, `WEEKLY OFF`).
  - **Public Holiday Marker**: Soft sky-blue (`bg-sky-50`, `border-sky-300`, `text-sky-800`, `HOLIDAY`).
  - **Recommended Target Day**: Subtle cyan highlight ring (`ring-1 ring-cyan-500/70`).
  - **Quota Met Indicator**: Soft emerald pill with checkmark (`bg-emerald-50`, `text-emerald-700`, `✓ Quota Met`).
  - **Excess Visit**: Soft purple pill (`bg-purple-100`, `text-purple-700`, `+1 Excess`).

### 3.2 Layout & Freeze Panes
- **Sticky Freeze Headers**: Table column headers (`MON` to `SUN`) and top control bars remain pinned (`sticky top-0 z-20 bg-white/95 backdrop-blur border-b border-slate-200`) so planners never lose context while scrolling large contract schedules.
- **High-Density Data Grid**: Optimized cell height (50–60px) and clean whitespace allowing 15+ job lines on a standard 1080p display without excessive scrolling.

---

## 4. Unified Grid Architecture for Both Planners

Both the **Base Planner** and the **Operational Planner** share the **identical, intuitive high-density matrix grid**:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ TOP CONTROLS BAR                                                                                                                 │
│ [Search Job # or Name...]   Supervisor Crew: [All Crews | Shakir (Hiace) | Deira Bus ▾]   Week: [<] Week 45: 02-08 Nov [>] [Today]│
├──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ WORKSITE 12A14301 - Emirates Hills Villas (Outdoor) • Contract: 01 Jan 2026 – 31 Dec 2026 • Budget: 185,000 AED / yr            │
├──────────────────────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬──────────────┬─────────────┤
│ Job Item & Quota         │ MON          │ TUE          │ WED          │ THU          │ FRI          │ SAT          │ SUN         │
├──────────────────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼─────────────┤
│ Item A: Gardener         │ Shanto Miah  │ Shanto Miah  │ Shanto Miah  │ Shanto Miah  │ Farooq Khan  │ Shanto Miah  │   —         │
│ (G1 - 6x/week, 8h/day)   │ Hamid Ali    │ Hamid Ali    │ Hamid Ali    │ Hamid Ali    │ Bashir M.    │ Hamid Ali    │ (Rest Day)  │
│ Quota: 6 / 6 Met ✓       │ (8h)         │ (8h)         │ (8h)         │ (8h)         │ (8h)         │ (8h)         │             │
├──────────────────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼──────────────┼─────────────┤
│ Item I: Supervisor       │ Shakir (4h)  │   —          │   —          │   —          │   —          │   —          │   —         │
│ (G3 - 1x/week, 4h/visit) │ [Target] ✓   │ (Quota Met)  │ (Quota Met)  │ (Quota Met)  │ (Quota Met)  │ (Quota Met)  │ (Rest Day)  │
└──────────────────────────┴──────────────┴──────────────┴──────────────┴──────────────┴──────────────┴──────────────┴─────────────┘
```

### 4.1 Grid Dimensions
1. **Rows**: Grouped by Job (Worksite).
   - **Worksite Header Bar**: Displays Job Number, Job Name, Customer Type, Outdoor/Indoor badge, Contract Validity Period, and Annual Operating Budget.
   - **Sub-Rows (Job Items)**: Under each Worksite, each row represents a contractual line item:
     - Sub-item code (e.g. `A`, `B`, `I`)
     - Staff grade description (e.g. `Gardener - Hand Watering`, `Supervisor`)
     - Planned grade code (e.g. `G1A`, `G2B`)
     - Frequency & occurrences (e.g. `Weekly - 6x/week` or `Monthly - 2x/month`)
     - Shift duration & headcount required
     - Quota fulfillment summary (`N / K visits assigned`, `✓ Quota Met`)
2. **Columns**: The 7 weekdays (`MON`, `TUE`, `WED`, `THU`, `FRI`, `SAT`, `SUN`).
3. **Cells**: Assigned workers for that weekday slot. Clicking any cell opens the **Assignment Modal**.

---

## 5. Base Planner vs. Operational Planner: Clear Logic Distinction

While both pages use the exact same grid layout, their **business logic and underlying purpose are distinctly separated**:

| Feature | Base Planner (`/base-planner`) | Operational Planner (`/operational-planner`) |
|---|---|---|
| **Core Purpose** | Master recurring blueprint (permanent year-long staffing plan). | Live daily calendar execution (weekly roster, overrides, leave covers). |
| **Dates Scope** | Recurring weekdays across the contract validity horizon (`start_date` to `end_date`). | Specific calendar dates (`23 Nov 2026` to `29 Nov 2026`). |
| **Assignment Storage** | **Explicit Day-by-Day Storage**: Every entry is stored with its concrete day (`MON`, `TUE`, ..., `SUN`) and cadence interval. Zero fragile `ALL` masks that wipe other days. | **Single-Day Shifts**: Stored as concrete calendar date shifts in `scheduled_works`. |
| **Quota Enforcement** | **Strict Contract Quota (No Excess)**: Cannot assign more than the contract occurrences (e.g. 6 days for a 6-day job). | **Allows Operational Excess**: Extra spot visits or compensatory shifts are marked `+1 Excess`. |
| **Cadence for Periodic Jobs** | **In-Modal Cadence Selector**: For monthly items, select which week(s) (`Week 1..4`); for quarterly items, select which month (`Month 1..3`) and week. | **Date-Bound**: Shifts sit on specific calendar dates within the month/quarter. |
| **Visual Styling** | Standard template chips. Target day recommendations highlighted with cyan ring. | Visual hierarchy: Low-opacity muted chips for Base Blueprint vs Solid chips for Overrides. |
| **Absence / Leave** | Does not track daily leave; configures who *should* regularly work. | Tracks approved leaves; absent workers render as **`TO_BE_COVERED`** (dashed amber). |
| **Underlying Table** | `base_roster_templates` & `base_roster_entries`. | `scheduled_works` (linked to `base_roster_templates` via precedence). |

---

## 6. Click-to-Assign Slot Modal & Cadence Engine

Clicking on any weekday cell/slot opens the **Assignment Modal**:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ ASSIGN WORKERS TO SLOT                                                                           [ ✕ ] │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ Worksite: 12A14301 - Emirates Hills Villas • Item A (Gardener - G1A)                                   │
│ Target Slot: WEDNESDAY • Required Headcount: 2 Staff • Shift Duration: 8.0 hrs                         │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ PERIODIC CADENCE (For Monthly & Quarterly Items)                                                       │
│ For Monthly:   [x] Week 1   [ ] Week 2   [x] Week 3   [ ] Week 4                                       │
│ For Quarterly: Target Month: [ Month 1 | Month 2 | Month 3 ]  • Target Week: [ Week 1..4 ]             │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ CONVENIENCE ACTIONS                                                                                    │
│ [ Fill Across Active Working Days (Mon–Sat) ]  (Copies current crew without touching other days)      │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ CURRENTLY ASSIGNED WORKERS IN THIS SLOT (1 / 2)                                                        │
│  [ Shanto Miah (G1A) • 8.0h • Off: Friday ]                                                      [ ✕ ] │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ CANDIDATE WORKER RECOMMENDATIONS                                                                       │
│ Search: [___________________]    ☑ Filter to Supervisor Shakir's Crew (Toggle to search all)         │
│                                                                                                        │
│  ★ Hamid Ali * (G1A) • Hand Watering             Today: 0/8h  Week: 32/48h   Off: Friday     [ + Add ] │
│    Reason: Exact staff type match, same supervisor crew, worked at this site last week                 │
│                                                                                                        │
│  ★ Bashir M. (G1B) • Gardener Helper             Today: 0/8h  Week: 40/48h   Off: Sunday     [ + Add ] │
│    Reason: Same grade group (G1), same supervisor crew                                                 │
│                                                                                                        │
│  ⚠ Farooq Khan (G1A) • Hand Watering             Today: 8/8h  Week: 48/48h   Off: Wednesday  [ + Add ] │
│    Warning: Rest Day Today (OT applies) • Over standard weekly hours                                   │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ [Cancel]                                                                         [ Save Slot Roster ]  │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 6.1 Modal Components & Behaviors
1. **Target Slot Context**: Displays Worksite, Item Code, Staff Grade, Target Weekday/Date, Required Staff Count, and Shift Hours.
2. **Monthly & Quarterly In-Modal Cadence Selector (Option B)**:
   - For **Monthly items** (`frequency_unit == "MONTH"`):
     - Displays multi-select week checkboxes: `[ ] Week 1   [ ] Week 2   [ ] Week 3   [ ] Week 4`.
     - Planners choose which week(s) of the month this visit recurs on (e.g. Week 1 Monday and Week 3 Monday for 2x/month).
     - In the Base Planner grid cell, assigned chips show their cadence prefix: `W1: Ali`, `W3: Ali`.
   - For **Quarterly items** (`frequency_unit == "QUARTER"`):
     - Displays `Target Month: [ Month 1 | Month 2 | Month 3 ]` and `Target Week: [ Week 1 | Week 2 | Week 3 | Week 4 ]`.
     - In the Base Planner grid cell, assigned chips show `M1-W2: Ali`.
3. **Explicit Day-by-Day Storage (Zero Overwrite Bug)**:
   - Every day is stored explicitly as `MON`, `TUE`, `WED`, `THU`, `FRI`, `SAT`, `SUN`.
   - The button `[ Fill Across Active Days ]` is strictly a convenience action that copies the chosen crew into Mon–Sat.
   - Editing Sunday, Friday, or any day individually afterwards **never drops, overwrites, or clears other days**.
4. **Base Planner Quota Enforcement (No Excess Allowed)**:
   - If a contract line item specifies $K$ occurrences, the Base Planner permits at most $K$ active day slots.
   - When all $K$ slots are assigned, assigning another day is blocked with:
     > *Contract limit reached ($K$ of $K$ days planned). Remove an assigned day first to reallocate.*
5. **No Hallucinated Header Labels or Site Off Restrictions**:
   - All weekday columns (`MON` to `SUN`) are plain, standard headers without "Rest-Day Shift" or similar labels.
   - Sunday is fully enabled and assignable. No "Site Off" labels.
   - Scheduled days from contract imports are treated strictly as visual recommendation guidance.
6. **Supervisor Crew Filter Toggle & 3-Tier Candidate Ranking**:
   - In-modal toggle `☑ Filter to Supervisor's Crew` can be unchecked to immediately search all workers company-wide.
   - Candidates are ranked strictly by:
     1. **Tier 1: Same Staff Grade Description** (exact matching role label, starred with `*`).
     2. **Tier 2: Same Staff Grade** (matching base grade group, e.g. `G1`, `G2`).
     3. **Tier 3: Same Supervisor Group / Crew`.
7. **Action Buttons**: Clear **Save** and **Cancel** buttons.

---

## 7. Operational Planner: Leave Gaps, Overrides, Staging & Quotas

### 7.1 Precedence Waterfall & Shift Labeling
On any calendar date $D$, effective cell staffing is computed via strict precedence:
1. **Approved Worker Leave**: If a base blueprint worker is on approved leave on Date $D$, the worker is suppressed and the slot renders as **`TO_BE_COVERED`** (dashed amber border).
2. **Operational Overrides / Covers (`display_type: OVERRIDE`)**: When a replacement worker is assigned to cover an absent or leave gap worker, they render with **Solid 100% opacity** and badge **`Cover`** (indigo).
3. **Direct Shifts (`display_type: DIRECT`)**:
   - Within contract quota: renders with **Solid 100% opacity** and badge **`Additional`** (emerald).
   - Exceeding contract quota: renders with **Solid 100% opacity** and badge **`Excess`** (purple).
4. **Base Blueprint (`display_type: BLUEPRINT`)**: Regular recurring workers present and working render with **Muted 40–50% opacity**.

### 7.2 Calendar Month & Calendar Quarter Quota Aggregation
- **Monthly Items (`frequency_unit == "MONTH"`)**:
  - Quotas are evaluated over the **full calendar month** ($\text{1st of month}$ to $\text{last day of month}$).
  - All visits across all weeks of the month (template blueprint visits + operational shifts) are aggregated.
  - Viewing any individual week reflects the cumulative monthly progress (e.g. `1 / 1 month visits` if scheduled in Week 4). Adding an extra visit in any week immediately evaluates as visit #2, correctly tagging it as **`+1 Excess`**.
- **Quarterly Items (`frequency_unit == "QUARTER"`)**:
  - Quotas are evaluated across the **entire 3-month calendar quarter**.
- **Weekly Items (`frequency_unit == "WEEK"`)**:
  - Quotas are evaluated across the 7-day Monday–Sunday ISO week.

### 7.3 Operational Action Modal: Full Staging Workspace
The Operational Planner modal functions as an atomic staging workspace:
1. **Multi-Worker Selection**: Planners can select and add multiple candidate workers in one modal session.
2. **Staged Actions**:
   - Removing an existing shift stages it for cancellation (red strike-through with Undo).
   - Replacing a blueprint worker stages a replacement cover (`Cover for [Worker]`).
   - Adding extra workers stages them as `Additional`.
   - Each added worker includes an editable shift duration (hours) and an optional note/reason.
3. **Atomic Commit**:
   - `[Cancel]` or `[✕]` discards all staged changes without database mutation.
   - `[Save Operational Roster]` executes all deletions and additions atomically, then triggers a silent background refresh retaining scroll position.

### 7.4 Reason & Note Visibility
- **Grid Cell**: If a shift has an `override_reason` / note, a subtle note icon is rendered on the chip and the full note appears in the hover tooltip (`title={`${worker_name} • Note: ${reason}`}`).
- **Modal Workspace**: The note is displayed directly beneath each assigned worker card.

---

## 8. Weekday Normalization & Rest-Day Precision
- Worker rest days in the database (`employees.weekly_off_day`) store uppercase full names (e.g. `"FRIDAY"`, `"SUNDAY"`).
- Grid columns and weekday masks use 3-letter codes (`"MON"`, `"TUE"`, ..., `"SUN"`).
- Normalization matches via `isSameWeekday(offDay, weekdayCode)`:
  - Auto-fill across active working days (Mon–Sat) reliably skips the worker's rest day (e.g. Friday is skipped for workers with `"FRIDAY"` off).
  - Candidate cards and grid chips reliably render the amber `⚠ Rest Day (FRI)` warning.

---

## 9. Base Planned Worker Operational Removal (Red Slot with Reason)

### 9.1 Data Model & Persistence
- Base blueprint recurring shifts originate from `base_roster_templates`.
- When an operational user removes a base worker for a single calendar date without assigning a cover worker:
  - An operational record is saved in `scheduled_work` with:
    - `employee_id = base_worker_id`
    - `work_date = target_date`
    - `job_item_id = item.id`, `worksite_id = item.worksite_id`
    - `status = "CANCELLED"`
    - `source = "OVERRIDE"`
    - `override_reason = <reason>` (mandatory reason explaining why the base planned worker was cancelled for this date)
    - `assigned_hours = base_hours`
- Restoring the base planned worker simply deletes this `CANCELLED` record via `DELETE /api/v1/operational-planner/shifts/{shift_id}`, instantly restoring the blueprint slot.

### 9.2 Domain Rule Resolution (`resolve_operational_cell`)
- If a `CANCELLED` record exists for a base worker on that date:
  ```python
  ResolvedOperationalCellWorker(
      employee_id=base_worker_id,
      assigned_hours=base.assigned_hours,
      display_type="REMOVED",
      opacity_class="removed",
      shift_id=cancelled_shift.id,
      reason=cancelled_shift.override_reason,
      tags=["Removed"],
  )
  ```
- If all workers on a date are removed, active staff count is 0 and the visit is decremented from `quota_assigned`.

### 9.3 Visual Presentation
- **Day Cell Grid**:
  - Rendered in bold red: `bg-rose-50 border border-dashed border-rose-300 text-rose-800`.
  - Worker Name: `line-through text-rose-700`.
  - Badge: `REMOVED` (`bg-rose-700 text-white font-bold text-[8px] uppercase`).
  - Note Icon: `<FileText className="text-rose-500" />` with tooltip: `{worker_name} • Removed: {reason}`.
- **Operational Modal**:
  - Alongside `[Replace with Cover]`, an explicit `[Remove Base Shift]` action button.
  - Clicking `[Remove Base Shift]` prompts inline for the cancellation reason and stages the removal.
  - Cancelled base shifts appear under scheduled staff in a red card with `[Restore Base Worker]` to revert.

---

## 10. Worker Roster Tab Enhancements

### 10.1 Persistent Header
- `<thead>` has `sticky top-0 z-10 bg-slate-100 shadow-sm border-b border-slate-200` to remain fixed during deep vertical scrolling.

### 10.2 Exclusion of System Administrators
- Operational roster queries explicitly filter `Employee.role != "ADMIN"`, preventing system administrators and office users from appearing in the field worker schedule.

### 10.3 Work Hour Heatmap Shading
- **Weekly Total vs Standard Hours**:
  - Under Target (< 40h): Amber badge (`bg-amber-50 text-amber-800 border-amber-200`).
  - Target Met (== 40h): Emerald badge (`bg-emerald-50 text-emerald-800 border-emerald-200`).
  - Overtime (> 40h): Purple badge (`bg-purple-50 text-purple-800 border-purple-200`) with `+X.Xh OT`.
- **Daily Day Cells**:
  - Weekly Off: Neutral slate (`bg-slate-100/80 text-slate-400 font-semibold text-[10px]`).
  - Partial Shift (< 8h): Light sky tint (`bg-sky-50 text-sky-900 border-sky-200`).
  - Full Day (8h): Solid indigo badge (`bg-indigo-600 text-white font-semibold`).
  - Overtime (> 8h): Purple badge with `+Xh OT` (`bg-purple-600 text-white font-bold`).
  - Removed Shift: Soft red tint (`bg-rose-50 text-rose-700 line-through`).

### 10.4 Search, Job Filter & Supervisor Grouping
- **Search Input**: Filters workers in real-time by name, tally ID, grade, or assigned job numbers.
- **Filter by Job / Site**: Dropdown of active worksites for the week; displays only workers scheduled for the selected site.
- **Group by Supervisor**: Toggle button grouping workers under supervisor section headers with worker count and aggregated hours.

---

## 11. Week Navigation Scroll Retention & Entity Pinning

### 11.1 Scroll Retention
- Week navigation (`Prev Week`, `Next Week`, `Current Week`) uses silent data refresh (`isRefreshing = true`) without unmounting the table.
- Saves `window.scrollY` prior to data fetching and restores it immediately upon state update.

### 11.2 Entity Pinning
- **Worksites (Coverage View)**: Pin icon button `<Pin />` on each worksite card. Pinned worksites sort to the top. Persisted in `localStorage` (`fwt_pinned_worksites`).
- **Workers (Worker Roster View)**: Pin icon button `<Pin />` in each worker row. Pinned workers sort to the top. Persisted in `localStorage` (`fwt_pinned_workers`).

---

## 12. Clean Purge & Rebuild Plan

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: SPECIFICATION & DESIGN APPROVAL (Current)                                                      │
│  ✔ Light-theme enterprise UI design tokens defined (no dark mode classes)                              │
│  ✔ Unified 7-weekday matrix grid for both Base Planner and Operational Planner                         │
│  ✔ Modal click-to-assign specification with 3-tier candidate ranking and crew filter toggle             │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ STEP 2: PURGE & REBUILD FRONTEND INTERFACES                                                            │
│  ├─ Purge old dark-mode classes and replace with clean light enterprise styling                        │
│  ├─ Rebuild web/src/routes/BasePlanner.tsx as 7-weekday matrix grid matching Operational Planner        │
│  ├─ Refactor web/src/routes/OperationalPlanner.tsx to matching light styling and sticky headers        │
│  ├─ Implement click-to-assign modal with in-modal Supervisor Crew filter toggle and 3-tier ranking     │
│  └─ Verify build with npm --prefix web run build                                                       │
├────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ STEP 3: BACKEND VERIFICATION                                                                           │
│  ├─ Verify Base Planner endpoints (/api/v1/base-planner/*)                                             │
│  ├─ Verify Operational Planner endpoints (/api/v1/operational-planner/*)                               │
│  └─ Run ruff check src, lint-imports, and pytest suites                                                │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```
