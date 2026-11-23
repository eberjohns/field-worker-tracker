import { describe, it } from "node:test";
import assert from "node:assert/strict";

import { formatApiError, buildJobItemPayload } from "./jobItemUtils.ts";

describe("JobItemModal Validation and Error Display", () => {
  it("formats FastAPI 422 invalid_params into readable <field>: <message> output", () => {
    const errData = {
      type: "about:blank",
      title: "Unprocessable Entity",
      status: 422,
      detail: "Request validation failed.",
      invalid_params: [
        {
          field: "body.staff_grade_description",
          reason:
            "Value error, Staff grade description 'GARDENER' is not in the controlled list. Must be one of: Admin, Commercial - QS, ...",
        },
        {
          field: "body.start_date",
          reason: "Field required",
        },
      ],
    };

    const formatted = formatApiError(errData);
    assert.ok(
      formatted.includes(
        "staff_grade_description: Staff grade description 'GARDENER' is not in the controlled list"
      ),
      "Should format field and reason clearly without [object Object]"
    );
    assert.ok(
      formatted.includes("start_date: Field required"),
      "Should include second validation error"
    );
    assert.ok(
      !formatted.includes("[object Object]"),
      "Should never render [object Object]"
    );
  });

  it("formats standard FastAPI 422 detail array into readable <field>: <message>", () => {
    const errData = {
      detail: [
        { loc: ["body", "start_date"], msg: "Field required" },
        { loc: ["body", "planned_grade_code"], msg: "Field required" },
      ],
    };

    const formatted = formatApiError(errData);
    assert.equal(
      formatted,
      "start_date: Field required\nplanned_grade_code: Field required"
    );
  });

  it("preserves standard string error details", () => {
    const errData = { detail: "Worksite not found." };
    assert.equal(formatApiError(errData), "Worksite not found.");

    const genericErr = { message: "Network connection lost." };
    assert.equal(formatApiError(genericErr), "Network connection lost.");
  });

  it("buildJobItemPayload formats all required fields cleanly for API submission", () => {
    const payload = buildJobItemPayload({
      subItemCode: "SUB-01",
      sgd: "Gardener Expert",
      plannedGrade: "G2A",
      startDate: "2026-11-01",
      endDate: "2027-10-31",
      frequencyUnit: "WEEK",
      occurrencesPerPeriod: 6,
      periodInterval: 1,
      selectedWeekdays: ["MON", "TUE", "WED", "THU", "FRI", "SAT"],
      requiredStaff: 4,
      hoursPerOccurrence: 8,
      deploymentType: "PERMANENT",
      breakOverride: 30,
    });

    assert.equal(payload.sub_item_code, "SUB-01");
    assert.equal(payload.staff_grade_description, "Gardener Expert");
    assert.equal(payload.planned_grade_code, "G2A");
    assert.equal(payload.start_date, "2026-11-01");
    assert.equal(payload.end_date, "2027-10-31");
    assert.equal(payload.frequency_unit, "WEEK");
    assert.equal(payload.occurrences_per_period, 6);
    assert.equal(payload.required_staff_count, 4);
    assert.equal(payload.hours_per_occurrence_per_staff, 8);
    assert.equal(payload.deployment_type, "PERMANENT");
    assert.equal(payload.break_override_minutes, 30);
  });
});
