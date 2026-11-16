# Runbook 05 - Administrator Operations Guide

## 1. Overview
This guide provides step-by-step operating instructions for System Administrators and HR Directors responsible for managing data archives, retention policies, Data Subject Access Requests (DSAR), and privacy consent controls in Field Worker Tracker.

---

## 2. Yearly Archive Execution & Verification

### Purpose & Schedule
Per **DEC-38** and **docs/14-nonfunctional.md**, raw location events (`mobile_event_logs`), raw site visits, and tracking gaps from previous calendar years must be archived and purged once the financial/payroll year is closed. Daily attendance summaries, monthly payroll snapshots, and audit logs are retained live for 7 years.

### Step 2.1: Trigger Archive Package Creation
1. Navigate to **Admin Settings** > **Archive & Retention** in the React Dashboard (or execute via API).
2. Enter the calendar year to archive (e.g. `2024` or `2025`).
3. Click **"Run Yearly Archive"**.
4. The backend:
   - Queries all raw mobile event logs and derived site visits/gaps for the specified year.
   - Serializes records to JSON.
   - Encrypts the payload using **AES-256-GCM** (PyCA cryptography) with a unique 96-bit nonce and 16-byte authentication tag.
   - Computes the **SHA-256 checksum** of the encrypted artifact.
   - Stores the encrypted archive file (`archives/archive_{year}_{timestamp}.enc`) on disk and registers metadata in `archive_records`.

### Step 2.2: Download and Store Offsite Copy
1. In the **Archive Records & Yearly Packages** table, locate the newly generated archive.
2. Click **"Download Encrypted Package"**.
3. Move the downloaded `.enc` package to secondary enterprise cloud storage (e.g. Azure Blob Storage with immutability policy enabled).

### Step 2.3: Verify Archive Integrity
Before purging data from the live database, verify that the encrypted file has not been corrupted and can be decrypted:
1. Click **"Verify Checksum & Integrity"** in the UI.
2. The system recalculates the SHA-256 hash against disk, decrypts the first payload sample using the encryption key, and confirms the status as `VERIFIED`.

### Step 2.4: Execute Year Purge
1. Once verified, click **"Purge Live Records"** (requires Admin confirmation).
2. The system executes a transactional purge with `SET LOCAL fwt.bypass_immutability = 'on'`, safely purging historical raw events, visits, and gaps for that calendar year while logging the event in `audit_logs`.

---

## 3. Statutory Retention Purge Procedure

### Policy Schedule
- `sync_changes`: Purged after **60 days**.
- `notification_logs` / `alerts`: Purged after **6 months** (resolved/dismissed alerts only).

### Execution Steps
1. Navigate to **Admin Settings** > **Archive & Retention** > **Statutory Data Retention**.
2. Review retention parameters (default: 60 days for sync changes, 6 months for notification logs).
3. Click **"Run Retention Purge"**.
4. The system executes the purge and displays the total number of deleted transient records.

---

## 4. Terminated Worker Anonymisation

### Legal Rationale (UAE Labour Law)
Under UAE labour regulations, employee records must be retained for at least 2 years post-termination. After 2 years, terminated employees must be anonymised to comply with data minimisation principles under UAE PDPL.

### Anonymisation Mechanics
When anonymised:
- `phone`, `email`, and emergency contacts are set to `NULL`.
- `name` is replaced with `Anonymised Worker ({tally_id})`.
- Associated employee document attachments are cleared.
- Attendance hours, payroll amounts, and operational cost history remain intact for statutory reporting.

### Execution Steps
1. In **Admin Settings** > **Archive & Retention** > **Terminated Worker Anonymisation**:
2. Set threshold (default: 2 years).
3. Click **"Anonymise Inactive Workers"**.

---

## 5. Employee DSAR Export (Data Subject Access Request)

When an employee requests a copy of all personal data held by the organisation:
1. Navigate to **Employees & People** > select the employee profile.
2. In the top action bar, click **"Export DSAR (.xlsx)"**.
3. The system generates a comprehensive, multi-sheet Excel workbook containing:
   - **Sheet 1: Employee Profile**: Names, IDs, roles, contact info, join dates.
   - **Sheet 2: Consent History**: All recorded consent acceptances and policy versions.
   - **Sheet 3: Documents**: Visa, passport, labor card records.
   - **Sheet 4: Attendance Summary**: Daily shift hours, regular hours, overtime.
   - **Sheet 5: Payroll Slips**: Approved gross pay, deductions, net salary.
4. Deliver the exported file securely to the requesting employee.

---

## 6. Worker Tracking Consent Withdrawal

If an employee revokes consent for location tracking:
1. **Via Mobile App**: The worker can tap "Withdraw Tracking Consent" in settings.
2. **Via Web Dashboard (Admin/HR)**:
   - Open **Employee Detail**.
   - Click **"Withdraw Consent"**.
   - Enter reason for withdrawal.
3. Once withdrawn:
   - The employee's consent status becomes `WITHDRAWN`.
   - All subsequent mobile location batch uploads from this worker will immediately be rejected with **HTTP 403 CONSENT_WITHDRAWN**.
   - An alert is automatically published to system administrators.
