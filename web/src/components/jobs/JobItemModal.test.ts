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

import {
  draftProblem,
  draftReady,
  draftToPayload,
  duplicateCodes,
  duplicateDraft,
  emptyDraft,
  nextSubItemCode,
  rowError,
} from "./jobItemUtils.ts";

describe("Job item drafts (Batch 5.1 B wizard)", () => {
  it("numbers sub-items A, B … Z, AA and fills gaps first", () => {
    assert.equal(nextSubItemCode([]), "A");
    assert.equal(nextSubItemCode(["A", "b"]), "C");
    assert.equal(nextSubItemCode(["A", "C"]), "B");
    assert.equal(nextSubItemCode(["01", "A"]), "B");
    const all = Array.from({ length: 26 }, (_, i) => String.fromCharCode(65 + i));
    assert.equal(nextSubItemCode(all), "AA");
    assert.equal(nextSubItemCode([...all, "AA"]), "AB");
  });

  it("starts empty for staff type and grade, with the contract dates", () => {
    const d = emptyDraft("A", "2026-01-01", "2026-12-31");
    assert.equal(d.staff_grade_description, "");
    assert.equal(d.planned_grade_code, "");
    assert.equal(d.start_date, "2026-01-01");
    assert.equal(d.end_date, "2026-12-31");
    assert.equal(draftReady(d), false);
    assert.equal(draftProblem(d), "a staff type");
  });

  it("duplicates a row under a new code without sharing the weekday list", () => {
    const a = { ...emptyDraft("A", "2026-01-01"), staff_grade_description: "Gardener Helper" };
    const b = duplicateDraft(a, "B");
    b.weekday_pattern.push("SUN");
    assert.equal(b.sub_item_code, "B");
    assert.equal(b.staff_grade_description, "Gardener Helper");
    assert.equal(a.weekday_pattern.includes("SUN"), false);
  });

  it("builds the API body; weekdays only for weekly items", () => {
    const d = {
      ...emptyDraft(" C ", "2026-01-01"),
      staff_grade_description: "Gardener Helper",
      planned_grade_code: "G1A",
      hours_per_occurrence_per_staff: "8.5",
    };
    assert.equal(draftReady(d), true);
    const p = draftToPayload(d);
    assert.equal(p.sub_item_code, "C");
    assert.equal(p.hours_per_occurrence_per_staff, 8.5);
    assert.deepEqual(p.weekday_pattern, ["MON", "TUE", "WED", "THU", "FRI", "SAT"]);
    assert.equal(p.end_date, null);
    assert.equal(p.break_override_minutes, null);
    assert.equal(draftToPayload({ ...d, frequency_unit: "MONTH" }).weekday_pattern, null);
    assert.equal(draftProblem({ ...d, end_date: "2025-12-31" }), "an end date after the start");
  });

  it("finds repeated sub-item codes ignoring case and spaces", () => {
    const rows = ["A", " a", "B"].map((c) => emptyDraft(c, "2026-01-01"));
    assert.deepEqual(duplicateCodes(rows), ["A"]);
  });

  it("points create errors at the wizard step, row and field", () => {
    assert.deepEqual(
      rowError({
        code: "UNKNOWN_GRADE_CODE",
        detail: "Job item 2 (B): Grade code 'G99Z' has no line in an active salary revision.",
        field: "job_items[1].planned_grade_code",
        row: 1,
      }),
      {
        step: 2,
        row: 1,
        field: "planned_grade_code",
        message: "Job item 2 (B): Grade code 'G99Z' has no line in an active salary revision.",
      },
    );
    const schema = rowError({
      code: "VALIDATION_ERROR",
      detail: "Request validation failed.",
      invalid_params: [{ field: "body.job_items.2.required_staff_count", reason: "too small" }],
    });
    assert.equal(schema.step, 2);
    assert.equal(schema.row, 2);
    assert.equal(schema.field, "required_staff_count");
    const ws = rowError({ code: "DUPLICATE_JOB_NUMBER", detail: "exists", field: "job_number" });
    assert.deepEqual([ws.step, ws.row, ws.field], [1, null, "job_number"]);
    assert.equal(rowError({ detail: "Supervisor: not a supervisor", field: "supervisor_ids" }).step, 1);
  });
});
