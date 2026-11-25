# Runbook 08: Google Maps keys for the dashboard (ADR-033)

The dashboard uses Google Maps when `VITE_MAP_PROVIDER=google` and both Google values are set.
With either missing it uses the MapLibre fallback and logs why in the browser console.

## 1. Create the key and the Map ID (Google Cloud console, owner)
1. Pick or create the Google Cloud project for the company. Billing must be enabled.
2. **APIs & Services → Library:** enable **Maps JavaScript API** and **Places API (New)**. Nothing else is needed.
3. **APIs & Services → Credentials → Create credentials → API key.** Name it `fwt-web-dashboard`.
   - This is a separate key from the mobile app's; never reuse that one.
   - **Application restrictions:** Websites. Add every address the dashboard is served from: the production domain (`https://<domain>/*`), staging, and `http://localhost:5173/*` and `http://localhost:4173/*` for local work. Use a separate dev key if production must not allow localhost.
   - **API restrictions:** Restrict key to **Maps JavaScript API** and **Places API (New)**.
4. **Google Maps Platform → Map management → Create Map ID**:
   - type **JavaScript**, rendering **Vector**, name `fwt-dashboard`;
   - advanced markers need it.
5. **Quotas and budget:**
   - in Billing, set a budget with an alert;
   - in Quotas, cap Maps JavaScript API map loads and Places Autocomplete requests per day to a sensible ceiling for about 100 users.

## 2. Give the values to the app (environment only)
Never write the values into a tracked file, a doc, a commit or a PR.

| Where | Variables |
|---|---|
| Local | `web/.env.local` (git-ignored): `VITE_MAP_PROVIDER=google`, `VITE_GOOGLE_MAPS_API_KEY=...`, `VITE_GOOGLE_MAPS_MAP_ID=...` |
| Hosting (static web build) | the same three as build-time environment variables of the web service, then redeploy |
| Owner's naming | the owner may hand them over as `GOOGLE_MAPS_API_KEY` and `GOOGLE_MAPS_MAP_ID`; the web build reads them with the `VITE_` prefix |

Vite puts `VITE_` values into the browser bundle. That is expected for a Maps JavaScript key, and it is why the key restrictions in step 1 matter.

## 3. Check
1. Restart `pnpm dev`, or rebuild for the hosting, and sign in.
2. Open Worksites → a worksite → Map:
   - the Google road map shows;
   - Map/Satellite switches;
   - the boundary loads unchanged.
3. Search "Dubai Mall": suggestions appear after 3 characters, and picking one moves the map.
4. Live Map: markers appear in their state colours and clusters split when you zoom in.
5. The browser console has no Google Maps errors such as `RefererNotAllowedMapError` or `ApiNotActivatedMapError`. The network tab shows no `maptiler.com` or `nominatim` requests.

## 4. Switching back
Set `VITE_MAP_PROVIDER=maplibre` (or remove the Google values) and rebuild. There's no data change, because boundaries are stored as PostGIS geometry either way.

## 5. Rotating the key
1. Create the new key with the same restrictions.
2. Update the environment and redeploy.
3. Check step 3 above.
4. Delete the old key.
