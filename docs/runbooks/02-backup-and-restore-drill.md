# Runbook 02 - Database Backup, PITR and Restore Drill

## 1. Overview and Recovery Objectives
Per **docs/14-nonfunctional.md (Section 5)** and **ADR-009**, Field Worker Tracker maintains point-in-time recovery and snapshot backups inside the sovereign jurisdiction of the United Arab Emirates.

| Metric | Target SLA | Description |
|---|---|---|
| **RPO (Recovery Point Objective)** | <= 15 minutes | Maximum allowable data loss window in an unrecoverable failure |
| **RTO (Recovery Time Objective)** | <= 4 hours | Maximum allowable time to restore full operational service |
| **Drill Frequency** | Quarterly | Mandatory documented restore drill every calendar quarter |

---

## 2. Backup Architecture & Policies
- **Managed Database**: Azure Database for PostgreSQL Flexible Server in `UAE North` (Dubai).
- **Point-in-Time Recovery (PITR)**: Transaction logs (WAL) continuously streamed to geo-redundant storage with 35-day retention.
- **Geo-Redundant Backup Copy**: Secondary backup repository located in `UAE Central` (Abu Dhabi). No customer personal data leaves the UAE.
- **Encryption**: Backups encrypted at rest using AES-256 with customer-managed keys (CMK) in Azure Key Vault.

---

## 3. Quarterly Restore Drill Procedure
Every quarter, the infrastructure engineer conducts a disaster recovery drill to verify backup integrity and measure actual RTO against the 4-hour SLA.

### Automated Drill Tool
The repository provides an automated drill harness at `tools/backup_restore_drill.py`.

```bash
uv run --project backend python tools/backup_restore_drill.py
```

### Manual Drill Steps (Production Cloud)
1. In Azure Portal / CLI, create a restored server from the latest restore point:
   ```bash
   az postgres flexible-server restore \
     --resource-group rg-fwt-prod-uaenorth \
     --name fwt-pg-drill-scratch \
     --source-server fwt-pg-prod-flexible \
     --restore-time "2026-11-16T10:00:00Z"
   ```
2. Connect to the scratch database instance:
   ```bash
   psql "postgresql://fw_migrator@fwt-pg-drill-scratch.postgres.database.azure.com:5432/fw_db"
   ```
3. Run data parity verification:
   - Check row counts for `employees`, `worksites`, `mobile_event_logs`, `attendance_records`, `payroll_runs`, `audit_logs`.
   - Verify PostGIS geometry validity:
     ```sql
     SELECT count(*) FROM worksites WHERE boundary IS NOT NULL AND NOT ST_IsValid(boundary);
     ```
   - Verify Alembic migration head:
     ```sql
     SELECT version_num FROM alembic_version;
     ```
4. Record elapsed time from trigger to verification completion.
5. Destroy scratch instance:
   ```bash
   az postgres flexible-server delete --resource-group rg-fwt-prod-uaenorth --name fwt-pg-drill-scratch --yes
   ```

---

## 4. Phase 13 Recorded Restore Drill Result
The Phase 13 pre-go-live restore drill was executed on **2026-11-16**.

| Check | Expected | Actual Result | Status |
|---|---|---|---|
| **Backup Generation** | Successful dump | 0.45s (2.1 MB) | **PASS** |
| **Restore Duration (RTO)** | < 14,400s (4h) | **4.49s** | **PASS** |
| **Data Parity (Employees)** | 315 rows | 315 rows (100% matched) | **PASS** |
| **Data Parity (Worksites)** | 4 rows | 4 rows (100% matched) | **PASS** |
| **Data Parity (Audit Logs)** | 5,650 rows | 5,650 rows (100% matched) | **PASS** |
| **Data Parity (Archive Records)** | 4 rows | 4 rows (100% matched) | **PASS** |
| **PostGIS Spatial Integrity** | 0 invalid | 0 invalid geometries | **PASS** |
| **Alembic Schema Version** | `0014_archive...` | `0014_archive_and_retention` | **PASS** |
| **Overall Assessment** | Full Recovery | **SUCCESSFUL** | **PASS** |

The full machine-readable verification record is stored at `docs/runbooks/restore_drill_record.json`.
