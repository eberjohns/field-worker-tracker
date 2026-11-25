import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { cn } from "./cn";
import { nextEnabledIndex } from "./keyboard";
import { formatNumberInput, parseNumberInput } from "./numbers";
import { computePosition } from "./overlay";
import { defaultDuration, makeToast, MAX_TOASTS, toastReducer, type ToastItem } from "./toastStore";

describe("cn", () => {
  it("lets later classes win, including the token classes", () => {
    assert.equal(cn("px-2", "px-4"), "px-4");
    assert.equal(cn("text-fw-text", "text-fw-sm"), "text-fw-text text-fw-sm");
    assert.equal(cn("text-fw-sm", false, "text-fw-xs"), "text-fw-xs");
    assert.equal(cn("rounded-fw-md", "rounded-fw-lg"), "rounded-fw-lg");
  });
});

describe("nextEnabledIndex", () => {
  const items = [{}, { disabled: true }, {}, {}];
  it("skips disabled items and wraps", () => {
    assert.equal(nextEnabledIndex(items, 0, "ArrowRight"), 2);
    assert.equal(nextEnabledIndex(items, 3, "ArrowRight"), 0);
    assert.equal(nextEnabledIndex(items, 0, "ArrowLeft"), 3);
    assert.equal(nextEnabledIndex(items, 2, "Home"), 0);
    assert.equal(nextEnabledIndex(items, 0, "End"), 3);
  });
  it("uses up and down for vertical lists", () => {
    assert.equal(nextEnabledIndex(items, 0, "ArrowDown", "vertical"), 2);
    assert.equal(nextEnabledIndex(items, 0, "ArrowRight", "vertical"), null);
  });
  it("returns null when everything is disabled", () => {
    assert.equal(nextEnabledIndex([{ disabled: true }], 0, "ArrowRight"), null);
  });
});

describe("parseNumberInput", () => {
  it("keeps empty as null, not 0", () => {
    assert.deepEqual(parseNumberInput("  "), { value: null, error: null });
  });
  it("parses decimals and thousands separators", () => {
    assert.deepEqual(parseNumberInput("1,250.5"), { value: 1250.5, error: null });
    assert.deepEqual(parseNumberInput(".5"), { value: 0.5, error: null });
  });
  it("explains bad input", () => {
    assert.equal(parseNumberInput("12a").error, "Enter a number");
    assert.equal(parseNumberInput("2.5", { integer: true }).error, "Enter a whole number");
    assert.equal(parseNumberInput("13", { max: 12 }).error, "Must be at most 12");
    assert.equal(parseNumberInput("-1", { min: 0 }).error, "Must be at least 0");
  });
  it("formats values back", () => {
    assert.equal(formatNumberInput(null), "");
    assert.equal(formatNumberInput(8), "8");
    assert.equal(formatNumberInput(0.1 + 0.2), "0.3");
  });
});

describe("toasts", () => {
  const item = (id: number, title = `T${id}`): ToastItem => makeToast(id, { tone: "success", title });
  it("leave on their own except errors with field lists", () => {
    assert.equal(defaultDuration("success"), 4000);
    assert.equal(defaultDuration("warning"), 6000);
    assert.equal(defaultDuration("error"), 8000);
    assert.equal(defaultDuration("error", true), null);
    assert.equal(makeToast(1, { tone: "info", title: "x", durationMs: null }).durationMs, null);
  });
  it("keeps at most MAX_TOASTS, dropping the oldest", () => {
    let state: ToastItem[] = [];
    for (let i = 1; i <= MAX_TOASTS + 2; i += 1) state = toastReducer(state, { type: "add", toast: item(i) });
    assert.equal(state.length, MAX_TOASTS);
    assert.equal(state[0].id, 3);
  });
  it("shows the same message twice in a row once", () => {
    let state = toastReducer([], { type: "add", toast: item(1, "Saved") });
    state = toastReducer(state, { type: "add", toast: item(2, "Saved") });
    assert.equal(state.length, 1);
  });
  it("dismisses by id", () => {
    const state = toastReducer([item(1), item(2)], { type: "dismiss", id: 1 });
    assert.deepEqual(
      state.map((t) => t.id),
      [2],
    );
  });
});

describe("computePosition", () => {
  const viewport = { width: 1000, height: 800 };
  const anchor = { top: 100, bottom: 130, left: 200, right: 300, width: 100 };
  it("opens below the anchor when there is room", () => {
    const pos = computePosition(anchor, { width: 280, height: 300 }, viewport);
    assert.deepEqual(pos, { top: 136, left: 200, placement: "below" });
  });
  it("flips above when there is no room below", () => {
    const low = { top: 700, bottom: 730, left: 200, right: 300, width: 100 };
    const pos = computePosition(low, { width: 280, height: 300 }, viewport);
    assert.equal(pos.placement, "above");
    assert.equal(pos.top, 394);
  });
  it("stays inside the viewport horizontally", () => {
    const right = { top: 100, bottom: 130, left: 900, right: 990, width: 90 };
    assert.equal(computePosition(right, { width: 280, height: 100 }, viewport).left, 712);
    assert.equal(computePosition(anchor, { width: 280, height: 100 }, viewport, "bottom-end").left, 20);
  });
});
