/**
 * /dev/ui: every ui/ component in its states (Batch 10 A). Development builds only; no data, no
 * sign-in. Each section has id="ui-<name>" (the gallery test checks they all render).
 */
import React, { useState } from "react";
import { Copy, Pencil, Plus, Trash2, Users } from "lucide-react";
import {
  AlertBanner,
  ApiError,
  Badge,
  Button,
  Calendar,
  ConfirmDialog,
  CountBadge,
  DatePicker,
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
  useDialogs,
  useToast,
} from "../ui";

export const GALLERY_SECTIONS = [
  "tokens",
  "button",
  "page-header",
  "alert-banner",
  "toast",
  "modal",
  "confirm-dialog",
  "text-field",
  "number-field",
  "select",
  "lookup-select",
  "date-picker",
  "date-range-picker",
  "calendar",
  "tabs",
  "menu",
  "tooltip",
  "badge",
  "empty-state",
  "skeleton",
  "scroll-area",
] as const;

const Section: React.FC<{ id: (typeof GALLERY_SECTIONS)[number]; title: string; children: React.ReactNode }> = ({
  id,
  title,
  children,
}) => (
  <section id={`ui-${id}`} className="rounded-fw-xl border border-fw-border bg-fw-surface p-4 shadow-fw-sm">
    <h2 className="mb-3 text-fw-base font-semibold text-fw-text">{title}</h2>
    <div className="flex flex-wrap items-start gap-4">{children}</div>
  </section>
);

const Swatch: React.FC<{ name: string; className: string }> = ({ name, className }) => (
  <div className="flex w-24 flex-col gap-1">
    <div className={`h-10 rounded-fw-md border border-fw-border ${className}`} />
    <code className="text-[11px] text-fw-text-muted">{name}</code>
  </div>
);

const FIELD_ERROR = new ApiError({
  status: 422,
  code: "VALIDATION_ERROR",
  message: "Some values need attention.",
  fields: [
    { field: "Date from", reason: "must be on or before Date to" },
    { field: "Hours per day", reason: "must be at most 12" },
  ],
});

