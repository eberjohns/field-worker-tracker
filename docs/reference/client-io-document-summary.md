# Client "Inputs and Outputs" document - summary and reconciliation

Source: `SGS_Field_Tracker_Inputs_Outputs.docx` (in this folder). It is the client's first, business-level description (the client calls the product **SGS Field Tracker**; this pack uses the working name FWT). The requirements specification (`field_workforce_system_requirements.md`) is later and more detailed and **governs** where they disagree.

## What it asks for (outputs, section 4)
**Reports** (all exportable to Excel): Daily Attendance (Present / Partial / Absent), Employee Movement, Site Visit (worker-wise), Employee Utilization (productive vs idle or travel), Job Costing (actual vs project budget entered at setup), Payroll (basic, overtime, allowances, deductions, net pay), Transportation Time, Late Arrival / Early Departure, Project Attendance Summary (manpower per project), Pending Visits List (follow-up).
**Live monitoring**: real-time map of active staff and current location; management dashboard (today's attendance, active/offline workers, pending visits, late arrivals, overtime hours).
**Alerts**: workers (shift-start reminder, arrival/departure confirmation); supervisors/engineers (tracking interrupted, pending-visit reminders); Admin/HR (expiring Emirates ID, passport, labour card).
**Payroll output**: final monthly payroll consolidated to net salary, ready for management approval.

## Where each item lives in the pack
| Client item | Pack location |
|---|---|
| Ten reports | `12-reports.md` sections 2-3 (traceability table with intent) |
| Excel export for all reports | `12-reports.md` section 1, BR-RP-01 |
| Real-time map, dashboard | `12-reports.md` section 4, `10-ui-views.md` 3.13, `08-api-spec.md`, ADR-006 |
| Alerts | `12-reports.md` section 5, `09-mobile-sync-contract.md` section 6 |
| Net pay | `06-payroll-and-cost.md` (no deductions in v1), DEC-30 |
| Project budget | `06-payroll-and-cost.md` section 6 (calculated from job items), optional override on `Worksites`, DEC-29 |
| Pending visit follow-up | `12-reports.md` 3.10, `05-attendance-engine.md` 6c, DEC-32 |

## Differences from the requirements specification (to confirm with the client)
| Topic | Inputs/Outputs document | Requirements spec | Pack handling |
|---|---|---|---|
| Checklists | Engineers/Supervisors create, workers complete | "Checklist functionality is not included" | Out of scope; **client confirmed not needed** (DEC-40) |
| Roles | Admin, Engineer, Supervisor, Worker | adds Superintendent; Admin creates sites; Engineer approves | Requirements govern |
| Shift start/end | Worker confirms start/end **and** accommodation geofence records it automatically | Accommodation events; no manual clock events unless approved | Automatic only; **client confirmed** (DEC-40) |
| Worker login | OTP or username/password | account setup/reset handled securely | Activation code + PIN/password (DEC-15); OTP possible |
| Employee documents | Employee details include identification document numbers; alerts name Emirates ID, passport, labour card | Validity dates only; Visa, Passport, Emirates ID, optional Driving Licence | Dates only; **Labour Card added** as a type (DEC-33) |
| Payroll report | includes deductions and net pay | components and OT; insufficient hours never reduce salary | Client later confirmed **no deductions**: net pay = gross pay (DEC-30) |
| Job costing budget | "approved labour cost estimate" entered by Operations at setup | "budget where maintained" | Budget per contract, **calculated from job items** (manual override optional) (DEC-29) |
| Utilization | productive vs idle or travel time | "employee utilization report" (undefined) | Productive / travel / idle split (DEC-28) |
| Live location | "real-time map" of current location | event-based tracking | Near-real-time last known position (DEC-31) |
