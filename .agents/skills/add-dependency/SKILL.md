---
name: add-dependency
description: Use when adding, upgrading or replacing any dependency (Python or JavaScript package, tile provider, external service). Verifies it is actively maintained, compatible and licensed, pins it, and records it.
---
1. Read `.agents/rules/dependencies.md` and `docs/17-dependencies.md`.
2. Look up the package registry and repository: latest release date, release cadence, last commit, open issues about maintenance, licence, and compatibility notes with our pinned majors. If you cannot check these, say so and ask the user.
3. Reject anything not released for about 12 months or archived. Propose an alternative with the same facts.
4. Show the user a one-line verdict per candidate (version, last release, licence, risk) and wait for approval.
5. Install with an exact pin (lock file updated). Add or update the row in `docs/17-dependencies.md` (status and verification date).
6. If this changes an architectural choice, add an ADR (`write-adr` skill).
