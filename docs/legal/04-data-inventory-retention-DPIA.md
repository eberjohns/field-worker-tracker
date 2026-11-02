# Data inventory, proposed retention and DPIA (DRAFT)

For counsel/DPO review. Keep this updated when features change.

## 1. Data inventory (record of processing)
| Data | Source | Purpose | Basis (to confirm) | Who accesses | Stored where | Proposed retention |
|---|---|---|---|---|---|---|
| Name, worker ID, role, grade label, weekly off day, accommodation | Import / Admin | Scheduling, payroll, access control | Contract / legal obligation | Admin; scope roles read | Primary DB | Employment + 7 years |
| Reporting links (who reports to whom) | Import / Admin | Access scope, approvals | Legitimate interest | Admin | Primary DB | Employment + 7 years |
| Salary structure (basic, allowances, standard hours) | Import | Payroll | Contract / legal obligation | Admin, Engineers (scope), the worker (own) | Primary DB | 7 years |
| Document validity dates (visa, passport, Emirates ID, labour card, licence) | Import / Admin | Expiry alerts, legal compliance | Legal obligation | Admin; scope roles read | Primary DB | Employment + 2 years minimum |
| Schedule, leave, reassignments | Planner | Operations | Contract | Scope roles | Primary DB | 7 years |
| **Location events** (coordinates, accuracy, time, event type) | Worker's phone | Attendance, pay, verification | Consent / contract (to confirm) | Scope roles; every view logged | Primary DB then encrypted archive | 13 months live; then archive for a fixed period [to decide]; then delete |
| Attendance records and versions, comments, approvals | Derived | Payroll, disputes | Legal obligation | Scope roles | Primary DB | 7 years |
| Payroll snapshots, month-end reports | Derived | Payroll, audit, tax | Legal obligation | Admin, Engineers (scope) | Primary DB / report store | 7 years |
| Device info (model, OS, app version), push token | Phone | Account security, sync | Legitimate interest | Admin | Primary DB | While device active + 1 year |
| Consent records | Phone | Evidence | Legal obligation | Admin | Primary DB | Employment + 7 years |
| Audit logs | System | Security, accountability | Legitimate interest | Admin | Primary DB | 7 years |

Not collected: document numbers or scans, photos, messages, contacts, location outside working time.

## 2. Proposed retention schedule
| Item | Live system | Then |
|---|---|---|
| Raw location events | 13 months | Encrypted yearly archive for [N] years (propose 5), then permanent deletion; legal-hold exception |
| Attendance, payroll, reports | 7 years | Anonymise personal fields, keep aggregates |
| Sync history | 60 days | Delete |
| Notifications, report exports | 6 months | Delete |
| Closed employees | End of employment + 2 years minimum (UAE labour law) | Anonymise at retention expiry |
The client wishes to keep location and attendance records permanently; this conflicts with storage limitation and must be agreed with counsel.

## 3. DPIA (draft)
**Processing:** continuous-purpose location tracking of field workers during working hours for attendance and payroll, with supervisor visibility and live map.
**Necessity and proportionality:** needed to verify presence at sites and calculate hours and overtime for ~300 workers; less intrusive means (manual timesheets) are error-prone. Mitigations keep intrusion minimal: only during working hours, positions on geofence events and periodic checks (about every 5 minutes) rather than continuous GPS, no tracking off duty.
**Risks and mitigations**
| Risk | Mitigation |
|---|---|
| Tracking outside working hours | Tracking starts at alarm stop and ends with the day; app stops when consent is withdrawn |
| Excess retention of location history | Retention schedule, yearly archive and deletion/anonymisation |
| Unauthorised internal access (supervisors browsing workers) | Scope-based access, view logging, periodic access review |
| Misuse for discipline beyond purpose | Policy limiting use to attendance, pay and safety; review by engineers; comments logged |
| Data breach (location + salary data) | Encryption, access control, device binding, backups, breach runbook (72 h) |
| Inaccurate location causing unfair pay outcomes | Server verification, flags for low accuracy, human review, draft payroll approval |
| Cross-border transfer (backups, providers) | In-country storage and backups; transfers only with a legal basis |
| Workers not understanding the notice | Plain-language notice in workers' languages |
**Residual risk:** moderate; acceptable if the human actions in `01-human-actions.md` are completed.
**Review:** at go-live, after the pilot, annually, and whenever tracking behaviour changes.
