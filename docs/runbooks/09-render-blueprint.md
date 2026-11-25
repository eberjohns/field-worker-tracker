# Runbook 09: Render setup and the Blueprint (`render.yaml`)

The current Render deployment (owner, 25 Nov 2026):

| Part | Render service | URL | Plan |
|---|---|---|---|
| Web dashboard (static site) | `field-worker-tracker-1` | its `onrender.com` URL | static |
| Backend API (Docker web service) | `field-worker-tracker-2` | `https://field-worker-tracker-2.onrender.com` | **free** |

`render.yaml` at the repository root describes this setup as a Blueprint. Nothing in the repository calls Render.

**The Blueprint is for new environments** (a fresh staging, or a second deployment). The owner does **not** apply it to the two existing services; those are set by hand (section 2). Runbook 01 covers the target production stack (Azure UAE).

## 1. What `render.yaml` contains
- **Static site `field-worker-tracker-1`:**
  - build: `npm install -g pnpm@12.16.1 && cd web && pnpm install --frozen-lockfile && pnpm run build`, the same steps as CI;
  - publish directory `web/dist`;
  - two rewrites, `/api/*` → `https://field-worker-tracker-2.onrender.com/api/*`, then `/*` → `/index.html` (section 4);
  - variables `VITE_GOOGLE_MAPS_API_KEY` and `VITE_GOOGLE_MAPS_MAP_ID`.
- **Docker web service `field-worker-tracker-2`:**
  - built from `backend/Dockerfile` with context `backend`, on `plan: free`, with health check `/health/liveness`;
  - start command, with the migration first because the free plan has no pre-deploy command (section 5):
    ```sh
    sh -c "uv run alembic upgrade head && uv run uvicorn fw.main:app --host 0.0.0.0 --port $PORT"
    ```
  - the paid-plan `preDeployCommand` is kept as a comment.
- **Variables:** every one is `sync: false` with no value. Render asks for each value when the Blueprint is created and never reads one from the file. Never put a value in `render.yaml`.
- **Not included:** push, email, MapTiler or Nominatim (DEC-62, DEC-64, ADR-033), and `VITE_API_URL` (section 4).

## 2. The existing services: set by hand
Apply these once in the Render dashboard. Nothing here needs the Blueprint.

**Backend `field-worker-tracker-2`: migrations on every deploy (free plan)**
1. Render → `field-worker-tracker-2` → **Settings → Build & Deploy → Docker Command**.
2. Set it to:
   ```sh
   sh -c "uv run alembic upgrade head && uv run uvicorn fw.main:app --host 0.0.0.0 --port $PORT"
   ```
   - The image's working folder is `/app`, which holds `alembic.ini`, so no `cd` is needed.
   - If the service is a native Python service rather than Docker (Settings → Runtime), put `uv run alembic upgrade head && ` in front of the existing **Start Command** instead, run from the folder that has `alembic.ini` (`backend`).
3. Save. Render redeploys. In the logs, the start must show `alembic.runtime.migration` lines (or nothing to upgrade), then uvicorn starting.
4. **If you move to a paid plan later:**
   - put `uv run alembic upgrade head` in **Pre-Deploy Command**;
   - remove the migration part from the Docker Command, or clear it to use the Dockerfile's CMD.

   The pre-deploy command is better: if it fails, the old version keeps serving.
5. **Delete leftover variables**, none of which is read any more: `PUSH_BACKEND`, `FCM_CREDENTIALS`, `EMAIL_BACKEND`, `SMTP_HOST`, `SMTP_PORT`, `MAP_STYLE_STREETS_URL`, `MAP_STYLE_SATELLITE_URL`, `MAP_API_KEY`.

**Static site `field-worker-tracker-1`**
1. **Settings → Redirects/Rewrites.** Two rules, in this order (section 4):

   | # | Source | Destination | Action |
   |---|---|---|---|
   | 1 | `/api/*` | `https://field-worker-tracker-2.onrender.com/api/*` | Rewrite |
   | 2 | `/*` | `/index.html` | Rewrite |

