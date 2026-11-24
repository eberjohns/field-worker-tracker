// UI rules for the web app (Batch 10 A). Pages build on src/ui; these checks keep it that way.
// Text-based on purpose (no ESLint in this project): each rule is a regex over one line, comment
// lines are skipped, and a line ending in a `ui-rules-allow: <reason>` comment is exempt.

/** A library the ui layer wraps, and the one file allowed to import it. */
export const WRAPPED_LIBRARIES = [
  { name: "clsx", adapter: "src/ui/cn.ts", use: "cn() from src/ui" },
  { name: "tailwind-merge", adapter: "src/ui/cn.ts", use: "cn() from src/ui" },
  { name: "react-dom", adapter: "src/ui/overlay.tsx", use: "Modal, Popover or Portal from src/ui" },
];

const BROWSER_DIALOG = /(?<![\w$.])(?:window\.)?(alert|confirm|prompt)\s*\(/;
// A page's own function or variable with one of these names is not the browser's.
const OWN_DEFINITION = /\b(?:function|const|let|var)\s+(?:alert|confirm|prompt)\b/g;
const NATIVE_DATE_INPUT = /type=(?:"|'|\{\s*["'])(date|datetime-local)["']/;
const CUSTOM_OVERLAY = /\bfixed\s+inset-0\b/;
const IMPORT_FROM = /(?:\bfrom\s*|\bimport\s*\(?\s*)["']([^"']+)["']/g;

export const RULES = {
  "no-browser-dialogs": "Use useDialogs().confirm/prompt or useToast() from src/ui, not window.alert/confirm/prompt.",
  "no-native-date-input": 'Use DatePicker or DateRangePicker from src/ui, not <input type="date">.',
  "no-custom-overlay": "Use Modal (or ConfirmDialog) from src/ui, not a hand-made `fixed inset-0` overlay.",
  "no-wrapped-library-import": "This library is wrapped by src/ui; import the ui component instead.",
};

/** Files the rules look at: app source, not the ui layer itself (except for imports) or tests. */
export function inScope(path) {
  return /^src\/.*\.(ts|tsx)$/.test(path) && !/\.test\.(ts|tsx)$/.test(path) && !path.endsWith(".d.ts");
}

function isComment(line) {
  const t = line.trim();
  return t.startsWith("//") || t.startsWith("*") || t.startsWith("/*") || t.startsWith("{/*");
}

/**
 * Violations in one file: [{rule, line, text}]. `path` is relative to web/, with forward slashes.
 */
export function findViolations(path, source) {
  const out = [];
  const inUi = path.startsWith("src/ui/");
  const lines = source.split(/\r?\n/);
  lines.forEach((text, index) => {
    if (isComment(text) || /ui-rules-allow\b/.test(text)) return;
    const line = index + 1;
    const add = (rule) => out.push({ rule, line, text: text.trim() });
    if (!inUi) {
      if (BROWSER_DIALOG.test(text.replace(OWN_DEFINITION, ""))) add("no-browser-dialogs");
      if (NATIVE_DATE_INPUT.test(text)) add("no-native-date-input");
      if (CUSTOM_OVERLAY.test(text)) add("no-custom-overlay");
    }
    for (const match of text.matchAll(IMPORT_FROM)) {
      const lib = WRAPPED_LIBRARIES.find((l) => match[1] === l.name);
      if (lib && path !== lib.adapter) add("no-wrapped-library-import");
    }
  });
  return out;
}

/** Counts per file and rule: {"src/routes/X.tsx": {"no-browser-dialogs": 3}}. */
export function countByFile(violationsByFile) {
  const counts = {};
  for (const [path, violations] of Object.entries(violationsByFile)) {
    for (const v of violations) {
      counts[path] ??= {};
      counts[path][v.rule] = (counts[path][v.rule] ?? 0) + 1;
    }
  }
  return sortKeys(counts);
}

function sortKeys(obj) {
  return Object.fromEntries(
    Object.keys(obj)
      .sort()
      .map((k) => [k, typeof obj[k] === "object" ? sortKeys(obj[k]) : obj[k]]),
  );
}

/**
 * Compares counts with the baseline (the violations that existed when the rule arrived; Batch 10
 * B removes them). New violations fail; fewer than the baseline only asks for `--update`.
 */
export function compareWithBaseline(counts, baseline) {
  const added = [];
  const reduced = [];
  const paths = new Set([...Object.keys(counts), ...Object.keys(baseline)]);
  for (const path of paths) {
    const rules = new Set([...Object.keys(counts[path] ?? {}), ...Object.keys(baseline[path] ?? {})]);
    for (const rule of rules) {
      const now = counts[path]?.[rule] ?? 0;
      const allowed = baseline[path]?.[rule] ?? 0;
      if (now > allowed) added.push({ path, rule, now, allowed });
      else if (now < allowed) reduced.push({ path, rule, now, allowed });
    }
  }
  return { added, reduced };
}
