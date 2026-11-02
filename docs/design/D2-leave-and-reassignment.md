# D2 - Leave, temporary reassignment and the approvals inbox

Users: Supervisor (records leave, requests changes), Superintendent (requests changes), Engineer (approves), Admin (everything). Rules: `04-scheduling-engine.md` section 9, BR-SC-04/05.

## Leave flow
1. The worker asks the supervisor (outside the system).
2. **Supervisor records the request**: worker, type (annual, sick, unpaid, emergency, other), dates, reason -> status REQUESTED.
3. **Engineer approves or rejects** (Approvals inbox). Reject needs a reason.
4. On approval: the worker's assignments in those dates become **TO BE COVERED** slots; an alert goes to the supervisor and engineer ("3 days to cover"); the worker's phone shows LEAVE for those days.
5. Cover is arranged with a temporary reassignment (below). Alerts repeat daily until every slot is covered or the date passes.
6. Leave never changes pay. **Leave taken** is counted per worker, type and year (shown on the worker profile and in a summary); no balances.
Edge cases: overlapping leave is rejected; leave in the past can be recorded by Admin/Engineer; cancelling approved leave restores slots (cover requests stay but are flagged); leave on a public holiday or weekly off does not create slots.

## Temporary reassignment (exception to the plan, for specific dates)
**When it is used** (scenarios): worker on leave; weekly-off conflict; a job needs more people that day; a priority job needs a worker moved; customer closes the site; Ramadan/summer capacity shortfall; a driver or technician is unavailable; training or other duty. Permanent changes (leaver, new joiner) are done in the Year plan instead.
**Types**
| Type | Meaning | Effect on the plan |
|---|---|---|
| REPLACE | Worker B takes worker A's assignment | A's row REASSIGNED, B gets a row (origin EXCEPTION) |
| MOVE | Worker A goes to another site that day | A's row REASSIGNED, new row at the other item |
| ADD | Extra worker on a job | new row |
| CANCEL | No work that day (customer closed, weather) | rows CANCELLED, shown as such |
**Request**: requested by Supervisor, Superintendent, Engineer or Admin; must be **at least 3 days ahead** (setting); fields: type, date or range, original worker/slot, new worker or site, reason category and note. A live preview shows the worker hours after the change and warnings (over standard hours, grade group, PERMANENT conflict, leave).
**Approval**: an Engineer (scope) approves or rejects; an Engineer/Admin request can be approved by the same person. Status: PENDING -> APPROVED / REJECTED / CANCELLED / EXPIRED (not decided by the work date).
**Effect on approval**: rows written, originals kept in history, sync to both workers' phones, notifications to the requester, both workers' supervisors, and the driver if a transport run changes. If approval arrives too late (less than the notice period) it is still allowed but flagged `LATE_APPROVAL`.
**Representation in the UI**: a coloured corner badge on the roster cell ("Cover: B for A - leave", hover shows requester, approver, reason); the original assignment stays visible struck through in history. The Coverage view shows covered slots in green with the cover worker, uncovered ones in red.

## TO BE COVERED slots and alerts
Slot = a standing assignment day with no available worker (leave, weekly off). Listed in a **Cover needed** list (filters: date range, supervisor, site, days to go) with a one-click "Request reassignment" that pre-fills the slot. No automatic relief logic (client decision).

## Approvals inbox
```
Approvals (12)   [Leave 3] [Reassignments 4] [Overtime / variation 5]   Filter: supervisor, date
 Leave  Cletus G.  10-24 Nov  annual   requested by Shakir      [Approve] [Reject]
 Reassign REPLACE Y -> W  Wed 4 Nov  12A14301 A  reason: leave   requested by Shakir  hours: W 9/8  [Approve] [Reject]
 Attendance rows needing review (variation / flags / overtime)   [Select all] [Approve selected]
```
Engineers see only their scope; Admin sees all. Approving or rejecting records user, time and note. Bulk approve for attendance rows. Notification badge in the top bar; email/push optional through adapters.

## Acceptance
Leave created -> approved -> slots appear -> reassignment requested at least 3 days ahead -> approved -> phone syncs; a request under 3 days is refused; rejection needs a reason; history keeps originals; leave-taken count correct.
