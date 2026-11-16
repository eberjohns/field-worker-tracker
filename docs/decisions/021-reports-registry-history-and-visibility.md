# 021 - Reports Registry, Month-End Archive, and Role Visibility
Status: Accepted
Date: 2026-11-16

## Context
Phase 12 delivers the system-wide reporting subsystem, background export infrastructure, and historical generated reports archive:
1. Catalog of reports per `docs/12-reports.md` (15 active reports; `driver-run-sheet` omitted as transport is inactive).
2. Export formats: XLSX for all reports, CSV for tabular data, and PDF for daily attendance and payroll sheets.
3. Automated month-end report generation (11 reports) upon draft payroll creation and approval per active country.
4. Generated Reports archive (`/reports/generated`): persistent file storage, immutable versioning, SHA-256 verification, and re-download capability.
5. Strict role permissions: Salary and cost reports (`payroll`, `provisions-staff-cost`, `job-costing`) must be accessible to Admin only.

## Options Considered
1. **Synchronous File Generation for All Exports:** Rejected. Large multi-site export queries risk HTTP gateway timeouts. Long exports run asynchronously through `report_exports` with polling (`GET /exports/{id}`).
2. **Allow Engineers Access to Salary and Cost Reports:** Rejected. User explicitly instructed that salary, provision, and project costing reports are strictly ADMIN only (Engineers, Superintendents, and Supervisors receive 403 Forbidden).
3. **Overwrite Existing Report Files on Re-Run / Approval:** Rejected. DEC-46 mandates that every generated file is kept immutably; subsequent generations increment `version_no` and record status (`DRAFT` vs `APPROVED`).
4. **Direct Import from Payroll to Reports:** Rejected. Violates modular monolith layer contracts (`reports` is at the top layer). Inter-module orchestration uses `event_bus` domain events (`PayrollRunCreated`, `PayrollRunApproved`).

## Decision
1. **Registry Pattern (`fw.modules.reports.registry`):** Centralizes all 15 report definitions, column types, allowed roles, filter schemas, and format mappings.
2. **File Storage Port (`fw.adapters.storage`):** Pluggable `FileStoragePort` protocol with `LocalStorageAdapter` implementing path sanitization and SHA-256 digest validation.
3. **Domain Event Orchestration:** Payroll dispatches `PayrollRunCreated` and `PayrollRunApproved`; reports module listens asynchronously and generates the month-end package.
4. **File Naming & Archive (DEC-46):** `<Company>_<Report>_<Country>_<Period>_generated-<datetime>.xlsx`, suffixed with `_APPROVED` for final approved runs.
5. **Excel Standard:** Single header row, ISO dates, numeric formatting, no merged data cells, and a dedicated "Filters" worksheet.
6. **Frontend Hub & Archive:** Integrated Reports Hub (`/reports`) and Generated Reports archive (`/reports/generated`) with live download helpers.

## Why
- Guarantees strict confidentiality of workforce financial data and employer provisions.
- Ensures non-blocking performance for large tabular exports.
- Provides tamper-evident audit history for all monthly attendance, labor allocation, and payroll packages.

## Consequences
- Archive files cannot be deleted or mutated once created.
- Background exports can be monitored and re-downloaded seamlessly.

**Related ADRs:** ADR-001 (Modular Monolith), ADR-005 (Immutable Events), ADR-018 (Attendance Immutability), ADR-020 (Month-End Payroll).  
**Affected Docs:** `docs/12-reports.md`, `docs/07-data-model.md`, `docs/08-api-spec.md`, `docs/10-ui-views.md`, `docs/decisions/decision-register.md`.

