import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { canAddUnit, findUnitByName, unitOptions, unitPayload, type OrgUnit } from "./groupZoneUtils.ts";

const units: OrgUnit[] = [
  { id: "1", code: "151", name: "Wasl Properties" },
  { id: "2", code: "102", name: "Dr. Moopens (Aster)" },
  { id: "3", code: "999", name: "Old Group", is_active: false },
];

describe("group and zone dropdowns (DEC-60 amendment)", () => {
  it("lists active units by name with their code, plus the current one", () => {
    assert.deepEqual(unitOptions(units, null), [
      { value: "2", label: "Dr. Moopens (Aster) (102)" },
      { value: "1", label: "Wasl Properties (151)" },
    ]);
    assert.equal(unitOptions(units, "3").length, 3);
  });

  it("finds an existing unit by name ignoring case and spaces", () => {
    assert.equal(findUnitByName(units, "wasl  properties")?.id, "1");
    assert.equal(findUnitByName(units, "Wasl"), undefined);
  });

  it("sends only the name for a group, code and name for a zone", () => {
    assert.deepEqual(unitPayload("group", " Marina Parks ", "ignored", false), {
      name: "Marina Parks",
      confirm_near_match: false,
    });
    assert.deepEqual(unitPayload("zone", "Jebel Ali", " 7 ", true), {
      name: "Jebel Ali",
      confirm_near_match: true,
      code: "7",
    });
  });

  it("lets only Admin add (DEC-61)", () => {
    assert.ok(canAddUnit("ADMIN"));
    assert.ok(!canAddUnit("ENGINEER") && !canAddUnit("SUPERVISOR") && !canAddUnit(null));
  });
});
