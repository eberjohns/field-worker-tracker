# 020 - Month-End Payroll, Salary Revisions, and Dynamic Job Budget
Status: Accepted
Date: 2026-11-14

## Context
Phase 11 introduces month-end payroll calculation, salary revisions management, immutable payroll snapshots, and contract labor budgeting. Previously (Phase 08), attendance was calculated on a daily basis. The system required:
1. Automated monthly draft generation (`payroll_auto_run_delay_days`, default 5 days post month-end).
2. Explicit draft re-runs (incrementing `run_no`), unapproved overtime detection in issues panels, and Admin approval locking attendance records.
3. Salary revisions with side-by-side diff previews and template exports.
4. Dynamic worksite contract budget computation linked to salary revision codes, with actual cost allocation from attendance.
5. Role scoping: Administrators manage and approve; Engineers view within scope read-only; Supervisors receive 403.
6. Worker-facing approved payroll slips for mobile (`/payroll/my-records`), exposing employee pay while withholding employer provisions.

## Options Considered
1. **Compute payroll on-the-fly dynamically without snapshotting:** Rejected. Financial records must be immutable for audit and legal compliance. Later changes to attendance or settings must never alter approved pay.
2. **Hardcode revision rates onto worksite items:** Rejected. Contracts are renewed and tenders re-priced. Worksites must bind dynamically to revision codes.
3. **Expose employer statutory provisions on mobile slips:** Rejected. Gratuity accrual, leave salary provisions, company provisions, and 5% HR OH are employer-side staff costs and must not be visible to field workers.

## Decision
1. **Pure Business Logic (`fw.rules.payroll`):**
   - Standard 208-hour monthly divisor (26 days × 8 hours).
   - OT1 Rate = `(basic / 208) * 1.25` (hours worked beyond standard hours on normal working days).
   - OT2 Rate = `(basic / 208) * 1.50` (all hours worked on public holidays and worker's weekly off day).
   - Missed Hours Deduction = `missed_hours * (basic / 208)`. Paid leaves incur zero deduction.
   - Gratuity Provision = `(basic / 30) * (21 / 12)`.
   - Leave Salary Provision = `((basic + housing) / 30) * (30 / 12)`.
   - Five Company Provisions (Visa, Air Ticket, Uniform, Medical, Accommodation).
   - 5% HR Overhead added to Total Staff Cost for Final Staff Cost.
2. **Draft & Approval Lifecycle (`fw.modules.payroll`):**
   - Background check triggers draft runs 5 days after month-end.
   - Draft re-run increments `run_no` and picks up newly approved overtime.
   - Approval freezes `payroll_records` with immutable snapshots and sets `locked = True` on `attendance_records`.
3. **Dynamic Job Budget & Revision Binding:**
   - Worksites store `salary_revision_code` (or fallback to country active revision).
   - Budget Report states the provision basis difference: budget uses revision commercial provisions; actual uses dynamic company settings.
4. **Mobile Endpoint (`GET /payroll/my-records`):**
   - Returns approved slips containing only employee pay components, worked hours, OT amounts, and net pay.

## Why
- Fully satisfies UAE/GCC statutory labor standards (208 divisor benchmark: Basic $1,100 -> OT1 $6.61, OT2 $7.93).
- Ensures tamper-proof audit trails for historic payroll months.
- Enables seamless annual contract budget repricing upon revision updates.

## Consequences
- Attendance calculations for a locked month cannot be recomputed unless an admin unlocks the run.
- Changes to grade salary revisions do not alter previously approved payroll runs.
- Mobile contract adds `/payroll/my-records` without changing existing sync schemas.

**Related ADRs:** ADR-001 (Modular Monolith), ADR-008 (Effective Configuration), ADR-013 (Salary Structures), ADR-018 (Attendance Immutability).  
**Affected Docs:** `docs/06-payroll-and-cost.md`, `docs/07-data-model.md`, `docs/08-api-spec.md`, `docs/decisions/decision-register.md`.
