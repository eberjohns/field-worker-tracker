#!/usr/bin/env node
// `pnpm run check:ui` (also part of `pnpm run lint`): fails when app code adds a browser dialog,
// a native date input, a hand-made overlay, or imports a library the ui layer wraps.
// Existing violations are listed in ui-rules-baseline.json until Batch 10 B removes them;
// `--update` rewrites the baseline (only do that after removing violations, never to add them).
import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { compareWithBaseline, countByFile, findViolations, inScope, RULES } from "./ui-rules.mjs";

const webRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const baselinePath = join(webRoot, "scripts", "ui-rules-baseline.json");
const update = process.argv.includes("--update");

function walk(dir, files = []) {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) walk(full, files);
    else files.push(full);
  }
  return files;
}

const violationsByFile = {};
for (const file of walk(join(webRoot, "src"))) {
  const path = relative(webRoot, file).split(sep).join("/");
  if (!inScope(path)) continue;
  const found = findViolations(path, readFileSync(file, "utf8"));
  if (found.length) violationsByFile[path] = found;
}
const counts = countByFile(violationsByFile);

if (update) {
  writeFileSync(baselinePath, `${JSON.stringify(counts, null, 2)}\n`);
  const total = Object.values(counts).reduce((n, r) => n + Object.values(r).reduce((a, b) => a + b, 0), 0);
  console.log(`ui-rules: baseline written (${total} existing violations in ${Object.keys(counts).length} files).`);
  process.exit(0);
}

let baseline = {};
try {
  baseline = JSON.parse(readFileSync(baselinePath, "utf8"));
} catch {
  baseline = {};
}
const { added, reduced } = compareWithBaseline(counts, baseline);

if (added.length) {
  console.error("ui-rules: new violations\n");
  for (const a of added) {
    console.error(`${a.path}  ${a.rule}  (${a.now}, baseline ${a.allowed})`);
    for (const v of violationsByFile[a.path].filter((v) => v.rule === a.rule)) {
      console.error(`  ${a.path}:${v.line}  ${v.text.slice(0, 120)}`);
    }
    console.error(`  -> ${RULES[a.rule]}\n`);
  }
  console.error('A line that must stay can end with a comment: // ui-rules-allow: <reason>');
  process.exit(1);
}

const remaining = Object.values(counts).reduce((n, r) => n + Object.values(r).reduce((a, b) => a + b, 0), 0);
if (reduced.length) {
  console.log(`ui-rules: OK, ${reduced.length} baseline entries improved; run "pnpm run check:ui --update" to lock that in.`);
} else {
  console.log(`ui-rules: OK (${remaining} known violations left in the baseline).`);
}
