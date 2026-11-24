/**
 * Component tests (Batch 10 A): each ui/ component rendered to HTML, checking the props that
 * pages rely on (states, labels, ARIA). Behaviour that needs a browser (focus, popovers opening)
 * is covered by the logic tests and the /dev/ui gallery.
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  AlertBanner,
  Badge,
  Button,
  Calendar,
  canConfirm,
  ConfirmDialog,
  CountBadge,
  DatePicker,
  dateInputError,
  DateRangePicker,
  EmptyState,
  IconButton,
  LookupSelect,
  Menu,
  Modal,
  NumberField,
  PageHeader,
  ScrollArea,
  Select,
  Skeleton,
  SkeletonTable,
  SkeletonText,
  TabPanel,
  Tabs,
  TextArea,
  TextField,
  Tooltip,
  UiProvider,
  useDialogs,
  useToast,
} from "./index";

const html = (el: React.ReactElement) => renderToStaticMarkup(el);
const noop = () => undefined;
const count = (s: string, needle: string | RegExp) =>
  typeof needle === "string" ? s.split(needle).length - 1 : (s.match(new RegExp(needle, "g")) ?? []).length;

describe("Button", () => {
  it("renders a type=button with the variant's classes", () => {
    const out = html(<Button variant="primary">Save</Button>);
    assert.match(out, /^<button type="button"/);
    assert.match(out, /bg-fw-primary/);
    assert.match(out, />Save<\/button>$/);
  });
  it("is busy and disabled while loading", () => {
    const out = html(<Button loading>Save</Button>);
    assert.match(out, /disabled=""/);
    assert.match(out, /aria-busy="true"/);
    assert.match(out, /animate-spin/);
  });
  it("uses the destructive colour", () => {
    assert.match(html(<Button variant="destructive">Delete</Button>), /bg-fw-danger/);
  });
  it("IconButton always has an accessible name", () => {
    const out = html(<IconButton label="Edit" icon={<span>e</span>} />);
    assert.match(out, /aria-label="Edit"/);
    assert.match(out, /title="Edit"/);
  });
});

describe("Modal", () => {
  it("renders nothing when closed", () => {
    assert.equal(html(<Modal open={false} onClose={noop} title="Edit" />), "");
  });
  it("is a labelled modal dialog with body and footer", () => {
    const out = html(
      <Modal open onClose={noop} title="Edit job item" description="From tomorrow" footer={<button>Save</button>}>
        <p>Body</p>
      </Modal>,
    );
    assert.match(out, /role="dialog"/);
    assert.match(out, /aria-modal="true"/);
    assert.match(out, /aria-labelledby="[^"]+"/);
    assert.match(out, /aria-describedby="[^"]+"/);
    assert.match(out, /Edit job item/);
    assert.match(out, /<p>Body<\/p>/);
    assert.match(out, /aria-label="Close"/);
    assert.match(out, /fw-scroll/);
  });
  it("hides the close button when not dismissible", () => {
    const out = html(<Modal open onClose={noop} title="Saving" dismissible={false} />);
    assert.doesNotMatch(out, /aria-label="Close"/);
  });
});

describe("ConfirmDialog", () => {
  it("default variant has a primary Confirm button", () => {
    const out = html(<ConfirmDialog open title="Publish?" onConfirm={noop} onCancel={noop} />);
    assert.match(out, /Publish\?/);
    assert.match(out, /bg-fw-primary[^"]*"[^>]*>Confirm</);
    assert.match(out, />Cancel</);
  });
  it("destructive variant warns and uses a red Delete button", () => {
    const out = html(<ConfirmDialog open variant="destructive" title="Delete site?" onConfirm={noop} onCancel={noop} />);
    assert.match(out, /This cannot be undone\./);
    assert.match(out, /bg-fw-danger[^"]*"[^>]*>Delete</);
  });
  it("asks for a reason when given an input", () => {
    const out = html(
      <ConfirmDialog open title="Reject" input={{ label: "Reason", multiline: true, required: true }} onConfirm={noop} onCancel={noop} />,
    );
    assert.match(out, /<textarea/);
    assert.match(out, />Reason</);
  });
  it("canConfirm requires the typed text or a reason", () => {
    assert.equal(canConfirm({}, ""), true);
    assert.equal(canConfirm({ input: { label: "Reason", required: true } }, "  "), false);
    assert.equal(canConfirm({ input: { label: "Reason", required: true } }, "Sick"), true);
    assert.equal(canConfirm({ requireText: "RESET" }, "reset"), false);
    assert.equal(canConfirm({ requireText: "RESET" }, "RESET"), true);
  });
});

describe("UiProvider", () => {
  it("renders its children and gives access to dialogs and toasts", () => {
    let seen = "";
    const Probe = () => {
      const dialogs = useDialogs();
      const toast = useToast();
      seen = `${typeof dialogs.confirm}/${typeof dialogs.prompt}/${typeof toast.success}/${typeof toast.error}`;
      return <span>child</span>;
    };
    const out = html(
      <UiProvider>
        <Probe />
      </UiProvider>,
    );
    assert.match(out, /<span>child<\/span>/);
    assert.match(out, /aria-label="Notifications"/);
    assert.equal(seen, "function/function/function/function");
  });
  it("hooks fail loudly outside the provider", () => {
    const Bad = () => {
      useToast();
      return null;
    };
    assert.throws(() => html(<Bad />), /UiProvider/);
  });
});

describe("AlertBanner", () => {
  it("errors are alerts and list field problems", () => {
    const out = html(
      <AlertBanner tone="error" title="Could not save" fields={[{ field: "Date from", reason: "required" }]}>
        Fix the fields
      </AlertBanner>,
    );
    assert.match(out, /role="alert"/);
    assert.match(out, /Could not save/);
    assert.match(out, /<li><span class="font-medium">Date from:<\/span> required<\/li>/);
  });
  it("info is a status with an optional dismiss button", () => {
    const out = html(
      <AlertBanner tone="info" onDismiss={noop}>
        Note
      </AlertBanner>,
    );
    assert.match(out, /role="status"/);
    assert.match(out, /aria-label="Dismiss"/);
  });
});

describe("Calendar", () => {
  const out = html(
    <Calendar
      value="2026-11-25"
      onSelect={noop}
      today="2026-11-20"
      min="2026-11-03"
      markers={{ "2026-11-30": { tone: "holiday", title: "Holiday" } }}
    />,
  );
  it("shows the value's month in a grid", () => {
    assert.match(out, /role="grid"/);
    assert.match(out, /aria-label="November 2026"/);
    assert.equal(count(out, 'role="gridcell"'), 42);
  });
  it("marks the selected day and today", () => {
    assert.match(out, /aria-selected="true"><button type="button" data-iso="2026-11-25"/);
    assert.match(out, /data-iso="2026-11-20" tabindex="-1" aria-label="Fri, 20 Nov 2026" aria-current="date"/);
  });
  it("only the focused day is in the tab order", () => {
    assert.equal(count(out, 'tabindex="0"'), 1);
    assert.match(out, /data-iso="2026-11-25" tabindex="0"/);
  });
  it("disables days before min and labels markers", () => {
    assert.match(out, /data-iso="2026-11-02" tabindex="-1" disabled=""/);
    assert.match(out, /aria-label="Mon, 30 Nov 2026, Holiday"/);
  });
  it("highlights a range", () => {
    const r = html(<Calendar range={{ from: "2026-11-09", to: "2026-11-11" }} onSelect={noop} today="2026-11-20" />);
    assert.equal(count(r, 'aria-selected="true"'), 2);
    assert.match(r, /data-iso="2026-11-10"[^>]*class="[^"]*bg-fw-primary-soft/);
  });
});

describe("DatePicker", () => {
  it("shows the ISO value as an en-GB date with a calendar button", () => {
    const out = html(<DatePicker label="Work date" value="2026-11-25" onChange={noop} />);
    assert.match(out, /value="25 Nov 2026"/);
    assert.match(out, /aria-label="Choose date"/);
    assert.match(out, /aria-haspopup="dialog"/);
    assert.match(out, /aria-label="Clear date"/);
  });
  it("required pickers have no clear button and show errors", () => {
    const out = html(<DatePicker value="2026-11-25" onChange={noop} required error="Pick a later day" />);
    assert.doesNotMatch(out, /Clear date/);
    assert.match(out, /aria-invalid="true"/);
    assert.match(out, /Pick a later day/);
  });
  it("dateInputError explains typed dates", () => {
    assert.equal(dateInputError("", { required: true }), "Enter a date");
    assert.equal(dateInputError("", {}), null);
    assert.equal(dateInputError("31/02/2026", {}), "Use a date like 25/11/2026");
    assert.equal(dateInputError("01/10/2026", { min: "2026-11-01" }), "On or after 1 Nov 2026");
    assert.equal(dateInputError("01/12/2026", { max: "2026-11-30" }), "On or before 30 Nov 2026");
    assert.equal(dateInputError("25/11/2026", { min: "2026-11-01", max: "2026-11-30" }), null);
  });
});

describe("DateRangePicker", () => {
  it("shows the period or a placeholder", () => {
    assert.match(
      html(<DateRangePicker value={{ from: "2026-11-01", to: "2026-11-07" }} onChange={noop} />),
      /1 Nov 2026 – 7 Nov 2026/,
    );
    assert.match(html(<DateRangePicker value={{ from: "", to: "" }} onChange={noop} />), /Choose dates/);
  });
});

describe("ScrollArea", () => {
  it("uses the thin scrollbar and the chosen axis", () => {
    assert.match(html(<ScrollArea>x</ScrollArea>), /class="fw-scroll min-h-0 overflow-y-auto overflow-x-hidden"/);
    assert.match(html(<ScrollArea axis="x">x</ScrollArea>), /overflow-x-auto/);
    assert.match(html(<ScrollArea maxHeight={160}>x</ScrollArea>), /style="max-height:160px"/);
  });
});

describe("TextField and TextArea", () => {
  it("links label, hint and error to the input", () => {
    const out = html(<TextField id="name" label="Name" required error="Too short" />);
    assert.match(out, /<label for="name"/);
    assert.match(out, /aria-invalid="true"/);
    assert.match(out, /aria-describedby="name-error"/);
    assert.match(out, /id="name-error"[^>]*role="alert"/);
  });
  it("shows the hint when there is no error", () => {
    assert.match(html(<TextField id="n" hint="Shown on the phone" />), /aria-describedby="n-hint"/);
  });
  it("TextArea renders a textarea with rows", () => {
    assert.match(html(<TextArea label="Comment" rows={4} />), /<textarea[^>]*rows="4"/);
  });
});

describe("NumberField", () => {
  it("shows the number right-aligned with its unit", () => {
    const out = html(<NumberField value={8.5} onChange={noop} suffix="h" />);
    assert.match(out, /value="8.5"/);
    assert.match(out, /inputMode="decimal"/i);
    assert.match(out, /text-right/);
    assert.match(out, />h<\/span>/);
  });
  it("shows null as an empty field", () => {
    assert.match(html(<NumberField value={null} onChange={noop} />), /value=""/);
  });
});

describe("Select", () => {
  it("renders the placeholder first, then the options", () => {
    const out = html(
      <Select
        value="SA"
        onChange={noop}
        placeholder="Any country"
        options={[
          { value: "AE", label: "UAE" },
          { value: "SA", label: "KSA" },
        ]}
      />,
    );
    assert.match(out, /<option value="">Any country<\/option><option value="AE">UAE<\/option><option value="SA" selected="">KSA<\/option>/);
  });
});

describe("LookupSelect", () => {
  it("keeps a value that left the list, marked", () => {
    const out = html(<LookupSelect listKey="grade_code" values={["G1", "G2A"]} loaded value="G9" onChange={noop} />);
    assert.match(out, /G9 \(not in list\)/);
    assert.match(out, /<option value="G1">G1<\/option>/);
  });
  it("does not mark anything before the list has loaded", () => {
    assert.doesNotMatch(html(<LookupSelect listKey="grade_code" values={[]} loaded={false} value="G9" onChange={noop} />), /not in list/);
  });
});

describe("Tabs", () => {
  const out = html(
    <Tabs
      idBase="t"
      value="b"
      onChange={noop}
      tabs={[
        { id: "a", label: "Pending", count: 3 },
        { id: "b", label: "Decided" },
        { id: "c", label: "Archived", disabled: true },
      ]}
    />,
  );
  it("is a tablist with one selected tab in the tab order", () => {
    assert.match(out, /role="tablist"/);
    assert.equal(count(out, 'role="tab"'), 3);
    assert.match(out, /id="t-tab-b" aria-selected="true" aria-controls="t-panel-b" tabindex="0"/);
    assert.match(out, /id="t-tab-a" aria-selected="false" aria-controls="t-panel-a" tabindex="-1"/);
  });
  it("shows counts and disabled tabs", () => {
    assert.match(out, />3<\/span>/);
    assert.match(out, /id="t-tab-c"[^>]*disabled=""/);
  });
  it("TabPanel points back at its tab", () => {
    assert.match(html(<TabPanel idBase="t" id="b">x</TabPanel>), /role="tabpanel" id="t-panel-b" aria-labelledby="t-tab-b"/);
  });
});

describe("Menu", () => {
  it("renders a closed menu button", () => {
    const out = html(<Menu label="Row actions" items={[{ label: "Edit", onSelect: noop }]} />);
    assert.match(out, /aria-haspopup="menu"/);
    assert.match(out, /aria-expanded="false"/);
    assert.match(out, /aria-label="Row actions"/);
    assert.doesNotMatch(out, /role="menu"/);
  });
  it("a text trigger is its own label", () => {
    const out = html(<Menu label="Export" trigger="Export" items={[]} />);
    assert.match(out, />Export<\/button>/);
    assert.doesNotMatch(out, /aria-label="Export"/);
  });
});

describe("Tooltip", () => {
  it("renders only the child until hovered or focused", () => {
    const out = html(
      <Tooltip content="Hint">
        <button>x</button>
      </Tooltip>,
    );
    assert.match(out, /<button>x<\/button>/);
    assert.doesNotMatch(out, /role="tooltip"/);
  });
});

describe("Badge and CountBadge", () => {
  it("uses the tone and an optional dot", () => {
    const out = html(
      <Badge tone="danger" dot>
        Absent
      </Badge>,
    );
    assert.match(out, /bg-fw-danger-soft/);
    assert.match(out, /rounded-full bg-fw-danger/);
  });
  it("CountBadge hides zero and caps at 99+", () => {
    assert.equal(html(<CountBadge count={0} />), "");
    assert.match(html(<CountBadge count={140} />), />99\+</);
    assert.match(html(<CountBadge count={7} />), />7</);
  });
});

describe("EmptyState", () => {
  it("shows a title, description and action", () => {
    const out = html(<EmptyState title="No reports yet" description="Pick a report" action={<button>Generate</button>} />);
    assert.match(out, /No reports yet/);
    assert.match(out, /Pick a report/);
    assert.match(out, /<button>Generate<\/button>/);
  });
});

describe("Skeleton", () => {
  it("is hidden from screen readers; the table announces Loading once", () => {
    assert.match(html(<Skeleton width={40} />), /aria-hidden="true"[^>]*style="width:40px"/);
    assert.equal(count(html(<SkeletonText lines={3} />), "h-3"), 3);
    const table = html(<SkeletonTable rows={2} columns={3} />);
    assert.match(table, /role="status" aria-label="Loading"/);
    assert.equal(count(table, "flex-1"), 6);
  });
});

describe("PageHeader", () => {
  it("has one h1 with actions and meta", () => {
    const out = html(<PageHeader title="Worksites" description="All sites" actions={<button>New</button>} meta={<span>3</span>} />);
    assert.equal(count(out, "<h1"), 1);
    assert.match(out, /Worksites<\/h1>/);
    assert.match(out, /<button>New<\/button>/);
  });
});
