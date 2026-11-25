# Runbook 09: Render Blueprint (`render.yaml`)

`render.yaml` at the repository root describes the current Render setup as a Blueprint:
- the web dashboard as a static site;
- the backend API as a Docker web service.

The owner applies it in the Render dashboard; nothing in the repository calls Render. Runbook 01 covers the target production stack (Azure UAE); this runbook covers the Render deployment used today.

## 1. Check against Render before the first apply
Some values in `render.yaml` couldn't be read from the repository. They are marked `CHECK AGAINST RENDER`:

| Item | In `render.yaml` | Where it came from | Check |
|---|---|---|---|
| Backend URL in the `/api/*` rewrite | `https://fwt-backend.onrender.com` | `web/vercel.json` | Render → backend service → its `onrender.com` URL. Note: the 19 Nov handover mentions `field-worker-tracker-2.onrender.com`; if that is the backend, use it here (and in `web/vercel.json`) |
| Backend service name | `fwt-backend` | the host name above | must equal the existing service's name |
| Web service name | `field-worker-tracker-1` | owner | must equal the existing static site's name |
| Web build command | `npm install -g pnpm@12.16.1 && cd web && pnpm install --frozen-lockfile && pnpm run build`, publish `web/dist` | CI (`.github/workflows`) | compare with Render → static site → Settings → Build Command / Publish Directory |
| Backend runtime | Docker (`backend/Dockerfile`, context `backend`) | the repo's Dockerfile | Render → backend → Settings → Runtime. If it is a native **Python** service instead, change the entry to `runtime: python`, `rootDir: backend`, `buildCommand: pip install uv && uv sync --frozen --no-dev`, `startCommand: uv run uvicorn fw.main:app --host 0.0.0.0 --port $PORT` |
| Plan | not set (Render keeps the current plan) | - | free or paid decides the migration option in section 4 |

**A name that doesn't match creates a new service**, which may be billed, instead of updating the existing one. Read Render's preview of the Blueprint before confirming: it must say *update*, not *create*, for both services.

## 2. Apply the Blueprint
1. Merge the PR so `render.yaml` is on `main`.
2. Render → **New → Blueprint** → choose this repository and branch `main`. For an existing Blueprint, use **Blueprints → (this one) → Manual sync**.
3. Check the preview against section 1. Render lists the `sync: false` variables:
   - **For variables the services already have,** keep the current values. Render doesn't overwrite them.
   - **For any variable it asks for,** enter the value in the dashboard. Values never go into `render.yaml`.
4. Apply. Both services redeploy.
5. **Delete leftovers by hand.** The Blueprint doesn't remove variables it doesn't list:
   - on the static site: `VITE_API_URL`, and any `VITE_MAP_*` or MapTiler key;
   - on the backend: `PUSH_BACKEND`, `FCM_CREDENTIALS`, `EMAIL_BACKEND`, `SMTP_HOST`, `SMTP_PORT`, `MAP_STYLE_*`, `MAP_API_KEY`.

   None of them is read any more (DEC-62, DEC-64, ADR-033).

## 3. Why the rewrite order matters
The static site has two rewrites, and **the first match wins**:
1. `/api/*` → `https://<backend>.onrender.com/api/*`
2. `/*` → `/index.html`

`/*` also matches `/api/...`. If the catch-all came first, every API call would get `index.html` (status 200, HTML instead of JSON). Logins and data would fail with JSON parse errors, while the page itself still loads.

Because of rule 1, the browser calls its own origin (`/api/...`), and Render forwards the call to the backend:
- the web build needs **no `VITE_API_URL`**; leave it unset;
- CORS doesn't come into play for the dashboard.

`web/vercel.json` holds the same two rules in the same order, for a Vercel deployment. Keep the two files in step when the backend URL changes.

## 4. Environment variables and redeploys
- **`VITE_` variables** (`VITE_GOOGLE_MAPS_API_KEY`, `VITE_GOOGLE_MAPS_MAP_ID`) are written into the built files at build time.
  - After changing one, run **Manual Deploy → Clear build cache & deploy** on the static site; a restart is not enough.
  - Keys, restrictions and quotas are in runbook 08.
- **Backend variables** apply on the next deploy or restart.
- **Never commit a value.** Every variable in `render.yaml` is `sync: false` with no value.

## 5. Migrations run on every deploy
- **Paid plans (Starter and up):** `preDeployCommand: uv run alembic upgrade head`.
  - It runs in the image's `/app` folder, which has `alembic.ini`, after the build and before the new version takes traffic.
  - It uses `DATABASE_MIGRATOR_URL`, or `DATABASE_URL` when that is unset.
  - If it fails, the deploy stops and **the old version keeps serving**.
- **Free plan:** Render has no pre-deploy command on free.
  - Delete `preDeployCommand` and set the start command to run the migration first:
    ```yaml
    dockerCommand: sh -c "uv run alembic upgrade head && uv run uvicorn fw.main:app --host 0.0.0.0 --port $PORT"
    ```
    For a native Python service, put `uv run alembic upgrade head && ` in front of the `startCommand` instead.
  - Here a failing migration stops the new instance from starting. Render then keeps the previous instance only while the deploy is in progress, so check promptly (section 6).
- Migrations are written to be additive. A deploy that only adds code runs `upgrade head` as a no-op.

## 6. If a deploy fails
1. Render → backend → **Events / Logs**. Find the pre-deploy (or start) output, which ends with the Alembic error.
2. See where the database is: Render → backend → **Shell** (paid plans), then:
   ```sh
   uv run alembic current        # revision the database is at
   uv run alembic heads          # revision the code expects
   uv run alembic history -r -3:head
   ```
   On the free plan (no shell), run the same commands locally against the Render database. Use the external connection string, set as `DATABASE_MIGRATOR_URL` in your shell only, never in a file, from `backend/`.
3. **`current` is behind `heads`:** the migration failed partway or didn't run. Fix the cause shown in the log (a missing permission for the migrator role, say, or data that breaks a constraint), then redeploy.
4. **`current` equals `heads` but the app fails:** the problem is not the migration. Check the start log and environment variables.
5. Don't run `alembic downgrade` on the hosted database without the owner's go-ahead (runbook 01 §4).

## 7. Not in the Blueprint
- **The database:** it is managed separately, and the Blueprint only references it through `DATABASE_URL`.
- **The background worker** (`python -m fw.worker` in docker-compose): add it as a `type: worker` service only if it runs on Render today.
- **Push, email, MapTiler and Nominatim:** removed (DEC-62, DEC-64, ADR-033).
- **Local file storage** (`LOCAL_STORAGE_PATH` for generated reports and archives) is on the instance's disk. On Render that disk is wiped on every deploy unless a persistent disk is attached (paid plans).
