---
name: import-column
description: Use when a column is added to, removed from, or changed in the bulk-import workbook, or an import validation rule changes. Keeps template, parser, validator and docs in sync.
---
Read `docs/11-import-pipeline.md` first.
1. Update the sheet definition in the import module's schema registry (single source of truth for sheets and columns).
2. Update parsing and normalization (aliases, type coercion) and the validation rule codes.
3. Update the preview/error report so the new rule shows row-level messages with a stable code.
4. Regenerate the template workbook with `tools/` (the template is generated from the same registry) and add an example value.
5. Update `docs/11-import-pipeline.md` and `docs/import-templates/README.md`.
Imports must stay idempotent: the same file uploaded twice must not create duplicates.
