# 14 - Non-functional Requirements

## 1. Security
- **Transport**: TLS everywhere; HSTS; secure cookies.
- **Authentication**: web = employee ID + password (Argon2id), company default password forced to change at first login, access token 15 min, refresh token rotating in an httpOnly cookie, absolute session limit 12 h. Mobile = activation code then PIN/password, device-bound refresh tokens. Lockout after 5 failed logins (15 min). Reuse of a rotated refresh token revokes the session.
- **Authorization**: role + reporting scope enforced in the service/repository layer on every endpoint; denied attempts audited.
- **Input**: Pydantic validation on all inputs; parameterized SQL only (SQLAlchemy); GeoJSON validated (valid ring, size limits).
- **Uploads**: `.xlsx` only, max 10 MB, reject macros/external links, parse with limits (rows/sheets), store outside the web root, scan type by content not extension.
- **Secrets**: environment/secret manager; never in the repo; rotate on staff change.
- **Headers/CORS**: strict CORS allow-list, CSP, `X-Content-Type-Options`, `Referrer-Policy`.
- **Dependencies**: lock files, vulnerability scan in CI, secret scan in CI.
- **Logs**: no tokens, passwords, or coordinate trails in application logs.
- **Rate limiting**: auth endpoints and import upload.

## 2. Privacy and consent (engineering view; legal review is separate)
- Location is collected only during the worker's tracked hours and only after consent; the consent record stores policy version, device, timestamp.
- Collect the minimum: no document numbers or scans; no `source` field on events.
- Map tile providers see only which map area a dashboard user views. Worker coordinates and boundaries are rendered from our own API and are never sent to a tile provider or any other third party.
- Access to raw locations is limited to roles in scope and logged.
- **Data residency**: each country's personal data is stored and backed up in that country (ADR-009, `legal/02-compliance-review.md`). Avoid sending personal data to third-party SaaS (analytics, error tracking, AI APIs) and scrub payloads.
- Support retention policy enforcement and subject-access exports by employee.
- Breach response runbook (`docs/runbooks/`, to be written in M9).
- Legal review is required before go-live in each country (UAE PDPL; KSA PDPL and SDAIA requirements). The project does not give legal advice.

## 3. Audit
Every state-changing action writes `audit_logs` (actor, role, action, entity, safe diff, reason, UTC time, IP). The table is append-only for the application role. Raw events, attendance versions, comments, approvals and payroll snapshots are themselves immutable history.

## 4. Data retention and archiving   [DEC-38]
Detailed schedule and the legal rationale: `legal/04-data-inventory-retention-DPIA.md`.
- **Raw location events**: 13 months in the live database, then an **encrypted yearly archive** kept for a fixed period decided with counsel (proposal 5 years), then deletion. (The client asked to keep location and attendance records permanently; this needs legal agreement, see `legal/01-human-actions.md`.)
- **Attendance, payroll, reports, approvals, audit**: kept live for 7 years (small tables), then anonymised. Generated reports are kept with them.
- **Yearly clean-up**: after the year's payroll is approved, an Admin runs the archive: export the year's raw events and derived detail to encrypted files with checksums, **download an encrypted copy to a local machine and store a second copy in cloud storage**, verify by restoring a sample, then purge from the live database. Archives are never deleted without a legal decision.
- `sync_changes`: 60 days. `notification_logs`: 6 months.
- Employees leaving: kept at least 2 years after end of service (UAE labour law), then anonymised.

## 5. Backup and recovery
- Managed PostgreSQL with **point-in-time recovery**, daily snapshots, multi-AZ.
- Second copy in a different zone/region **inside the same legal territory**.
- Targets (confirm with client): **RPO <= 15 min, RTO <= 4 h**.
- Object storage versioning for exports and archives.
- **Restore drill every quarter**; record the result. Backups are encrypted; keys in a managed KMS.
- Migration safety: expand/contract, backup/snapshot before each production migration, rollback plan in the release notes.

