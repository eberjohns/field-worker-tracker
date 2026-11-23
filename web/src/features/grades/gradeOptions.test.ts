import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { displayGrade, gradeOptions } from "./gradeOptions.ts";

describe("gradeOptions", () => {
  it("sorts naturally and includes grades above G7C", () => {
    assert.deepEqual(gradeOptions(["G10A", "G2A", "G25", "G1C", "G16A"]), [
      "G1C",
      "G2A",
      "G10A",
      "G16A",
      "G25",
    ]);
  });

  it("keeps the record's current value selectable and drops blanks", () => {
    assert.deepEqual(gradeOptions(["G1A", ""], "G20A"), ["G1A", "G20A"]);
    assert.deepEqual(gradeOptions([], null), []);
  });

  it("formats the revision display suffix", () => {
    assert.equal(displayGrade("G3C", "2026"), "G3C-2026");
    assert.equal(displayGrade("G3C", null), "G3C");
  });
});
