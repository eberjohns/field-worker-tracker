/**
 * The /dev/ui gallery (Batch 10 A): every section renders, and every component the ui layer
 * exports appears in the gallery, so a new component cannot be added without showing it.
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { UiProvider } from "../ui";
import { DevUi, GALLERY_SECTIONS } from "./DevUi";

const render = () =>
  renderToStaticMarkup(
    <UiProvider>
      <DevUi />
    </UiProvider>,
  );

describe("/dev/ui gallery", () => {
  const out = render();

  it("renders every section", () => {
    for (const id of GALLERY_SECTIONS) assert.match(out, new RegExp(`id="ui-${id}"`), `section ui-${id}`);
  });

  it("renders the same markup every time (stable snapshot)", () => {
    assert.equal(render(), out);
  });

  it("shows every component the ui layer exports", () => {
    const index = readFileSync(new URL("../ui/index.ts", import.meta.url), "utf8");
    const gallery = readFileSync(new URL("./DevUi.tsx", import.meta.url), "utf8");
    const exported = [...index.matchAll(/export \{([^}]+)\}/g)]
      .flatMap((m) => m[1].split(","))
      .map((s) => s.trim())
      .filter((s) => /^[A-Z]/.test(s) && !s.startsWith("type "));
    // Not visual: the error class, and pieces shown through the components that use them.
    const notVisual = new Set(["ApiError", "Field", "FieldErrorList", "Popover", "UiProvider"]);
    const missing = exported.filter((name) => !notVisual.has(name) && !new RegExp(`<${name}[\\s>/]`).test(gallery));
    assert.deepEqual(missing, []);
  });
});