## 6. Performance targets (500 workers, ~100 dashboard users)
| Operation | Target (p95) |
|---|---|
| List endpoints | < 300 ms |
| Week view (one week, all worksites in scope) | < 1.5 s |
| Event batch ingest (200 events) | < 500 ms |
| Sync changes pull | < 300 ms |
| Daily attendance recompute (one employee-day) | < 2 s |
| Payroll preview (500 employees, one month) | < 3 min (background) |
| Report export (up to 50k rows) | < 2 min (background) |
Volume estimate: 500 workers x 10 h x 12 pings/h ~ 60k events/day ~ 22M/year ~ 5-6 GB/year.

## 7. Availability and operations
Single region, multi-AZ database, at least two API instances. Zero-downtime deploys (rolling). Planned maintenance windows outside 04:00-18:00 local (workers' day). Health checks, alerting on queue backlog, error rate, DB connections and disk.

## 8. Database policy summary
Roles as in 13 section 9; statement timeout 30 s for the app role; connection pool sized to instances; `audit_logs` and `mobile_event_logs` append-only for the app role; all FKs `RESTRICT`; migrations only through Alembic by `fw_migrator`.

## 9. Indicative infrastructure cost (planning only; validate in the provider's calculator)
Production for ~500 workers: ~USD 650-1,000 per month (two small containers, managed Postgres multi-AZ, storage/backup, load balancer/WAF, monitoring); staging adds ~250-400. Gulf regions typically cost more than US regions. Add SaaS (source control, error tracking, map tiles) ~50-200.

## 10. Accessibility and localization
Web: keyboard navigation, focus visibility, ARIA on the scheduler, contrast. English first; structure strings for later Arabic and RTL.

## 11. Hosting and database recommendation
- **Managed PostgreSQL with PostGIS, not a self-managed VM database.**
- **Provider: Microsoft Azure, region UAE North (Dubai)**, Azure Database for PostgreSQL flexible server with zone-redundant high availability and geo-redundant backup; UAE Central (Abu Dhabi) is the in-country recovery region (it is access-restricted: confirm with Microsoft that the subscription can use it). PostGIS is supported through the extension allow-list.
- **Why**: in March 2026 the AWS UAE region was physically damaged and some data hosted in a single zone could not be recovered, so multi-AZ in one region is not enough; two in-country regions plus tested restores are required. Other Gulf providers (including Oracle in Dubai) were also affected by incidents, so no provider is assumed immune.
- **Backups**: daily plus point-in-time recovery in-country; **restore drill every quarter**; an additional encrypted off-region copy only after counsel confirms it is permitted.
- **Saudi stack**: separate, inside the Kingdom, when Saudi goes live (AWS and Azure Saudi regions were announced for late 2026; confirm availability, PostGIS support and the legal position at that time).
- **Application hosting**: one container host in the same region as the database for the pilot; two instances behind a load balancer for production.
- **Portability**: plain PostgreSQL + PostGIS; moving provider is a dump and restore.

- **Use a managed PostgreSQL service with PostGIS, not a self-managed VM database.** This system holds payroll, attendance and location history: managed services give automatic backups with point-in-time recovery, patching, multi-AZ failover and monitoring, which a small team would otherwise build and operate itself. A self-managed database only makes sense with a dedicated DBA.
- **Region**: choose a UAE region for the first deployment. Check that the provider offers PostGIS in that region when buying (AWS RDS for PostgreSQL and Azure Database for PostgreSQL support PostGIS; confirm availability in the UAE region). Saudi regions from AWS, Azure and Google are new or arriving; re-check availability and the legal position before the Saudi go-live.
- **Application hosting**: for the pilot, one container host (a single VM running Docker Compose, or the provider's container service) in the same region as the database; move to two instances behind a load balancer for production.
- **Portability**: the database is plain PostgreSQL + PostGIS, so moving provider later is a dump and restore.
- Cost, backups and recovery targets: sections 5 and 9.
