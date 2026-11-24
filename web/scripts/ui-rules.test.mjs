import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { compareWithBaseline, countByFile, findViolations, inScope } from "./ui-rules.mjs";

const rules = (path, source) => findViolations(path, source).map((v) => v.rule);

describe("ui-rules", () => {
  it("flags browser dialogs, bare or on window", () => {
    assert.deepEqual(rules("src/routes/A.tsx", 'if (!window.confirm("Delete?")) return;'), ["no-browser-dialogs"]);
    assert.deepEqual(rules("src/routes/A.tsx", 'alert("Saved");'), ["no-browser-dialogs"]);
    assert.deepEqual(rules("src/routes/A.tsx", 'const reason = prompt ("Why?");'), ["no-browser-dialogs"]);
  });

  it("does not flag the ui dialogs or local names", () => {
    assert.deepEqual(rules("src/routes/A.tsx", 'await dialogs.confirm({ title: "x" });'), []);
    assert.deepEqual(rules("src/routes/A.tsx", "const confirm = async () => true;"), []);
    assert.deepEqual(rules("src/routes/A.tsx", "function confirm(x) {}"), []);
    assert.deepEqual(rules("src/routes/A.tsx", "onConfirm(text)"), []);
    assert.deepEqual(rules("src/routes/A.tsx", '// window.confirm("old")'), []);
  });

  it("flags native date inputs and hand-made overlays outside src/ui", () => {
    assert.deepEqual(rules("src/routes/A.tsx", '<input type="date" value={d} />'), ["no-native-date-input"]);
    assert.deepEqual(rules("src/routes/A.tsx", "<input type={'datetime-local'} />"), ["no-native-date-input"]);
    assert.deepEqual(rules("src/routes/A.tsx", '<div className="fixed inset-0 bg-black/40">'), ["no-custom-overlay"]);
    assert.deepEqual(rules("src/ui/Modal.tsx", '<div className="fixed inset-0 z-fw-modal">'), []);
    assert.deepEqual(rules("src/routes/A.tsx", '<input type="time" />'), []);
  });

  it("allows wrapped libraries only in their adapter", () => {
    assert.deepEqual(rules("src/routes/A.tsx", 'import clsx from "clsx";'), ["no-wrapped-library-import"]);
    assert.deepEqual(rules("src/ui/Button.tsx", 'import { twMerge } from "tailwind-merge";'), ["no-wrapped-library-import"]);
    assert.deepEqual(rules("src/ui/cn.ts", 'import { twMerge } from "tailwind-merge";'), []);
    assert.deepEqual(rules("src/routes/A.tsx", 'import { createPortal } from "react-dom";'), ["no-wrapped-library-import"]);
    assert.deepEqual(rules("src/main.tsx", 'import ReactDOM from "react-dom/client";'), []);
  });

  it("honours ui-rules-allow", () => {
    assert.deepEqual(rules("src/routes/A.tsx", 'alert("x"); // ui-rules-allow: legacy print view'), []);
  });

  it("skips tests and type declarations", () => {
    assert.equal(inScope("src/routes/A.tsx"), true);
    assert.equal(inScope("src/ui/dates.test.ts"), false);
    assert.equal(inScope("src/api/schema.d.ts"), false);
  });

  it("ratchets against the baseline", () => {
    const counts = countByFile({
      "src/routes/A.tsx": [
        { rule: "no-browser-dialogs", line: 1, text: "" },
        { rule: "no-browser-dialogs", line: 2, text: "" },
      ],
      "src/routes/B.tsx": [{ rule: "no-custom-overlay", line: 1, text: "" }],
    });
    const baseline = { "src/routes/A.tsx": { "no-browser-dialogs": 3 }, "src/routes/C.tsx": { "no-custom-overlay": 1 } };
    const { added, reduced } = compareWithBaseline(counts, baseline);
    assert.deepEqual(
      added.map((a) => a.path),
      ["src/routes/B.tsx"],
    );
    assert.deepEqual(reduced.map((r) => r.path).sort(), ["src/routes/A.tsx", "src/routes/C.tsx"]);
  });
});
