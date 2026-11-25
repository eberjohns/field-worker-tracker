# Field Worker Tracker – mobile handover for v1 (25 Nov 2026)

**Audience: the mobile app team.** This one document lists everything that changed on the server since the contract you built against, what the app must do about each change, how worksite boundaries reach the app and how to draw them, and how to set up the Google Maps SDK key.

- **Authoritative contract:** [`docs/09-mobile-sync-contract.md`](09-mobile-sync-contract.md), now at revision **1.2.0**. The OpenAPI file is [`openapi-mobile.json`](../openapi-mobile.json).
- **Baseline:** this document assumes you built against revision **1.1.1** (18 Nov 2026). If you built against an earlier revision, also read the 1.0.x–1.1.x rows in §14 of the contract.
- **Contract version header:** unchanged (`X-Contract-Version: 1`). Nothing here needs a new API path.
- It replaces [`mobile-team-notes-2026-11-19.md`](mobile-team-notes-2026-11-19.md), which is kept for history.

---

## 1. Summary: what the app must do

| # | Change | App must | Section |
|---|---|---|---|
| 1 | Login lockout is `403 ACCOUNT_LOCKED` (no `429`) | Show the server's `detail`; drop any `429` / `Retry-After` handling for login | 2.1 |
| 2 | Error text is in `detail` (the contract example wrongly said `message`) | Read `detail` | 2.2 |
| 3 | Push is not used in v1 | Not register for push (no FCM setup); not wait for push; keep syncing on heartbeat and app open | 2.3 |
| 4 | Weekly scorecard removed | Not call `/mobile/me/scorecard`; not build a scorecard screen; ignore `SCORECARD` | 2.4 |
| 5 | Gzip on responses over 1 KB | Nothing with OkHttp/Retrofit; if you set `Accept-Encoding` yourself, unpack the body | 2.5 |
| 6 | Template days become real `SCHEDULE_ITEM`s (`source: TEMPLATE`, `DELETE` ops) | Treat unknown `source` as `PLANNED`; deleting an unknown id is a no-op | 2.6 |
| 7 | Device mismatch raises an Admin alert | Nothing (the reply is unchanged) | 2.7 |
| 8 | OT2 rule, reassignment dates, absent days, example people | Nothing (values differ, shapes don't) | 2.8 |
| 9 | Boundaries | Draw with `Polygon`/`LatLng` as in section 3 | 3 |
| 10 | Maps SDK key | Set it up as in section 4 | 4 |

---

## 2. Contract changes since revision 1.1.1

### 2.1 Login lockout: `403 ACCOUNT_LOCKED` instead of `429 RATE_LIMITED`
Endpoint: `POST /api/v1/mobile/auth/login` (the web login behaves the same way).

**Before (1.1.1).** The contract said: "Login locks after repeated failures; on `429 RATE_LIMITED`, honour `Retry-After`." The server never actually locked, and never sent 429.

**Now (1.2.0).**
- **Locking:** after **5 wrong passwords in a row** for the same Tally ID, the account is locked for **15 minutes**. Both numbers are company settings and may change. The 5th wrong attempt already gets the lock reply.
- **While locked:** every login, **even with the right password**, gets:
  ```http
  HTTP/1.1 403 Forbidden
  Content-Type: application/problem+json

  {
    "type": "about:blank",
    "title": "Account Locked",
    "status": 403,
    "detail": "Too many failed sign-in attempts. Try again after 14:35 (25 Nov 2026, site time) or ask Admin to unlock the account.",
    "code": "ACCOUNT_LOCKED",
    "instance": "/api/v1/mobile/auth/login",
    "reason": "TOO_MANY_ATTEMPTS",
    "locked_until": "2026-11-25T10:35:00+00:00",
    "locked_until_local": "2026-11-25 14:35"
  }
  ```
- **`reason` values:**
  - `TOO_MANY_ATTEMPTS`: temporary; the worker can try again after `locked_until`.
  - `DEFAULT_PASSWORD_EXPIRED`: the default password was not changed in time. Unchanged behaviour; needs Admin.
  - `LOCKED`: any other lock; needs Admin.
- **Resetting:** a successful login resets the count. Admin can unlock early from the web Users page.
- **Unknown Tally ID:** the same `401 INVALID_CREDENTIALS` as a wrong password, so the reply never shows whether an ID exists.

**The app must:**
- Show `detail` as the message on `403 ACCOUNT_LOCKED`. The fixed text "Account Locked: Too many failed attempts or password expired..." can stay as a fallback when `detail` is missing.
- Remove any `429` / `Retry-After` handling for login.
- Optionally, for `reason: TOO_MANY_ATTEMPTS`, disable the Sign-in button until `locked_until`.
- The app's own 30-second local lock may stay; the server's lock is the real protection.

### 2.2 Error body: the text is in `detail`
**Before (1.1.1).** The contract's example error body showed `{"code": ..., "message": ...}`.

**Now.** The server sends RFC 7807 problem details and always has: `type`, `title`, `status`, `detail`, `code`, `instance`. Some errors add fields (for example `ACCOUNT_LOCKED` above, or `invalid_params` on `422`). There has never been a `message` key; this is a correction to the document, not a server change.

**The app must:** read the human text from `detail` and branch on `code`.

### 2.3 Push is not used in v1
**Before (1.1.1).** §7.4 said the server "may send a silent data push" `{"type": "SYNC", "latest_cursor": ..., "priority": 1}` on urgent changes, and `push_token` was sent at login and in `PUT /mobile/device`.

**Now.**
- The server sends **no push** at all (owner decision, DEC-64); the FCM sender is removed.
- `push_token` is still **accepted and stored** on `POST /mobile/auth/login` and `PUT /mobile/device`, but never used. Sending `null` or leaving it out is fine:
  ```json
  "device": {
    "device_identifier": "b6c1f8a0-9e4d-4c2a-81e3-55a2c77d1022",
    "platform": "ANDROID",
    "device_model": "Pixel 8",
    "app_version": "1.0.4",
    "os_version": "15",
    "push_token": null
  }
  ```

**The app must:**
- **Not register for push.** No Firebase Messaging setup is needed for this backend, and no notification permission prompt for push.
- **Not wait for a push.** Pick up changes the way you already do:
  - `has_pending_changes: true` in the `POST /mobile/heartbeat` reply;
  - a newer `latest_cursor` in the `POST /mobile/events/batch` reply;
  - `GET /mobile/sync/changes` when the app opens and before the morning alarm.
  Schedule changes are made at least a day ahead, and the app holds 30 days of schedule.
- Keep local notifications (arrival, departure, the morning alarm). Those are on the device and unaffected.

### 2.4 Weekly scorecard removed
**Before (1.1.1).** `GET /api/v1/mobile/me/scorecard?week_start=YYYY-MM-DD` was "reserved", and the `SCORECARD` sync entity type was "reserved".

**Now.** Both are **removed** (owner decision, DEC-63). The server never exposed the endpoint; it returns `404`.

**The app must:** not call it, not build a scorecard screen, and ignore any `SCORECARD` entity (none will be sent). `PAYROLL_SUMMARY` stays reserved; ignore it.

### 2.5 Compressed responses (gzip)
**Before.** Uncompressed.

**Now.**
- Responses of **1 KB or more** are gzip-compressed **when the request sends `Accept-Encoding: gzip`**. The live stream and file downloads are never compressed.
- Payloads, fields and status codes are identical.

**The app must:** nothing, if it uses OkHttp or Retrofit: they send the header and unpack transparently. If the app sets `Accept-Encoding` by hand, it must also unpack the body, or leave the header out.

### 2.6 Template days are real schedule items
Server v1.22.0. No field changes; behaviour only.
- **Real rows:** the server turns the Base Planner's weekly templates into real `SCHEDULE_ITEM` rows for the next 4 weeks. They arrive with real ids and `"source": "TEMPLATE"`.
- **Before:**
  ```json
  {"schedule_item_id": "<id derived from the template>", "source": "PLANNED", ...}
  ```
- **Now:**
  ```json
  {"schedule_item_id": "<real row id>", "source": "TEMPLATE", ...}
  ```
  The earlier "virtual" item for the same day arrives as `{"op": "DELETE", "entity_type": "SCHEDULE_ITEM", "entity_id": "<old id>"}`.
- **Other planner changes:** template edits and Operational Planner changes (remove, cover, restore) arrive as normal `UPSERT` and `DELETE` changes. Before, the app only saw them after a full snapshot.

**The app must:**
- Treat unknown `source` values as `PLANNED` (already in the contract) and show `TEMPLATE` items as planned work.
- Treat `DELETE` of an id it doesn't have as a no-op.

### 2.7 Device mismatch raises an Admin alert
When a login is refused with `403 DEVICE_MISMATCH`, the server now records an Admin alert: "Sign-in from another phone", one per worker per day, with the device model.

**The app must:** nothing. The reply is unchanged. The existing message "Contact Admin to reset device binding" is right, and Admin now sees the attempt.

### 2.8 Value changes with no shape change
- **Overtime:** OT2 is only for public holidays and the worker's own weekly off day; every Sunday no longer counts. `GET /mobile/me/payroll` figures differ from older test data.
- **Reassignment dates** use the site's local date (Dubai/KSA), not the server clock.
- **Absent days:** a planned day with no events is marked ABSENT after the day closes and goes to review. An Engineer can enter the times by hand when the phone was dead, and the payslip then reflects the reviewed day.
- **Example people** in the docs and the mobile proxy are the demo's mock people: worker 2001, supervisor 2701 and so on. Use the demo import (`tools/demo_data/FieldWorkerTracker_Demo_Import.xlsx`) for fixtures.

---

## 3. Worksite and camp boundaries in the app

### 3.1 Where they come from
| Entity (sync) | Endpoint | Field | Also |
|---|---|---|---|
| `JOB` (one per worksite in the worker's 30-day schedule) | `GET /api/v1/mobile/sync/snapshot`, then `GET /api/v1/mobile/sync/changes` | `boundary` | `geofence_circle`, `boundary_missing` |
| `ACCOMMODATION` (the worker's camp) | same | `boundary` | `geofence_circle` |

When Admin redraws a boundary, the app gets an `UPSERT` of that `JOB` or `ACCOMMODATION` with the new `boundary` and `geofence_circle`.

### 3.2 Format
- **Not WKT.** The field is a **GeoJSON `Polygon` object**. The server stores PostGIS `POLYGON`, SRID 4326 (WGS84), and converts it.
- **Coordinate order is `[longitude, latitude]`** (GeoJSON order), **not** lat/lng. Getting this backwards puts Dubai sites in the Indian Ocean near Somalia.
- **Rings:**
  - `coordinates[0]` is the outer ring; any further rings are holes.
  - Each ring is **closed**: its last position equals its first.
  - Up to 7 decimal places (about 1 cm).
- **Orientation:** don't rely on the order of the vertices (clockwise or counter-clockwise).
- **Missing boundary:** `boundary_missing: true` with `boundary: null` and `geofence_circle: null` means the site has no boundary yet. Show the site in the schedule, but don't register a geofence and don't draw a polygon.
- **`geofence_circle`** uses **named** keys, `{"center": {"lat": ..., "lng": ...}, "radius_m": ...}`. It is the OS geofence trigger: centroid plus the distance to the farthest vertex plus `SETTINGS.geofence_circle_radius_m`. The polygon is the real boundary for the inside/outside check.

### 3.3 Worked example
```json
{
  "job_id": "77b10011-aaaa-4f22-b888-112233445566",
  "job_number": "12A14301",
  "job_name": "Example worksite",
  "boundary": {
    "type": "Polygon",
    "coordinates": [
      [
        [55.2000000, 25.1000000],
        [55.2015000, 25.1000000],
        [55.2015000, 25.1012000],
        [55.2000000, 25.1012000],
        [55.2000000, 25.1000000]
      ]
    ]
  },
  "geofence_circle": { "center": { "lat": 25.1006, "lng": 55.20075 }, "radius_m": 480.0 },
  "boundary_missing": false
}
```
The first corner `[55.2000000, 25.1000000]` is **longitude 55.2, latitude 25.1**, which becomes `LatLng(25.1, 55.2)`. The last position repeats the first, so there are 4 distinct corners.

### 3.4 Drawing it with the Google Maps SDK for Android
```kotlin
import com.google.android.gms.maps.GoogleMap
import com.google.android.gms.maps.model.LatLng
import com.google.android.gms.maps.model.LatLngBounds
import com.google.android.gms.maps.model.Polygon
import com.google.android.gms.maps.model.PolygonOptions

/** GeoJSON ring [[lng, lat], ...] -> LatLng list, dropping the closing repeat. */
fun ringToLatLng(ring: List<List<Double>>): List<LatLng> {
    val points = ring.map { (lng, lat) -> LatLng(lat, lng) }   // swap: GeoJSON is lng, lat
    return if (points.size > 1 && points.first() == points.last()) points.dropLast(1) else points
}

fun drawBoundary(map: GoogleMap, coordinates: List<List<List<Double>>>): Polygon {
    val outer = ringToLatLng(coordinates[0])
    val options = PolygonOptions()
        .addAll(outer)
        .strokeWidth(4f)
        .strokeColor(0xFF2563EB.toInt())     // blue outline
        .fillColor(0x332563EB)               // 20 % blue fill
        .clickable(false)
    coordinates.drop(1).forEach { hole -> options.addHole(ringToLatLng(hole)) }
    return map.addPolygon(options)
}

fun fitTo(map: GoogleMap, outer: List<LatLng>, paddingPx: Int = 64) {
    val bounds = LatLngBounds.builder().apply { outer.forEach { include(it) } }.build()
    map.animateCamera(com.google.android.gms.maps.CameraUpdateFactory.newLatLngBounds(bounds, paddingPx))
}
```
- **Updating:** keep the returned `Polygon` and call `polygon.points = ...` / `polygon.holes = ...` when an `UPSERT` arrives, instead of removing and re-adding it. Remove it on a `DELETE`, or when `boundary_missing` becomes true.
- **Inside/outside check** (approach polling): use the same rings with `PolyUtil.containsLocation(point, outer, true)` from `com.google.maps.android:android-maps-utils`. A point inside a hole counts as outside. The server re-checks every event in PostGIS, so the device check only decides when to emit `ENTRY`/`PING`/`EXIT`.
- **No geocoding:** don't geocode or reverse-geocode positions on the phone for this app. The server never needs addresses from the device.

---

## 4. Google Maps SDK for Android: key setup
This is also in [runbook 08](runbooks/08-google-maps-keys.md) §6.

1. **Own key:** use a key from the **client's Google Cloud project**, created only for the Android app. It is separate from the web dashboard's browser key; never reuse that one.
2. **Application restriction:** Android apps. Add:
   - the **package name** with the **release SHA-1**: the **App signing key** certificate from the Play Console **App integrity** page, if Play App Signing is on;
   - for testing, **either** the debug SHA-1 (`./gradlew signingReport`, or `keytool -list -v -keystore ~/.android/debug.keystore -alias androiddebugkey -storepass android`) and the upload key SHA-1, **or** a separate test key restricted the same way.
3. **API restriction:** **Maps SDK for Android** only.
4. **No Map ID.**
   - Don't set `mapId` on the map, and don't enable cloud-based map styling, so map loads stay in Google's free mobile tier.
   - Use the SDK's normal `Marker` and `Polygon`.
   - For styling, use a local JSON style (`MapStyleOptions`), not a Map ID.
5. **Never commit the key.** Put it in `AndroidManifest.xml` through a build variable:
   ```xml
   <!-- AndroidManifest.xml, inside <application> -->
   <meta-data
       android:name="com.google.android.geo.API_KEY"
       android:value="${MAPS_API_KEY}" />
   ```
   ```kotlin
   // app/build.gradle.kts
   android {
       defaultConfig {
           manifestPlaceholders["MAPS_API_KEY"] =
               (project.findProperty("MAPS_API_KEY") as String?)
                   ?: System.getenv("MAPS_API_KEY")
                   ?: ""
       }
   }
   ```
   - Locally, set `MAPS_API_KEY=...` in `~/.gradle/gradle.properties` (outside the repo).
   - On CI, set the `MAPS_API_KEY` secret as an environment variable.
   - The Secrets Gradle Plugin with a git-ignored `secrets.properties` is an equally good alternative.
6. **Check:** a release build on a real phone shows the map. Logcat must not show `Authorization failure` / `API key not authorized`. A wrong SHA-1 or package name gives exactly those errors.

---

## 5. Questions
Please reply if:
- the app relies on push anywhere besides the sync nudge;
- your error handling can't read `detail`;
- you need the lockout numbers before the client confirms any change to the settings.
