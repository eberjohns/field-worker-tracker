# D4 - Month-end payroll, approvals and the Generated Reports section

Users: Admin (run, re-run, approve), Engineers (read in scope), all roles (operational reports). Rules: `06-payroll-and-cost.md`, `12-reports.md`.

## Timeline
```
Month ends (31 Oct)  ->  +5 days (setting)  ->  DRAFT run + reports  ->  Admin reviews / re-runs  ->  Admin APPROVES  ->  final reports stored
                         phones keep uploading                           (picks up everything uploaded so far)       later uploads ignored for this month
```
1. **Automatic draft** `payroll_auto_run_delay_days` after month-end: payroll draft for the previous calendar month and the month-end reports (listed in 12 section 7). Admins and Engineers get an in-app notification.
2. **Draft page**: totals; an **Issues** panel (attendance rows still pending review - overtime not yet approved; workers without a salary structure; missing standard hours; workers with events but no assignment); records table per worker with the numbers behind each figure.
3. **Re-run**: Admin can re-run any number of times before approval; each run replaces the draft, earlier drafts kept in history with the time they ran.
4. **Approve**: Admin confirms (dialog shows totals and unresolved issues). The system writes immutable per-worker snapshots, locks the month's attendance versions, generates the final reports (a new version) and marks the run APPROVED. Approved runs are read-only.
5. **After approval**: events that arrive later are stored and visible in attendance but are **ignored for that month's payroll**. Abnormal cases are handled outside the system.
Workers then see their own approved payroll in the app.

## Draft page layout
```
Payroll - October 2026 (AE)   DRAFT run 2   generated 6 Nov 09:00     [Re-run] [Approve]
Totals: workers 148 | gross 245,310.00 | OT1 312 h | OT2 40 h | final total staff cost 612,408.30
Issues (3): 2 attendance rows pending overtime review | 1 worker without salary structure
Worker | Std h | Salary portion | OT1 h/amt | OT2 h/amt | Gross | Gratuity | Leave sal | Provisions | Per-month prov | Total staff cost | HR OH 5% | Final total staff cost
```
Clicking a worker opens the breakdown and the daily attendance rows that produced the overtime.

## Generated Reports section
```
Generated reports   Report [All]  Period [All]  Country [AE]  Kind [Month-end|On demand]
Name                                                          Period   Version  Generated          By      Visible to
FieldWorkerTracker_Payroll-Cost_AE_2026-10_generated-2026-11-06.xlsx   2026-10  v2      6 Nov 09:00        system  Admin, Engineers
FieldWorkerTracker_Daily-Attendance_AE_2026-10_generated-2026-11-06.xlsx 2026-10 v1     6 Nov 09:00        system  all in scope   [Download]
```
- Every month-end and on-demand file is kept; **nothing is overwritten**; re-generations get a new version. Filter, search by name, download again at any time.
- Name pattern: `<Company>_<Report>_<Country>_<Period>_generated-<date>.xlsx`.
- Visibility: operational reports for Admin, Engineers, Superintendents and Supervisors in scope; payroll, provisions-staff-cost and job-costing for Admin and Engineers only.
- On-demand report runs (with filters) are also saved here.

## Job budget vs actual
In Payroll and Cost: per worksite the **contract budget** (from the revision file and job items, manual override optional), cumulative actual, pro-rated budget, variance; the note explains budget provisions come from the revision file and actual from company settings.

## Acceptance
Draft appears automatically on the configured day; re-run changes figures when new events are uploaded; approval locks and snapshots; later events do not change the approved run; every report file listed, named correctly and re-downloadable; visibility rules enforced.
