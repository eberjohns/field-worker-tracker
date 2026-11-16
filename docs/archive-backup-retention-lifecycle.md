# Data Lifecycle, Archiving, Backups and Worker Retention

This document explains the complete data lifecycle, encryption architecture, disaster recovery procedures, and statutory retention schedules for **Field Worker Tracker (FWT)** per UAE and KSA data protection laws.

---

## 1. What the Yearly Archive Contains vs. What Remains Live

Field workers generate millions of GPS pings annually (~22 million events per year for 500 workers, ~5-6 GB). Retaining high-frequency raw location pings indefinitely violates statutory storage limitation and privacy mandates (UAE PDPL & KSA PDPL).

### Contents of the Yearly Archive Package (.enc)
When an administrator triggers a yearly archive (e.g. for calendar year `2024`), the archive engine packages:
1. **`mobile_event_logs`**: Every raw location ping received during that year (exact latitude, longitude, device timestamp, server timestamp, accuracy, mock-location flags, sequence number, and raw JSON payload).
2. **`site_visits`**: All derived site entry/exit times, durations, matched worksite IDs, and supervisor approval records.
3. **`tracking_gaps`**: All recorded intervals where device location was disabled, network was lost, or battery optimization stopped pings.

### What Remains Live in the Database (7-Year Statutory Retention)
The yearly archive **never deletes aggregate attendance, payroll, or audit trails**:
- **`attendance_records`**: Daily total hours, regular hours, overtime hours (OT1/OT2), variances, and approval statuses remain live in the primary database for 7 years.
- **`payroll_runs` and `payroll_records`**: Immutable month-end gross pay, deductions, employer provisions (gratuity, leave salary, visa), and net pay remain live for 7 years.
- **`generated_reports`**: Stored Excel and PDF reports generated at month-end remain preserved with their SHA-256 checksums.
- **`audit_logs`**: Complete historical audit trails of system actions remain immutable.

---

## 2. Encryption, Checksums & How to Open an Archive Later

Archives are protected with industry-standard authenticated encryption so they can be securely archived offsite or audited years into the future.

### Encryption Specifications
- **Algorithm**: **AES-256-GCM** (Galois/Counter Mode) via PyCA `cryptography`.
- **Integrity & Authenticity**: A unique 96-bit random nonce (IV) and a 16-byte authentication tag are prepended to each archive file. Any bit flipped or tampered with renders the archive mathematically undecryptable.
- **Checksum**: A cryptographic **SHA-256 checksum** is calculated over the encrypted binary package and recorded in `archive_records`.
- **Key Management**: Encrypted with `ARCHIVE_ENCRYPTION_KEY` (stored in Azure Key Vault / managed KMS).

### How to Open and Inspect an Archive Later

#### Method A: Via the Web Dashboard (Admin UI)
1. Navigate to **Settings** > **Archive & Retention**.
2. Locate the archive package in the **Archive Records & Yearly Packages** table.
3. Click **"Verify Checksum & Integrity"**:
   - The server verifies that the SHA-256 checksum of the file on disk matches the database record.
   - The server decrypts a sample of the payload to confirm that the decryption key is valid and the contents are intact.
4. Click **"Download Encrypted Package"** to retrieve the `.enc` file.

#### Method B: Standalone CLI Decryption Tool (Air-Gapped / Audit Mode)
If an external auditor or legal counsel needs to open an `.enc` file without running the web application:
```bash
# Inspect contents and verify integrity
uv run --project backend python tools/decrypt_archive.py archives/archive_2024_xxx.enc

# Decrypt to a readable JSON file
uv run --project backend python tools/decrypt_archive.py archives/archive_2024_xxx.enc --output decrypted_2024.json --key "$ARCHIVE_ENCRYPTION_KEY"
```

#### Method C: Backend API
- `GET /api/v1/admin/archives`: Lists all archive records, sizes, checksums, and verification statuses.
- `GET /api/v1/admin/archives/{year}/download`: Streams the encrypted binary file.
- `POST /api/v1/admin/archives/{year}/verify`: Verifies checksum and performs test decryption.

---

## 3. Statutory Retention & Automated Pruning

