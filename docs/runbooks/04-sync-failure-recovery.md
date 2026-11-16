# Runbook 04 - Mobile Sync Failure & Recovery

## 1. Overview & Sync Architecture
Field Worker Tracker implements an offline-first mobile sync engine per **docs/09-mobile-sync-contract.md**.
- The server produces monotonic incrementing cursors in `sync_changes` (60-day retention).
- Mobile devices track their local cursor (`last_acked_cursor`) and poll `/api/v1/mobile/sync/changes?cursor={cursor}`.
- Upon successful local SQLite persistence, the mobile app sends `/api/v1/mobile/sync/ack`.
- Devices report location batches asynchronously via `/api/v1/mobile/events/batch` (up to 200 events).

---

## 2. Common Sync Failure Modes

| Failure Symptom | Underlying Cause | Impact |
|---|---|---|
| **Sync Stalling / Gap** | Device offline > 60 days; changes purged by retention schedule | Device receives incomplete delta history |
| **Cursor Drift / Desync** | Local SQLite database corrupted or app data cleared | Device rejects newer changes or continuously loops |
| **Batch Rejection (403)** | Worker tracking consent withdrawn or device revoked | Incoming location events rejected (`CONSENT_WITHDRAWN`) |
| **Batch Rejection (422)** | Clock skew > 120s or invalid coordinates | Device clock drifting; events rejected (`INVALID_COORDINATES`) |

---

## 3. Diagnostic Procedures

### Step 3.1: Check Device Sync Lag
Query the device's last seen timestamp and cursor progress against the server's maximum cursor:
```sql
SELECT
    d.id AS device_id,
    e.tally_id,
    e.name,
    d.platform,
    d.device_model,
    d.last_seen_at,
    d.last_acked_cursor,
    (SELECT COALESCE(MAX(id), 0) FROM sync_changes) AS latest_server_cursor,
    ((SELECT COALESCE(MAX(id), 0) FROM sync_changes) - d.last_acked_cursor) AS cursor_lag
FROM registered_devices d
JOIN employees e ON e.id = d.employee_id
WHERE d.is_active = TRUE
ORDER BY cursor_lag DESC;
```

### Step 3.2: Check Event Ingestion Errors
Inspect recent rejected events for a specific worker:
```sql
SELECT
    event_id,
    event_type,
    event_timestamp_utc,
    processing_status,
    server_verdict,
    flags,
    device_clock_skew_s
FROM mobile_event_logs
WHERE employee_id = '<employee_uuid>'
  AND created_at >= NOW() - INTERVAL '24 hours'
  AND processing_status = 'REJECTED'
ORDER BY created_at DESC
LIMIT 50;
```

---

## 4. Recovery & Remediation Actions

### Action A: Force Full Snapshot Resync
When a device has fallen behind the 60-day change log retention window or has local database corruption:
1. Advise the worker to tap **"Force Resync"** in the mobile app settings.
2. The mobile app calls:
   ```http
   GET /api/v1/mobile/sync/snapshot
   ```
3. The server computes a complete self-contained baseline snapshot (all worksite boundaries, current assignments, time rules, policies) spanning the last 30 days and resets the device's cursor anchor.

### Action B: Reset Device Cursor Server-Side
If an administrator needs to force a device to replay recent changes:
```sql
-- Reset device to cursor 0 to trigger fresh sync
UPDATE registered_devices
SET last_acked_cursor = 0, updated_at = NOW()
WHERE id = '<device_uuid>';
```

### Action C: Re-pair Compromised or Replaced Device
If a worker loses their phone or uninstalls the app:
1. Revoke the old device binding in the Admin UI or via SQL:
   ```sql
   UPDATE registered_devices
   SET is_active = FALSE, revoked_at = NOW()
   WHERE id = '<old_device_uuid>';
   ```
2. Generate a new activation code for the employee via the Admin dashboard.
3. The worker downloads the app on the new phone and completes device pairing.

### Action D: Consent Withdrawal Unblocking
If location events are returning `403 CONSENT_WITHDRAWN`:
1. Check employee consent state:
   ```sql
   SELECT id, tally_id, name, consent_status, consent_withdrawn_at FROM employees WHERE id = '<employee_uuid>';
   ```
2. If the employee wishes to resume tracking, re-record consent via the mobile app or have HR update the profile.
