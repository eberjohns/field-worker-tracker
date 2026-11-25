/** The grouped menu (Batch 10 B): owner's groups and order, role hiding, titles, active item. */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { isNavItemActive, navForRole, navGroups, pageTitle } from "./nav";

const labels = (role: string | undefined) =>
  navForRole(role).map((g) => `${g.label}: ${g.items.map((i) => i.label).join(", ")}`);
const item = (label: string) => navGroups.flatMap((g) => g.items).find((i) => i.label === label)!;

describe("menu groups", () => {
  it("Admin sees every group and item in the owner's order", () => {
    assert.deepEqual(labels("ADMIN"), [
      "Overview: Dashboard, Live Map",
      "Planning: Base Planner, Operational Planner, Leave, Approvals, Staffing Gaps",
      "Workforce: Employees, Documents, Devices",
      "Sites: Worksites, Boundaries, Accommodations",
      "Time & Pay: Attendance, Pending Visits, Payroll, Salary Structures",
      "Reports: Reports, Generated Reports",
      "Admin: Master Data Import, Settings, Users & Security, Audit Logs, System",
    ]);
  });

  it("hides items and empty groups a role can't use", () => {
    const sup = labels("SUPERVISOR");
    assert.ok(sup.includes("Planning: Base Planner, Operational Planner, Leave, Staffing Gaps"), sup.join("\n"));
    assert.ok(sup.includes("Workforce: Employees"));
    assert.ok(sup.includes("Sites: Worksites, Accommodations"));
    assert.ok(sup.includes("Time & Pay: Attendance, Pending Visits"));
    assert.ok(sup.includes("Admin: System"));
    const worker = navForRole("WORKER").map((g) => g.label);
    assert.deepEqual(worker, ["Overview", "Time & Pay", "Reports", "Admin"]);
    assert.ok(!navForRole("WORKER").some((g) => g.items.length === 0));
  });

  it("shows only role-free items when signed out", () => {
    for (const g of navForRole(undefined)) for (const i of g.items) assert.equal(i.roles, undefined, i.label);
  });
});

describe("page titles", () => {
  it("uses the menu label, the tab item, or the detail page name", () => {
    assert.equal(pageTitle("/"), "Dashboard");
    assert.equal(pageTitle("/payroll"), "Payroll");
    assert.equal(pageTitle("/worksites"), "Worksites");
    assert.equal(pageTitle("/worksites", { tab: "accommodations" }), "Accommodations");
    assert.equal(pageTitle("/worksites/abc"), "Worksite");
    assert.equal(pageTitle("/employees/abc"), "Employee");
    assert.equal(pageTitle("/operational-planner"), "Operational Planner");
    assert.equal(pageTitle("/nowhere"), "Field Worker Tracker");
  });
});

describe("active item", () => {
  it("a tab or section item wins over the plain item with the same path", () => {
    assert.equal(isNavItemActive(item("Worksites"), "/worksites", {}, ""), true);
    assert.equal(isNavItemActive(item("Accommodations"), "/worksites", {}, ""), false);
    assert.equal(isNavItemActive(item("Worksites"), "/worksites", { tab: "accommodations" }, ""), false);
    assert.equal(isNavItemActive(item("Accommodations"), "/worksites", { tab: "accommodations" }, ""), true);
    assert.equal(isNavItemActive(item("Staffing Gaps"), "/operational-planner", {}, "staffing-gaps"), true);
    assert.equal(isNavItemActive(item("Operational Planner"), "/operational-planner", {}, "staffing-gaps"), false);
  });

  it("detail pages highlight their list item, and the longest matching path wins", () => {
    assert.equal(isNavItemActive(item("Employees"), "/employees/123", {}, ""), true);
    assert.equal(isNavItemActive(item("Dashboard"), "/employees/123", {}, ""), false);
    assert.equal(isNavItemActive(item("Generated Reports"), "/reports/generated", {}, ""), true);
    assert.equal(isNavItemActive(item("Reports"), "/reports/generated", {}, ""), false);
  });
});
