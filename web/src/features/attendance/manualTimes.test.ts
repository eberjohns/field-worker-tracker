import { test } from "node:test";
import assert from "node:assert/strict";
import { toHhMm, validateManualTimes, type ManualTimesForm } from "./manualTimes";

const ok: ManualTimesForm = {
  firstSiteEntry: "07:00",
  lastSiteExit: "15:30",
  accommodationDeparture: "",
  accommodationReturn: "",
  reason: "Phone battery died",
};

test("toHhMm trims seconds and pads hours", () => {
  assert.equal(toHhMm("06:00:00"), "06:00");
  assert.equal(toHhMm("6:05"), "06:05");
  assert.equal(toHhMm(null), "");
  assert.equal(toHhMm("later"), "");
});

test("valid times have no errors", () => {
  assert.deepEqual(validateManualTimes(ok), {});
  assert.deepEqual(
    validateManualTimes({ ...ok, accommodationDeparture: "06:00", accommodationReturn: "16:30" }),
    {}
  );
});

test("exit must follow entry, and a reason is required", () => {
  const e = validateManualTimes({ ...ok, lastSiteExit: "07:00", reason: "  " });
  assert.ok(e.lastSiteExit);
  assert.ok(e.reason);
});

test("accommodation times come in pairs around the site times", () => {
  assert.ok(validateManualTimes({ ...ok, accommodationDeparture: "06:00" }).accommodationReturn);
  assert.ok(validateManualTimes({ ...ok, accommodationReturn: "16:00" }).accommodationDeparture);
  const late = validateManualTimes({ ...ok, accommodationDeparture: "08:00", accommodationReturn: "15:00" });
  assert.ok(late.accommodationDeparture);
  assert.ok(late.accommodationReturn);
});
