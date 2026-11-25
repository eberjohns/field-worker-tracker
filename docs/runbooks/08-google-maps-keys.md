# Runbook 08: Google Maps keys, quotas and checks for the dashboard (ADR-033)

Google Maps is the dashboard's only map provider. Without the two values below, map areas show "Map not configured" and the rest of the app works.

## 1. Create the key and the Map ID (Google Cloud console, owner)
1. **Pick or create the Google Cloud project for the company. Billing must be enabled.**
   - Without billing, Google refuses geocoding with "You must enable Billing on the Google Cloud Project".
   - Maps may show "For development purposes only".
2. **APIs & Services → Library:** enable the **Maps JavaScript API** and the **Geocoding API**.
   - Places API is not used: search runs only on the Search button.
3. **APIs & Services → Credentials → Create credentials → API key.** Name it `fwt-web-dashboard`.
   - This is a separate key from the mobile app's; never reuse that one.
   - **Application restrictions:** Websites. Add:
     - `http://localhost:5173/*` (local development);
     - the Render web URL, for example `https://<web-service>.onrender.com/*`;
     - any custom domain later.
   - **API restrictions:** restrict the key to the **Maps JavaScript API** and the **Geocoding API**.
4. **Google Maps Platform → Map management → Create Map ID:**
   - type **JavaScript**, rendering **Vector**, name `fwt-dashboard`;
   - advanced markers need it.
   - Optional: a map style in the same place can hide business points of interest, which are clutter on a site map.

## 2. Quotas and alerts (starting values, raise when usage shows the need)
1. **Google Maps Platform → Quotas** (or APIs & Services → each API → Quotas):

   | API | Quota | Per day |
   |---|---|---|
   | Maps JavaScript API | Map loads | **300** |
   | Geocoding API | Requests | **100** |

2. **Quota alert at 80%:**
   - Monitoring → Alerting → Create policy;
   - metric: Consumer Quota → quota usage, for each of the two quotas;
   - threshold: 80% of the limit; notify the owner's email.
3. **Budget alert:** Billing → Budgets & alerts → Create budget for the project, with email alerts at 50%, 90% and 100%.
4. **Our own counter:** Settings → System (Admin) shows map loads and place searches per month for each environment.
   - It is measured by the app, so it is the first place to look.
   - Soft limits are the company settings `map_loads_soft_limit_month` (7,200) and `geocodes_soft_limit_month` (2,400): 80% of the daily quotas over 30 days.

When a quota is used up, map areas show "Map unavailable today (usage limit reached)" and search says the same. Everything else keeps working. The quota resets at midnight Pacific time.

**What a normal session costs**, measured on the demo data on 25 Nov 2026: 1 map load. A session covering Live Map, a worksite's Boundary tab (draw, edit, map type switch) and Live Map again still loads one map. Each Search press is one geocode.

## 3. Give the values to the app (environment only)
Never write the values into a tracked file, a doc, a commit or a PR.

| Where | How |
|---|---|
| Local | `web/.env.local` (git-ignored): `VITE_GOOGLE_MAPS_API_KEY=...` and `VITE_GOOGLE_MAPS_MAP_ID=...`, then restart `pnpm dev` |
| Render (web service) | Environment → add `VITE_GOOGLE_MAPS_API_KEY` and `VITE_GOOGLE_MAPS_MAP_ID`, then **Manual Deploy → Clear build cache & deploy** |
| Owner's naming | the owner may hand them over as `GOOGLE_MAPS_API_KEY` and `GOOGLE_MAPS_MAP_ID`; the web build reads them with the `VITE_` prefix |

**`VITE_` variables are read at build time**, not run time. Vite writes them into the built files, so changing them on Render needs a rebuild and redeploy; a restart is not enough.

They end up in the browser bundle. That is expected for a Maps JavaScript key, and it is why the referrer and API restrictions in step 1 matter.

## 4. Check
1. Sign in as Admin.
2. **Live Map:**
   - the Google road map shows;
   - workers are coloured markers, and clusters split when you zoom in;
   - the refresh button doesn't redraw the map.
3. **Worksites → a worksite:**
   - the header shows a small boundary outline;
   - **Show on map** opens the Boundary tab;
   - the boundary loads, and Map/Satellite switches through Google's control.
4. **Search** "Dubai Mall" and press **Search:** results appear, and picking one moves the map.
5. **Settings → System:** this month's map loads and place searches went up.
6. **Browser console:** no `RefererNotAllowedMapError`, `ApiNotActivatedMapError`, `InvalidKeyMapError` or billing messages.

## 5. Rotating the key
1. Create the new key with the same restrictions.
2. Update the environment and rebuild and redeploy.
3. Run the checks in step 4.
4. Delete the old key.

## 6. Mobile app: Google Maps SDK for Android key
The mobile app draws worksite and camp boundaries with the Google Maps SDK for Android. Its key is separate from the dashboard's. The full handover for the mobile team is in `docs/mobile-handover-v1.md` §3–4.

1. **Own key.** Use the client's Google Cloud project (the same project is fine). Create credentials → API key, named `fwt-android-app`. Never reuse the web key.
2. **Application restriction:** Android apps. Add:
   - the **package name** with the **release SHA-1**: the **App signing key** certificate from the Play Console **App integrity** page, if Play App Signing is on;
   - for testing, **either** the debug SHA-1 (`./gradlew signingReport`) and the upload key SHA-1, **or** a separate test key (`fwt-android-test`) restricted the same way.
3. **API restriction:** enable and allow the **Maps SDK for Android** only.
4. **No Map ID.** The app doesn't set a `mapId` and doesn't use cloud-based styling, so mobile map loads stay in Google's free tier. Styling, if any, is a local JSON style.
5. **Never commit the key.** The app reads it into `AndroidManifest.xml` as `<meta-data android:name="com.google.android.geo.API_KEY" android:value="${MAPS_API_KEY}" />` through a Gradle build variable. The value comes from `~/.gradle/gradle.properties` locally, or from a CI secret (`MAPS_API_KEY`).
6. **Quota and alerts.** The Maps SDK for Android has no per-load charge without a Map ID. Still keep the project's budget alert from §2, and add a quota alert on the Maps SDK for Android at 80 % of whatever daily cap is set.
7. **Check.** A release build on a real phone shows the map, with no `Authorization failure` in logcat. That error means a wrong SHA-1 or package name.
8. **Rotating.** Create the new key with the same restrictions, ship an app build with it, wait until old builds are out of use, then delete the old key.
