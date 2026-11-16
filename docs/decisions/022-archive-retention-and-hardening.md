# 022. Yearly Archive, Data Retention, Privacy Tooling and Operational Hardening

- **Status:** Accepted
- **Date:** 2026-11-16
- **Context:** Resolves DEC-38, DEC-55, DEC-56. Pertains to Phase 13 hardening, disaster recovery, data protection, and statutory compliance.

## Context
Under UAE and Saudi data protection regulations (UAE PDPL, KSA PDPL) and labor laws:
1. High-frequency raw location pings (`mobile_event_logs`) represent sensitive personal data and rapidly grow in volume (~22 million events/year for 500 workers, ~5-6 GB/year). Retaining them indefinitely violates statutory data minimization and storage limitation mandates.
2. Conversely, payroll runs, attendance summaries, and financial reports must be preserved for statutory audit windows (7 years).
3. Employees have legal rights to withdraw location tracking consent, access full personal records (Data Subject Access Requests - DSAR), and request data minimization upon contract termination (> 2 years post-service).
4. System disaster recovery requires verifiable Point-in-Time Recovery with an RTO <= 4 hours and RPO <= 15 minutes, proven by regular restore drills.

## Options Considered
1. **Database Table Partitioning with Automated Drops**:
   - *Pros*: Simple SQL DDL operations.
   - *Cons*: Drops data without creating verifiable, encrypted external archives; does not allow offsite compliance storage or sample verification prior to deletion.
2. **Plain Unencrypted JSON/CSV Dumps**:
   - *Pros*: Easy to inspect.
   - *Cons*: Violates privacy security controls; unencrypted location trails stored on disk or transferred offsite constitute an immediate breach risk.
3. **AES-256-GCM Encrypted Yearly Archive with SHA-256 Checksums and Admin Verification** (Chosen):
   - Structured JSON export of previous calendar year raw events, site visits, and tracking gaps.
   - Encrypted with AES-256-GCM (PyCA cryptography) utilizing a unique 96-bit nonce and 16-byte authentication tag per package.
   - Recorded with SHA-256 checksums in `archive_records`.
   - Admin UI workflow: Create Archive -> Download Encrypted Copy -> Verify Integrity & Decryption -> Purge Live Records.

## Decision
1. **Yearly Archive Engine**:
   - Implemented in `backend/src/fw/modules/archive/`.
   - Raw events, visits, and tracking gaps are archived by calendar year.
   - Purge executes with `SET LOCAL fwt.bypass_immutability = 'on'` within a single transaction, preserving immutability triggers against accidental deletes.
   - Daily attendance summaries, monthly payroll snapshots, and audit logs are retained live for 7 years.
2. **Statutory Retention Purge**:
   - Transient `sync_changes` are purged after 60 days.
   - Resolved alerts and notification logs are purged after 6 months.
3. **Worker Privacy & Consent**:
   - Terminated employees inactive for > 2 years are anonymised (personal fields set to NULL, name replaced with `Anonymised Worker ({tally_id})`).
   - Worker consent withdrawal is supported via mobile API (`POST /api/v1/mobile/consent/withdraw`) and Admin dashboard.
   - Subsequent event batches from withdrawn workers are rejected with `HTTP 403 CONSENT_WITHDRAWN`.
   - Full DSAR Excel export package generated via `/api/v1/employees/{id}/export-dsar`.
4. **Disaster Recovery & Tooling**:
   - Automated drill tool `tools/backup_restore_drill.py` verifies backup dump, restore to scratch DB, table parity, and PostGIS geometry validity.
   - Recorded RTO: 4.49 seconds (well within the 4-hour SLA).

## Consequences
- **Positive**: Strict regulatory compliance with UAE and KSA data protection laws; storage footprint stabilized; disaster recovery verified; worker privacy controls enforced.
- **Negative / Operational**: Administrators must execute the yearly archive workflow after year-end payroll finalization and store the encrypted `.enc` file in secondary immutable cloud storage.
- **Links**:
  - `docs/14-nonfunctional.md`
  - `docs/runbooks/01-production-deployment.md`
  - `docs/runbooks/02-backup-and-restore-drill.md`
  - `docs/runbooks/03-incident-breach-response.md`
  - `docs/runbooks/04-sync-failure-recovery.md`
  - `docs/runbooks/05-admin-operations-guide.md`
  - `docs/legal/01-human-actions.md`

