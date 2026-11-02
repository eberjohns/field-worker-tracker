---
name: finish-phase
description: Use when a phase's work is complete. Verifies the checklist, updates docs and changelog, and prepares the pull request and review notes.
---
1. Go through the phase checklist item by item; for each, state how it was verified (test, demo step, screenshot). List anything unfinished.
2. Make sure docs were updated (including the data model, API spec and mobile contract if touched), an ADR exists for any design decision, and `CHANGELOG.md` has an entry.
3. Run linters, type checks, import-linter and the migration check; report results.
4. Write the pull request description using the template and a short demo script for the reviewer.
5. Do not merge and do not mark the phase done; tell the owner it is ready for review.
