import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  addOutcome,
  canManageLists,
  displayGrade,
  optionsWithCurrent,
  selectOptions,
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

  it("marks a current value that left the list, once the list has loaded", () => {
    assert.deepEqual(selectOptions("grade_code", ["G2A", "G1A"], "G20A", true), [
      { value: "G1A", label: "G1A" },
      { value: "G2A", label: "G2A" },
      { value: "G20A", label: "G20A (not in list)" },
    ]);
    // While loading, nothing is marked.
    assert.deepEqual(selectOptions("grade_code", [], "G20A", false), [{ value: "G20A", label: "G20A" }]);
  });

  it("only Admin manages the staff type list", () => {
    assert.ok(canManageLists("ADMIN"));
    assert.ok(!canManageLists("ENGINEER") && !canManageLists("SUPERVISOR") && !canManageLists(undefined));
  });

  it("reads add responses: added, duplicate, near match, error", () => {
    const added = addOutcome(201, { value: "Fountain Technician", id: "1" });
    assert.ok(added.kind === "added" && added.value === "Fountain Technician");
    const group = addOutcome(201, { id: "g1", code: "152", name: "Marina Parks" });
    assert.ok(group.kind === "added" && group.value === "Marina Parks" && group.body.code === "152");
    const dup = addOutcome(409, { code: "LOOKUP_DUPLICATE", existing: "Gardener Helper", is_active: true, detail: "x" });
    assert.equal(dup.kind, "exists");
    const dupGroup = addOutcome(409, { code: "DUPLICATE_NAME", existing: "Emaar", existing_id: "g2", is_active: true });
    assert.ok(dupGroup.kind === "exists" && dupGroup.existingId === "g2");
    const near = addOutcome(422, { code: "LOOKUP_NEAR_MATCH", value: "Gardner Helper", suggestions: ["Gardener Helper"] });
    assert.ok(near.kind === "near" && near.suggestions[0] === "Gardener Helper");
    assert.equal(addOutcome(422, { code: "NEAR_MATCH", suggestions: ["Emaar"] }).kind, "near");
    assert.deepEqual(addOutcome(409, { code: "DUPLICATE_CODE", detail: "Zone code 2 is already used" }), {
      kind: "error",
      message: "Zone code 2 is already used",
    });
  });

  it("formats the revision display suffix", () => {
    assert.equal(displayGrade("G3C", "2026"), "G3C-2026");
    assert.equal(displayGrade("G3C", null), "G3C");
  });
});