2. **Environment:**
   - set `VITE_GOOGLE_MAPS_API_KEY` and `VITE_GOOGLE_MAPS_MAP_ID` (runbook 08);
   - delete `VITE_API_URL` if it is set, along with any `VITE_MAP_*` or MapTiler key;
   - then **Manual Deploy → Clear build cache & deploy**.
3. **Build command and publish directory:** compare them with section 1. They only need to produce `web/dist` with the same steps.

## 3. A new environment from the Blueprint
1. **Edit `render.yaml` on a branch first.** Rename both services, for example `fwt-staging-web` and `fwt-staging-api`, and point the `/api/*` rewrite at the new backend's URL (`https://<new-api-name>.onrender.com/api/*`). If the names still match the existing services, Render would take those services over instead of creating new ones.
2. Render → **New → Blueprint** → this repository and that branch.
3. **Read the preview.** It must say *create* for both services, not *update*. Enter each `sync: false` value when asked.
4. Create the database separately, and set `DATABASE_URL` and `DATABASE_MIGRATOR_URL` to it.
5. The first start runs every migration on the empty database. Then sign in as `ADMIN001` (runbook 05).

## 4. Why the rewrite order matters
**The first matching rule wins**, and `/*` also matches `/api/...`. If the catch-all came first, every API call would get `index.html` (status 200, HTML instead of JSON). Sign-in and data loading would fail with JSON parse errors, while the page itself still loads.

Because of rule 1, the browser calls its own origin (`/api/...`), and Render forwards the call to the backend:
- the web build needs **no `VITE_API_URL`** (the app treats it as an optional prefix; leave it unset);
- CORS doesn't come into play for the dashboard.

(`web/vercel.json` held the same rules for Vercel. Vercel isn't used, so it was deleted on 25 Nov 2026.)

## 5. Environment variables and redeploys
- **`VITE_` variables** are written into the built files at build time.
  - After changing one, run **Manual Deploy → Clear build cache & deploy** on the static site; a restart isn't enough.
  - Keys, restrictions and quotas are in runbook 08.
- **Backend variables** apply on the next deploy or restart.
- **Migrations run on every start (free plan).** A start with nothing new to migrate is a quick no-op.
  - If a migration fails, uvicorn never starts and the deploy fails.
  - Free instances also start after sleeping, so a broken migration shows up on the next wake-up too.
  - Migrations are written to be additive.

## 6. If a deploy fails
1. Render → `field-worker-tracker-2` → **Logs**. Find the start output: an Alembic traceback means the migration failed.
2. **See where the database is.** The free plan has no Render shell, so run these locally from `backend/`:
   ```sh
   uv run alembic current        # revision the database is at
   uv run alembic heads          # revision the code expects
   uv run alembic history -r -3:head
   ```
   Point them at the Render database with its **external** connection string, set as `DATABASE_MIGRATOR_URL` (and `DATABASE_URL`) in that shell session only, never in a file. On a paid plan, use **Shell** on the service instead.
3. **`current` is behind `heads`:** the migration failed partway or didn't run. Fix the cause shown in the log (for example a missing permission for the migrator role, or data that breaks a new constraint), then redeploy.
4. **`current` equals `heads` but the app fails:** the migration isn't the problem. Check the uvicorn part of the log and the environment variables.
5. Don't run `alembic downgrade` on the hosted database without the owner's go-ahead (runbook 01 §4).

## 7. Not in the Blueprint
- **The database:** managed separately, and referenced through `DATABASE_URL`.
- **The background worker** (`python -m fw.worker` in docker-compose): add it as a `type: worker` service only if a deployment needs it.
- **Local file storage** (`LOCAL_STORAGE_PATH` for generated reports and archives) is on the instance's disk. On Render's free plan that disk is wiped on every deploy and restart; a persistent disk needs a paid plan.
