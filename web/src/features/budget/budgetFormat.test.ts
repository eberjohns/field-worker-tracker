import { test } from "node:test";
import assert from "node:assert/strict";
import { diffClass, fmtDiff, fmtHours, fmtMoney, fmtPct, monthLabel, sumField } from "./budgetFormat.ts";

test("money and hours fields that are null (non-Admin) show a dash", () => {
  assert.equal(fmtMoney(null), "–");
  assert.equal(fmtHours(undefined), "–");
  assert.equal(fmtPct(null), "–");
});

test("formats hours, money, percentages and signed differences", () => {
  assert.equal(fmtHours("1248.000"), "1,248 h");
  assert.equal(fmtMoney("960"), "960.00");
  assert.equal(fmtPct("12.345"), "+12.3%");
  assert.equal(fmtPct(-3), "-3.0%");
  assert.equal(fmtDiff("2.5", (n) => n.toFixed(1)), "+2.5");
});

test("over plan is red, under plan green", () => {
  assert.equal(diffClass(1), "text-rose-600");
  assert.equal(diffClass(-1), "text-emerald-600");
  assert.equal(diffClass(0), "text-slate-600");
});

test("month labels and sums that ignore masked values", () => {
  assert.equal(monthLabel("2026-03-01"), "Mar 2026");
  assert.equal(sumField([{ v: "1.5" }, { v: null }, { v: 2 }], (r) => r.v), 3.5);
  assert.equal(sumField([{ v: null }], (r) => r.v), null);
});
