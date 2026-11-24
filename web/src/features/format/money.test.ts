import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { currencyForCountry, formatAmount, formatMoney } from "./money.ts";

describe("money formatting (v1.16.0)", () => {
  it("maps the country to its currency", () => {
    assert.equal(currencyForCountry("AE"), "AED");
    assert.equal(currencyForCountry("sa"), "SAR");
    assert.equal(currencyForCountry(null), "AED");
  });

  it("formats amounts with the currency, never a dollar sign", () => {
    assert.equal(formatMoney(1234.5, "AED"), "AED 1,234.50");
    assert.equal(formatMoney("960", "SAR"), "SAR 960.00");
    assert.equal(formatMoney(-12, "AED"), "AED -12.00");
    assert.equal(formatMoney(0, null), "AED 0.00");
    assert.ok(!formatMoney(5, "AED").includes("$"));
  });

  it("shows a dash when there is no amount", () => {
    assert.equal(formatMoney(null, "AED"), "–");
    assert.equal(formatMoney("", "AED"), "–");
    assert.equal(formatMoney("abc", "AED"), "–");
    assert.equal(formatAmount(undefined), "–");
  });
});
