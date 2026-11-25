# Field Worker Tracker – notes for the mobile team (19 Nov 2026)

> **Superseded by [`mobile-handover-v1.md`](mobile-handover-v1.md) (25 Nov 2026)**, which collects these notes and every later change. Kept for history.

Backend changes coming in the next release, and what they mean for the app. Contract reference: `docs/09-mobile-sync-contract.md` (it will be updated in the same backend release).

## 1. Login lockout now enforced by the server

**Backend change:** after **5 wrong passwords** for the same Tally ID, the account is locked for **15 minutes**. A successful login resets the count. Admin can unlock the account early from the web dashboard.

**While the account is locked**, `POST /api/v1/mobile/auth/login` returns:
```json
HTTP 403
{
  "code": "ACCOUNT_LOCKED",
  "detail": "Too many failed attempts. Try again after 14:35 or contact your administrator.",
  "status": 403
}
```
The same code is also returned when the default password was not changed in time (unchanged from today).

**What the app needs to do:**
- The app already handles `ACCOUNT_LOCKED`. Please show the server's `detail` text instead of the fixed message, so the user sees when they can try again.
- The app's own 30-second lock can stay as a usability feature. The server's lock is the real protection.
- **Contract correction:** the contract mentioned `429 RATE_LIMITED` with a `Retry-After` header for login. That is being removed; the server uses `403 ACCOUNT_LOCKED` as above. No `Retry-After` handling is needed for login.

## 2. No push notifications in v1

**Backend change:** the server will **not send FCM push messages** in v1. That includes the optional silent "SYNC" nudge in contract §7.4.

**What the app needs to do:**
- Keep using the normal check-ins to pick up changes: app open, `POST /mobile/heartbeat`, and the `latest_cursor` / `has_pending_changes` in responses, followed by `GET /mobile/sync/changes`. This is the path you have already tested.
- Make sure the app syncs **at least once a day** (the operational expectation). Schedule changes are made at least one day in advance, and the app already holds 30 days of schedule.
- `push_token` in `PUT /mobile/device` stays optional. You can keep sending it or send `null`; the server stores it but does not use it in v1.

## 3. Weekly scorecard dropped

`GET /api/v1/mobile/me/scorecard` and the `SCORECARD` sync entity (both marked "reserved") are **removed from the contract**. Please don't build them.

## 4. No API changes, but values may differ

- **Overtime:** OT2 now applies only on public holidays and the worker's own weekly off day. Previously every Sunday counted as OT2. The shape of `GET /mobile/me/payroll` is unchanged, but OT1/OT2 figures will differ from earlier test data.
- **Reassignment dates:** the server now uses the site's local date (Dubai/KSA) instead of the server clock. The app needs no change.
- **Example people (20 Nov, Batch 5.3a):** the example names and Tally IDs in `docs/09-mobile-sync-contract.md`, `docs/18-mobile-integration-guide.md` and `tools/mobile-proxy` now use the demo's mock people (for example worker 2001 Ravi Varghese, supervisor 2701 Salman Javed) instead of 1193 and 1017. No fields, types or endpoints changed. If your test fixtures use 1193, switch to the demo import (`tools/demo_data/FieldWorkerTracker_Demo_Import.xlsx`).
- **Compressed responses (24 Nov, v1.19.0):** the server now gzips responses of 1 KB or more **when the request sends `Accept-Encoding: gzip`**. OkHttp and Retrofit send that header and unpack the response by themselves, so the app needs no change; payloads, fields and status codes are the same. If the app sets `Accept-Encoding` by hand, it must also unpack the body (or leave the header out). Responses without that header are not compressed. The live stream and file downloads are not compressed.
- **Planned days become real schedule items (25 Nov, v1.22.0).** The server now turns Base Planner templates into real schedule rows for the next 4 weeks. For the app:
  - `SCHEDULE_ITEM` changes arrive with real ids for those days. Their `source` is `TEMPLATE`; the contract says unknown values are treated as `PLANNED`, so show them as planned work.
  - The "virtual" blueprint item the app held for the same day (an id derived from the template) is sent as a `DELETE` op when the real row replaces it. Deleting an id the app doesn't have must stay a no-op.
  - Rows removed because a template changed arrive as `DELETE` ops.
  - Changes made in the Operational Planner (remove, cover, restore) now reach the phones as normal `SCHEDULE_ITEM` changes; before, the app saw them only after a full snapshot.
  - No fields, types or endpoints changed.
- **Absent days (25 Nov, v1.22.0):** a planned day with no events from the phone is marked ABSENT after the day ends and goes to review. A supervisor's Engineer can enter the day's times by hand when the phone was dead; the worker's payroll view then reflects the reviewed day. No app change.

## Questions
Please reply if the app depends on push anywhere else, or if `detail` isn't available in your error handling.