export const DevUi: React.FC = () => {
  const toast = useToast();
  const dialogs = useDialogs();
  const [modalOpen, setModalOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [lastAnswer, setLastAnswer] = useState("");
  const [name, setName] = useState("Al Wasl Park");
  const [hours, setHours] = useState<number | null>(8);
  const [grade, setGrade] = useState("G3C");
  const [staffType, setStaffType] = useState("Gardener");
  const [date, setDate] = useState("2026-11-25");
  const [emptyDate, setEmptyDate] = useState("");
  const [range, setRange] = useState({ from: "2026-11-01", to: "2026-11-07" });
  const [calendarDay, setCalendarDay] = useState("2026-12-02");
  const [tab, setTab] = useState("pending");

  return (
    <div className="min-h-screen bg-fw-bg">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 p-6">
        <PageHeader
          title="UI components"
          description="Every building block in web/src/ui and its states. Development builds only."
          meta={
            <>
              <Badge tone="primary">Batch 10 A</Badge>
              <Badge dot tone="success">
                Light theme
              </Badge>
            </>
          }
          actions={
            <>
              <Button icon={<Copy className="h-3.5 w-3.5" />}>Secondary</Button>
              <Button variant="primary" icon={<Plus className="h-3.5 w-3.5" />}>
                Primary action
              </Button>
            </>
          }
        />

        <Section id="tokens" title="Tokens (src/ui/tokens.css)">
          <Swatch name="fw-bg" className="bg-fw-bg" />
          <Swatch name="fw-surface" className="bg-fw-surface" />
          <Swatch name="fw-muted" className="bg-fw-muted" />
          <Swatch name="fw-border" className="bg-fw-border" />
          <Swatch name="fw-text" className="bg-fw-text" />
          <Swatch name="fw-primary" className="bg-fw-primary" />
          <Swatch name="fw-success" className="bg-fw-success" />
          <Swatch name="fw-warning" className="bg-fw-warning" />
          <Swatch name="fw-danger" className="bg-fw-danger" />
          <Swatch name="fw-info" className="bg-fw-info" />
          <div className="flex flex-col gap-1 text-fw-text">
            <span className="text-fw-2xl font-semibold">2xl Page title</span>
            <span className="text-fw-xl font-semibold">xl Section</span>
            <span className="text-fw-lg">lg Dialog title</span>
            <span className="text-fw-base">base Body text</span>
            <span className="text-fw-sm text-fw-text-muted">sm Secondary text</span>
            <span className="text-fw-xs text-fw-text-subtle">xs Labels and hints</span>
          </div>
        </Section>

        <Section id="button" title="Button and IconButton">
          <Button variant="primary">Primary</Button>
          <Button>Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="destructive" icon={<Trash2 className="h-3.5 w-3.5" />}>
            Delete
          </Button>
          <Button variant="primary" loading>
            Saving
          </Button>
          <Button disabled>Disabled</Button>
          <Button size="sm">Small</Button>
          <IconButton label="Edit" icon={<Pencil className="h-4 w-4" />} />
          <IconButton label="Delete" variant="destructive" icon={<Trash2 className="h-4 w-4" />} />
        </Section>

        <Section id="page-header" title="PageHeader">
          <div className="w-full rounded-fw-lg border border-dashed border-fw-border p-3">
            <PageHeader
              breadcrumbs={<span>Worksites / 22A11702</span>}
              title="Le Pont"
              description="Landscape maintenance, 3 job items"
              meta={<Badge tone="success">Active</Badge>}
              actions={<Button size="sm">Edit</Button>}
            />
          </div>
        </Section>

        <Section id="alert-banner" title="AlertBanner">
          <div className="flex w-full flex-col gap-2">
            <AlertBanner tone="info" title="Plan published">Phones receive it on their next sync.</AlertBanner>
            <AlertBanner tone="success">Saved.</AlertBanner>
            <AlertBanner tone="warning" title="Over 8 hours" onDismiss={() => undefined}>
              2007 is planned for 9 h on Tuesday.
            </AlertBanner>
            <AlertBanner tone="error" title="Could not save" fields={FIELD_ERROR.fields} action={<Button size="sm">Retry</Button>}>
              {FIELD_ERROR.message}
            </AlertBanner>
          </div>
        </Section>

        <Section id="toast" title="Toast (useToast)">
          <Button onClick={() => toast.success("Leave approved", "2017, 20-21 Oct")}>Success</Button>
          <Button onClick={() => toast.info("Sync queued")}>Info</Button>
          <Button onClick={() => toast.warning("Cover needed", "Nobody covers 22A14107 on 3 Dec")}>Warning</Button>
          <Button onClick={() => toast.error("Could not reach the server")}>Error</Button>
          <Button onClick={() => toast.error(FIELD_ERROR)}>422 with fields</Button>
        </Section>

        <Section id="modal" title="Modal">
          <Button onClick={() => setModalOpen(true)}>Open modal</Button>
          <Modal
            open={modalOpen}
            onClose={() => setModalOpen(false)}
            title="Edit job item"
            description="Changes apply from tomorrow."
            footer={
              <>
                <Button onClick={() => setModalOpen(false)}>Cancel</Button>
                <Button variant="primary" onClick={() => setModalOpen(false)}>
                  Save
                </Button>
              </>
            }
          >
            <div className="grid grid-cols-2 gap-3">
              <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} />
              <NumberField label="Hours per visit" value={hours} onChange={setHours} min={0} max={12} suffix="h" />
              <DatePicker label="Start" value={date} onChange={setDate} />
              <DatePicker label="End" value={emptyDate} onChange={setEmptyDate} min={date} />
            </div>
          </Modal>
        </Section>

        <Section id="confirm-dialog" title="ConfirmDialog (useDialogs)">
          <Button
            onClick={async () =>
              setLastAnswer(String(await dialogs.confirm({ title: "Publish the plan?", message: "Workers see it on their phones." })))
            }
          >
            Confirm
          </Button>
          <Button
            variant="destructive"
            onClick={async () =>
              setLastAnswer(
                String(
                  await dialogs.confirm({
                    title: "Delete worksite 22A14107?",
                    message: "Its job items and plans are removed.",
                    variant: "destructive",
                  }),
                ),
              )
            }
          >
            Destructive
          </Button>
          <Button
            onClick={async () =>
              setLastAnswer(
                String(
                  await dialogs.prompt({
                    title: "Reject leave",
                    confirmLabel: "Reject",
                    variant: "destructive",
                    input: { label: "Reason", multiline: true, required: true },
                  }),
                ),
              )
            }
          >
            With a reason
          </Button>
          <Button
            onClick={async () =>
              setLastAnswer(
                String(await dialogs.confirm({ title: "Reset database", variant: "destructive", requireText: "RESET", confirmLabel: "Reset" })),
              )
            }
          >
            Type to confirm
          </Button>
          <Button onClick={() => setConfirmOpen(true)}>Busy state</Button>
          <ConfirmDialog
            open={confirmOpen}
            busy={busy}
            title="Approve 12 days?"
            onCancel={() => setConfirmOpen(false)}
            onConfirm={() => {
              setBusy(true);
              setTimeout(() => {
                setBusy(false);
                setConfirmOpen(false);
              }, 1200);
            }}
          />
          <span className="self-center text-fw-xs text-fw-text-muted">Answer: {lastAnswer || "-"}</span>
        </Section>

        <Section id="text-field" title="TextField and TextArea">
          <TextField label="Name" value={name} onChange={(e) => setName(e.target.value)} fieldClassName="w-56" />
          <TextField label="Search" placeholder="Tally ID or name" leading={<Users className="h-3.5 w-3.5" />} fieldClassName="w-56" />
          <TextField label="Required" required hint="Shown on the phone" fieldClassName="w-56" />
          <TextField label="With error" defaultValue="22A" error="Job number has 8 characters" fieldClassName="w-56" />
          <TextField label="Disabled" value="Read only" disabled fieldClassName="w-56" readOnly />
          <TextArea label="Comment" placeholder="Why the day was changed" fieldClassName="w-72" />
        </Section>

        <Section id="number-field" title="NumberField">
          <NumberField label="Hours" value={hours} onChange={setHours} min={0} max={12} step={0.5} suffix="h" fieldClassName="w-40" />
          <NumberField label="Workers" value={3} onChange={() => undefined} integer min={1} fieldClassName="w-40" hint="Whole number" />
          <NumberField label="Amount" value={null} onChange={() => undefined} suffix="AED" fieldClassName="w-40" placeholder="0.00" />
          <NumberField label="Server error" value={14} onChange={() => undefined} error="Above the item's limit" fieldClassName="w-40" />
        </Section>

        <Section id="select" title="Select">
          <Select
            label="Country"
            value="AE"
            onChange={() => undefined}
            options={[
              { value: "AE", label: "United Arab Emirates" },
              { value: "SA", label: "Saudi Arabia" },
            ]}
            fieldClassName="w-56"
          />
          <Select label="Status" value="" placeholder="Any status" onChange={() => undefined} options={[{ value: "OPEN", label: "Open" }]} fieldClassName="w-56" />
          <Select label="Disabled" value="" placeholder="-" onChange={() => undefined} options={[]} disabled fieldClassName="w-56" />
        </Section>

        <Section id="lookup-select" title="LookupSelect (managed lists)">
          <LookupSelect
            listKey="grade_code"
            label="Grade"
            values={["G1", "G2A", "G3C", "G4A"]}
            loaded
            value={grade}
            onChange={setGrade}
            fieldClassName="w-56"
          />
          <LookupSelect
            listKey="staff_grade_description"
            label="Staff type (value left the list)"
            values={["Gardener Helper", "Irrigation Technician"]}
            loaded
            value={staffType}
            onChange={setStaffType}
            fieldClassName="w-64"
          />
        </Section>

        <Section id="date-picker" title="DatePicker">
          <DatePicker label="Work date" value={date} onChange={setDate} fieldClassName="w-48" />
          <DatePicker label="Empty, optional" value={emptyDate} onChange={setEmptyDate} fieldClassName="w-48" hint="Type 25/11/2026" />
          <DatePicker label="Within November" value={date} onChange={setDate} min="2026-11-01" max="2026-11-30" required fieldClassName="w-48" />
          <DatePicker label="With error" value="" onChange={() => undefined} error="Required" fieldClassName="w-48" />
          <DatePicker label="Disabled" value={date} onChange={() => undefined} disabled fieldClassName="w-48" />
          <DatePicker label="Small" size="sm" value={date} onChange={setDate} fieldClassName="w-40" />
        </Section>

        <Section id="date-range-picker" title="DateRangePicker">
          <DateRangePicker
            label="Period"
            value={range}
            onChange={setRange}
            fieldClassName="w-72"
            presets={[
              { label: "November", from: "2026-11-01", to: "2026-11-30" },
              { label: "October", from: "2026-10-01", to: "2026-10-31" },
              { label: "First week", from: "2026-11-01", to: "2026-11-07" },
            ]}
          />
          <DateRangePicker label="Empty" value={{ from: "", to: "" }} onChange={setRange} fieldClassName="w-72" />
        </Section>

        <Section id="calendar" title="Calendar">
          <Calendar
            value={calendarDay}
            onSelect={setCalendarDay}
            today="2026-11-25"
            markers={{
              "2026-12-01": { tone: "holiday", title: "Commemoration Day" },
              "2026-12-02": { tone: "holiday", title: "National Day" },
              "2026-12-03": { tone: "holiday", title: "National Day" },
              "2026-12-11": { tone: "leave", title: "On leave" },
            }}
            isDateDisabled={(iso) => iso < "2026-11-25"}
          />
          <Calendar range={{ from: "2026-11-09", to: "2026-11-15" }} onSelect={() => undefined} today="2026-11-25" />
        </Section>

        <Section id="tabs" title="Tabs">
          <div className="w-full">
            <Tabs
              idBase="gallery-tabs"
              value={tab}
              onChange={setTab}
              aria-label="Approvals"
              tabs={[
                { id: "pending", label: "Pending", count: 12 },
                { id: "decided", label: "Decided" },
                { id: "all", label: "All history" },
                { id: "archived", label: "Archived", disabled: true },
              ]}
            />
            <TabPanel idBase="gallery-tabs" id={tab} className="py-3 text-fw-sm text-fw-text-muted">
              Panel for "{tab}".
            </TabPanel>
          </div>
        </Section>

        <Section id="menu" title="Menu">
          <Menu
            label="Row actions"
            items={[
              { label: "Edit", icon: <Pencil className="h-3.5 w-3.5" />, onSelect: () => toast.info("Edit") },
              { label: "Duplicate", icon: <Copy className="h-3.5 w-3.5" />, onSelect: () => toast.info("Duplicate") },
              { label: "Archive", disabled: true, onSelect: () => undefined },
              "separator",
              { label: "Delete", icon: <Trash2 className="h-3.5 w-3.5" />, destructive: true, onSelect: () => toast.warning("Delete") },
            ]}
          />
          <Menu label="Export" trigger="Export" align="start" items={[{ label: "Excel", onSelect: () => undefined }, { label: "PDF", onSelect: () => undefined }]} />
        </Section>

        <Section id="tooltip" title="Tooltip">
          <Tooltip content="Planned hours minus worked hours">
            <Badge tone="warning">Short 15 min</Badge>
          </Tooltip>
          <Tooltip content="Opens the worker's day" side="bottom">
            <Button size="sm">Hover or focus me</Button>
          </Tooltip>
        </Section>

        <Section id="badge" title="Badge and CountBadge">
          <Badge>Neutral</Badge>
          <Badge tone="primary">Primary</Badge>
          <Badge tone="success" dot>
            Present
          </Badge>
          <Badge tone="warning" dot>
            Pending review
          </Badge>
          <Badge tone="danger" dot>
            Absent
          </Badge>
          <Badge tone="info">Info</Badge>
          <Badge size="md" tone="primary">
            Medium
          </Badge>
          <CountBadge count={7} />
          <CountBadge count={140} />
        </Section>

        <Section id="empty-state" title="EmptyState">
          <div className="w-80 rounded-fw-lg border border-fw-border">
            <EmptyState title="No reports generated yet" description="Choose a report and a period, then Generate." action={<Button size="sm" variant="primary">Generate</Button>} />
          </div>
          <div className="w-64 rounded-fw-lg border border-fw-border">
            <EmptyState compact title="Nothing pending" />
          </div>
        </Section>

        <Section id="skeleton" title="Skeleton">
          <div className="flex w-64 items-center gap-3">
            <Skeleton circle width={32} />
            <SkeletonText lines={2} className="flex-1" />
          </div>
          <div className="w-96 rounded-fw-lg border border-fw-border">
            <SkeletonTable rows={3} columns={4} />
          </div>
        </Section>

        <Section id="scroll-area" title="ScrollArea (thin scrollbar on hover)">
          <ScrollArea maxHeight={160} className="w-72 rounded-fw-lg border border-fw-border">
            <ul className="divide-y divide-fw-border text-fw-sm">
              {Array.from({ length: 20 }, (_, i) => (
                <li key={i} className="px-3 py-1.5">
                  Worker {2001 + i}
                </li>
              ))}
            </ul>
          </ScrollArea>
          <ScrollArea axis="x" className="w-72 rounded-fw-lg border border-fw-border">
            <div className="flex w-[48rem] gap-2 p-2">
              {Array.from({ length: 14 }, (_, i) => (
                <div key={i} className="h-14 w-24 shrink-0 rounded-fw-md bg-fw-muted p-1 text-fw-xs text-fw-text-muted">
                  Day {i + 1}
                </div>
              ))}
            </div>
          </ScrollArea>
        </Section>
      </div>
    </div>
  );
};
