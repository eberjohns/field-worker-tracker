// Module hooks for the web tests (Batch 10 A).
// - resolve: extensionless relative imports find .ts, .tsx or an index file, as Vite does;
// - load: .ts and .tsx are transpiled (types removed, JSX to react/jsx-runtime); .css and
//   images become empty modules, since tests render to HTML and never apply styles.
import { existsSync, statSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import ts from "typescript";

const TS_EXT = [".ts", ".tsx"];
const ASSET = /\.(css|svg|png|jpe?g|gif|webp|ico)$/;

function isFile(path) {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}

function findTs(base) {
  for (const ext of TS_EXT) if (isFile(base + ext)) return base + ext;
  for (const ext of TS_EXT) if (isFile(`${base}/index${ext}`)) return `${base}/index${ext}`;
  return null;
}

export async function resolve(specifier, context, nextResolve) {
  const relative = specifier.startsWith("./") || specifier.startsWith("../");
  if (relative && context.parentURL?.startsWith("file:")) {
    const target = new URL(specifier, context.parentURL);
    const path = fileURLToPath(target);
    if (!existsSync(path) || !isFile(path)) {
      const found = findTs(path);
      if (found) return { url: pathToFileURL(found).href, shortCircuit: true };
    }
  }
  return nextResolve(specifier, context);
}

const compilerOptions = {
  module: ts.ModuleKind.ESNext,
  target: ts.ScriptTarget.ES2022,
  jsx: ts.JsxEmit.ReactJSX,
  esModuleInterop: true,
  verbatimModuleSyntax: false,
  isolatedModules: true,
  sourceMap: false,
  inlineSourceMap: true,
};

export async function load(url, context, nextLoad) {
  if (ASSET.test(url)) {
    return { format: "module", source: "export default {};", shortCircuit: true };
  }
  if (url.startsWith("file:") && TS_EXT.some((ext) => url.endsWith(ext))) {
    const path = fileURLToPath(url);
    const source = await readFile(path, "utf8");
    const out = ts.transpileModule(source, { compilerOptions, fileName: path });
    return { format: "module", source: out.outputText, shortCircuit: true };
  }
  return nextLoad(url, context);
}
