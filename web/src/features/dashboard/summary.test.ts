import { describe, it } from "node:test";
import assert from "node:assert/strict";

import { mapDashboardSummary } from "./summary.ts";

// Shape returned by the backend's DashboardSummaryResponse (backend/src/fw/api/dashboard.py).
const apiResponse = {
  today_date: "2026-11-20",
  attendance: { present: 5, partial: 1, absent: 2, not_started: 3, total_scheduled: 11 },
  live_workers: { active: 4, no_recent_signal: 2, location_disabled: 1, not_scheduled: 0, total: 7 },
  pending_visits_count: 3,
  pending_visits_escalated_count: 1,
  late_arrivals_count: 2,
  overtime_hours_today: 6.5,
  open_alerts_count: 4,
  expiring_documents_count: 1,
  pending_approvals_count: 5,
  unassigned_worksites_count: 2,
};

describe("Dashboard summary mapping", () => {
  it("shows non-zero counts when there are open visits and live workers", () => {
    const cards = mapDashboardSummary(apiResponse);
    assert.equal(cards.pendingVisits.open, 3);
    assert.equal(cards.pendingVisits.escalated, 1);
    assert.equal(cards.live.active, 4);
    assert.equal(cards.live.noRecentSignal, 2);
    assert.equal(cards.live.locationDisabled, 1);
    assert.equal(cards.lateArrivals, 2);
    assert.equal(cards.overtimeHours, 6.5);
    assert.equal(cards.attendance.present, 5);
    assert.equal(cards.attendance.totalScheduled, 11);
    assert.equal(cards.unassignedWorksites, 2);
  });

  it("falls back to 0 for missing or null fields", () => {
    const cards = mapDashboardSummary({ unassigned_worksites_count: null });
    assert.equal(cards.pendingVisits.open, 0);
    assert.equal(cards.live.active, 0);
    assert.equal(cards.unassignedWorksites, 0);
    assert.equal(mapDashboardSummary(null).lateArrivals, 0);
  });

  it("does not read the old field names the API never returned", () => {
    const cards = mapDashboardSummary({
      // @ts-expect-error old, wrong shape
      pending_visits: { total_open: 9 },
      live: { active: 9 },
    });
    assert.equal(cards.pendingVisits.open, 0);
    assert.equal(cards.live.active, 0);
  });
});
