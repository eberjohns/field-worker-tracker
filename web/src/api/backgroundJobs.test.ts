import { test } from "node:test";
import assert from "node:assert/strict";
import { describeJobProgress, isActiveJob, jobPercent, pollJob, type BackgroundJob } from "./backgroundJobs.ts";

function job(over: Partial<BackgroundJob>): BackgroundJob {
  return {
    id: "j1",
    kind: "payroll_draft",
    status: "RUNNING",
    params: {},
    phase: null,
    progress_done: 0,
    progress_total: 0,
    result: null,
    error_code: null,
    error_message: null,
    created_at: "",
    started_at: null,
    finished_at: null,
    ...over,
  };
}

test("progress text and percent across the two payroll phases", () => {
  assert.equal(describeJobProgress(job({ status: "QUEUED" })), "Starting…");
  assert.equal(
    describeJobProgress(job({ phase: "employees", progress_done: 120, progress_total: 580 })),
    "Calculating employees 120 / 580",
  );
  assert.equal(jobPercent(job({ phase: "employees", progress_done: 290, progress_total: 580 })), 30);
  assert.equal(jobPercent(job({ phase: "reports", progress_done: 11, progress_total: 11 })), 100);
  assert.equal(jobPercent(job({ status: "SUCCEEDED" })), 100);
  assert.equal(isActiveJob(job({ status: "QUEUED" })), true);
  assert.equal(isActiveJob(job({ status: "FAILED" })), false);
});

test("pollJob polls until the job finishes", async () => {
  const states = [job({ status: "QUEUED" }), job({ phase: "employees" }), job({ status: "SUCCEEDED" })];
  const seen: string[] = [];
  let calls = 0;
  const fetchFn = async () => new Response(JSON.stringify(states[calls++]), { status: 200 });
  const done = await pollJob("j1", "t", (j) => seen.push(j.status), { fetchFn, intervalMs: 1 });
  assert.equal(done?.status, "SUCCEEDED");
  assert.deepEqual(seen, ["QUEUED", "RUNNING", "SUCCEEDED"]);
});

test("pollJob stops when aborted", async () => {
  const ctrl = new AbortController();
  ctrl.abort();
  const fetchFn = async () => {
    throw new Error("should not fetch");
  };
  assert.equal(await pollJob("j1", "t", () => {}, { fetchFn, signal: ctrl.signal }), null);
});
