# 15 - Development Process

## 1. Roles in the loop
You (product owner/PM) decide scope and approve plans and merges. The agent (Antigravity) plans, writes code, writes docs, and opens pull requests. A human reviews every pull request. QA is handled by the testing team.

## 2. Working phase by phase
The build is split into **phases** (`phases/README.md`). Each phase is independent, small enough for one agent session, and has its own **context pack** (the few files to read), **deliverables** and **checklist**.
1. Start a new agent conversation per phase. Tell it: "Work on PHASE-NN. Read only the files listed in its Context section."
2. The agent asks questions, then writes a plan for the phase; **you approve the plan** before code.
3. The agent builds on a branch, edits code and docs together, ticks the phase checklist, opens a pull request, never merges.
4. You review, run it, check the checklist and demo script, then merge.
5. Update the phase status in `phases/README.md`, then start the next phase.
Corrections that repeat become rules or skills (`.agents/`).

## 3. Git
- **GitHub Flow**: protected `main` (PR required, CI required, no direct pushes, linear history via squash merge).
- Branch names: `feat/<module>-<short>`, `fix/<short>`, `docs/<short>`, `chore/<short>`.
- **Conventional Commits**: `feat(scheduling): add recommendation ranking`, `fix(sync): ...`, `docs: ...`, `chore: ...`, `refactor: ...`. Breaking contract changes: `feat(mobile)!:`.
- Tags: `vMAJOR.MINOR.PATCH` for releases. The mobile contract has its own version (`X-Contract-Version`).
- `CODEOWNERS` per module once the team grows. Never commit `.env`, secrets, or client data files.

## 4. Pull request template (`.github/pull_request_template.md`)
```
## What and why
## Related issue / milestone
## Changes (by module)
## Docs updated (list files) and ADR added? 
## Migration? (yes/no, reversible? rollback notes)
## API / mobile contract change? (yes/no; if yes, changelog + approval)
## Settings or rule-pack values touched? (PROPOSED decisions respected?)
## How to try it
## Screenshots (UI)
```

## 5. Definition of Ready / Done
**Ready**: acceptance criteria written, relevant docs identified, decisions it depends on are CONFIRMED or explicitly PROPOSED-with-setting.
**Done**: code merged via reviewed PR; CI green (lint, types, import boundaries, migration check); docs and `CHANGELOG.md` updated; ADR written for design decisions; audit entries for state changes; permission and scope checks in place; no secrets or client data committed; demo-able in staging.

## 6. Review checklist for AI-written code
- Does it respect module boundaries (no cross-module internals) and keep `rules/` pure?
- Time: UTC stored, work date from site country, no naive datetimes? Money: `Decimal`, no floats?
- Is every list/detail query **scope-filtered**? Is the permission dependency present?
- Raw events and finalized records untouched (append-only respected)?
- Settings/rule-pack values used instead of constants? PROPOSED decisions behind settings?
- Migration reversible, indexes added, spatial indexes where needed?
- Sync: does the change emit the right domain event so affected workers get `sync_changes`?
- Errors use stable codes; no secrets/PII in logs.
- Docs and changelog updated; ADR if a design choice was made.

## 7. CI pipeline (GitHub Actions)
On every PR: install with `uv`; `ruff check` and `ruff format --check`; `pyright`; `import-linter`; `alembic upgrade head` on a PostGIS service container then `alembic check` (models match migrations); unit tests for `rules/`; OpenAPI export and diff (flag mobile-contract changes); web `tsc`, lint and build; dependency and secret scans. On merge to `main`: build images, deploy to staging. Production deploy: manual approval, snapshot first.

## 8. Environments
local (docker-compose) -> staging (client demos, anonymized/fictional data) -> production. Promote the same image. Feature flags for unfinished work.

## 9. Local setup (target state after M0)
```
cp .env.example .env
docker compose up -d db            # postgres + postgis
cd backend && uv sync && uv run alembic upgrade head
uv run uvicorn fw.main:app --reload
cd ../web && pnpm install && pnpm dev
```
Seed data comes from `tools/seed/` and uses **fictional** people, never client data.

## 10. Antigravity setup (summary - verify against current docs)
- Rules live in `.agents/rules/`, skills in `.agents/skills/<name>/SKILL.md`, MCP servers in `.agents/mcp_config.json` (older versions used `.agent/`). Keep each rule file small (there is a size cap of roughly 12,000 characters).
- Useful slash commands: a "grill me"/clarify command to have the agent interview you, and `/plan` to produce an implementation plan.
- **MCP servers to add** (start small): GitHub (issues/PRs); PostgreSQL **read-only against the local dev database only**; a library-docs server for FastAPI/SQLAlchemy/PostGIS docs. Keep credentials in environment variables.
- **Terminal approval** stays on for deletes, migrations downward and network calls.
- **Custom MCP later** (only when the agent needs to call our own system): `seed_dev_data`, `import_validator`, `simulate_day` (post fake events to the local API).
- Use `/learn`-style feedback or edit the rules whenever you correct the same mistake twice.

## 11. Dependency policy
Every library, framework and external service is verified before use (release recency, maintenance, licence, compatibility with pinned majors) and recorded with the date in `docs/17-dependencies.md` (rule: `.agents/rules/dependencies.md`, skill: `add-dependency`). Anything not actively released for about 12 months is rejected (as Leaflet was). Versions are pinned with lock files; automated update PRs run monthly; the register is re-checked at the start of each milestone and on major upgrades. Map libraries sit behind a wrapper in `web/src/features/map/`.

## 12. Release and changelog
Keep `CHANGELOG.md` (Keep-a-Changelog format). Each release notes: migrations, settings added, mobile-contract changes. Mobile contract changes are also logged in `09-mobile-sync-contract.md` section 12.
