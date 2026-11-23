import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  addOutcome,
  canAddLookup,
  displayGrade,
  filterOptions,
  optionsWithCurrent,
  sortValues,
  valueKey,
} from "./lookupUtils.ts";

describe("managed list helpers (DEC-60)", () => {
  it("compares values ignoring case and spaces, like the server", () => {
    assert.equal(valueKey("Gardener  Helper"), valueKey("gardenerhelper"));
  });

  it("sorts grades naturally, including grades above G7C", () => {
    assert.deepEqual(sortValues("grade_code", ["G10A", "G2A", "G25", "G1C", "G16A"]), [
      "G1C",
      "G2A",
      "G10A",
      "G16A",
      "G25",
    ]);
    assert.deepEqual(sortValues("staff_grade_description", ["team Leader", "Admin"]), ["Admin", "team Leader"]);
  });

  it("keeps the record's current value selectable, drops blanks and duplicates", () => {
    assert.deepEqual(optionsWithCurrent("grade_code", ["G1A", "", "g1a"], "G20A"), ["G1A", "G20A"]);
    assert.deepEqual(optionsWithCurrent("grade_code", [], null), []);
    assert.deepEqual(
      optionsWithCurrent("staff_grade_description", ["Gardener Helper"], "gardener helper"),
      ["Gardener Helper"],
    );
  });

  it("filters by typed text ignoring case and spaces", () => {
    const opts = ["Gardener Helper", "Gardener Expert", "Team Leader"];
    assert.deepEqual(filterOptions(opts, "gardenerh"), ["Gardener Helper"]);
    assert.deepEqual(filterOptions(opts, ""), opts);
  });

  it("only Admin and Engineer can add values", () => {
    assert.ok(canAddLookup("ADMIN") && canAddLookup("ENGINEER"));
    assert.ok(!canAddLookup("SUPERVISOR") && !canAddLookup(undefined));
  });

  it("reads add responses: added, duplicate, near match, error", () => {
    assert.deepEqual(addOutcome(201, { value: "G26A", warnings: [{ code: "NO_REVISION_LINE", message: "No line" }] }), {
      kind: "added",
      value: "G26A",
      warnings: ["No line"],
    });
    const dup = addOutcome(409, { code: "LOOKUP_DUPLICATE", existing: "Gardener Helper", is_active: true, detail: "x" });
    assert.equal(dup.kind, "exists");
    const near = addOutcome(422, { code: "LOOKUP_NEAR_MATCH", value: "Gardner Helper", suggestions: ["Gardener Helper"] });
    assert.ok(near.kind === "near" && near.suggestions[0] === "Gardener Helper");
    assert.deepEqual(addOutcome(422, { code: "INVALID_GRADE_CODE", detail: "Invalid grade code" }), {
      kind: "error",
      message: "Invalid grade code",
    });
  });

  it("formats the revision display suffix", () => {
    assert.equal(displayGrade("G3C", "2026"), "G3C-2026");
    assert.equal(displayGrade("G3C", null), "G3C");
  });
});
