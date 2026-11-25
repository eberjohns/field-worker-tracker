import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { ApiError, describeError, ensureOk, fieldLabel, problemFromBody, problemFromResponse } from "./errors";

describe("problem details", () => {
  it("reads the API's 422 with invalid_params", () => {
    const info = problemFromBody(422, {
      type: "about:blank",
      title: "Unprocessable Entity",
      status: 422,
      detail: "Request validation failed.",
      code: "VALIDATION_ERROR",
      invalid_params: [
        { field: "body.date_from", reason: "must be before date_to", type: "value_error" },
        { field: "body.entries.0.hours", reason: "must be at most 12" },
      ],
    });
    assert.equal(info.message, "Request validation failed.");
    assert.equal(info.code, "VALIDATION_ERROR");
    assert.deepEqual(info.fields, [
      { field: "Date from", reason: "must be before date_to" },
      { field: "Entries 1 hours", reason: "must be at most 12" },
    ]);
  });

  it("reads detail as an object with a message", () => {
    const info = problemFromBody(409, { detail: { message: "Plan already published", code: "PLAN_PUBLISHED" } });
    assert.equal(info.message, "Plan already published");
    assert.equal(info.code, "PLAN_PUBLISHED");
  });

  it("reads FastAPI's list of errors", () => {
    const info = problemFromBody(422, { detail: [{ loc: ["body", "work_date"], msg: "field required" }] });
    assert.equal(info.message, "Some values need attention.");
    assert.deepEqual(info.fields, [{ field: "Work date", reason: "field required" }]);
  });

  it("falls back for text and empty bodies", () => {
    assert.equal(problemFromBody(500, "Internal Server Error").message, "Internal Server Error");
    assert.equal(problemFromBody(500, null, "Could not save").message, "Could not save");
  });

  it("labels fields readably", () => {
    assert.equal(fieldLabel("query.date_to"), "Date to");
    assert.equal(fieldLabel(""), "Value");
  });
});

describe("responses", () => {
  it("parses a JSON error response", async () => {
    const res = new Response(JSON.stringify({ detail: "Worksite not found", code: "NOT_FOUND" }), { status: 404 });
    const info = await problemFromResponse(res);
    assert.equal(info.status, 404);
    assert.equal(info.message, "Worksite not found");
  });

  it("uses the status when the body is empty", async () => {
    const info = await problemFromResponse(new Response("", { status: 502, statusText: "Bad Gateway" }), "Could not load");
    assert.equal(info.message, "Could not load (502 Bad Gateway)");
  });

  it("ensureOk passes OK responses and throws ApiError otherwise", async () => {
    const ok = new Response("{}", { status: 200 });
    assert.equal(await ensureOk(ok), ok);
    await assert.rejects(
      ensureOk(new Response(JSON.stringify({ detail: "Not allowed" }), { status: 403 })),
      (err: unknown) => err instanceof ApiError && err.status === 403 && err.message === "Not allowed",
    );
  });

  it("describes anything thrown", () => {
    assert.equal(describeError(new Error("Network down")).message, "Network down");
    assert.equal(describeError({ detail: "Gone" }).message, "Gone");
    const api = new ApiError({ status: 422, code: null, message: "Bad", fields: [{ field: "A", reason: "b" }] });
    assert.deepEqual(describeError(api).fields, [{ field: "A", reason: "b" }]);
  });
});
