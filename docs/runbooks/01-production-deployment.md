# Runbook 01 - Production Deployment (UAE Stack)

## 1. Overview and Architecture
This runbook defines the operational procedure for deploying and updating Field Worker Tracker (FWT) in the primary production environment (UAE Stack) per **ADR-009** and **docs/14-nonfunctional.md**. The Render deployment used today is described by `render.yaml`; see **runbook 09**.

### Infrastructure Topology
- **Cloud Provider**: Microsoft Azure
- **Primary Region**: `UAE North` (Dubai)
- **Secondary / Disaster Recovery Region**: `UAE Central` (Abu Dhabi) — restricted access in-country pairing for geo-redundant backups
- **Database**: Azure Database for PostgreSQL Flexible Server (PostgreSQL 16 + PostGIS)
  - Zone-redundant high availability (Zone 1 + Zone 2)
  - Daily snapshots + Point-in-Time Recovery (PITR) with 15-minute RPO window
  - In-country automated geo-redundant backup storage (UAE Central)
- **Application Runtime**: Azure App Service / Azure Container Apps (2 minimum instances behind Load Balancer)
- **Reverse Proxy / Ingress**: Caddy / Nginx terminating TLS 1.3, enforcing HSTS, CSP, and rate limiting

---

## 2. Secrets Management
All production secrets must be retrieved from **Azure Key Vault** at startup or injected via managed environment variables. Secrets must never be stored in version control or plain text.

| Secret Name | Purpose | Rotation Policy |
|---|---|---|
| `DATABASE_URL` | Application pool credentials (`fw_app`) | 90 days / staff change |
| `DATABASE_MIGRATOR_URL` | Schema migration credentials (`fw_migrator`) | 90 days / staff change |
| `JWT_SECRET` | HS256 JWT access and refresh token signing key | Annual / on breach |
| `ARCHIVE_ENCRYPTION_KEY` | AES-256-GCM master key for yearly archive packages | Master KMS key |

---

## 3. Pre-Deployment Checklist
Before triggering any production deployment:
1. Ensure the target release git commit is tagged (e.g. `v1.0.0`) and CI pipeline checks have passed (all unit tests, import linter, vulnerability scan).
2. Verify that an automated database snapshot has completed within the last 15 minutes.
3. Check the Alembic migration history:
   ```bash
   alembic history --verbose -r -3:head
   ```
4. Verify that any database schema changes are backward-compatible (Expand/Contract pattern per `docs/14-nonfunctional.md`).

---

## 4. Standard Rolling Deployment Procedure

### Step 4.1: Run Database Schema Migrations
Database migrations are run prior to updating application containers using the dedicated `fw_migrator` user:
```bash
docker run --rm \
  --env DATABASE_URL="$DATABASE_MIGRATOR_URL" \
  field-worker-tracker/backend:v1.0.0 \
  alembic upgrade head
```

### Step 4.2: Deploy Application Containers (Zero-Downtime)
1. Deploy new container version `v1.0.0` to the secondary slot or stage in the rolling cluster.
2. The orchestrator polls `/health/readiness` on the new instance.
3. Once readiness returns `200 OK`, route incoming traffic to the new instances.
4. Drain connections from old instances gracefully (grace period: 30 seconds).

### Step 4.3: Post-Deployment Smoke Test
Verify critical system paths:
1. **Liveness / Readiness**:
   ```bash
   curl -f -k https://api.fieldtracker.example.com/health/liveness
   curl -f -k https://api.fieldtracker.example.com/health/readiness
   ```
2. **Dashboard Ingress**: Verify React web assets load without 404s or CSP violations.
3. **Audit Log Verification**: Confirm that the system has logged the startup event in `audit_logs`.

---

## 5. Rollback Procedure
If the post-deployment smoke test fails or error rate spikes above 0.5%:
1. Immediately switch traffic back to the previous stable container image (`v0.9.x`).
2. If migrations cannot run with old code, run Alembic downgrade:
   ```bash
   alembic downgrade -1
   ```
3. If data corruption occurred, initiate PITR restore per **Runbook 02**.
4. Log an incident ticket and notify the engineering team.

---

## 6. Reverse Proxy Selection: Caddy vs. Nginx

The application backend (FastAPI/Uvicorn) and frontend (React SPA) are proxy-agnostic and adhere to standard HTTP/1.1 and ASGI reverse-proxy specifications. **Switching between Caddy and Nginx requires zero changes to application code.**

### Option A: Caddy (Default)
- **Use case**: Automatic Let's Encrypt / ZeroSSL certificate management with zero manual TLS configuration.
- **Command**:
  ```bash
  docker compose -f docker-compose.prod.yml up -d
  ```

### Option B: Nginx
- **Use case**: Environments with pre-existing enterprise TLS certificates, custom Edge SSL terminators, or strict IT enterprise Nginx mandates.
- **Configuration**: `infra/nginx/nginx.conf`
- **Command**:
  ```bash
  # Start stack with Nginx instead of Caddy proxy
  docker compose -f docker-compose.prod.yml --profile nginx up -d api worker nginx migrator
  ```
- **Key Nginx Directives Required by FWT**:
  1. `proxy_buffering off;` and `proxy_cache off;` on `/api/v1/live/stream` for real-time Server-Sent Events (SSE) tracking.
  2. `client_max_body_size 12M;` to support up to 10 MB bulk Excel file imports (`/api/v1/imports/upload`).
  3. `try_files $uri $uri/ /index.html;` for React SPA client-side routing.
  4. Forwarded headers: `X-Forwarded-For`, `X-Forwarded-Proto`, and `Host`.


