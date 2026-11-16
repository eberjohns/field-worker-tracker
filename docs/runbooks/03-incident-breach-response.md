# Runbook 03 - Incident & Breach Response Procedure

## 1. Statutory Context & Regulatory Timelines
Field Worker Tracker handles employee location events, work schedules, and payroll snapshots. Under the data protection laws of operating jurisdictions, data breaches involving personal data trigger strict notification clocks:
- **KSA (Saudi Arabia)**: **72-hour statutory notification** to the Saudi Data and Artificial Intelligence Authority (SDAIA) under the Saudi Personal Data Protection Law (PDPL).
- **UAE**: Notification to the UAE Data Office and relevant supervisory authorities without undue delay where personal data confidentiality, integrity, or availability is compromised.

---

## 2. Incident Response Team & Key Roles

| Role | Operational Owner | Responsibilities |
|---|---|---|
| **Incident Commander / DPO** | Lead Compliance & Security Officer | Directs breach response, enforces containment, authorises regulatory filings |
| **Technical Lead** | Head of Infrastructure | System forensics, vulnerability patching, credential rotation, log preservation |
| **Legal Counsel** | UAE / KSA Legal Counsel | Advises on regulatory exposure, drafts official filings to UAE Data Office and SDAIA |
| **Communications Lead** | HR Director | Prepares worker communications in clear language (per Legal Action #5), internal notices |

---

## 3. Incident Severity Levels

| Level | Definition | Response Time | Action |
|---|---|---|---|
| **Sev 1 - Critical** | Confirmed unauthorized extraction or public exposure of location trails, payroll records, or worker credentials | < 15 minutes | Immediate containment; 72-hour notification clock starts; daily executive briefings |
| **Sev 2 - Major** | Unauthorized internal access, privilege escalation, or integrity tampering without public exfiltration | < 1 hour | Immediate access revocation, audit trail review, remediation within 24 hours |
| **Sev 3 - Minor** | Localized technical misconfiguration, rejected rogue batch, single worker device compromise | < 4 hours | Normal support triage, device revocation via Admin panel |

---

## 4. Phase-by-Phase Incident Response Workflow

```
[Detection & Alert] -> [Immediate Containment] -> [Investigation & Scope] -> [Statutory Notification (<= 72h)] -> [Recovery & Remediation] -> [Post-Mortem]
```

### Phase 1: Detection & Triage
1. Detection can originate from:
   - Automated alerts (`Alert` entries with `alert_type="ROGUE_DEVICE"` or repeated 401s/403s).
   - Database immutability trigger failure alerts.
   - Anomaly in location event volume or export endpoints.
2. The detecting engineer immediately pages the **Incident Commander** and **Head of Infrastructure**.
3. Create an incident tracking war room and timestamp all actions in the incident log.

### Phase 2: Immediate Containment
1. **Compromised Credentials / Session**:
   - Immediately revoke active user sessions:
     ```sql
     UPDATE user_sessions SET is_revoked = TRUE WHERE user_id = '<user_uuid>';
     ```
   - Lock out compromised user accounts:
     ```sql
     UPDATE users SET is_active = FALSE, locked_until = NOW() + INTERVAL '7 days' WHERE id = '<user_uuid>';
     ```
2. **Compromised Mobile Device**:
   - Revoke the device registration:
     ```sql
     UPDATE registered_devices SET is_active = FALSE, revoked_at = NOW() WHERE id = '<device_uuid>';
     ```
3. **Database Compromise**:
   - Rotate application database passwords (`fw_app`, `fw_migrator`) in Azure Key Vault and restart container pools.
   - Restrict database firewall rules to known static IPs / private VNet endpoints.

### Phase 3: Investigation & Scope Assessment
Query `audit_logs` and `live_location_access_logs` to ascertain the precise perimeter of affected data:
```sql
-- Identify all records viewed or modified by the compromised identity
SELECT actor_user_id, action, entity_type, entity_id, client_ip, created_at
FROM audit_logs
WHERE actor_user_id = '<compromised_user_uuid>'
  AND created_at >= '<breach_start_time>'
ORDER BY created_at ASC;

-- Identify location trails viewed
SELECT user_id, access_type, filters, client_ip, created_at
FROM live_location_access_logs
WHERE user_id = '<compromised_user_uuid>'
ORDER BY created_at ASC;
```

### Phase 4: Regulatory & Worker Notifications (Within 72 Hours)
If personal data was exposed:
1. **Legal Counsel** drafts the formal notification to:
   - UAE Data Office (UAE jurisdiction)
   - SDAIA National Platform (KSA jurisdiction)
2. Notification includes:
   - Nature of the security breach and affected categories of personal data.
   - Estimated number of affected data subjects (field workers, supervisors).
   - Likely consequences and risks to data subjects.
   - Measures taken or proposed to mitigate negative effects.
   - Contact details of the DPO / Incident Owner.
3. **HR Director** issues notices to affected employees in their native language (English, Arabic, Hindi/Urdu per legal requirements).

### Phase 5: Post-Incident Review & Hardening
1. Complete a root cause analysis (RCA) within 5 business days.
2. File permanent changes to code, infrastructure, or policies.
3. Update ADRs or runbooks as required.

