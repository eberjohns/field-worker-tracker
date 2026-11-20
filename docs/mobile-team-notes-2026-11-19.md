# Field Worker Tracker – notes for the mobile team (19 Nov 2026)

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

## Questions
Please reply if the app depends on push anywhere else, or if `detail` isn't available in your error handling.