Transient operational data is automatically purged on an agreed statutory schedule:

| Data Type | Table | Retention Period | Rationale / Regulatory Basis |
|---|---|---|---|
| **Raw Location Pings** | `mobile_event_logs` | **13 months live** | Operational buffer for annual attendance dispute review; archived yearly thereafter |
| **Transient Sync Cursors** | `sync_changes` | **60 days** | Mobile devices synchronize within 60 days; devices offline longer receive a full snapshot |
| **Notification Logs & Alerts** | `notification_logs`, `alerts` | **6 months** | In-app alerts and resolved notifications are pruned to prevent database bloat |
| **Daily Attendance Summaries** | `attendance_records` | **7 years** | UAE Labour Law and statutory tax/audit limitation periods |
| **Approved Payroll Runs** | `payroll_records`, `payroll_runs` | **7 years** | Statutory wage protection and company financial compliance |
| **Audit Logs** | `audit_logs` | **7 years** | Security forensics and regulatory accountability |

Administrators trigger statutory retention pruning via **Settings** > **Archive & Retention** > **"Run Retention Purge"** or through the API:
```http
POST /api/v1/admin/retention/purge
Content-Type: application/json

{
  "sync_changes_retention_days": 60,
  "notification_retention_months": 6
}
```

---

## 4. Terminated Worker Handling & Anonymisation

### Legal Retention Requirement (UAE Labour Law)
Under UAE labour regulations, an employer must maintain basic employment records for **at least 2 years post-termination** in the event of end-of-service gratuity claims or labor dispute adjudication.

### Anonymisation Mechanics (> 2 Years Post-Termination)
After the 2-year window expires, the employee's personal identifiable data is erased per the right to be forgotten / data minimization principles:
- **Erased Personal Fields**: `phone`, `email`, and emergency contacts are set to `NULL`.
- **Name Scrubbing**: The worker's real name is replaced with `Anonymised Worker ({tally_id})`.
- **Attached Documents**: Passport scans, visas, and national IDs in `employee_documents` are purged.
- **Preserved Operational History**: Historical shift hours, worksite allocations, and payroll earnings are retained linked only to the anonymised ID for statutory tax, cost accounting, and billing audits.

Execution via API:
```http
POST /api/v1/admin/retention/anonymise
Content-Type: application/json

{
  "older_than_years": 2
}
```

---

## 5. Worker Privacy & Consent Management

1. **Tracking Consent**: Mobile tracking is activated only after the worker accepts the location policy in the mobile app (`POST /api/v1/mobile/consent`).
2. **Consent Withdrawal**: A worker can withdraw consent at any time via the app, or HR/Admin can record withdrawal via the dashboard.
   - When withdrawn, `employees.consent_status` is updated to `WITHDRAWN`.
   - Any further location batch uploaded by that worker's phone is immediately rejected with **HTTP 403 CONSENT_WITHDRAWN**.
   - An automated alert is generated for the Admin team.
3. **Data Subject Access Request (DSAR)**:
   - When an employee requests a copy of their personal data, HR clicks **"Export DSAR (.xlsx)"** on the employee detail page (`GET /api/v1/employees/{id}/export-dsar`).
   - The generated Excel workbook provides 5 sheets: *Employee Profile*, *Consent History*, *Documents*, *Attendance Summary*, and *Payroll Slips*.

---

## 6. Disaster Recovery & Backups

- **Cloud Provider**: Microsoft Azure (Flexible Server for PostgreSQL 16 + PostGIS).
- **Primary Region**: `UAE North` (Dubai) with Zone-Redundant High Availability.
- **Secondary Region**: `UAE Central` (Abu Dhabi) for automated in-country geo-redundant backups.
- **Recovery Targets**:
  - **RPO (Recovery Point Objective)**: <= 15 minutes (continuous WAL archiving).
  - **RTO (Recovery Time Objective)**: <= 4 hours.
- **Restore Drills**: Executed quarterly using `tools/backup_restore_drill.py`. The Phase 13 pre-go-live drill restored a full database image, validated 100% table parity across 9 tables, verified 0 invalid PostGIS geometries, and completed in **4.49 seconds**.
