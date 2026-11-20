# CLAUDE.md

This repo's agent instructions live in `AGENTS.md`. Read it at the start of every session, then:

1. `.agents/rules/*` (architecture, conventions, dependencies, documentation, phase workflow, safety, time and money)
2. `docs/decisions/decision-register.md`
3. `docs/handover-2026-11-19.md`: current state, owner confirmations, queued work

## Skills
The project's skills are in `.agents/skills/<name>/SKILL.md`. They are not Claude Code skills, so open and follow the matching file yourself:
`add-dependency`, `add-endpoint`, `add-module`, `add-synced-entity`, `db-migration`, `finish-phase`, `import-column`, `start-phase`, `write-adr`.

## Source of truth
`AGENTS.md` makes the client requirements and the decision register the source of truth. Since 18-19 Nov 2026 the **owner confirmations in section 1 of the handover win** wherever they disagree with the requirements doc or the v1.0 PDFs. If any other documents disagree, stop and ask.

## Working agreement
- Work is now done in batches, not phases. One batch per branch; plan first and wait for approval; open a PR; never merge it yourself.
- Before saying anything is done, run the backend tests, ruff check and ruff format --check, pyright, lint-imports, alembic check and the web build. Report the results.
- The mobile app is built by another team. Never change it here. If a change affects the app or `docs/09-mobile-sync-contract.md`, write a note for the mobile team.
- Client data files (`docs/reference/client-files/`) are git-ignored. Read them, but never commit them (golden rule 8).
- Never run anything against a database other than the local docker-compose one. Start it with the repo-root file: `docker compose up -d db` (container `field-worker-tracker-db-1`). Don't use `infra/docker-compose.yml` for the local DB; on the owner's machine its postgis image fails.
- The GitHub repo is public. Never commit real worker names, salaries or other personal data; use Tally IDs in docs.
