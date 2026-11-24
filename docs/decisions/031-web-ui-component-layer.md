# ADR-031: Web UI component layer (`web/src/ui`)

- **Status:** Accepted
- **Date:** 2026-11-25
- **Batch:** 10 A (`feat/batch10-ui-a`); applied to the pages in Batch 10 B
- **Affects:** `docs/10-ui-views.md` sections 1 and 4 (replaces "Tailwind + shadcn/ui" with this layer)

## Context
The web app grew page by page. It had 65 `window.alert/confirm/prompt` calls, 42 native date inputs
(each browser shows them differently, and they show US-style dates on some machines), and 50 hand-made
`fixed inset-0` overlays in 23 files, each with its own close button, focus handling (mostly none) and
error text. Server errors were shown as "Error 422" or `[object Object]` in places. The Batch 10 brief
asks for one set of building blocks with stable props, tokens in one file, a gallery page, and a check
that stops pages going back to the old patterns.

## Options considered
1. **shadcn/ui on Radix** (what `10-ui-views.md` named): good accessibility, but about ten new Radix
   packages, and copy-pasted sources we would own anyway.
2. **A component library** (MUI, Mantine, Ant): fastest, but heavy, its own styling system next to
   Tailwind, and a new dependency to approve.
3. **Our own small layer on what is installed** (React, Tailwind, `clsx`, `tailwind-merge`,
   `lucide-react`), with the hard parts (focus trap, popover placement, calendar keys) written once
   and tested.

## Decision
Option 3. `web/src/ui/` holds the app's only building blocks: Button, Modal, ConfirmDialog,
toasts and AlertBanner, DatePicker, DateRangePicker, Calendar, ScrollArea, TextField, NumberField,
Select, LookupSelect, Tabs, Menu, Tooltip, Badge, EmptyState, Skeleton and PageHeader.
- **Tokens:** `ui/tokens.css` holds CSS variables (RGB channels, so Tailwind opacity works). The
  `fw-*` Tailwind names map to them. The light theme is defined now; a dark theme later only
  redefines the variables.
- **Dialogs and toasts are services:** `useDialogs().confirm/prompt` returns a promise, so a
  `window.confirm` call becomes one `await`. `useToast().error(err)` shows the server's message and,
  for a 422, one line per field (`ui/errors.ts` reads every error body shape the API sends).
- **Dates:** values stay ISO `YYYY-MM-DD`, as the API uses, and the arithmetic runs on UTC midnights,
  so the browser's time zone never shifts a day. Dates display en-GB ("25 Nov 2026"), and typing
  is day-first ("25/11/2026").
- **Adapters:** a third-party library used by the layer is imported in exactly one file. Today that
  is `clsx` and `tailwind-merge` in `ui/cn.ts`, and `react-dom` portals in `ui/overlay.tsx`.
- **Check:** `pnpm run lint` runs `scripts/check-ui-rules.mjs`. It fails on a new browser dialog,
  native date input, hand-made overlay, or import of a wrapped library. The violations that existed
  when the check arrived are listed in `scripts/ui-rules-baseline.json`. Batch 10 B removes them,
  and the baseline only ever shrinks. A line can opt out with `// ui-rules-allow: <reason>`.
- **Gallery:** `/dev/ui` exists in development builds only. A test checks that every exported
  component appears on it.

## Why
- No new dependency or licence question.
- One look and one keyboard behaviour everywhere.
- Small enough to read in an afternoon.

The check is a script and not ESLint, because the project has no ESLint set up. Adding it would be a
new dependency set, for four regex rules.

## Consequences
- We maintain focus trapping, popover placement and the calendar ourselves; the unit tests and the
  gallery cover them.
- Component tests render to HTML in Node (`renderToStaticMarkup`), using a small TypeScript loader
  (`scripts/register-ts.mjs`) built on the installed `typescript` package. Interaction is checked in
  the gallery, not in a DOM test library.
- The web tests now run in CI (`pnpm run test`).
