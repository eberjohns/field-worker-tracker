import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  addDays,
  addMonths,
  addMonthsToIso,
  daysInMonth,
  formatDisplayDate,
  formatRange,
  inRange,
  isValidIso,
  isWithin,
  monthGrid,
  moveByKey,
  parseUserDate,
  rangeSelect,
  todayIso,
  weekdayHeaders,
  weekdayIndex,
} from "./dates";

describe("ISO dates", () => {
  it("accepts real dates and rejects impossible ones", () => {
    assert.equal(isValidIso("2026-11-25"), true);
    assert.equal(isValidIso("2028-02-29"), true);
    assert.equal(isValidIso("2026-02-29"), false);
    assert.equal(isValidIso("2026-13-01"), false);
    assert.equal(isValidIso("25/11/2026"), false);
    assert.equal(isValidIso(""), false);
    assert.equal(isValidIso(null), false);
  });

  it("adds days across month and year ends without time-zone drift", () => {
    assert.equal(addDays("2026-11-30", 1), "2026-12-01");
    assert.equal(addDays("2026-12-31", 1), "2027-01-01");
    assert.equal(addDays("2026-03-01", -1), "2026-02-28");
    assert.equal(addDays("2026-10-25", 7), "2026-11-01");
  });

  it("adds months, clamping the day to the month's length", () => {
    assert.deepEqual(addMonths({ year: 2026, month: 12 }, 1), { year: 2027, month: 1 });
    assert.deepEqual(addMonths({ year: 2026, month: 1 }, -1), { year: 2025, month: 12 });
    assert.equal(addMonthsToIso("2026-01-31", 1), "2026-02-28");
    assert.equal(addMonthsToIso("2028-01-31", 1), "2028-02-29");
    assert.equal(daysInMonth({ year: 2026, month: 2 }), 28);
  });

  it("knows the weekday (0 = Monday)", () => {
    assert.equal(weekdayIndex("2026-11-25"), 2); // Wednesday
    assert.equal(weekdayIndex("2026-11-01"), 6); // Sunday
  });

  it("uses the browser's local day for today", () => {
    assert.equal(todayIso(new Date(2026, 10, 25, 23, 59)), "2026-11-25");
  });
});

describe("display and typing", () => {
  it("shows dates the en-GB way", () => {
    assert.equal(formatDisplayDate("2026-11-25"), "25 Nov 2026");
    assert.equal(formatDisplayDate("2026-11-25", { weekday: true }), "Wed, 25 Nov 2026");
    assert.equal(formatDisplayDate(""), "");
  });

  it("formats ranges", () => {
    assert.equal(formatRange("2026-11-01", "2026-11-07"), "1 Nov 2026 – 7 Nov 2026");
    assert.equal(formatRange("2026-11-01", "2026-11-01"), "1 Nov 2026");
    assert.equal(formatRange("2026-11-01", ""), "From 1 Nov 2026");
    assert.equal(formatRange("", "2026-11-07"), "Until 7 Nov 2026");
    assert.equal(formatRange("", ""), "");
  });

  it("reads typed dates day first", () => {
    assert.equal(parseUserDate("25/11/2026"), "2026-11-25");
    assert.equal(parseUserDate("5/1/2026"), "2026-01-05");
    assert.equal(parseUserDate("25-11-2026"), "2026-11-25");
    assert.equal(parseUserDate("25.11.26"), "2026-11-25");
    assert.equal(parseUserDate("2026-11-25"), "2026-11-25");
    assert.equal(parseUserDate("25 Nov 2026"), "2026-11-25");
    assert.equal(parseUserDate("25 november 2026"), "2026-11-25");
    assert.equal(parseUserDate(" 1 Dec 2026 "), "2026-12-01");
  });

  it("rejects text that is not a date", () => {
    assert.equal(parseUserDate("31/02/2026"), null);
    assert.equal(parseUserDate("11/25/2026"), null);
    assert.equal(parseUserDate("25 Foo 2026"), null);
    assert.equal(parseUserDate("tomorrow"), null);
    assert.equal(parseUserDate(""), null);
  });

  it("checks min and max", () => {
    assert.equal(isWithin("2026-11-25", "2026-11-01", "2026-11-30"), true);
    assert.equal(isWithin("2026-10-31", "2026-11-01", null), false);
    assert.equal(isWithin("2026-12-01", null, "2026-11-30"), false);
  });
});

describe("month grid", () => {
  it("has six Monday-first weeks covering the month", () => {
    const grid = monthGrid({ year: 2026, month: 11 });
    assert.equal(grid.length, 6);
    assert.ok(grid.every((w) => w.length === 7));
    assert.equal(grid[0][0].iso, "2026-10-26");
    assert.equal(grid[0][0].inMonth, false);
    assert.equal(grid[0][6].iso, "2026-11-01");
    assert.equal(grid[0][6].inMonth, true);
    assert.equal(grid[5][6].iso, "2026-12-06");
    assert.equal(grid.flat().filter((c) => c.inMonth).length, 30);
  });

  it("can start the week on Sunday", () => {
    const grid = monthGrid({ year: 2026, month: 11 }, 6);
    assert.equal(grid[0][0].iso, "2026-11-01");
    assert.deepEqual(weekdayHeaders(6).slice(0, 2), ["Sun", "Mon"]);
  });
});

describe("range selection", () => {
  it("first click starts, second click ends, in either order", () => {
    let r = rangeSelect({ from: null, to: null }, "2026-11-10");
    assert.deepEqual(r, { from: "2026-11-10", to: null });
    r = rangeSelect(r, "2026-11-03");
    assert.deepEqual(r, { from: "2026-11-03", to: "2026-11-10" });
    r = rangeSelect(r, "2026-11-20");
    assert.deepEqual(r, { from: "2026-11-20", to: null });
  });

  it("knows the days inside a range", () => {
    const r = { from: "2026-11-03", to: "2026-11-10" };
    assert.equal(inRange("2026-11-03", r), true);
    assert.equal(inRange("2026-11-11", r), false);
    assert.equal(inRange("2026-11-05", { from: "2026-11-03", to: null }), false);
  });
});

describe("calendar keys", () => {
  it("moves by day, week, month and to the week's ends", () => {
    assert.equal(moveByKey("2026-11-25", "ArrowLeft"), "2026-11-24");
    assert.equal(moveByKey("2026-11-25", "ArrowDown"), "2026-12-02");
    assert.equal(moveByKey("2026-11-25", "PageUp"), "2026-10-25");
    assert.equal(moveByKey("2026-11-25", "Home"), "2026-11-23");
    assert.equal(moveByKey("2026-11-25", "End"), "2026-11-29");
    assert.equal(moveByKey("2026-11-25", "a"), null);
  });
});
