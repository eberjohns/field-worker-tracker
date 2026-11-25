/** Dashboard pending actions (Batch 10 B): sections per role, newest-first previews, rendering. */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { renderToString } from "react-dom/server";
import {
  createMemoryHistory,
  createRootRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { ActionSection } from "./ActionSection";
import { newest, sectionsForRole } from "./actionSections";

describe("sections per role", () => {
  it("Admin sees all nine, in the owner's order", () => {
    assert.deepEqual(sectionsForRole("ADMIN"), [
      "docExpiry",
      "cover",
      "leave",
      "reassignment",
      "attendance",
      "pendingVisits",
      "boundary",
      "unassigned",
      "device",
    ]);
  });

  it("other roles see only what they can act on", () => {
    assert.deepEqual(sectionsForRole("ENGINEER"), [
      "cover",
      "leave",
      "reassignment",
      "attendance",
      "pendingVisits",
      "boundary",
      "device",
    ]);
    assert.deepEqual(sectionsForRole("SUPERVISOR"), ["cover", "pendingVisits"]);
    assert.deepEqual(sectionsForRole("WORKER"), []);
    assert.deepEqual(sectionsForRole(undefined), []);
  });
});

describe("previews", () => {
  it("keeps the 5 newest", () => {
    const items = Array.from({ length: 8 }, (_, i) => ({ id: i, created_at: `2026-11-0${i + 1}T00:00:00Z` }));
    assert.deepEqual(
      newest(items).map((x) => x.id),
      [7, 6, 5, 4, 3],
    );
  });
});

async function render(node: React.ReactNode): Promise<string> {
  const rootRoute = createRootRoute({ component: () => <>{node}</> });
  const router = createRouter({ routeTree: rootRoute, history: createMemoryHistory({ initialEntries: ["/"] }) });
  await router.load();
  return renderToString(<RouterProvider router={router} />);
}

describe("ActionSection", () => {
  it("shows the count, the rows and View all", async () => {
    const html = await render(
      <ActionSection
        title="Leave approval"
        icon={null}
        count={12}
        rows={[{ id: "a", primary: "Tally 2011", secondary: "2026-12-01 to 2026-12-03" }]}
        viewAll={{ to: "/approvals", search: { tab: "leave" } }}
        emptyText="Nothing waiting."
      />,
    );
    assert.match(html, /Leave approval/);
    assert.match(html, /aria-label="12 Leave approval"/);
    assert.match(html, /Tally 2011/);
    assert.match(html, /href="\/approvals\?tab=leave"/);
    assert.doesNotMatch(html, /Nothing waiting/);
  });

  it("shows the empty text when there is nothing to do", async () => {
    const html = await render(
      <ActionSection title="Boundary queue" icon={null} count={0} rows={[]} viewAll={{ to: "/boundaries" }} emptyText="All drawn." />,
    );
    assert.match(html, /All drawn\./);
    assert.match(html, /href="\/boundaries"/);
  });
});
